from __future__ import annotations

from datetime import date

from daily_ca.db import Article, Database


def test_upsert_idempotent(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    article = Article(
        source="insightsias",
        article_date=date(2026, 11, 11),
        title="UPSC CURRENT AFFAIRS – 11 NOVEMBER 2026",
        url="https://www.insightsonindia.com/2026/11/11/upsc-current-affairs-11-november-2026/",
        body_html="<p>hello</p>",
        body_text="hello",
    )
    assert db.upsert_article(article) == "inserted"
    assert db.upsert_article(article) == "skipped"
    assert db.has_url(article.source, article.url)
    assert db.has_date(article.source, article.article_date)


def test_fetch_run_roundtrip(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    run_id = db.start_fetch_run("insightsias", date(2026, 11, 11))
    db.finish_fetch_run(run_id, status="ok", inserted=1, skipped=0, message="done")
    with db.connection() as conn:
        row = conn.execute("SELECT status, inserted FROM fetch_runs WHERE id = ?", (run_id,)).fetchone()
    assert row["status"] == "ok"
    assert row["inserted"] == 1