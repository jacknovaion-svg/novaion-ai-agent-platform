from __future__ import annotations

from app.agents.hardware_hunter import HardwareHunterAgent
from app.agents.site_hunter import SiteHunterAgent
from app.models.enums import AgentType
from app.models.schemas import AgentInfo, SearchRequest


class AgentCenter:
    def __init__(self) -> None:
        hardware = HardwareHunterAgent()
        site_hunter = SiteHunterAgent()
        self._agents = {
            AgentType.HARDWARE_HUNTER: hardware,
            AgentType.SITE_HUNTER: site_hunter,
        }

    def list_agents(self) -> list[AgentInfo]:
        return [
            AgentInfo(
                id="hardware-hunter",
                name="Hardware Hunter",
                type=AgentType.HARDWARE_HUNTER,
                enabled=True,
                description="Search computer hardware inventory, pricing, pickup, and shipping options.",
            ),
            AgentInfo(
                id="site-hunter",
                name="Site Hunter",
                type=AgentType.SITE_HUNTER,
                enabled=True,
                description="Search U.S. industrial sites from Chinese requirements and retain original source evidence.",
            ),
            AgentInfo(
                id="power-hunter",
                name="Power Hunter",
                type=AgentType.POWER_HUNTER,
                enabled=False,
                description="Reserved agent for power and energy resource discovery.",
            ),
            AgentInfo(
                id="land-hunter",
                name="Land Hunter",
                type=AgentType.LAND_HUNTER,
                enabled=False,
                description="Reserved agent for land and real estate resource discovery.",
            ),
            AgentInfo(
                id="supplier-hunter",
                name="Supplier Hunter",
                type=AgentType.SUPPLIER_HUNTER,
                enabled=True,
                description="Discover ITAD, data center decommissioning, used enterprise hardware, and asset remarketing suppliers.",
            ),
            AgentInfo(
                id="data-center-hunter",
                name="Data Center Hunter",
                type=AgentType.DATA_CENTER_HUNTER,
                enabled=False,
                description="Reserved agent for data center resource discovery.",
            ),
        ]

    async def run_search(self, request: SearchRequest):
        agent = self._agents.get(request.agent_type)
        if not agent or not agent.enabled:
            raise ValueError(f"Agent is not enabled: {request.agent_type}")
        return await agent.run_search(request)
