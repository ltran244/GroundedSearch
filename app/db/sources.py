from uuid import UUID

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


async def save_contents(contents: dict[UUID, str]) -> None:
    """Store extracted text for many sources in one transaction.

    Only pages that produced text are passed in, so sources that could not be
    fetched or read keep content NULL. Sets retrieved_at = now() alongside.
    The raw HTML is never saved: it goes from fetch_pages to extract_text in memory.
    """
    if not contents:
        return
    async with pool_module.pool.connection(timeout=2) as conn:
        async with conn.cursor() as cursor:
            await cursor.executemany(
                "UPDATE sources SET content = %s, retrieved_at = now() WHERE id = %s",
                # Content first, id second, matching the placeholder order.
                [(text, source_id) for source_id, text in contents.items()],
            )
