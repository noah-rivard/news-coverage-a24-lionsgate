# Component Guide: `src/` (Python application code)

Scope: All Python modules under `src/`, including the agent workflow, configuration, and CLI.

Gotchas and expectations:
- Use the OpenAI Responses API (`openai>=1.54.0`) and Agents SDK (`openai-agents>=0.6.1`). Prefer the Responses API over legacy completions.
- Keep agent calls mockable in tests. Expose a helper to inject a client or stub so unit tests never hit the network.
- Centralize configuration (API keys, model names, timeouts) in `config.py` and rely on environment variables rather than hard-coded secrets.
- The coordinator pipeline (`workflow.process_article`) is single-article and stateless. It builds an OpenAI client only when default classifier/summarizer tools are used; injected tools plus/or a provided client allow offline tests. It routes prompts/formatters via a declarative table keyed off classifier category substrings; when `confidence` is below `routing_confidence_floor` (default 0.5) it falls back to `general_news.txt`.
- Favor Pydantic models for external inputs/outputs to keep validation strict and user-facing text consistent.
- Any change to behavior or structure here must be mirrored in this `AGENTS.md` and documented in `README.md` plus `CHANGELOG.md`.
- Run `pytest` and `flake8` after modifications in this area; tests should not require internet access.
- DOCX generation for buyer-specific reports lives in `coverage_builder.py` + `docx_builder.py`; it uses the existing agent pipeline for summaries. Update this guide if output locations, keyword routing, or CLI flags change.
- The FastAPI server now exposes `/process/article`, which wraps the manager-agent pipeline (classify → summarize → format → ingest). It accepts raw article fields (`title`, `source`, `url`, `content`, `published_at`) and returns the Markdown plus storage path; missing dates will raise because the pipeline cannot infer a quarter.

Recent changes:
- Manager-agent path added in `agent_runner.py`; CLI defaults to `--mode agent` with a `--mode direct` fallback to the previous hand-wired pipeline.
- Summarizer requests skip the `temperature` parameter when `SUMMARIZER_MODEL` is `gpt-5-mini` (model rejects it).
- Default summary token budget raised to 1,200 (`MAX_TOKENS` env var) to prevent truncated Responses API outputs on longer articles.
- Classifier confidence is now only used to trigger the general-news fallback when present and below the floor; missing confidence no longer forces the fallback prompt.
- Prompt templates reside in `src/prompts/`; keep `workflow.PROMPTS_DIR` aligned if relocating.
- Batch summarization helper `_extract_summary_chunks`/`summarize_articles_batch` now fails fast when the model does not emit one summary per article, preventing silent data loss.
- CLI runs skip duplicate checks automatically for fixtures under `data/samples/debug/`; `ingest_article` also accepts `skip_duplicate=True` when you need to bypass deduping in controlled scenarios.
- Markdown formatter now outputs three lines (Title, Category, Content) and places the article date (M/D) as the hyperlink to the article URL to match delivery formatting.
- Company inference now uses the buyer keyword routing list (Amazon, Apple, Comcast/NBCU, Disney, Netflix, Paramount, Sony, WBD, A24, Lionsgate), falling back to `Unknown` when nothing matches.
- After a successful, non-duplicate ingest the pipeline appends the formatted final-output block (with matched buyers and ISO timestamp) to `docs/templates/final_output.md`; override via `FINAL_OUTPUT_PATH` for tests or alternate destinations.
