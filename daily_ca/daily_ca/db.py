from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from .config import SCHEMA_PATH, Settings


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Article:
    source: str
    article_date: date
    title: str
    url: str
    body_html: Optional[str]
    body_text: Optional[str]
    fetched_at: Optional[str] = None


class Database:
    """Thin SQLite wrapper. Schema is plain SQL so Postgres swap is straightforward."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self) -> None:
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.executescript(sql)
            conn.commit()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def has_url(self, source: str, url: str) -> bool:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM articles WHERE source = ? AND url = ? LIMIT 1",
                (source, url),
            ).fetchone()
            return row is not None

    def has_date(self, source: str, article_date: date) -> bool:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM articles WHERE source = ? AND article_date = ? LIMIT 1",
                (source, article_date.isoformat()),
            ).fetchone()
            return row is not None

    def upsert_article(self, article: Article) -> str:
        """Insert article. Returns 'inserted' or 'skipped' (already present)."""
        fetched_at = article.fetched_at or utc_now_iso()
        with self.connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO articles (
                        source, article_date, title, url, body_html, body_text, fetched_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        article.source,
                        article.article_date.isoformat(),
                        article.title,
                        article.url,
                        article.body_html,
                        article.body_text,
                        fetched_at,
                    ),
                )
                return "inserted"
            except sqlite3.IntegrityError:
                return "skipped"

    def start_fetch_run(
        self, source: str, target_date: Optional[date], status: str = "running"
    ) -> int:
        with self.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO fetch_runs (source, target_date, started_at, status)
                VALUES (?, ?, ?, ?)
                """,
                (
                    source,
                    target_date.isoformat() if target_date else None,
                    utc_now_iso(),
                    status,
                ),
            )
            return int(cur.lastrowid)

    def finish_fetch_run(
        self,
        run_id: int,
        *,
        status: str,
        inserted: int = 0,
        skipped: int = 0,
        message: Optional[str] = None,
    ) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE fetch_runs
                SET finished_at = ?, status = ?, inserted = ?, skipped = ?, message = ?
                WHERE id = ?
                """,
                (utc_now_iso(), status, inserted, skipped, message, run_id),
            )


def open_db(settings: Settings) -> Database:
    return Database(settings.sqlite_path)