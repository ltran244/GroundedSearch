import asyncio

import httpx

from app.config import settings
from app.search.models import BraveSearchResponse, QueryResults


class BraveSearchError(RuntimeError):
    """Raised when Brave cannot complete a search or returns an invalid response."""


def get_client() -> httpx.AsyncClient:
    """Create a Brave Search client; use it with `async with` so it closes."""
    if (
        not settings.brave_search_api_key
        or not settings.brave_search_api_key.get_secret_value()
    ):
        raise ValueError("Set BRAVE_SEARCH_API_KEY in .env before using Brave Search")
    return httpx.AsyncClient(
        base_url="https://api.search.brave.com/res/v1/",
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": settings.brave_search_api_key.get_secret_value(),
        },
        # Fail fast if Brave is unreachable; allow longer for the response itself.
        timeout=httpx.Timeout(30.0, connect=5.0),
        # Never open more connections than searches allowed to run at once.
        limits=httpx.Limits(
            max_connections=settings.brave_max_concurrent_requests,
            max_keepalive_connections=settings.brave_max_concurrent_requests,
        ),
    )


async def search_one(client: httpx.AsyncClient, query: str) -> QueryResults:
    """Search one query; no web results is a valid, empty result."""
    if not query.strip() or len(query) > 600 or len(query.split()) > 75:
        raise BraveSearchError(
            "Search queries must contain 1-600 characters and 1-75 words"
        )
    try:
        # HTTPX timeouts limit individual I/O waits; this bounds the whole request.
        async with asyncio.timeout(30):
            response = await client.get(
                "web/search",
                params={
                    "q": query,
                    "count": settings.brave_results_per_query,
                    "result_filter": "web",
                    "extra_snippets": "true",
                    "text_decorations": "false",
                    # Preserve technical terms and names in generated queries.
                    "spellcheck": "false",
                    "safesearch": "moderate",
                },
            )
        response.raise_for_status()
        parsed = BraveSearchResponse.model_validate(response.json())
    except (httpx.HTTPError, ValueError, TimeoutError) as exc:
        raise BraveSearchError(
            "Brave search failed or returned an invalid response"
        ) from exc
    return QueryResults(query=query, results=parsed.web.results if parsed.web else [])


async def search_all(queries: list[str]) -> list[QueryResults]:
    """Search with bounded concurrency, preserving order and failing as a batch."""
    if not queries:
        return []
    semaphore = asyncio.Semaphore(settings.brave_max_concurrent_requests)
    try:
        async with get_client() as client:

            async def bounded_search(query: str) -> QueryResults:
                async with semaphore:
                    return await search_one(client, query)

            # TaskGroup cancels and awaits sibling tasks before the client closes.
            async with asyncio.TaskGroup() as group:
                tasks = [group.create_task(bounded_search(query)) for query in queries]
            return [task.result() for task in tasks]
    except Exception as exc:
        raise BraveSearchError("Brave could not complete all searches") from exc
