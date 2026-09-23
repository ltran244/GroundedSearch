import asyncio
from unittest.mock import patch

import httpx
import pytest

from app.search.brave import BraveSearchError, search_all, search_one

WEB_RESPONSE = {
    "web": {
        "results": [
            {
                "title": "Rust vs C++",
                "url": "https://example.com/a",
                "description": "A comparison",
                "age": "2 days",
            },
            {"title": "No snippet", "url": "https://example.com/b"},
        ]
    },
    "news": {"results": []},
}


def client_for(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.search.brave.com/res/v1/",
    )


def search(handler, query="rust"):
    async def run():
        async with client_for(handler) as client:
            return await search_one(client, query)

    return asyncio.run(run())


def test_parses_results_and_keeps_the_query():
    results = search(lambda request: httpx.Response(200, json=WEB_RESPONSE))

    assert results.query == "rust"
    assert [r.url for r in results.results] == [
        "https://example.com/a",
        "https://example.com/b",
    ]
    assert results.results[0].description == "A comparison"
    # Brave omits the description on some results.
    assert results.results[1].description == ""


def test_sends_the_documented_query_parameters():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.url.params)
        return httpx.Response(200, json=WEB_RESPONSE)

    search(handler, query="solar panels")

    assert seen["q"] == "solar panels"
    # Without this, Brave wraps matched words in <strong> inside descriptions.
    assert seen["text_decorations"] == "false"


def test_a_query_with_no_web_results_is_empty_not_an_error():
    # Brave leaves out the whole "web" section rather than sending an empty list.
    results = search(lambda request: httpx.Response(200, json={"type": "search"}))

    assert results.results == []


def test_http_error_becomes_a_brave_search_error():
    with pytest.raises(BraveSearchError):
        search(lambda request: httpx.Response(500))


def test_unparseable_body_becomes_a_brave_search_error():
    with pytest.raises(BraveSearchError):
        search(lambda request: httpx.Response(200, text="not json"))


def search_many(handler, queries):
    with patch("app.search.brave.get_client", side_effect=lambda: client_for(handler)):
        return asyncio.run(search_all(queries))


def test_search_all_returns_results_in_query_order():
    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params["q"]
        return httpx.Response(
            200,
            json={"web": {"results": [{"title": query, "url": f"https://x/{query}"}]}},
        )

    results = search_many(handler, ["first", "second", "third"])

    assert [group.query for group in results] == ["first", "second", "third"]


def test_search_all_with_no_queries_calls_nothing():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request should be sent")

    assert search_many(handler, []) == []


def test_one_failed_search_fails_the_batch():
    # Unlike page fetching, a missing search means the evidence is incomplete.
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["q"] == "second":
            return httpx.Response(500)
        return httpx.Response(200, json=WEB_RESPONSE)

    with pytest.raises(BraveSearchError):
        search_many(handler, ["first", "second"])
