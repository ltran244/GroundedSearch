from uuid import UUID

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.config import settings

# Connected on first use, closed by the lifespan in app.main.
queue: ArqRedis | None = None


def redis_settings() -> RedisSettings:
    return RedisSettings(host=settings.redis_host, port=settings.redis_port)


async def open_queue() -> ArqRedis:
    """Return the shared queue connection, connecting on first use."""
    global queue
    if queue is None:
        queue = await create_pool(redis_settings())
    return queue


async def close_queue() -> None:
    global queue
    if queue is not None:
        await queue.aclose()
        queue = None


async def check_queue() -> None:
    """Raise if Redis is unreachable."""
    await (await open_queue()).ping()


async def enqueue_research(job_id: UUID) -> None:
    """Hand a job to the worker. Raises if Redis is unreachable."""
    await (await open_queue()).enqueue_job("research_task", str(job_id))
