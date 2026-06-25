from __future__ import annotations

import asyncio
from urllib.parse import urlparse
from uuid import UUID

from app.supplier_hunter.adapters import (
    CertificationDirectoryDiscoveryAdapter,
    ManualSupplierImportAdapter,
    PublicSupplierWebSearchAdapter,
    SupplierSourceAdapter,
)
from app.supplier_hunter.models import (
    RawSupplierResult,
    SupplierCategory,
    SupplierQualityStats,
    SupplierSearchJob,
    SupplierJobStatus,
    SupplierSearchRequest,
    SupplierSourceRun,
    SupplierSourceRunStatus,
    utc_now,
)
from app.supplier_hunter.normalizer import SupplierNormalizer
from app.supplier_hunter.parser import SupplierRequirementParser
from app.supplier_hunter.query_builder import SupplierSearchQueryBuilder
from app.supplier_hunter.scoring import SupplierScoringService
from app.supplier_hunter.store import supplier_hunter_store


class SupplierHunterJobService:
    def __init__(self) -> None:
        self.parser = SupplierRequirementParser()
        self.query_builder = SupplierSearchQueryBuilder()
        self.normalizer = SupplierNormalizer()
        self.scoring = SupplierScoringService()
        self.adapters: list[SupplierSourceAdapter] = [
            PublicSupplierWebSearchAdapter(),
            CertificationDirectoryDiscoveryAdapter(),
            ManualSupplierImportAdapter(),
        ]

    def create_job(self, request: SupplierSearchRequest) -> SupplierSearchJob:
        job = SupplierSearchJob(
            natural_language_query_zh=request.natural_language_query_zh,
            status=SupplierJobStatus.CREATED,
        )
        supplier_hunter_store.create_job(job)
        return job

    async def run_job(self, job_id: UUID, request: SupplierSearchRequest) -> None:
        job = supplier_hunter_store.get_job(job_id)
        if not job:
            return
        try:
            job.status = SupplierJobStatus.PARSING_REQUIREMENTS
            supplier_hunter_store.update_job(job)
            criteria = self.parser.parse(request.natural_language_query_zh or "", request.structured_criteria)
            job.parsed_criteria = criteria

            job.status = SupplierJobStatus.GENERATING_QUERIES
            state_profile, subjobs, queries = self.query_builder.build(criteria)
            job.state_job = self._state_job_summary(state_profile)
            job.region_subjobs = subjobs
            job.generated_queries = queries
            supplier_hunter_store.update_job(job)

            job.status = SupplierJobStatus.SEARCHING_SUPPLIERS
            selected_queries = self._select_queries(job.generated_queries, max_queries=34)
            self._mark_executed_regions(job, selected_queries)
            raw_results: list[RawSupplierResult] = []
            for adapter in self.adapters:
                source_run = SupplierSourceRun(
                    source_name=adapter.source_name,
                    adapter_type=adapter.adapter_type,
                    status=SupplierSourceRunStatus.SEARCHING,
                    started_at=utc_now(),
                )
                job.source_runs.append(source_run)
                supplier_hunter_store.update_job(job)
                try:
                    adapter_results: list[RawSupplierResult] = []
                    if adapter.adapter_type == "manual_supplier_import":
                        adapter_results.extend(await asyncio.wait_for(adapter.search("manual import", request), timeout=20))
                    else:
                        for query in selected_queries:
                            query_results = await asyncio.wait_for(adapter.search(query.generated_query_en, request), timeout=30)
                            for raw in query_results:
                                raw.raw_data["region_name"] = query.region_name
                                raw.raw_data["state"] = query.state
                                raw.raw_data["supplier_type_query"] = query.supplier_type
                            adapter_results.extend(query_results)
                    raw_results.extend(adapter_results)
                    source_run.status = SupplierSourceRunStatus.SUCCESS
                    source_run.result_count = len(adapter_results)
                except asyncio.TimeoutError:
                    source_run.status = SupplierSourceRunStatus.TIMEOUT
                    source_run.error_message = "Source timed out without blocking the whole job."
                except Exception as exc:
                    source_run.status = self._status_from_exception(exc)
                    source_run.error_message = str(exc)[:500]
                finally:
                    source_run.query = f"{len(selected_queries)} generated query task(s)"
                    source_run.completed_at = utc_now()
                    supplier_hunter_store.update_job(job)

            job.status = SupplierJobStatus.NORMALIZING_RESULTS
            normalized = [self.normalizer.normalize(raw) for raw in raw_results]
            deduped, duplicates_removed = self._dedupe(normalized)
            final_suppliers = [supplier for supplier in deduped if supplier.supplier_category != SupplierCategory.D]
            rejected = [supplier for supplier in deduped if supplier.supplier_category == SupplierCategory.D]
            job.rejected_low_value_results = rejected
            job.quality_stats = SupplierQualityStats(
                raw_results=len(raw_results),
                normalized_suppliers=len(normalized),
                duplicates_removed=duplicates_removed,
                low_value_filtered=len(rejected),
                final_suppliers=len(final_suppliers),
                high_value_suppliers=len([s for s in final_suppliers if s.supplier_category in {SupplierCategory.A, SupplierCategory.B}]),
            )
            self._update_region_counts(job, raw_results, final_suppliers)

            job.status = SupplierJobStatus.SCORING
            job.results = self.scoring.score(final_suppliers)[:80]
            job.status = SupplierJobStatus.COMPLETED if job.results else SupplierJobStatus.PARTIALLY_COMPLETED
            job.completed_at = utc_now()
            supplier_hunter_store.update_job(job)
        except Exception as exc:
            job.status = SupplierJobStatus.FAILED
            job.error_message = str(exc)[:500]
            job.completed_at = utc_now()
            supplier_hunter_store.update_job(job)

    def get_job(self, job_id: UUID) -> SupplierSearchJob | None:
        return supplier_hunter_store.get_job(job_id)

    def get_supplier(self, supplier_id: UUID):
        return supplier_hunter_store.get_supplier(supplier_id)

    def _state_job_summary(self, state_profile) -> dict | None:
        if not state_profile:
            return None
        return {
            "state_code": state_profile.get("state_code"),
            "state_name": state_profile.get("state_name"),
            "region_count": len(state_profile.get("regions", ())),
            "max_suppliers": state_profile.get("max_suppliers"),
        }

    def _select_queries(self, queries, max_queries: int):
        selected = []
        seen: set[str] = set()
        region_names = []
        for query in queries:
            if query.region_name and query.region_name != "Statewide" and query.region_name not in region_names:
                region_names.append(query.region_name)
        for region_name in region_names:
            for query in [q for q in queries if q.region_name == region_name][:2]:
                if query.generated_query_en in seen:
                    continue
                selected.append(query)
                seen.add(query.generated_query_en)
        for query in queries:
            if query.region_name == "Statewide" and query.generated_query_en not in seen:
                selected.append(query)
                seen.add(query.generated_query_en)
        return selected[:max_queries]

    def _mark_executed_regions(self, job: SupplierSearchJob, queries) -> None:
        counts: dict[str, int] = {}
        for query in queries:
            if query.region_name:
                counts[query.region_name] = counts.get(query.region_name, 0) + 1
        for subjob in job.region_subjobs:
            subjob.executed_query_count = counts.get(subjob.region_name, 0)
            if subjob.executed_query_count:
                subjob.status = SupplierSourceRunStatus.SEARCHING

    def _update_region_counts(self, job: SupplierSearchJob, raw_results: list[RawSupplierResult], suppliers) -> None:
        raw_counts: dict[str, int] = {}
        supplier_counts: dict[str, int] = {}
        high_value_counts: dict[str, int] = {}
        for raw in raw_results:
            region_name = raw.raw_data.get("region_name")
            if region_name:
                raw_counts[region_name] = raw_counts.get(region_name, 0) + 1
        for supplier in suppliers:
            region_name = supplier.raw_data_json.get("region_name")
            if region_name:
                supplier_counts[region_name] = supplier_counts.get(region_name, 0) + 1
                if supplier.supplier_category in {SupplierCategory.A, SupplierCategory.B}:
                    high_value_counts[region_name] = high_value_counts.get(region_name, 0) + 1
        for subjob in job.region_subjobs:
            subjob.raw_result_count = raw_counts.get(subjob.region_name, 0)
            subjob.supplier_count = supplier_counts.get(subjob.region_name, 0)
            subjob.high_value_count = high_value_counts.get(subjob.region_name, 0)
            if subjob.executed_query_count:
                subjob.status = SupplierSourceRunStatus.SUCCESS

    def _dedupe(self, suppliers):
        seen: set[str] = set()
        output = []
        duplicates = 0
        for supplier in suppliers:
            key = self._supplier_key(supplier)
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            output.append(supplier)
        return output, duplicates

    def _supplier_key(self, supplier) -> str:
        if supplier.website:
            parsed = urlparse(supplier.website)
            return parsed.netloc.lower().removeprefix("www.")
        return supplier.company_name.lower()

    def _status_from_exception(self, exc: Exception) -> SupplierSourceRunStatus:
        message = str(exc).lower()
        if "403" in message or "blocked" in message or "captcha" in message:
            return SupplierSourceRunStatus.BLOCKED
        return SupplierSourceRunStatus.FAILED


supplier_hunter_jobs = SupplierHunterJobService()
