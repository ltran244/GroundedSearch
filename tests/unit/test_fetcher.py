import asyncio
from unittest.mock import patch

import httpx
import pytest

from app.web import fetcher
from app.web.fetcher import FetchError, fetch_pages

A = "https://a.test/"
B = "https://b.test/"


def run_with(handler, urls, extracted: str | None = "text"):
    """Run fetch_pages against a fake network, with extraction stubbed out."""
    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient  # captured before the patch replaces it

    with (
        patch(
            "app.web.fetcher.httpx.AsyncClient",
            side_effect=lambda **kw: real_client(transport=transport, **kw),
        ),
        patch.object(fetcher.extractor, "extract_text", return_value=extracted),
    ):
        return asyncio.run(fetch_pages(urls))


def ok(request):
    return httpx.Response(200, headers={"Content-Type": "text/html"}, text="<html/>")


def only_b_works(bad: httpx.Response | Exception):
    def handler(request):
        if request.url.host == "a.test":
            if isinstance(bad, Exception):
                raise bad
            return bad
        return ok(request)

    return handler


def test_returns_text_for_pages_that_work():
    assert run_with(ok, [A, B]) == {A: "text", B: "text"}


def test_keeps_the_order_the_urls_were_given_in():
    # Source order is what the citation numbering relies on.
    assert list(run_with(ok, [B, A])) == [B, A]


def test_skips_a_page_that_404s():
    assert run_with(only_b_works(httpx.Response(404)), [A, B]) == {B: "text"}


def test_skips_a_page_that_is_not_html():
    pdf = httpx.Response(
        200, headers={"Content-Type": "application/pdf"}, content=b"%PDF-"
    )

    assert run_with(only_b_works(pdf), [A, B]) == {B: "text"}


def test_skips_a_page_over_the_size_cap(monkeypatch):
    monkeypatch.setattr(fetcher, "MAX_PAGE_BYTES", 10)
    big = httpx.Response(200, headers={"Content-Type": "text/html"}, text="x" * 100)

    assert run_with(only_b_works(big), [A, B]) == {B: "text"}


def test_skips_a_page_that_errors():
    assert run_with(only_b_works(httpx.ConnectError("dns")), [A, B]) == {B: "text"}


def test_raises_when_nothing_is_readable():
    with pytest.raises(FetchError):
        run_with(ok, [A, B], extracted=None)


def test_raises_when_nothing_downloads():
    with pytest.raises(FetchError):
        run_with(lambda request: httpx.Response(500), [A, B])
