def extract_text(html: str) -> str | None:
    """Pull the main readable text out of a page, or None if there isn't any.

    trafilatura.extract(html) drops navigation, ads, cookie banners and footers,
    leaving the article body. It returns None for pages with no real content
    (login walls, empty shells rendered by JavaScript), which the caller skips.
    Needs `uv add trafilatura`.
    """
    raise NotImplementedError
