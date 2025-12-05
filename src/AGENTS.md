# Component Guide: `src/` (Python application code)

Scope: All Python modules under `src/`, including the agent workflow, configuration, and CLI.

Gotchas and expectations:
- Use the OpenAI Responses API (`openai>=1.54.0`) and Agents SDK (`openai-agents>=0.6.1`). Prefer the Responses API over legacy completions.
- Keep agent calls mockable in tests. Expose a helper to inject a client or stub so unit tests never hit the network.
- Centralize configuration (API keys, model names, timeouts) in `config.py` and rely on environment variables rather than hard-coded secrets.
- Favor Pydantic models for external inputs/outputs to keep validation strict and user-facing text consistent.
- Any change to behavior or structure here must be mirrored in this `AGENTS.md` and documented in `README.md` plus `CHANGELOG.md`.
- Run `pytest` and `flake8` after modifications in this area; tests should not require internet access.
