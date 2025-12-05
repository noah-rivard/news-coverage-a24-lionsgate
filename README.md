# news-coverage-a24-lionsgate

Python workflow for summarizing and formatting entertainment news articles (Deadline, Variety, Hollywood Reporter) using the OpenAI Agents SDK and Responses API.

## Getting Started

1) Install Python 3.10+. Set `OPENAI_API_KEY` when using the default classifier/summarizer; you can omit it when injecting your own tools or a preconfigured client (e.g., during tests).  
2) Install dependencies (editable mode for local development):

```
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

3) Run the CLI with a single-article JSON payload:

```
python -m news_coverage.cli run path/to/article.json
```

Add `--out output.json` to write both the structured run output and ingest metadata as JSON (file-system paths are rendered as strings for portability). If omitted, Markdown is printed to stdout.

Payload format: one JSON object (not a list) with `title`, `source`, `url`, `content`, and optional `published_at` (ISO datetime). Example:

```
{
  "title": "Example headline",
  "source": "SampleWire",
  "url": "https://example.com/story",
 "content": "Full text of the article...",
  "published_at": "2025-01-15T00:00:00Z"
}
```

## Debug Fixtures

- Reuse the three sample Variety articles in `data/samples/debug/` when you need a quick, repeatable input. Each file is a single JSON object so it works directly with the CLI. Example:

```
python -m news_coverage.cli run data/samples/debug/variety_wga_netflix_warner_merger.json --out scratch.md
```

- The set covers the Netflix-Warner Bros. merger story, an A24/Peacock series announcement, and a column on what a Netflix-owned Warner Bros. would mean for theaters.
- Duplicate checks are automatically skipped for files under `data/samples/debug/` so you can rerun them without 409-style messages.

## Workflow Pattern (current decision)

- One coordinator (manager model) stays in control and calls specialist helpers as tools: classify (fine-tuned), summarize, format (Markdown), ingest (schema + JSONL storage).
- Each run handles a single article end-to-end (stateless); default tools need an API key, but you can inject classifier/summarizer implementations (or a prepared `OpenAI` client) to run offline for tests.
- Duplicate URLs return a 409-style message and do not write a new record.
- Batch summarization helper (summarize_articles_batch) fails fast if the model response does not include one summary per article, so no stories disappear silently.
- A reviewer/quality-check agent is planned later to flag tone or accuracy issues (see `ROADMAP.md`).

## Project Structure

- `src/news_coverage/`: application code (`config.py`, `models.py`, coordinator `workflow.py`, `cli.py`)
- `src/prompts/`: prompt templates used by the summarizer/classifier
- `tests/`: smoke tests that mock network calls
- `.agent/`: ExecPlans and design guidance
- `src/AGENTS.md`: component-specific gotchas for the Python code
- `src/news_coverage/schema.py`: loader/validator for the coverage JSON schema used by ingest.
- `src/news_coverage/server.py`: FastAPI ingest service exposing `/health` and `/ingest/article` for the Chrome extension.
- `docs/templates/coverage_schema.json` and `docs/templates/coverage_schema.md`: canonical payload schema and human-readable guide for the Chrome intake extension and backend ingest.
- `docs/templates/ingest_api_contract.md`: endpoint contract for the ingest service that the Chrome extension will call.

## Documentation

- Agents SDK quick reference: `docs/agents_sdk_quickref.md` (links to the authoritative OpenAI docs and notes the patterns we use here).
- Docs guidelines for contributors: `docs/AGENTS.md`.

## Contributing Guidelines for Agents

Review `AGENTS.md` before making changes. Key points:
- Run `pytest` and `flake8` after code changes.
- Update component `AGENTS.md` files when behavior changes.
- Use ExecPlans for complex work per `.agent/PLANS.md`; place them under `.agent/in_progress/` or `.agent/completed/` as appropriate.

## Roadmap

- See `ROADMAP.md` for the full list. Highlights:
  - Replace the offline fallback with a full Agents workflow call and structured parsing.
  - Add richer formatting options (Markdown/HTML) for downstream consumption.
  - Later: add a reviewer/LLM quality-check step after formatting.
