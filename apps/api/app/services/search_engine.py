from __future__ import annotations

import asyncio

from app.adapters import BestBuyAdapter, CDWAdapter, MicroCenterAdapter, NeweggAdapter, ProvantageAdapter
from app.adapters.base import SearchAdapter
from app.models.enums import SearchSource
from app.models.schemas import NormalizedResult, SearchOptions


class SearchEngineCenter:
    def __init__(self) -> None:
        adapters: list[SearchAdapter] = [
            BestBuyAdapter(),
            MicroCenterAdapter(),
            NeweggAdapter(),
            CDWAdapter(),
            ProvantageAdapter(),
        ]
        self.adapters = {adapter.source_key: adapter for adapter in adapters}

    async def search(self, query: str, options: SearchOptions) -> list[NormalizedResult]:
        selected = [source.value for source in options.sources] or [source.value for source in SearchSource]
        adapters = [self.adapters[key] for key in selected if key in self.adapters]
        results = await asyncio.gather(
            *(adapter.run(query, options) for adapter in adapters),
            return_exceptions=True,
        )

        normalized: list[NormalizedResult] = []
        for adapter_results in results:
            if isinstance(adapter_results, Exception):
                continue
            normalized.extend(adapter_results)
        return normalized
