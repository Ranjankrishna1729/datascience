# Daily CA ingest

Fetches **InsightsIAS-style** daily UPSC current affairs into a local **SQLite** database (schema is plain SQL so Postgres is a later swap).

This is a polite, personal/educational ingest slice: identifying `User-Agent`, configurable request delay, skip-if-already-fetched by `(source, url)` and by date.

## Source URL assumptions

| Role | URL |
| ---- | --- |
| Category listing (discovery) | `https://www.insightsonindia.com/category/current-affairs-2/` |
| Typical daily post | `https://www.insightsonindia.com/YYYY/MM/DD/upsc-current-affairs-D-month-YYYY/` |

**robots.txt** (checked 2026-11): disallows `/wp-admin/`, `/demolive/`, and some query-string search/sort URLs. Category archives and posts are allowed. We still rate-limit and do not crawl aggressively.

Site slugs and markup can change. The fetcher prefers the category listing match for a date, then falls back to common slug guesses. If InsightsIAS changes URLs, update `DAILY_CA_INSIGHTS_CATEGORY_URL` and/or `daily_ca/fetchers/insights.py`.

Respect InsightsIAS terms of use. Prefer their official products for commercial use; this tool is for personal study pipelines.

## Setup

```bash
cd daily_ca
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # optional
```

## CLI

```bash
# Create DB + schema
python -m daily_ca init-db

# Fetch today's post (idempotent)
python -m daily_ca fetch-today

# Fetch a specific date
python -m daily_ca fetch --date 2026-11-11

# Resolve URL without writing rows / downloading article body
python -m daily_ca --dry-run fetch --date 2026-11-11
```

## Environment variables

| Variable | Default | Meaning |
| -------- | ------- | ------- |
| `DAILY_CA_DATABASE_URL` | `sqlite:///./data/daily_ca.sqlite3` | SQLite URL or path |
| `DAILY_CA_USER_AGENT` | educational bot UA | HTTP User-Agent |
| `DAILY_CA_REQUEST_DELAY_SECONDS` | `1.5` | Pause between HTTP calls |
| `DAILY_CA_REQUEST_TIMEOUT_SECONDS` | `30` | Per-request timeout |
| `DAILY_CA_INSIGHTS_CATEGORY_URL` | InsightsIAS CA category | Listing page |

Also accepts `DATABASE_URL` as an alias for the DB setting.

## Database

Default file: `daily_ca/data/daily_ca.sqlite3` (created on first run).

### `articles`

| Column | Notes |
| ------ | ----- |
| `source` | e.g. `insightsias` |
| `article_date` | `YYYY-MM-DD` |
| `title` | Post title |
| `url` | Canonical post URL |
| `body_html` | `entry-content` HTML |
| `body_text` | Plain text extraction |
| `fetched_at` | UTC ISO-8601 |

Uniques: `(source, url)` and `(source, article_date, title)`.

### `fetch_runs`

Lightweight run log (`status`, `inserted`, `skipped`, `message`).

**Postgres later:** reuse `daily_ca/schema.sql` (swap `INTEGER PRIMARY KEY AUTOINCREMENT` → `BIGSERIAL` / `GENERATED … AS IDENTITY` as needed) behind the same column set.

## Tests

```bash
cd daily_ca
pytest -q
```

Parser/DB tests use offline HTML fixtures under `tests/fixtures/` (no network).

## Schedule

### cron

```cron
# Every day at 07:30 local time
30 7 * * * cd /path/to/datascience/daily_ca && . .venv/bin/activate && python -m daily_ca fetch-today >> /var/log/daily_ca.log 2>&1
```

### GitHub Actions

See [`../.github/workflows/daily-ca.yml`](../.github/workflows/daily-ca.yml) (daily cron + `workflow_dispatch`). The workflow runs `fetch-today` and uploads the SQLite file as an artifact. For a durable DB, point `DAILY_CA_DATABASE_URL` at an external store or commit/sync the artifact elsewhere — Actions runners are ephemeral.

## Layout

```
daily_ca/
  daily_ca/           # package
    fetchers/         # InsightsIAS adapter
    schema.sql
    cli.py
  tests/
  requirements.txt
  .env.example

# repo root
.github/workflows/daily-ca.yml
```
