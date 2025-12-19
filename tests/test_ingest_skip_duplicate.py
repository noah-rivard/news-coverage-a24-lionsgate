import json
from pathlib import Path

from news_coverage.models import Article
from news_coverage.workflow import (
    ClassificationResult,
    SummaryResult,
    ingest_article,
)


def test_ingest_article_skips_duplicates(tmp_path, monkeypatch):
    monkeypatch.setenv("INGEST_DATA_DIR", str(tmp_path))

    article = Article(
        title="Sample",
        source="Demo",
        url="https://example.com/story",
        content="A short demo article.",
    )
    classification = ClassificationResult(
        category="Strategy & Miscellaneous News -> Strategy",
        section="Strategy & Miscellaneous News",
        subheading="Strategy",
        confidence=0.5,
        company="A24",
        quarter="2025 Q4",
    )
    summary = SummaryResult(bullets=["Point one"], facts=[])

    # First write should succeed and create the file.
    first = ingest_article(article, classification, summary)
    assert first.duplicate_of is None
    path = Path(first.stored_path)
    assert path.exists()
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1

    # Second write should skip when the URL matches.
    second = ingest_article(article, classification, summary)
    assert second.duplicate_of == str(article.url)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1


def test_ingest_article_falls_back_when_summary_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("INGEST_DATA_DIR", str(tmp_path))

    article = Article(
        title="Headline-only story",
        source="Demo",
        url="https://example.com/empty-summary",
        content="Body text that the summarizer failed to handle.",
    )
    classification = ClassificationResult(
        category="Strategy & Miscellaneous News -> Strategy",
        section="Strategy & Miscellaneous News",
        subheading="Strategy",
        confidence=0.5,
        company="A24",
        quarter="2025 Q4",
    )
    summary = SummaryResult(bullets=[], facts=[])

    result = ingest_article(article, classification, summary)
    stored = Path(result.stored_path).read_text(encoding="utf-8").splitlines()
    assert len(stored) == 1
    payload = json.loads(stored[0])
    assert payload["facts"]
    assert payload["facts"][0]["content_line"].strip()
