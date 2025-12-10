# Component Guide: `docs/`

Scope: Reference and template docs that accompany the agent workflow, ingest service, and SDK usage.

Gotchas and expectations:
- Keep docs concise and link to authoritative sources instead of copying large sections (avoids confusing Codex and reduces drift).
- When SDK versions change, update both `docs/agents_sdk_quickref.md` and the version notes in `README.md` and `CHANGELOG.md`.
- If a doc describes behavior (e.g., API contract, workflow steps), ensure the corresponding code and tests reflect it.
- Use ASCII and short sections so non-technical collaborators can skim.
- Documentation-only edits do not require running `pytest` or `flake8`; code changes still do.
- The DOCX generator for multi-buyer coverage is documented in README; keep this file aligned when CLI flags or output locations change.
