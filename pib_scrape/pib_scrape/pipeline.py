from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from .article import fetch_article
from .chunking import TextChunk, chunk_article
from .chroma_store import existing_prids, upsert_chunks
from .config import Settings
from .http_client import PoliteSession
from .listing import (
    extract_release_links,
    fetch_listing_html,
    iter_release_links,
    listing_date_from_html,
)


def run_fetch(
    settings: Settings,
    *,
    target_date: date | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    skip_existing: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    """
    End-to-end: listing → articles → chunks → Chroma upsert.

    skip_existing: if True (default), do not re-fetch PRIDs already in the DB
    (unless force=True).
    """
    started = datetime.now(timezone.utc).isoformat()
    session = PoliteSession(settings)

    html = fetch_listing_html(
        session,
        listing_url=settings.listing_url,
        target_date=target_date,
    )
    listing_dt = listing_date_from_html(html) or target_date or date.today()
    listing_date = listing_dt.isoformat()

    links = extract_release_links(
        html,
        base_url=settings.base_url,
        listing_date=listing_date,
    )
    links = iter_release_links(links, limit=limit)

    already: set[str] = set()
    if skip_existing and not force and not dry_run:
        already = existing_prids(
            settings.persist_dir,
            settings.collection_name,
            (lnk.prid for lnk in links),
        )

    to_fetch = [lnk for lnk in links if force or lnk.prid not in already]
    skipped = len(links) - len(to_fetch)

    result: dict[str, Any] = {
        "status": "ok",
        "started_at": started,
        "listing_date": listing_date,
        "discovered": len(links),
        "to_fetch": len(to_fetch),
        "skipped": skipped,
        "fetched": 0,
        "chunks": 0,
        "upserted": 0,
        "errors": [],
        "sample_urls": [lnk.url for lnk in links[:5]],
        "persist_dir": str(settings.persist_dir),
        "collection": settings.collection_name,
        "dry_run": dry_run,
    }

    if dry_run:
        result["message"] = (
            f"dry-run: would fetch {len(to_fetch)} of {len(links)} releases "
            f"for {listing_date} (skip_existing={skip_existing and not force})"
        )
        return result

    all_chunks: list[TextChunk] = []
    for lnk in to_fetch:
        try:
            article = fetch_article(
                session,
                prid=lnk.prid,
                detail_or_page_url=lnk.url,
                ministry_hint=lnk.ministry,
                title_hint=lnk.title,
            )
            chunks = chunk_article(
                article,
                listing_date=listing_date,
                max_chars=settings.max_chars,
            )
            all_chunks.extend(chunks)
            result["fetched"] += 1
        except Exception as exc:  # noqa: BLE001 — collect per-URL failures
            result["errors"].append({"prid": lnk.prid, "url": lnk.url, "error": str(exc)})

    stats = upsert_chunks(
        all_chunks,
        persist_dir=settings.persist_dir,
        collection_name=settings.collection_name,
    )
    result["chunks"] = len(all_chunks)
    result["upserted"] = stats.get("upserted", 0)
    result["count_before"] = stats.get("count_before")
    result["count_after"] = stats.get("count_after")
    if result["errors"] and result["fetched"] == 0:
        result["status"] = "error"
        result["message"] = f"all fetches failed ({len(result['errors'])})"
    elif result["errors"]:
        result["status"] = "partial"
        result["message"] = (
            f"fetched {result['fetched']}, errors {len(result['errors'])}, "
            f"upserted {result['upserted']} chunks"
        )
    else:
        result["message"] = (
            f"fetched {result['fetched']}, skipped {skipped}, "
            f"upserted {result['upserted']} chunks → {settings.collection_name}"
        )
    return result
