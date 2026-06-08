from __future__ import annotations

from app.agents.base import Agent
from app.models.enums import AgentType
from app.models.schemas import NormalizedResult, SearchOptions, SearchRequest
from app.services.recommendation import RecommendationService
from app.services.search_engine import SearchEngineCenter


class HardwareHunterAgent(Agent):
    name = "Hardware Hunter"
    agent_type = AgentType.HARDWARE_HUNTER
    enabled = True

    def __init__(self) -> None:
        self.search_engine = SearchEngineCenter()
        self.recommendation = RecommendationService()

    async def run_search(self, request: SearchRequest) -> list[NormalizedResult]:
        options = SearchOptions(
            quantity=request.quantity,
            zip_code=request.zip_code,
            radius=request.radius,
            mode=request.mode,
            sources=request.sources,
        )
        results = await self.search_engine.search(request.query, options)
        return self.recommendation.score(results)
