from fastapi import APIRouter

from app.agents.center import AgentCenter

router = APIRouter(prefix="/agents", tags=["agents"])
agent_center = AgentCenter()


@router.get("")
def list_agents():
    return agent_center.list_agents()
