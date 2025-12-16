# Min-Permission Feedly Capture Flow for Chrome Intake (MV3)

This ExecPlan is a living document. Update all sections—especially Progress, Surprises & Discoveries, Decision Log, and Outcomes & Retrospective—as work proceeds. Follow `.agent/PLANS.md` from the repo root.

## Purpose / Big Picture

Enable the Chrome intake extension to request only the Feedly origin at install while still scraping arbitrary article links on demand. Scraping should be triggered by a user gesture (context menu), request per-site permission at click time, open the target in a background tab, run the scraper, cache the article, and close the tab. Users gain a lighter install prompt and explicit control over cross-site access without losing functionality.

## Progress

- [x] (2025-12-15 18:00Z) Current state analyzed; scope and flow decided.
- [x] (2025-12-15 19:10Z) Implemented manifest tightening, optional host permissions, and runtime permission helper.
- [x] (2025-12-15 19:25Z) Added link-aware context-menu capture with background-tab scraping and timeout; handles denied permissions.
- [x] (2025-12-15 19:28Z) Popup now surfaces capture failures and clearer no-article guidance.
- [x] (2025-12-15 19:40Z) Updated component guide, README, CHANGELOG; rebuilt dist with new manifest.

## Surprises & Discoveries

- Running `pytest` in this environment failed at collection (`ModuleNotFoundError: No module named 'src'`), likely because the package is not installed in editable mode in the current shell. No code changes were made to address this; rerun after ensuring the project is installed (e.g., `pip install -e .`).

## Decision Log

- Decision: Remove auto-injection `<all_urls>` content script; inject only on demand via scripting after permission.  
  Rationale: Avoid install-time all-site prompt while preserving functionality through per-origin grants.  
  Date/Author: 2025-12-15 / Codex

- Decision: Treat any `https://feedly.com` or `https://*.feedly.com` page as Feedly mode; if `contextMenus` click has `linkUrl`, capture that target; else capture current page/frame.  
  Rationale: Matches Feedly card-link pattern and minimizes extra UI.  
  Date/Author: 2025-12-15 / Codex

- Decision: Use single menu label “Capture article for ingest” with contexts `page, frame, link`; reuse one flow to choose link vs. page.  
  Rationale: Keeps UX simple and leverages user gesture for permission requests.  
  Date/Author: 2025-12-15 / Codex

## Outcomes & Retrospective

- Install-time permissions are now limited to Feedly; other origins prompt at capture time. Capture runs in the background for links and closes tabs within 20s. Popup communicates failures. Documentation and dist are aligned. Remaining risk: no automated JS tests; manual verification required in Chrome.

## Context and Orientation

Repo root: `news-coverage-a24-lionsgate`. Chrome extension lives in `extensions/chrome-intake/`. Key files:
- `src/manifest.json`: MV3 manifest (currently uses `<all_urls>` host_permissions and a `<all_urls>` content script).
- `src/background.ts`: service worker; registers context menu, stores scraped article, posts to ingest.
- `src/contentScript.ts`: scrapes page content with Readability and sends `ARTICLE_SCRAPED`.
- `src/popup.ts`: displays cached article and triggers ingest POST.
- `scripts/build.mjs`: bundles TS and copies manifest/html into `dist/`.
Component guide: `extensions/chrome-intake/AGENTS.md` (must update when behavior changes).
Top-level rules: update README and CHANGELOG after changes; run tests when code changes (JS area currently has no tests; Python tests not needed for extension-only changes but note in plan).

## Plan of Work

Describe in prose what to change:

1) Manifest tightening  
   - In `src/manifest.json`, set `host_permissions` to `["https://feedly.com/*", "https://*.feedly.com/*"]`.  
   - Add `optional_host_permissions`: `["https://*/*", "http://*/*"]`.  
   - Remove the static `content_scripts` block to stop auto-injection on `<all_urls>`.  
   - Keep permissions list to `["storage", "activeTab", "scripting", "contextMenus"]`.  
   - Bump `version` to `1.0.0`.

2) Runtime host-permission helper  
   - In `src/background.ts`, add `ensureHostPermissionForUrl(url)` that builds `<protocol>//<host>/*`, checks `chrome.permissions.contains`, and if absent, requests within the click handler user gesture. Return boolean success.

3) Capture flow changes (service worker)  
   - Update context-menu registration: call `removeAll` then create menu on `onInstalled` and `onStartup`. Contexts: `["page", "frame", "link"]`.  
   - In `onClicked`, decide target URL: prefer `info.linkUrl` when present; else current tab URL. Detect Feedly by tab URL origin.  
   - Before injecting/opening, call `ensureHostPermissionForUrl(targetUrl)`; if denied, notify (e.g., `chrome.notifications` or send response to popup) and exit.  
   - Implement background-tab capture: `chrome.tabs.create({ url: targetUrl, active: false })`, wait for load complete (or a short delay), inject `contentScript.js` via `chrome.scripting.executeScript`. Add timeout (~20s) to abort, then close the temp tab. On success, `ARTICLE_SCRAPED` message will populate storage (existing listener). Ensure tab closes on both success and failure.  
   - For same-tab capture (when target is current tab), inject script directly without opening a new tab.

4) Popup feedback tweaks  
   - In `src/popup.ts`, handle new status messages returned from background (permission denied, capture failed). Show concise text (green for success, red for errors). Default remains “Ready to send” when article present.

5) Documentation and guides  
   - Update `extensions/chrome-intake/AGENTS.md` to reflect reduced permissions, on-demand injection, and background-tab capture behavior.  
   - Update repo `README.md` extension section to describe new permission model and capture flow.  
   - Append `CHANGELOG.md` entry describing manifest tightening and on-demand host permission request.  
   - No code tests exist here; note in CHANGELOG that JS area still lacks automated tests.

6) Build artifacts  
   - Run `npm run build` in `extensions/chrome-intake` to refresh `dist/` with new manifest and bundles.

## Concrete Steps

Commands (run from repo root unless noted):
- Inspect / edit files per plan (no command).  
- `cd extensions/chrome-intake && npm run build`  
- (No pytest/flake8 needed for JS-only change; state this explicitly in final notes.)

## Validation and Acceptance

- Install/load `dist/` in Chrome. On install, permission prompt should mention only Feedly, not all sites.  
- Right-click on a Feedly card link: on first click for a new domain, Chrome prompts for that origin; if granted, capture completes and popup shows scraped article ready to send.  
- Right-click on any page/link outside Feedly: first use prompts for that origin; after granting, capture succeeds.  
- Permission denial results in visible red status text in popup (or notification) and no tab remains open.  
- Background tab used for capture closes automatically within timeout after scraping.  
- Ingest “Send” still posts successfully (existing behavior).

## Idempotence and Recovery

- Menu registration uses `removeAll` to avoid duplicates; safe to reload extension.  
- Background-tab capture always closes the created tab on success, timeout, or error.  
- Permission requests are origin-scoped; repeated clicks reuse grants. If a request is denied, user can retry the menu action to re-prompt.

## Artifacts and Notes

- Keep changes confined to `extensions/chrome-intake/src/manifest.json`, `background.ts`, `popup.ts`, and docs (`README.md`, `CHANGELOG.md`, `extensions/chrome-intake/AGENTS.md`).  
- Build outputs land in `extensions/chrome-intake/dist/` via existing script.

## Interfaces and Dependencies

- Chrome APIs: `chrome.permissions.contains/request`, `chrome.contextMenus`, `chrome.scripting.executeScript`, `chrome.tabs.create/remove`, `chrome.runtime.onInstalled/onStartup/onMessage`, `chrome.storage.local/sync`.  
- No new npm deps anticipated; reuse existing Readability and TS setup.  
- `ensureHostPermissionForUrl(url: string): Promise<boolean>` utility in `background.ts` centralizes permission checks/requests.
