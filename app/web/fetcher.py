import asyncio

import httpx

from app.web import extractor

MAX_PAGE_BYTES = 5 * 1024 * 1024


class FetchError(Exception):
    """Raised when no page produced readable text."""


async def fetch_pages(urls: list[str]) -> dict[str, str]:
    """Download every URL concurrently; map each readable URL to its extracted text."""
    pages: dict[str, str | None] = dict.fromkeys(urls)
    semaphore = asyncio.Semaphore(4)

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:

        async def fetch_one(url: str) -> None:
            async with semaphore:
                try:
                    async with asyncio.timeout(30):
                        async with client.stream("GET", url) as response:
                            response.raise_for_status()
                            content_type = (
                                response.headers.get("Content-Type", "")
                                .split(";", 1)[0]
                                .strip()
                                .lower()
                            )
                            if content_type not in ("text/html", "application/xhtml+xml"):
                                return
                            # read the body in chunks to avoid big downloads
                            body = bytearray()
                            async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                                if len(body) + len(chunk) > MAX_PAGE_BYTES:
                                    return
                                body.extend(chunk)
                            html = body.decode(
                                response.encoding or "utf-8", errors="replace"
                            )
                            # Trafilatura is CPU work; a thread keeps it from
                            # blocking the event loop and the other downloads.
                            text = await asyncio.to_thread(extractor.extract_text, html)
                            if text is not None:
                                pages[url] = text
                except Exception:
                    # Any escaping exception would make the TaskGroup cancel
                    # every other download; a broken page only costs itself.
                    pass

        async with asyncio.TaskGroup() as group:
            for url in urls:
                group.create_task(fetch_one(url))

    # pages was built from urls, so this keeps the order they were given in.
    texts = {url: text for url, text in pages.items() if text is not None}
    if not texts:
        raise FetchError("No pages had readable text")
    return texts
