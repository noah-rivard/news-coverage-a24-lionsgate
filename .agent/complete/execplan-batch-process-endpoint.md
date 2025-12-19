# Add Batch Process Endpoint for Agent Runs

This ExecPlan is a living document. The sections Progress, Surprises & Discoveries, Decision Log, and Outcomes & Retrospective must be kept up to date as work proceeds.

This plan is maintained according to `.agent/PLANS.md` at the repository root.

## Purpose / Big Picture

After this change, a client can submit multiple article payloads to the ingest server in a single request and receive per-article results, rather than calling `/process/article` one by one. This reduces client-side orchestration work and makes multi-article runs possible from integrations like scripts or extensions. You can see it working by POSTing a JSON array to `/process/articles` and receiving a response that lists each item with a processed or error status.

## Progress

- [x] (2025-12-19 01:20Z) Create `/process/articles` endpoint that accepts a list of article payloads (or an `articles` wrapper), validates each entry, runs the manager-agent batch pipeline, and returns per-item results with counts.
- [x] (2025-12-19 01:25Z) Add server tests covering full success and mixed valid/invalid payloads for the batch endpoint.
- [x] (2025-12-19 01:30Z) Update README, component guides, and ingest API contract to document the batch endpoint and tracing-disable environment option.
- [x] (2025-12-19 01:36Z) Update CHANGELOG and run `pytest` + `flake8`.

## Surprises & Discoveries

- Observation: FastAPI treated the batch payload as a query parameter until the body was explicitly annotated.
  Evidence: TestClient returned 422 with `loc: ['query', 'payload']` until `payload: Any = Body(...)` was added.

## Decision Log

- Decision: Accept either a raw JSON array or an object with an `articles` array, and allow `concurrency` via query param (or body fallback) for the batch endpoint.
  Rationale: Supports the most common client formats with minimal friction while keeping the endpoint strict about each article object.
  Date/Author: 2025-12-19 / Codex

- Decision: Return HTTP 201 when all batch items succeed and HTTP 207 when any item fails or is invalid.
  Rationale: Preserves the existing "created" status for full success while signaling partial failures without dropping results.
  Date/Author: 2025-12-19 / Codex

## Outcomes & Retrospective

Batch processing is now available via `/process/articles` with per-item results, optional concurrency controls, and documentation updates across README, API contract, and component guides. Tests and lint pass (pytest: 51 passed; flake8: clean); the only notable issue was the need to explicitly declare the body parameter to avoid 422 errors.

## Context and Orientation

The ingest server lives in `src/news_coverage/server.py` and exposes `/process/article`, which runs the manager-agent pipeline for a single `Article`. The manager-agent batch helper lives in `src/news_coverage/agent_runner.py` as `run_with_agent_batch`, returning per-item results. The CLI already uses that helper for its `batch` command, but the HTTP server does not expose a batch endpoint yet.

Tests for the server are in `tests/test_server.py`. Documentation describing server endpoints is in `README.md` and `docs/templates/ingest_api_contract.md`. Component behavior notes live in `src/AGENTS.md` and `src/news_coverage/AGENTS.md`. The changelog is `CHANGELOG.md` under `## [Unreleased]`.

## Plan of Work

First, add a new `/process/articles` endpoint in `src/news_coverage/server.py`. It should accept a JSON array of article objects or an object with an `articles` array and optional `concurrency` value. For each payload, reuse the existing single-article normalization (`_normalize_article_payload` and `_parse_published_at`) to build `Article` models. Invalid items should be captured as errors rather than aborting the entire request. The endpoint should call a new helper (e.g., `_run_articles_pipeline`) that wraps `run_with_agent_batch` and then return a response that includes per-item status (`processed`, `error`, or `invalid`) plus overall counts.

Next, add tests in `tests/test_server.py` that monkeypatch `_run_articles_pipeline` so the batch endpoint can be exercised without contacting OpenAI. Cover the happy path (two valid articles) and a mixed payload (one invalid, one valid) to verify index mapping and HTTP status codes.

Then update documentation: add a batch endpoint section in `README.md` with a curl example, describe the optional `concurrency` parameter, and add a short note about `OPENAI_AGENTS_DISABLE_TRACING=true` to silence the non-fatal tracing 503 logs if desired. Update `docs/templates/ingest_api_contract.md` to include `/process/article` and `/process/articles` descriptions. Update `src/AGENTS.md` and `src/news_coverage/AGENTS.md` to mention the batch endpoint and its behavior.

Finally, update `CHANGELOG.md` under `## [Unreleased]`, run `pytest` and `flake8` from the repo root, and record results in this plan.

## Concrete Steps

1. Edit `src/news_coverage/server.py`:
   - Add helper(s) to extract a list of article payloads and validate them into `Article` models.
   - Add `_run_articles_pipeline` wrapper calling `run_with_agent_batch`.
   - Implement `/process/articles` endpoint with per-item results and counts.

2. Edit `tests/test_server.py`:
   - Add stub batch result classes.
   - Add tests for `/process/articles` covering success and mixed invalid payloads.

3. Update docs:
   - `README.md`: add batch endpoint example and tracing-disable note.
   - `docs/templates/ingest_api_contract.md`: add `/process/article` and `/process/articles` sections.
   - `src/AGENTS.md` and `src/news_coverage/AGENTS.md`: mention batch endpoint.

4. Update `CHANGELOG.md` under `## [Unreleased]`.

5. Run validation commands from repo root:

   python -m pytest
   python -m flake8

   Expect all tests to pass and no lint errors.

## Validation and Acceptance

Acceptance is met when:
1. POSTing a JSON array of article payloads to `/process/articles` returns a JSON response with per-item statuses and counts, and valid articles are processed through the manager-agent pipeline.
2. The batch endpoint handles mixed valid/invalid payloads without aborting the entire request and returns a partial-success HTTP status.
3. `pytest` and `flake8` pass from the repository root.
4. Documentation and component guides describe the new endpoint and how to disable tracing logs.

## Idempotence and Recovery

The changes are additive and safe to reapply. If the server endpoint behavior needs to be rolled back, remove the new route and helper functions and revert the related docs/tests. For retries, re-run `pytest` and `flake8` after code edits.

## Artifacts and Notes

Example curl (expected to return a `results` array with two processed items):

  curl -X POST http://localhost:8000/process/articles ^
    -H "Content-Type: application/json" ^
    -d "[{\"title\":\"Example 1\",\"source\":\"Variety\",\"url\":\"https://example.com/1\",\"content\":\"Text\",\"published_at\":\"2025-12-01\"},{\"title\":\"Example 2\",\"source\":\"Variety\",\"url\":\"https://example.com/2\",\"content\":\"Text\",\"published_at\":\"2025-12-02\"}]"

## Interfaces and Dependencies

- `news_coverage.server._run_articles_pipeline(articles: list[Article], max_workers: int) -> BatchRunResult` wraps `news_coverage.agent_runner.run_with_agent_batch`.
- `news_coverage.server.process_articles` handles JSON arrays or `{ "articles": [...] }` payloads and returns per-item results.
- No new dependencies are required; reuse FastAPI, existing models, and the batch helper.

Plan updates must be reflected across all sections, including Progress, Decision Log, Surprises & Discoveries, and Outcomes & Retrospective.

Plan updated on 2025-12-19 to record completed implementation, testing results, and decision notes.
