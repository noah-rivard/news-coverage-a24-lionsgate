# Remove duplicate skipping across the pipeline

This ExecPlan is a living document. The sections Progress, Surprises & Discoveries, Decision Log, and Outcomes & Retrospective must be kept up to date as work proceeds.

This plan follows .agent/PLANS.md from the repository root and must be maintained in accordance with it.

## Purpose / Big Picture

After this change, the pipeline will always ingest and append articles, even if the URL has been seen before. People running the CLI, the FastAPI server, or the Chrome extension will see new entries appended every time they send an article, and the ingest API will no longer reject duplicate URLs. You can see it working by posting the same article twice and observing two lines in the JSONL file plus two appended blocks in docs/templates/final_output.md.

## Progress

- [x] (2025-12-19 00:00Z) Captured current duplicate-handling behavior and identified files, tests, and docs to update.
- [x] (2025-12-19 00:45Z) Remove duplicate detection and skip flags from core pipeline code and ingest server.
- [x] (2025-12-19 00:50Z) Update CLI, agent runner, and coverage builder to drop skip-duplicate options and flows.
- [x] (2025-12-19 00:55Z) Update tests to reflect always-ingest behavior and remove duplicate-specific assertions.
- [x] (2025-12-19 01:00Z) Update documentation (README, CHANGELOG, AGENTS guides) for the new always-ingest behavior.
- [x] (2025-12-19 01:05Z) Run pytest and flake8 from repo root and capture outcomes.

## Surprises & Discoveries

- Observation: The README contains older non-ASCII artifacts, which made exact patch matching brittle; a small script was used to insert the new de-duplication note safely.
  Evidence: README note insertion done via a short Python script rather than apply_patch.

## Decision Log

- Decision: Keep the IngestResult.duplicate_of field but stop populating it so existing consumers can still deserialize the result without breaking.
  Rationale: Removing the field would be a larger API break. Always returning None matches the new behavior while keeping compatibility.
  Date/Author: 2025-12-19 / Codex
- Decision: Remove skip-duplicate CLI flags and server query params entirely instead of keeping them as no-op switches.
  Rationale: Eliminating the surface area avoids confusion and keeps the CLI/API behavior aligned with the always-ingest rule.
  Date/Author: 2025-12-19 / Codex

## Outcomes & Retrospective

- Completed removal of duplicate detection across workflow, server, CLI, and agent runner. Ingest and process now always append, and docs/tests reflect the new behavior.
- Tests: pytest passed (44 tests), flake8 clean.

## Context and Orientation

Duplicate detection currently lives in src/news_coverage/workflow.py (ingest_article imports _is_duplicate from src/news_coverage/server.py). The FastAPI server in src/news_coverage/server.py rejects duplicates for /ingest/article and marks duplicates for /process/article. The CLI in src/news_coverage/cli.py exposes --skip-duplicate and --skip-duplicate-for-url and threads those flags into run_with_agent or process_article. The agent runner in src/news_coverage/agent_runner.py carries a skip_duplicate flag in PipelineContext and passes it into ingest_article. The coverage builder in src/news_coverage/coverage_builder.py calls run_with_agent(skip_duplicate=True). Tests in tests/test_ingest_skip_duplicate.py, tests/test_agent_runner.py, and tests/test_server.py cover duplicate behavior. README.md and AGENTS guides describe duplicate skipping and the current append behavior for non-duplicates.

## Plan of Work

First, remove duplicate detection in the ingest path by deleting _is_duplicate usage and any skip_duplicate branching in src/news_coverage/workflow.py and src/news_coverage/server.py. Keep IngestResult.duplicate_of but always set it to None. Update /ingest/article to always append and return 201, and /process/article to always return status processed with duplicate_of None. Next, remove skip-duplicate options and plumbing in src/news_coverage/cli.py, src/news_coverage/agent_runner.py, and src/news_coverage/coverage_builder.py. Then, update tests to assert two writes for the same URL and remove any duplicate-specific checks. Update docs in README.md, CHANGELOG.md, docs/AGENTS.md, src/AGENTS.md, and src/news_coverage/AGENTS.md to describe the always-ingest behavior and remove skip-duplicate flags. Finally, run pytest and flake8 from the repo root and record results here.

## Concrete Steps

1) Edit src/news_coverage/workflow.py to remove _is_duplicate import, remove skip_duplicate parameter from ingest_article, and always append to JSONL. Ensure IngestResult.duplicate_of is always None.
2) Edit src/news_coverage/server.py to remove _is_duplicate, remove skip_duplicate inputs, and remove 409 duplicate response. Always append and return 201 with duplicate_of None for /process/article.
3) Edit src/news_coverage/agent_runner.py to remove PipelineContext.skip_duplicate and related flow, simplify run_with_agent and run_with_agent_batch signatures, and update any internal comments.
4) Edit src/news_coverage/cli.py to remove --skip-duplicate and --skip-duplicate-for-url options and related validation, and simplify call sites.
5) Edit src/news_coverage/coverage_builder.py to call run_with_agent without skip_duplicate.
6) Update tests: rename or rewrite tests/test_ingest_skip_duplicate.py to expect two writes without special flags; remove skip-duplicate tests in tests/test_agent_runner.py and tests/test_server.py; adjust mocks accordingly.
7) Update README.md and CHANGELOG.md to reflect always-ingest behavior and removal of skip-duplicate flags. Update docs/AGENTS.md, src/AGENTS.md, and src/news_coverage/AGENTS.md to remove duplicate-specific notes and describe the new behavior.
8) Run from repo root:
   pytest
   flake8
   Capture results in this plan.

## Validation and Acceptance

Acceptance means:
- Posting the same payload twice to /ingest/article yields two JSONL lines and both responses are 201.
- Running the CLI or /process/article twice for the same URL appends two blocks in docs/templates/final_output.md.
- pytest and flake8 pass.

## Idempotence and Recovery

The edits are safe to re-run and should not require migration. If a change fails tests, revert only the related file and retry. JSONL files may contain duplicates by design after this change; this is expected.

## Artifacts and Notes

- Expected quick check (example):
    POST /ingest/article twice with the same payload returns HTTP 201 both times.
- Test runs:
    pytest -> 44 passed in 3.68s
    flake8 -> no output (success)

## Interfaces and Dependencies

- Keep news_coverage.workflow.ingest_article returning IngestResult with duplicate_of always None.
- Keep news_coverage.server endpoints /ingest/article and /process/article signatures stable for core payloads but remove skip_duplicate query logic.
- Keep CLI entry points functional without duplicate-related flags.

Change log note: This plan removes duplicate skipping across ingest and processing. Added to avoid confusion when users re-send the same article and still expect a new appended run.

Plan updated on 2025-12-19 after implementation and validation to reflect completed steps and test outcomes.
