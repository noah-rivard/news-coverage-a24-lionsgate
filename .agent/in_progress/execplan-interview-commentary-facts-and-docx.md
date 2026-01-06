# Interview/commentary single-fact formatting and DOCX rendering

This ExecPlan is a living document. The sections Progress, Surprises & Discoveries, Decision Log, and Outcomes & Retrospective must be kept up to date as work proceeds.

This plan must be maintained in accordance with `/.agent/PLANS.md`.

## Purpose / Big Picture

After this change, interview/commentary-style articles produce one coverage fact with a clear header line plus multiple follow-on lines (paragraphs). This mirrors how quarterly News Coverage DOCX files present interviews and commentary: a labeled header (Interview/Commentary) followed by a small set of concise paragraphs.

You can see it working by processing an interview/commentary article, then checking:

  - the stored JSONL record: a single fact with `content_line` starting with `Interview:` or `Commentary:` and `summary_bullets` containing the header plus the follow-on lines; and
  - the generated DOCX: the header line appears as its own paragraph with label styling, and the follow-on lines appear as separate paragraphs underneath (not as separate coverage items).

## Progress

- [x] (2026-01-05) Update prompts to emit a header line plus paragraphs (no manual dates).
- [x] (2026-01-05) Update fact assembly to group interview/commentary into a single fact.
- [x] (2026-01-05) Update DOCX build path to render interview/commentary using fact-level header + paragraphs.
- [x] (2026-01-05) Add unit tests and update `CHANGELOG.md`; run `pytest` and `flake8`.

## Surprises & Discoveries

Pending.

## Decision Log

- Decision: Interview/commentary items should be represented as one fact (not one fact per paragraph), and the DOCX should use the fact header line as the visible entry line.
  Rationale: Matches the reference quarterly coverage docs (single item with multiple paragraphs) and prevents low-value fact spam.
  Date/Author: 2026-01-05 / Codex (user-directed).

## Outcomes & Retrospective

Interview/commentary articles now produce a single fact when the model output begins with `Interview:` or `Commentary:`. The DOCX builder renders the header line as one paragraph and emits the follow-on lines as separate paragraphs under the same entry, matching the reference style more closely. Tests cover the grouping logic and DOCX rendering.

## Context and Orientation

The pipeline currently splits model output into one "bullet" per non-empty line and then assembles facts. For content-list items we now group title lines into per-title facts. Interview/commentary items need the opposite: keep many lines but treat them as one fact.

Key files:

  - `src/prompts/interview.txt` and `src/prompts/commentary.txt` define summarizer instructions.
  - `src/news_coverage/workflow.py` contains `_assemble_facts(...)` which builds `FactResult` objects from lines.
  - `src/news_coverage/coverage_builder.py` converts facts to `CoverageEntry` for DOCX output.
  - `src/news_coverage/docx_builder.py` renders `CoverageEntry` objects into DOCX paragraphs.

## Plan of Work

1) Prompts: revise `interview.txt` and `commentary.txt` so the first output line is a header that starts with `Interview:` or `Commentary:` and the remaining lines are concise paragraphs. Do not require dates in the output; the pipeline appends (M/D) in DOCX and adds date markers in Markdown from `published_at`.

2) Fact assembly: add a branch in `_assemble_facts(...)` for interview/commentary categories that returns exactly one fact with:

  - `content_line` equal to the first output line, and
  - `summary_bullets` equal to all output lines (header + paragraphs), preserving order.

3) DOCX: update the coverage build path so interview/commentary entries use the fact header line as the entry title, and the follow-on lines are rendered as separate paragraphs under that entry.

4) Tests: add a unit test asserting grouping behavior and a DOCX smoke test asserting the header + paragraphs are present as separate paragraphs.

## Validation and Acceptance

Acceptance criteria:

  - Processing an interview/commentary article yields exactly one fact whose first line starts with the correct label.
  - The generated DOCX includes the header line (with label styling) and multiple follow-on paragraphs under it.
  - `pytest` and `flake8` pass.
