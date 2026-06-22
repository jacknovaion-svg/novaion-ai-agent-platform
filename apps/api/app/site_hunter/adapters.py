from __future__ import annotations

import re
from abc import ABC, abstractmethod
from urllib.parse import urljoin

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
        blocked_domains = [
            "github.com",
            "wikipedia.org",
            "youtube.com",
            "facebook.com",
            "texags.com",
            "reddit.com",
            "x.com",
            "twitter.com",
        ]
        business_only_domains = [
            "linkbusiness.com",
            "tworld.com",
        ]
        if domain and any(blocked in domain for blocked in blocked_domains + business_only_domains):
            return False
        haystack = f"{title} {snippet or ''}".lower()
        if "businesses for sale" in haystack and not any(token in haystack for token in ["real estate", "property", "land", "acre"]):
            return False
        return any(
            token in haystack
            for token in [
                "industrial",
                "warehouse",
                "factory",
                "commercial real estate",
                "land for sale",
                "property",
                "available sites",
                "acre",
                "acres",
                "shovel-ready",
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
                page_description = self._meta(soup, "description")
                listings = self._prioritize_listings(self._listing_links(soup, url))
                for listing_title, listing_url, listing_summary in listings:
                    results.append(
                        RawPropertyResult(
                            source_name=self.source_name,
                            source_type=self.source_type,
                            source_url=listing_url,
                            original_title=listing_title,
                            original_description=listing_summary or page_description,
                            raw_data={
                                "query": query,
                                "state": state,
                                "direct_public_page": True,
                                "extraction": "listing_link",
                            },
                        )
                    )
                    if len(results) >= max(request.max_results_per_source, 12):
                        return results
                if not listings:
                    title = self._meta(soup, "title")
                    if not title and soup.title:
                        title = soup.title.get_text(" ", strip=True)
                    title = title or f"{state} Commercial Real Estate"
                    results.append(
                        RawPropertyResult(
                            source_name=self.source_name,
                            source_type=self.source_type,
                            source_url=url,
                            original_title=title,
                            original_description=page_description,
                            raw_data={
                                "query": query,
                                "state": state,
                                "direct_public_page": True,
                                "extraction": "state_page_fallback",
                            },
                        )
                    )
        return results[: max(request.max_results_per_source, 12)]

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

    def _listing_links(self, soup: BeautifulSoup, base_url: str) -> list[tuple[str, str, str | None]]:
        listings: list[tuple[str, str, str | None]] = []
        seen: set[str] = set()
        for link in soup.select("a[href]"):
            href = str(link.get("href") or "")
            title = link.get_text(" ", strip=True)
            if not href or not title:
                continue
            absolute_url = urljoin(base_url, href)
            lowered = absolute_url.lower()
            if "commercial.century21.com" not in lowered:
                continue
            if not any(token in lowered for token in ["/property/", "/commercial-property/", "/listing/"]):
                continue
            if absolute_url in seen:
                continue
            seen.add(absolute_url)
            container = link.find_parent(["article", "li", "div"])
            summary = container.get_text(" ", strip=True)[:500] if container else None
            listings.append((title, absolute_url, summary))
        return listings

    def _prioritize_listings(self, listings: list[tuple[str, str, str | None]]) -> list[tuple[str, str, str | None]]:
        return sorted(listings, key=self._listing_sort_key)

    def _listing_sort_key(self, listing: tuple[str, str, str | None]) -> tuple[int, float, float]:
        title, _, summary = listing
        text = f"{title} {summary or ''}"
        price = self._price(text)
        acres = self._acres(text)
        over_budget = 1 if price and price > 10_000_000 else 0
        price_sort = price if price is not None else 10_000_000
        acres_sort = -acres if acres is not None else 0
        return over_budget, price_sort, acres_sort

    def _price(self, text: str) -> float | None:
        match = re.search(r"\$\s*(\d+(?:,\d{3})+(?:\.\d+)?)", text)
        return float(match.group(1).replace(",", "")) if match else None

    def _acres(self, text: str) -> float | None:
        match = re.search(r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:\+|-)?\s*ac(?:res?)?\b", text, re.IGNORECASE)
        return float(match.group(1).replace(",", "")) if match else None


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
