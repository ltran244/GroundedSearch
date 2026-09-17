import logging
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from anyio import from_thread
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from psycopg import OperationalError
from psycopg.rows import dict_row
from pydantic import BaseModel, Field, StringConstraints

import app.db.pool as pool_module
from app.db.research import mark_job_failed, save_queries
from app.llm.client import QueryGenerationError, generate_search_queries
from app.search.brave import BraveSearchError, search_queries
from app.search.models import QuerySearchResults

logger = logging.getLogger(__name__)


class ResearchRequest(BaseModel):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ResearchJobResponse(BaseModel):
    id: UUID
    query: str
    status: Literal["pending", "running", "completed", "failed"]
    answer: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
    search_queries: list[str] = Field(default_factory=list)


class ResearchErrorResponse(BaseModel):
    detail: str


class ResearchCreationResponse(ResearchJobResponse):
    search_results: list[QuerySearchResults]


class ResearchCreationError(ResearchErrorResponse):
    job_id: UUID | None = None


research_router = APIRouter(
    prefix="/api/v1/research",
    tags=["Research"],
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ResearchErrorResponse,
            "description": "Database unavailable",
            "content": {
                "application/json": {"example": {"detail": "Database unavailable"}},
            },
        },
    },
)


@research_router.post(
    "",
    response_model=ResearchCreationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        502: {
            "model": ResearchCreationError,
            "description": "Query generation or Brave search failed",
        },
        500: {"model": ResearchCreationError, "description": "Could not save queries"},
        503: {"model": ResearchCreationError, "description": "Database unavailable"},
    },
)
def create_research_job(
    request: ResearchRequest,
) -> ResearchCreationResponse | JSONResponse:
    """Generate and save queries, then return live Brave results (not persisted yet)."""
    try:
        with pool_module.pool.connection(timeout=2) as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO research_jobs (query, status) VALUES (%s, 'running')
                    RETURNING id, query, status, answer, error_message,
                              created_at, completed_at
                    """,
                    (request.query,),
                )
                job = ResearchJobResponse.model_validate(cursor.fetchone())
    except OperationalError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc
    # The job is committed and its connection released before waiting for Gemini.
    try:
        generated_queries = from_thread.run(generate_search_queries, job.query)
        save_queries(job.id, generated_queries.queries)
        search_results = from_thread.run(search_queries, generated_queries.queries)
    except Exception as exc:
        if isinstance(exc, QueryGenerationError):
            code, message = 502, "Search query generation failed"
        elif isinstance(exc, BraveSearchError):
            code, message = 502, "Brave search failed"
        elif isinstance(exc, OperationalError):
            code, message = 503, "Database unavailable"
        else:
            code, message = 500, "Could not save generated queries"
        logger.error("Research job %s failed (%s)", job.id, type(exc).__name__)
        try:
            mark_job_failed(job.id, message)
        except Exception as failure:
            logger.error(
                "Could not mark research job %s failed (%s)",
                job.id,
                type(failure).__name__,
            )
        return JSONResponse(
            status_code=code, content={"detail": message, "job_id": str(job.id)}
        )
    job.status = "pending"
    job.search_queries = generated_queries.queries
    return ResearchCreationResponse(**job.model_dump(), search_results=search_results)


@research_router.get(
    "/{job_id}",
    response_model=ResearchJobResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ResearchErrorResponse,
            "description": "Research job not found",
            "content": {
                "application/json": {"example": {"detail": "Research job not found"}},
            },
        },
    },
)
def get_research_job(job_id: UUID) -> ResearchJobResponse:
    """Fetch a research job by its ID."""
    try:
        with pool_module.pool.connection(timeout=2) as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT id, query, status, answer, error_message,
                           created_at, completed_at
                    FROM research_jobs WHERE id = %s
                    """,
                    (job_id,),
                )
                row = cursor.fetchone()
                if row is not None:
                    cursor.execute(
                        """
                        SELECT query FROM search_queries
                        WHERE research_job_id = %s ORDER BY position
                        """,
                        (job_id,),
                    )
                    row["search_queries"] = [item["query"] for item in cursor.fetchall()]
    except OperationalError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Research job not found"
        )
    return ResearchJobResponse.model_validate(row)
