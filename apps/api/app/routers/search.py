from fastapi import APIRouter, HTTPException

from app.agents.center import AgentCenter
from app.db.repository import repository
from app.models.schemas import SearchJobResponse, SearchRequest

router = APIRouter(prefix="/search", tags=["search"])
agent_center = AgentCenter()


@router.post("", response_model=SearchJobResponse)
async def run_search(payload: SearchRequest) -> SearchJobResponse:
    try:
        results = await agent_center.run_search(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job_id = repository.create_search_job(payload, results)

    return SearchJobResponse(
        id=job_id,
        agent_type=payload.agent_type,
        query=payload.query,
        quantity=payload.quantity,
        zip_code=payload.zip_code,
        radius=payload.radius,
        mode=payload.mode,
        status="completed",
        results=results,
    )
