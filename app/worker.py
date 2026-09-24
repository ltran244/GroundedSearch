from uuid import UUID

from arq import cron, func

import app.db.research as research_db
from app.agents.researcher import run_research
from app.config import settings
from app.db.pool import pool
from app.queue import redis_settings


async def research_task(ctx: dict, job_id: str) -> None:
    """Run one research job. Ids arrive as strings, since they go through Redis."""
    await run_research(UUID(job_id))


async def sweep_stale_jobs(ctx: dict) -> None:
    """Fail jobs stranded by a worker that died"""
    failed = await research_db.fail_stale_jobs()
    if failed:
        print(f"Swept {failed} stale job(s)")


async def startup(ctx: dict) -> None:
    await pool.open()


async def shutdown(ctx: dict) -> None:
    await pool.close()


class WorkerSettings:
    # max_tries=1: no retries
    functions = [func(research_task, max_tries=1)]
    redis_settings = redis_settings()
    max_jobs = settings.worker_max_jobs
    job_timeout = settings.worker_job_timeout_seconds
    # Every minute, and once on startup so a new worker cleans up after one
    # that died mid-job.
    cron_jobs = [cron(sweep_stale_jobs, minute=set(range(60)), run_at_startup=True)]
    on_startup = startup
    on_shutdown = shutdown
