from __future__ import annotations

from datetime import date
from pathlib import Path

from pib_scrape.listing import extract_release_links, listing_date_from_html

FIXTURES = Path(__file__).parent / "fixtures"


def test_listing_date_and_links():
    html = (FIXTURES / "listing_sample.html").read_text(encoding="utf-8")
    d = listing_date_from_html(html)
    assert d == date(2026, 11, 18)
    links = extract_release_links(
        html,
        base_url="https://www.pib.gov.in",
        listing_date=d.isoformat(),
    )
    assert len(links) >= 3
    assert all(lnk.prid.isdigit() for lnk in links)
    assert all("PressReleaseDetail.aspx?PRID=" in lnk.url for lnk in links)
    assert links[0].ministry  # first group has a ministry/secretariat label
    prids = [lnk.prid for lnk in links]
    assert len(prids) == len(set(prids))
