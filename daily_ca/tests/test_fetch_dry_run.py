from __future__ import annotations

from datetime import date
from pathlib import Path

from daily_ca.config import Settings
from daily_ca.db import Database
from daily_ca.fetchers.insights import InsightsFetcher, parse_listing

FIXTURES = Path(__file__).parent / "fixtures"


class FakeSession:
    def __init__(self, listing_html: str):
        self.listing_html = listing_html
        self.gets: list[str] = []

    def get_text(self, url: str) -> str:
        self.gets.append(url)
        if "category" in url:
            return self.listing_html
        raise AssertionError(f"dry-run should not fetch article body: {url}")


def test_dry_run_resolves_listing_without_writing(tmp_path):
    html = (FIXTURES / "category_sample.html").read_text(encoding="utf-8")
    # sanity on fixture
    assert parse_listing(html, "https://example.com/") 

    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'ca.sqlite3'}",
        user_agent="test-agent",
        request_delay_seconds=0,
        request_timeout_seconds=5,
        insights_category_url="https://www.insightsonindia.com/category/current-affairs-2/",
    )
    db = Database(settings.sqlite_path)
    session = FakeSession(html)
    fetcher = InsightsFetcher(settings, db, session=session)

    result = fetcher.fetch_date(date(2026, 11, 11), dry_run=True)
    assert result["status"] == "dry_run"
    assert result["inserted"] == 0
    assert "upsc-current-affairs-11-november-2026" in (result["url"] or "")
    assert not db.has_date("insightsias", date(2026, 11, 11))
    assert len(session.gets) == 1  # listing only