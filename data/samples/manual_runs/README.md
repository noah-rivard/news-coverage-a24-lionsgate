# Manual Runs

This folder holds sample article payloads used for manual pipeline spot-checks.

- Files may contain only a `url` when captured via the Chrome extension. Those URL-only stubs are *not* runnable through the CLI until full article fields (title, source, content, published_at) are populated by the extension.
- To view pipeline output, right-click the article with the extension to capture the full payload, or replace the stub with a full JSON article object that matches `src/news_coverage/models.Article`.

Helper script:
- Run `python tools/run_manual_samples.py` from the repo root. It will iterate `*.json` in this folder. URL-only stubs are reported and skipped. Files with full fields are passed to the CLI (`--mode agent`), and output is written next to the input with `.out.md`.
