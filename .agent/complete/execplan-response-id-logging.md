# OpenAI Responses: store=true and response.id correlation

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan must be maintained in accordance with `.agent/PLANS.md` in the repository root.

## Purpose / Big Picture

After this change, every pipeline run will record the OpenAI `response.id` values used during the run, so a developer can correlate a CLI/server run with the OpenAI dashboard Logs and/or retrieve the stored Response by ID via the API. We also set `store=true` by default for Responses requests so the IDs can be looked up later (configurable via an environment variable).

You can see it working by running the CLI on a sample article and observing an `openai_response_ids` block in JSON output and/or the agent trace log showing the response IDs.

## Progress

- [x] (2026-01-07) Add settings for `OPENAI_STORE` (default true) and wire it into all Responses API calls.
- [x] (2026-01-07) Collect and return response IDs from both direct pipeline and manager-agent runs.
- [x] (2026-01-07) Surface response IDs in CLI output (`--out *.json`) and server JSON responses.
- [x] (2026-01-07) Add unit tests that validate `store=true` is sent and response IDs are captured without hitting the network.
- [x] (2026-01-07) Update `README.md` and `CHANGELOG.md` under `## [Unreleased]`.
- [x] (2026-01-07) Run `pytest` and `flake8` from repo root and ensure green.

## Surprises & Discoveries

- Observation: Repo uses a 100-character line limit (flake8 E501).
  Evidence: `flake8` reported long lines in `tests/test_workflow.py` until wrapped.

## Decision Log

- Decision: Default `OPENAI_STORE` to true.
  Rationale: User explicitly approved enabling `store=true` and it enables dashboard/API correlation.
  Date/Author: 2026-01-07 / Codex

- Decision: Capture response IDs via an internal collector rather than scraping the dashboard Logs UI.
  Rationale: The dashboard Logs view is not exposed as a stable public API; response IDs are stable and already returned by the API.
  Date/Author: 2026-01-07 / Codex

- Decision: For Agents SDK manager calls, set `model_settings.store` explicitly from `OPENAI_STORE`.
  Rationale: Keeps manager-agent model calls consistent with the rest of the pipeline and makes behavior configurable.
  Date/Author: 2026-01-07 / Codex

## Outcomes & Retrospective

All OpenAI Responses calls in the pipeline now (a) send `store` according to `OPENAI_STORE` and (b) record `response.id` values into `PipelineResult.openai_response_ids`, CLI output, server responses, and optional agent trace logs. Tests remain offline and `pytest`/`flake8` are green.

## Context and Orientation

Key concepts in this repo:

- "Direct pipeline": `src/news_coverage/workflow.py:process_article` calls `classify_article` and `summarize_article` directly (plus formatting and ingest). This path is used by the CLI when `--mode direct`.
- "Manager-agent pipeline": `src/news_coverage/agent_runner.py:run_with_agent` uses the OpenAI Agents SDK to run a manager model which then calls tools (classify -> summarize -> format -> ingest). This is the default CLI mode and is also used by the FastAPI `/process/*` endpoints.
- "Response ID": the `id` field returned on an OpenAI Responses API response. Storing these IDs in local outputs makes it possible to find the corresponding run in the OpenAI dashboard or retrieve it via `GET /v1/responses/{id}` (with the same API key).

Key files:

- `src/news_coverage/config.py`: typed environment-driven settings.
- `src/news_coverage/workflow.py`: OpenAI Responses calls for classifier/summarizer and the direct pipeline orchestration.
- `src/news_coverage/agent_runner.py`: manager-agent orchestration and optional trace log writing (`AGENT_TRACE_PATH` / CLI `--trace`).
- `src/news_coverage/cli.py`: prints run output and optionally writes JSON/Markdown.
- `src/news_coverage/server.py`: FastAPI endpoints returning JSON results.
- `tests/test_workflow.py`, `tests/test_agent_runner.py`, `tests/test_server.py`: unit tests; must remain offline.

## Plan of Work

Implement three related capabilities:

1) Configuration: add `OPENAI_STORE` (default true) to `Settings` in `src/news_coverage/config.py`.

2) Collection: implement a small in-process response-id collector in `src/news_coverage/workflow.py` and have `classify_article`, `summarize_article`, and `summarize_articles_batch` record `response.id` values when the collector is active. Update `PipelineResult` to carry a structured `openai_response_ids` mapping. Wrap the direct pipeline (`process_article`) so it enables the collector for the duration of the run.

3) Manager-agent path: in `src/news_coverage/agent_runner.py`, enable the same collector while tools run and also extract manager model response IDs from the Agents SDK run result. Attach both to the returned `PipelineResult`, and include IDs in the trace log output when enabled.

4) Surfacing: update `src/news_coverage/cli.py` to print response IDs when present and ensure JSON output includes them. Update `src/news_coverage/server.py` to include IDs in `/process/article` and `/process/articles` responses.

5) Tests: add focused unit tests validating (a) `store=true` is passed into the create calls, and (b) response IDs are captured and included in results for the direct pipeline and (lightly) for the agent-run wrapper without calling the network.

6) Docs: update `README.md` to document `OPENAI_STORE` and describe where to find `openai_response_ids`. Update `CHANGELOG.md` under `## [Unreleased]`.

## Concrete Steps

Run these commands from the repository root (`c:\\Users\\KBAsst\\Coding\\news-coverage-a24-lionsgate`):

1) Tests:

    pytest

2) Lint:

    flake8

Expected outcome: both commands succeed. New tests should fail before the implementation and pass after.

## Validation and Acceptance

Acceptance criteria (behavior):

- Direct pipeline (`python -m news_coverage.cli ... --mode direct --out out.json`) produces an `openai_response_ids` field in the JSON output with at least `classifier` and `summarizer` IDs when using real OpenAI calls.
- Manager-agent pipeline (`python -m news_coverage.cli ... --mode agent --trace --out out.json`) includes both tool response IDs and manager response IDs (Agents SDK turns) in `openai_response_ids`, and the trace log includes the same IDs.
- Setting `OPENAI_STORE=false` disables the `store=true` parameter on Responses API calls (so no storing occurs).
- `pytest` and `flake8` are green.

## Idempotence and Recovery

- These changes are safe to re-run: enabling `store=true` affects only OpenAI-side storage for that response, and recording IDs only appends metadata to outputs.
- If storing responses is undesired in an environment, set `OPENAI_STORE=false` to disable.

## Artifacts and Notes

- Keep response IDs out of tracked docs by default; they should appear in CLI output, server responses, and optional trace logs, not in committed fixtures.

## Interfaces and Dependencies

- OpenAI SDK: use the existing `openai` client and keep using the Responses API.
- Agents SDK: use `RunResult.raw_responses[*].response_id` (when available) to capture manager-model response IDs.
