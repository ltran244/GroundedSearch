from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import app.db.research as research_db
from app.agents.researcher import run_research
from app.api.responses import DATABASE_UNAVAILABLE, RESEARCH_NOT_FOUND

research_router = APIRouter(
    prefix="/api/v1",
    tags=["Research"],
    responses=DATABASE_UNAVAILABLE,
)


class ResearchRequest(BaseModel):
    query: str


class ResearchResponse(BaseModel):
    id: UUID
    query: str
    status: Literal["pending", "running", "completed", "failed"]
    answer: str | None = None
    error_message: str | None = None


@research_router.post("/research")
async def research(request: ResearchRequest) -> ResearchResponse:
    job_id = await research_db.post_research(request.query)
    # The job is committed before the pipeline starts, so a failure inside
    # run_research can still be recorded against it.
    await run_research(job_id)
    job = await research_db.get_research(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Research job not found")
    return ResearchResponse.model_validate(job)


@research_router.get(
    "/research/{job_id}",
    response_model=ResearchResponse,
    responses={**RESEARCH_NOT_FOUND},
)
async def get_research_status(job_id: UUID) -> ResearchResponse:
    job = await research_db.get_research(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Research job not found")
    return ResearchResponse.model_validate(job)
