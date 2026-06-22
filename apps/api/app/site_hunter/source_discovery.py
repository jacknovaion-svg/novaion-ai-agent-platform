from __future__ import annotations

from app.site_hunter.models import DiscoveredSource, GeneratedSearchQuery, SourceRunStatus, SourceType, TrustLevel, utc_now
from app.site_hunter.web_search import WebSearchClient


NATIONAL_SOURCES: list[tuple[str, str, SourceType]] = [
    ("LoopNet", "loopnet.com", SourceType.NATIONAL_MARKETPLACE),
    ("Crexi", "crexi.com", SourceType.NATIONAL_MARKETPLACE),
    ("Land.com", "land.com", SourceType.NATIONAL_MARKETPLACE),
    ("LandWatch", "landwatch.com", SourceType.NATIONAL_MARKETPLACE),
    ("Commercial Exchange", "commercialexchange.com", SourceType.NATIONAL_MARKETPLACE),
    ("CBRE", "cbre.com", SourceType.NATIONAL_BROKERAGE),
    ("JLL", "jll.com", SourceType.NATIONAL_BROKERAGE),
    ("Cushman & Wakefield", "cushmanwakefield.com", SourceType.NATIONAL_BROKERAGE),
    ("Colliers", "colliers.com", SourceType.NATIONAL_BROKERAGE),
    ("Newmark", "nmrk.com", SourceType.NATIONAL_BROKERAGE),
    ("Lee & Associates", "lee-associates.com", SourceType.NATIONAL_BROKERAGE),
    ("NAI Global", "naiglobal.com", SourceType.NATIONAL_BROKERAGE),
]


class SourceDiscoveryService:
    def __init__(self) -> None:
        self.web_search = WebSearchClient()

    async def discover(self, queries: list[GeneratedSearchQuery]) -> list[DiscoveredSource]:
        discovered = self._national_sources()
        seen = {source.domain for source in discovered}

        for query in queries[:12]:
            if query.source_group not in {"economic_development", "industrial_park", "local_brokerage", "utility"}:
                continue
            try:
                hits = await self.web_search.search(query.generated_query_en, max_results=4)
            except Exception:
                continue
            for hit in hits:
                if not hit.domain or hit.domain in seen:
                    continue
                seen.add(hit.domain)
                discovered.append(
                    DiscoveredSource(
                        source_name=hit.title[:120],
                        domain=hit.domain,
                        source_type=self._classify(hit.domain, hit.title, hit.snippet or "", query.source_group),
                        state=query.state,
                        county=query.county,
                        city=query.city,
                        discovery_method=f"web_search:{query.generated_query_en}",
                        trust_level=self._trust_level(hit.domain, query.source_group),
                        adapter_type="generic_page_parser",
                        status=SourceRunStatus.SUCCESS,
                        last_success_at=utc_now(),
                    )
                )
        return discovered

    def _national_sources(self) -> list[DiscoveredSource]:
        return [
            DiscoveredSource(
                source_name=name,
                domain=domain,
                source_type=source_type,
                discovery_method="seeded_national_source",
                trust_level=TrustLevel.SOURCE_CONFIRMED,
                adapter_type="web_search" if "crexi" not in domain else "crexi_search",
                status=SourceRunStatus.SUCCESS,
                last_success_at=utc_now(),
            )
            for name, domain, source_type in NATIONAL_SOURCES
        ]

    def _classify(self, domain: str, title: str, snippet: str, source_group: str) -> SourceType:
        haystack = f"{domain} {title} {snippet}".lower()
        if ".gov" in domain or "government" in haystack:
            if "county" in haystack:
                return SourceType.COUNTY_GOVERNMENT
            if "city" in haystack:
                return SourceType.CITY_GOVERNMENT
            return SourceType.STATE_GOVERNMENT
        if "utility" in haystack or "electric" in haystack or "power" in haystack:
            return SourceType.UTILITY
        if "industrial park" in haystack:
            return SourceType.INDUSTRIAL_PARK
        if "economic development" in haystack or "development corporation" in haystack:
            return SourceType.ECONOMIC_DEVELOPMENT
        if "broker" in haystack or "real estate" in haystack or source_group == "local_brokerage":
            return SourceType.LOCAL_BROKERAGE
        if "auction" in haystack:
            return SourceType.AUCTION
        return SourceType.OTHER

    def _trust_level(self, domain: str, source_group: str) -> TrustLevel:
        if ".gov" in domain:
            return TrustLevel.SOURCE_CONFIRMED
        if source_group in {"economic_development", "industrial_park", "utility"}:
            return TrustLevel.SOURCE_CONFIRMED
        return TrustLevel.UNVERIFIED
