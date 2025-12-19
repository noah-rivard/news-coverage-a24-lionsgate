# Agent Operating Guide (Repo-Wide)

This file tells coding agents how to work in this repository safely and consistently. It exists to reduce mistakes, keep documentation aligned with behavior, and keep updates understandable to non-technical collaborators.

If a subdirectory contains its own `AGENTS.md`, follow that one for any files under that directory (more specific instructions override this file).

## Definition of Done (for code changes)

A change is "done" when:
- The behavior works end-to-end (not just "code compiles").
- Tests and lint are green (see commands below).
- `CHANGELOG.md` is updated (under `## [Unreleased]`) to describe what changed.
- `README.md` is updated if the change affects how someone installs, runs, or uses the repo (commands, flags, files, output locations, API contract, schemas).
- The final response includes a plain-language summary and any decisions needed.

## Quality Checks (run for all code changes)

Run these from the repo root:

```bash
pytest
flake8
```

Exceptions:
- Documentation-only or comment-only changes do not require running `pytest`/`flake8`.

If checks fail:
- Fix the failures as part of the same task if they are caused by your change.
- Do not "fix the world" (avoid unrelated refactors).

## Communication Style (non-technical friendly)

When responding to the user, prefer plain language. Avoid jargon; when you must use a technical term, define it once in simple words.

In your final response, include:
- A brief overview of what changed (what a person can do now that they couldn't before).
- How to verify it (a command to run, or what to click/expect).
- Any risks or limitations.
- Decisions (only if needed), as a numbered list with brief context.

## Safety, Secrets, and Data Handling

- Never print, commit, or paste secrets (API keys, tokens, cookies). Use environment variables (e.g., `OPENAI_API_KEY`) and redact sensitive values in logs/output.
- Treat scraped article text as potentially copyrighted/sensitive. Avoid adding large raw articles to the repo; prefer small fixtures or minimal excerpts needed for tests, and document provenance when relevant.
- Be careful with files under `data/` and any JSONL outputs: avoid duplicating personal data; prefer deterministic fixtures for tests.

## OpenAI API Usage

- Default to the Responses API (not the legacy Completions API).
- Prefer patterns already used in this repo (shared client creation, consistent model configuration, and consistent error handling).
- If changing prompts, schemas, or model usage, also update any docs that describe expected outputs (README and relevant docs under `docs/`).

## ExecPlans (for complex work)

For complex features or significant refactors, use an ExecPlan from design through implementation, following `.agent/PLANS.md`.

Use an ExecPlan when the work is likely to require multiple steps or careful coordination, for example:
- Touches 3+ files in different areas (workflow + server + docs, etc.).
- Changes storage formats, schemas, API contracts, or output templates.
- Introduces a new pipeline step, new CLI command/flag, or new agent/tool behavior.
- Has unclear requirements or needs a prototype to de-risk feasibility.

ExecPlan conventions (see component guide for details):
- Active plans live in `.agent/in_progress/`.
- Completed plans live in `.agent/complete/` (and README/CHANGELOG should reflect the move when it changes how the repo is navigated).

## Component Guides (directory-specific `AGENTS.md`)

Before changing files inside these directories, read the colocated guide first and keep it in sync with behavior changes:
- `.agent/AGENTS.md` (ExecPlans and planning conventions)
- `docs/AGENTS.md` (documentation expectations and schema/API docs)
- `data/AGENTS.md` (fixtures and sample data handling)
- `extensions/chrome-intake/AGENTS.md` (Chrome intake extension)
- `src/AGENTS.md` (Python package-level conventions)
- `src/news_coverage/AGENTS.md` (core workflow, server, schema, tools)

If you touch a major area that lacks an `AGENTS.md`, add one that captures the risks/gotchas you observed so future contributors avoid repeat mistakes.
