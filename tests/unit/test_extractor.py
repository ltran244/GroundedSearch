from app.web.extractor import extract_text

ARTICLE = """
<html><body>
  <nav>Home About Contact Subscribe</nav>
  <div class="ad">Buy now! Limited offer!</div>
  <article>
    <h1>Solar panels</h1>
    <p>Photovoltaic cells convert sunlight directly into electricity, and a
    typical residential installation produces several kilowatts.</p>
    <p>Efficiency has improved steadily, with commercial panels now converting
    around a fifth of the light that reaches them.</p>
  </article>
  <footer>Copyright 2026. All rights reserved.</footer>
</body></html>
"""


def test_keeps_the_article_and_drops_the_rest():
    text = extract_text(ARTICLE)

    assert text is not None
    assert "Photovoltaic cells convert sunlight" in text
    # Navigation, ads and the footer are what Trafilatura is here to remove.
    assert "Subscribe" not in text
    assert "Buy now" not in text
    assert "All rights reserved" not in text


def test_a_page_with_no_article_yields_only_scraps():
    # Trafilatura does not return None here: it falls back to whatever text it
    # finds. Nothing filters these out yet, so a junk page can still become a
    # "usable" source. A minimum-length check in extract_text would fix it.
    text = extract_text("<html><body><nav>Home</nav></body></html>")

    assert text == "Home"


def test_returns_none_for_empty_html():
    assert extract_text("") is None
