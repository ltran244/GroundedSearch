from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

import app.db.pool as pool_module
from app.search.models import QueryResults


async def save_sources(job_id: UUID, results: list[QueryResults]) -> dict[str, UUID]:
    """Save sources atomically, keeping the first query to find each URL."""
    async with pool_module.pool.connection(timeout=2) as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT query, id FROM search_queries WHERE research_job_id = %s",
                (job_id,),
            )
            query_ids = dict(await cursor.fetchall())
            rows = [
                (
                    job_id,
                    query_ids[group.query],
                    rank,
                    result.url,
                    result.title,
                    result.description,
                )
                for group in results
                for rank, result in enumerate(group.results)
            ]

            await cursor.executemany(
                """
                INSERT INTO sources
                    (research_job_id, search_query_id, rank, url, title, snippet)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (research_job_id, url) DO NOTHING
                """,
                rows,
            )
            # A separate SELECT also includes IDs skipped by ON CONFLICT.
            urls = list(
                dict.fromkeys(result.url for group in results for result in group.results)
            )
            await cursor.execute(
                """
                SELECT url, id FROM sources
                WHERE research_job_id = %s AND url = ANY(%s)
                """,
                (job_id, urls),
            )
            source_ids = dict(await cursor.fetchall())
    return {url: source_ids[url] for url in urls}


async def save_contents(sources: list[tuple[UUID, str]]) -> None:
    """Store the extracted text of readable sources, all of them or none."""
    if not sources:
        return
    async with pool_module.pool.connection(timeout=2) as conn:
        async with conn.cursor() as cursor:
            await cursor.executemany(
                """
                UPDATE sources
                SET content = %s, retrieved_at = now()
                WHERE id = %s
                """,
                [(text, source_id) for source_id, text in sources],
            )


async def set_citation_numbers(source_ids: list[UUID]) -> None:
    """Number the sources that went into the answer prompt, 1-based."""
    if not source_ids:
        return
    async with pool_module.pool.connection(timeout=2) as conn:
        async with conn.cursor() as cursor:
            await cursor.executemany(
                "UPDATE sources SET citation_number = %s WHERE id = %s",
                [
                    (number, source_id)
                    for number, source_id in enumerate(source_ids, start=1)
                ],
            )


async def get_sources(job_id: UUID) -> list[dict[str, Any]]:
    """A job's sources, cited ones first in citation order."""
    async with pool_module.pool.connection(timeout=2) as conn:
        async with conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                SELECT citation_number AS number, title, url, snippet
                FROM sources
                WHERE research_job_id = %s
                ORDER BY citation_number NULLS LAST, rank, url
                """,
                (job_id,),
            )
            return await cursor.fetchall()
