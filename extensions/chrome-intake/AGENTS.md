# Component Guide: `extensions/chrome-intake/`

 Scope: Chrome Manifest V3 extension that scrapes article pages and posts payloads to the ingest API.

Gotchas and expectations:
- Build with `npm run build` (esbuild) to emit `dist/`. Load `dist/` as the unpacked extension in Chrome. The build script now uses `fileURLToPath` so Windows paths (double drive letters) no longer break `npm run build`.
- Service worker stores the latest scraped article in `chrome.storage.local` and queues it for send to the configured endpoint in `chrome.storage.sync` (default `http://localhost:8000/process/articles`). It auto-sends after each scrape; the popup is mainly for status or retry.
- Quarter is derived from the article date (prefers `published_at`, falls back to `scrapedAt`, then the current date) before posting; nothing is hard-coded in the payload.
- Content script uses `@mozilla/readability`; if a page blocks script injection, reloading may be required.
- Manifest requires only Feedly origins at install and lists all other origins as optional host permissions. The content script is no longer auto-injected; scraping happens on demand after a per-origin permission grant.
- Manifest must include the `tabs` permission so the service worker can open/close background tabs during link capture; without it `tabs.create/remove` calls fail.
- A single context menu item ("Capture article for ingest") is registered on page/frame/link. On click, the service worker requests host permission for the actual capture target (link destination or the iframe origin when right-clicking inside a frame) before injecting `contentScript.js` (background tab for links to avoid stealing focus). A 45s timeout closes background tabs that hang and reports a capture error (instead of failing silently).
- Update README/CHANGELOG when changing build steps, manifest, or permissions.
- `published_at` must be a `YYYY-MM-DD` date per `coverage_schema.json`; the content script trims any datetime meta tag (e.g., `article:published_time`) down to the date before sending to the service worker. If no publish date is found, the service worker now falls back to the scrape timestamp’s date before sending so both ingest and process endpoints have a valid date.
- If the endpoint contains `/ingest/`, the service worker sends the coverage-schema payload including a required `facts` array (min 1). Otherwise it sends the raw article (title/source/url/content/published_at) to the pipeline endpoint. When the endpoint contains `/process/articles`, it sends the queued articles as a JSON array and clears only the successful ones.
