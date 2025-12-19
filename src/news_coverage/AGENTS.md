# Component Guide: `src/news_coverage/` (core workflow & services)

- Default classifier/summarizer rely on the OpenAI Responses API. `process_article` only builds a client (and therefore requires `OPENAI_API_KEY`) when those defaults are used; when injecting both tools or passing a client, it will run offline for tests.
- Injected tools must accept a `client` argument that can be `None` when you provide both classifier and summarizer; return the same dataclasses used in `workflow.py`.
- Ingest writes JSONL files under `data/ingest/{company}/{quarter}.jsonl` after schema validation; keep file paths stable so Chrome extension/back-end stay in sync.
- Ingest does not de-duplicate; repeated URLs are stored again and will produce additional final-output entries.
- Summarizer calls skip the `temperature` parameter when `SUMMARIZER_MODEL` is `gpt-5-mini` (model rejects it).
- Prompt/formatter routing is declarative (`ROUTING_RULES` in `workflow.py`), matching category substrings to prompt files; if the classifier confidence is below `routing_confidence_floor` (default 0.5), the coordinator falls back to `general_news.txt` to stay safe.
- Batch summarization helper (`summarize_articles_batch` + `_extract_summary_chunks`) accepts one prompt per article and raises when the model returns fewer chunks than articles to avoid silent drops.
- Prompt templates live in `src/prompts/`; keep `workflow.PROMPTS_DIR` aligned if relocating.
- Manager-agent path lives in `agent_runner.py` (Agents SDK). CLI defaults to `--mode agent`, with `--mode direct` retaining the legacy pipeline. Agent tools share a `PipelineContext` so classification/summarization/formatting/ingest stay in order.
- `run_with_agent_batch` enables concurrent per-article agent runs (used by the CLI `batch` command); each article still flows through classify -> summarize -> format -> ingest independently.
- Typer CLI uses the root command as the single-article runner (no `run` subcommand needed); the `build-docx` helper remains a subcommand.
- Update this guide whenever workflow behavior, storage paths, or tool signatures change so downstream services and tests remain aligned.
- Multi-title content deals (international slates) now route to `content_deals.txt` and use the `format_content_deals` formatter, which preserves multiple titles and ensures any date marker is hyperlinked to the article URL (it appends the publish date when missing and ignores unrelated parentheses such as subtitles).
- Ingest server CORS: `CORS_ALLOW_ALL` defaults to true; if origins resolve to `*` we automatically disable credentials to satisfy Starlette's wildcard+credentials restriction. To permit credentials, set explicit origins via `CORS_ALLOW_ORIGINS` and leave `CORS_ALLOW_CREDENTIALS=true` (default).
- Multi-buyer DOCX generation is handled via `coverage_builder.py` and `docx_builder.py`, invoked through `python -m news_coverage.cli build-docx`. It relies on keyword-based buyer routing (`buyer_routing.py`) and writes outputs to `docs/samples/news_coverage_docx/`; keep these paths and rules in sync with README/CHANGELOG.
- Buyer routing regexes use word-character lookarounds (`(?<!\\w)` / `(?!\\w)`) to avoid substring matches (e.g., "max" should not match "maxwell"); keep lookarounds intact when editing keyword logic.
- Manager-agent runs can append a plain-text trace log when `AGENT_TRACE_PATH` is set (or the CLI `--trace`/`--trace-path` flags); the log captures raw article content, tool calls/outputs, and the final markdown to help debug truncation issues.
- JSONL ingest writes, final-output appends, and trace logs are guarded with process-local file locks so parallel runs do not interleave writes.
