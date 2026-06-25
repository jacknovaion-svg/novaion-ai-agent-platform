from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import quote_plus, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.hardware_daily.models import HardwareScanRequest, RawHardwareListing, utc_now
from app.hardware_daily.quality import HardwareResultQualityClassifier
from app.site_hunter.web_search import WebSearchClient


@dataclass
class HardwareSearchHit:
    title: str
    url: str
    snippet: str | None = None
    domain: str | None = None


class HardwareSourceAdapter(ABC):
    source_name: str
    adapter_type: str

    @abstractmethod
    async def search(self, query, request: HardwareScanRequest) -> list[RawHardwareListing]:
        raise NotImplementedError


class WebSearchHardwareAdapter(HardwareSourceAdapter):
    source_name = "Public Hardware Web Search"
    adapter_type = "web_search_hardware"

    def __init__(self) -> None:
        self.web_search = WebSearchClient()
        self.quality = HardwareResultQualityClassifier()

    async def search(self, query, request: HardwareScanRequest) -> list[RawHardwareListing]:
        if query.source_group == "Public Surplus":
            direct_results = await self._public_surplus_search(query, request)
            if direct_results:
                return direct_results
        try:
            hits = await self.web_search.search(query.generated_query_en, max_results=request.max_results_per_query)
        except Exception:
            hits = await self._bing_search(query.generated_query_en, max_results=request.max_results_per_query)
        listings: list[RawHardwareListing] = []
        for hit in hits:
            if not self._is_relevant(hit.title, hit.snippet, hit.domain):
                continue
            if not self._is_category_relevant(query.category.value, hit.title, hit.snippet):
                continue
            classification = self.quality.classify(query.source_group or self.source_name, hit.url, hit.title, hit.snippet)
            listings.append(
                RawHardwareListing(
                    source_name=query.source_group or self.source_name,
                    source_url=hit.url,
                    original_title=hit.title,
                    original_description=hit.snippet,
                    category=query.category,
                    page_type=classification.page_type,
                    classification_reason=classification.reason,
                    raw_data={
                        "query": query.generated_query_en,
                        "domain": hit.domain,
                        "adapter_type": self.adapter_type,
                        "public_search_discovery": True,
                        "page_type": classification.page_type.value,
                        "classification_reason": classification.reason,
                    },
                    fetched_at=utc_now(),
                )
            )
        return listings

    def _is_relevant(self, title: str, snippet: str | None, domain: str | None) -> bool:
        haystack = f"{title} {snippet or ''} {domain or ''}".lower()
        blocked = [
            "reddit.com",
            "youtube.com",
            "facebook.com",
            "wikipedia.org",
            "indeed.com",
            "manualslib.com",
            "firmware",
            "driver download",
        ]
        if any(token in haystack for token in blocked):
            return False
        return any(
            token in haystack
            for token in [
                "auction",
                "surplus",
                "liquidation",
                "lot",
                "bulk",
                "server",
                "poweredge",
                "proliant",
                "supermicro",
                "nvidia",
                "a100",
                "h100",
                "gpu",
                "memory",
                "rdimm",
                "ecc",
                "ssd",
                "nvme",
                "hard drive",
                "xeon",
                "epyc",
                "cpu",
                "desktop",
                "laptop",
                "computer",
                "itad",
            ]
        )

    async def _bing_search(self, query: str, max_results: int) -> list[HardwareSearchHit]:
        url = f"https://www.bing.com/search?q={quote_plus(query)}"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; NOVAIONHardwareHunter/2.1; +https://novaion.ai)"}
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        hits: list[HardwareSearchHit] = []
        for item in soup.select("li.b_algo")[: max_results * 2]:
            link = item.select_one("h2 a")
            if not link:
                continue
            href = link.get("href") or ""
            title = link.get_text(" ", strip=True)
            snippet_node = item.select_one(".b_caption p") or item.select_one("p")
            snippet = snippet_node.get_text(" ", strip=True) if snippet_node else None
            if not href or not title:
                continue
            domain = urlparse(href).netloc.lower().removeprefix("www.")
            hits.append(HardwareSearchHit(title=title, url=href, snippet=snippet, domain=domain))
            if len(hits) >= max_results:
                break
        return hits

    async def _public_surplus_search(self, query, request: HardwareScanRequest) -> list[RawHardwareListing]:
        keyword = self._public_surplus_keyword(query)
        cat_id = "1" if query.category.value in {"servers", "memory", "storage", "cpu", "gpu"} else "2"
        url = (
            "https://www.publicsurplus.com/sms/browse/search?"
            f"posting=y&keyWord={quote_plus(keyword)}&catId={cat_id}&page=0&sortBy=end&sortDesc=N"
        )
        headers = {"User-Agent": "Mozilla/5.0 (compatible; NOVAIONHardwareHunter/2.1; +https://novaion.ai)"}
        async with httpx.AsyncClient(timeout=25, follow_redirects=True, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        listings: list[RawHardwareListing] = []
        seen: set[str] = set()
        for link in soup.select('a[href*="/sms/auction/view?auc="]'):
            href = link.get("href") or ""
            title = link.get_text(" ", strip=True)
            if not title or href in seen:
                continue
            seen.add(href)
            absolute_url = urljoin("https://www.publicsurplus.com", href)
            container_text = link.find_parent().get_text(" ", strip=True) if link.find_parent() else title
            snippet = container_text[:500]
            if not self._is_relevant(title, snippet, "publicsurplus.com"):
                continue
            if not self._is_category_relevant(query.category.value, title, snippet):
                continue
            classification = self.quality.classify("Public Surplus", absolute_url, title, snippet)
            listings.append(
                RawHardwareListing(
                    source_name="Public Surplus",
                    source_url=absolute_url,
                    original_title=title,
                    original_description=snippet,
                    category=query.category,
                    page_type=classification.page_type,
                    classification_reason=classification.reason,
                    raw_data={
                        "query": query.generated_query_en,
                        "direct_source_url": url,
                        "domain": "publicsurplus.com",
                        "adapter_type": "public_surplus_html",
                        "page_type": classification.page_type.value,
                        "classification_reason": classification.reason,
                    },
                )
            )
            if len(listings) >= request.max_results_per_query:
                break
        return listings

    def _clean_source_query(self, query: str) -> str:
        cleaned = query
        for token in ["site:publicsurplus.com", "site:govdeals.com", "site:ebay.com", "site:hgpauction.com"]:
            cleaned = cleaned.replace(token, "")
        for token in ["Texas", "California", "Georgia", "TX", "CA", "GA", "lot", "bulk"]:
            cleaned = cleaned.replace(token, "")
        return " ".join(cleaned.split()) or "server"

    def _public_surplus_keyword(self, query) -> str:
        by_category = {
            "servers": "server",
            "gpu": "gpu",
            "memory": "memory",
            "storage": "hard drive",
            "cpu": "cpu",
        }
        return by_category.get(query.category.value, self._clean_source_query(query.generated_query_en))

    def _is_category_relevant(self, category: str, title: str, snippet: str | None) -> bool:
        text = f"{title} {snippet or ''}".lower()
        category_terms = {
            "servers": ["server", "poweredge", "proliant", "supermicro", "blade"],
            "gpu": ["gpu", "graphics card", "graphic card", "nvidia", "amd radeon", "a100", "h100", "rtx", "tesla"],
            "memory": ["memory", "ram", "rdimm", "dimm", "ddr4", "ddr5", "ecc"],
            "storage": ["ssd", "nvme", "hard drive", "hdd", "storage", "sas drive", "sata drive"],
            "cpu": ["cpu", "processor", "xeon", "epyc"],
        }
        if category == "storage" and any(token in text for token in ["hard drive removed", "drives removed", "no hard drive"]):
            return False
        if category == "cpu" and any(token in text for token in ["cpu tower", "desktop", "laptop"]) and not any(token in text for token in ["processor", "xeon", "epyc"]):
            return False
        return any(token in text for token in category_terms.get(category, []))


class ManualHardwareImportAdapter(HardwareSourceAdapter):
    source_name = "Manual Import"
    adapter_type = "manual_hardware_import"

    def __init__(self) -> None:
        self.quality = HardwareResultQualityClassifier()

    async def search(self, query, request: HardwareScanRequest) -> list[RawHardwareListing]:
        listings: list[RawHardwareListing] = []
        for url in request.manual_urls:
            classification = self.quality.classify(self.source_name, str(url), str(url), request.manual_text)
            listings.append(
                RawHardwareListing(
                    source_name=self.source_name,
                    source_url=str(url),
                    original_title=str(url),
                    original_description=request.manual_text,
                    category=query.category,
                    page_type=classification.page_type,
                    classification_reason=classification.reason,
                    raw_data={"query": query.generated_query_en, "manual": True},
                )
            )
        if request.manual_text and not request.manual_urls:
            listings.append(
                RawHardwareListing(
                    source_name=self.source_name,
                    source_url="manual://hardware-listing",
                    original_title="Manual hardware listing",
                    original_description=request.manual_text,
                    category=query.category,
                    raw_data={"query": query.generated_query_en, "manual": True},
                )
            )
        return listings
