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
        "section": "Highlights",
        "title": "Sample headline",
        "source": "Variety",
        "url": "https://example.com/story",
        "published_at": "2025-01-15",
    }
    base.update(overrides)
    return base


def test_health(tmp_path):
    client = make_client(tmp_path)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


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
    assert stored["section"] == "Highlights"
    assert "captured_at" in stored


def test_ingest_rejects_duplicate_url(tmp_path):
    client = make_client(tmp_path)
    payload = sample_payload()
    first = client.post("/ingest/article", json=payload)
    assert first.status_code == 201
    second = client.post("/ingest/article", json=payload)
    assert second.status_code == 409
    body = second.json()["detail"]
    assert "duplicate_of" in body
