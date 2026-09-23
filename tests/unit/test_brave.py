import asyncio
from unittest.mock import patch

import httpx
import pytest

from app.search.brave import BraveSearchError, search_all, search_one

# "age" is one of many fields the model ignores.
RESPONSE = {
    "web": {"results": [{"title": "T", "url": "u", "description": "d", "age": "1d"}]}
}


def client_for(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://brave.test/"
    )


def search(handler, query="q"):
    async def run():
        async with client_for(handler) as client:
            return await search_one(client, query)

    return asyncio.run(run())


def ok(request):
    return httpx.Response(200, json=RESPONSE)


def test_parses_results():
    results = search(ok)

    assert results.query == "q"
    assert [(r.title, r.url, r.description) for r in results.results] == [("T", "u", "d")]


def test_missing_description_defaults_to_empty():
    response = {"web": {"results": [{"title": "T", "url": "u"}]}}
    results = search(lambda request: httpx.Response(200, json=response))

    assert results.results[0].description == ""


def test_sends_the_query_without_html_decorations():
    seen = {}

    def handler(request):
        seen.update(request.url.params)
        return ok(request)

    search(handler, query="solar panels")

    assert seen["q"] == "solar panels"
    assert seen["text_decorations"] == "false"


def test_no_web_section_is_an_empty_result():
    results = search(lambda request: httpx.Response(200, json={}))

    assert results.results == []


def test_http_error_raises():
    with pytest.raises(BraveSearchError):
        search(lambda request: httpx.Response(500))


def test_unparseable_body_raises():
    with pytest.raises(BraveSearchError):
        search(lambda request: httpx.Response(200, text="not json"))


def search_many(handler, queries):
    with patch("app.search.brave.get_client", side_effect=lambda: client_for(handler)):
        return asyncio.run(search_all(queries))


def test_results_follow_query_order():
    def handler(request):
        query = request.url.params["q"]
        return httpx.Response(
            200, json={"web": {"results": [{"title": query, "url": query}]}}
        )

    results = search_many(handler, ["a", "b", "c"])

    assert [group.query for group in results] == ["a", "b", "c"]


def test_no_queries_sends_nothing():
    def handler(request):
        raise AssertionError("no request expected")

    assert search_many(handler, []) == []


def test_one_failed_search_fails_the_batch():
    def handler(request):
        return httpx.Response(500) if request.url.params["q"] == "b" else ok(request)

    with pytest.raises(BraveSearchError):
        search_many(handler, ["a", "b"])
