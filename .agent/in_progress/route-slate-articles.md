# Route slate articles to content-deals formatter and emit multi-title lines

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds. This plan must be maintained in accordance with `.agent/PLANS.md` in the repository root.

## Purpose / Big Picture

After implementing this plan, the CLI/agent pipeline will correctly format multi-title international slate articles (like the Variety Brazil Netflix slate) into one line per title using the template `[Country] Title: Platform, genre (M/D)` and will route such articles to the content-deals prompt/formatter. Ingest remains single-record. Users will see the expected seven-line output for the referenced article instead of a single general-news line.

## Progress

- [x] (2025-12-11 18:00Z) Drafted ExecPlan.
- [x] (2025-12-11 18:25Z) Routing rule added for content-deals slate articles.
- [x] (2025-12-11 18:25Z) Content-deals formatter implemented and registered.
- [x] (2025-12-11 18:25Z) Content-deals prompt file aligned with supplied instructions.
- [x] (2025-12-11 18:30Z) Golden test added for the Variety Brazil slate.
- [x] (2025-12-11 18:32Z) README/AGENTS/CHANGELOG updated.
- [x] (2025-12-11 18:40Z) Tests (`pytest`, `flake8`) run and passing.
- [x] (2025-12-11 18:55Z) Added manual_runs sample folder, stub JSON, and helper script.

## Surprises & Discoveries

- None yet.

## Decision Log

- Decision: Keep ingest single-record; focus on routing/formatting only.
  Rationale: Avoid schema ripple; requirement limited to presentation.
  Date/Author: 2025-12-11 / Codex
- Decision: Fire content-deals formatter whenever multiple titles are emitted by the content-deals prompt; no extra heuristic passes.
  Rationale: User confirmed prompt already designed to handle multiple titles.
  Date/Author: 2025-12-11 / Codex

## Outcomes & Retrospective

Implemented routing + formatter + prompt to support multi-title content-deals slates with a golden test. Pipeline now renders the expected seven-line output for the Variety Brazil slate while keeping ingest single-record. No surprises encountered.

## Context and Orientation

Relevant files:
- `src/news_coverage/workflow.py`: routing (`ROUTING_RULES`, `_route_prompt_and_formatter`), formatter map (`FORMATTERS`), default `format_markdown`.
- `src/news_coverage/agent_runner.py`: agent path uses routing/formatter results.
- `src/prompts/`: prompt templates; will add/update a content-deals prompt file.
- `tests/`: place golden test for slate formatting.
Existing behavior: classifier output drives routing; formatter currently always uses first summary bullet. No formatter for multi-line content deals exists.

## Plan of Work

Describe edits concretely:
1) Update routing in `src/news_coverage/workflow.py`:
   - Add a routing rule for content-deals (greenlights/development) that maps to the new content-deals prompt and formatter. Ensure it triggers for international content; confidence may be null.
   - Keep existing rules intact; default remains general news.
2) Add content-deals formatter in `workflow.py` (or nearby module):
   - Accept `article`, `classification`, `summary`.
   - Use `summary.bullets` verbatim as multiple lines; do not collapse to first bullet.
   - Do not alter accents.
   - If summary lines lack dates, append article published_at formatted as M/D (no leading zero). Otherwise trust model output.
   - Register this formatter in `FORMATTERS` and bind to the routing rule.
3) Align prompt:
   - Create or update `src/prompts/content_deals.txt` (name consistent with routing) with the supplied system prompt text covering country prefix, platform, genre inference, S# rules, ending-season wording, no leading zeros, sub-studio handling, date must be article publish date, and ask user only if date missing.
4) Tests:
   - Add a golden test (e.g., `tests/test_content_deals_formatter.py`) that:
     - Mocks classifier to return `Content, Deals & Distribution -> International -> Greenlights -> TV`, company `Netflix`, quarter `2025 Q4`.
     - Provides article text from the Variety Brazil slate.
     - Mocks summarizer to return bullets representing the expected seven lines (with [Brazil] prefix, platforms, genres, (12/9)).
     - Asserts formatter output matches all seven lines and routing selects content-deals formatter.
     - Confirms ingest called once (single-record).
5) Docs:
   - Update `README.md` and `src/news_coverage/AGENTS.md` to note new content-deals routing/formatter behavior.
   - Add entry to `CHANGELOG.md`.
6) Run validation:
   - Run `pytest` and `flake8` from repo root.
   - Manually run CLI against the Variety article JSON to confirm output shows seven lines in desired format.

## Concrete Steps

From repo root:
- Edit `src/news_coverage/workflow.py` to add routing rule and formatter; register in `FORMATTERS`.
- Add/replace `src/prompts/content_deals.txt` with provided prompt text.
- Create `tests/test_content_deals_formatter.py` with mocks and golden assertions.
- Update `README.md`, `src/news_coverage/AGENTS.md`, `CHANGELOG.md`.
- Run:
    python -m pytest
    flake8
- Optional manual check:
    python -m news_coverage.cli path/to/variety_article.json --mode agent
  Expect markdown to list seven lines as specified.

## Validation and Acceptance

Feature is accepted when:
- `pytest` passes including new golden test; test fails on old code and passes after changes.
- `flake8` reports no issues.
- Running the CLI on the Variety Brazil slate yields:
    [Brazil] The Pilgrimage: Netflix, drama (12/9)
    [Brazil] A Estranha na Cama: Netflix, psychological thriller (12/9)
    [Brazil] Rauls: Netflix, crime drama (12/9)
    [Brazil] Habeas Corpus: Netflix, legal drama (12/9)
    [Brazil] Os 12 Signos de Valentina: Netflix, romantic comedy (12/9)
    [Brazil] As Crianças Estão de Volta: Netflix, family drama (12/9)
    [Brazil] Sua Mãe Te Conhece: Netflix, reality competition (12/9)

## Idempotence and Recovery

Edits are additive and reversible via git. Re-running tests is safe. If routing misfires, revert `workflow.py` and rerun tests. Prompt changes affect only content-deals routing; other prompts untouched.

## Artifacts and Notes

Keep new prompt text in `src/prompts/content_deals.txt` exactly as supplied. Golden test should embed expected lines explicitly for clarity.

## Interfaces and Dependencies

- `FORMATTERS` map in `workflow.py` must include the new formatter name (e.g., "content_deals") and callable `format_content_deals(article, classification, summary) -> str`.
- Routing rule should map to prompt filename `content_deals.txt` and formatter key `content_deals`.
- No external libraries needed beyond existing project deps.
