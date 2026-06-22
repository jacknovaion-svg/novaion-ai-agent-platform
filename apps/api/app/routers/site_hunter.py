from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.site_hunter.job_service import site_hunter_jobs
from app.site_hunter.models import NormalizedSiteListing, SiteHunterJob, SiteHunterSearchRequest, SiteReviewRequest
from app.site_hunter.store import site_hunter_store

router = APIRouter(prefix="/site-hunter", tags=["site-hunter"])


@router.post("/search-jobs", response_model=SiteHunterJob)
async def create_search_job(payload: SiteHunterSearchRequest) -> SiteHunterJob:
    job = site_hunter_jobs.create_job(payload)
    asyncio.create_task(site_hunter_jobs.run_job(job.id, payload))
    return job


@router.get("/search-jobs/{job_id}", response_model=SiteHunterJob)
def get_search_job(job_id: UUID) -> SiteHunterJob:
    job = site_hunter_jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Site Hunter job not found")
    return job


@router.get("/search-jobs/{job_id}/results", response_model=list[NormalizedSiteListing])
def get_search_results(job_id: UUID) -> list[NormalizedSiteListing]:
    job = site_hunter_jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Site Hunter job not found")
    return site_hunter_jobs.get_results(job_id)


@router.get("/sites/{site_id}", response_model=NormalizedSiteListing)
def get_site(site_id: UUID) -> NormalizedSiteListing:
    site = site_hunter_jobs.get_site(site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


@router.post("/sites/{site_id}/review", response_model=NormalizedSiteListing)
def review_site(site_id: UUID, payload: SiteReviewRequest) -> NormalizedSiteListing:
    site = site_hunter_store.review_site(site_id, payload)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site
