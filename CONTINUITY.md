# CONTINUITY.md

## Goal (incl. success criteria):
- Disable OpenAI Agents SDK tracing export by default so local runs don’t spam `[non-fatal] Tracing: server error 503` retries.

## Constraints/Assumptions:
- Environment: Windows PowerShell; approval_policy=never; sandbox_mode=danger-full-access; network_access=enabled.
- Run `pytest` and `flake8` from repo root for code changes.
- Treat captured article text as potentially copyrighted; avoid adding large real-article fixtures.
- Do not print secrets; `.env` contains an OpenAI key.

## Key decisions:
- Agents SDK trace export is disabled by default at package import; users can re-enable by setting `OPENAI_AGENTS_DISABLE_TRACING=false` before running.

## State:
- Implemented and verified: tests/lint green.

## Done:
- Set `OPENAI_AGENTS_DISABLE_TRACING=true` by default inside `src/news_coverage/__init__.py`.
- Updated `README.md` and `CHANGELOG.md`.
- Ran `pytest` and `flake8` (green).

## Now:
- Restart server/CLI and confirm 503 tracing spam is gone.

## Next:
- (Optional) Add a dedicated CLI flag to toggle tracing on/off per run.

## Open questions (UNCONFIRMED if needed):
- UNCONFIRMED: Are article POSTs actually reaching the server? (Prior logs showed only `OPTIONS /process/articles` preflights, no `POST` yet.)

## Working set (files/ids/commands):
- `src/news_coverage/__init__.py`
- `README.md`
- `CHANGELOG.md`
- `pytest`
- `flake8`
