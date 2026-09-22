async def fetch_pages(urls: list[str]) -> dict[str, str | None]:
    """Download every URL concurrently; map each URL to its HTML, or None.

    1. One httpx.AsyncClient with follow_redirects=True and a per-page timeout,
       so one slow site can't hold up the job.
    2. A semaphore caps how many downloads run at once.
    3. Unlike Brave search, a failed page is normal (paywalls, 404s, sites that
       block bots): record None for it and keep going. Only fail the job if
       every page failed.
    4. Skip responses that aren't HTML (PDFs, images) by checking Content-Type.
    """
    raise NotImplementedError
