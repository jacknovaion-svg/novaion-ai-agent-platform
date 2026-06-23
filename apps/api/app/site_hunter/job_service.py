from __future__ import annotations

import asyncio
from uuid import UUID

from app.site_hunter.adapters import (
    Century21CommercialAdapter,
    CrexiSearchAdapter,
    ManualImportAdapter,
    PropertySourceAdapter,
    WebSearchPropertyAdapter,
)
from app.site_hunter.chinese_requirement_parser import ChineseRequirementParser
from app.site_hunter.models import (
    SearchSourceRun,
    SiteHunterJob,
    SiteHunterJobStatus,
    SiteHunterSearchRequest,
    SourceRunStatus,
    SourceType,
    utc_now,
)
from app.site_hunter.normalizer import PropertyNormalizer
from app.site_hunter.power_screening import PowerScreeningService
from app.site_hunter.power_geometry import haversine_miles
from app.site_hunter.quality import ResultQualityService
from app.site_hunter.query_builder import EnglishSearchQueryBuilder
from app.site_hunter.scoring import SiteOpportunityScoringService
from app.site_hunter.search_anchor import SearchAnchorResolver
from app.site_hunter.source_discovery import SourceDiscoveryService
from app.site_hunter.store import site_hunter_store


class SiteHunterJobService:
    def __init__(self) -> None:
        self.parser = ChineseRequirementParser()
        self.anchor_resolver = SearchAnchorResolver()
        self.query_builder = EnglishSearchQueryBuilder()
        self.source_discovery = SourceDiscoveryService()
        self.normalizer = PropertyNormalizer()
        self.quality = ResultQualityService()
        self.power_screening = PowerScreeningService()
        self.scoring = SiteOpportunityScoringService()
        self.adapters: list[PropertySourceAdapter] = [
            WebSearchPropertyAdapter(),
            CrexiSearchAdapter(),
            Century21CommercialAdapter(),
            ManualImportAdapter(),
        ]

    def create_job(self, request: SiteHunterSearchRequest) -> SiteHunterJob:
        job = SiteHunterJob(
            natural_language_query_zh=request.natural_language_query_zh,
            status=SiteHunterJobStatus.CREATED,
        )
        site_hunter_store.create_job(job)
        return job

    async def run_job(self, job_id: UUID, request: SiteHunterSearchRequest) -> None:
        job = site_hunter_store.get_job(job_id)
        if not job:
            return
        try:
            job.status = SiteHunterJobStatus.PARSING_REQUIREMENTS
            site_hunter_store.update_job(job)

            parsed = self.parser.parse(request.natural_language_query_zh or "", request.structured_criteria)
            parsed = await self.anchor_resolver.resolve(parsed)
            job.parsed_criteria = parsed

            job.status = SiteHunterJobStatus.GENERATING_QUERIES
            job.generated_queries = self.query_builder.build(parsed)
            site_hunter_store.update_job(job)

            job.status = SiteHunterJobStatus.DISCOVERING_SOURCES
            job.discovered_sources = await self.source_discovery.discover(job.generated_queries)
            site_hunter_store.update_job(job)

            job.status = SiteHunterJobStatus.SEARCHING_PROPERTIES
            raw_results = []
            queries = self._select_queries(job.generated_queries, max_queries=12)
            for adapter in self.adapters:
                adapter_query_count = 1 if adapter.adapter_type == "manual_import" else len(queries)
                source_run = SearchSourceRun(
                    source_name=adapter.source_name,
                    source_type=adapter.source_type,
                    adapter_type=adapter.adapter_type,
                    status=SourceRunStatus.SEARCHING,
                    started_at=utc_now(),
                )
                job.source_runs.append(source_run)
                site_hunter_store.update_job(job)
                try:
                    adapter_results = []
                    if adapter.adapter_type == "manual_import":
                        adapter_results.extend(await asyncio.wait_for(adapter.search("manual import", request), timeout=20))
                    else:
                        for query in queries:
                            adapter_results.extend(await asyncio.wait_for(adapter.search(query.generated_query_en, request), timeout=30))
                    raw_results.extend(adapter_results)
                    source_run.status = SourceRunStatus.SUCCESS
                    source_run.result_count = len(adapter_results)
                    source_run.completed_at = utc_now()
                except asyncio.TimeoutError:
                    source_run.status = SourceRunStatus.TIMEOUT
                    source_run.error_message = "Source timed out without blocking the whole job."
                    source_run.completed_at = utc_now()
                except Exception as exc:
                    source_run.status = self._status_from_exception(exc)
                    source_run.error_message = str(exc)[:500]
                    source_run.completed_at = utc_now()
                finally:
                    source_run.query = f"{adapter_query_count} generated query task(s)"
                    site_hunter_store.update_job(job)

            job.status = SiteHunterJobStatus.NORMALIZING_RESULTS
            listings = [self.normalizer.normalize(raw) for raw in raw_results]
            final_candidates, discovery_candidates, quality_stats = self.quality.process(listings, job.parsed_criteria)
            job.discovery_candidates = discovery_candidates
            job.quality_stats = quality_stats

            job.status = SiteHunterJobStatus.SCORING
            scored = self.scoring.score(final_candidates)
            assessed = await self.power_screening.assess_sites(scored)
            job.results = self._apply_anchor_distances(assessed, parsed, job)
            job.status = SiteHunterJobStatus.COMPLETED if job.results else SiteHunterJobStatus.PARTIALLY_COMPLETED
            job.completed_at = utc_now()
            site_hunter_store.update_job(job)
        except Exception as exc:
            job.status = SiteHunterJobStatus.FAILED
            job.error_message = str(exc)[:500]
            job.completed_at = utc_now()
            site_hunter_store.update_job(job)

    def get_job(self, job_id: UUID) -> SiteHunterJob | None:
        return site_hunter_store.get_job(job_id)

    def get_results(self, job_id: UUID):
        return site_hunter_store.get_results(job_id)

    def get_site(self, site_id: UUID):
        return site_hunter_store.get_site(site_id)

    def _select_queries(self, queries, max_queries: int):
        selected = []
        seen: set[str] = set()
        source_priority = ["economic_development", "industrial_park", "utility", "local_brokerage"]
        states = []
        for query in queries:
            if query.state and query.state not in states:
                states.append(query.state)

        for state in states or [None]:
            for query in queries:
                if query.generated_query_en in seen:
                    continue
                if state and query.state != state:
                    continue
                if query.source_group == "property_market":
                    selected.append(query)
                    seen.add(query.generated_query_en)
                    break
            for query in queries:
                if query.generated_query_en in seen:
                    continue
                if state and query.state != state:
                    continue
                if query.source_group == "property_market" and "industrial land" in query.generated_query_en.lower():
                    selected.append(query)
                    seen.add(query.generated_query_en)
                    break
            for source_group in source_priority:
                for query in queries:
                    if query.generated_query_en in seen:
                        continue
                    if state and query.state != state:
                        continue
                    if query.source_group != source_group:
                        continue
                    selected.append(query)
                    seen.add(query.generated_query_en)
                    if len(selected) >= max_queries:
                        return selected
                    break

        for query in queries:
            if query.generated_query_en in seen:
                continue
            selected.append(query)
            seen.add(query.generated_query_en)
            if len(selected) >= max_queries:
                break
        return selected

    def _apply_anchor_distances(self, sites, criteria, job: SiteHunterJob):
        anchor = criteria.search_anchor
        if not anchor or anchor.latitude is None or anchor.longitude is None:
            return sites
        output = []
        for site in sites:
            assessment = site.power_assessment
            latitude = assessment.latitude if assessment and assessment.latitude is not None else site.latitude
            longitude = assessment.longitude if assessment and assessment.longitude is not None else site.longitude
            if latitude is None or longitude is None:
                site.quality_flags.append("needs_verification: distance_to_search_anchor unknown")
                output.append(site)
                continue
            distance = round(haversine_miles(anchor.latitude, anchor.longitude, latitude, longitude), 3)
            site.distance_to_search_anchor_miles = distance
            site.search_anchor_distance_basis = "address_point_to_search_anchor"
            if anchor.radius_miles and distance > anchor.radius_miles:
                job.quality_stats.radius_mismatch_removed += 1
                continue
            output.append(site)
        job.quality_stats.final_candidates = len(output)
        return output

    def _status_from_exception(self, exc: Exception) -> SourceRunStatus:
        message = str(exc).lower()
        if "403" in message or "blocked" in message or "captcha" in message:
            return SourceRunStatus.BLOCKED
        return SourceRunStatus.FAILED


site_hunter_jobs = SiteHunterJobService()
