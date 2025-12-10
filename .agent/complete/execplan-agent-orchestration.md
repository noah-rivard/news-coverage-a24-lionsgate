# Coordinator Agent Orchestration with Specialist Tools (stateless, one article per run)

This ExecPlan is a living document. Maintain `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` as work proceeds, in line with `.agent/PLANS.md`.

## Purpose / Big Picture

Enable a single “coordinator” agent (manager model `gpt-5.1`) to run one article end-to-end, invoking specialist tools for: (1) classification (section/subheading via fine-tuned model), (2) summarization, (3) formatting to Markdown, and (4) ingest (schema validation + storage). Runs remain stateless, refuse to start without `OPENAI_API_KEY`, and surface any failure immediately. Output is a Markdown bullet list suitable for human readers; the CLI can also write JSON/Markdown to disk.

## Progress

- [x] (2025-12-05 16:05Z) Plan drafted and approved.
- [x] (2025-12-05 16:45Z) Coordinator agent scaffolded with tool registry and routing.
- [x] (2025-12-05 17:00Z) Classification tool integrated with fine-tuned model; label normalization implemented.
- [x] (2025-12-05 17:15Z) Summarize/format tools implemented using prompts and `gpt-5-mini`.
- [x] (2025-12-05 17:35Z) Ingest tool reusing schema validation/storage; 409 surfaced cleanly.
- [x] (2025-12-05 17:45Z) CLI updated (API-key requirement, Markdown/JSON output options).
- [x] (2025-12-05 18:10Z) Tests (unit + light integration) added; `pytest`/`flake8` passing.
- [x] (2025-12-05 18:25Z) Docs/CHANGELOG/README updates completed.

## Surprises & Discoveries

- The fine-tuned classifier returns plain path strings (no JSON/confidence) despite the system prompt requesting JSON; we accept the string and optionally parse JSON if present.

## Decision Log

- Manager model: `gpt-5.1`; specialist summarize/format: `gpt-5-mini`; classifier: `ft:gpt-4.1-2025-04-14:personal:news-categorizer:BY2DIiT5`.
- Runs are stateless, one article each; refuse to run without API key.
- Ingest writes to `data/ingest/{company}/{quarter}.jsonl`; ingest tool surfaces 409 duplicate as user-visible error.
- Stop on first failure (validate/classify/summarize/format/ingest); no partial outputs.
- Output is Markdown bullets; CLI defaults to stdout, optional `--out` for file (md/json).

## Outcomes & Retrospective

- Coordinator agent and four tools were wired with the Agents SDK; CLI now enforces `OPENAI_API_KEY`, routes output to stdout or optional files, and stops cleanly on 409 duplicates. Tests and lint were green on 2025-12-05, and docs/CHANGELOG landed with the feature. Remaining risk: reliance on the fine-tuned classifier’s path formatting; added normalization mitigates the biggest mismatch.

## Context and Orientation

- Current flow: `summarize_articles` uses the Responses API with offline fallback; CLI prints a Rich table; the ingest FastAPI service validates/stores JSONL but is not tied to summarization.
- Models/schema: `Article`, `ArticleSummary`, `SummaryBundle`; coverage schema in `docs/templates/coverage_schema.json`; tests in `tests/`.
- Prompts available: `prompts/commentary.txt`, `prompts/interview.txt`, `prompts/content_formatter.txt`, `prompts/general_news.txt`, `prompts/exec_changes.txt`. Missing: `general_news_summarizer.txt`.
- Fine-tune label space (38 categories) uses path strings like `Org -> Exec Changes`, `Content, Deals & Distribution -> TV -> Greenlights`, etc.; highlights variants exist (“Highlights From The Quarter/This Quarter”) and need normalization to the schema’s `Highlights`.

## Plan of Work

1) **Agent scaffolding**
   - Add a coordinator in `src/news_coverage/workflow.py` (or new module) using Agents SDK `Runner.run_sync`.
   - Configure models per decision; enforce `tool_choice="required"` so summarize/format/ingest are called.
   - Enforce API key presence; otherwise abort with clear message.

2) **Classification tool**
   - Implement tool that calls the fine-tuned model with the training prompt.
   - Accept plain path string or JSON; normalize to canonical path.
   - Normalize highlights variants to `Highlights`.
   - Derive `section`, `subheading` from path; capture confidence if present, else set `None`.
   - Company inference (since model does not return company): add lightweight heuristic (regex/keywords for A24/Lionsgate; default `Unknown`); quarter inferred from `published_at`.

3) **Prompt routing**
   - Map classifier-derived `category` to prompt selection:
     - Exec Changes -> `prompts/exec_changes.txt`
     - Interview -> `prompts/interview.txt`
     - Commentary/analysis/strategy -> `prompts/commentary.txt`
     - Content deals/greenlights/renewals/cancellations/pickups/general -> `prompts/content_formatter.txt` when title formatting is needed; otherwise default to `prompts/general_news.txt`
     - Default fallback: `prompts/general_news.txt`
   - Document mapping and allow override flag for tests.

4) **Summarize & format tools**
   - Summarize tool: use chosen prompt + article body to produce structured bullets (list[str]) and optional tone/takeaway.
   - Format tool: take summary + metadata, emit Markdown string (bulleted list per current style).
   - Ensure deterministic, minimal outputs; no offline mode.

5) **Ingest tool**
   - Reuse existing `validate_article_payload` and storage path logic; write to `data/ingest/{company}/{quarter}.jsonl`.
   - On duplicate, propagate 409-style message; do not write partials.
   - Enrich payload with classifier outputs (section/subheading), inferred quarter/company, summary bullets, formatted text as optional fields.

6) **CLI integration**
   - Update `news_coverage/cli.py` to call the coordinator for one article.
   - Add `--out` (md or json) optional; default print Markdown to stdout.
   - Remove offline fallback; if no API key, exit with message.

7) **Tests**
   - Unit: mock Agents runner/tools to verify routing, normalization, duplicate handling, API-key refusal.
   - Integration-lite: run coordinator with stub tool implementations to confirm sequencing and output shape.
   - Keep `pytest`/`flake8` passing.

8) **Docs & housekeeping**
   - Update `README.md` (new flow, API key requirement, CLI usage).
   - Update `CHANGELOG.md` under Unreleased.
   - Update `src/AGENTS.md` if behavior changes; add prompt mapping notes if needed.
   - No code changes to FastAPI unless small helper reuse is needed.

## Concrete Steps

- Working dir: repo root.
- Implement coordinator/tools and routing per above in `src/news_coverage/`.
- Add/adjust tests in `tests/` for new behavior.
- Run `pytest` and `flake8`.
- Update docs/CHANGELOG/AGENTS as described.

## Validation and Acceptance

- With `OPENAI_API_KEY` set, `python -m news_coverage.cli run path/to/article.json` processes one article, prints Markdown bullets; exits with clear error if duplicate (409) or validation fails.
- Classifier returns mapped section/subheading; quarter inferred from `published_at`; company set via heuristic; stored JSONL entry contains these fields.
- `pytest` and `flake8` pass.

## Idempotence and Recovery

- Re-running coordinator on the same URL triggers 409 and leaves store unchanged.
- CLI run is read-only except for ingest append; storage path creation is mkdir -p and safe to rerun.

## Artifacts and Notes

- Code: coordinator + tools (classification, summarize, format, ingest) in `src/news_coverage/`.
- Prompts: existing files; no new prompts unless absolutely required.
- Storage: `data/ingest/{company}/{quarter}.jsonl` shared with FastAPI service.
- Script `tmp_run_classifier.py` (temporary) can be removed after development.
