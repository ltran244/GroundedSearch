from app.web.extractor import extract_text

ARTICLE = """
<html><body>
  <nav>Home About Subscribe</nav>
  <article><p>Photovoltaic cells convert sunlight into electricity, and a
  typical installation produces several kilowatts.</p></article>
  <footer>Copyright 2026</footer>
</body></html>
"""


def test_keeps_the_article_and_drops_the_rest():
    text = extract_text(ARTICLE)

    assert text is not None
    assert "Photovoltaic cells" in text
    assert "Subscribe" not in text
    assert "Copyright" not in text


def test_rejects_a_page_with_no_article():
    # Trafilatura returns scraps ("Home"); the length floor rejects them.
    assert extract_text("<html><body><nav>Home</nav></body></html>") is None


def test_rejects_text_under_the_length_floor():
    assert (
        extract_text("<html><body><article><p>Too short.</p></article></body></html>")
        is None
    )


def test_rejects_empty_html():
    assert extract_text("") is None
