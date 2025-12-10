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
python -m news_coverage.cli path/to/article.json
```

Add `--out output.json` to write both the structured run output and ingest metadata as JSON (file-system paths are rendered as strings for portability). If omitted, Markdown is printed to stdout.

The CLI defaults to the manager agent path (OpenAI Agents SDK). Keep the legacy direct pipeline with `--mode direct`. Examples:

```
python -m news_coverage.cli data/samples/debug/variety_mandy_moore_teach_me.json --mode agent
python -m news_coverage.cli data/samples/debug/variety_mandy_moore_teach_me.json --mode direct
```

Both modes require `OPENAI_API_KEY` unless you inject your own classifier/summarizer. The agent path always needs the key because it builds the manager model.

By default summaries can use up to 1,200 tokens; set the environment variable `MAX_TOKENS` if you need to raise or lower that limit when articles are especially long.

### Generate DOCX coverage reports (multi-buyer)

### Run the ingest server for the Chrome extension

Start the FastAPI service locally (defaults to port 8000 and CORS enabled for all origins):

`
python -m news_coverage.server
# or
uvicorn news_coverage.server:app --host 0.0.0.0 --port 8000
`

Health check:

`
curl http://localhost:8000/health
`

Ingest an article (matches the coverage schema):

`
curl -X POST http://localhost:8000/ingest/article ^
  -H "Content-Type: application/json" ^
  -d "{"company":"A24","quarter":"2025 Q4","section":"Content / Deals / Distribution","subheading":"Development","title":"Example","source":"Variety","url":"https://example.com","published_at":"2025-12-01"}"
`

Environment knobs:
- INGEST_DATA_DIR to change storage root.
- INGEST_HOST / INGEST_PORT / INGEST_RELOAD for server startup.
- CORS_ALLOW_ALL (default true) or CORS_ALLOW_ORIGINS (comma-separated) to constrain extension access.


Run the new helper to produce Q4 2025 News Coverage DOCX files for each buyer plus a single `needs_review.txt`:

```
python -m news_coverage.cli build-docx data/my_articles --quarter "2025 Q4"
```

Provide one or more JSON article files (or a directory of them). Articles missing `published_at` or with only weak keyword matches are logged to `needs_review.txt`. Highlights are left for manual editing in the DOCX.

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

- Reuse the three sample Variety articles in `data/samples/debug/` when you need a quick, repeatable input. Each file now contains the full article body text from Dec. 5, 2025 Variety stories so runs mirror real ingest conditions. Each file is a single JSON object so it works directly with the CLI. Example:

```
python -m news_coverage.cli data/samples/debug/variety_wga_netflix_warner_merger.json --out scratch.md
```

- The set covers the Netflix-Warner Bros. merger story, an A24/Peacock series announcement, and a column on what a Netflix-owned Warner Bros. would mean for theaters.
- Duplicate checks are automatically skipped for files under `data/samples/debug/` so you can rerun them without 409-style messages.

## Output Format

Markdown output is delivery-ready and follows three lines:
- `Title: <headline>`
- `Category: <classifier path with arrows>`
- `Content: <leading summary sentence> ([M/D](article_url))` — the date (month/day) is the hyperlink to the article.

## Workflow Pattern (current decision)

- One coordinator (manager model) stays in control and calls specialist helpers as tools: classify (fine-tuned), summarize, format (Markdown), ingest (schema + JSONL storage).
- Each run handles a single article end-to-end (stateless); default tools need an API key, but you can inject classifier/summarizer implementations (or a prepared `OpenAI` client) to run offline for tests.
- Duplicate URLs return a 409-style message and do not write a new record.
- Prompt routing now uses a declarative table (category substrings -> prompt + formatter). If classifier confidence is below `ROUTING_CONFIDENCE_FLOOR` (default 0.5), the coordinator defaults to `general_news.txt` to avoid misrouting.
- Batch summarization helper (`summarize_articles_batch`) accepts one prompt per article and still fails fast if the model response does not include one summary per article, so no stories disappear silently.
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
- Debug fixture sample outputs (Title/Category/Content format): `docs/sample_outputs.md`.

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
