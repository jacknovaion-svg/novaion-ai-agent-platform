from __future__ import annotations

from app.agents.hardware_hunter import HardwareHunterAgent
from app.models.enums import AgentType
from app.models.schemas import AgentInfo, SearchRequest


class AgentCenter:
    def __init__(self) -> None:
        hardware = HardwareHunterAgent()
        self._agents = {
            AgentType.HARDWARE_HUNTER: hardware,
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
                enabled=False,
                description="Reserved agent for supplier discovery and qualification.",
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
