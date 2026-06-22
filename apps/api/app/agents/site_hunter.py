from __future__ import annotations

from app.agents.base import Agent
from app.models.enums import AgentType


class SiteHunterAgent(Agent):
    name = "Site Hunter"
    agent_type = AgentType.SITE_HUNTER
    enabled = True

    async def run_search(self, request):  # Site Hunter uses task-based routes in V1.
        raise NotImplementedError("Site Hunter uses /site-hunter/search-jobs task APIs.")
