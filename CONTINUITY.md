# CONTINUITY.md

## Goal (incl. success criteria):
- Validate that interview/commentary and exec-change articles format like the manual buyer DOCX templates under `docs/samples/news_coverage_docx/`.
- A/B test exec-change “detail note” behavior:
  - A = `EXEC_CHANGE_NOTE_MODE=prefixed` (exec-change details must be explicitly prefixed `Note:`)
  - B = `EXEC_CHANGE_NOTE_MODE=unprefixed` (exec-change can absorb one unprefixed follow-on sentence)
- Success criteria: outputs capture multiple *material* items per source when appropriate (including multi-category “AND” routing) while avoiding low-value extra blurbs; exec-change items include helpful detail lines in the same spirit as the manual templates.

## Constraints/Assumptions:
- Prefer isolated temp ingest/output dirs for live URL tests; avoid writing scraped content into tracked `data/` by accident.
- Do not include manual (M/D) dates in model outputs; renderers add date markers/links from `published_at`.

## Key decisions:
- Use deterministic, line-level routing override prefixes in summarizer output so multi-category splitting is routing-independent.
  - Examples: `Film GNS: ...`, `TV GNS: ...`, `Specials Greenlights: ...`, plus exec-change lines (`Exit:`/`Promotion:`/`Hiring:`/`New Role:`).
- Allow A/B testing exec-change note behavior via `EXEC_CHANGE_NOTE_MODE` (default `prefixed`, alternative `unprefixed`).

## State:
- Active task: Run a handful of articles referenced by the manual buyer DOCX templates through both A and B modes and compare which output is closer to the template style.

## Done:
- Workflow parses routing override lines into separate facts regardless of classifier/prompt routing: `src/news_coverage/workflow.py`.
- Routed facts now support follow-on note lines without creating separate facts (non-Content included): `src/news_coverage/workflow.py`.
- DOCX medium grouping now supports `Specials`: `src/news_coverage/coverage_builder.py`, `src/news_coverage/docx_builder.py`.
- DOCX builder now includes Highlights and uses List Paragraph styling + subheading headings for non-Content sections to match manual templates: `src/news_coverage/docx_builder.py`.
- Prompts updated to allow `<Medium> GNS:` and `<Medium> Development/Greenlights/...:` lines: `src/prompts/*.txt`.
- Prompts updated to allow non-Content routing overrides (`M&A:`, `Strategy:`, `IR Quarterly Earnings:`): `src/prompts/*.txt`.
- Docs updated to mention `Specials` as a medium option: `docs/templates/coverage_schema.md`.
- Validation: `pytest` (60 passed) and `flake8` (pass).
- Ran A/B exec-change note behavior on 4 WBD-relevant articles referenced by the 2024 Q4 WBD manual template (Finch interview, Harry Potter commentary, Wuthering Heights pickup, and a US networks leadership/executive structure story).
  - Outputs stored under: `C:\Users\KBAsst\AppData\Local\Temp\news_coverage_manual_docx_ab_20260105-172100\`
  - Per-article Markdown outputs:
    - A (`prefixed`): `...\out-prefixed\*.out.md`
    - B (`unprefixed`): `...\out-unprefixed\*.out.md`
  - Aggregated final outputs:
    - A: `...\final_output-prefixed.md`
    - B: `...\final_output-unprefixed.md`

## Now:
- Review the printed A/B outputs against the manual template style and decide whether `EXEC_CHANGE_NOTE_MODE` should default to `prefixed` or `unprefixed` (or whether prompts should be unified so the A/B difference is *only* note-line handling).

## Next:
- If `unprefixed` is preferred: ensure the unprefixed exec-changes prompt variant preserves the same multi-category prefix behavior as other prompts so “AND” routing remains consistent.

## Open questions (UNCONFIRMED if needed):
- For mixed-medium deal list stories: should we encourage (via prompt) prefixing *every* title item with `<Medium> <Subheading>:` to avoid relying on the classifier's single category?

## Working set (files/ids/commands):
- `src/news_coverage/workflow.py`
- `src/prompts/general_news.txt`
- `src/prompts/content_formatter.txt`
- `docs/templates/coverage_schema.md`
- `tests/test_workflow.py`
- Commands: `pytest`, `flake8`
