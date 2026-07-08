from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.hardware_daily.job_service import hardware_daily_scheduler
from app.hardware_daily.models import (
    HardwareBrowserImportRequest,
    HardwareDailyReport,
    HardwareDashboard,
    HardwareListingRecheckSummary,
    HardwareManualStatusReviewRequest,
    HardwareBulkReviewRequest,
    HardwareBulkReviewResult,
    HardwareOpportunity,
    HardwareScanJob,
    HardwareScanProgress,
    HardwareScanRequest,
    HardwareSchedulerState,
    HardwareSourceHealth,
    HardwareQueryPerformance,
    TelegramReportRequest,
)

router = APIRouter(prefix="/hardware-hunter", tags=["hardware-hunter-v2"])


@router.post("/daily-scan/run", response_model=HardwareScanJob)
async def run_daily_scan(payload: HardwareScanRequest) -> HardwareScanJob:
    job = hardware_daily_scheduler.create_job(payload)
    if hardware_daily_scheduler.consume_queued_job(job.id):
        asyncio.create_task(hardware_daily_scheduler.run_job(job.id, payload))
    return job


@router.get("/daily-scan/jobs/{job_id}", response_model=HardwareScanJob)
def get_daily_scan_job(job_id: UUID) -> HardwareScanJob:
    job = hardware_daily_scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Hardware daily scan job not found")
    return job


@router.post("/daily-scan/jobs/{job_id}/cancel", response_model=HardwareScanJob)
def cancel_daily_scan_job(job_id: UUID) -> HardwareScanJob:
    job = hardware_daily_scheduler.cancel_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Hardware daily scan job not found")
    return job


@router.get("/daily-scan/dashboard", response_model=HardwareDashboard)
def get_hardware_dashboard() -> HardwareDashboard:
    return hardware_daily_scheduler.dashboard()


@router.post("/browser-import/visible-page", response_model=HardwareScanJob)
async def import_browser_visible_page(payload: HardwareBrowserImportRequest) -> HardwareScanJob:
    return await hardware_daily_scheduler.import_browser_visible_page(payload)


@router.get("/scan-progress/{job_id}", response_model=HardwareScanProgress)
def get_hardware_scan_progress(job_id: UUID) -> HardwareScanProgress:
    progress = hardware_daily_scheduler.scan_progress(job_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Hardware scan job not found")
    return progress


@router.get("/source-health", response_model=list[HardwareSourceHealth])
def get_hardware_source_health() -> list[HardwareSourceHealth]:
    return hardware_daily_scheduler.source_health()


@router.get("/query-performance", response_model=list[HardwareQueryPerformance])
def get_hardware_query_performance() -> list[HardwareQueryPerformance]:
    return hardware_daily_scheduler.query_performance()


@router.post("/cache/clear")
def clear_hardware_query_cache() -> dict:
    return hardware_daily_scheduler.clear_query_cache()


@router.post("/source/{source_name}/disable")
def disable_hardware_source(source_name: str) -> dict:
    return hardware_daily_scheduler.set_source_enabled(source_name, enabled=False)


@router.post("/source/{source_name}/enable")
def enable_hardware_source(source_name: str) -> dict:
    return hardware_daily_scheduler.set_source_enabled(source_name, enabled=True)


@router.post("/daily-scan/opportunities/{opportunity_id}/recheck", response_model=HardwareOpportunity)
async def recheck_hardware_opportunity(opportunity_id: UUID) -> HardwareOpportunity:
    opportunity = await hardware_daily_scheduler.recheck_opportunity(opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=404, detail="Hardware opportunity not found")
    return opportunity


@router.post("/daily-scan/recheck", response_model=HardwareListingRecheckSummary)
async def recheck_hardware_opportunities(limit: int = 80) -> HardwareListingRecheckSummary:
    return await hardware_daily_scheduler.bulk_recheck(limit=limit)


@router.post("/daily-scan/opportunities/{opportunity_id}/manual-status", response_model=HardwareOpportunity)
def update_hardware_manual_status(opportunity_id: UUID, payload: HardwareManualStatusReviewRequest) -> HardwareOpportunity:
    opportunity = hardware_daily_scheduler.manual_status_review(opportunity_id, payload)
    if not opportunity:
        raise HTTPException(status_code=404, detail="Hardware opportunity not found")
    return opportunity


@router.post("/daily-scan/opportunities/bulk-review", response_model=HardwareBulkReviewResult)
async def bulk_review_hardware_opportunities(payload: HardwareBulkReviewRequest) -> HardwareBulkReviewResult:
    return await hardware_daily_scheduler.bulk_manual_review(payload)


@router.post("/daily-scan/jobs/{job_id}/telegram-report", response_model=HardwareDailyReport)
async def create_telegram_report(job_id: UUID, payload: TelegramReportRequest | None = None) -> HardwareDailyReport:
    request = payload or TelegramReportRequest()
    report = await hardware_daily_scheduler.generate_report(job_id, action=request.action, message=request.message)
    if not report:
        raise HTTPException(status_code=404, detail="Hardware daily scan job not found")
    return report


@router.get("/daily-scan/scheduler", response_model=HardwareSchedulerState)
def get_scheduler_status() -> HardwareSchedulerState:
    return hardware_daily_scheduler.scheduler_status()


@router.post("/daily-scan/scheduler/pause", response_model=HardwareSchedulerState)
def pause_scheduler() -> HardwareSchedulerState:
    return hardware_daily_scheduler.pause_scheduler()


@router.post("/daily-scan/scheduler/resume", response_model=HardwareSchedulerState)
def resume_scheduler() -> HardwareSchedulerState:
    return hardware_daily_scheduler.resume_scheduler()
