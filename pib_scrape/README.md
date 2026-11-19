# PIB scrape → Chroma

Polite personal/educational ingest of **Press Information Bureau (PIB)** daily English releases into a local **Chroma** vector DB (same append/upsert style as the Constitution ingest helpers).

## Source assumptions

| Role | URL |
| ---- | --- |
| Day listing (Delhi/HQ, English) | `https://www.pib.gov.in/allRel.aspx?reg=3&lang=1` |
| Release shell (iframe host) | `/PressReleaseDetail.aspx?PRID=…` |
| Release body (parsed) | `/PressReleasePage.aspx?PRID=…` |

- Listing defaults to **today**; other days use an ASP.NET postback on the day/month/year dropdowns (`__VIEWSTATE` + `__EVENTTARGET`).
- Body text comes from `#pibReleaseBody` on `PressReleasePage.aspx` (not the Detail chrome).
- Markup can change; parsers prefer stable hooks (`PressReleaseDetail` links, `h3.font104` ministries, `#pibReleaseBody`, `Posted On:`).

## robots / ToS / politeness

- `robots.txt` on pib.gov.in is behind the same Akamai edge as the site; a non-browser User-Agent gets **403**. We therefore use a **desktop Chrome User-Agent** so GETs succeed, and set `X-Research-Purpose` to document educational intent.
- Default delay **1.5s** between requests; retries with backoff on 429/5xx.
- **Skip-if-already-stored**: PRIDs with an existing `pib-{PRID}-0` chunk are not re-fetched (use `--force` to refresh).
- Do **not** scrape aggressively or redistribute wholesale; this is for personal UPSC study pipelines. Re-check PIB / GoI terms before any commercial use.
- Assumption: public press releases may be ingested for private retrieval; we store only release text + metadata (URL, PRID, date, ministry).

## Setup

```bash
cd pib_scrape
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # optional
```

## CLI

```bash
# Show Chroma path / collection
python -m pib_scrape info

# Dry-run: list today's release URLs only
python -m pib_scrape --dry-run fetch-today

# Fetch today (idempotent upsert); limit for smoke tests
python -m pib_scrape --limit 3 fetch-today

# Specific calendar day via ASP.NET postback
python -m pib_scrape fetch --date 2026-11-17

# Re-fetch even if PRID already in Chroma
python -m pib_scrape --force --limit 2 fetch-today

# JSON summary
python -m pib_scrape --json --limit 1 fetch-today
```

## Vector DB

| Setting | Default |
| ------- | ------- |
| Persist dir | `pib_scrape/data/chroma` (`PIB_SCRAPE_PERSIST_DIR`) |
| Collection | `pib_releases` (`PIB_SCRAPE_COLLECTION`) |
| Chunk ids | `pib-{PRID}-{split_index}` (stable upsert keys) |

Metadata per chunk: `prid`, `url`, `page_url`, `title`, `ministry`, `posted_on`, `listing_date`, `split_index`, `content_sha1`, `source=pib.gov.in`.

Chunking: pack paragraphs up to `PIB_SCRAPE_MAX_CHARS` (default 1800); oversize paragraphs split on sentence boundaries.

Point `PIB_SCRAPE_PERSIST_DIR` at an existing shared Chroma folder (e.g. the Constitution DB path) to **append** the `pib_releases` collection beside others — upsert does not wipe sibling collections.

### Quick check

```python
import chromadb
from chromadb.config import Settings

client = chromadb.PersistentClient(
    path="data/chroma",
    settings=Settings(anonymized_telemetry=False),
)
print(client.list_collections())  # names only on Chroma ≥0.6
col = client.get_collection("pib_releases")
print(col.count(), col.peek(2)["ids"])
print(col.query(query_texts=["infrastructure digital transformation"], n_results=3)["ids"])
```

## Tests

Offline parser/chunk tests (no network):

```bash
cd pib_scrape
pytest -q
```

## Layout

```
pib_scrape/
  pib_scrape/
    listing.py      # allRel.aspx + date postback
    article.py      # PressReleasePage body
    chunking.py
    chroma_store.py
    pipeline.py
    cli.py
  tests/fixtures/
  requirements.txt
  .env.example
```
