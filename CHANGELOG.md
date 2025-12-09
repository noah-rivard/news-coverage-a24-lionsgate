# Changelog

All notable changes to this project will be documented in this file. This project adheres to [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- ROADMAP outlining the agent-as-tool workflow decisions, sequential processing, and future reviewer agent.
- ExecPlan for building the Python OpenAI Agents workflow (`.agent/in_progress/execplan-news-agent.md`).
- Project scaffolding with `pyproject.toml`, package source under `src/news_coverage/`, and component guide `src/AGENTS.md`.
- Coordinator pipeline (`news_coverage.workflow.process_article`) that classifies (fine-tuned model), summarizes, formats Markdown, and ingests to JSONL.
- CLI now supports single-article runs with optional file output and surfaces duplicate (409-style) responses.
- Unit tests for the coordinator pipeline; pytest/flake8 kept green.
- Expanded subheading normalization (Analyst Perspective, IR Conferences, Misc. News) to align classifier output with schema.
- ExecPlan for the Chrome intake extension and ingest service design (`.agent/in_progress/execplan-chrome-extension.md`), including taxonomy findings from the sample news coverage DOCX files.
- Canonical coverage payload schema and guide (`docs/templates/coverage_schema.json` and `docs/templates/coverage_schema.md`) for the Chrome extension and backend ingest.
- Ingest API contract draft (`docs/templates/ingest_api_contract.md`) specifying endpoints, validation, errors, and storage rules aligned to the coverage schema.
- Python schema loader/validator (`news_coverage.schema`) backed by `jsonschema`, plus tests for valid/invalid payloads.
- FastAPI ingest service (`news_coverage.server`) with `/health` and `/ingest/article` endpoints using the schema validator, duplicate detection, and JSONL storage; tests cover happy path and duplicate rejection.
- Agents SDK quick reference (`docs/agents_sdk_quickref.md`) summarizing how this repo should use the OpenAI Agents SDK.
- Docs component guide (`docs/AGENTS.md`) to keep documentation updates concise and aligned with code behavior.
- Component guide for the core workflow/services (`src/news_coverage/AGENTS.md`) noting how injected tools can run offline.
- Debug fixture set of three Variety articles under `data/samples/debug/` plus a `data/AGENTS.md` guide for managing fixtures.
- Sample output markdown for the three debug fixtures (`docs/sample_outputs.md`) generated with the latest pipeline defaults.

### Changed
- README now documents the coordinator workflow, single-article CLI usage, duplicate handling, and the fact that injected tools can run without an API key.
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
- CLI `--out` JSON output now serializes dataclass results safely (converts `Path` and other non-JSON types), preventing `TypeError` crashes when writing `.json` files.
- Summarizer requests omit `temperature` when using `gpt-5-mini`, avoiding API 400 errors.
- Multi-article summary parsing now validates a 1:1 article-to-chunk mapping and raises if the model omits sections, preventing silent loss of stories.
