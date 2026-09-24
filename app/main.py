from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from psycopg import OperationalError
from redis.exceptions import RedisError

from app.api.health import health_router
from app.api.research import research_router
from app.db.pool import check_database, pool
from app.llm.client import check_gemini
from app.queue import check_queue, close_queue


async def check_dependencies() -> None:
    """Warn at startup if a dependency is down, but never stop the app starting."""
    try:
        await check_database()
    except Exception as exc:
        print(f"Startup check: database unavailable ({exc})")
    try:
        await check_gemini()
    except Exception as exc:
        print(f"Startup check: Gemini unavailable ({exc})")
    try:
        await check_queue()
    except Exception as exc:
        print(f"Startup check: job queue unavailable ({exc})")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await pool.open()
    await check_dependencies()
    try:
        yield
    finally:
        await close_queue()
        await pool.close()


app = FastAPI(
    lifespan=lifespan,
)
app.include_router(health_router)
app.include_router(research_router)


@app.exception_handler(OperationalError)
async def database_unavailable(request: Request, exc: OperationalError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "Database unavailable"})


@app.exception_handler(RedisError)
async def queue_unavailable(request: Request, exc: RedisError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "Job queue unavailable"})
