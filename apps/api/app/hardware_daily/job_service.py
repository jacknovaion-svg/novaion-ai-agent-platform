from __future__ import annotations

import asyncio
from datetime import timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.hardware_daily.adapters import ManualHardwareImportAdapter, WebSearchHardwareAdapter
from app.hardware_daily.catalog import HardwareSearchQueryBuilder
from app.hardware_daily.models import (
    HardwareCategory,
    HardwareQualityStats,
    HardwareResultPageType,
    HardwareSchedulerState,
    SchedulerStatus,
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
        self.scheduler_state = hardware_daily_store.scheduler_state
        self._active_tasks: set[UUID] = set()
        self._queued_tasks: set[UUID] = set()
        self._loop_task: asyncio.Task | None = None
        self._refresh_next_run()

    def start_background_loop(self) -> None:
        if self._loop_task and not self._loop_task.done():
            return
        self._loop_task = asyncio.create_task(self._scheduler_loop())

    def create_job(self, request: HardwareScanRequest) -> HardwareScanJob:
        if self.scheduler_state.is_job_running and self.scheduler_state.current_job_id:
            running_job = hardware_daily_store.get_job(self.scheduler_state.current_job_id)
            if running_job:
                return running_job
        categories = request.categories or list(HardwareCategory)
        job = HardwareScanJob(mode=request.mode, categories=categories, states=request.states)
        hardware_daily_store.create_job(job)
        self._queued_tasks.add(job.id)
        self.scheduler_state.is_job_running = True
        self.scheduler_state.current_job_id = job.id
        hardware_daily_store.save_scheduler_state(self.scheduler_state)
        return job

    def consume_queued_job(self, job_id: UUID) -> bool:
        if job_id not in self._queued_tasks:
            return False
        self._queued_tasks.remove(job_id)
        return True

    async def run_job(self, job_id: UUID, request: HardwareScanRequest) -> None:
        job = hardware_daily_store.get_job(job_id)
        if not job:
            return
        if job_id in self._active_tasks:
            return
        self._active_tasks.add(job_id)
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

            stats = self._quality_stats(raw_results, job)
            specific_raw_results = [raw for raw in raw_results if raw.page_type == HardwareResultPageType.SPECIFIC_LISTING]
            normalized = [self.normalizer.normalize(raw) for raw in specific_raw_results]
            deduped, duplicates_removed = self._dedupe(normalized)
            remembered = []
            stats.normalized_listings = len(normalized)
            stats.duplicates_removed = duplicates_removed
            for opportunity in deduped:
                key = self.normalizer.opportunity_key(opportunity)
                saved, changes = hardware_daily_store.remember_opportunity(key, opportunity)
                saved.change_types = changes
                stats.new_opportunities += 1 if "NEW" in {change.value for change in changes} else 0
                stats.price_changes += 1 if "PRICE_CHANGED" in {change.value for change in changes} else 0
                stats.quantity_changes += 1 if "QUANTITY_CHANGED" in {change.value for change in changes} else 0
                stats.status_changes += 1 if "STATUS_CHANGED" in {change.value for change in changes} else 0
                stats.changed_opportunities += 1 if changes and "NEW" not in {change.value for change in changes} else 0
                remembered.append(saved)

            job.opportunities = self.scoring.score(remembered)[:120]
            stats.final_opportunities = len(job.opportunities)
            stats.high_score_opportunities = len([item for item in job.opportunities if item.opportunity_score >= 60])
            job.quality_stats = stats
            job.status = HardwareScanJobStatus.COMPLETED if job.opportunities else HardwareScanJobStatus.PARTIALLY_COMPLETED
            report_action = "approve_and_send" if request.send_telegram else "preview"
            job.report = await self.reporter.build_and_send(job, action=report_action)
            job.completed_at = utc_now()
            hardware_daily_store.update_job(job)
        except Exception as exc:
            job.status = HardwareScanJobStatus.FAILED
            job.error_message = str(exc)[:500]
            job.completed_at = utc_now()
            hardware_daily_store.update_job(job)
            self.scheduler_state.last_error = str(exc)[:500]
        finally:
            self.scheduler_state.is_job_running = False
            self.scheduler_state.current_job_id = None
            self.scheduler_state.last_job_id = job.id
            self.scheduler_state.last_run_at = job.completed_at or utc_now()
            self._refresh_next_run()
            hardware_daily_store.save_scheduler_state(self.scheduler_state)
            self._active_tasks.discard(job_id)

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
            scheduler=self.scheduler_state,
            top_opportunities=top,
        )

    async def generate_report(self, job_id: UUID, action="preview", message: str | None = None):
        job = hardware_daily_store.get_job(job_id)
        if not job:
            return None
        job.report = await self.reporter.build_and_send(job, action=action, message_override=message)
        hardware_daily_store.update_job(job)
        return job.report

    def scheduler_status(self) -> HardwareSchedulerState:
        self._refresh_next_run()
        return self.scheduler_state

    def pause_scheduler(self) -> HardwareSchedulerState:
        self.scheduler_state.status = SchedulerStatus.PAUSED
        self.scheduler_state.enabled = False
        self.scheduler_state.next_run_at = None
        return hardware_daily_store.save_scheduler_state(self.scheduler_state)

    def resume_scheduler(self) -> HardwareSchedulerState:
        self.scheduler_state.status = SchedulerStatus.RUNNING
        self.scheduler_state.enabled = True
        self._refresh_next_run()
        return hardware_daily_store.save_scheduler_state(self.scheduler_state)

    async def _scheduler_loop(self) -> None:
        while True:
            await asyncio.sleep(60)
            try:
                if not self.scheduler_state.enabled or self.scheduler_state.is_job_running:
                    continue
                if not self.scheduler_state.next_run_at:
                    self._refresh_next_run()
                if not self.scheduler_state.next_run_at or self.scheduler_state.next_run_at > utc_now():
                    continue
                request = HardwareScanRequest(
                    mode=HardwareScanMode.BOTH,
                    categories=list(HardwareCategory),
                    states=[],
                    test_run=False,
                    max_results_per_query=4,
                    max_queries_per_category=8,
                    send_telegram=self.settings.hardware_hunter_telegram_enabled,
                )
                job = self.create_job(request)
                if self.consume_queued_job(job.id):
                    asyncio.create_task(self.run_job(job.id, request))
            except Exception as exc:
                self.scheduler_state.last_error = str(exc)[:500]
                hardware_daily_store.save_scheduler_state(self.scheduler_state)

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

    def _quality_stats(self, raw_results: list[RawHardwareListing], job: HardwareScanJob) -> HardwareQualityStats:
        stats = HardwareQualityStats(
            raw_results=len(raw_results),
            failed_sources=len([run for run in job.source_runs if run.status in {HardwareSourceRunStatus.FAILED, HardwareSourceRunStatus.TIMEOUT, HardwareSourceRunStatus.BLOCKED}]),
        )
        for raw in raw_results:
            if raw.page_type == HardwareResultPageType.SPECIFIC_LISTING:
                stats.specific_listings += 1
            elif raw.page_type == HardwareResultPageType.LISTING_COLLECTION:
                stats.listing_collections += 1
            elif raw.page_type == HardwareResultPageType.SOURCE_PAGE:
                stats.source_pages += 1
            elif raw.page_type == HardwareResultPageType.NEWS_OR_ARTICLE:
                stats.news_or_articles += 1
            else:
                stats.irrelevant += 1
        return stats

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

    def _refresh_next_run(self) -> None:
        self.scheduler_state.daily_report_hour = self.settings.hardware_hunter_daily_report_hour
        self.scheduler_state.timezone = self.settings.hardware_hunter_timezone
        if not self.scheduler_state.enabled:
            return
        try:
            tz = ZoneInfo(self.scheduler_state.timezone)
        except Exception:
            tz = ZoneInfo("America/Los_Angeles")
        now = utc_now().astimezone(tz)
        next_run = now.replace(hour=self.scheduler_state.daily_report_hour, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run = next_run + timedelta(days=1)
        self.scheduler_state.next_run_at = next_run.astimezone(ZoneInfo("UTC"))


hardware_daily_scheduler = HardwareHunterDailyScheduler()
