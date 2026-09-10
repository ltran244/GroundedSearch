from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import health_router
from app.db.pool import pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool.open()
    try:
        yield
    finally:
        pool.close()


app = FastAPI(lifespan=lifespan)
app.include_router(health_router)


@app.get("/")
def read_root():
    return {"Hello": "World"}
