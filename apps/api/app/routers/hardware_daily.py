from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.hardware_daily.job_service import hardware_daily_scheduler
from app.hardware_daily.models import HardwareDailyReport, HardwareDashboard, HardwareScanJob, HardwareScanRequest

router = APIRouter(prefix="/hardware-hunter", tags=["hardware-hunter-v2"])


@router.post("/daily-scan/run", response_model=HardwareScanJob)
async def run_daily_scan(payload: HardwareScanRequest) -> HardwareScanJob:
    job = hardware_daily_scheduler.create_job(payload)
    asyncio.create_task(hardware_daily_scheduler.run_job(job.id, payload))
    return job


@router.get("/daily-scan/jobs/{job_id}", response_model=HardwareScanJob)
def get_daily_scan_job(job_id: UUID) -> HardwareScanJob:
    job = hardware_daily_scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Hardware daily scan job not found")
    return job


@router.get("/daily-scan/dashboard", response_model=HardwareDashboard)
def get_hardware_dashboard() -> HardwareDashboard:
    return hardware_daily_scheduler.dashboard()


@router.post("/daily-scan/jobs/{job_id}/telegram-report", response_model=HardwareDailyReport)
async def create_telegram_report(job_id: UUID, send: bool = Query(default=False)) -> HardwareDailyReport:
    report = await hardware_daily_scheduler.generate_report(job_id, send=send)
    if not report:
        raise HTTPException(status_code=404, detail="Hardware daily scan job not found")
    return report
