from __future__ import annotations

from uuid import UUID

from app.site_hunter.models import NormalizedSiteListing, SiteHunterJob, SiteReviewRequest, utc_now


class SiteHunterMemoryStore:
    def __init__(self) -> None:
        self.jobs: dict[UUID, SiteHunterJob] = {}
        self.sites: dict[UUID, NormalizedSiteListing] = {}

    def create_job(self, job: SiteHunterJob) -> SiteHunterJob:
        self.jobs[job.id] = job
        return job

    def update_job(self, job: SiteHunterJob) -> SiteHunterJob:
        job.updated_at = utc_now()
        self.jobs[job.id] = job
        for result in [*job.results, *job.discovery_candidates]:
            self.sites[result.id] = result
        return job

    def get_job(self, job_id: UUID) -> SiteHunterJob | None:
        return self.jobs.get(job_id)

    def get_results(self, job_id: UUID) -> list[NormalizedSiteListing]:
        job = self.jobs.get(job_id)
        return job.results if job else []

    def get_site(self, site_id: UUID) -> NormalizedSiteListing | None:
        return self.sites.get(site_id)

    def review_site(self, site_id: UUID, payload: SiteReviewRequest) -> NormalizedSiteListing | None:
        site = self.sites.get(site_id)
        if not site:
            return None
        site.review_status = payload.status
        self.sites[site_id] = site
        return site


site_hunter_store = SiteHunterMemoryStore()
