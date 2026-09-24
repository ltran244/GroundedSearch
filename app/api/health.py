from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from psycopg import Error as PsycopgError
from pydantic import BaseModel
from redis.exceptions import RedisError

from app.api.responses import DATABASE_UNAVAILABLE
from app.db.pool import check_database
from app.queue import check_queue


class ErrorResponse(BaseModel):
    detail: str


health_router = APIRouter(responses=DATABASE_UNAVAILABLE)


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    status: Literal["ready"]


@health_router.get("/healthz", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check that the application is running without accessing the database."""
    return HealthResponse(status="ok")


@health_router.get(
    "/readyz",
    response_model=ReadinessResponse,
)
async def readiness_check() -> ReadinessResponse | JSONResponse:
    """Check that the application can reach the database and the job queue.

    Both are needed to accept work: without the queue a POST could create a job
    that nothing would ever run.
    """
    try:
        await check_database()
    except PsycopgError as exc:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        ) from exc
    try:
        await check_queue()
    except RedisError as exc:
        raise HTTPException(
            status_code=503,
            detail="Job queue unavailable",
        ) from exc
    return ReadinessResponse(status="ready")
