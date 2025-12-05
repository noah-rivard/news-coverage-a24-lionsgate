# Component Guide: `src/news_coverage/` (core workflow & services)

- Default classifier/summarizer rely on the OpenAI Responses API. `process_article` only builds a client (and therefore requires `OPENAI_API_KEY`) when those defaults are used; when injecting both tools or passing a client, it will run offline for tests.
- Injected tools must accept a `client` argument that can be `None` when you provide both classifier and summarizer; return the same dataclasses used in `workflow.py`.
- Ingest writes JSONL files under `data/ingest/{company}/{quarter}.jsonl` after schema validation and duplicate detection; keep file paths stable so Chrome extension/back-end stay in sync.
- Summarizer calls skip the `temperature` parameter when `SUMMARIZER_MODEL` is `gpt-5-mini` (model rejects it).
- Batch summarization helper (`summarize_articles_batch` + `_extract_summary_chunks`) raises when the model returns fewer chunks than articles to avoid silent drops.
- Prompt templates live in `src/prompts/`; keep `workflow.PROMPTS_DIR` aligned if relocating.
- Update this guide whenever workflow behavior, storage paths, or tool signatures change so downstream services and tests remain aligned.
