from __future__ import annotations

from abc import ABC, abstractmethod

from app.site_hunter.web_search import WebSearchClient
from app.supplier_hunter.models import RawSupplierResult, SupplierSearchRequest


class SupplierSourceAdapter(ABC):
    source_name: str
    adapter_type: str

    @abstractmethod
    async def search(self, query: str, request: SupplierSearchRequest) -> list[RawSupplierResult]:
        raise NotImplementedError


class PublicSupplierWebSearchAdapter(SupplierSourceAdapter):
    source_name = "Public Web Search"
    adapter_type = "supplier_web_search"

    def __init__(self) -> None:
        self.web_search = WebSearchClient()

    async def search(self, query: str, request: SupplierSearchRequest) -> list[RawSupplierResult]:
        hits = await self.web_search.search(query, max_results=request.max_results_per_source)
        return [
            RawSupplierResult(
                source_name=self.source_name,
                source_url=hit.url,
                original_title=hit.title,
                original_description=hit.snippet,
                raw_data={"query": query, "domain": hit.domain, "discovery_mode": "public_web_search"},
            )
            for hit in hits
            if self._is_supplier_relevant(hit.title, hit.snippet, hit.domain)
        ]

    def _is_supplier_relevant(self, title: str, snippet: str | None, domain: str | None) -> bool:
        haystack = f"{title} {snippet or ''} {domain or ''}".lower()
        blocked = ["facebook.com", "youtube.com", "reddit.com", "wikipedia.org", "yelp.com", "indeed.com", "linkedin.com/jobs"]
        if any(token in haystack for token in blocked):
            return False
        low_value = ["phone repair", "computer repair shop", "residential recycling only", "consumer drop-off only"]
        if any(token in haystack for token in low_value):
            return False
        return any(
            token in haystack
            for token in [
                "itad",
                "asset disposition",
                "asset recovery",
                "asset remarketing",
                "data center decommission",
                "electronics recycler",
                "r2",
                "e-stewards",
                "server recycling",
                "server refurb",
                "used server",
                "equipment buyer",
                "laptop liquidation",
                "computer liquidation",
                "wholesale",
            ]
        )


class CertificationDirectoryDiscoveryAdapter(SupplierSourceAdapter):
    source_name = "Certification Directory Discovery"
    adapter_type = "certification_directory_discovery"

    def __init__(self) -> None:
        self.web_search = WebSearchClient()

    async def search(self, query: str, request: SupplierSearchRequest) -> list[RawSupplierResult]:
        directory_queries = [
            f"site:sustainableelectronics.org/recyclers {query}",
            f"site:e-stewards.org recycler {query}",
            f"site:naidonline.org aaa certified {query}",
        ]
        results: list[RawSupplierResult] = []
        for directory_query in directory_queries:
            hits = await self.web_search.search(directory_query, max_results=max(2, request.max_results_per_source // 2))
            results.extend(
                RawSupplierResult(
                    source_name=self.source_name,
                    source_url=hit.url,
                    original_title=hit.title,
                    original_description=hit.snippet,
                    raw_data={"query": directory_query, "domain": hit.domain, "discovery_mode": "directory_search_discovery"},
                )
                for hit in hits
            )
        return results


class ManualSupplierImportAdapter(SupplierSourceAdapter):
    source_name = "Manual Import"
    adapter_type = "manual_supplier_import"

    async def search(self, query: str, request: SupplierSearchRequest) -> list[RawSupplierResult]:
        results: list[RawSupplierResult] = []
        for url in request.manual_urls:
            results.append(
                RawSupplierResult(
                    source_name=self.source_name,
                    source_url=str(url),
                    original_title=str(url),
                    original_description=request.manual_text,
                    raw_data={"query": query, "manual": True},
                )
            )
        if request.manual_text and not request.manual_urls:
            results.append(
                RawSupplierResult(
                    source_name=self.source_name,
                    source_url="manual://supplier-text",
                    original_title="Manual supplier description",
                    original_description=request.manual_text,
                    raw_data={"query": query, "manual": True},
                )
            )
        return results

