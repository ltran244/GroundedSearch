from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

import app.db.pool as pool_module

ChunkRow = tuple[UUID, int, str, list[float]]
"""(source_id, chunk_index, content, embedding)"""


async def save_chunks(rows: list[ChunkRow]) -> None:
    """Insert chunk rows, all of them or none."""
    if not rows:
        return
    async with pool_module.pool.connection(timeout=5) as conn:
        async with conn.cursor() as cursor:
            await cursor.executemany(
                """
                INSERT INTO chunks (source_id, chunk_index, content, embedding)
                VALUES (%s, %s, %s, %s::vector)
                """,
                rows,
            )


async def get_nearest_chunks(
    job_id: UUID, query_embedding: list[float], limit: int
) -> list[dict[str, Any]]:
    """A job's chunks closest in meaning to the query vector, nearest first."""
    async with pool_module.pool.connection(timeout=5) as conn:
        async with conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                SELECT c.id, c.source_id, c.content,
                       c.embedding <=> %(embedding)s::vector AS distance
                FROM chunks AS c
                JOIN sources AS s ON s.id = c.source_id
                WHERE s.research_job_id = %(job_id)s
                ORDER BY c.embedding <=> %(embedding)s::vector
                LIMIT %(limit)s
                """,
                {"job_id": job_id, "embedding": query_embedding, "limit": limit},
            )
            return await cursor.fetchall()
