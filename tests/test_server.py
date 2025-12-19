from datetime import timezone
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from news_coverage.server import app


def make_client(tmp_path: Path) -> TestClient:
    os.environ["INGEST_DATA_DIR"] = str(tmp_path)
    return TestClient(app)


def sample_payload(**overrides):
    base = {
        "company": "A24",
        "quarter": "2025 Q1",
        "title": "Sample headline",
        "source": "Variety",
        "url": "https://example.com/story",
        "published_at": "2025-01-15",
        "facts": [
            {
                "fact_id": "fact-1",
                "category_path": "Content, Deals, Distribution -> TV -> Development",
                "section": "Content / Deals / Distribution",
                "subheading": "Development",
                "company": "A24",
                "quarter": "2025 Q1",
                "published_at": "2025-01-15",
                "content_line": "Sample line",
                "summary_bullets": ["Sample line"],
            }
        ],
    }
    base.update(overrides)
    return base


def test_health(tmp_path):
    client = make_client(tmp_path)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_cors_wildcard_disables_credentials():
    cors = next(
        m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"
    )
    assert cors.kwargs["allow_origins"] == ["*"]
    assert cors.kwargs["allow_credentials"] is False


def test_ingest_stores_article(tmp_path):
    client = make_client(tmp_path)
    payload = sample_payload()
    resp = client.post("/ingest/article", json=payload)
    assert resp.status_code == 201
    stored_path = Path(resp.json()["stored_path"])
    assert stored_path.exists()
    lines = stored_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    stored = json.loads(lines[0])
    assert stored["url"] == payload["url"]
    assert stored["facts"][0]["section"] == "Content / Deals / Distribution"
    assert "captured_at" in stored


def test_ingest_allows_duplicate_url(tmp_path):
    client = make_client(tmp_path)
    payload = sample_payload()
    first = client.post("/ingest/article", json=payload)
    assert first.status_code == 201
    second = client.post("/ingest/article", json=payload)
    assert second.status_code == 201
    stored_path = Path(first.json()["stored_path"])
    lines = stored_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_ingest_accepts_legacy_single_category_payload(tmp_path):
    client = make_client(tmp_path)
    payload = {
        "company": "A24",
        "quarter": "2025 Q1",
        "section": "Strategy & Miscellaneous News",
        "subheading": "General News & Strategy",
        "title": "Legacy headline",
        "source": "Variety",
        "url": "https://example.com/legacy",
        "published_at": "2025-01-15",
        "summary": "Legacy summary line",
    }
    resp = client.post("/ingest/article", json=payload)
    assert resp.status_code == 201
    stored_path = Path(resp.json()["stored_path"])
    stored = json.loads(stored_path.read_text(encoding="utf-8").splitlines()[0])
    assert stored["url"] == payload["url"]
    assert stored["facts"][0]["section"] == "Strategy & Miscellaneous News"
    assert stored["facts"][0]["content_line"] == "Legacy summary line"


class _StubIngest:
    def __init__(self, path: Path, duplicate_of=None):
        self.stored_path = path
        self.duplicate_of = duplicate_of


class _StubResult:
    def __init__(self, path: Path, duplicate_of=None):
        self.markdown = "Processed"
        self.ingest = _StubIngest(path, duplicate_of)


def _process_payload():
    return {
        "title": "Example",
        "source": "Feedly",
        "url": "https://example.com/article",
        "published_at": "2025-01-15",
        "content": "Full text",
    }


def test_process_article_runs_pipeline(monkeypatch, tmp_path):
    client = make_client(tmp_path)

    def fake_pipeline(article):
        return _StubResult(tmp_path / "A24" / "2025 Q1.jsonl")

    monkeypatch.setattr("news_coverage.server._run_article_pipeline", fake_pipeline)

    resp = client.post("/process/article", json=_process_payload())
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "processed"
    assert data["markdown"] == "Processed"
    assert Path(data["stored_path"]).name == "2025 Q1.jsonl"
    assert data["duplicate_of"] is None


def test_process_article_parses_rfc3339_z_published_at(monkeypatch, tmp_path):
    client = make_client(tmp_path)

    def fake_pipeline(article):
        assert article.published_at is not None
        assert article.published_at.year == 2025
        assert article.published_at.month == 12
        assert article.published_at.day == 1
        assert article.published_at.tzinfo == timezone.utc
        return _StubResult(tmp_path / "A24" / "2025 Q4.jsonl")

    monkeypatch.setattr("news_coverage.server._run_article_pipeline", fake_pipeline)

    payload = _process_payload()
    payload["published_at"] = "2025-12-01T00:00:00Z"
    resp = client.post("/process/article", json=payload)
    assert resp.status_code == 201


def test_process_article_rejects_invalid_published_at(monkeypatch, tmp_path):
    client = make_client(tmp_path)

    def fake_pipeline(article):
        raise AssertionError("pipeline should not be called when payload is invalid")

    monkeypatch.setattr("news_coverage.server._run_article_pipeline", fake_pipeline)

    payload = _process_payload()
    payload["published_at"] = "definitely-not-a-timestamp"
    resp = client.post("/process/article", json=payload)
    assert resp.status_code == 400
    assert "published_at" in resp.json()["detail"]
