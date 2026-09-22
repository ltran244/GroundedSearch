import trafilatura


def extract_text(html: str) -> str | None:
    """Pull the main readable text out of a page, or None if there isn't any."""
    text = trafilatura.extract(html)
    return text.strip() if text and text.strip() else None
