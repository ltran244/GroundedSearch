from uuid import UUID

import app.db.pool as pool_module


def create_job_with_queries(question: str, queries: list[str]) -> UUID:
    """Save a question and its generated queries together, or save neither."""
    question = question.strip()
    queries = [query.strip() for query in queries]
    if not question:
        raise ValueError("Question must not be blank")
    if not 3 <= len(queries) <= 5 or any(not query for query in queries):
        raise ValueError("Provide 3-5 nonempty search queries")
    if len({" ".join(query.casefold().split()) for query in queries}) != len(queries):
        raise ValueError("Search queries must be distinct")

    with pool_module.pool.connection(timeout=2) as conn:
        # The connection context commits both inserts, or rolls back on failure.
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO research_jobs (query) VALUES (%s) RETURNING id",
                (question,),
            )
            row = cursor.fetchone()
            assert row is not None
            job_id = row[0]
            cursor.executemany(
                """
                INSERT INTO search_queries (research_job_id, query, position)
                VALUES (%s, %s, %s)
                """,
                [(job_id, query, position) for position, query in enumerate(queries)],
            )
    return job_id


def save_queries(job_id: UUID, queries: list[str]) -> None:
    """Save all validated queries and advance the job in one transaction."""
    with pool_module.pool.connection(timeout=2) as conn:
        with conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO search_queries (research_job_id, query, position)
                VALUES (%s, %s, %s)
                """,
                [(job_id, query, position) for position, query in enumerate(queries)],
            )
            cursor.execute(
                "UPDATE research_jobs SET status = 'pending' WHERE id = %s",
                (job_id,),
            )


def mark_job_failed(job_id: UUID, message: str) -> None:
    with pool_module.pool.connection(timeout=2) as conn:
        conn.execute(
            """
            UPDATE research_jobs
            SET status = 'failed', error_message = %s, completed_at = now()
            WHERE id = %s
            """,
            (message, job_id),
        )
