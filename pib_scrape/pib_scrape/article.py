from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString, Tag

from .http_client import PoliteSession

_POSTED_ON_RE = re.compile(
    r"Posted\s+On\s*:\s*"
    r"(?P<day>\d{1,2})\s+"
    r"(?P<mon>[A-Za-z]{3,9})\s+"
    r"(?P<year>\d{4})"
    r"(?:\s+(?P<time>\d{1,2}:\d{2}\s*[AP]M))?"
    r"(?:\s+by\s+(?P<source>.+))?",
    re.I,
)
_RELEASE_ID_RE = re.compile(r"\(Release\s+ID:\s*(\d+)\)", re.I)
_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


@dataclass(frozen=True)
class Article:
    prid: str
    title: str
    url: str  # canonical detail URL
    page_url: str  # PressReleasePage URL actually parsed
    ministry: str
    posted_on: str  # ISO date YYYY-MM-DD when parseable, else raw
    posted_raw: str
    body_text: str
    body_html: str


def detail_url(base_url: str, prid: str) -> str:
    return f"{base_url.rstrip('/')}/PressReleaseDetail.aspx?PRID={prid}"


def page_url(base_url: str, prid: str) -> str:
    return f"{base_url.rstrip('/')}/PressReleasePage.aspx?PRID={prid}"


def fetch_article(
    session: PoliteSession,
    *,
    prid: str,
    detail_or_page_url: str,
    ministry_hint: str = "",
    title_hint: str = "",
) -> Article:
    """
    Prefer PressReleasePage.aspx (iframe body). If given a Detail URL, follow the
    iframe src or fall back to constructing PressReleasePage?PRID=.
    """
    abs_url = session.absolute(detail_or_page_url)
    html = session.get_text(abs_url)
    soup = BeautifulSoup(html, "lxml")

    iframe = soup.find("iframe", id="ContentPlaceHolder1_iframepressrealese")
    if iframe and iframe.get("src"):
        page = urljoin(abs_url, iframe["src"])
        html = session.get_text(page, referer=abs_url)
        page_abs = session.absolute(page)
    elif "PressReleasePage.aspx" in abs_url:
        page_abs = abs_url
    else:
        # Detail page without iframe — try constructed page URL
        page_abs = page_url(session.settings.base_url, prid)
        html = session.get_text(page_abs, referer=abs_url)

    return parse_press_release_page(
        html,
        prid=prid,
        detail_url=detail_url(session.settings.base_url, prid),
        page_url=page_abs,
        ministry_hint=ministry_hint,
        title_hint=title_hint,
    )


def parse_press_release_page(
    html: str,
    *,
    prid: str,
    detail_url: str,
    page_url: str,
    ministry_hint: str = "",
    title_hint: str = "",
) -> Article:
    soup = BeautifulSoup(html, "lxml")

    title = _og(soup, "og:title") or _h1(soup) or title_hint
    title = re.sub(r"\s+", " ", title).strip()

    ministry = ministry_hint
    if not ministry:
        ministry = _guess_ministry(soup)

    posted_raw, posted_iso = _parse_posted_on(soup)
    body_el = soup.find(id="pibReleaseBody") or soup.find(id="PdfDiv")
    if body_el is None:
        # Last resort: largest text block under main content class
        body_el = soup.select_one(".innner-page-main-about-us-content-right-part")

    body_html = ""
    body_text = ""
    if body_el is not None:
        # Work on a copy so we can strip scripts/styles/images noise for text
        clone = BeautifulSoup(str(body_el), "lxml")
        root = clone.find(id=body_el.get("id")) or clone.body or clone
        for bad in root.find_all(["script", "style", "noscript"]):
            bad.decompose()
        body_html = root.decode_contents() if hasattr(root, "decode_contents") else str(root)
        body_text = _html_to_text(root)

    # Prefer Release ID from page if present
    rid_m = _RELEASE_ID_RE.search(soup.get_text(" ", strip=True))
    if rid_m:
        prid = rid_m.group(1)

    if not body_text.strip():
        raise ValueError(f"empty PIB body for PRID={prid}")

    return Article(
        prid=prid,
        title=title,
        url=detail_url,
        page_url=page_url,
        ministry=ministry,
        posted_on=posted_iso or "",
        posted_raw=posted_raw,
        body_text=body_text.strip(),
        body_html=body_html,
    )


def _og(soup: BeautifulSoup, prop: str) -> str:
    tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
    return (tag.get("content") or "").strip() if tag else ""


def _h1(soup: BeautifulSoup) -> str:
    h = soup.find("h1")
    return h.get_text(" ", strip=True) if h else ""


def _guess_ministry(soup: BeautifulSoup) -> str:
    # Often the ministry/secretariat label sits just above the H1.
    h1 = soup.find("h1")
    if h1 is None:
        return ""
    for sib in h1.find_all_previous(["div", "span", "p", "h2", "h3", "strong"], limit=12):
        text = sib.get_text(" ", strip=True)
        if not text or len(text) > 120:
            continue
        if re.search(r"Ministry|Secretariat|Office|Commission|Department|AYUSH", text, re.I):
            return text
    return ""


def _parse_posted_on(soup: BeautifulSoup) -> tuple[str, str]:
    text = soup.get_text("\n", strip=True)
    m = _POSTED_ON_RE.search(text)
    if not m:
        return "", ""
    raw = m.group(0).strip()
    mon = _MONTHS.get(m.group("mon").lower())
    if not mon:
        return raw, ""
    try:
        d = datetime(int(m.group("year")), mon, int(m.group("day"))).date()
        return raw, d.isoformat()
    except ValueError:
        return raw, ""


def _html_to_text(root: Tag) -> str:
    """Paragraph-aware plain text; keeps blank lines between blocks."""
    blocks: list[str] = []

    def flush_inline(parts: list[str]) -> None:
        text = re.sub(r"[ \t]+", " ", "".join(parts)).strip()
        if text:
            blocks.append(text)

    # Prefer explicit paragraphs
    paragraphs = root.find_all("p")
    if paragraphs:
        for p in paragraphs:
            # skip empty / image-only paragraphs
            t = p.get_text(" ", strip=True)
            t = re.sub(r"\s+", " ", t).strip()
            if t:
                blocks.append(t)
        return "\n\n".join(blocks)

    # Fallback: walk children
    buf: list[str] = []
    for child in root.children:
        if isinstance(child, NavigableString):
            buf.append(str(child))
        elif isinstance(child, Tag):
            if child.name in {"br"}:
                buf.append("\n")
            elif child.name in {"p", "div", "li", "h1", "h2", "h3", "h4"}:
                flush_inline(buf)
                buf = []
                t = child.get_text(" ", strip=True)
                if t:
                    blocks.append(re.sub(r"\s+", " ", t))
            else:
                buf.append(child.get_text(" ", strip=True))
    flush_inline(buf)
    return "\n\n".join(blocks)
