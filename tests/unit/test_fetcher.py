import asyncio
from unittest.mock import patch

import httpx
import pytest

from app.web import fetcher
from app.web.fetcher import FetchError, fetch_pages

PAGE_A = "https://example.com/a"
PAGE_B = "https://example.com/b"


def run_with(handler, urls, extracted: str | None = "Readable text"):
    """Run fetch_pages against a fake network, with extraction stubbed out.

    httpx.MockTransport answers requests in-process, so no page is ever really
    downloaded. extract_text is stubbed so these tests check the fetcher's
    behaviour rather than Trafilatura's judgement.
    """
    transport = httpx.MockTransport(handler)
    # Captured before patching: the patch replaces httpx.AsyncClient itself.
    real_client = httpx.AsyncClient

    def build_client(**kwargs):
        return real_client(transport=transport, **kwargs)

    with (
        patch("app.web.fetcher.httpx.AsyncClient", side_effect=build_client),
        patch.object(fetcher.extractor, "extract_text", return_value=extracted),
    ):
        return asyncio.run(fetch_pages(urls))


def html_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, headers={"Content-Type": "text/html"}, text="<html/>")


def test_returns_text_for_every_page_that_works():
    pages = run_with(html_response, [PAGE_A, PAGE_B])

    assert pages == {PAGE_A: "Readable text", PAGE_B: "Readable text"}


def test_keeps_the_order_the_urls_were_given_in():
    # Downloads finish in any order; source rank order is what the citation
    # numbering relies on, so the result must follow the input.
    pages = run_with(html_response, [PAGE_B, PAGE_A])

    assert list(pages) == [PAGE_B, PAGE_A]


def test_one_failed_page_does_not_affect_the_others():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/a":
            return httpx.Response(404)
        return html_response(request)

    pages = run_with(handler, [PAGE_A, PAGE_B])

    assert pages == {PAGE_B: "Readable text"}


def test_skips_responses_that_are_not_html():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/a":
            return httpx.Response(
                200, headers={"Content-Type": "application/pdf"}, content=b"%PDF-"
            )
        return html_response(request)

    pages = run_with(handler, [PAGE_A, PAGE_B])

    assert pages == {PAGE_B: "Readable text"}


def test_skips_pages_over_the_size_cap(monkeypatch):
    monkeypatch.setattr(fetcher, "MAX_PAGE_BYTES", 50)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/a":
            return httpx.Response(
                200, headers={"Content-Type": "text/html"}, text="x" * 500
            )
        return html_response(request)

    pages = run_with(handler, [PAGE_A, PAGE_B])

    assert pages == {PAGE_B: "Readable text"}


def test_a_network_error_only_costs_that_page():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/a":
            raise httpx.ConnectError("dns failure")
        return html_response(request)

    pages = run_with(handler, [PAGE_A, PAGE_B])

    assert pages == {PAGE_B: "Readable text"}


def test_downloaded_pages_with_no_readable_text_count_as_failures():
    # Every page downloaded fine but none had article text, so there is still
    # nothing to answer from.
    with pytest.raises(FetchError):
        run_with(html_response, [PAGE_A, PAGE_B], extracted=None)


def test_raises_when_no_page_produces_text():
    with pytest.raises(FetchError):
        run_with(lambda request: httpx.Response(500), [PAGE_A, PAGE_B])
