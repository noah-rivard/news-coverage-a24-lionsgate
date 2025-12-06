# Component Guide: `data/`

Scope: Sample and ingest artifacts used by the workflow (JSON/JSONL fixtures under `data/`).

Gotchas and expectations:
- Keep fixtures lightweight and plain-text (ASCII) so they are easy to diff and safe to ship.
- The CLI expects a single-article JSON object (not JSONL); keep per-article files for quick runs.
- Debug fixtures under `data/samples/debug/` now carry the full Variety article bodies (Dec 5, 2025) so the pipeline can be exercised on realistic text; keep these for internal testing only and avoid adding other full-page scrapes elsewhere without updating this guide.
- Do not store copyrighted full-page scrapes or PII outside approved debug fixtures; prefer short, representative text for new samples.
- When adding or moving fixtures, update README and CHANGELOG so other contributors know where to find them.
- Avoid editing historical ingest files under `data/ingest/` unless you are intentionally changing stored output from the pipeline.
- CLI bypasses duplicate checks for fixtures under `data/samples/debug/` so repeated runs stay noise-free.

Recent additions:
- `data/samples/debug/` holds three Variety-based articles the team can reuse for local debugging.
