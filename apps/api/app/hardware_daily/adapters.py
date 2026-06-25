from __future__ import annotations

from abc import ABC, abstractmethod

from app.hardware_daily.models import HardwareScanRequest, RawHardwareListing, utc_now
from app.site_hunter.web_search import WebSearchClient


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

    async def search(self, query, request: HardwareScanRequest) -> list[RawHardwareListing]:
        hits = await self.web_search.search(query.generated_query_en, max_results=request.max_results_per_query)
        listings: list[RawHardwareListing] = []
        for hit in hits:
            if not self._is_relevant(hit.title, hit.snippet, hit.domain):
                continue
            listings.append(
                RawHardwareListing(
                    source_name=query.source_group or self.source_name,
                    source_url=hit.url,
                    original_title=hit.title,
                    original_description=hit.snippet,
                    category=query.category,
                    raw_data={
                        "query": query.generated_query_en,
                        "domain": hit.domain,
                        "adapter_type": self.adapter_type,
                        "public_search_discovery": True,
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
                "rdimm",
                "ecc",
                "ssd",
                "nvme",
                "xeon",
                "epyc",
                "itad",
            ]
        )


class ManualHardwareImportAdapter(HardwareSourceAdapter):
    source_name = "Manual Import"
    adapter_type = "manual_hardware_import"

    async def search(self, query, request: HardwareScanRequest) -> list[RawHardwareListing]:
        listings: list[RawHardwareListing] = []
        for url in request.manual_urls:
            listings.append(
                RawHardwareListing(
                    source_name=self.source_name,
                    source_url=str(url),
                    original_title=str(url),
                    original_description=request.manual_text,
                    category=query.category,
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
