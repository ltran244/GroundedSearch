from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

import app.db.research as research_db
from app.api.responses import DATABASE_UNAVAILABLE, RESEARCH_NOT_FOUND

research_router = APIRouter(responses=DATABASE_UNAVAILABLE)


class ResearchRequest(BaseModel):
    query: str


class ResearchResponse(BaseModel):
    id: UUID
    query: str
    status: Literal["pending", "running", "completed", "failed"]
    answer: str | None = None
    error_message: str | None = None


@research_router.post("/research")
def research(request: ResearchRequest) -> ResearchResponse:
    # Try entering the query and handle error with db operations
    job_id = research_db.post_research(request.query)
    return ResearchResponse(status="pending", id=job_id, query=request.query)


@research_router.get(
    "/research",
    response_model=ResearchResponse,
    responses={**RESEARCH_NOT_FOUND},
)
def get_research_status(job_id: UUID) -> ResearchResponse:
    job = research_db.get_research(job_id)
    if job is None:
        raise HTTPException(
            status_code=404, detail="Research job not found"
        )
    return ResearchResponse.model_validate(job)
