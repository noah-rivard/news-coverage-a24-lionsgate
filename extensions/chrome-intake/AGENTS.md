# Component Guide: `extensions/chrome-intake/`

Scope: Chrome Manifest V3 extension that scrapes article pages and posts payloads to the ingest API.

Gotchas and expectations:
- Build with `npm run build` (esbuild) to emit `dist/`. Load `dist/` as the unpacked extension in Chrome.
- Service worker stores the latest scraped article in `chrome.storage.local` and sends it to the ingest endpoint from `chrome.storage.sync` (default `http://localhost:8000/ingest/article`).
- Content script uses `@mozilla/readability`; if a page blocks script injection, reloading may be required.
- Keep manifest permissions minimal; avoid adding host permissions beyond `<all_urls>` without updating this guide.
- Update README/CHANGELOG when changing build steps, manifest, or permissions.
