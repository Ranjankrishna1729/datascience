from __future__ import annotations

import argparse
import sys
from datetime import date, datetime

from .config import load_settings
from .db import open_db
from .fetchers import InsightsFetcher


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"expected YYYY-MM-DD, got {value!r}"
        ) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="daily-ca",
        description="Fetch daily UPSC current affairs into a local database.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve target URL(s) but do not download article body or write rows.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("fetch-today", help="Fetch InsightsIAS current affairs for today.")

    fetch = sub.add_parser("fetch", help="Fetch InsightsIAS current affairs for a date.")
    fetch.add_argument(
        "--date",
        required=True,
        type=_parse_date,
        help="Calendar date YYYY-MM-DD",
    )

    sub.add_parser("init-db", help="Create SQLite file and apply schema.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = load_settings()
    db = open_db(settings)

    if args.command == "init-db":
        print(f"Database ready: {settings.sqlite_path}")
        return 0

    fetcher = InsightsFetcher(settings, db)
    dry_run = bool(args.dry_run)

    if args.command == "fetch-today":
        result = fetcher.fetch_today(dry_run=dry_run)
    elif args.command == "fetch":
        result = fetcher.fetch_date(args.date, dry_run=dry_run)
    else:
        parser.error(f"unknown command {args.command}")
        return 2

    print(
        f"status={result['status']} inserted={result['inserted']} "
        f"skipped={result['skipped']} message={result.get('message')}"
    )
    return 0 if result["status"] != "error" else 1


if __name__ == "__main__":
    sys.exit(main())