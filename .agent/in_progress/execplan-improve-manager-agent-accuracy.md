# Improve manager-agent accuracy and text hygiene

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan must be maintained in accordance with `.agent/PLANS.md` from the repository root.

## Purpose / Big Picture

After this change, the manager-agent pipeline will file articles under the correct company even when multiple buyers are mentioned, and it will no longer leak garbled characters (mojibake, meaning broken symbols caused by a text encoding mismatch) into summaries or trace logs. For exec-change stories, summaries will reflect when a role is explicitly described as “former,” improving accuracy. You can see the change working by reprocessing `tmp_deadline_leavy.json` and observing that the output company is WBD, the ingest path is under `data/ingest/WBD/`, and the summary does not contain mojibake.

## Progress

- [x] (2025-12-19 01:20Z) Drafted ExecPlan based on trace log findings and repo guides.
- [x] (2025-12-19 02:10Z) Implemented text normalization and wired it into direct and agent pipelines.
- [x] (2025-12-19 02:20Z) Added position-aware company inference and coverage tests.
- [x] (2025-12-19 02:35Z) Added exec-change qualifier guard and unit test coverage.
- [x] (2025-12-19 02:50Z) Updated changelog/guides and ran pytest/flake8.

## Surprises & Discoveries

- Observation: The trace shows company inference chose Netflix even though the article is about WBD, causing ingest into `data/ingest/Netflix/...`.
  Evidence: `docs/traces/agent-trace-20251219-005825.log` shows `company: "Netflix"` and `stored_path` under `data/ingest/Netflix/...`.
- Observation: The article text includes mojibake (`ƒ?` sequences) that surfaces in outputs.
  Evidence: Same trace and `tmp_deadline_leavy.json` content.

## Decision Log

- Decision: Replace fixed buyer-priority selection with a scored, position-aware selection that prefers the earliest/strongest subject company in title and lead.
  Rationale: The current priority list can misfile when multiple buyers are mentioned in a single sentence.
  Date/Author: 2025-12-19 (Codex)
- Decision: Add a lightweight, dependency-free text normalization step before classification/summarization and trace logging.
  Rationale: Avoids adding new packages while removing visible mojibake in outputs.
  Date/Author: 2025-12-19 (Codex)
- Decision: Add a post-processing guard for exec-change summaries to preserve "former" role qualifiers when present.
  Rationale: The trace summary overstated current role; the article explicitly said "former."
  Date/Author: 2025-12-19 (Codex)
- Decision: Skip README changes because there are no new commands, flags, or usage steps.
  Rationale: Behavior changes are internal quality improvements without user-facing workflow changes.
  Date/Author: 2025-12-19 (Codex)

## Outcomes & Retrospective

Normalization now cleans common mojibake sequences before classification and summarization, and agent traces note when normalization occurs. Company inference now scores title/lead matches ahead of body-only mentions, preventing misfiled buyers in multi-mention stories. Exec-change summaries now preserve "former" when the article explicitly uses it. Tests passed (pytest, flake8) with no remaining gaps identified for this scope.

## Context and Orientation

The manager-agent pipeline lives in `src/news_coverage/agent_runner.py` and uses tools that call into `src/news_coverage/workflow.py`. Company inference happens in `_infer_company` inside `src/news_coverage/workflow.py`, which depends on keyword routing from `src/news_coverage/buyer_routing.py`. Summaries for exec changes are guided by `src/prompts/exec_changes.txt`. Trace logs are written by `_format_trace_log` in `src/news_coverage/agent_runner.py`. Tests for company inference are in `tests/test_company_inference.py`; pipeline tests live in `tests/test_workflow.py` and `tests/test_agent_runner.py`. The sample article for verification is `tmp_deadline_leavy.json`.

## Plan of Work

Milestone 1: Normalize article text before the agent and direct pipeline stages. Add a new helper (for example, `normalize_article_text`) in `src/news_coverage/workflow.py` that fixes common mojibake sequences (examples: `ƒ?` pairs for quotes/apostrophes, `Ã¢ÂÂ` sequences) and returns a cleaned string plus a short “normalization notes” summary. Use this helper to create a normalized `Article` instance in both `process_article` and `run_with_agent` so classification, summarization, and formatting see clean text. Keep the original raw content in the trace log but add a small line in the trace indicating normalization occurred (do not dump the full cleaned text). Update or add tests to prove mojibake is removed from the summary while raw input remains unchanged in fixtures.

Milestone 2: Improve company inference to prefer the actual subject when multiple buyers appear. Extend the buyer routing logic to record match locations (title, lead, body) and positions. Use a scoring rule that explicitly prefers title hits over lead hits, lead hits over body hits, and earlier positions over later. Preserve the existing word-boundary matching to avoid substring noise. Update `_infer_company` in `src/news_coverage/workflow.py` to use the new scoring rather than fixed priority. Add a test using `tmp_deadline_leavy.json` to assert the inferred company is WBD even when Netflix is mentioned in the lead. Update the existing “prefers priority when multiple” test to reflect the new tie-break rules (for example, Apple still wins if it appears first in the title).

Milestone 3: Improve exec-change summary accuracy by preserving “former” when the article indicates it. Add a small post-processing step after `summarize_article` for exec-change routed prompts that scans the article text for patterns like “former [role]” or “former [title]” near the person’s name and ensures the summary bullet reflects that qualifier. Do not invent roles; only add “former” when it appears in the article text. Add a focused test in `tests/test_workflow.py` (or a new test module) that feeds a short article snippet and verifies the summary bullet includes “former” when appropriate.

Milestone 4: Documentation and changelog updates. Update `CHANGELOG.md` under `## [Unreleased]` with the improvements (company inference scoring, text normalization, exec-change qualifier handling). Update `README.md` and any relevant `AGENTS.md` files if behavior changes are user-visible or alter assumptions about output formatting. Keep updates concise and in plain language.

## Concrete Steps

From repo root, edit the following files:

    src/news_coverage/workflow.py
    src/news_coverage/buyer_routing.py
    src/news_coverage/agent_runner.py
    src/prompts/exec_changes.txt (only if prompt wording needs adjustment)
    tests/test_company_inference.py
    tests/test_workflow.py
    CHANGELOG.md
    README.md (only if behavior changes need user guidance)
    src/AGENTS.md and src/news_coverage/AGENTS.md (only if behavior changes need to be documented)

Suggested local verification (avoid writing into real ingest/output):

    $env:INGEST_DATA_DIR = "c:\Users\KBAsst\Coding\news-coverage-a24-lionsgate\.tmp\ingest"
    $env:FINAL_OUTPUT_PATH = "c:\Users\KBAsst\Coding\news-coverage-a24-lionsgate\.tmp\final_output.md"
    $env:AGENT_TRACE_PATH = "c:\Users\KBAsst\Coding\news-coverage-a24-lionsgate\.tmp\trace.log"
    python -m news_coverage.cli tmp_deadline_leavy.json --mode agent --trace

Then run quality checks:

    pytest
    flake8

## Validation and Acceptance

- Running the CLI on `tmp_deadline_leavy.json` produces a `PipelineResult` with `classification.company` equal to `WBD`.
- The ingest output is written under `.../.tmp/ingest/WBD/2025 Q4.jsonl`.
- The summary bullet for the exec change includes “former” when the article says “Former CNN COO...”.
- The trace log indicates normalization occurred and the final markdown is free of mojibake.
- `pytest` and `flake8` are green.

## Idempotence and Recovery

All steps are safe to rerun. Use the `.tmp` folder with `INGEST_DATA_DIR`, `FINAL_OUTPUT_PATH`, and `AGENT_TRACE_PATH` so you can delete and re-run without affecting production data. If a test fails after modifying inference logic, revert that single test to a stricter version, re-run, and then update the code to satisfy it.

## Artifacts and Notes

Expected updated output excerpt for the sample article (summary line only):

    Content: Exit: David Leavy, former Chief Corporate Affairs Officer at Warner Bros. Discovery ([12/18](https://deadline.com/2025/12/david-leavy-wbd-exit-zaslav-cnn-1236652941/)) ...

Expected trace note (short, single line):

    Normalization: applied; replacements=quotes/apostrophes; length_delta=0

## Interfaces and Dependencies

Define or update these interfaces:

- In `src/news_coverage/workflow.py`, add a helper similar to:

    normalize_article_text(text: str) -> tuple[str, str | None]

  It returns the cleaned text and a short note describing changes (or None if unchanged).

- In `src/news_coverage/buyer_routing.py`, introduce a structured match result that includes positions, for example:

    @dataclass(frozen=True)
    class BuyerScore:
        buyer: str
        score: int
        earliest_pos: int
        matched_in: str  # "title" | "lead" | "body" | "url"

  Provide a helper that returns a list of BuyerScore for an article, and use that in `_infer_company`.

- In `src/news_coverage/agent_runner.py`, capture the normalization note in the trace log without duplicating the full cleaned text.

Note: Avoid adding new third-party dependencies unless absolutely necessary; keep normalization internal and deterministic.

---

Plan revision note: Initial draft created to address trace-identified misclassification and mojibake issues, plus an accuracy guard for exec-change summaries (2025-12-19).

Plan revision note: Updated progress and outcomes after implementation and validation (2025-12-19).
