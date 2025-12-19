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

Add `--out output.json` to write both the structured run output and ingest metadata as JSON (file-system paths are rendered as strings for portability). If omitted, Markdown is printed to stdout. Use `--trace` to append an agent trace log for that run under `docs/traces/` (includes raw article content).

The CLI defaults to the manager agent path (OpenAI Agents SDK). Keep the legacy direct pipeline with `--mode direct`. Examples:

```
python -m news_coverage.cli data/samples/debug/variety_mandy_moore_teach_me.json --mode agent
python -m news_coverage.cli data/samples/debug/variety_mandy_moore_teach_me.json --mode direct
```

Both modes require `OPENAI_API_KEY` unless you inject your own classifier/summarizer. The agent path always needs the key because it builds the manager model.

By default summaries can use up to 1,200 tokens; set the environment variable `MAX_TOKENS` if you need to raise or lower that limit when articles are especially long. If the model hits `max_output_tokens`, the run now errors so you can increase the limit instead of logging a raw response blob.

If you need to re-run an article that was already ingested (same URL), use either:
- `--skip-duplicate-for-url "<exact url>"` (recommended; only bypasses when the payload URL matches)
- `--skip-duplicate` (bypasses duplicate detection for the whole run)

To process multiple articles in parallel (each article remains a separate run), use the batch command:

```
python -m news_coverage.cli batch data/my_articles --concurrency 4 --outdir outputs
```

`--outdir` writes one file per article (named with a numeric prefix plus the input filename). Set `--format json` to write structured JSON outputs instead of Markdown.

Run the new helper to produce Q4 2025 News Coverage DOCX files for each buyer plus a single `needs_review.txt`:

```
python -m news_coverage.cli build-docx data/my_articles --quarter "2025 Q4"
```

Provide one or more JSON article files (or a directory of them). Articles missing `published_at` or with only weak keyword matches are logged to `needs_review.txt`. Highlights are left for manual editing in the DOCX.

### Run the ingest server for the Chrome extension

Start the FastAPI service locally (defaults to port 8000 and CORS open to all origins; credentials are disabled for the wildcard case to keep FastAPI happy):

```
python -m news_coverage.server
# or
uvicorn news_coverage.server:app --host 0.0.0.0 --port 8000
```

Health check:

```
curl http://localhost:8000/health
```

Ingest an article (matches the coverage schema):

```
curl -X POST http://localhost:8000/ingest/article ^
  -H "Content-Type: application/json" ^
  -d "{\"company\":\"A24\",\"quarter\":\"2025 Q4\",\"title\":\"Example\",\"source\":\"Variety\",\"url\":\"https://example.com\",\"published_at\":\"2025-12-01\",\"facts\":[{\"fact_id\":\"fact-1\",\"category_path\":\"Strategy & Miscellaneous News -> General News & Strategy\",\"section\":\"Strategy & Miscellaneous News\",\"subheading\":\"General News & Strategy\",\"content_line\":\"Example\",\"summary_bullets\":[\"Example\"]}]}"
```

Process an article through the full pipeline (classify → summarize → format → ingest) via the new endpoint:

```
curl -X POST http://localhost:8000/process/article ^
  -H "Content-Type: application/json" ^
  -d "{\"title\":\"Example\",\"source\":\"Variety\",\"url\":\"https://example.com\",\"content\":\"Full text of the article...\",\"published_at\":\"2025-12-01\"}"
```

Returns Markdown plus where it was stored; requires `OPENAI_API_KEY` on the server because it calls the manager agent.

To re-run a URL that already exists in storage, pass a query param:
- `skip_duplicate=true` (bypass for this request), or
- `skip_duplicate_for_url=<exact url>` (safer; only bypasses when it matches the payload `url`)

Environment knobs:
- `INGEST_DATA_DIR` to change storage root.
- `INGEST_HOST` / `INGEST_PORT` / `INGEST_RELOAD` for server startup.
- `CORS_ALLOW_ALL` (default true) or `CORS_ALLOW_ORIGINS` (comma-separated) to constrain extension access.
- `CORS_ALLOW_CREDENTIALS` (default true, but forced false when origins are `*` to avoid the wildcard+credentials startup error).
- `AGENT_TRACE_PATH` to append a plain-text trace log for manager-agent runs (tool calls + outputs + final markdown + raw article content).

### Chrome extension scaffold (MV3)

Location: `extensions/chrome-intake/`

Build (requires Node/npm; if scripts are blocked, enable script execution for npm):

```
cd extensions/chrome-intake
npm install
npm run build   # on Windows, use `npm.cmd run build` if PowerShell blocks npm.ps1
```

Load in Chrome:
1) Open `chrome://extensions/`, enable Developer Mode.
2) Click "Load unpacked" and choose `extensions/chrome-intake/dist/`.
3) Right-click any page, frame, or link and choose "Capture article for ingest." On first use for a new site (or an embedded article hosted in a different origin), Chrome will prompt for that specific origin; grant permission to scrape. Link targets are opened in a background tab, scraped, and closed automatically; if the background tab hangs or Chrome cannot inject into a frame, the popup shows a capture error instead of failing silently.
4) After capture, the extension now auto-sends the article to the configured endpoint. Opening the popup shows whether it was processed (or marked duplicate); the "Send" button is a manual retry.

Configure endpoint:
- In the options page, set the endpoint URL (default `http://localhost:8000/process/article`). If you point it to `/ingest/article`, the extension sends the coverage-schema payload instead of the full pipeline payload.
  - Note: the ingest payload now includes a required `facts` array (min 1). The server still accepts legacy `section/subheading` payloads and will synthesize one fact for backward compatibility.

Note: The build emits `dist/` with bundled `background.js`, `contentScript.js`, `popup.js`, and static `manifest.json`, `popup.html`, `options.html`. Install-time host permissions are limited to Feedly; other sites are requested at click time. The manifest requests `storage`, `activeTab`, `tabs`, `scripting`, and `contextMenus`; `tabs` is required so link captures can open and close a background tab.

Payload format for the default pipeline endpoint: one JSON object (not a list) with `title`, `source`, `url`, `content`, and optional `published_at` date (`YYYY-MM-DD`). The content script trims common datetime meta tags (e.g., `article:published_time`) down to just the date so the pipeline can infer the quarter. Example:

```
{
  "title": "Example headline",
  "source": "SampleWire",
  "url": "https://example.com/story",
  "content": "Full text of the article...",
  "published_at": "2025-01-15"
}
```

The service worker derives the `quarter` automatically from `published_at` (falling back to the scrape timestamp, then the current date), so articles land in the correct reporting period without manual entry.
If a page does not expose a publish date, the service worker sends the scrape date instead so ingest does not fail on required `published_at`.

## Debug Fixtures

- Reuse the three sample Variety articles in `data/samples/debug/` when you need a quick, repeatable input. Each file now contains the full article body text from Dec. 5, 2025 Variety stories so runs mirror real ingest conditions. Each file is a single JSON object so it works directly with the CLI. Example:

```
python -m news_coverage.cli data/samples/debug/variety_wga_netflix_warner_merger.json --out scratch.md
```

- The set covers the Netflix-Warner Bros. merger story, an A24/Peacock series announcement, and a column on what a Netflix-owned Warner Bros. would mean for theaters.
- Duplicate checks are automatically skipped for files under `data/samples/debug/` so you can rerun them without 409-style messages.

## Output Format

Markdown output is delivery-ready and follows three lines for single-title articles:
- Title: <headline>
- Category: <classifier path with arrows>
- Content: <leading summary sentence> ([M/D](article_url)) -- the date (month/day) is the hyperlink to the article.

If the summarizer emits multiple bullets, the markdown keeps every line (only adding the date hyperlink when a line lacks a date parenthetical) so multi-title stories are not collapsed.

Multi-title content-deal/slate articles (e.g., international greenlights) are formatted one line per title using the content-deals prompt: [Country] Title: Platform, genre (M/D) with M/D taken from the article publish date. If the model adds parentheses for subtitles/alternate titles but no date, the formatter still appends the publish date.

Multi-fact articles (e.g., one greenlight plus multiple renewals) now render as one block per article with repeated Category/Content pairs in model order. The stored JSONL record contains a `facts` array (min 1) with per-fact category/subheading/company/quarter/published_at plus `content_line` and `summary_bullets`. Legacy single-category `section/subheading/summary/bullet_points` are deprecated in favor of `facts`.

Markdown output is delivery-ready and follows three lines:
- `Title: <headline>`
- `Category: <classifier path with arrows>` (the top bucket stays as `Content, Deals, Distribution` so you’ll see `Content, Deals, Distribution -> TV -> …`)
- `Content: <leading summary sentence> ([M/D](article_url))` -- the date (month/day) is the hyperlink to the article.

After a successful, non-duplicate run, the pipeline also appends a delivery-ready
block (including matched buyers and ISO publish timestamp) to
`docs/templates/final_output.md`. Set `FINAL_OUTPUT_PATH` to redirect this log
in tests or other environments.
In that log, each `Category:` block uses a `Content:` bullet list (even for a
single item). This keeps every summary bullet while avoiding ambiguous parsing
when a single fact contains multiple bullets. Each bullet gains the date
hyperlink when it lacks a date parenthetical.
### Company Recognition

- The pipeline now recognizes major buyers (Amazon, Apple, Comcast/NBCU, Disney, Netflix, Paramount, Sony, WBD, A24, Lionsgate) using keywords in the title, early body text, and URL host, treating keywords as whole words so substrings like "maxwell" do not trigger the WBD keyword `max`.
- When nothing matches clearly, runs fall back to `Unknown` so a human can decide later.

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
- Final output template showing buyers/date layout: `docs/templates/final_output.md`.

## Contributing Guidelines for Agents

Review `AGENTS.md` before making changes. Key points:
- Run `pytest` and `flake8` after code changes.
- Update component `AGENTS.md` files when behavior changes.
- Use ExecPlans for complex work per `.agent/PLANS.md`; place them under `.agent/in_progress/` while active and `.agent/complete/` when finished.

Current ExecPlans
- Active: `.agent/in_progress/execplan-chrome-extension.md` (extension + ingest design), `.agent/in_progress/execplan-multi-fact-classification-storage.md` (store multiple labeled facts per article), and `.agent/in_progress/execplan-parallel-agent-runs.md` (parallel batch processing).
- Recently finished and archived to `.agent/complete/`: auto-process endpoint & extension auto-send (`execplan-auto-process-endpoint.md`), minimal-permission Feedly capture flow (`execplan-feedly-capture-flow.md`), and multi-title slate routing/formatting (`route-slate-articles.md`).

## Roadmap

- See `ROADMAP.md` for the full list. Highlights:
  - Replace the offline fallback with a full Agents workflow call and structured parsing.
  - Add richer formatting options (Markdown/HTML) for downstream consumption.
  - Later: add a reviewer/LLM quality-check step after formatting.
