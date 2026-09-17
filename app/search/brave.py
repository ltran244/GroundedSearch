import httpx
from anyio import CapacityLimiter, create_task_group, fail_after

from app.config import settings
from app.search.models import BraveSearchResponse, QuerySearchResults

_limiter = CapacityLimiter(settings.brave_max_concurrent_requests)


class BraveSearchError(Exception):
    """Brave could not complete the searches or returned an invalid response."""


def get_client() -> httpx.AsyncClient:
    """Create a Brave API client; use it with async with to close connections."""
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
        timeout=httpx.Timeout(30.0, connect=5.0),
        limits=httpx.Limits(
            max_connections=settings.brave_max_concurrent_requests,
            max_keepalive_connections=settings.brave_max_concurrent_requests,
        ),
    )


async def search_queries(queries: list[str]) -> list[QuerySearchResults]:
    """Search concurrently, preserving query order; fail if any search fails."""
    results = [QuerySearchResults(query=query) for query in queries]
    try:
        async with get_client() as client:

            async def search_one(index: int, query: str) -> None:
                async with _limiter:
                    with fail_after(30):
                        response = await client.get(
                            "web/search",
                            params={
                                "q": query,
                                "count": 5,
                                "result_filter": "web",
                                "text_decorations": "false",
                            },
                        )
                        response.raise_for_status()
                        parsed = BraveSearchResponse.model_validate(response.json())
                    results[index].results = parsed.web.results if parsed.web else []

            # A failed task cancels its siblings before the HTTP client closes.
            async with create_task_group() as tasks:
                for index, query in enumerate(queries):
                    tasks.start_soon(search_one, index, query)
    except Exception as exc:
        raise BraveSearchError("Brave search failed") from exc
    return results
