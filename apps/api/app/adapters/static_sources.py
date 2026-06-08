from __future__ import annotations

from app.adapters.base import SearchAdapter
from app.models.schemas import NormalizedResult, SearchOptions


class StaticPlaceholderAdapter(SearchAdapter):
    source_key = "placeholder"
    source_name = "Placeholder"
    base_url = "https://example.com"

    async def search(self, query: str, options: SearchOptions) -> dict:
        return {"query": query}

    def parse_results(self, raw_data: dict) -> list[dict]:
        return []

    def normalize_result(self, parsed_data: dict) -> NormalizedResult:
        raise NotImplementedError(f"{self.source_name} live adapter is not implemented yet")


class MicroCenterAdapter(StaticPlaceholderAdapter):
    source_key = "micro_center"
    source_name = "Micro Center"
    base_url = "https://www.microcenter.com/"


class CDWAdapter(StaticPlaceholderAdapter):
    source_key = "cdw"
    source_name = "CDW"
    base_url = "https://www.cdw.com/"


class ProvantageAdapter(StaticPlaceholderAdapter):
    source_key = "provantage"
    source_name = "Provantage"
    base_url = "https://www.provantage.com/"
