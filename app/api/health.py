from typing import Literal

from fastapi import APIRouter, HTTPException, status
from psycopg import Error as PsycopgError
from pydantic import BaseModel

from app.db.pool import pool

health_router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    status: Literal["ready"]


class ErrorResponse(BaseModel):
    detail: str


@health_router.get("/healthz", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Check that the application is running without accessing the database."""
    return HealthResponse(status="ok")


@health_router.get(
    "/readyz",
    response_model=ReadinessResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Database unavailable",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {"detail": "Database unavailable"},
                },
            },
        },
    },
)
def readiness_check() -> ReadinessResponse:
    """Check that the application can execute a database query."""
    try:
        with pool.connection(timeout=2) as conn, conn.cursor() as cursor:
            cursor.execute("SELECT 1;")
            cursor.fetchone()
    except PsycopgError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc
    return ReadinessResponse(status="ready")
