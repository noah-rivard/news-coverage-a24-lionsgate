# Multi-Fact Classification & Storage (Single Article, Multiple Labeled Facts)

This ExecPlan follows `.agent/PLANS.md` and is fully self-contained for a novice contributor.

## Purpose / Big Picture

We want a single article run to produce multiple labeled facts (e.g., greenlight + renewals) while keeping one output block and one stored JSONL record. Facts carry their own category/subheading (and optional per-fact company/quarter overrides) but share duplicate detection at the article URL level. Outputs (CLI, final_output.md, DOCX) must show the multiple facts without repeating the article header.

## Progress

- [x] (2025-12-17 11:20Z) Read relevant code and docs for workflow, storage, formatting, DOCX, schema.
- [x] (2025-12-17 11:35Z) Update schema/docs to add `facts` array and per-fact fields.
- [x] (2025-12-17 11:35Z) Update schema/docs to add `facts` array and per-fact fields.
- [x] (2025-12-17 11:55Z) Implement workflow changes (classification, summarization parsing, routing, formatting, ingest).
- [x] (2025-12-17 11:55Z) Update DOCX builder to place facts correctly without duplicating article headers.
- [x] (2025-12-17 11:57Z) Add/adjust tests for multi-fact behavior.
- [x] (2025-12-17 12:05Z) Update component AGENTS/README/CHANGELOG.
- [x] (2025-12-17 12:00Z) Run `pytest` and `flake8`.

## Surprises & Discoveries

- Schema required property change forced updating ingest/extension tests; added `minItems` to `facts` to keep validation meaningful (empty facts were silently allowed).
- `/ingest/article` had legacy clients that posted top-level `section/subheading`; added server-side normalization to synthesize a single `facts[0]` entry so older clients don't start failing after the schema change.

## Decision Log

- Duplicate detection remains URL-based; one stored record per article.
- Storage adds `facts` array; no legacy top-level section/subheading/summary/bullet_points needed.
- Per fact fields: fact_id, category_path, section, subheading, company, quarter (default article-level), published_at (article-level), content_line, summary_bullets.
- Summarization: single pass with labeled bullets to map facts.
- Ordering: preserve model order in outputs.
- Output: one block per article with multiple Category/Content pairs; DOCX uses facts to place content without repeating the article header.
- Schema now requires at least one fact (`minItems: 1`) to prevent empty payloads slipping through validation.
- Keep `/ingest/article` backward compatible by synthesizing `facts` when missing (storage still relies solely on `facts`).

## Outcomes & Retrospective

- Multi-fact support shipped: schema requires facts (min 1), workflow assembles facts from labeled bullets and renders multiple Category/Content pairs per article; ingest/DOCX honor facts without duplicating article headers. Tests and lint pass.

## Context and Orientation

Key files:
- `src/news_coverage/workflow.py`: classification, summarization, routing, formatting, ingest.
- `src/news_coverage/agent_runner.py`: agent path using the same workflow pieces.
- `src/news_coverage/coverage_builder.py` + `docx_builder.py`: DOCX placement by section/subheading.
- `docs/templates/coverage_schema.json` (+ `.md`): ingest schema docs.
- `docs/templates/final_output.md`: appended delivery log format.
- Tests: `tests/test_workflow.py`, `tests/test_content_deals_formatter.py`, `tests/test_agent_runner.py`, CLI/server tests.
- Component guides: `AGENTS.md`, `src/AGENTS.md`, `docs/AGENTS.md`, `src/news_coverage/AGENTS.md`.

## Plan of Work

1) Schema & docs
   - Extend `coverage_schema.json` to add `facts` (array of objects) with fields: `fact_id` (string), `category_path`, `section`, `subheading`, `company`, `quarter`, `published_at`, `content_line`, `summary_bullets` (array). Mark top-level single-category fields as legacy/optional in docs.
   - Update `coverage_schema.md` to describe the new fact-level structure and clarify URL-based dedupe.
   - Note per-fact company/quarter defaults to article-level; published_at is inherited.

2) Classification & fact extraction
   - Adjust classifier output handling to allow multiple category paths. Decide parsing strategy: either extend classifier prompt to emit multiple labeled categories or keep classifier single-category and rely on summarizer labels; document chosen approach here.
   - Introduce a fact assembly step that pairs labeled summary bullets with category/subheading/company/quarter defaults (and optional overrides if emitted).

3) Summarization & parsing
   - Update `content_formatter` (or a new prompt) to instruct the model to emit labeled bullets (e.g., “Greenlights: …”, “Renewals: …”) in one pass.
   - Implement a parser to split bullets into facts, preserving order, mapping labels to category paths/subheadings, and capturing both `content_line` (first line) and `summary_bullets` (list).
   - Define the label→category/subheading mapping table in code (covers Greenlights, Renewals, Development, Cancellations, Pickups, Dating, Exec Changes, General fallback).

4) Workflow data structures
   - Extend `SummaryResult` or add a new dataclass to hold structured facts (list of fact objects with fields above) while keeping raw bullets for backward references if needed.
   - Update `ClassificationResult` and downstream logic to carry multiple categories or per-fact links as required.
   - Ensure per-fact company/quarter default from article-level; allow overrides if present.

5) Formatting (CLI markdown & final_output.md)
   - Update `format_markdown` and `format_final_output_entry` to render:
     - Title once.
     - For each fact (model order): “Category: <path>” then “Content: <content_line with date link>”.
   - Ensure date link uses article published_at; do not duplicate date parentheticals already present in a bullet.

6) Ingest/storage
   - Modify `ingest_article` to write a single JSONL record with the new `facts` array and updated schema validation.
   - Keep URL-based duplicate detection unchanged; skip ingest on duplicate as today.

7) DOCX generation
   - Update `coverage_builder.py` to iterate facts, creating coverage entries per fact (with section/subheading from the fact) while keeping one article title/url/published_at per entry.
   - Ensure docx_builder placement uses these per-fact entries without duplicating article headers.

8) Agent path parity
   - Ensure `agent_runner.py` mirrors the direct workflow changes (tools store structured facts, formatting uses the new renderer).

9) Tests
   - Add/extend tests:
     - Workflow parse: multi-fact labeled bullets produce correct facts array.
     - Formatting: single block with multiple Category/Content pairs.
     - Ingest: schema accepts facts array; duplicate URL still blocks re-run.
     - DOCX: mixed categories in one article place facts under correct subheadings with no repeated header.
   - Adjust existing tests that assume single category/bullet behavior.

10) Docs & metadata
    - Update `README.md` summary of outputs, ingest shape, and DOCX behavior.
    - Update relevant `AGENTS.md` files for `src/`, `docs/`, `src/news_coverage/`.
    - Update `CHANGELOG.md`.

11) Validation
    - Run `pytest` and `flake8`.
    - (Optional) Run CLI on a sample article with mixed categories to inspect markdown and appended final_output.md.

## Concrete Steps

- Edit schema files: `docs/templates/coverage_schema.json`, `docs/templates/coverage_schema.md`.
- Update workflow code: `src/news_coverage/workflow.py` (data structures, parsing, formatting, ingest), `src/news_coverage/agent_runner.py`.
- Update prompts if needed: `src/prompts/content_formatter.txt` (or add a new prompt file) for labeled output.
- Update DOCX pipeline: `src/news_coverage/coverage_builder.py`, `src/news_coverage/docx_builder.py` if interface changes.
- Tests: modify/add under `tests/` as outlined.
- Docs/meta: `README.md`, `CHANGELOG.md`, component `AGENTS.md` files.

Commands to run (from repo root, after code changes):
- `pytest`
- `flake8`

## Validation and Acceptance

- `pytest` passes; new tests confirm multi-fact parsing, formatting, ingest schema acceptance, DOCX placement.
- `flake8` clean.
- Manual run (optional): CLI on a mixed-category article produces one block with multiple Category/Content pairs, appends correctly to `docs/templates/final_output.md`.
- JSONL written contains `facts` array with expected fields; duplicate URL re-run reports duplicate as before.

## Idempotence and Recovery

- Schema and code changes are additive to structure but replace reliance on single-category fields; re-running CLI on the same URL will still be blocked by duplicate detection, avoiding partial fact duplication.
- If parsing fails to map labels, fallback should either raise (to surface error) or place in a General/unknown bucket—documented in code comments.

## Artifacts and Notes

- Keep label→category mapping small and explicit in code.
- Preserve model output order; do not sort facts.
- Date links use article-level published_at; do not attempt per-fact dating.

## Interfaces and Dependencies

- `facts` array schema (per fact):
  - `fact_id` (string/index)
  - `category_path` (string)
  - `section` (string)
  - `subheading` (string or null)
  - `company` (string)
  - `quarter` (string)
  - `published_at` (string date, inherited)
  - `content_line` (string)
  - `summary_bullets` (array of strings)

- Formatter output structure (markdown/final_output.md):
  - Title once, then for each fact:
    - `Category: <category_path_display>`
    - `Content: <content_line with date link>`
