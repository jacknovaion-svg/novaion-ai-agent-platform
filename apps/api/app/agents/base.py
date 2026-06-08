from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.schemas import NormalizedResult, SearchRequest


class Agent(ABC):
    name: str
    agent_type: str
    enabled: bool

    @abstractmethod
    async def run_search(self, request: SearchRequest) -> list[NormalizedResult]:
        raise NotImplementedError
