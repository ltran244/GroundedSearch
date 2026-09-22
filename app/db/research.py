from uuid import UUID

from psycopg.rows import dict_row

import app.db.pool as pool_module


async def post_research(query: str, answer: str | None = None) -> UUID:
    """Insert a pending research job and return its generated ID."""
    async with pool_module.pool.connection(timeout=2) as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO research_jobs (query, answer)
                VALUES (%s, %s)
                RETURNING id
                """,
                (query, answer),
            )
            row = await cursor.fetchone()
            if row is None:
                raise RuntimeError("Research insert did not return an ID")
            job_id = row[0]
    return job_id


async def get_research(job_id: UUID) -> dict[str, str | UUID | None] | None:
    """Retrieve a research job by ID, or None if it does not exist."""
    async with pool_module.pool.connection(timeout=2) as conn:
        async with conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                SELECT id, query, status, answer, error_message
                FROM research_jobs
                WHERE id = %s
                """,
                (job_id,),
            )
            return await cursor.fetchone()


async def save_queries(job_id: UUID, queries: list[str]) -> None:
    """Save a job's search queries, all of them or none."""
    async with pool_module.pool.connection(timeout=2) as conn:
        async with conn.cursor() as cursor:
            await cursor.executemany(
                """
                INSERT INTO search_queries (research_job_id, query, position)
                VALUES (%s, %s, %s)
                """,
                [(job_id, query, position) for position, query in enumerate(queries)],
            )


async def mark_job_running(job_id: UUID) -> None:
    """Mark a job as started, so 'running' means work actually began."""
    async with pool_module.pool.connection(timeout=2) as conn:
        await conn.execute(
            "UPDATE research_jobs SET status = 'running' WHERE id = %s",
            (job_id,),
        )


async def mark_job_failed(job_id: UUID, message: str) -> None:
    """Record why a job failed, in its own transaction."""
    async with pool_module.pool.connection(timeout=2) as conn:
        await conn.execute(
            """
            UPDATE research_jobs
            SET status = 'failed', error_message = %s, completed_at = now()
            WHERE id = %s
            """,
            (message, job_id),
        )


async def complete_job(job_id: UUID, answer: str) -> None:
    """Save the answer and mark the job completed, in one transaction.

    UPDATE research_jobs SET answer, status = 'completed', completed_at = now().
    Both change together so a job is never 'completed' without its answer.
    """
    raise NotImplementedError
