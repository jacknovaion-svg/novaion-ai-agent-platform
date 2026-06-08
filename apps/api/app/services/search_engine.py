from __future__ import annotations

import asyncio

from app.adapters import BestBuyAdapter, CDWAdapter, MicroCenterAdapter, NeweggAdapter, ProvantageAdapter
from app.adapters.base import SearchAdapter
from app.core.config import get_settings
from app.models.enums import SearchMode, SearchSource
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
        adapters = self._ordered_adapters(selected)
        timeout = get_settings().adapter_timeout_seconds

        normalized: list[NormalizedResult] = []
        for adapter in adapters:
            try:
                adapter_results = await asyncio.wait_for(adapter.run(query, options), timeout=timeout)
            except Exception:
                continue
            normalized.extend(adapter_results)
        return self._apply_search_constraints(normalized, options)

    def _ordered_adapters(self, selected: list[str]) -> list[SearchAdapter]:
        priority = {
            "newegg": 0,
            "best_buy": 1,
            "micro_center": 2,
            "cdw": 3,
            "provantage": 4,
        }
        keys = [key for key in selected if key in self.adapters]
        keys.sort(key=lambda key: priority.get(key, 99))
        return [self.adapters[key] for key in keys]

    def _apply_search_constraints(
        self,
        results: list[NormalizedResult],
        options: SearchOptions,
    ) -> list[NormalizedResult]:
        return [item for item in results if self._matches_mode_and_radius(item, options)]

    def _matches_mode_and_radius(self, item: NormalizedResult, options: SearchOptions) -> bool:
        radius = options.radius
        local_match = (
            item.pickup_available
            and item.distance is not None
            and (radius is None or item.distance <= radius)
        )
        online_match = item.shipping_available

        if options.mode == SearchMode.LOCAL:
            return local_match
        if options.mode == SearchMode.ONLINE:
            return online_match
        return local_match or online_match
