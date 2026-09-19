from uuid import UUID

from psycopg.rows import dict_row

import app.db.pool as pool_module


def post_research(query: str, answer: str | None = None) -> UUID:
    """Insert a pending research job and return its generated ID."""
    with pool_module.pool.connection(timeout=2) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO research_jobs (query, answer)
                VALUES (%s, %s)
                RETURNING id
                """,
                (query, answer),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Research insert did not return an ID")
            job_id = row[0]
    return job_id


def get_research(job_id: UUID) -> dict[str, str | UUID | None] | None:
    """Retrieve a research job by ID, or None if it does not exist."""
    with pool_module.pool.connection(timeout=2) as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT id, query, status, answer, error_message
                FROM research_jobs
                WHERE id = %s
                """,
                (job_id,),
            )
            return cursor.fetchone()
