# Changelog

All notable changes to this project will be documented in this file. This project adheres to [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Chrome intake extension now exposes a right-click context menu for pages and embedded frames so users can trigger a scrape on the clicked frame; manifest includes the `contextMenus` permission to support it.
- FastAPI `/process/articles` endpoint to process multiple articles in one request with per-item status and optional concurrency controls.
- Component guide for the planning area (`.agent/AGENTS.md`) plus a `complete/` folder for finished ExecPlans.
- Manager agent path implemented with the OpenAI Agents SDK (`agent_runner.py`) plus CLI mode flag (`--mode agent|direct`) defaulting to the agent path.
- Batch CLI command to process multiple articles in parallel (`news_coverage.cli batch`) with per-article outputs and configurable concurrency.
- Optional agent trace logging via `AGENT_TRACE_PATH`, which appends raw article content, tool calls, outputs, and final markdown for manager-agent runs.
- CLI `--trace`/`--trace-path` support plus `docs/traces/` placeholder for on-demand agent trace logs.
- Multi-buyer DOCX generation pipeline: buyer keyword routing (`buyer_routing.py`), coverage/DOCX builders, and CLI command `build-docx` to produce Q4 2025 News Coverage files per buyer plus `needs_review.txt`.
- Dependency on `python-docx` to render coverage reports styled after the WBD Q2 template.
- Chrome MV3 extension scaffold under `extensions/chrome-intake/` with content script (Readability-based scrape), service worker, popup, options page, esbuild bundling, and component AGENTS guide.
- README now documents how to build/load the extension and run the ingest server for it.
- ROADMAP outlining the agent-as-tool workflow decisions, sequential processing, and future reviewer agent.
- ExecPlan for building the Python OpenAI Agents workflow (`.agent/in_progress/execplan-news-agent.md`).
- Project scaffolding with `pyproject.toml`, package source under `src/news_coverage/`, and component guide `src/AGENTS.md`.
- Coordinator pipeline (`news_coverage.workflow.process_article`) that classifies (fine-tuned model), summarizes, formats Markdown, and ingests to JSONL.
- CLI now supports single-article runs with optional file output.
- Unit tests for the coordinator pipeline; pytest/flake8 kept green.
- Expanded subheading normalization (Analyst Perspective, IR Conferences, Misc. News) to align classifier output with schema.
- Pipeline now appends each successful article to `docs/templates/final_output.md` (override with `FINAL_OUTPUT_PATH`) using the matched-buyers format.
- Backfilled existing ingested articles into `docs/templates/final_output.md` so the log starts with prior runs.
- Final-output content lines now ensure dates are hyperlinked to the article URL (appended dates and any existing `(M/D)` date parentheticals within content).
- ExecPlan for the Chrome intake extension and ingest service design (`.agent/in_progress/execplan-chrome-extension.md`), including taxonomy findings from the sample news coverage DOCX files.
- Canonical coverage payload schema and guide (`docs/templates/coverage_schema.json` and `docs/templates/coverage_schema.md`) for the Chrome extension and backend ingest.
- Ingest API contract draft (`docs/templates/ingest_api_contract.md`) specifying endpoints, validation, errors, and storage rules aligned to the coverage schema.
- Python schema loader/validator (`news_coverage.schema`) backed by `jsonschema`, plus tests for valid/invalid payloads.
- FastAPI ingest service (`news_coverage.server`) with `/health` and `/ingest/article` endpoints using the schema validator and JSONL storage; tests cover happy paths.
- FastAPI `/process/article` endpoint that runs the manager-agent pipeline (classify → summarize → format → ingest) and returns Markdown plus storage metadata for a single scraped article.
- Agents SDK quick reference (`docs/agents_sdk_quickref.md`) summarizing how this repo should use the OpenAI Agents SDK.
- Docs component guide (`docs/AGENTS.md`) to keep documentation updates concise and aligned with code behavior.
- Component guide for the core workflow/services (`src/news_coverage/AGENTS.md`) noting how injected tools can run offline.
- Debug fixture set of three Variety articles under `data/samples/debug/` plus a `data/AGENTS.md` guide for managing fixtures.
- Sample output markdown for the three debug fixtures (`docs/sample_outputs.md`) generated with the latest pipeline defaults.
- Final output Markdown template with buyer list and ISO timestamp layout (`docs/templates/final_output.md`) and README link.

### Changed
- ExecPlan housekeeping: moved auto-process endpoint, Feedly minimal-permission capture flow, and slate-routing ExecPlans to `.agent/complete/`; README now lists active vs. completed plans.
- ExecPlan housekeeping: archived `execplan-batch-process-endpoint.md` to `.agent/complete/` after adding the batch processing endpoint.
- Chrome intake extension now defaults to `/process/articles` and batches queued captures when using the batch endpoint; single-article endpoints still work via sequential sends.
- ExecPlan housekeeping: archived `execplan-summarizer-retry.md` to `.agent/complete/` and updated README pointers.
- Chrome intake extension now requests only Feedly hosts at install; other origins are requested at click time. Content script is no longer auto-injected and link captures run in a background tab with a 20s timeout.
- Popup surfaces capture failures (e.g., permission denied) and guides users to right-click capture when no article is cached.
- Final-output "Matched buyers" display now uses strong matches (title/lead/URL host) plus the primary company, excluding body-only mentions from that list.
- Company inference now routes across all major buyers (Amazon, Apple, Comcast/NBCU, Disney, Netflix, Paramount, Sony, WBD, A24, Lionsgate) instead of only A24/Lionsgate; schema/docs/ingest contract updated to reflect the expanded enum.
- Paramount keyword order now prioritizes `cbs`/network brands before generic `paramount` terms so title hits (e.g., "... at CBS") register as strong matches instead of being overridden by weaker body-only matches.
- Removed duplicate detection across ingest and processing; repeated URLs always append and skip-duplicate flags/query params were removed.
- ExecPlan housekeeping: archived `execplan-remove-duplicate-skips.md` to `.agent/complete/`.
- README cleanup: clarified Chrome extension steps, fixed output format bullet, and pointed ExecPlan references to `.agent/complete/`.
- Chrome intake extension now auto-sends each captured article to the configured endpoint (default `/process/article`) and reports status in the popup; options default updated accordingly while keeping `/ingest/article` compatibility.
- Rewrote top-level `AGENTS.md` to clarify definition of done, quality checks, safety/data handling expectations, ExecPlan triggers, and component-guide index.
- README now documents the coordinator workflow, single-article CLI usage, and the fact that injected tools can run without an API key.
- README documents the DOCX generator and how to invoke it.
- CLI defaults to the manager agent path; `--mode direct` retains the legacy direct pipeline.
- JSONL ingest, final-output, and agent-trace appends now use process-local file locks to prevent interleaved writes during concurrent runs.
- Clarified CLI invocation uses a single command (no `run` subcommand) in README examples.
- Summarizer no longer sets a default max-output token cap; `MAX_TOKENS` is now optional (unset or 0 removes the cap, positive values enforce one). README and component guides note the new behavior.
- Prompt routing now treats missing classifier confidence as sufficiently confident, so specialized prompts (e.g., content formatter) are used unless a low confidence score is explicitly returned.
- Clarified in the Agents SDK quick reference that runs are stateless and handled one article at a time.
- `process_article` only constructs an OpenAI client when default tools are used; injected classifier/summarizer pairs (or a provided client) no longer require `OPENAI_API_KEY`, enabling offline tests. README and component guides now reflect this behavior.
- Prompt templates relocated under `src/prompts/` to align with `workflow.PROMPTS_DIR`.
- README includes a quick-start note on the debug fixture files for repeatable testing.
- Debug fixture content now uses the full Dec 5, 2025 Variety article bodies so local runs reflect real-world ingest text; README and `data/AGENTS.md` note the change and its internal-only intent.
- Coordinator prompt/formatter routing is now a declarative table with a confidence floor fallback to `general_news.txt`; batch summarization accepts one prompt per article while preserving 1:1 chunk validation. README and component guides capture the new behavior.
- Markdown formatter now emits delivery-ready `Title` / `Category` / `Content` lines and appends the article date (M/D) as the hyperlink to the source URL; docs and sample outputs reflect the format.
- Reformatted `docs/sample_outputs.md` to match the Title/Category/Content layout used in deliveries, hyperlinking publication dates (now M/D format) instead of sources, and added a README pointer to the sample output doc.

### Fixed
- Summarizer/classifier now raise on incomplete Responses API outputs instead of stringifying the full response into coverage bullets when `max_output_tokens` is hit.
- Summarizer now retries with a truncated article body when `max_output_tokens` is hit, reducing failures on long articles before raising.
- Coordinator ingest now synthesizes a fallback fact (from takeaway/bullets/headline) when the summarizer returns no facts, preventing schema validation crashes that previously aborted `/process/article` ingestion.
- Final-output log now uses the same fallback fact when a summary is empty, so headline-only articles still include a Category/Content block instead of being silently dropped.
- `/process/article` now correctly parses RFC3339 timestamps with `Z` (and `+0000`-style offsets) for `published_at`, and rejects invalid timestamps with a 400 instead of silently treating them as missing.
- Ingest now de-duplicates by URL per company/quarter, returning `duplicate_of` and skipping final-output appends instead of writing duplicate records.
- Category display now preserves the combined top-level bucket (`Content, Deals, Distribution`) instead of splitting it into separate arrows, preventing mis-ordered paths like `Content -> Deals -> Distribution -> Sports -> …` in final outputs.
- Chrome intake capture now requests iframe origins and reports injection failures, restoring right-click scraping of embedded cross-origin articles.
- Chrome intake link-capture now reports background-tab timeouts (and uses a longer timeout), avoiding silent no-op runs when a site takes too long to load.
- Chrome intake manifest now requests the `tabs` permission so background link captures can open/close tabs instead of failing silently.
- Final-output log now renders every bullet in each fact’s `summary_bullets` (adding date links when missing) instead of only `content_line`, so multi-title facts aren’t truncated.
- Final-output log now formats each fact’s Content as a bullet list (instead of repeating `Content:` lines), preventing downstream parsers from dropping bullets when a fact contains multiple lines.
- Markdown formatter now renders every bullet in each fact’s `summary_bullets` and only adds the date link when missing, preventing multi-title facts from collapsing and avoiding duplicate date parentheses.
- Backfilled the HGTV multi-show entry in `docs/templates/final_output.md` so all three titles are visible.
- Final-output appender now keeps consistent spacing between entries (exactly one blank line), improving readability.
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
- Company inference now scores title/lead matches to avoid misfiling when multiple buyers appear in an article.
- Added a lightweight company-inference fixture under `tests/fixtures/` so `test_infer_company_prefers_title_subject_over_lead_mentions` runs without relying on temp files.
- Article text normalization now cleans common mojibake sequences before summarization/formatting and notes normalization in agent traces.
- Exec-change summaries now preserve "former" qualifiers when the article text explicitly uses them.
### Added
- Multi-fact pipeline: single articles now produce multiple fact entries (with their own category/subheading/company/quarter) inside one record; markdown/final_output blocks list multiple Category/Content pairs in model order; DOCX builder places facts into the correct subheadings without repeating the article header.
- Coverage schema now requires a `facts` array (min 1) and documents per-fact fields; legacy single-category summary fields are deprecated.
### Fixed
- Ingest server now accepts legacy single-category `/ingest/article` payloads (top-level `section/subheading`), synthesizing a single `facts[0]` entry so older clients don’t start failing with 400s after the schema change.
