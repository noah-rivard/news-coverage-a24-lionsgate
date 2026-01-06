# Per-title facts for list articles and DOCX-friendly rendering

This ExecPlan is a living document. The sections Progress, Surprises & Discoveries, Decision Log, and Outcomes & Retrospective must be kept up to date as work proceeds.

This plan must be maintained in accordance with `/.agent/PLANS.md`.

## Purpose / Big Picture

After this change, a single "greenlight/pickup/etc." list article produces one stored fact per title item (instead of one fact per output line), and each title item may optionally carry one additional note line when the article includes a material strategic detail. This prevents "detail blurb spam" while still capturing multiple titles from one source article.

In addition, the DOCX generator can render title items using the title-item fact content line (rather than the source article headline), which makes the generated quarterly coverage DOCX closer to the reference style.

You can see it working by running the pipeline on a known list article that includes multiple titles, then inspecting:

  - the stored JSONL record (it should contain multiple entries in `facts[]`, one per title item); and
  - the generated DOCX (each item line should be the title item line, with an optional follow-up note line).

## Progress

- [x] (2026-01-05) Add ExecPlan and capture decisions.
- [x] (2026-01-05) Update `content_formatter.txt` prompt to allow at most one note line per title item and to omit manual dates (pipeline renders dates).
- [x] (2026-01-05) Update `workflow._assemble_facts` to group content-list bullets into per-title facts with optional note lines.
- [x] (2026-01-05) Update DOCX build path to use fact-level title lines and render optional note lines as follow-on paragraphs.
- [x] (2026-01-05) Add unit tests for content-list grouping and a DOCX smoke test using `python-docx`.
- [x] (2026-01-05) Update `CHANGELOG.md` under Unreleased and run `pytest` and `flake8` from repo root.

## Surprises & Discoveries

- Observation: The reference WBD Q4 2024 DOCX uses mostly "No Spacing" paragraphs (not Word bullet list styles) and separates subheadings like "Development" / "Pickups" as their own bold paragraphs.
  Evidence: Extracted paragraph styles from `docs/samples/news_coverage_docx/2024 Q4 Warner Bros Discovery News Coverage vSend.docx` via `python-docx`.
- Observation: The DOCX build path was treating `FactResult` dataclasses as dicts (`fact.get(...)`), which would crash whenever `run.summary.facts` was populated.
  Evidence: `run.summary.facts` is filled with dataclasses from `workflow._assemble_facts(...)`; updated `coverage_builder.py` now normalizes facts via `dataclasses.asdict(...)`.

## Decision Log

- Decision: For greenlight/pickup/etc. list articles, the stored schema and DOCX use one fact per title item; final output markdown may repeat Category blocks per item.
  Rationale: Matches the user's preferred representation and aligns with how quarterly coverage docs list one line per title item with optional follow-up details.
  Date/Author: 2026-01-05 / Codex (user-confirmed).

## Outcomes & Retrospective

The pipeline now supports "one fact per title item" for content-list articles, with an optional attached note line that stays inside the same fact. This reduces low-value fact spam while preserving multi-title coverage.

DOCX generation now renders content-list entries using the fact-level title line and emits optional note lines as follow-on paragraphs under the entry, which is closer to the reference document's structure.

Tests added for the new grouping logic and a DOCX smoke test; `pytest` and `flake8` pass.

## Context and Orientation

The pipeline writes a single JSONL record per source article under `data/ingest/{company}/{quarter}.jsonl`. Each record contains a `facts[]` array where each fact represents one coverage item. Facts are later rendered into:

  - appended markdown blocks in `docs/templates/final_output.md`, and
  - buyer-specific quarterly DOCX files via `python -m news_coverage.cli build-docx`.

Relevant modules:

  - `src/news_coverage/workflow.py` builds summaries, assembles facts, formats markdown, and ingests validated payloads.
  - `src/prompts/content_formatter.txt` is the summarizer instruction used for content list categories (greenlights, pickups, etc.).
  - `src/news_coverage/coverage_builder.py` converts stored/agent facts into `CoverageEntry` items for DOCX generation.
  - `src/news_coverage/docx_builder.py` renders a `BuyerReport` into a DOCX.

Current behavior that causes the issue:

  - The summarizer output is split into one "bullet" per non-empty line.
  - When `summary.facts` is empty, `workflow._assemble_facts(...)` creates one fact per bullet line. This is wrong for list items that sometimes need a follow-up note line, because the note line becomes a separate fact.

## Plan of Work

First, update the content list prompt so the model emits one line per title item and optionally one additional line immediately after it only when the article contains a strategic detail worth capturing. Remove the requirement for the model to manually add (M/D) dates; the pipeline already knows `published_at` and adds date links/markers during rendering.

Second, update `workflow._assemble_facts` so that when the classifier indicates a content-list category (greenlights/pickups/development/renewals/cancellations/dating), the assembler groups consecutive lines into per-title facts:

  - A new fact starts at a line that looks like a title item line (contains a colon separating title from platform/genre).
  - A following line without such a colon attaches to the previous fact as a note line (capped at one note line per fact).

Third, update the DOCX builder path to use `fact.content_line` as the entry line rather than `article.title`, and to render any additional note lines as subsequent paragraphs under the entry.

Finally, add tests that fail before and pass after:

  - A unit test that verifies grouping: two title lines plus one note line under the first title yields two facts, with the note attached to the first fact.
  - A DOCX smoke test that writes a small report and asserts the expected paragraph texts exist in the resulting file.

## Concrete Steps

From repository root:

  1) Edit `src/prompts/content_formatter.txt` to reflect the new output rules (one title line per item, optional one note line, no manual date requirement).
  2) Edit `src/news_coverage/workflow.py` in `_assemble_facts(...)` to implement grouping for content-list categories.
  3) Edit `src/news_coverage/coverage_builder.py` and `src/news_coverage/docx_builder.py` to render fact-level title lines and optional note lines.
  4) Add/update tests under `tests/`.
  5) Update `CHANGELOG.md` under `## [Unreleased]`.
  6) Run:

      pytest
      flake8

## Validation and Acceptance

Acceptance criteria:

  - For a list article where one title has a meaningful extra detail line, the stored record contains:
      - fact-1: `content_line` is the title item line; `summary_bullets` contains two strings (title line then note line).
      - fact-2: `content_line` is the second title item line; `summary_bullets` contains one string.
  - The generated DOCX contains the title item lines as the visible entry lines (not the source article headline), and includes the extra note line as a separate following paragraph.
  - `pytest` and `flake8` pass.

## Idempotence and Recovery

The changes are deterministic and safe to rerun. If grouping logic misfires, revert to the prior `_assemble_facts` behavior by removing the content-list grouping branch, then rerun `pytest` to confirm baseline behavior.

## Artifacts and Notes

No artifacts yet.

## Interfaces and Dependencies

No new third-party dependencies. Use existing `python-docx` (already in the project) for DOCX writing and for reading the output in tests.
