# Roadmap

## Near term
- Keep a single coordinator that calls specialist agents as tools (ingest, summarize, format) so we stay in control of the conversation and context.
- Run each article through the pipeline one step at a time; we are not parallelizing article steps.
- Replace the offline fallback with a live OpenAI Agents workflow and structured parsing.

## Soon
- Offer richer output formats (Markdown and HTML) to drop into downstream tools without rework.

## Later
- Add a reviewer/"LLM-as-judge" agent after formatting to spot tone or accuracy issues and trigger a quick revise pass if needed.
