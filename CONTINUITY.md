# CONTINUITY.md

## Goal (incl. success criteria):
- Fix Chrome intake extension so sending from Feedly only ingests the user-selected article (no previously-captured/previously-processed articles are resent).

## Constraints/Assumptions:
- Environment: Windows PowerShell; approval_policy=never; sandbox_mode=danger-full-access; network_access=enabled.
- Run `pytest` and `flake8` from repo root for code changes.
- Treat captured article text as potentially copyrighted; avoid adding large real-article fixtures.

## Key decisions:
- “Send” and auto-send operate on the selected/latest article only (no flushing previously queued items).

## State:
- Fix implemented; docs updated; Python tests/lint passing.

## Done:
- Updated Chrome intake extension to only send selected/latest article.
- Updated `README.md` and `CHANGELOG.md`.
- Rebuilt extension `dist/` via `npm run build`.
- Ran `pytest` and `flake8` (both green).

## Now:
- Ready for manual verification in Chrome with the unpacked extension.

## Next:
- Manually verify: capture a Feedly link and confirm only that article posts to the backend.

## Open questions (UNCONFIRMED if needed):
- None.

## Working set (files/ids/commands):
- `extensions/chrome-intake/`
- `src/news_coverage/server.py`
- `extensions/chrome-intake/src/background.ts`
- `README.md`
- `CHANGELOG.md`
