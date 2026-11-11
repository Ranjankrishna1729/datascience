from __future__ import annotations

from datetime import date
from pathlib import Path

from daily_ca.fetchers.insights import (
    candidate_article_urls,
    parse_article,
    parse_date_from_title,
    parse_listing,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_date_from_title():
    assert parse_date_from_title("UPSC CURRENT AFFAIRS – 11 NOVEMBER 2026") == date(
        2026, 11, 11
    )
    assert parse_date_from_title("UPSC CURRENT AFFAIRS &#8211; 9 NOVEMBER 2026") == date(
        2026, 11, 9
    )


def test_parse_listing_fixture():
    html = (FIXTURES / "category_sample.html").read_text(encoding="utf-8")
    items = parse_listing(html, "https://www.insightsonindia.com/category/current-affairs-2/")
    assert len(items) >= 2
    assert items[0].article_date == date(2026, 11, 11)
    assert "upsc-current-affairs-11-november-2026" in items[0].url


def test_parse_article_fixture():
    html = (FIXTURES / "article_sample.html").read_text(encoding="utf-8")
    url = "https://www.insightsonindia.com/2026/11/11/upsc-current-affairs-11-november-2026/"
    article = parse_article(html, url)
    assert article.source == "insightsias"
    assert article.article_date == date(2026, 11, 11)
    assert "CURRENT AFFAIRS" in article.title.upper()
    assert article.body_text
    assert ("GEM" in article.body_text) or ("Education" in article.body_text)
    assert article.body_html
    assert ("entry-content" in article.body_html) or ("ca-article" in article.body_html)


def test_candidate_urls_contain_modern_slug():
    urls = candidate_article_urls(date(2026, 11, 11))
    assert any("upsc-current-affairs-11-november-2026" in u for u in urls)