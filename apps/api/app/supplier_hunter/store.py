from __future__ import annotations

from uuid import UUID

from app.supplier_hunter.models import SupplierReviewRequest, SupplierResult, SupplierSearchJob, utc_now


class SupplierHunterMemoryStore:
    def __init__(self) -> None:
        self.jobs: dict[UUID, SupplierSearchJob] = {}
        self.suppliers: dict[UUID, SupplierResult] = {}

    def create_job(self, job: SupplierSearchJob) -> SupplierSearchJob:
        self.jobs[job.id] = job
        return job

    def update_job(self, job: SupplierSearchJob) -> SupplierSearchJob:
        job.updated_at = utc_now()
        self.jobs[job.id] = job
        for supplier in [*job.results, *job.rejected_low_value_results]:
            self.suppliers[supplier.supplier_id] = supplier
        return job

    def get_job(self, job_id: UUID) -> SupplierSearchJob | None:
        return self.jobs.get(job_id)

    def get_supplier(self, supplier_id: UUID) -> SupplierResult | None:
        return self.suppliers.get(supplier_id)

    def review_supplier(self, supplier_id: UUID, payload: SupplierReviewRequest) -> SupplierResult | None:
        supplier = self.suppliers.get(supplier_id)
        if not supplier:
            return None
        supplier.review_status = payload.status
        supplier.notes = payload.notes or supplier.notes
        self.suppliers[supplier_id] = supplier
        for job in self.jobs.values():
            for item in [*job.results, *job.rejected_low_value_results]:
                if item.supplier_id == supplier_id:
                    item.review_status = supplier.review_status
                    item.notes = supplier.notes
                    job.updated_at = utc_now()
        return supplier


supplier_hunter_store = SupplierHunterMemoryStore()

