from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.supplier_hunter.job_service import supplier_hunter_jobs
from app.supplier_hunter.models import SupplierReviewRequest, SupplierResult, SupplierSearchJob, SupplierSearchRequest
from app.supplier_hunter.store import supplier_hunter_store

router = APIRouter(prefix="/supplier-hunter", tags=["supplier-hunter"])


@router.post("/search-jobs", response_model=SupplierSearchJob)
async def create_supplier_search_job(payload: SupplierSearchRequest) -> SupplierSearchJob:
    job = supplier_hunter_jobs.create_job(payload)
    asyncio.create_task(supplier_hunter_jobs.run_job(job.id, payload))
    return job


@router.get("/search-jobs/{job_id}", response_model=SupplierSearchJob)
def get_supplier_search_job(job_id: UUID) -> SupplierSearchJob:
    job = supplier_hunter_jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Supplier Hunter job not found")
    return job


@router.get("/suppliers/{supplier_id}", response_model=SupplierResult)
def get_supplier(supplier_id: UUID) -> SupplierResult:
    supplier = supplier_hunter_jobs.get_supplier(supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@router.post("/suppliers/{supplier_id}/review", response_model=SupplierResult)
def review_supplier(supplier_id: UUID, payload: SupplierReviewRequest) -> SupplierResult:
    supplier = supplier_hunter_store.review_supplier(supplier_id, payload)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier

