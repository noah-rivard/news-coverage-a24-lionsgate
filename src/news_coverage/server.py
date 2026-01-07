"""FastAPI ingest service wired to the coverage schema validator."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable

from fastapi import Body, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from .schema import load_schema, validate_article_payload
from .models import Article
from .file_lock import locked_path
from .reviewer import list_sample_articles, load_article_payload_from_path, render_reviewer_page


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


def _jsonl_contains_url(path: Path, url: str) -> bool:
    """Return True when the JSONL file already contains an entry for the URL."""
    if not path.exists():
        return False

    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if str(record.get("url")) == url:
                    return True
    except FileNotFoundError:
        return False

    return False


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _run_article_pipeline(
    article: Article,
    *,
    allow_duplicate_ingest: bool = False,
):
    """
    Lazy import wrapper to avoid circular import between server and workflow/agent_runner.
    """
    from .agent_runner import run_with_agent

    return run_with_agent(
        article,
        allow_duplicate_ingest=allow_duplicate_ingest,
    )


def _run_article_pipeline_override(
    article: Article,
    *,
    override_category: str,
    override_company: str | None = None,
    override_quarter: str | None = None,
    allow_duplicate_ingest: bool = False,
):
    """
    Reroute an article using a manual category override.

    This forces prompt/formatter routing based on the override category and
    re-runs the summarizer/formatter/ingest. Useful for reviewer workflows
    where the model picked a plausible but undesirable category.
    """
    from .agent_runner import run_with_agent
    from .workflow import build_classification_override

    classification_override = build_classification_override(
        article,
        category=override_category,
        company=override_company,
        quarter=override_quarter,
    )
    return run_with_agent(
        article,
        classification_override=classification_override,
        allow_duplicate_ingest=allow_duplicate_ingest,
    )


def _run_articles_pipeline(
    articles: list[Article],
    max_workers: int = 4,
):
    """
    Lazy import wrapper for batch manager-agent runs.
    """
    from .agent_runner import run_with_agent_batch

    return run_with_agent_batch(articles, max_workers=max_workers)


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


def _extract_article_payloads(payload: Any) -> list[Dict[str, Any]]:
    """
    Accept either a JSON array of article objects or an object with an `articles` list.
    """
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if "articles" in payload:
            articles = payload.get("articles")
            if not isinstance(articles, list):
                raise ValueError("articles must be a list of objects.")
            return articles
    raise ValueError(
        "Request body must be a JSON array of articles or an object with an 'articles' list."
    )


def _parse_articles_payload(
    payloads: Iterable[Any],
) -> tuple[list[tuple[int, Article]], list[dict[str, Any]]]:
    """
    Validate multiple article payloads, returning (valid, errors).
    """
    valid: list[tuple[int, Article]] = []
    errors: list[dict[str, Any]] = []
    for idx, raw in enumerate(payloads):
        try:
            if not isinstance(raw, dict):
                raise ValueError("Each article must be a JSON object.")
            normalized = _normalize_article_payload(raw)
            published = _parse_published_at(normalized.get("published_at"))
            normalized["published_at"] = published
            valid.append((idx, Article(**normalized)))
        except Exception as exc:
            errors.append({"index": idx, "error": str(exc)})
    return valid, errors


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


def _parse_published_at(raw: str | datetime | None) -> datetime | None:
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


def _build_article_from_payload(payload: Dict[str, Any]) -> Article:
    normalized = _normalize_article_payload(payload)
    # Allow date-only strings; invalid timestamps raise 400.
    published = _parse_published_at(normalized.get("published_at"))
    normalized["published_at"] = published
    return Article(**normalized)


def _process_result_body(result) -> dict[str, Any]:
    cls = getattr(result, "classification", None)
    body: dict[str, Any] = {
        "status": "processed",
        "markdown": result.markdown,
        "stored_path": str(result.ingest.stored_path),
        "duplicate_of": getattr(result.ingest, "duplicate_of", None),
        "classification_category": getattr(cls, "category", None),
        "prompt_name": None,
    }
    openai_response_ids = getattr(result, "openai_response_ids", None)
    if openai_response_ids:
        body["openai_response_ids"] = openai_response_ids
    if cls is not None:
        from .workflow import _route_prompt_and_formatter

        body["prompt_name"] = _route_prompt_and_formatter(cls)[0]
    return body


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/review", response_class=HTMLResponse)
def review_page() -> HTMLResponse:
    html = render_reviewer_page(samples=list_sample_articles())
    return HTMLResponse(content=html)


@app.post("/review/api/load")
def review_load(body: Dict[str, Any]) -> JSONResponse:
    try:
        if "payload" in body and body["payload"] is not None:
            payload = dict(body["payload"])
        else:
            payload = load_article_payload_from_path(str(body.get("path") or ""))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    normalized = dict(payload)
    if "content" not in normalized and "body" in normalized:
        normalized["content"] = normalized["body"]

    preview = {
        "title": normalized.get("title"),
        "source": normalized.get("source"),
        "url": normalized.get("url"),
        "published_at": normalized.get("published_at"),
        "content_chars": len(str(normalized.get("content") or "")),
    }
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"payload": normalized, "preview": preview},
    )


@app.post("/review/api/run")
def review_run(body: Dict[str, Any]) -> JSONResponse:
    try:
        if "payload" in body and body["payload"] is not None:
            payload = dict(body["payload"])
        else:
            payload = load_article_payload_from_path(str(body.get("path") or ""))
        article = _build_article_from_payload(payload)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # validation errors
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        allow_duplicate_ingest = bool(body.get("allow_duplicate_ingest", False))
        override_category = body.get("override_category")
        if override_category:
            result = _run_article_pipeline_override(
                article,
                override_category=str(override_category),
                override_company=(
                    str(body.get("override_company"))
                    if body.get("override_company") is not None
                    else None
                ),
                override_quarter=(
                    str(body.get("override_quarter"))
                    if body.get("override_quarter") is not None
                    else None
                ),
                allow_duplicate_ingest=allow_duplicate_ingest,
            )
        else:
            result = _run_article_pipeline(
                article,
                allow_duplicate_ingest=allow_duplicate_ingest,
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=_process_result_body(result),
    )


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
    duplicate_of = None
    with locked_path(path):
        _ensure_parent(path)
        if _jsonl_contains_url(path, validated["url"]):
            duplicate_of = validated["url"]
        else:
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(validated, ensure_ascii=False))
                f.write("\n")

    body = {
        "status": "duplicate" if duplicate_of else "stored",
        "id": validated["id"],
        "stored_path": str(path),
        "normalized_quarter": validated["quarter"],
        "duplicate_of": duplicate_of,
    }
    return JSONResponse(status_code=status.HTTP_201_CREATED, content=body)


@app.post("/process/article", status_code=status.HTTP_201_CREATED)
def process_article(
    payload: Dict[str, Any],
) -> JSONResponse:
    """
    End-to-end processing endpoint: classify -> summarize -> format -> ingest via manager agent.
    Returns markdown and ingest metadata.
    """
    try:
        article = _build_article_from_payload(payload)
    except Exception as exc:  # validation errors
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    try:
        allow_duplicate_ingest = bool(payload.get("allow_duplicate_ingest", False))
        override_category = payload.get("override_category")
        if override_category:
            result = _run_article_pipeline_override(
                article,
                override_category=str(override_category),
                override_company=(
                    str(payload.get("override_company"))
                    if payload.get("override_company") is not None
                    else None
                ),
                override_quarter=(
                    str(payload.get("override_quarter"))
                    if payload.get("override_quarter") is not None
                    else None
                ),
                allow_duplicate_ingest=allow_duplicate_ingest,
            )
        else:
            result = _run_article_pipeline(
                article,
                allow_duplicate_ingest=allow_duplicate_ingest,
            )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=_process_result_body(result),
    )


@app.post("/process/articles", status_code=status.HTTP_201_CREATED)
def process_articles(
    payload: Any = Body(...),
    concurrency: int | None = None,
) -> JSONResponse:
    """
    End-to-end batch processing endpoint: classify -> summarize -> format -> ingest
    for each article.
    Accepts a JSON array of article objects or `{ "articles": [...] }`.
    """
    try:
        article_payloads = _extract_article_payloads(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    if concurrency is None and isinstance(payload, dict):
        body_concurrency = payload.get("concurrency")
        if body_concurrency is not None:
            try:
                concurrency = int(body_concurrency)
            except (TypeError, ValueError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="concurrency must be an integer >= 1.",
                ) from exc

    if concurrency is None:
        concurrency = 4
    if concurrency < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="concurrency must be >= 1.",
        )

    indexed_articles, errors = _parse_articles_payload(article_payloads)
    if not indexed_articles:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "status": "error",
                "message": "No valid articles found.",
                "errors": errors,
            },
        )

    try:
        batch = _run_articles_pipeline(
            [article for _, article in indexed_articles],
            max_workers=concurrency,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc

    results: list[dict[str, Any]] = []
    processed_count = 0
    failed_count = 0

    for item in batch.items:
        original_index = indexed_articles[item.index][0]
        if item.error:
            failed_count += 1
            results.append(
                {"index": original_index, "status": "error", "error": item.error}
            )
            continue

        processed_count += 1
        processed_item = {
            "index": original_index,
            "status": "processed",
            "markdown": item.result.markdown,
            "stored_path": str(item.result.ingest.stored_path),
            "duplicate_of": getattr(item.result.ingest, "duplicate_of", None),
        }
        openai_response_ids = getattr(item.result, "openai_response_ids", None)
        if openai_response_ids:
            processed_item["openai_response_ids"] = openai_response_ids
        results.append(processed_item)

    for error in errors:
        results.append(
            {
                "index": error["index"],
                "status": "invalid",
                "error": error["error"],
            }
        )

    results.sort(key=lambda item: item["index"])
    body = {
        "status": "processed",
        "counts": {
            "total": len(article_payloads),
            "processed": processed_count,
            "failed": failed_count,
            "invalid": len(errors),
        },
        "results": results,
    }
    response_status = (
        status.HTTP_201_CREATED
        if failed_count == 0 and not errors
        else status.HTTP_207_MULTI_STATUS
    )
    return JSONResponse(status_code=response_status, content=body)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "news_coverage.server:app",
        host=os.getenv("INGEST_HOST", "0.0.0.0"),
        port=int(os.getenv("INGEST_PORT", "8000")),
        reload=os.getenv("INGEST_RELOAD", "false").lower() == "true",
    )
