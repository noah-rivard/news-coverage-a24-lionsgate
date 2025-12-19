# Enable Parallel Agent Runs

This ExecPlan is a living document. The sections Progress, Surprises & Discoveries, Decision Log, and Outcomes & Retrospective must be kept up to date as work proceeds.

This plan is maintained according to `.agent/PLANS.md` at the repository root.

## Purpose / Big Picture

After this change, a user can send multiple article JSON files through the pipeline at once and have each article processed independently in parallel. The output stays separated per article, and concurrent runs do not interleave JSONL, final-output, or trace logs. You can see it working by running the new batch CLI command with multiple input files and observing per-article outputs plus a summary.

## Progress

- [x] (2025-12-18 23:45Z) Reviewed current single-article workflow, CLI entry points, and ingest/final-output appenders to identify concurrency touchpoints.
- [x] (2025-12-18 23:52Z) Added process-local file locks for JSONL ingest, final-output append, and agent trace appends to prevent interleaved writes.
- [x] (2025-12-18 23:58Z) Implemented concurrent batch helper for manager-agent runs and added a batch CLI command with per-article outputs.
- [x] (2025-12-18 23:59Z) Updated docs and component guides to describe the batch command and concurrency safeguards.
- [x] (2025-12-18 23:59Z) Run pytest and flake8 and record results.

## Surprises & Discoveries

- Observation: The pipeline appends to both JSONL ingest files and `docs/templates/final_output.md`, so parallel runs can interleave without a process-local lock.
  Evidence: Existing appenders in `src/news_coverage/workflow.py` and `src/news_coverage/agent_runner.py` wrote directly without locking.
- Observation: The default `.env` `AGENT_TRACE_PATH` uses backslashes that can be interpreted as escapes in tests, yielding an invalid path.
  Evidence: `pytest` initially failed in `test_agent_runner.py` with WinError 123 when `_append_trace_log` tried to create the parent directory.

## Decision Log

- Decision: Use process-local thread locks keyed by file path instead of adding a new dependency for cross-process locks.
  Rationale: The batch command uses threads inside a single process; a lightweight lock prevents interleaved writes without expanding dependencies.
  Date/Author: 2025-12-18 / Codex

- Decision: Add a CLI `batch` command rather than overloading the single-article command.
  Rationale: It keeps single-run behavior stable while exposing concurrency and per-article outputs explicitly.
  Date/Author: 2025-12-18 / Codex

## Outcomes & Retrospective

Batch processing now runs multiple agent pipelines concurrently with per-article outputs and safe file appends. Tests ran successfully after overriding `AGENT_TRACE_PATH` in agent-runner tests to avoid the invalid path from `.env`.

## Context and Orientation

The single-article pipeline lives in `src/news_coverage/workflow.py` (direct mode) and `src/news_coverage/agent_runner.py` (manager-agent mode). The CLI entry point is `src/news_coverage/cli.py`, which currently processes one JSON article file per invocation. Ingest writes JSONL under `data/ingest/{company}/{quarter}.jsonl`, and successful runs append a delivery-friendly block to `docs/templates/final_output.md`. Agent runs can also append trace logs when `AGENT_TRACE_PATH` is set.

## Plan of Work

Update the core appenders to use a process-local lock around read/append operations. Add a concurrent batch helper for agent runs, then expose it through a new CLI `batch` command that accepts multiple input files or directories, processes them in parallel, and writes per-article outputs to an optional output directory. Update README and component guides to describe the new command and concurrency safeguards, and add a targeted test to validate the batch helper collects both successes and failures.

## Concrete Steps

1. Add `src/news_coverage/file_lock.py` with a path-keyed thread lock and a context manager for locked appends.
2. Wrap JSONL ingest and final-output appends in `src/news_coverage/workflow.py` with the new lock helper; wrap agent trace appends in `src/news_coverage/agent_runner.py` and server ingest writes in `src/news_coverage/server.py`.
3. Add `run_with_agent_batch` in `src/news_coverage/agent_runner.py` to run multiple articles in parallel, returning per-article success or error outcomes.
4. Add a new `batch` command in `src/news_coverage/cli.py` that loads multiple article files, applies per-article skip-duplicate rules, runs the pipeline concurrently, and writes per-article outputs when `--outdir` is provided.
5. Update `README.md`, `src/AGENTS.md`, and `src/news_coverage/AGENTS.md` to document the batch command and concurrency safeguards.
6. Add a unit test in `tests/test_agent_runner.py` covering `run_with_agent_batch` error collection and per-article skip-duplicate flags.

## Validation and Acceptance

Run tests from the repo root:

    pytest
    flake8

Acceptance: The new `batch` CLI command processes multiple input JSON files in parallel, writes one output file per article when `--outdir` is set, and reports failures without aborting the whole batch. The new test passes, and existing tests remain green.

## Idempotence and Recovery

All changes are additive. Re-running the steps should be safe. If batch runs append to output logs during testing, set `FINAL_OUTPUT_PATH` and `AGENT_TRACE_PATH` to temporary locations to avoid mutating tracked files.

## Artifacts and Notes

Expected CLI example:

    python -m news_coverage.cli batch data/samples/debug --concurrency 2 --outdir scratch

Expected output includes per-article stored-path messages and a summary line reporting successes and failures.

## Interfaces and Dependencies

No new external dependencies. File locking is implemented via Python's `threading.Lock` in `src/news_coverage/file_lock.py`. The batch helper is exposed as `news_coverage.agent_runner.run_with_agent_batch(articles, skip_duplicate, max_workers, runner_factory)` and returns a `BatchRunResult` containing ordered `BatchItemResult` entries.

Change log: Updated Progress to mark tests complete and added the `.env` trace-path test discovery, plus the resolution note in Outcomes.
