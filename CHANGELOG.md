# Changelog

All notable changes to this project will be documented in this file. This project adheres to [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Chrome intake extension now exposes a right-click context menu for pages and embedded frames so users can trigger a scrape on the clicked frame; manifest includes the `contextMenus` permission to support it.
- Component guide for the planning area (`.agent/AGENTS.md`) plus a `complete/` folder for finished ExecPlans.
- Manager agent path implemented with the OpenAI Agents SDK (`agent_runner.py`) plus CLI mode flag (`--mode agent|direct`) defaulting to the agent path.
- Multi-buyer DOCX generation pipeline: buyer keyword routing (`buyer_routing.py`), coverage/DOCX builders, and CLI command `build-docx` to produce Q4 2025 News Coverage files per buyer plus `needs_review.txt`.
- Dependency on `python-docx` to render coverage reports styled after the WBD Q2 template.
- Chrome MV3 extension scaffold under `extensions/chrome-intake/` with content script (Readability-based scrape), service worker, popup, options page, esbuild bundling, and component AGENTS guide.
- README now documents how to build/load the extension and run the ingest server for it.
- ROADMAP outlining the agent-as-tool workflow decisions, sequential processing, and future reviewer agent.
- ExecPlan for building the Python OpenAI Agents workflow (`.agent/in_progress/execplan-news-agent.md`).
- Project scaffolding with `pyproject.toml`, package source under `src/news_coverage/`, and component guide `src/AGENTS.md`.
- Coordinator pipeline (`news_coverage.workflow.process_article`) that classifies (fine-tuned model), summarizes, formats Markdown, and ingests to JSONL.
- CLI now supports single-article runs with optional file output and surfaces duplicate (409-style) responses.
- Unit tests for the coordinator pipeline; pytest/flake8 kept green.
- Expanded subheading normalization (Analyst Perspective, IR Conferences, Misc. News) to align classifier output with schema.
- Pipeline now appends each successful article to `docs/templates/final_output.md` (override with `FINAL_OUTPUT_PATH`) using the matched-buyers format.
- Backfilled existing ingested articles into `docs/templates/final_output.md` so the log starts with prior runs.
- Final-output content line now hyperlinks the appended date to the article URL.
- ExecPlan for the Chrome intake extension and ingest service design (`.agent/in_progress/execplan-chrome-extension.md`), including taxonomy findings from the sample news coverage DOCX files.
- Canonical coverage payload schema and guide (`docs/templates/coverage_schema.json` and `docs/templates/coverage_schema.md`) for the Chrome extension and backend ingest.
- Ingest API contract draft (`docs/templates/ingest_api_contract.md`) specifying endpoints, validation, errors, and storage rules aligned to the coverage schema.
- Python schema loader/validator (`news_coverage.schema`) backed by `jsonschema`, plus tests for valid/invalid payloads.
- FastAPI ingest service (`news_coverage.server`) with `/health` and `/ingest/article` endpoints using the schema validator, duplicate detection, and JSONL storage; tests cover happy path and duplicate rejection.
- FastAPI `/process/article` endpoint that runs the manager-agent pipeline (classify → summarize → format → ingest) and returns Markdown plus storage metadata for a single scraped article.
- Agents SDK quick reference (`docs/agents_sdk_quickref.md`) summarizing how this repo should use the OpenAI Agents SDK.
- Docs component guide (`docs/AGENTS.md`) to keep documentation updates concise and aligned with code behavior.
- Component guide for the core workflow/services (`src/news_coverage/AGENTS.md`) noting how injected tools can run offline.
- Debug fixture set of three Variety articles under `data/samples/debug/` plus a `data/AGENTS.md` guide for managing fixtures.
- Sample output markdown for the three debug fixtures (`docs/sample_outputs.md`) generated with the latest pipeline defaults.
- Final output Markdown template with buyer list and ISO timestamp layout (`docs/templates/final_output.md`) and README link.

### Changed
- Chrome intake extension now requests only Feedly hosts at install; other origins are requested at click time. Content script is no longer auto-injected and link captures run in a background tab with a 20s timeout.
- Popup surfaces capture failures (e.g., permission denied) and guides users to right-click capture when no article is cached.
- Company inference now routes across all major buyers (Amazon, Apple, Comcast/NBCU, Disney, Netflix, Paramount, Sony, WBD, A24, Lionsgate) instead of only A24/Lionsgate; schema/docs/ingest contract updated to reflect the expanded enum.
- Paramount keyword order now prioritizes `cbs`/network brands before generic `paramount` terms so title hits (e.g., “... at CBS”) register as strong matches instead of being overridden by weaker body-only matches.
- README cleanup: clarified Chrome extension steps, fixed output format bullet, and pointed ExecPlan references to `.agent/complete/`.
- Chrome intake extension now auto-sends each captured article to the configured endpoint (default `/process/article`) and reports status in the popup; options default updated accordingly while keeping `/ingest/article` compatibility.
- README now documents the coordinator workflow, single-article CLI usage, duplicate handling, and the fact that injected tools can run without an API key.
- README documents the DOCX generator and how to invoke it.
- CLI defaults to the manager agent path; `--mode direct` retains the legacy direct pipeline.
- Clarified CLI invocation uses a single command (no `run` subcommand) in README examples.
- Default summary token limit increased to 1,200 (`MAX_TOKENS`) to reduce truncated Responses API outputs on longer articles; README and component guides note the new default.
- Prompt routing now treats missing classifier confidence as sufficiently confident, so specialized prompts (e.g., content formatter) are used unless a low confidence score is explicitly returned.
- Clarified in the Agents SDK quick reference that runs are stateless and handled one article at a time.
- `process_article` only constructs an OpenAI client when default tools are used; injected classifier/summarizer pairs (or a provided client) no longer require `OPENAI_API_KEY`, enabling offline tests. README and component guides now reflect this behavior.
- Prompt templates relocated under `src/prompts/` to align with `workflow.PROMPTS_DIR`.
- README includes a quick-start note on the debug fixture files for repeatable testing.
- CLI skips duplicate checks when running fixtures under `data/samples/debug/`, and `ingest_article` now supports an explicit `skip_duplicate` flag (covered by tests).
- Debug fixture content now uses the full Dec 5, 2025 Variety article bodies so local runs reflect real-world ingest text; README and `data/AGENTS.md` note the change and its internal-only intent.
- Coordinator prompt/formatter routing is now a declarative table with a confidence floor fallback to `general_news.txt`; batch summarization accepts one prompt per article while preserving 1:1 chunk validation. README and component guides capture the new behavior.
- Markdown formatter now emits delivery-ready `Title` / `Category` / `Content` lines and appends the article date (M/D) as the hyperlink to the source URL; docs and sample outputs reflect the format.
- Reformatted `docs/sample_outputs.md` to match the Title/Category/Content layout used in deliveries, hyperlinking publication dates (now M/D format) instead of sources, and added a README pointer to the sample output doc.

### Fixed
- Chrome intake capture now requests iframe origins and reports injection failures, restoring right-click scraping of embedded cross-origin articles.
- Chrome intake manifest now requests the `tabs` permission so background link captures can open/close tabs instead of failing silently.
- Content-deals formatter now detects real date parentheticals instead of any parentheses, so subtitles/alternate-title parentheses still receive the publish date.
- Ingest server CORS setup now disables credentials when origins resolve to `*`, preventing the FastAPI startup crash caused by the wildcard+credentials combination; explicit origins keep credentials enabled.
- CLI `--out` JSON output now serializes dataclass results safely (converts `Path` and other non-JSON types), preventing `TypeError` crashes when writing `.json` files.
- Summarizer requests omit `temperature` when using `gpt-5-mini`, avoiding API 400 errors.
- Multi-article summary parsing now validates a 1:1 article-to-chunk mapping and raises if the model omits sections, preventing silent loss of stories.
- Typer CLI now treats the single-article runner as the default callback (no `run` subcommand needed), so `python -m news_coverage.cli path/to/article.json` matches the documented usage again.
- Chrome intake content script now normalizes `published_at` to `YYYY-MM-DD` (trimming datetime meta tags) to satisfy the ingest schema; README and component guide updated accordingly.
- Chrome intake service worker derives the `quarter` from the article date (falling back to scrape time or current date) instead of hard-coding `2025 Q4`, preventing mis-filed ingest records across quarters.
- Chrome intake service worker now falls back to the scrape date for `published_at` when the page lacks a publish date, preventing ingest 400s for pages with missing metadata.
- Buyer keyword routing now applies word-character lookarounds correctly (e.g., `max` no longer matches `maxwell`), reducing false positives when inferring companies; tests cover the regression.
- Added content-deals routing/formatter to preserve multi-title slate outputs (Dec 11, 2025).
- Chrome intake build script now resolves paths with `fileURLToPath`, fixing the double-drive-letter failure on Windows when running `npm run build`.
