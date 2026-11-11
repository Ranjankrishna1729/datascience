from __future__ import annotations

import calendar
import html as html_lib
import re
from dataclasses import dataclass
from datetime import date
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..config import SOURCE_INSIGHTS, Settings
from ..db import Article, Database
from ..http_client import PoliteSession

# Public listing used to discover daily CA posts.
# robots.txt (as of 2026-11): Disallow /wp-admin/, /demolive/, search/orderby query URLs.
# Category archives and posts are crawlable; we still rate-limit and identify ourselves.
TITLE_CA_RE = re.compile(r"UPSC\s+CURRE?NT\s+AFFAIRS", re.I)
DATE_IN_TITLE_RE = re.compile(
    r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+(\d{4})",
    re.I,
)
MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}


@dataclass
class ListingItem:
    title: str
    url: str
    article_date: Optional[date]


def parse_date_from_title(title: str) -> Optional[date]:
    cleaned = html_lib.unescape(title)
    m = DATE_IN_TITLE_RE.search(cleaned)
    if not m:
        return None
    day = int(m.group(1))
    month = MONTHS[m.group(2).lower()]
    year = int(m.group(3))
    try:
        return date(year, month, day)
    except ValueError:
        return None


def candidate_article_urls(target: date) -> list[str]:
    """Best-effort URL guesses for a calendar day (site slug conventions change)."""
    day = target.day
    month = calendar.month_name[target.month].lower()
    y, m = target.year, f"{target.month:02d}"
    d2 = f"{day:02d}"
    slugs = [
        f"upsc-current-affairs-{day}-{month}-{target.year}",
        f"upsc-current-affairs-{d2}-{month}-{target.year}",
        f"insights-daily-current-affairs-{day}-{month}-{target.year}",
        f"insights-daily-current-affairs-{d2}-{month}-{target.year}",
    ]
    base = f"https://www.insightsonindia.com/{y}/{m}/{d2}/"
    return [urljoin(base, slug + "/") for slug in slugs]


def parse_listing(html: str, base_url: str) -> list[ListingItem]:
    soup = BeautifulSoup(html, "lxml")
    items: list[ListingItem] = []
    seen: set[str] = set()

    for article in soup.select("article"):
        title_a = article.select_one("h2.entry-title a, h1.entry-title a, .entry-title a")
        if not title_a:
            continue
        title = html_lib.unescape(title_a.get_text(" ", strip=True))
        href = title_a.get("href")
        if not href:
            continue
        url = urljoin(base_url, href)
        if url in seen:
            continue
        if not TITLE_CA_RE.search(title) and "current-affairs" not in url:
            continue
        seen.add(url)

        article_date = parse_date_from_title(title)
        if article_date is None:
            time_el = article.select_one("time.entry-date[datetime], time[datetime]")
            if time_el and time_el.get("datetime"):
                try:
                    article_date = date.fromisoformat(time_el["datetime"][:10])
                except ValueError:
                    article_date = None

        items.append(ListingItem(title=title, url=url, article_date=article_date))

    return items


def parse_article(html: str, url: str) -> Article:
    soup = BeautifulSoup(html, "lxml")

    title_el = soup.select_one("h1.entry-title, h1")
    title = html_lib.unescape(title_el.get_text(" ", strip=True)) if title_el else url

    article_date = parse_date_from_title(title)
    if article_date is None:
        time_el = soup.select_one("time.entry-date[datetime], time[datetime]")
        if time_el and time_el.get("datetime"):
            try:
                article_date = date.fromisoformat(time_el["datetime"][:10])
            except ValueError:
                pass
    if article_date is None:
        # Fall back to YYYY/MM/DD in the path.
        m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
        if m:
            article_date = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        else:
            article_date = date.today()

    content = soup.select_one("div.entry-content") or soup.select_one("article")
    body_html = str(content) if content else None
    body_text = content.get_text("\n", strip=True) if content else None

    return Article(
        source=SOURCE_INSIGHTS,
        article_date=article_date,
        title=title,
        url=url,
        body_html=body_html,
        body_text=body_text,
    )


class InsightsFetcher:
    def __init__(
        self,
        settings: Settings,
        db: Database,
        session: Optional[PoliteSession] = None,
    ):
        self.settings = settings
        self.db = db
        self.session = session or PoliteSession(settings)

    def fetch_listing(self) -> list[ListingItem]:
        html = self.session.get_text(self.settings.insights_category_url)
        return parse_listing(html, self.settings.insights_category_url)

    def fetch_article(self, url: str) -> Article:
        html = self.session.get_text(url)
        return parse_article(html, url)

    def ingest_url(self, url: str, *, dry_run: bool = False) -> str:
        if self.db.has_url(SOURCE_INSIGHTS, url):
            return "skipped"
        if dry_run:
            return "dry_run"
        article = self.fetch_article(url)
        return self.db.upsert_article(article)

    def fetch_date(self, target: date, *, dry_run: bool = False) -> dict:
        """Fetch a single calendar day. Idempotent: skips if date or URL already stored."""
        run_id = self.db.start_fetch_run(SOURCE_INSIGHTS, target)
        inserted = skipped = 0
        message = None
        status = "ok"

        try:
            if self.db.has_date(SOURCE_INSIGHTS, target):
                skipped = 1
                status = "skipped"
                message = f"already have article(s) for {target.isoformat()}"
                return {
                    "status": status,
                    "inserted": inserted,
                    "skipped": skipped,
                    "message": message,
                    "url": None,
                }

            # Prefer listing match (handles Sundays / missing days / slug changes).
            chosen_url: Optional[str] = None
            listing = self.fetch_listing()
            for item in listing:
                if item.article_date == target:
                    chosen_url = item.url
                    break

            if chosen_url is None:
                for guess in candidate_article_urls(target):
                    if self.db.has_url(SOURCE_INSIGHTS, guess):
                        skipped = 1
                        status = "skipped"
                        message = f"URL already stored: {guess}"
                        chosen_url = guess
                        break
                    try:
                        # Probe without storing until success.
                        article = self.fetch_article(guess)
                        if article.article_date == target or TITLE_CA_RE.search(article.title):
                            chosen_url = guess
                            if dry_run:
                                status = "dry_run"
                                message = f"would fetch {guess}"
                            else:
                                result = self.db.upsert_article(article)
                                if result == "inserted":
                                    inserted = 1
                                else:
                                    skipped = 1
                                message = guess
                            break
                    except Exception:
                        continue

                if chosen_url is None and inserted == 0 and status == "ok":
                    status = "skipped"
                    message = (
                        f"no InsightsIAS daily CA post found for {target.isoformat()} "
                        "(weekend/holiday or URL pattern changed)"
                    )
                    skipped = 1
            else:
                if self.db.has_url(SOURCE_INSIGHTS, chosen_url):
                    skipped = 1
                    status = "skipped"
                    message = f"URL already stored: {chosen_url}"
                elif dry_run:
                    status = "dry_run"
                    message = f"would fetch {chosen_url}"
                else:
                    result = self.ingest_url(chosen_url, dry_run=False)
                    if result == "inserted":
                        inserted = 1
                    else:
                        skipped = 1
                    message = chosen_url

            return {
                "status": status,
                "inserted": inserted,
                "skipped": skipped,
                "message": message,
                "url": chosen_url,
            }
        except Exception as exc:  # noqa: BLE001 — surface to CLI / run log
            status = "error"
            message = str(exc)
            raise
        finally:
            self.db.finish_fetch_run(
                run_id,
                status=status,
                inserted=inserted,
                skipped=skipped,
                message=message,
            )

    def fetch_today(self, *, dry_run: bool = False) -> dict:
        return self.fetch_date(date.today(), dry_run=dry_run)