# news-coverage-a24-lionsgate

Python workflow for summarizing and formatting entertainment news articles (Deadline, Variety, Hollywood Reporter) using the OpenAI Agents SDK and Responses API.

## Getting Started

1) Install Python 3.10+ and ensure `OPENAI_API_KEY` is set in your environment (optional for offline demo).
2) Install dependencies (editable mode for local development):

```
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

3) Run the sample CLI (uses offline fallback if no API key is set):

```
python -m news_coverage.cli run
```

To summarize your own articles, provide a JSON file containing a list of article objects with `title`, `source`, `url`, `content`, and optional `published_at` fields:

```
python -m news_coverage.cli run path/to/articles.json
```

## Project Structure

- `src/news_coverage/` – application code (`config.py`, `models.py`, `workflow.py`, `cli.py`)
- `tests/` – smoke tests that mock network calls
- `.agent/` – ExecPlans and design guidance
- `src/AGENTS.md` – component-specific gotchas for the Python code
- `src/news_coverage/schema.py` – loader/validator for the coverage JSON schema used by ingest.
- `src/news_coverage/server.py` – FastAPI ingest service exposing `/health` and `/ingest/article` for the Chrome extension.
- `docs/templates/coverage_schema.json` and `docs/templates/coverage_schema.md` – canonical payload schema and human-readable guide for the Chrome intake extension and backend ingest.
- `docs/templates/ingest_api_contract.md` – endpoint contract for the ingest service that the Chrome extension will call.

## Contributing Guidelines for Agents

Review `AGENTS.md` before making changes. Key points:
- Run `pytest` and `flake8` after code changes.
- Update component `AGENTS.md` files when behavior changes.
- Use ExecPlans for complex work per `.agent/PLANS.md`; place them under `.agent/in_progress/` or `.agent/completed/` as appropriate.

## Roadmap

- Replace the offline fallback with a full Agents workflow call and structured parsing.
- Add richer formatting options (Markdown/HTML) for downstream consumption.
