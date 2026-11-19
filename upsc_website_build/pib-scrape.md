# PIB daily releases → chunk → vector DB

Code package: [`../pib_scrape/`](../pib_scrape/) (repo root). Full package README: [`../pib_scrape/README.md`](../pib_scrape/README.md).

Source listing: `https://www.pib.gov.in/allRel.aspx?reg=3&lang=1`

## What it does

1. Fetches the PIB **All Releases** listing for a day (today by default; other days via ASP.NET date postback)
2. Collects ministry-grouped `PressReleaseDetail.aspx?PRID=…` links
3. Loads each release body from `PressReleasePage.aspx` (`#pibReleaseBody`) — polite delay + retries
4. Chunks paragraph/sentence-aware text
5. **Upserts** into local Chroma (`pib_releases`), idempotent by `pib-{PRID}-{n}` and skip-if-already-stored

## Quick start

```bash
cd pib_scrape
pip install -r requirements.txt
python -m pib_scrape --dry-run fetch-today
python -m pib_scrape --limit 5 fetch-today
python -m pib_scrape fetch --date 2026-11-17
```

| Setting | Default |
| ------- | ------- |
| Persist dir | `pib_scrape/data/chroma` |
| Collection | `pib_releases` |
| Delay | 1.5s between HTTP calls |

Point `PIB_SCRAPE_PERSIST_DIR` at an existing Chroma folder (same pattern as Constitution ingest) to append this collection beside others.

## Compliance notes

- Akamai on pib.gov.in **403s** non-browser User-Agents; default UA is desktop Chrome, with `X-Research-Purpose` documenting educational use
- Rate-limited; no aggressive crawling; skip stored PRIDs unless `--force`
- Personal/educational assumption for public press releases — re-check GoI/PIB terms before redistribution or commercial use
