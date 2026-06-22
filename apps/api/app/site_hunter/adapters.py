from __future__ import annotations

from abc import ABC, abstractmethod

import httpx
from bs4 import BeautifulSoup

from app.site_hunter.models import RawPropertyResult, SiteHunterSearchRequest, SourceType
from app.site_hunter.web_search import WebSearchClient


class PropertySourceAdapter(ABC):
    source_name: str
    source_type: SourceType
    adapter_type: str

    @abstractmethod
    async def search(self, query: str, request: SiteHunterSearchRequest) -> list[RawPropertyResult]:
        raise NotImplementedError


class WebSearchPropertyAdapter(PropertySourceAdapter):
    source_name = "Public Web Search"
    source_type = SourceType.OTHER
    adapter_type = "web_search_property"

    def __init__(self) -> None:
        self.web_search = WebSearchClient()

    async def search(self, query: str, request: SiteHunterSearchRequest) -> list[RawPropertyResult]:
        hits = await self.web_search.search(query, max_results=request.max_results_per_source)
        return [
            RawPropertyResult(
                source_name=self.source_name,
                source_type=self.source_type,
                source_url=hit.url,
                original_title=hit.title,
                original_description=hit.snippet,
                raw_data={"query": query, "domain": hit.domain},
            )
            for hit in hits
            if self._is_relevant(hit.title, hit.snippet, hit.domain)
        ]

    def _is_relevant(self, title: str, snippet: str | None, domain: str | None) -> bool:
        if domain and any(blocked in domain for blocked in ["github.com", "wikipedia.org", "youtube.com", "facebook.com"]):
            return False
        haystack = f"{title} {snippet or ''}".lower()
        return any(
            token in haystack
            for token in [
                "industrial",
                "manufacturing",
                "warehouse",
                "factory",
                "commercial real estate",
                "land for sale",
                "property",
                "available sites",
                "businesses for sale",
            ]
        )


class CrexiSearchAdapter(PropertySourceAdapter):
    source_name = "Crexi"
    source_type = SourceType.NATIONAL_MARKETPLACE
    adapter_type = "crexi_search"

    def __init__(self) -> None:
        self.web_search = WebSearchClient()

    async def search(self, query: str, request: SiteHunterSearchRequest) -> list[RawPropertyResult]:
        hits = await self.web_search.search(f"site:crexi.com/properties {query}", max_results=request.max_results_per_source)
        return [
            RawPropertyResult(
                source_name=self.source_name,
                source_type=self.source_type,
                source_url=hit.url,
                original_title=hit.title,
                original_description=hit.snippet,
                raw_data={"query": query, "domain": hit.domain, "discovery_mode": "search_engine_site_query"},
            )
            for hit in hits
            if hit.domain and "crexi.com" in hit.domain
        ]


class Century21CommercialAdapter(PropertySourceAdapter):
    source_name = "Century 21 Commercial"
    source_type = SourceType.NATIONAL_BROKERAGE
    adapter_type = "century21_commercial_search"

    def __init__(self) -> None:
        self.web_search = WebSearchClient()

    async def search(self, query: str, request: SiteHunterSearchRequest) -> list[RawPropertyResult]:
        state_urls = self._state_urls(query)
        if not state_urls:
            return []

        results: list[RawPropertyResult] = []
        headers = {"User-Agent": "Mozilla/5.0 (compatible; NOVAIONSiteHunter/1.0; +https://novaion.ai)"}
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=headers) as client:
            for state, url in state_urls:
                response = await client.get(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                title = self._meta(soup, "title")
                if not title and soup.title:
                    title = soup.title.get_text(" ", strip=True)
                title = title or f"{state} Commercial Real Estate"
                description = self._meta(soup, "description")
                results.append(
                    RawPropertyResult(
                        source_name=self.source_name,
                        source_type=self.source_type,
                        source_url=url,
                        original_title=title,
                        original_description=description,
                        raw_data={"query": query, "state": state, "direct_public_page": True},
                    )
                )
        return results[: request.max_results_per_source]

    def _state_urls(self, query: str) -> list[tuple[str, str]]:
        mapping = {
            "Texas": "https://commercial.century21.com/real-estate/texas/LSTX/",
            "Georgia": "https://commercial.century21.com/real-estate/georgia/LSGA/",
            "California": "https://commercial.century21.com/real-estate/california/LSCA/",
            "Arizona": "https://commercial.century21.com/real-estate/arizona/LSAZ/",
            "Nevada": "https://commercial.century21.com/real-estate/nevada/LSNV/",
            "Ohio": "https://commercial.century21.com/real-estate/ohio/LSOH/",
            "Florida": "https://commercial.century21.com/real-estate/florida/LSFL/",
        }
        return [(state, url) for state, url in mapping.items() if state.lower() in query.lower()]

    def _meta(self, soup: BeautifulSoup, name: str) -> str | None:
        node = soup.find("meta", attrs={"name": name})
        if node and node.get("content"):
            return str(node["content"]).strip()
        if name == "title":
            node = soup.find("meta", attrs={"property": "og:title"})
            if node and node.get("content"):
                return str(node["content"]).strip()
        return None


class ManualImportAdapter(PropertySourceAdapter):
    source_name = "Manual Import"
    source_type = SourceType.OTHER
    adapter_type = "manual_import"

    async def search(self, query: str, request: SiteHunterSearchRequest) -> list[RawPropertyResult]:
        results: list[RawPropertyResult] = []
        for url in request.manual_urls:
            results.append(
                RawPropertyResult(
                    source_name=self.source_name,
                    source_type=self.source_type,
                    source_url=str(url),
                    original_title=str(url),
                    original_description=request.manual_text,
                    raw_data={"query": query, "manual": True},
                )
            )
        if request.manual_text and not request.manual_urls:
            results.append(
                RawPropertyResult(
                    source_name=self.source_name,
                    source_type=self.source_type,
                    source_url="manual://text",
                    original_title="Manual pasted property description",
                    original_description=request.manual_text,
                    raw_data={"query": query, "manual": True},
                )
            )
        return results
