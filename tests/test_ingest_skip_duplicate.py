from pathlib import Path

from news_coverage.models import Article
from news_coverage.workflow import (
    ClassificationResult,
    SummaryResult,
    ingest_article,
)


def test_ingest_article_can_skip_duplicates(tmp_path, monkeypatch):
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
    summary = SummaryResult(bullets=["Point one"])

    # First write should succeed and create the file.
    first = ingest_article(article, classification, summary)
    assert first.duplicate_of is None
    path = Path(first.stored_path)
    assert path.exists()
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1

    # Second write with skip_duplicate=True should append instead of flagging a duplicate.
    second = ingest_article(article, classification, summary, skip_duplicate=True)
    assert second.duplicate_of is None
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
