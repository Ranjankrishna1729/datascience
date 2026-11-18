from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime

from .config import load_settings
from .pipeline import run_fetch


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"expected YYYY-MM-DD, got {value!r}"
        ) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pib-scrape",
        description=(
            "Scrape PIB daily press releases, chunk bodies, upsert into local Chroma."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve listing links only; do not fetch bodies or write to Chroma.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of releases to process (after listing parse).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch and upsert even if PRID already has chunks in Chroma.",
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Do not skip PRIDs already stored (same as --force for skip logic).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON summary.",
    )

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("fetch-today", help="Fetch today's PIB releases (listing default date).")

    fetch = sub.add_parser("fetch", help="Fetch PIB releases for a calendar date.")
    fetch.add_argument(
        "--date",
        required=True,
        type=_parse_date,
        help="Calendar date YYYY-MM-DD (ASP.NET postback on allRel.aspx).",
    )

    sub.add_parser(
        "info",
        help="Show configured Chroma persist path and collection name.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = load_settings()

    if args.command == "info":
        payload = {
            "persist_dir": str(settings.persist_dir),
            "collection": settings.collection_name,
            "listing_url": settings.listing_url,
            "request_delay_seconds": settings.request_delay_seconds,
        }
        print(json.dumps(payload, indent=2) if args.json else (
            f"persist_dir={settings.persist_dir}\n"
            f"collection={settings.collection_name}\n"
            f"listing_url={settings.listing_url}"
        ))
        return 0

    target: date | None
    if args.command == "fetch-today":
        target = None  # use site default (today)
    elif args.command == "fetch":
        target = args.date
    else:
        parser.error(f"unknown command {args.command}")
        return 2

    result = run_fetch(
        settings,
        target_date=target,
        limit=args.limit,
        dry_run=bool(args.dry_run),
        skip_existing=not (args.force or args.no_skip_existing),
        force=bool(args.force or args.no_skip_existing),
    )

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(
            f"status={result['status']} listing_date={result.get('listing_date')} "
            f"discovered={result.get('discovered')} fetched={result.get('fetched')} "
            f"skipped={result.get('skipped')} chunks={result.get('chunks')} "
            f"upserted={result.get('upserted')}"
        )
        print(f"message={result.get('message')}")
        if result.get("errors"):
            print(f"errors={len(result['errors'])} (first: {result['errors'][0]})")
        print(f"persist_dir={result.get('persist_dir')} collection={result.get('collection')}")

    return 0 if result.get("status") != "error" else 1


if __name__ == "__main__":
    sys.exit(main())
