from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, status
from pydantic import BaseModel, StringConstraints

import app.db.research as research_db
import app.db.sources as sources_db
from app.agents.researcher import run_research
from app.api.responses import DATABASE_UNAVAILABLE, RESEARCH_NOT_FOUND

research_router = APIRouter(
    prefix="/api/v1",
    tags=["Research"],
    responses=DATABASE_UNAVAILABLE,
)


class ResearchRequest(BaseModel):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


JobStatus = Literal["pending", "running", "completed", "failed"]


class SourceResponse(BaseModel):
    """One source. `number` is the [n] the answer cites it by.

    It is None for sources that were found but never offered to the model:
    the page could not be fetched, or had no readable text.
    """

    number: int | None
    title: str
    url: str
    snippet: str


class ResearchResponse(BaseModel):
    id: UUID
    query: str
    status: JobStatus
    answer: str | None = None
    error_message: str | None = None
    # Both fill in as the pipeline progresses, so a client polling this endpoint
    # can show the searches, then the sources, then the answer.
    search_queries: list[str] = []
    sources: list[SourceResponse] = []


class ResearchCreated(BaseModel):
    """All POST can say: the work has not started yet."""

    id: UUID
    status: JobStatus


@research_router.post(
    "/research",
    status_code=status.HTTP_201_CREATED,
    response_model=ResearchCreated,
)
async def research(
    request: ResearchRequest, background: BackgroundTasks, response: Response
) -> ResearchCreated:
    """Create a job and start it; poll GET /research/{job_id} for the answer."""
    job_id = await research_db.post_research(request.query)
    background.add_task(run_research, job_id)
    response.headers["Location"] = f"/api/v1/research/{job_id}"
    return ResearchCreated(id=job_id, status="pending")


@research_router.get(
    "/research/{job_id}",
    response_model=ResearchResponse,
    responses={**RESEARCH_NOT_FOUND},
)
async def get_research_status(job_id: UUID) -> ResearchResponse:
    job = await research_db.get_research(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Research job not found")
    return ResearchResponse.model_validate(
        {
            **job,
            "search_queries": await research_db.get_queries(job_id),
            "sources": await sources_db.get_sources(job_id),
        }
    )
