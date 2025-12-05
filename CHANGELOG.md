# Changelog

All notable changes to this project will be documented in this file. This project adheres to [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- ExecPlan for building the Python OpenAI Agents workflow (`.agent/in_progress/execplan-news-agent.md`).
- Project scaffolding with `pyproject.toml`, package source under `src/news_coverage/`, and component guide `src/AGENTS.md`.
- CLI stub (`news_coverage.cli`) with offline fallback and sample run command.
- Basic models, workflow skeleton, and smoke test for offline summary behavior.
- ExecPlan for the Chrome intake extension and ingest service design (`.agent/in_progress/execplan-chrome-extension.md`), including taxonomy findings from the sample news coverage DOCX files.
- Canonical coverage payload schema and guide (`docs/templates/coverage_schema.json` and `docs/templates/coverage_schema.md`) for the Chrome extension and backend ingest.
- Ingest API contract draft (`docs/templates/ingest_api_contract.md`) specifying endpoints, validation, errors, and storage rules aligned to the coverage schema.
- Python schema loader/validator (`news_coverage.schema`) backed by `jsonschema`, plus tests for valid/invalid payloads.
- FastAPI ingest service (`news_coverage.server`) with `/health` and `/ingest/article` endpoints using the schema validator, duplicate detection, and JSONL storage; tests cover happy path and duplicate rejection.
