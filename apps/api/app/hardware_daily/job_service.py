from __future__ import annotations

import asyncio
from uuid import UUID

from app.core.config import get_settings
from app.hardware_daily.adapters import ManualHardwareImportAdapter, WebSearchHardwareAdapter
from app.hardware_daily.catalog import HardwareSearchQueryBuilder
from app.hardware_daily.models import (
    HardwareCategory,
    HardwareQualityStats,
    HardwareScanJob,
    HardwareScanJobStatus,
    HardwareScanMode,
    HardwareScanRequest,
    HardwareSourceRun,
    HardwareSourceRunStatus,
    RawHardwareListing,
    utc_now,
)
from app.hardware_daily.normalizer import HardwareListingNormalizer
from app.hardware_daily.reporter import TelegramHardwareDailyReporter
from app.hardware_daily.scoring import HardwareOpportunityScoringService
from app.hardware_daily.store import hardware_daily_store


class HardwareHunterDailyScheduler:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.query_builder = HardwareSearchQueryBuilder()
        self.normalizer = HardwareListingNormalizer()
        self.scoring = HardwareOpportunityScoringService()
        self.reporter = TelegramHardwareDailyReporter()
        self.adapters = [WebSearchHardwareAdapter(), ManualHardwareImportAdapter()]

    def create_job(self, request: HardwareScanRequest) -> HardwareScanJob:
        categories = request.categories or list(HardwareCategory)
        job = HardwareScanJob(mode=request.mode, categories=categories, states=request.states)
        hardware_daily_store.create_job(job)
        return job

    async def run_job(self, job_id: UUID, request: HardwareScanRequest) -> None:
        job = hardware_daily_store.get_job(job_id)
        if not job:
            return
        try:
            job.status = HardwareScanJobStatus.RUNNING
            job.generated_queries = self.query_builder.build(
                categories=job.categories,
                states=job.states,
                max_queries_per_category=request.max_queries_per_category,
            )
            hardware_daily_store.update_job(job)

            raw_results: list[RawHardwareListing] = []
            if request.mode in {HardwareScanMode.ASSET_LISTING_SEARCH, HardwareScanMode.BOTH}:
                raw_results = await self._run_asset_searches(job, request)

            normalized = [self.normalizer.normalize(raw) for raw in raw_results]
            deduped, duplicates_removed = self._dedupe(normalized)
            remembered = []
            stats = HardwareQualityStats(
                raw_results=len(raw_results),
                normalized_listings=len(normalized),
                duplicates_removed=duplicates_removed,
                failed_sources=len([run for run in job.source_runs if run.status in {HardwareSourceRunStatus.FAILED, HardwareSourceRunStatus.TIMEOUT, HardwareSourceRunStatus.BLOCKED}]),
            )
            for opportunity in deduped:
                key = self.normalizer.opportunity_key(opportunity)
                saved, changes = hardware_daily_store.remember_opportunity(key, opportunity)
                saved.change_types = changes
                stats.new_opportunities += 1 if "NEW" in {change.value for change in changes} else 0
                stats.price_changes += 1 if "PRICE_CHANGED" in {change.value for change in changes} else 0
                stats.quantity_changes += 1 if "QUANTITY_CHANGED" in {change.value for change in changes} else 0
                stats.status_changes += 1 if "STATUS_CHANGED" in {change.value for change in changes} else 0
                remembered.append(saved)

            job.opportunities = self.scoring.score(remembered)[:120]
            stats.final_opportunities = len(job.opportunities)
            stats.high_score_opportunities = len([item for item in job.opportunities if item.opportunity_score >= 60])
            job.quality_stats = stats
            job.status = HardwareScanJobStatus.COMPLETED if job.opportunities else HardwareScanJobStatus.PARTIALLY_COMPLETED
            job.report = await self.reporter.build_and_send(job, force_send=request.send_telegram)
            job.completed_at = utc_now()
            hardware_daily_store.update_job(job)
        except Exception as exc:
            job.status = HardwareScanJobStatus.FAILED
            job.error_message = str(exc)[:500]
            job.completed_at = utc_now()
            hardware_daily_store.update_job(job)

    def get_job(self, job_id: UUID) -> HardwareScanJob | None:
        return hardware_daily_store.get_job(job_id)

    def dashboard(self):
        jobs = hardware_daily_store.list_jobs()
        latest = jobs[0] if jobs else None
        from app.hardware_daily.models import HardwareDashboard

        top = sorted(
            hardware_daily_store.opportunities_by_key.values(),
            key=lambda item: (item.opportunity_score, -item.risk_score),
            reverse=True,
        )[:20]
        return HardwareDashboard(
            total_jobs=len(jobs),
            total_opportunities_seen=len(hardware_daily_store.opportunities_by_key),
            active_opportunities=len(top),
            latest_job=latest,
            telegram_enabled=self.settings.hardware_hunter_telegram_enabled,
            daily_report_hour=self.settings.hardware_hunter_daily_report_hour,
            timezone=self.settings.hardware_hunter_timezone,
            immediate_alerts=self.settings.hardware_hunter_immediate_alerts,
            top_opportunities=top,
        )

    async def generate_report(self, job_id: UUID, send: bool = False):
        job = hardware_daily_store.get_job(job_id)
        if not job:
            return None
        job.report = await self.reporter.build_and_send(job, force_send=send)
        hardware_daily_store.update_job(job)
        return job.report

    async def _run_asset_searches(self, job: HardwareScanJob, request: HardwareScanRequest) -> list[RawHardwareListing]:
        selected_queries = job.generated_queries
        raw_results: list[RawHardwareListing] = []
        web_adapter = self.adapters[0]
        manual_adapter = self.adapters[1]
        for query in selected_queries:
            source_run = HardwareSourceRun(
                source_name=query.source_group,
                adapter_type=web_adapter.adapter_type,
                query=query.generated_query_en,
                category=query.category,
                status=HardwareSourceRunStatus.SEARCHING,
                started_at=utc_now(),
            )
            job.source_runs.append(source_run)
            hardware_daily_store.update_job(job)
            try:
                results = await asyncio.wait_for(web_adapter.search(query, request), timeout=35)
                raw_results.extend(results)
                source_run.status = HardwareSourceRunStatus.SUCCESS
                source_run.result_count = len(results)
                query.status = HardwareSourceRunStatus.SUCCESS
                query.result_count = len(results)
            except asyncio.TimeoutError:
                source_run.status = HardwareSourceRunStatus.TIMEOUT
                source_run.error_message = "Source timed out without blocking the scan."
                query.status = HardwareSourceRunStatus.TIMEOUT
            except Exception as exc:
                source_run.status = self._status_from_exception(exc)
                source_run.error_message = str(exc)[:500]
                query.status = source_run.status
            finally:
                source_run.completed_at = utc_now()
                hardware_daily_store.update_job(job)

        if request.manual_urls or request.manual_text:
            for category in job.categories[:1]:
                manual_query = type("ManualQuery", (), {"generated_query_en": "manual import", "category": category, "source_group": "Manual Import"})
                source_run = HardwareSourceRun(
                    source_name=manual_adapter.source_name,
                    adapter_type=manual_adapter.adapter_type,
                    query="manual import",
                    category=category,
                    status=HardwareSourceRunStatus.SEARCHING,
                    started_at=utc_now(),
                )
                job.source_runs.append(source_run)
                try:
                    results = await manual_adapter.search(manual_query, request)
                    raw_results.extend(results)
                    source_run.status = HardwareSourceRunStatus.SUCCESS
                    source_run.result_count = len(results)
                except Exception as exc:
                    source_run.status = self._status_from_exception(exc)
                    source_run.error_message = str(exc)[:500]
                finally:
                    source_run.completed_at = utc_now()
                    hardware_daily_store.update_job(job)
        return raw_results

    def _dedupe(self, opportunities):
        seen: set[str] = set()
        output = []
        duplicates = 0
        for item in opportunities:
            key = self.normalizer.opportunity_key(item)
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            output.append(item)
        return output, duplicates

    def _status_from_exception(self, exc: Exception) -> HardwareSourceRunStatus:
        message = str(exc).lower()
        if "403" in message or "captcha" in message or "blocked" in message:
            return HardwareSourceRunStatus.BLOCKED
        return HardwareSourceRunStatus.FAILED


hardware_daily_scheduler = HardwareHunterDailyScheduler()
