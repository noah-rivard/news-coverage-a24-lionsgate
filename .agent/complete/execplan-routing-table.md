# Routing Table for Summaries and Formatters

This ExecPlan is a living document. Update `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` as work proceeds. Keep it compliant with `.agent/PLANS.md`.

## Purpose / Big Picture

We want the coordinator to use a routing table so each article is sent to the right summarizer prompt and formatter. When classifier confidence is low, the system should default to the general-news prompt. Batch summarization must use the same routing rules, giving each article its own prompt even when processed together. The outcome should be observable through tests and CLI runs: categories drive prompt/formatter selection predictably, and low-confidence classifications avoid misrouting.

## Progress

- [x] (2025-12-06 18:00Z) Wrote initial ExecPlan capturing goals and approach.
- [x] (2025-12-06 19:00Z) Implemented routing table with confidence floor, routed formatter selection, and per-article prompts for batch summaries.
- [x] (2025-12-06 19:05Z) Updated tests, README, AGENTS, CHANGELOG; ran pytest and flake8 (all green).

## Surprises & Discoveries

- None yet.

## Decision Log

- Decision: Use `routing_confidence_floor` defaulting to 0.5; confidence below the floor routes to `general_news.txt` regardless of category.
  Rationale: Avoid misrouting when the classifier is unsure while keeping the threshold configurable via settings.
  Date/Author: 2025-12-06 / Codex
- Decision: Keep batch summaries in a single model call but embed per-article instructions and require one prompt name per article.
  Rationale: Preserves throughput while honoring routing differences per story and maintaining 1:1 chunk validation.
  Date/Author: 2025-12-06 / Codex

## Outcomes & Retrospective

- Routing is declarative and confidence-aware; batch helper now respects per-article routing. Tests and lint pass. No unexpected issues.

## Context and Orientation

Relevant code sits in `src/news_coverage/workflow.py`, which currently picks a prompt via `_select_prompt` (string matching) and always uses `format_markdown`. `summarize_articles_batch` takes a single `prompt_name` for all articles. Settings live in `src/news_coverage/config.py`. Tests are in `tests/test_workflow.py`. Prompts live under `src/prompts/`. Component guides are `src/AGENTS.md` and `src/news_coverage/AGENTS.md`. README documents the workflow and batch helper. Any behavioral change must be mirrored in those docs plus `CHANGELOG.md`.

## Plan of Work

Describe routing with explicit rules: match category substrings to prompt file and formatter name; include a configurable confidence floor (default 0.5) that forces `general_news.txt` when confidence is below the floor or missing. Implement a helper that returns both prompt and formatter for a `ClassificationResult`.

Update the coordinator to use the new routing helper instead of `_select_prompt`, plugging the selected formatter into the pipeline. Keep default formatter `format_markdown`, but allow routing table entries to specify a formatter name.

Revise batch summarization so each article uses its routed prompt. Accept a list of prompt names (or a single name for backward compatibility), and build a combined request that embeds per-article instructions while still enforcing 1:1 chunk parsing. Share the same routing helper for both single and batch flows.

Add tests: routing falls back to `general_news.txt` on low confidence; high confidence selects specialized prompt; batch summarization accepts per-article prompts and still raises on missing chunks. Adjust existing batch tests for the new signature. Mock file loads/clients to stay offline.

Add a `routing_confidence_floor` setting to `config.py` with README/AGENTS updates. Record changes in `CHANGELOG.md`.

## Concrete Steps

1) Modify `workflow.py`: define routing table/rule helper; add confidence floor support; wire coordinator and batch summarization to per-article routing and formatter selection.
2) Update `config.py` with `routing_confidence_floor` default 0.5.
3) Expand tests in `tests/test_workflow.py` to cover routing behavior and new batch API.
4) Update docs: `src/AGENTS.md`, `src/news_coverage/AGENTS.md`, `README.md`, `CHANGELOG.md` to reflect routing table, confidence fallback, and batch prompt-per-article behavior.
5) Run `pytest` and `flake8`.

## Validation and Acceptance

Run `pytest` and `flake8` from repo root; expect all green. For manual proof, run the CLI on a debug fixture and confirm routing (e.g., a Greenlights path uses `content_formatter.txt` when confidence >= floor; setting confidence low should force `general_news.txt`). Batch helper tests should demonstrate it raises on misaligned chunks and accepts per-article prompts.

## Idempotence and Recovery

Changes are additive/configurable; rerunning steps is safe. If routing rules misbehave, lower the confidence floor or adjust the table and rerun tests. No migrations or destructive steps are involved.

## Artifacts and Notes

N/A yet.

## Interfaces and Dependencies

Expose routing via a helper returning `(prompt_name, formatter_fn)` given `ClassificationResult` and settings. Batch summarization should accept either a single `prompt_name` (applied to all) or a list matching the articles. Config adds `routing_confidence_floor: float`. Default formatter remains `format_markdown`. Use OpenAI Responses API stubs in tests (no network).
