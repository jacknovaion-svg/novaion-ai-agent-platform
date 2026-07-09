from __future__ import annotations

import asyncio
import hashlib
import json
import threading
from datetime import timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.hardware_daily.adapters import ManualHardwareImportAdapter, WebSearchHardwareAdapter
from app.hardware_daily.browser_import import GovDealsVisibleTextParser
from app.hardware_daily.catalog import HardwareSearchQueryBuilder, SOURCE_CONFIGS
from app.hardware_daily.models import (
    HardwareBrowserImportRequest,
    HardwareCategory,
    HardwareQualityStats,
    HardwareResultPageType,
    HardwareSchedulerState,
    HardwareScanProgress,
    AuctionEndVerificationLevel,
    ListingStatus,
    SchedulerStatus,
    HardwareScanJob,
    HardwareScanJobStatus,
    HardwareScanDepth,
    HardwareScanLane,
    HardwareScanMode,
    HardwareScanRequest,
    HardwareScanScope,
    HardwareSourceRun,
    HardwareSourceHealth,
    HardwareSourceHealthStatus,
    HardwareSourceRunStatus,
    HardwareQueryPerformance,
    HardwareZeroResultReason,
    RawHardwareListing,
    utc_now,
)
from app.hardware_daily.detail_parser import HardwareListingDetailParser
from app.hardware_daily.normalizer import HardwareListingNormalizer
from app.hardware_daily.persistence import hardware_daily_persistence
from app.hardware_daily.reporter import TelegramHardwareDailyReporter
from app.hardware_daily.scoring import HardwareOpportunityScoringService
from app.hardware_daily.state_matcher import hardware_state_matcher
from app.hardware_daily.status_recheck import listing_status_recheck_service
from app.hardware_daily.store import hardware_daily_store


class HardwareHunterDailyScheduler:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.query_builder = HardwareSearchQueryBuilder()
        self.detail_parser = HardwareListingDetailParser()
        self.normalizer = HardwareListingNormalizer()
        self.scoring = HardwareOpportunityScoringService()
        self.reporter = TelegramHardwareDailyReporter()
        self.browser_import_parser = GovDealsVisibleTextParser()
        self.adapters = [WebSearchHardwareAdapter(), ManualHardwareImportAdapter()]
        self.scheduler_state = hardware_daily_store.scheduler_state
        self._active_tasks: set[UUID] = set()
        self._queued_tasks: set[UUID] = set()
        self._cancelled_tasks: set[UUID] = set()
        self._disabled_sources: set[str] = set()
        self._loop_task: asyncio.Task | None = None
        self._store_write_lock = threading.RLock()
        self._recover_interrupted_job()
        self._recover_stale_running_jobs()
        self._recover_orphaned_source_runs()
        self._apply_local_scheduler_default()
        self._refresh_next_run()

    def _recover_interrupted_job(self) -> None:
        if not self.scheduler_state.is_job_running or not self.scheduler_state.current_job_id:
            return
        job = hardware_daily_store.get_job(self.scheduler_state.current_job_id)
        if job and job.status in {HardwareScanJobStatus.CREATED, HardwareScanJobStatus.RUNNING}:
            job.status = HardwareScanJobStatus.FAILED
            job.error_message = "Previous scan was interrupted before completion and was cleared on backend startup."
            job.completed_at = utc_now()
            self._mark_unfinished_source_runs_failed(job)
            hardware_daily_store.update_job(job)
        self.scheduler_state.is_job_running = False
        self.scheduler_state.current_job_id = None
        self.scheduler_state.last_error = "Recovered interrupted scan from previous backend process."
        hardware_daily_store.save_scheduler_state(self.scheduler_state)

    def _recover_stale_running_jobs(self) -> None:
        current_job_id = self.scheduler_state.current_job_id if self.scheduler_state.is_job_running else None
        recovered = 0
        now = utc_now()
        for job in hardware_daily_store.list_jobs():
            if job.status not in {HardwareScanJobStatus.CREATED, HardwareScanJobStatus.RUNNING}:
                continue
            if current_job_id and job.id == current_job_id:
                continue
            job.status = HardwareScanJobStatus.FAILED
            job.error_message = "Scan was interrupted before completion and was cleared on backend startup."
            job.completed_at = now
            self._mark_unfinished_source_runs_failed(job, now=now)
            hardware_daily_store.update_job(job)
            recovered += 1
        if recovered:
            self.scheduler_state.last_error = f"Recovered {recovered} stale running scan job(s) from previous backend process."
            hardware_daily_store.save_scheduler_state(self.scheduler_state)

    def _recover_orphaned_source_runs(self) -> None:
        recovered = 0
        for job in hardware_daily_store.list_jobs():
            if job.status in {HardwareScanJobStatus.CREATED, HardwareScanJobStatus.RUNNING}:
                continue
            if self._mark_unfinished_source_runs_failed(job):
                hardware_daily_store.update_job(job)
                recovered += 1
        if recovered:
            self.scheduler_state.last_error = f"Recovered unfinished source runs on {recovered} completed/interrupted scan job(s)."
            hardware_daily_store.save_scheduler_state(self.scheduler_state)

    def _mark_unfinished_source_runs_failed(self, job: HardwareScanJob, now=None) -> bool:
        finished_at = now or utc_now()
        changed = False
        for run in job.source_runs:
            if run.status in {HardwareSourceRunStatus.PENDING, HardwareSourceRunStatus.SEARCHING, HardwareSourceRunStatus.RUNNING}:
                run.status = HardwareSourceRunStatus.FAILED
                run.completed_at = finished_at
                run.error_message = "Parent scan job was interrupted before completion."
                changed = True
        return changed

    def _apply_local_scheduler_default(self) -> None:
        if self.settings.hardware_hunter_scheduler_enabled:
            return
        if self.scheduler_state.enabled or self.scheduler_state.status != SchedulerStatus.PAUSED:
            self.scheduler_state.status = SchedulerStatus.PAUSED
            self.scheduler_state.enabled = False
            self.scheduler_state.next_run_at = None
            self.scheduler_state.last_error = "Scheduler is paused by local development default."
            hardware_daily_store.save_scheduler_state(self.scheduler_state)

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
        job_states = request.states if request.scan_scope == HardwareScanScope.LEGACY_STATE else []
        job = HardwareScanJob(mode=request.mode, categories=categories, states=job_states, scan_scope=request.scan_scope, scan_lane=request.scan_lane)
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

    def cancel_job(self, job_id: UUID) -> HardwareScanJob | None:
        job = hardware_daily_store.get_job(job_id)
        if not job:
            return None
        if job.status not in {HardwareScanJobStatus.CREATED, HardwareScanJobStatus.RUNNING}:
            return job
        self._cancelled_tasks.add(job_id)
        now = utc_now()
        job.status = HardwareScanJobStatus.CANCELLED
        job.completed_at = now
        job.error_message = "Scan stopped by user. Completed source runs were saved; unfinished workers were cancelled."
        for run in job.source_runs:
            if run.status in {HardwareSourceRunStatus.PENDING, HardwareSourceRunStatus.SEARCHING, HardwareSourceRunStatus.RUNNING}:
                run.status = HardwareSourceRunStatus.CANCELLED
                run.completed_at = now
                run.error_message = "Source worker cancelled by user."
        hardware_daily_store.update_job(job)
        if self.scheduler_state.current_job_id == job_id:
            self.scheduler_state.is_job_running = False
            self.scheduler_state.current_job_id = None
            self.scheduler_state.last_job_id = job_id
            self.scheduler_state.last_run_at = now
            hardware_daily_store.save_scheduler_state(self.scheduler_state)
        return job

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
                scan_depth=request.scan_depth,
                scan_lane=request.scan_lane,
                scan_scope=request.scan_scope,
            )
            if request.scan_lane == HardwareScanLane.FAST:
                job.generated_queries.extend(
                    self.query_builder.planned_deep_queries(
                        categories=job.categories,
                        states=job.states,
                        scan_depth=request.scan_depth,
                        scan_scope=request.scan_scope,
                    )
                )
            await self._update_job_async(job)

            raw_results: list[RawHardwareListing] = []
            if request.mode in {HardwareScanMode.ASSET_LISTING_SEARCH, HardwareScanMode.BOTH}:
                raw_results = await self._run_asset_searches(job, request)

            cancelled = self._is_cancelled(job_id)
            if cancelled:
                raw_results = [raw for raw in raw_results if raw.raw_data.get("source_run_id")]

            specific_raw_results = [raw for raw in raw_results if raw.page_type == HardwareResultPageType.SPECIFIC_LISTING]
            if cancelled:
                enriched_specific_results = specific_raw_results
            else:
                enriched_specific_results = await self._enrich_specific_listings(specific_raw_results)
                raw_results = self._replace_enriched_results(raw_results, enriched_specific_results)
            self._apply_state_matching(raw_results, job)
            stats = self._quality_stats(raw_results, job)
            eligible_specific_results = [
                raw
                for raw in raw_results
                if raw.page_type == HardwareResultPageType.SPECIFIC_LISTING
                and (job.scan_scope != HardwareScanScope.LEGACY_STATE or raw.raw_data.get("state_match_status") != "mismatched")
            ]
            normalized = [listing_status_recheck_service._apply_status_rules(self.normalizer.normalize(raw)) for raw in eligible_specific_results]
            deduped, duplicates_removed = self._dedupe(normalized)
            remembered = []
            stats.normalized_listings = len(normalized)
            stats.duplicates_removed = duplicates_removed
            for opportunity in deduped:
                key = self.normalizer.opportunity_key(opportunity)
                saved, changes = await self._remember_opportunity_async(key, opportunity, job.id)
                saved.change_types = changes
                is_current = self._is_current_opportunity(saved)
                if is_current and "NEW" in {change.value for change in changes}:
                    stats.new_opportunities += 1
                stats.price_changes += 1 if "PRICE_CHANGED" in {change.value for change in changes} else 0
                stats.quantity_changes += 1 if "QUANTITY_CHANGED" in {change.value for change in changes} else 0
                stats.status_changes += 1 if "STATUS_CHANGED" in {change.value for change in changes} else 0
                stats.changed_opportunities += 1 if is_current and changes and "NEW" not in {change.value for change in changes} else 0
                remembered.append(saved)

            scored = self.scoring.score(remembered)
            self._apply_source_run_opportunity_counts(job, scored)
            stats.active_opportunities = len([item for item in scored if item.listing_status == ListingStatus.ACTIVE])
            stats.ending_soon = len([item for item in scored if item.listing_status == ListingStatus.ENDING_SOON])
            stats.expired_removed = len([item for item in scored if self._is_history_opportunity(item)])
            stats.unavailable_links = len([item for item in scored if item.listing_status == ListingStatus.UNAVAILABLE])
            stats.needs_manual_review = len([item for item in scored if self._is_needs_review_opportunity(item)])
            job.opportunities = [item for item in scored if self._is_current_opportunity(item)][:120]
            stats.final_opportunities = len(job.opportunities)
            stats.high_score_opportunities = len([item for item in job.opportunities if item.opportunity_score >= 60])
            job.quality_stats = stats
            if cancelled:
                job.status = HardwareScanJobStatus.CANCELLED
                job.error_message = "Scan stopped by user. Completed source runs were saved; cancelled source runs were skipped."
            else:
                job.status = HardwareScanJobStatus.COMPLETED if job.opportunities else HardwareScanJobStatus.PARTIALLY_COMPLETED
                report_action = "approve_and_send" if request.send_telegram else "preview"
                job.report = await self.reporter.build_and_send(job, action=report_action)
            job.completed_at = utc_now()
            await self._update_job_async(job)
            await self._save_scan_job_async(job)
        except Exception as exc:
            job.status = HardwareScanJobStatus.FAILED
            job.error_message = str(exc)[:500]
            job.completed_at = utc_now()
            await self._update_job_async(job)
            await self._save_scan_job_async(job)
            self.scheduler_state.last_error = str(exc)[:500]
        finally:
            self.scheduler_state.is_job_running = False
            self.scheduler_state.current_job_id = None
            self.scheduler_state.last_job_id = job.id
            self.scheduler_state.last_run_at = job.completed_at or utc_now()
            self._refresh_next_run()
            await self._save_scheduler_state_async()
            self._active_tasks.discard(job_id)
            self._cancelled_tasks.discard(job_id)

    async def import_browser_visible_page(self, payload: HardwareBrowserImportRequest) -> HardwareScanJob:
        job = HardwareScanJob(
            mode=HardwareScanMode.ASSET_LISTING_SEARCH,
            categories=[payload.category],
            states=[],
            scan_scope=HardwareScanScope.NATIONWIDE,
            scan_lane=HardwareScanLane.FAST,
        )
        hardware_daily_store.create_job(job)
        job.status = HardwareScanJobStatus.RUNNING
        started_at = utc_now()
        source_run = HardwareSourceRun(
            source_name=payload.source_name,
            adapter_type="browser_assisted_visible_text",
            query=str(payload.source_url),
            expanded_query=str(payload.source_url),
            category=payload.category,
            status=HardwareSourceRunStatus.SEARCHING,
            started_at=started_at,
        )
        job.source_runs.append(source_run)
        await self._update_job_async(job)
        try:
            raw = self.browser_import_parser.parse(str(payload.source_url), payload.visible_text, payload.category)
            raw.raw_data["captured_by"] = payload.captured_by or "browser_assisted_import"
            raw.raw_data["source_run_id"] = str(source_run.id)
            raw.detail_checked_at = utc_now()
            raw.detail_parse_status = "browser_visible_text_parsed"
            raw_results = [raw]
            self._apply_state_matching(raw_results, job)
            stats = self._quality_stats(raw_results, job)
            normalized = [listing_status_recheck_service._apply_status_rules(self.normalizer.normalize(raw))]
            remembered = []
            for opportunity in normalized:
                key = self.normalizer.opportunity_key(opportunity)
                saved, changes = await self._remember_opportunity_async(key, opportunity, job.id)
                saved.change_types = changes
                remembered.append(saved)
            scored = self.scoring.score(remembered)
            self._apply_source_run_opportunity_counts(job, scored)
            source_run.status = HardwareSourceRunStatus.SUCCESS
            source_run.result_count = len(raw_results)
            source_run.raw_results = len(raw_results)
            source_run.specific_listing_count = len(raw_results)
            source_run.completed_at = utc_now()
            stats.normalized_listings = len(normalized)
            stats.active_opportunities = len([item for item in scored if item.listing_status == ListingStatus.ACTIVE])
            stats.ending_soon = len([item for item in scored if item.listing_status == ListingStatus.ENDING_SOON])
            stats.expired_removed = len([item for item in scored if self._is_history_opportunity(item)])
            stats.needs_manual_review = len([item for item in scored if self._is_needs_review_opportunity(item)])
            job.opportunities = [item for item in scored if self._is_current_opportunity(item)][:120]
            stats.final_opportunities = len(job.opportunities)
            stats.high_score_opportunities = len([item for item in job.opportunities if item.opportunity_score >= 60])
            job.quality_stats = stats
            job.status = HardwareScanJobStatus.COMPLETED if job.opportunities else HardwareScanJobStatus.PARTIALLY_COMPLETED
            job.report = await self.reporter.build_and_send(job, action="preview")
        except Exception as exc:
            source_run.status = HardwareSourceRunStatus.FAILED
            source_run.error_message = str(exc)[:500]
            source_run.completed_at = utc_now()
            job.status = HardwareScanJobStatus.FAILED
            job.error_message = str(exc)[:500]
        finally:
            job.completed_at = utc_now()
            await self._update_job_async(job)
            await self._save_scan_job_async(job)
        return job

    def _is_cancelled(self, job_id: UUID) -> bool:
        return job_id in self._cancelled_tasks

    async def _update_job_async(self, job: HardwareScanJob) -> None:
        await asyncio.to_thread(self._update_job_sync, job)

    async def _save_scan_job_async(self, job: HardwareScanJob) -> None:
        await asyncio.to_thread(self._save_scan_job_sync, job)

    async def _save_scheduler_state_async(self) -> None:
        await asyncio.to_thread(self._save_scheduler_state_sync)

    async def _remember_opportunity_async(self, key: str, opportunity, job_id: UUID):
        return await asyncio.to_thread(self._remember_opportunity_sync, key, opportunity, job_id)

    async def _get_query_cache_async(self, cache_key: str, ttl_minutes: int):
        return await asyncio.to_thread(self._get_query_cache_sync, cache_key, ttl_minutes)

    async def _set_query_cache_async(self, cache_key: str, payload: dict) -> None:
        await asyncio.to_thread(self._set_query_cache_sync, cache_key, payload)

    def _update_job_sync(self, job: HardwareScanJob) -> None:
        with self._store_write_lock:
            hardware_daily_store.update_job(job)

    def _save_scan_job_sync(self, job: HardwareScanJob) -> None:
        with self._store_write_lock:
            hardware_daily_persistence.save_scan_job(job)

    def _save_scheduler_state_sync(self) -> None:
        with self._store_write_lock:
            hardware_daily_store.save_scheduler_state(self.scheduler_state)

    def _remember_opportunity_sync(self, key: str, opportunity, job_id: UUID):
        with self._store_write_lock:
            return hardware_daily_store.remember_opportunity(key, opportunity, job_id=job_id)

    def _get_query_cache_sync(self, cache_key: str, ttl_minutes: int):
        with self._store_write_lock:
            return hardware_daily_store.get_cached_query(cache_key, ttl_minutes)

    def _set_query_cache_sync(self, cache_key: str, payload: dict) -> None:
        with self._store_write_lock:
            hardware_daily_store.set_cached_query(cache_key, payload)

    def get_job(self, job_id: UUID) -> HardwareScanJob | None:
        return hardware_daily_store.get_job(job_id)

    def scan_progress(self, job_id: UUID) -> HardwareScanProgress | None:
        job = hardware_daily_store.get_job(job_id)
        if not job:
            return None
        runs = job.source_runs
        executable_runs = [run for run in runs if run.status != HardwareSourceRunStatus.PLANNED]
        fast_runs = [run for run in runs if run.scan_lane == HardwareScanLane.FAST and run.status != HardwareSourceRunStatus.PLANNED]
        deep_runs = [run for run in runs if run.scan_lane == HardwareScanLane.DEEP and run.status != HardwareSourceRunStatus.PLANNED]
        completed_statuses = {
            HardwareSourceRunStatus.SUCCESS,
            HardwareSourceRunStatus.ZERO_RESULTS,
            HardwareSourceRunStatus.FAILED,
            HardwareSourceRunStatus.TIMEOUT,
            HardwareSourceRunStatus.BLOCKED,
            HardwareSourceRunStatus.SKIPPED_CACHE,
            HardwareSourceRunStatus.DISABLED,
            HardwareSourceRunStatus.CANCELLED,
        }
        running = [run for run in executable_runs if run.status in {HardwareSourceRunStatus.SEARCHING, HardwareSourceRunStatus.RUNNING}]
        durations = [run.duration_ms for run in executable_runs if run.duration_ms]
        avg_duration = int(sum(durations) / len(durations)) if durations else None
        remaining = max(0, len(executable_runs) - len([run for run in executable_runs if run.status in completed_statuses]))
        return HardwareScanProgress(
            job_id=job.id,
            status=job.status,
            scan_lane=job.scan_lane,
            overall_total=len(executable_runs),
            overall_completed=len([run for run in executable_runs if run.status in completed_statuses]),
            fast_total=len(fast_runs),
            fast_completed=len([run for run in fast_runs if run.status in completed_statuses]),
            deep_total=len(deep_runs),
            deep_completed=len([run for run in deep_runs if run.status in completed_statuses]),
            running_workers=len(running),
            completed_workers=len([run for run in executable_runs if run.status in completed_statuses]),
            timed_out_workers=len([run for run in executable_runs if run.status == HardwareSourceRunStatus.TIMEOUT]),
            failed_workers=len([run for run in executable_runs if run.status in {HardwareSourceRunStatus.FAILED, HardwareSourceRunStatus.BLOCKED}]),
            cache_hits=len([run for run in executable_runs if run.cache_hit or run.status == HardwareSourceRunStatus.SKIPPED_CACHE]),
            current_source=running[0].source_name if running else None,
            estimated_remaining_seconds=int((avg_duration or 0) * remaining / 1000) if avg_duration else None,
            worker_runs=runs,
        )

    def source_health(self) -> list[HardwareSourceHealth]:
        runs = [run for job in hardware_daily_store.list_jobs() for run in job.source_runs if run.status != HardwareSourceRunStatus.PLANNED]
        by_source: dict[str, list[HardwareSourceRun]] = {}
        for run in runs:
            by_source.setdefault(run.source_name, []).append(run)
        health: list[HardwareSourceHealth] = []
        for source_name, source_runs in by_source.items():
            total = len(source_runs)
            success_runs = len([run for run in source_runs if run.status in {HardwareSourceRunStatus.SUCCESS, HardwareSourceRunStatus.SKIPPED_CACHE}])
            zero_result_runs = len([run for run in source_runs if run.status == HardwareSourceRunStatus.ZERO_RESULTS or (run.result_count == 0 and run.status == HardwareSourceRunStatus.SUCCESS)])
            failed_runs = len([run for run in source_runs if run.status in {HardwareSourceRunStatus.FAILED, HardwareSourceRunStatus.BLOCKED}])
            timeout_runs = len([run for run in source_runs if run.status == HardwareSourceRunStatus.TIMEOUT])
            raw_results = sum(run.raw_results or run.result_count for run in source_runs)
            specific = sum(run.specific_listing_count for run in source_runs)
            matched = sum(run.matched_state_results for run in source_runs)
            mismatch = sum(run.state_mismatch_results for run in source_runs)
            unknown = sum(run.location_unknown_results for run in source_runs)
            durations = [run.duration_ms for run in source_runs if run.duration_ms]
            avg_duration = sum(durations) / len(durations) if durations else 0
            result_rate = (len([run for run in source_runs if run.result_count > 0]) / total) if total else 0
            specific_rate = (specific / raw_results) if raw_results else 0
            state_total = matched + mismatch + unknown
            state_match_rate = (matched / state_total) if state_total else 0
            needs_review = sum(run.needs_review for run in source_runs)
            current = sum(run.current_opportunities for run in source_runs)
            history = sum(run.history for run in source_runs)
            needs_review_rate = (needs_review / max(1, current + needs_review + history))
            status = self._source_health_status(total, failed_runs, timeout_runs, zero_result_runs, avg_duration, mismatch, raw_results, result_rate)
            health.append(
                HardwareSourceHealth(
                    source_name=source_name,
                    scan_lane=source_runs[-1].scan_lane,
                    total_runs=total,
                    success_runs=success_runs,
                    zero_result_runs=zero_result_runs,
                    failed_runs=failed_runs,
                    timeout_runs=timeout_runs,
                    raw_results=raw_results,
                    matched_state_results=matched,
                    state_mismatch_results=mismatch,
                    location_unknown_results=unknown,
                    specific_listings=specific,
                    current_opportunities=current,
                    needs_review=needs_review,
                    history=history,
                    avg_duration_ms=avg_duration,
                    result_rate=result_rate,
                    specific_listing_rate=specific_rate,
                    state_match_rate=state_match_rate,
                    needs_review_rate=needs_review_rate,
                    last_success_at=max([run.completed_at for run in source_runs if run.status in {HardwareSourceRunStatus.SUCCESS, HardwareSourceRunStatus.SKIPPED_CACHE} and run.completed_at], default=None),
                    last_failure_at=max([run.completed_at for run in source_runs if run.status in {HardwareSourceRunStatus.FAILED, HardwareSourceRunStatus.TIMEOUT, HardwareSourceRunStatus.BLOCKED} and run.completed_at], default=None),
                    health_status=status,
                )
            )
        return sorted(health, key=lambda item: item.source_name)

    def query_performance(self) -> list[HardwareQueryPerformance]:
        runs = [run for job in hardware_daily_store.list_jobs() for run in job.source_runs if run.query_template_id and run.status != HardwareSourceRunStatus.PLANNED]
        by_key: dict[str, list[HardwareSourceRun]] = {}
        for run in runs:
            key = self._run_query_performance_key(run)
            by_key.setdefault(key, []).append(run)
        output: list[HardwareQueryPerformance] = []
        for key, rows in by_key.items():
            sorted_rows = sorted(rows, key=lambda run: run.started_at or utc_now())
            consecutive_zero = 0
            consecutive_failures = 0
            for run in reversed(sorted_rows):
                if run.result_count == 0 and run.status in {HardwareSourceRunStatus.SUCCESS, HardwareSourceRunStatus.ZERO_RESULTS, HardwareSourceRunStatus.SKIPPED_CACHE}:
                    consecutive_zero += 1
                else:
                    break
            for run in reversed(sorted_rows):
                if run.status in {HardwareSourceRunStatus.FAILED, HardwareSourceRunStatus.TIMEOUT, HardwareSourceRunStatus.BLOCKED}:
                    consecutive_failures += 1
                else:
                    break
            priority = "normal"
            if consecutive_failures >= 5:
                priority = "unstable"
            elif consecutive_zero >= 5:
                priority = "low_yield"
            elif consecutive_zero >= 3:
                priority = "deprioritize"
            elif sum(run.specific_listing_count for run in rows) >= 3:
                priority = "promote_to_fast"
            latest = sorted_rows[-1]
            output.append(
                HardwareQueryPerformance(
                    query_key=key,
                    source_name=latest.source_name,
                    category=latest.category,
                    state_code=latest.state_code,
                    query_template=latest.query_template,
                    scan_lane=latest.scan_lane,
                    total_runs=len(rows),
                    consecutive_zero_results=consecutive_zero,
                    consecutive_failures=consecutive_failures,
                    raw_results=sum(run.raw_results or run.result_count for run in rows),
                    specific_listings=sum(run.specific_listing_count for run in rows),
                    priority_status=priority,
                    last_run_at=latest.completed_at or latest.started_at,
                )
            )
        return sorted(output, key=lambda item: (item.priority_status, item.source_name, item.query_template or ""))

    def clear_query_cache(self) -> dict:
        count = hardware_daily_store.clear_query_cache()
        return {"cleared": count}

    def set_source_enabled(self, source_name: str, enabled: bool) -> dict:
        normalized = source_name.strip()
        if not normalized:
            return {"source_name": source_name, "enabled": enabled, "error": "Missing source name"}
        if enabled:
            self._disabled_sources.discard(normalized)
        else:
            self._disabled_sources.add(normalized)
        return {"source_name": normalized, "enabled": enabled}

    def dashboard(self):
        hardware_daily_persistence.refresh_counts()
        jobs = hardware_daily_store.list_jobs()
        latest = jobs[0] if jobs else None
        from app.hardware_daily.models import HardwareDashboard

        all_opportunities = list(hardware_daily_store.opportunities_by_key.values())
        current = [item for item in all_opportunities if self._is_current_opportunity(item)]
        history = [item for item in all_opportunities if self._is_history_opportunity(item)]
        needs_review = [item for item in all_opportunities if self._is_needs_review_opportunity(item)]
        top = sorted(
            current,
            key=lambda item: (item.opportunity_score, -item.risk_score),
            reverse=True,
        )[:20]
        latest_for_dashboard = latest.model_copy(deep=True) if latest else None
        if latest_for_dashboard:
            latest_for_dashboard.opportunities = [
                item
                for item in current
                if item.last_seen_job_id == latest_for_dashboard.id
                or item.last_updated_job_id == latest_for_dashboard.id
                or item.first_seen_job_id == latest_for_dashboard.id
            ][:120]
        return HardwareDashboard(
            total_jobs=len(jobs),
            total_opportunities_seen=len(hardware_daily_store.opportunities_by_key),
            active_opportunities=len(current),
            latest_job=latest_for_dashboard,
            telegram_enabled=self.settings.hardware_hunter_telegram_enabled,
            daily_report_hour=self.settings.hardware_hunter_daily_report_hour,
            timezone=self.settings.hardware_hunter_timezone,
            immediate_alerts=self.settings.hardware_hunter_immediate_alerts,
            scheduler=self.scheduler_state,
            persistence_mode=hardware_daily_persistence.status.mode,
            persistence_warning=hardware_daily_persistence.status.warning,
            database_health=hardware_daily_persistence.status.database_health,
            database_error=hardware_daily_persistence.status.error,
            database_url_configured=hardware_daily_persistence.status.database_url_configured,
            stored_opportunities=hardware_daily_persistence.status.stored_opportunities,
            stored_history_records=hardware_daily_persistence.status.stored_history_records,
            stored_needs_review_records=hardware_daily_persistence.status.stored_needs_review_records,
            last_successful_database_write=hardware_daily_persistence.status.last_successful_write_at,
            migration_version=hardware_daily_persistence.status.migration_version,
            top_opportunities=top,
            history_opportunities=sorted(history, key=lambda item: item.last_seen_at, reverse=True)[:80],
            needs_review_opportunities=sorted(needs_review, key=lambda item: item.last_seen_at, reverse=True)[:80],
            source_health=self.source_health(),
        )

    async def generate_report(self, job_id: UUID, action="preview", message: str | None = None):
        job = hardware_daily_store.get_job(job_id)
        if not job:
            return None
        job.report = await self.reporter.build_and_send(job, action=action, message_override=message)
        hardware_daily_store.update_job(job)
        return job.report

    async def recheck_opportunity(self, opportunity_id: UUID):
        for item in hardware_daily_store.opportunities_by_key.values():
            if item.opportunity_id == opportunity_id:
                return await listing_status_recheck_service.recheck_opportunity(item)
        return None

    async def bulk_recheck(self, limit: int = 80):
        return await listing_status_recheck_service.bulk_recheck(limit=limit)

    def manual_status_review(self, opportunity_id: UUID, payload):
        return listing_status_recheck_service.apply_manual_review(str(opportunity_id), payload)

    async def bulk_manual_review(self, payload):
        from app.hardware_daily.models import HardwareBulkReviewResult, HardwareManualStatusReviewRequest

        result = HardwareBulkReviewResult()
        for opportunity_id in payload.opportunity_ids:
            try:
                if payload.review_action == "recheck":
                    updated = await self.recheck_opportunity(opportunity_id)
                else:
                    status = payload.manual_status or ListingStatus.NEEDS_MANUAL_REVIEW
                    updated = listing_status_recheck_service.apply_manual_review(
                        str(opportunity_id),
                        HardwareManualStatusReviewRequest(
                            manual_status=status,
                            review_action=payload.review_action,
                            review_notes=payload.review_notes,
                            verified_by=payload.verified_by,
                        ),
                    )
                if updated:
                    result.updated += 1
                else:
                    result.failed += 1
            except Exception:
                result.failed += 1
        return result

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
                    scan_depth=HardwareScanDepth.STANDARD,
                    send_telegram=self.settings.hardware_hunter_telegram_enabled,
                )
                job = self.create_job(request)
                if self.consume_queued_job(job.id):
                    asyncio.create_task(self.run_job(job.id, request))
            except Exception as exc:
                self.scheduler_state.last_error = str(exc)[:500]
                hardware_daily_store.save_scheduler_state(self.scheduler_state)

    async def _run_asset_searches(self, job: HardwareScanJob, request: HardwareScanRequest) -> list[RawHardwareListing]:
        selected_queries = [query for query in job.generated_queries if query.scan_lane == request.scan_lane and query.status != HardwareSourceRunStatus.PLANNED]
        planned_queries = [query for query in job.generated_queries if query.status == HardwareSourceRunStatus.PLANNED]
        raw_results: list[RawHardwareListing] = []
        web_adapter = self.adapters[0]
        manual_adapter = self.adapters[1]
        semaphore = asyncio.Semaphore(4)

        async def run_query(query) -> list[RawHardwareListing]:
            timeout_seconds = self._query_timeout_seconds(query.scan_lane, query.source_group)
            if self._is_cancelled(job.id):
                query.status = HardwareSourceRunStatus.CANCELLED
                return []
            async with semaphore:
                if self._is_cancelled(job.id):
                    query.status = HardwareSourceRunStatus.CANCELLED
                    return []
                source_run = HardwareSourceRun(
                    source_name=query.source_group,
                    adapter_type=web_adapter.adapter_type,
                    query=query.generated_query_en,
                    expanded_query=query.generated_query_en,
                    query_template_id=query.query_template_id,
                    query_template=query.query_template,
                    state_code=query.state_code,
                    state_name=query.state_name,
                    scan_depth=query.scan_depth,
                    scan_lane=query.scan_lane,
                    category=query.category,
                    status=HardwareSourceRunStatus.RUNNING,
                    started_at=utc_now(),
                    timeout_seconds=timeout_seconds,
                )
                job.source_runs.append(source_run)
                await self._update_job_async(job)
                try:
                    if self._is_cancelled(job.id):
                        source_run.status = HardwareSourceRunStatus.CANCELLED
                        source_run.error_message = "Source worker cancelled before execution."
                        query.status = HardwareSourceRunStatus.CANCELLED
                        return []
                    if query.source_group in self._disabled_sources:
                        source_run.status = HardwareSourceRunStatus.DISABLED
                        source_run.error_message = "Source disabled by local operator."
                        query.status = HardwareSourceRunStatus.DISABLED
                        return []
                    cache_key = self._query_cache_key(query)
                    ttl_minutes = self._cache_ttl_minutes(query.scan_lane)
                    cached_results = await self._get_query_cache_async(cache_key, ttl_minutes) if self.settings.hardware_query_cache_enabled else None
                    if cached_results is not None:
                        results = self._hydrate_cached_results(cached_results)
                        for result in results:
                            result.raw_data["source_run_id"] = str(source_run.id)
                            result.raw_data["cache_hit"] = True
                        source_run.status = HardwareSourceRunStatus.SKIPPED_CACHE
                        source_run.cache_hit = True
                        source_run.result_count = len(results)
                        source_run.raw_results = len(results)
                        source_run.specific_listing_count = len([item for item in results if item.page_type == HardwareResultPageType.SPECIFIC_LISTING])
                        query.status = HardwareSourceRunStatus.SKIPPED_CACHE
                        query.result_count = len(results)
                        query.specific_listing_count = source_run.specific_listing_count
                        return results
                    results = await asyncio.wait_for(web_adapter.search(query, request), timeout=timeout_seconds)
                    if self._is_cancelled(job.id):
                        source_run.status = HardwareSourceRunStatus.CANCELLED
                        source_run.error_message = "Source worker result discarded because scan was stopped by user."
                        query.status = HardwareSourceRunStatus.CANCELLED
                        return []
                    for result in results:
                        result.raw_data["source_run_id"] = str(source_run.id)
                        result.raw_data["requested_state"] = query.state_code
                        result.raw_data["requested_states"] = [query.state_code] if query.state_code else []
                        result.raw_data["matched_keywords"] = [query.query_template] if query.query_template else []
                        result.raw_data["scan_scope"] = job.scan_scope.value
                        result.requested_states = [query.state_code] if query.state_code else []
                    if self.settings.hardware_query_cache_enabled:
                        await self._set_query_cache_async(
                            cache_key,
                            {
                                "source_name": query.source_group,
                                "category": query.category.value,
                                "state_code": query.state_code,
                                "query_normalized": self._normalize_query_key(query.generated_query_en),
                                "scan_depth": query.scan_depth.value,
                                "scan_lane": query.scan_lane.value,
                                "raw_results": self._serialize_raw_results(results),
                                "result_count": len(results),
                                "expires_at": utc_now() + timedelta(minutes=ttl_minutes),
                            },
                        )
                    source_run.status = HardwareSourceRunStatus.SUCCESS if results else HardwareSourceRunStatus.ZERO_RESULTS
                    source_run.result_count = len(results)
                    source_run.raw_results = len(results)
                    source_run.specific_listing_count = len([item for item in results if item.page_type == HardwareResultPageType.SPECIFIC_LISTING])
                    source_run.zero_result_reason = self._zero_result_reason(source_run, results)
                    query.status = HardwareSourceRunStatus.SUCCESS if results else HardwareSourceRunStatus.ZERO_RESULTS
                    query.result_count = len(results)
                    query.specific_listing_count = source_run.specific_listing_count
                    query.zero_result_reason = source_run.zero_result_reason
                    return results
                except asyncio.TimeoutError:
                    source_run.status = HardwareSourceRunStatus.TIMEOUT
                    source_run.error_message = "Source timed out without blocking the scan."
                    source_run.zero_result_reason = HardwareZeroResultReason.SOURCE_TIMEOUT
                    query.status = HardwareSourceRunStatus.TIMEOUT
                    query.zero_result_reason = source_run.zero_result_reason
                    return []
                except Exception as exc:
                    source_run.status = self._status_from_exception(exc)
                    source_run.error_message = str(exc)[:500]
                    source_run.zero_result_reason = HardwareZeroResultReason.SOURCE_BLOCKED if source_run.status == HardwareSourceRunStatus.BLOCKED else HardwareZeroResultReason.UNKNOWN
                    query.status = source_run.status
                    query.zero_result_reason = source_run.zero_result_reason
                    return []
                finally:
                    source_run.completed_at = utc_now()
                    if source_run.started_at:
                        source_run.duration_ms = max(0, int((source_run.completed_at - source_run.started_at).total_seconds() * 1000))
                    await self._update_job_async(job)

        for planned in planned_queries:
            job.source_runs.append(
                HardwareSourceRun(
                    source_name=planned.source_group,
                    adapter_type=web_adapter.adapter_type,
                    query=planned.generated_query_en,
                    expanded_query=planned.generated_query_en,
                    query_template_id=planned.query_template_id,
                    query_template=planned.query_template,
                    state_code=planned.state_code,
                    state_name=planned.state_name,
                    scan_depth=planned.scan_depth,
                    scan_lane=planned.scan_lane,
                    category=planned.category,
                    status=HardwareSourceRunStatus.PLANNED,
                    started_at=utc_now(),
                    completed_at=utc_now(),
                    error_message="Deep Scan source is planned for V2.6B and was not executed in this Fast Scan.",
                )
            )
        if planned_queries:
            await self._update_job_async(job)

        if selected_queries:
            batches = await asyncio.gather(*(run_query(query) for query in selected_queries))
            for results in batches:
                raw_results.extend(results)

        if request.manual_urls or request.manual_text:
            for category in job.categories[:1]:
                manual_query = type("ManualQuery", (), {"generated_query_en": "manual import", "category": category, "source_group": "Manual Import"})
                source_run = HardwareSourceRun(
                    source_name=manual_adapter.source_name,
                    adapter_type=manual_adapter.adapter_type,
                    query="manual import",
                    expanded_query="manual import",
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
                    source_run.raw_results = len(results)
                    source_run.specific_listing_count = len([item for item in results if item.page_type == HardwareResultPageType.SPECIFIC_LISTING])
                except Exception as exc:
                    source_run.status = self._status_from_exception(exc)
                    source_run.error_message = str(exc)[:500]
                finally:
                    source_run.completed_at = utc_now()
                    hardware_daily_store.update_job(job)
        return raw_results

    async def _enrich_specific_listings(self, raw_results: list[RawHardwareListing]) -> list[RawHardwareListing]:
        enriched: list[RawHardwareListing] = []
        for raw in raw_results:
            if raw.raw_data.get("adapter_type") == "govauctions_app_feed" and raw.raw_data.get("verification_status") != "verified":
                raw.detail_checked_at = utc_now()
                raw.detail_parse_status = "pending_original_source_verification"
                detail = dict(raw.raw_data.get("detail") or {})
                detail["needs_manual_review"] = True
                detail["unavailable_reason"] = "pending_original_source_verification"
                detail["listing_status_reason"] = "GovAuctions.app discovery requires original source verification."
                raw.raw_data["detail"] = detail
                enriched.append(raw)
                continue
            try:
                enriched.append(await asyncio.wait_for(self.detail_parser.enrich(raw), timeout=25))
            except Exception as exc:
                raw.detail_parse_status = "detail_failed"
                raw.detail_checked_at = utc_now()
                raw.raw_data["detail"] = {
                    "listing_status": ListingStatus.UNKNOWN.value,
                    "needs_manual_review": True,
                    "unavailable_reason": str(exc)[:240],
                    "checked_at": raw.detail_checked_at.isoformat(),
                }
                enriched.append(raw)
        return enriched

    def _replace_enriched_results(self, raw_results: list[RawHardwareListing], enriched_results: list[RawHardwareListing]) -> list[RawHardwareListing]:
        by_url = {raw.source_url: raw for raw in enriched_results}
        return [by_url.get(raw.source_url, raw) for raw in raw_results]

    def _apply_state_matching(self, raw_results: list[RawHardwareListing], job: HardwareScanJob) -> None:
        fallback_states = job.states if job.scan_scope == HardwareScanScope.LEGACY_STATE else []
        run_stats: dict[str, dict[str, object]] = {}
        for raw in raw_results:
            match = hardware_state_matcher.apply(raw, fallback_requested_states=fallback_states)
            raw.requested_states = match.requested_states
            raw.detected_state = match.detected_state
            raw.matched_requested_state = match.matched_requested_state
            raw.state_match_status = match.state_match_status
            raw.filter_reason = match.filter_reason
            raw.raw_data["requested_states"] = match.requested_states
            raw.raw_data["detected_state"] = match.detected_state
            raw.raw_data["matched_requested_state"] = match.matched_requested_state
            raw.raw_data["state_match_status"] = match.state_match_status
            raw.raw_data["filter_reason"] = match.filter_reason
            source_run_id = str(raw.raw_data.get("source_run_id") or "")
            if not source_run_id:
                continue
            stats = run_stats.setdefault(
                source_run_id,
                {
                    "raw_results": 0,
                    "matched_state_results": 0,
                    "state_mismatch_results": 0,
                    "location_unknown_results": 0,
                    "filtered_out_results": 0,
                    "detected_states": set(),
                },
            )
            stats["raw_results"] = int(stats["raw_results"]) + 1
            if match.detected_state:
                stats["detected_states"].add(match.detected_state)  # type: ignore[union-attr]
            if match.state_match_status == "matched":
                stats["matched_state_results"] = int(stats["matched_state_results"]) + 1
            elif match.state_match_status == "mismatched":
                stats["state_mismatch_results"] = int(stats["state_mismatch_results"]) + 1
                stats["filtered_out_results"] = int(stats["filtered_out_results"]) + 1
            else:
                stats["location_unknown_results"] = int(stats["location_unknown_results"]) + 1

        for run in job.source_runs:
            stats = run_stats.get(str(run.id))
            if not stats:
                continue
            run.raw_results = int(stats["raw_results"])
            run.matched_state_results = int(stats["matched_state_results"])
            run.state_mismatch_results = int(stats["state_mismatch_results"])
            run.location_unknown_results = int(stats["location_unknown_results"])
            run.filtered_out_results = int(stats["filtered_out_results"])
            run.detected_states = sorted(stats["detected_states"])  # type: ignore[arg-type]
            if run.state_mismatch_results and not run.matched_state_results:
                run.state_match_status = "mismatched"
                run.filter_reason = "state_mismatch"
                run.zero_result_reason = HardwareZeroResultReason.STATE_FILTER_TOO_STRICT
            elif run.location_unknown_results and not run.matched_state_results:
                run.state_match_status = "unknown"
                run.filter_reason = "location_unknown"
            else:
                run.state_match_status = "matched" if run.matched_state_results else None

    def _quality_stats(self, raw_results: list[RawHardwareListing], job: HardwareScanJob) -> HardwareQualityStats:
        stats = HardwareQualityStats(
            raw_results=len(raw_results),
            failed_sources=len([run for run in job.source_runs if run.status in {HardwareSourceRunStatus.FAILED, HardwareSourceRunStatus.TIMEOUT, HardwareSourceRunStatus.BLOCKED}]),
        )
        for raw in raw_results:
            if raw.raw_data.get("state_match_status") == "matched":
                stats.matched_state_results += 1
            elif raw.raw_data.get("state_match_status") == "mismatched":
                stats.state_mismatch_results += 1
                stats.filtered_out_results += 1
            elif raw.raw_data.get("state_match_status") == "unknown":
                stats.location_unknown_results += 1
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

    def _apply_source_run_opportunity_counts(self, job: HardwareScanJob, opportunities) -> None:
        runs_by_id = {str(run.id): run for run in job.source_runs}
        for run in runs_by_id.values():
            run.current_opportunities = 0
            run.needs_review = 0
            run.history = 0
        for opportunity in opportunities:
            source_run_id = str((opportunity.raw_data_json or {}).get("source_run_id") or "")
            run = runs_by_id.get(source_run_id)
            if not run:
                continue
            if self._is_current_opportunity(opportunity):
                run.current_opportunities += 1
            elif self._is_needs_review_opportunity(opportunity):
                run.needs_review += 1
            elif self._is_history_opportunity(opportunity):
                run.history += 1

    def _is_current_opportunity(self, opportunity) -> bool:
        if getattr(opportunity, "requested_states", None) and opportunity.state_match_status != "matched":
            return False
        if self._has_review_blocker(opportunity) or self._has_past_end_time(opportunity):
            return False
        if opportunity.listing_status in {ListingStatus.ACTIVE, ListingStatus.ENDING_SOON}:
            if self._has_unconfirmed_blocked_source(opportunity):
                return False
            return True
        if opportunity.listing_status == ListingStatus.UNKNOWN:
            if self._has_unconfirmed_blocked_source(opportunity) or self._has_closed_signal(opportunity):
                return False
            if not opportunity.first_seen_at or not opportunity.last_status_check_at:
                return False
            return (
                utc_now() - opportunity.first_seen_at <= timedelta(hours=24)
                and utc_now() - opportunity.last_status_check_at <= timedelta(hours=24)
            )
        return False

    def _is_needs_review_opportunity(self, opportunity) -> bool:
        if getattr(opportunity, "requested_states", None) and opportunity.state_match_status == "unknown":
            return True
        if opportunity.end_time_verification == AuctionEndVerificationLevel.CONFLICTING:
            return True
        if self._is_history_opportunity(opportunity):
            return False
        if opportunity.listing_status == ListingStatus.NEEDS_MANUAL_REVIEW or opportunity.needs_manual_review:
            return True
        if self._has_unconfirmed_blocked_source(opportunity) or opportunity.unavailable_reason:
            return True
        if opportunity.listing_status == ListingStatus.UNKNOWN:
            return not self._is_current_opportunity(opportunity)
        return False

    def _is_history_opportunity(self, opportunity) -> bool:
        if opportunity.end_time_verification == AuctionEndVerificationLevel.CONFLICTING:
            return False
        if self._has_past_end_time(opportunity):
            return True
        return opportunity.listing_status in {
            ListingStatus.ENDED,
            ListingStatus.SOLD,
            ListingStatus.REMOVED,
            ListingStatus.UNAVAILABLE,
            ListingStatus.IGNORED,
        }

    def _has_review_blocker(self, opportunity) -> bool:
        return bool(
            opportunity.needs_manual_review
            or opportunity.listing_status in {ListingStatus.NEEDS_MANUAL_REVIEW, ListingStatus.UNAVAILABLE, ListingStatus.IGNORED}
            or opportunity.end_time_verification == AuctionEndVerificationLevel.CONFLICTING
            or opportunity.unavailable_reason
        )

    def _confirmed_end_time(self, opportunity):
        return opportunity.end_time_utc or opportunity.auction_end_time or opportunity.calculated_end_time

    def _has_past_end_time(self, opportunity) -> bool:
        end_time = self._confirmed_end_time(opportunity)
        if not end_time:
            return False
        now = utc_now()
        try:
            return end_time <= now
        except TypeError:
            return end_time.replace(tzinfo=timezone.utc) <= now

    def _has_unconfirmed_blocked_source(self, opportunity) -> bool:
        if self._confirmed_end_time(opportunity):
            return False
        source = (opportunity.source or "").lower()
        status_note = " ".join(
            str(value or "").lower()
            for value in [
                opportunity.unavailable_reason,
                opportunity.status_check_result,
                opportunity.status_check_error,
                opportunity.raw_data_json.get("detail_parse_status"),
                opportunity.raw_data_json.get("detail_error"),
            ]
        )
        blocked = any(token in status_note for token in ["blocked", "captcha", "403", "login", "unavailable"])
        return blocked or ("govdeals" in source and opportunity.end_time_verification == AuctionEndVerificationLevel.UNKNOWN)

    def _has_closed_signal(self, opportunity) -> bool:
        text = " ".join(
            str(value or "").lower()
            for value in [
                opportunity.status_check_result,
                opportunity.unavailable_reason,
                opportunity.raw_title,
                opportunity.raw_description,
            ]
        )
        return any(token in text for token in ["auction ended", "closed", "sold", "no longer available", "removed"])

    def _status_from_exception(self, exc: Exception) -> HardwareSourceRunStatus:
        message = str(exc).lower()
        if "403" in message or "captcha" in message or "blocked" in message:
            return HardwareSourceRunStatus.BLOCKED
        return HardwareSourceRunStatus.FAILED

    def _query_timeout_seconds(self, scan_lane: HardwareScanLane, source_name: str | None = None) -> int:
        configured_timeout = SOURCE_CONFIGS.get(source_name or "", {}).get("default_timeout_seconds")
        if isinstance(configured_timeout, int):
            return max(5, configured_timeout)
        if scan_lane == HardwareScanLane.DEEP:
            return max(5, self.settings.hardware_deep_query_timeout_seconds)
        return max(5, self.settings.hardware_fast_query_timeout_seconds)

    def _cache_ttl_minutes(self, scan_lane: HardwareScanLane) -> int:
        if scan_lane == HardwareScanLane.DEEP:
            return max(1, self.settings.hardware_query_cache_ttl_deep_minutes)
        return max(1, self.settings.hardware_query_cache_ttl_fast_minutes)

    def _query_cache_key(self, query) -> str:
        raw = "|".join(
            [
                query.source_group,
                query.category.value,
                query.state_code or "nationwide",
                query.query_template or "",
                self._normalize_query_key(query.generated_query_en),
                query.scan_depth.value,
                query.scan_lane.value,
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _normalize_query_key(self, query: str) -> str:
        return " ".join(query.lower().replace('"', "").split())

    def _serialize_raw_results(self, results: list[RawHardwareListing]) -> list[dict]:
        return [result.model_dump(mode="json") for result in results]

    def _hydrate_cached_results(self, cached_results: list) -> list[RawHardwareListing]:
        hydrated: list[RawHardwareListing] = []
        for item in cached_results:
            try:
                hydrated.append(RawHardwareListing.model_validate(item))
            except Exception:
                continue
        return hydrated

    def _run_query_performance_key(self, run: HardwareSourceRun) -> str:
        raw = "|".join(
            [
                run.source_name,
                run.category.value if run.category else "all",
                run.state_code or "all",
                run.query_template_id or run.query_template or self._normalize_query_key(run.query or ""),
                run.scan_lane.value,
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _source_health_status(
        self,
        total: int,
        failed_runs: int,
        timeout_runs: int,
        zero_result_runs: int,
        avg_duration_ms: float,
        state_mismatch_results: int,
        raw_results: int,
        result_rate: float,
    ) -> HardwareSourceHealthStatus:
        if total <= 0:
            return HardwareSourceHealthStatus.LOW_YIELD
        if failed_runs + timeout_runs >= max(3, total * 0.4):
            return HardwareSourceHealthStatus.UNSTABLE
        if avg_duration_ms >= 15000:
            return HardwareSourceHealthStatus.SLOW
        if raw_results and state_mismatch_results / max(raw_results, 1) >= 0.6:
            return HardwareSourceHealthStatus.NOISY
        if zero_result_runs >= max(3, total * 0.7) or result_rate < 0.15:
            return HardwareSourceHealthStatus.LOW_YIELD
        return HardwareSourceHealthStatus.HEALTHY

    def _zero_result_reason(self, source_run: HardwareSourceRun, results: list[RawHardwareListing]) -> HardwareZeroResultReason | None:
        if source_run.result_count > 0 and source_run.specific_listing_count == 0:
            return HardwareZeroResultReason.NO_SPECIFIC_LISTING
        if source_run.result_count > 0:
            return None
        if source_run.query_template and len(source_run.query_template.split()) >= 3:
            return HardwareZeroResultReason.QUERY_TOO_NARROW
        return HardwareZeroResultReason.NO_INDEXED_RESULTS

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
