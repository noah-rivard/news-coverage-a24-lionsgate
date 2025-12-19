# Add summarizer retry on output truncation

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan must be maintained in accordance with `.agent/PLANS.md` in the repository root.

## Purpose / Big Picture

Long or multi-title articles sometimes cause the summarizer to stop early with a `max_output_tokens` incomplete response. After this change, the pipeline will automatically retry the summarizer with a trimmed article body before failing, so users can process long articles without manual reruns or hand edits. You can see it working by running the summarizer tests or by processing a long article and observing that the run completes without the truncation error.

## Progress

- [x] (2025-12-19 00:45Z) Read repo guides and located summarizer error path in `src/news_coverage/workflow.py`.
- [x] (2025-12-19 00:49Z) Updated summarizer flow to retry with truncated content when `max_output_tokens` is returned.
- [x] (2025-12-19 00:49Z) Updated batch summarizer to apply the same retry behavior.
- [x] (2025-12-19 00:49Z) Updated tests to cover the retry path and failure-after-retry behavior.
- [x] (2025-12-19 00:49Z) Updated docs (`README.md`, component guides) and `CHANGELOG.md` to reflect the new retry behavior.
- [x] (2025-12-19 00:49Z) Ran `pytest` and `flake8`.
- [x] (2025-12-19 00:50Z) Moved this ExecPlan to `.agent/complete/` with outcomes recorded.

## Surprises & Discoveries

No surprises. Retry logic worked with truncated inputs and tests passed on the first run. Archiving the plan required only README/CHANGELOG pointer updates.

## Decision Log

- Decision: Retry the summarizer using a truncated article body instead of changing prompts or introducing new configuration flags.
  Rationale: Trimming input keeps output format stable and avoids expanding the public configuration surface.
  Date/Author: 2025-12-19 (Codex)
- Decision: Use two fallback content limits (12000, then 6000 characters) before failing.
  Rationale: Two steps reduce output size while keeping enough context for summaries in most long articles.
  Date/Author: 2025-12-19 (Codex)

## Outcomes & Retrospective

Summarizer calls now retry with a truncated article body when `max_output_tokens` is returned, reducing failures on long articles. Batch summarization uses the same fallback. Tests (`pytest`, `flake8`) passed. The main limitation is that truncation can omit details found near the end of very long articles; runs still error if truncation is insufficient.
This ExecPlan is archived under `.agent/complete/` with README and changelog pointers updated.

## Context and Orientation

The summarizer logic lives in `src/news_coverage/workflow.py` inside `summarize_article` and `summarize_articles_batch`. These functions call the OpenAI Responses API and now retry with truncated article bodies when the response is incomplete with reason `max_output_tokens`. Tests covering this behavior are in `tests/test_workflow.py`. User-facing behavior notes live in `README.md` and component guides in `src/AGENTS.md` and `src/news_coverage/AGENTS.md`. The changelog entry belongs under `## [Unreleased]` in `CHANGELOG.md`.

## Plan of Work

Update the summarizer helpers in `src/news_coverage/workflow.py` to detect `max_output_tokens` and retry with a smaller article body. Keep the prompt and output parsing intact so formatting does not change. Apply the same retry logic to the batch summarizer. Adjust or add tests in `tests/test_workflow.py` to assert that a second summarizer call succeeds after a truncated retry and that repeated truncation still raises. Then update documentation and the changelog to explain the new retry behavior and its limitation (trimming may omit details from the end of an article). Finish by running `pytest` and `flake8` from the repo root.

## Concrete Steps

1) Edit `src/news_coverage/workflow.py` to add a helper that builds a user message with an optional content-length cap and a helper to detect incomplete reasons. Use these helpers in `summarize_article` and `summarize_articles_batch` to retry once or twice with shorter content.
2) Update `tests/test_workflow.py` to cover the retry path and the final failure path.
3) Update `README.md`, `src/AGENTS.md`, `src/news_coverage/AGENTS.md`, and `CHANGELOG.md` to describe the retry behavior.
4) From `c:\Users\KBAsst\Coding\news-coverage-a24-lionsgate`, run:
   - `pytest`
   - `flake8`

## Validation and Acceptance

Acceptance means a long-article summarization no longer fails immediately on `max_output_tokens` and instead retries with truncated content. Tests should pass: `pytest` should report all tests passing, and `flake8` should report no lint errors. The updated documentation should clearly state the retry behavior and its limitations.

## Idempotence and Recovery

Edits are safe to apply more than once. If tests fail due to the new retry logic, re-run after adjusting the retry limits. If a change needs to be backed out, revert the touched files (`src/news_coverage/workflow.py`, `tests/test_workflow.py`, `README.md`, `CHANGELOG.md`, `src/AGENTS.md`, `src/news_coverage/AGENTS.md`) to their previous content.

## Artifacts and Notes

Validation output (2025-12-19 00:49Z):

   pytest
   ============================= test session starts =============================
   collected 45 items
   ...
   ============================== 45 passed in 3.67s =============================

   flake8
   (no output; success)

## Interfaces and Dependencies

No new dependencies are required. Keep using the existing OpenAI Responses API via `client.responses.create` and the existing `SummaryResult` data class. The retry behavior should be implemented within `summarize_article` and `summarize_articles_batch` in `src/news_coverage/workflow.py`.

Plan updated on 2025-12-19 to reflect completed implementation, documentation updates, validation results, and archive status.
