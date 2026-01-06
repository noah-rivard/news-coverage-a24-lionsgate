# Multi-category “AND” routing for hybrid articles

This ExecPlan is a living document. The sections Progress, Surprises & Discoveries, Decision Log, and Outcomes & Retrospective must be kept up to date as work proceeds.

This plan must be maintained in accordance with `/.agent/PLANS.md`.

## Purpose / Big Picture

After this change, a single source article can yield multiple facts that belong to different category paths when the article truly covers multiple coverage areas. Concretely, “exec change” stories that also contain meaningful TV-network strategy context should produce both:

  - an `Org -> Exec Changes` fact (personnel event), and
  - a `Content, Deals & Distribution -> TV -> General News & Strategy` fact (strategic/business context).

This avoids forcing an “either/or” routing choice when both belong in the quarterly coverage report.

You can see it working by running the pipeline on a hybrid Variety story (exec exit + broader TV/cable context) and observing that the stored record contains at least two facts with different `category_path` values.

## Progress

- [x] (2026-01-05) Update prompts so the summarizer can emit “TV GNS” lines distinct from exec-change lines.
- [x] (2026-01-05) Update fact assembly to split “TV GNS” lines into a separate fact with the TV General News & Strategy category path.
- [x] (2026-01-05) Update DOCX coverage entry mapping so TV General News facts render as their own item lines.
- [x] (2026-01-05) Add tests and update `CHANGELOG.md`; run `pytest` and `flake8`.
- [x] (2026-01-05) Validate end-to-end on the two URL examples (isolated temp ingest/output).

## Surprises & Discoveries

Pending.

## Decision Log

- Decision: Use explicit line prefixes in summarizer output to drive multi-category fact splitting (`TV GNS:`).
  Rationale: Deterministic parsing without adding additional model calls; preserves “AND” semantics without changing the classifier’s single-path output contract.
  Date/Author: 2026-01-05 / Codex (user-directed).
- Decision: Make prefix-driven splitting routing-independent by allowing these prefixes across prompts and applying parsing regardless of classifier output.
  Rationale: The user explicitly wants “AND” behavior even when the classifier routes away from exec changes; prefix-based parsing is the smallest deterministic mechanism to achieve this.
  Date/Author: 2026-01-05 / Codex (user-directed).

## Outcomes & Retrospective

Validated end-to-end on the hybrid Variety example: the pipeline produced multiple `facts[]` with both `Org -> Exec Changes` and `Content, Deals & Distribution -> TV -> General News & Strategy` category paths from one source article, using `TV GNS:` lines. Prefix parsing is now applied regardless of classifier output or prompt routing.

## Context and Orientation

The pipeline currently routes each article to a single prompt based on the classifier’s `category_path`, and when assembling facts it typically builds fact category paths from the base classification and optional per-line labels (greenlights/pickups/etc). This works for “one topic” articles but fails for hybrid pieces where multiple categories legitimately apply.

Key files:

  - `src/prompts/exec_changes.txt` (exec-change summarizer format).
  - `src/news_coverage/workflow.py` (`_assemble_facts(...)` builds `FactResult` lists).
  - `src/news_coverage/coverage_builder.py` (maps facts to `CoverageEntry` for DOCX).
  - `src/news_coverage/docx_builder.py` (renders entries).

## Plan of Work

1) Prompt: extend `exec_changes.txt` so after the exec-change line(s), the model may add 1–3 lines prefixed with `TV GNS:` when the article contains meaningful TV/cable/streaming strategy context that belongs in Content/Deals/Distribution -> TV -> General News & Strategy. These lines must be separate from the exec-change line.

2) Assembly: update `_assemble_facts(...)` to detect and strip `TV GNS:` lines and group them into a single additional fact. The fact’s `category_path` is set explicitly to `Content, Deals & Distribution -> TV -> General News & Strategy`, with `section/subheading` derived via `_parse_category_path`.

3) DOCX mapping: update `coverage_builder._build_coverage_entry` to use `fact.content_line` as the item line for TV General News facts (instead of the article headline), and keep any additional lines as follow-on paragraphs.

4) Tests: add a unit test for `_assemble_facts` splitting behavior and a lightweight DOCX mapping test. Update `CHANGELOG.md`. Run `pytest` and `flake8`.

## Validation and Acceptance

Acceptance criteria:

  - A hybrid exec-change article that includes `TV GNS:` lines yields at least two facts with different `category_path` values.
  - The TV General News fact renders as its own entry line in DOCX (not just as a paragraph under the exec-change item).
  - `pytest` and `flake8` pass.
