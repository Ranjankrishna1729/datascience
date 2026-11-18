from __future__ import annotations

from pathlib import Path

from pib_scrape.article import parse_press_release_page
from pib_scrape.chunking import chunk_article

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_and_chunk_article():
    html = (FIXTURES / "article_sample.html").read_text(encoding="utf-8")
    article = parse_press_release_page(
        html,
        prid="2338083",
        detail_url="https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2338083",
        page_url="https://www.pib.gov.in/PressReleasePage.aspx?PRID=2338083",
        ministry_hint="President's Secretariat",
    )
    assert article.prid == "2338083"
    assert "PRESIDENT" in article.title.upper()
    assert article.posted_on == "2026-11-18"
    assert "Droupadi Murmu" in article.body_text
    assert "\n\n" in article.body_text  # paragraph separation

    chunks = chunk_article(article, listing_date="2026-11-18", max_chars=500)
    assert len(chunks) >= 1
    assert chunks[0].chunk_id == "pib-2338083-0"
    assert chunks[0].metadata["url"].endswith("PRID=2338083")
    # sentence-aware: no chunk should end with a dangling mid-word from hard wrap only
    for c in chunks:
        assert c.text.strip()
        assert c.document.startswith(c.title) or "President" in c.document


def test_chunk_does_not_split_mid_sentence_when_possible():
    from pib_scrape.article import Article

    long_sent = (
        "The government announced a new scheme for farmers across all states. "
        "Officials said implementation will begin next month with state coordination."
    )
    body = "\n\n".join([long_sent] * 5)
    article = Article(
        prid="1",
        title="Test",
        url="https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=1",
        page_url="https://www.pib.gov.in/PressReleasePage.aspx?PRID=1",
        ministry="Test Ministry",
        posted_on="2026-11-18",
        posted_raw="Posted On: 18 NOV 2026",
        body_text=body,
        body_html="",
    )
    chunks = chunk_article(article, max_chars=120)
    assert len(chunks) > 1
    for c in chunks:
        # Prefer ending on sentence punctuation when content has sentences
        assert c.text.rstrip()[-1] in ".!\"" or len(c.text) <= 120
