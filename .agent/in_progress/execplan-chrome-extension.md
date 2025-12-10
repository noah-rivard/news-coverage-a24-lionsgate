# Chrome Extension Intake for News Coverage Builder

This ExecPlan is a living document. Maintain every section in sync with the work, following `.agent/PLANS.md`.

## Purpose / Big Picture

Enable a non-technical user to click a Chrome button while reading any entertainment news article and have the extension capture the article, recognize whether it is about A24 or Lionsgate, assign it to the correct quarter and section (Highlights, Org, Content/Deals/Distribution, Strategy/Misc, Investor Relations, M&A), and hand it to the Python workflow in this repo so the quarterly news coverage document can be assembled with minimal manual effort.

## Progress

- [x] (2025-12-04 23:15Z) Reviewed sample news coverage DOCX files and extracted the shared outline and common subheadings to define the taxonomy.
- [x] (2025-12-04 23:55Z) Defined the canonical coverage schema (sections, subheadings, required fields, quarter rules) in JSON and human-readable docs under `docs/templates/`.
- [x] (2025-12-05 00:05Z) Defined the ingestion contract (HTTP endpoint, payload validation, storage, errors) in `docs/templates/ingest_api_contract.md`.
- [x] (2025-12-10 02:05Z) Scaffolded the Chrome MV3 extension (`extensions/chrome-intake/`) with content script scraper, service worker, popup, options page, build script (esbuild), and component AGENTS guide.
- [x] (2025-12-10 02:05Z) Backend ingest service runnable via `python -m news_coverage.server`; CORS enabled for extension; curl examples added to README. Tests (`pytest`, `flake8`) remain green.

## Surprises & Discoveries

- Top-level sections are consistent across buyers: 0 Highlights, 1 Org, 2 Content/Deals/Distribution, 3 Strategy & Miscellaneous News, 4 Investor Relations, 5 M&A. The DOCX files include stray page-number suffixes (for example, "1" or "Error! No bookmark name given.") that must be stripped when parsing.
- Subheadings are stable and high-frequency: General News & Strategy, Development, Greenlights, Pickups, Dating, Renewals, Exec Changes, Cancellations, Strategy, International, Quarterly Earnings, Company Materials, News Coverage; Podcasts and Sports appear occasionally. M&A rarely appears as a dedicated subheading, so it may be optional.
- Netflix files are about 33 MB each; parsing should stream or target specific XML parts to avoid memory spikes.
- Titles encode quarter boundaries (for example, "Q3 2024 News & Updates July - September 2024"), which can drive automatic quarter assignment from article dates.

## Decision Log

- Decision: Use Chrome Manifest V3 with a service worker (background script), content script, popup, and options page in TypeScript; rationale: MV3 is required for the Chrome Web Store and keeps the extension compatible with modern Chrome APIs. Date/Author: 2025-12-04 / Codex.
- Decision: Exchange data via a small FastAPI ingest service in this repo (JSON over HTTPS); rationale: reuses existing Pydantic models, keeps testing in Python, and gives the extension a single, well-defined endpoint. Date/Author: 2025-12-04 / Codex.
- Decision: Fix the taxonomy to the observed outline (Highlights, Org, Content/Deals/Distribution, Strategy/Misc, Investor Relations, M&A) with standard subheadings listed above; rationale: mirrors historical deliverables, enabling deterministic section placement. Date/Author: 2025-12-04 / Codex.
- Decision: Use esbuild for a lightweight MV3 bundle (background, content script, popup, options) and keep dependencies minimal (`@mozilla/readability`, `@types/chrome`, `typescript`). Date/Author: 2025-12-10 / Codex.

## Outcomes & Retrospective

To be completed after implementation and validation.

## Context and Orientation

The repository currently provides a Python CLI (`news_coverage.cli`) that summarizes entertainment news using the OpenAI Responses API with an offline fallback. Sample quarterly coverage documents live under `docs/samples/news_coverage_docx/`. Each document covers one buyer for one fiscal quarter and follows the outline captured in Surprises & Discoveries. The user already maintains a Feedly database of articles; the planned extension should ingest articles directly from the open browser tab and send them to this repo's workflow. No browser code or HTTP ingest service exists yet.

## Plan of Work

Start by formalizing the coverage template so both the extension and backend speak the same schema. Create a JSON schema plus short prose that describes required fields (company, quarter, section, subheading, headline, date, source, url, summary, notes) and quarter inference rules. Add helper code in Python to load and validate this schema.

Next, design and implement a FastAPI-based ingest service inside `src/news_coverage/` that exposes health and `POST /ingest/article` endpoints. Accepted payloads should match the schema and be stored durably (for example, JSONL files partitioned by company and quarter). Provide a CLI wrapper to start the server and a small formatter that converts stored items into the same internal structures used by the existing summarization workflow, so downstream rendering can be automated later.

Then scaffold the Chrome extension in a new `extensions/chrome-intake/` folder. Use TypeScript with a lightweight bundler (esbuild or Vite) to produce MV3 assets (service worker, content script, popup, options page). The content script should extract article metadata using DOM selectors plus a Readability-style parser to capture body text. The service worker should run lightweight keyword heuristics to guess buyer (A24, Lionsgate) and section/subheading based on the taxonomy; it should also allow an optional call to the backend for model-assisted classification. The popup should present the scraped content, predicted labels, quarter guess, and let the user correct before sending. The options page should store the ingest endpoint, API key (if needed), and toggles for auto-send vs. review.

Add tests: Python `pytest` for ingest validation and storage, and JS/TS tests (Vitest/Jest) for the classifier heuristics. Provide a manual verification script that launches the backend, loads the unpacked extension, visits a sample article, and confirms the posted payload appears in the backend storage.

Finally, document everything in README/CHANGELOG once implemented, including how to load the extension, configure the endpoint, and run tests.

## Concrete Steps

- Working dir: repository root. Create `docs/templates/coverage_schema.json` and companion `docs/templates/coverage_schema.md` describing the taxonomy and quarter rules derived from the sample DOCX files.
- Add Python helpers in `src/news_coverage/` to load the schema and start a FastAPI server (`uvicorn news_coverage.server:app --reload`). Store ingested articles under `data/ingest/{company}/{quarter}.jsonl` with rotation safeguards.
- Scaffold `extensions/chrome-intake/` with `package.json`, manifest v3, TypeScript source, and build scripts (`npm run build` -> `dist/`). Use `readability` for text extraction and `chrome.storage.sync` for settings.
- Implement classification heuristics (keyword lists for A24/Lionsgate names, talent aliases, franchise titles) and map to sections/subheadings. Provide an optional fetch to `/classify` on the backend for model-based classification when the user enables it.
- Write tests: `pytest` for the ingest API contract and storage; `npm test` (Vitest/Jest) for classifier and scraper utilities. Include an end-to-end manual checklist in README once working.

## Validation and Acceptance

Acceptance requires: (1) Running `python -m news_coverage.server` starts the FastAPI service and `/health` returns 200. (2) Posting a sample payload via curl writes to `data/ingest/{company}/{quarter}.jsonl` and is readable by the existing workflow loader. (3) Loading the unpacked extension in Chrome, scraping a live article, and clicking "Send" records the article with the predicted section/quarter; the popup allows corrections before sending. (4) `pytest`, `flake8`, and `npm test` all pass. (5) README documents setup for both backend and extension, and CHANGELOG notes the addition.

## Idempotence and Recovery

Schema generation, storage writes, and builds should be repeatable. The ingest service should ignore duplicate URLs by default (configurable), log rejects, and never delete existing data. The extension should queue failed sends in `chrome.storage.local` for retry when the backend becomes available. Re-running builds should overwrite `dist/` safely without manual cleanup.

## Artifacts and Notes

Key artifacts: `docs/templates/coverage_schema.json` (canonical outline), `docs/templates/ingest_api_contract.md` (ingest contract), `src/news_coverage/server.py` (FastAPI ingest), `extensions/chrome-intake/` (MV3 source + manifest), and sample payload fixtures for tests. Provide an example payload inline in the schema docs to show how "General News & Strategy" items are represented.

## Interfaces and Dependencies

Backend dependencies: `fastapi`, `uvicorn`, `pydantic` (already in use), and optionally `python-dateutil` for robust date parsing. Extension dependencies: `typescript`, `esbuild` or `vite`, `@mozilla/readability` for content extraction, and `vitest`/`jest` for tests. HTTP contract: `POST /ingest/article` with JSON fields `{company, quarter, section, subheading, title, source, url, published_at, summary?, body?, tags?, notes?}`; responses should include `{status, stored_path, normalized_quarter}`. Add `GET /health` and optionally `POST /classify` for server-side classification when enabled in the extension.
