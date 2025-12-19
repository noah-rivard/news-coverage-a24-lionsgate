# Ingest API Contract (Drafted for Chrome Intake)

Base URL: to be configured by the user (e.g., http://localhost:8000). All endpoints speak JSON and follow the coverage schema in `coverage_schema.json`.

## Endpoints

### GET /health
- Purpose: liveness check.
- Request: none.
- Response: `200 OK` with body `{ "status": "ok" }`.

### POST /ingest/article
- Purpose: accept one article payload matching `coverage_schema.json`.
- Request headers: `Content-Type: application/json`.
- Request body: CoverageArticle object (see schema). `id` optional; if omitted, server will assign a random id.
- Validation:
  - Required fields: company, quarter, title, source, url, published_at, facts (min 1).
  - `quarter` must match `YYYY Q[1-4]`.
  - Each `facts[]` object must include: fact_id, category_path, section, content_line, summary_bullets.
  - Facts may also include subheading/company/quarter/published_at overrides, but typical runs inherit company/quarter/published_at from the article level.
- Responses:
  - `201 Created` with body `{ "status": "stored", "id": "<uuid>", "stored_path": "data/ingest/{company}/{quarter}.jsonl", "normalized_quarter": "YYYY Q#" }`.
  - `400 Bad Request` on schema validation errors; body contains `errors: [...]`.

Legacy compatibility:
- The server accepts legacy single-category payloads that included top-level `section` and `subheading` (plus optional `summary` / `bullet_points`). When `facts` is missing, the server synthesizes a single `facts[0]` entry and drops the legacy keys before validation.

### POST /process/article
- Purpose: run the full manager-agent pipeline (classify -> summarize -> format -> ingest) for one scraped article.
- Request headers: `Content-Type: application/json`.
- Request body: `{ "title": "...", "source": "...", "url": "...", "content": "...", "published_at": "YYYY-MM-DD or RFC3339 timestamp" }`.
- Response:
  - `201 Created` with `{ "status": "processed", "markdown": "...", "stored_path": "...", "duplicate_of": null }`.
  - `400 Bad Request` for validation errors (missing required fields or invalid `published_at`).

### POST /process/articles
- Purpose: run the full manager-agent pipeline for multiple articles in one request.
- Request headers: `Content-Type: application/json`.
- Request body: either a JSON array of article objects or `{ "articles": [ ... ], "concurrency": 4 }`.
- Optional query parameter: `concurrency` (integer >= 1) to control parallelism.
- Response:
  - `201 Created` when all items succeed, or `207 Multi-Status` when some items fail or are invalid.
  - Body includes `counts` and a `results` array with `index`, `status` (`processed` | `error` | `invalid`), and per-item metadata (markdown, stored_path, error).

### POST /classify (optional)
- Purpose: return best-guess company/section/subheading/quarter for a URL+body before ingestion.
- Request body: `{ "url": "...", "title": "...", "body": "...", "published_at": "YYYY-MM-DD" }` (body optional but improves accuracy).
- Response: `200 OK` with `{ "company": "Amazon|Apple|Comcast/NBCU|Disney|Netflix|Paramount|Sony|WBD|A24|Lionsgate|Unknown", "company_match_confidence": 0-1, "section": "...", "subheading": "...", "quarter": "YYYY Q#", "quarter_inferred_from": "published_at|title", "classification_notes": "..." }`.

## Storage contract
- Accepted articles are appended to `data/ingest/{company}/{quarter}.jsonl` in UTF-8 JSONL.
- Each line must be a full CoverageArticle with server-assigned `id` (UUID v4) and `captured_at` timestamp (UTC ISO).
- Server must preserve client-supplied `ingest_source` and `ingest_version` for auditing.
- The server de-duplicates by URL per company/quarter. A repeated URL returns `duplicate_of` and does not append a new line.

## Error model
- All error responses: `application/json` with `{ "status": "error", "message": "...", "errors?": [ { "field": "...", "issue": "..." } ] }`.

## Security
- For local use, no auth required. For shared deployments, support optional `Bearer` token (static token configured via environment) checked on all POSTs; return `401` if missing/invalid.

## Rate and size limits
- Max body size: 1 MB per request (reject with `413 Payload Too Large`).
- Soft rate limit suggestion: 60 requests/minute per IP; respond `429` when exceeded.

## Alignment with schema
- The server must validate requests directly against `docs/templates/coverage_schema.json`. Any enum additions there automatically extend the API without code changes in clients.
