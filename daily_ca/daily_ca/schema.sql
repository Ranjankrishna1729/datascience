-- Portable-ish schema (SQLite default; swap engine later for Postgres).
-- Unique identity: (source, url). Optional helper unique on (source, article_date, title).

CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    article_date TEXT NOT NULL,          -- ISO date YYYY-MM-DD
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    body_html TEXT,
    body_text TEXT,
    fetched_at TEXT NOT NULL,            -- ISO-8601 UTC timestamp
    UNIQUE (source, url)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_articles_source_date_title
    ON articles (source, article_date, title);

CREATE INDEX IF NOT EXISTS ix_articles_source_date
    ON articles (source, article_date);

CREATE TABLE IF NOT EXISTS fetch_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    target_date TEXT,                    -- NULL means "today" / listing scrape
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,                -- ok | skipped | error | dry_run
    inserted INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER NOT NULL DEFAULT 0,
    message TEXT
);