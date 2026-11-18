from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Iterable
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

from .http_client import PoliteSession

_PRID_RE = re.compile(r"PRID=(\d+)", re.I)


@dataclass(frozen=True)
class ReleaseLink:
    title: str
    url: str
    prid: str
    ministry: str
    listing_date: str  # YYYY-MM-DD of the listing filter used


def _selected_option_value(select) -> str | None:
    if select is None:
        return None
    selected = select.find("option", selected=True)
    if selected is None:
        # Some ASP.NET markup marks selected via selected="selected" on first match only;
        # fall back to option with matching value attribute if present.
        for opt in select.find_all("option"):
            if opt.has_attr("selected"):
                selected = opt
                break
    if selected is None:
        return None
    return (selected.get("value") or selected.get_text(strip=True) or "").strip() or None


def listing_date_from_html(html: str) -> date | None:
    """Read selected day/month/year dropdowns on allRel.aspx."""
    soup = BeautifulSoup(html, "lxml")
    day = _selected_option_value(soup.find(id="ContentPlaceHolder1_ddlday"))
    month = _selected_option_value(soup.find(id="ContentPlaceHolder1_ddlMonth"))
    year = _selected_option_value(soup.find(id="ContentPlaceHolder1_ddlYear"))
    if not (day and month and year) or day == "0":
        return None
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


def _form_fields(soup: BeautifulSoup) -> dict[str, str]:
    data: dict[str, str] = {}
    form = soup.find("form", id="form1") or soup.find("form")
    if form is None:
        return data
    for inp in form.find_all("input"):
        name = inp.get("name")
        if not name:
            continue
        typ = (inp.get("type") or "text").lower()
        if typ in {"submit", "button", "image", "file"}:
            continue
        data[name] = inp.get("value") or ""
    for sel in form.find_all("select"):
        name = sel.get("name")
        if not name:
            continue
        val = _selected_option_value(sel)
        data[name] = val or ""
    return data


def fetch_listing_html(
    session: PoliteSession,
    *,
    listing_url: str,
    target_date: date | None = None,
) -> str:
    """
    GET allRel listing. If target_date is set and differs from the page default,
    POST an ASP.NET postback changing day/month/year dropdowns.
    """
    html = session.get_text(listing_url)
    if target_date is None:
        return html

    current = listing_date_from_html(html)
    if current == target_date:
        return html

    soup = BeautifulSoup(html, "lxml")
    data = _form_fields(soup)
    if not data:
        raise RuntimeError("PIB listing form fields missing; cannot postback for date")

    data["ctl00$ContentPlaceHolder1$ddlday"] = str(target_date.day)
    data["ctl00$ContentPlaceHolder1$ddlMonth"] = str(target_date.month)
    data["ctl00$ContentPlaceHolder1$ddlYear"] = str(target_date.year)
    data["__EVENTTARGET"] = "ctl00$ContentPlaceHolder1$ddlday"
    data["__EVENTARGUMENT"] = ""

    html2 = session.post_form(listing_url, data, referer=listing_url)
    got = listing_date_from_html(html2)
    if got != target_date:
        raise RuntimeError(
            f"PIB listing date postback failed: wanted {target_date}, got {got}"
        )
    return html2


def extract_release_links(
    html: str,
    *,
    base_url: str,
    listing_date: str,
) -> list[ReleaseLink]:
    """
    Parse ministry-grouped release links from allRel.aspx HTML.

    Structure (simplified):
      ul > li > h3.ministry + ul.num > li > a[href*=PressReleaseDetail]
    """
    soup = BeautifulSoup(html, "lxml")
    content = soup.select_one(".content-area") or soup
    out: list[ReleaseLink] = []
    seen: set[str] = set()

    for ministry_h3 in content.select("h3.font104"):
        ministry = ministry_h3.get_text(" ", strip=True)
        # Sibling / nested ul.num with release anchors
        ul = ministry_h3.find_next("ul", class_="num")
        if ul is None:
            continue
        # Stop if this ul belongs to a later ministry heading
        for a in ul.select("a[href*='PressReleaseDetail']"):
            href = (a.get("href") or "").strip()
            if not href:
                continue
            abs_url = urljoin(base_url.rstrip("/") + "/", href)
            prid = _prid_from_url(abs_url)
            if not prid or prid in seen:
                continue
            seen.add(prid)
            title = (a.get("title") or a.get_text(" ", strip=True) or "").strip()
            out.append(
                ReleaseLink(
                    title=title,
                    url=abs_url.split("#")[0],
                    prid=prid,
                    ministry=ministry,
                    listing_date=listing_date,
                )
            )

    # Fallback: any PressReleaseDetail links if ministry grouping markup changes
    if not out:
        for a in content.select("a[href*='PressReleaseDetail']"):
            href = (a.get("href") or "").strip()
            abs_url = urljoin(base_url.rstrip("/") + "/", href)
            prid = _prid_from_url(abs_url)
            if not prid or prid in seen:
                continue
            seen.add(prid)
            title = (a.get("title") or a.get_text(" ", strip=True) or "").strip()
            out.append(
                ReleaseLink(
                    title=title,
                    url=abs_url.split("#")[0],
                    prid=prid,
                    ministry="",
                    listing_date=listing_date,
                )
            )
    return out


def _prid_from_url(url: str) -> str | None:
    m = _PRID_RE.search(url)
    if m:
        return m.group(1)
    qs = parse_qs(urlparse(url).query)
    vals = qs.get("PRID") or qs.get("prid")
    return vals[0] if vals else None


def iter_release_links(links: Iterable[ReleaseLink], *, limit: int | None) -> list[ReleaseLink]:
    items = list(links)
    if limit is not None and limit >= 0:
        return items[:limit]
    return items
