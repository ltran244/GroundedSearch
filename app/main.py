from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from psycopg import OperationalError

from app.api.health import health_router
from app.api.research import research_router
from app.db.pool import pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool.open()
    try:
        yield
    finally:
        pool.close()


app = FastAPI(
    lifespan=lifespan,
)
app.include_router(health_router)
app.include_router(research_router)

@app.exception_handler(OperationalError)
async def database_unavailable(request: Request, exc: OperationalError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "Database unavailable"})