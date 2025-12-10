# Manager Agent Orchestration via OpenAI Agents SDK (single-article runs)

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds. Follow `.agent/PLANS.md`.

## Purpose / Big Picture

Enable a manager agent (OpenAI Agents SDK) to orchestrate the existing classify + summarize + format + ingest tools for one article. After this change, a user can run the CLI in agent mode and see the manager call the tools in order, producing the same Markdown plus JSONL ingest as today. This demonstrates the intended architecture and de-risks future multi-tool behaviors.

## Progress

- [x] (2025-12-09 20:15Z) Drafted ExecPlan and captured current state.
- [x] (2025-12-09 21:05Z) Implemented `src/news_coverage/agent_runner.py` with Agents SDK manager + tools (classify, summarize, format, ingest) sharing a pipeline context.
- [x] (2025-12-09 21:18Z) Added CLI mode flag (`--mode agent|direct`, default agent) delegating to the new agent runner while keeping the direct pipeline and debug fixture duplicate skip.
- [x] (2025-12-09 21:35Z) Added offline tests (`tests/test_agent_runner.py`) using a fake Runner to validate agent wiring, tool count, and `skip_duplicate` handling.
- [x] (2025-12-09 21:50Z) Updated README, component AGENTS guides, and CHANGELOG for the new agent mode/default and CLI flag.
- [x] (2025-12-09 21:58Z) Ran `pytest` (21 passed) and `flake8` (clean after minor test tidy).

## Surprises & Discoveries

- None encountered; agent tools and Runner stubbing behaved as expected.

## Decision Log

- Decision: Keep existing direct pipeline and add an agent-driven path selected via CLI flag, defaulting to agent mode. Rationale: reduces regression risk while demonstrating the requested Agents SDK wiring; allows offline tests to continue using direct stubs. Date/Author: 2025-12-09 / Codex.
- Decision: Implement agent and tools in a new module (`src/news_coverage/agent_runner.py`) to avoid entangling the current workflow helpers and to make tests target the agent boundary. Date/Author: 2025-12-09 / Codex.

## Outcomes & Retrospective

- Manager agent path exists and is the CLI default, with a direct fallback. Offline tests cover tool wiring and duplicate-skip behavior; the full suite remained green. Docs and CHANGELOG landed alongside the code, and smoke runs showed no regressions.

## Context and Orientation

Current flow (`src/news_coverage/workflow.py`) calls the OpenAI Responses API directly for classify/summarize, formats Markdown, and ingests to JSONL. CLI (`src/news_coverage/cli.py`) runs one article with optional `--out` and skips duplicate checks for debug fixtures. No manager agent exists despite the `openai-agents` dependency. Tests live in `tests/`, relying on stubs (no network). Component guides in `AGENTS.md`, `src/AGENTS.md`, and `src/news_coverage/AGENTS.md` require updates when behavior changes. ROADMAP calls for an agent-managed workflow.

## Plan of Work

Describe edits concretely:

1) Create `src/news_coverage/agent_runner.py` implementing:
   - Tool wrappers for classify, summarize, format, ingest reusing `workflow.py` logic where practical.
   - An `AgentRunner` helper that builds a manager agent with these tools, runs it once per article, and returns a `PipelineResult`-equivalent.
   - Clear API key requirement and ability to inject a prepared `OpenAI` client for tests.
2) Update `src/news_coverage/cli.py` to accept `--mode {agent,direct}` (default `agent`), selecting either the new agent runner or existing `process_article`; preserve debug fixture duplicate skip.
3) Extend tests:
   - New tests for agent runner using stubbed Agents SDK objects to assert tool call order, prompt routing, and ingest behavior without network.
   - Keep direct-path tests untouched; add any minimal refactors required for reuse.
4) Documentation:
   - README: explain modes, API key expectations, and how to run agent path.
   - Component guides (`src/AGENTS.md`, `src/news_coverage/AGENTS.md`) to describe the agent module and tool interfaces.
   - CHANGELOG: summarize additions/changes.
5) Validation: run `pytest` and `flake8`; capture results in `Progress` and `Outcomes`.

## Concrete Steps

- Worktree: repo root.
- Implement `agent_runner.py` with manager and tool definitions.
- Modify `cli.py` for mode selection.
- Add/adjust tests in `tests/` (likely `test_agent_runner.py` new file plus CLI coverage).
- Update docs and CHANGELOG.
- Run `pytest` then `flake8`.
- Update this plan's `Progress`, `Decision Log`, `Surprises`, and `Outcomes` after each milestone.

## Validation and Acceptance

Acceptance behaviors:
- Command: `python -m news_coverage.cli run data/samples/debug/variety_mandy_moore_teach_me.json --mode agent` stores ingest JSONL, prints Markdown, and logs no errors.
- Command with `--mode direct` behaves exactly as current pipeline.
- Tests: `pytest` passes with new agent tests; `flake8` clean.
- Agent path works offline in tests via stubs (no network dependency).

## Idempotence and Recovery

Agent runs are stateless per article. CLI flag defaults to agent but direct mode remains available. Storage is append-only JSONL; reruns may create duplicates unless `skip_duplicate` is triggered for debug fixtures. No migrations; safe to rerun tests and CLI.

## Artifacts and Notes

- Capture representative CLI output and test summaries in this section after implementation.

## Interfaces and Dependencies

- New module `src/news_coverage/agent_runner.py` should expose a function like `run_with_agent(article: Article, client: Optional[OpenAI] = None, skip_duplicate: bool = False) -> PipelineResult`.
- Tools should be constructed using OpenAI Agents SDK (`openai-agents>=0.6.1`). Manager model default remains `gpt-5.1`; summarizer/classifier models align with `config.py`.
- CLI imports `run_with_agent` and `process_article`; chooses based on `--mode`.
