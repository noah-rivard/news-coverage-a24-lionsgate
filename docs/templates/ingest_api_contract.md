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
- Request body: CoverageArticle object (see schema). `id` optional; if omitted, server will assign UUID.
- Validation:
  - Required fields: company, quarter, section, title, source, url, published_at.
  - `quarter` must match `YYYY Q[1-4]` and align with `published_at` unless `quarter_inferred_from` is `title` or `user_override`.
  - `section` and `subheading` must be from the enumerations in the schema.
  - Duplicate handling: the server should reject exact-URL duplicates with `409 Conflict` and include `duplicate_of` in the response.
- Responses:
  - `201 Created` with body `{ "status": "stored", "id": "<uuid>", "stored_path": "data/ingest/{company}/{quarter}.jsonl", "normalized_quarter": "YYYY Q#" }`.
  - `400 Bad Request` on schema validation errors; body contains `errors: [...]`.
  - `409 Conflict` on duplicate URL/ID; body contains `duplicate_of`.

### POST /classify (optional)
- Purpose: return best-guess company/section/subheading/quarter for a URL+body before ingestion.
- Request body: `{ "url": "...", "title": "...", "body": "...", "published_at": "YYYY-MM-DD" }` (body optional but improves accuracy).
- Response: `200 OK` with `{ "company": "A24|Lionsgate|Unknown", "company_match_confidence": 0-1, "section": "...", "subheading": "...", "quarter": "YYYY Q#", "quarter_inferred_from": "published_at|title", "classification_notes": "..." }`.

## Storage contract
- Accepted articles are appended to `data/ingest/{company}/{quarter}.jsonl` in UTF-8 JSONL.
- Each line must be a full CoverageArticle with server-assigned `id` (UUID v4) and `captured_at` timestamp (UTC ISO).
- Server must preserve client-supplied `ingest_source` and `ingest_version` for auditing.

## Error model
- All error responses: `application/json` with `{ "status": "error", "message": "...", "errors?": [ { "field": "...", "issue": "..." } ] }`.

## Security
- For local use, no auth required. For shared deployments, support optional `Bearer` token (static token configured via environment) checked on all POSTs; return `401` if missing/invalid.

## Rate and size limits
- Max body size: 1 MB per request (reject with `413 Payload Too Large`).
- Soft rate limit suggestion: 60 requests/minute per IP; respond `429` when exceeded.

## Deduping rules
- A payload is a duplicate if `url` matches an already stored record for the same company OR if the normalized body hash matches an existing record. Duplicate returns `409` with `duplicate_of` pointing to the stored `id` or `url`.

## Alignment with schema
- The server must validate requests directly against `docs/templates/coverage_schema.json`. Any enum additions there automatically extend the API without code changes in clients.
