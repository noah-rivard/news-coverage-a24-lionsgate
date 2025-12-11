# Component Guide: `extensions/chrome-intake/`

 Scope: Chrome Manifest V3 extension that scrapes article pages and posts payloads to the ingest API.

Gotchas and expectations:
- Build with `npm run build` (esbuild) to emit `dist/`. Load `dist/` as the unpacked extension in Chrome. The build script now uses `fileURLToPath` so Windows paths (double drive letters) no longer break `npm run build`.
- Service worker stores the latest scraped article in `chrome.storage.local` and sends it to the ingest endpoint from `chrome.storage.sync` (default `http://localhost:8000/ingest/article`).
- Quarter is derived from the article date (prefers `published_at`, falls back to `scrapedAt`, then the current date) before posting; nothing is hard-coded in the payload.
- Content script uses `@mozilla/readability`; if a page blocks script injection, reloading may be required.
- Keep manifest permissions minimal; avoid adding host permissions beyond `<all_urls>` without updating this guide.
- Update README/CHANGELOG when changing build steps, manifest, or permissions.
- `published_at` must be a `YYYY-MM-DD` date per `coverage_schema.json`; the content script trims any datetime meta tag (e.g., `article:published_time`) down to the date before sending to the service worker. If no publish date is found, the service worker now falls back to the scrape timestamp’s date before sending to ingest to avoid 400s.
