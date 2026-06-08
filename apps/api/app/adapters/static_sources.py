from __future__ import annotations

from app.adapters.base import SearchAdapter
from app.adapters.utils import infer_brand_and_model, utc_now
from app.models.schemas import NormalizedResult, SearchOptions


class StaticPlaceholderAdapter(SearchAdapter):
    source_key = "placeholder"
    source_name = "Placeholder"
    base_url = "https://example.com"

    async def search(self, query: str, options: SearchOptions) -> dict:
        return {"query": query}

    def parse_results(self, raw_data: dict) -> list[dict]:
        query = raw_data["query"]
        return [
            {
                "title": f"{query} - {self.source_name} source ready",
                "inventory": "Adapter Ready",
                "url": self.base_url,
                "store": self.source_name,
            }
        ]

    def normalize_result(self, parsed_data: dict) -> NormalizedResult:
        brand, model = infer_brand_and_model(parsed_data["title"], parsed_data["title"])
        return NormalizedResult(
            source=self.source_name,
            product_name=parsed_data["title"],
            brand=brand,
            model=model,
            store_name=parsed_data["store"],
            inventory_status=parsed_data["inventory"],
            product_url=parsed_data["url"],
            updated_at=utc_now(),
        )


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
