"""FastAPI ingest service wired to the coverage schema validator."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .schema import load_schema, validate_article_payload
from .models import Article
from .file_lock import locked_path


app = FastAPI(title="News Coverage Ingest")


def _add_cors(app: FastAPI) -> None:
    """Allow browser extensions to call the API during local development."""
    allow_all = os.getenv("CORS_ALLOW_ALL", "true").lower() == "true"
    origins_env = os.getenv("CORS_ALLOW_ORIGINS", "")
    origins = [o.strip() for o in origins_env.split(",") if o.strip()]
    allow_credentials = (
        os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
    )
    if allow_all or not origins:
        origins = ["*"]
    if origins == ["*"] and allow_credentials:
        # Starlette/FastAPI disallow wildcard origins when credentials are enabled.
        allow_credentials = False
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
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


def _run_article_pipeline(article: Article, *, skip_duplicate: bool = False):
    """
    Lazy import wrapper to avoid circular import between server and workflow/agent_runner.
    """
    from .agent_runner import run_with_agent

    return run_with_agent(article, skip_duplicate=skip_duplicate)


def _normalize_article_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accept either `content` (preferred) or `body` (compat with ingest payloads).
    Ensure required keys exist for Article model.
    """
    data = dict(payload)
    if "content" not in data:
        if "body" in data:
            data["content"] = data["body"]
        else:
            raise ValueError("content (full article text) is required.")
    missing = [key for key in ("title", "source", "url") if not data.get(key)]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")
    return data


def _normalize_ingest_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accept both the current schema (with `facts`) and legacy single-category payloads.

    Legacy clients historically sent `section` and `subheading` at the top-level,
    plus optional `summary` / `bullet_points`. The current schema requires a
    `facts` array; for legacy payloads we synthesize a single fact, remove the
    legacy keys, and validate the normalized payload against the schema.
    """
    data: Dict[str, Any] = dict(payload)
    if data.get("facts") is not None:
        return data

    # Legacy fields: lift into a single fact and remove from top-level.
    section = data.pop("section", None)
    subheading = data.pop("subheading", None)

    bullets_raw = data.get("bullet_points")
    bullets: list[str] = []
    if isinstance(bullets_raw, list):
        bullets = [str(b).strip() for b in bullets_raw if str(b).strip()]
    summary_raw = data.get("summary")
    summary = str(summary_raw).strip() if summary_raw else ""

    content_line = bullets[0] if bullets else (summary or str(data.get("title", "")))
    summary_bullets = bullets or (
        [summary]
        if summary
        else ([content_line] if content_line else [])
    )
    if not summary_bullets:
        summary_bullets = [""]

    category_path = str(data.get("classification_notes") or "").strip()
    if not category_path:
        if section and subheading:
            category_path = f"{section} -> {subheading}"
        elif section:
            category_path = str(section)
        else:
            category_path = "Strategy & Miscellaneous News -> General News & Strategy"

    if not section:
        lowered = category_path.lower()
        if lowered.startswith("org"):
            section = "Org"
        elif lowered.startswith("investor relations"):
            section = "Investor Relations"
        elif lowered.startswith("m&a"):
            section = "M&A"
        elif lowered.startswith("highlights"):
            section = "Highlights"
        elif "content" in lowered and "deals" in lowered:
            section = "Content / Deals / Distribution"
        else:
            section = "Strategy & Miscellaneous News"

    data["facts"] = [
        {
            "fact_id": "fact-1",
            "category_path": category_path,
            "section": section,
            "subheading": subheading or "General News & Strategy",
            "company": data.get("company"),
            "quarter": data.get("quarter"),
            "published_at": data.get("published_at"),
            "content_line": content_line,
            "summary_bullets": summary_bullets,
        }
    ]
    return data


def _parse_published_at(raw: Optional[str | datetime]) -> Optional[datetime]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    txt = str(raw).strip()
    if not txt:
        return None

    # datetime.fromisoformat doesn't accept common RFC3339 variants such as a
    # trailing "Z" or offsets like "+0000". Normalize those before parsing.
    if txt.endswith(("Z", "z")):
        txt = f"{txt[:-1]}+00:00"
    else:
        txt = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", txt)

    try:
        return datetime.fromisoformat(txt)
    except ValueError as exc:
        raise ValueError(
            "published_at must be an ISO-8601/RFC3339 datetime (e.g. "
            "'2025-12-01T00:00:00Z', '2025-12-01T00:00:00+00:00') "
            "or a date-only string (e.g. '2025-12-01')."
        ) from exc


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest/article", status_code=status.HTTP_201_CREATED)
def ingest_article(payload: Dict[str, Any]) -> JSONResponse:
    schema = load_schema()
    try:
        normalized = _normalize_ingest_payload(payload)
        validated = validate_article_payload(normalized, schema=schema)
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
    with locked_path(path):
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


@app.post("/process/article", status_code=status.HTTP_201_CREATED)
def process_article(
    payload: Dict[str, Any],
    skip_duplicate: bool = False,
    skip_duplicate_for_url: Optional[str] = None,
) -> JSONResponse:
    """
    End-to-end processing endpoint: classify -> summarize -> format -> ingest via manager agent.
    Returns markdown and ingest metadata; duplicates return 200 with duplicate_of set.
    """
    try:
        normalized = _normalize_article_payload(payload)
        # Allow date-only strings; invalid timestamps raise 400.
        published = _parse_published_at(normalized.get("published_at"))
        normalized["published_at"] = published
        article = Article(**normalized)
    except Exception as exc:  # validation errors
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    if skip_duplicate_for_url and skip_duplicate_for_url != str(article.url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "skip_duplicate_for_url was provided but does not match the payload url "
                f"({article.url})."
            ),
        )

    try:
        effective_skip_duplicate = bool(skip_duplicate) or bool(skip_duplicate_for_url)
        result = _run_article_pipeline(article, skip_duplicate=effective_skip_duplicate)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc

    duplicate_of = getattr(result.ingest, "duplicate_of", None)
    body = {
        "status": "duplicate" if duplicate_of else "processed",
        "markdown": result.markdown,
        "stored_path": str(result.ingest.stored_path),
        "duplicate_of": duplicate_of,
    }
    status_code = status.HTTP_200_OK if duplicate_of else status.HTTP_201_CREATED
    return JSONResponse(status_code=status_code, content=body)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "news_coverage.server:app",
        host=os.getenv("INGEST_HOST", "0.0.0.0"),
        port=int(os.getenv("INGEST_PORT", "8000")),
        reload=os.getenv("INGEST_RELOAD", "false").lower() == "true",
    )
