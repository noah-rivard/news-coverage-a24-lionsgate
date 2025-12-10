# Agent workflow for entertainment news summarization (Python, OpenAI Agents SDK)

This ExecPlan is a living document. Maintain all sections as work proceeds. Keep it consistent with `.agent/PLANS.md` in this repository.

## Purpose / Big Picture

We want a Python-based agent workflow that ingests entertainment news (Deadline, Variety, Hollywood Reporter), summarizes each article, and outputs a formatted bundle suitable for non-technical readers. After implementation, a contributor can install dependencies, run a CLI command, and receive structured summaries. The plan covers scaffolding the project, wiring the OpenAI Agents SDK, and establishing tests and linting so future improvements are safe.

## Progress

- [x] (2025-12-04 15:00Z) Drafted ExecPlan and identified scaffolding needs.
- [x] (2025-12-04 15:25Z) Created Python package skeleton, config, CLI stub, and component guide.
- [x] (2025-12-04 15:35Z) Added workflow placeholder using Responses API with offline fallback.
- [x] (2025-12-04 15:45Z) Wrote smoke test and configured linting with `.flake8`.
- [x] (2025-12-04 15:50Z) Ran `pytest` (pass) and `flake8` (pass); updated docs and changelog.

## Surprises & Discoveries

- `pip install -e .` intermittently broke stdout on Windows but still installed; re-running with `--progress-bar off` resolved it.

## Decision Log

- Decision: Use Python with `openai-agents` and `openai` Responses API as the core stack.  
  Rationale: Aligns with user request and current OpenAI guidance for agent workflows.  
  Date/Author: 2025-12-04 / Codex

## Outcomes & Retrospective

- Repo scaffolded with `pyproject.toml`, `src/news_coverage/` package, CLI stub, component guide, tests, and lint configuration. Baseline workflow using the Responses API with offline fallback is in place, and `pytest`/`flake8` were green on 2025-12-04. README and CHANGELOG document the initial capabilities. Remaining risk: workflow is intentionally minimal and will evolve once real prompts/models are wired.

## Context and Orientation

Current repository only contains `README.md`, `AGENTS.md`, and `CHANGELOG.md`. No code, tests, or component-level guides exist. We must create a Python package under `src/`, add a CLI entry point, and introduce tests/lint config. Component guides are required for new areas per top-level `AGENTS.md`.

## Plan of Work

1) Create project scaffolding: `pyproject.toml` with project metadata, runtime deps (`openai`, `openai-agents`, `pydantic`, `typer`, `rich`) and dev tools (`pytest`, `flake8`). Add minimal `requirements-dev.txt` if helpful for contributors.
2) Add package `src/news_coverage/` with:
   - `config.py` for settings (OpenAI API key, model choices) using environment variables.
   - `models.py` defining `Article` and `SummaryBundle` Pydantic models.
   - `workflow.py` with functions to build an Agents SDK workflow (placeholder agent that echoes summary steps) and a `summarize_articles` orchestrator.
   - `cli.py` using Typer to accept input file path or stub data and print formatted output.
3) Add component guide `src/AGENTS.md` documenting how to extend the workflow and SDK caveats.
4) Add smoke tests in `tests/` verifying imports, model validation, and that `summarize_articles` returns structured output when the agent call is mocked.
5) Configure linting: `.flake8` or `[tool.flake8]` in `pyproject.toml`; keep styles simple (line length, import rules). Add basic `pytest.ini` under `[tool.pytest.ini_options]`.
6) Update `README.md` with setup, install, and CLI usage; update `CHANGELOG.md` under "Unreleased" with additions.
7) Run `python -m pip install -e .` (or equivalent), then `pytest` and `flake8`, documenting results. If agent calls need network, mock them in tests to keep runs deterministic.

## Concrete Steps

- Working directory: repository root.
- Commands to run (in order):
  - `python -m pip install --upgrade pip`
  - `python -m pip install -e ".[dev]"` (or `pip install -e . && pip install -r requirements-dev.txt` depending on packaging)
  - `pytest`
  - `flake8`
- If adding a CLI demo: `python -m news_coverage.cli sample` (or equivalent Typer command) to print formatted summaries.

## Validation and Acceptance

Acceptance criteria:
- `pytest` passes, confirming models validate and workflow stub returns structured output without hitting the network.
- `flake8` passes with configured rules.
- Running the CLI sample produces a formatted summary bundle in the console with no unhandled exceptions.
- `README.md` reflects setup and usage; `CHANGELOG.md` records the change.

## Idempotence and Recovery

Steps are additive and safe to rerun. Reinstalling with `pip install -e .` is idempotent. If dependency install fails, rerun after fixing network or version pins. Tests are deterministic because agent calls are mocked; failures indicate code regressions rather than external services.

## Artifacts and Notes

- New files: `pyproject.toml`, `src/news_coverage/` modules, `tests/`, `src/AGENTS.md`.
- Command transcripts from test and lint runs should be recorded in commit messages or PR notes as needed.

## Interfaces and Dependencies

- Runtime dependencies: `openai>=1.54.0` for Responses API, `openai-agents>=0.6.1` for Agents SDK, `pydantic>=2.8`, `typer>=0.12`, `rich>=13.7`.
- Dev dependencies: `pytest>=8`, `flake8>=6`.
- Key functions to exist:
  - `news_coverage.models.Article` (Pydantic model)
  - `news_coverage.workflow.build_agent(client)` -> agent instance
  - `news_coverage.workflow.summarize_articles(client, articles)` -> `SummaryBundle`
  - CLI entry point `python -m news_coverage.cli` exposing a `sample` command to run with stub data.
