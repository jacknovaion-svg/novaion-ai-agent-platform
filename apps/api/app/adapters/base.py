from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.models.schemas import NormalizedResult, SearchOptions


class SearchAdapter(ABC):
    source_key: str
    source_name: str

    @abstractmethod
    async def search(self, query: str, options: SearchOptions) -> Any:
        raise NotImplementedError

    @abstractmethod
    def parse_results(self, raw_data: Any) -> list[Any]:
        raise NotImplementedError

    @abstractmethod
    def normalize_result(self, parsed_data: Any) -> NormalizedResult:
        raise NotImplementedError

    async def run(self, query: str, options: SearchOptions) -> list[NormalizedResult]:
        raw_data = await self.search(query, options)
        parsed_results = self.parse_results(raw_data)
        return [self.normalize_result(item) for item in parsed_results]
