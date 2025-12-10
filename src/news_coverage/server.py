"""FastAPI ingest service wired to the coverage schema validator."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .schema import load_schema, validate_article_payload


app = FastAPI(title="News Coverage Ingest")


def _add_cors(app: FastAPI) -> None:
    """Allow browser extensions to call the API during local development."""
    allow_all = os.getenv("CORS_ALLOW_ALL", "true").lower() == "true"
    origins_env = os.getenv("CORS_ALLOW_ORIGINS", "")
    origins = [o.strip() for o in origins_env.split(",") if o.strip()]
    if allow_all or not origins:
        origins = ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


_add_cors(app)


def storage_root() -> Path:
    """Base directory for ingested articles (override via INGEST_DATA_DIR)."""
    env_path = os.getenv("INGEST_DATA_DIR")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "data" / "ingest"


def _jsonl_path(company: str, quarter: str) -> Path:
    root = storage_root()
    return root / company / f"{quarter}.jsonl"


def _is_duplicate(path: Path, url: str) -> str | None:
    """Return stored id if the URL already exists in the JSONL file."""
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("url") == url:
            return record.get("id") or record.get("url")
    return None


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest/article", status_code=status.HTTP_201_CREATED)
def ingest_article(payload: Dict[str, Any]) -> JSONResponse:
    schema = load_schema()
    try:
        validated = validate_article_payload(payload, schema=schema)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    # normalize id and captured_at
    if "id" not in validated or not validated["id"]:
        validated["id"] = os.urandom(16).hex()
    validated.setdefault(
        "captured_at", datetime.now(timezone.utc).isoformat()
    )

    path = _jsonl_path(validated["company"], validated["quarter"])

    duplicate_id = _is_duplicate(path, validated["url"])
    if duplicate_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"status": "error", "duplicate_of": duplicate_id},
        )

    _ensure_parent(path)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(validated, ensure_ascii=False))
        f.write("\n")

    body = {
        "status": "stored",
        "id": validated["id"],
        "stored_path": str(path),
        "normalized_quarter": validated["quarter"],
    }
    return JSONResponse(status_code=status.HTTP_201_CREATED, content=body)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "news_coverage.server:app",
        host=os.getenv("INGEST_HOST", "0.0.0.0"),
        port=int(os.getenv("INGEST_PORT", "8000")),
        reload=os.getenv("INGEST_RELOAD", "false").lower() == "true",
    )
