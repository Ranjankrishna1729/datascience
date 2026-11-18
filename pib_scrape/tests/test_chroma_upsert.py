from __future__ import annotations

from pib_scrape.article import Article
from pib_scrape.chunking import chunk_article
from pib_scrape.chroma_store import existing_prids, upsert_chunks


def test_upsert_idempotent(tmp_path):
    article = Article(
        prid="9990001",
        title="Sample PIB Release",
        url="https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=9990001",
        page_url="https://www.pib.gov.in/PressReleasePage.aspx?PRID=9990001",
        ministry="Ministry of Test",
        posted_on="2026-11-18",
        posted_raw="Posted On: 18 NOV 2026 1:00PM by PIB Delhi",
        body_text=(
            "First paragraph about a policy announcement.\n\n"
            "Second paragraph with more detail for retrieval."
        ),
        body_html="<p>First</p><p>Second</p>",
    )
    chunks = chunk_article(article, listing_date="2026-11-18", max_chars=1800)
    persist = tmp_path / "chroma"
    stats1 = upsert_chunks(chunks, persist_dir=persist, collection_name="pib_releases")
    assert stats1["upserted"] == len(chunks)
    assert stats1["count_after"] >= len(chunks)

    stats2 = upsert_chunks(chunks, persist_dir=persist, collection_name="pib_releases")
    assert stats2["upserted"] == len(chunks)
    # Idempotent ids → count should not grow
    assert stats2["count_after"] == stats1["count_after"]

    assert existing_prids(persist, "pib_releases", ["9990001", "nope"]) == {"9990001"}
