import trafilatura


def extract_text(html: str) -> str | None:
    """Pull the main readable text out of a page, or None if there isn't any."""
    text = trafilatura.extract(html)
    if not text or len(text) < 50:
        return None
    return text.strip()
