# Q4 2025 Multi-Buyer News Coverage DOCX Generation

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept current as work proceeds. Follow `.agent/PLANS.md`.

## Purpose / Big Picture

Enable a one-command workflow that generates Q4 2025 “News Coverage” DOCX files for each buyer (Amazon, Apple, Comcast/NBCU, Disney, Netflix, Paramount, Sony, WBD, A24, Lionsgate) using the repository’s ingest data and a consistent template. The output should mirror the structure/styles of `2025 Q2 Warner Bros Discovery News Coverage.docx`, apply multi-buyer routing rules, surface questionable matches in a consolidated “Needs review” file, and skip auto-highlights (left for manual editing). After implementation, a user can run a CLI command and receive a complete DOCX per buyer plus one review file, without hand formatting.

## Progress

- [x] (2025-12-09 16:30Z) Drafted and saved ExecPlan.
- [x] (2025-12-09 17:05Z) Implementation in progress.
- [x] (2025-12-09 18:05Z) Implementation complete; docs/tests updated.
- [x] (2025-12-09 18:10Z) Validation (pytest/flake8/CLI demo) complete.
- [x] (2025-12-10 16:00Z) Retrospective written and plan closed.

## Surprises & Discoveries

- None observed during the build; template styles mapped cleanly to `python-docx`.

## Decision Log

- Decision: Use `docs/samples/news_coverage_docx/2025 Q2 Warner Bros Discovery News Coverage.docx` as the style/template reference. (2025-12-09 / you)
- Decision: Buyer set = Amazon, Apple, Comcast/NBCU, Disney, Netflix, Paramount, Sony, WBD, A24, Lionsgate. (2025-12-09 / you)
- Decision: No auto Highlights; manual later. (2025-12-09 / you)
- Decision: Multi-buyer detection via keyword rules; strong matches auto-include, weak matches flagged. (2025-12-09 / you)
- Decision: Missing `published_at` -> block and send to “Needs review.” (2025-12-09 / you)
- Decision: Re-run summaries for provided article JSONs; use results directly for DOCX (no need to append to ingest files). (2025-12-09 / you)

## Outcomes & Retrospective

- Built keyword-based routing, coverage assembly, and DOCX rendering with `python-docx`, plus a `build-docx` CLI that emits per-buyer Q4 2025 reports and a consolidated `needs_review.txt`. Tests (`pytest` 21 passed) and `flake8` were green on 2025-12-09, and README/CHANGELOG/AGENTS were updated alongside the code.
- The template mapping held up without requiring custom fonts; remaining manual work is limited to Highlights and any items flagged in the review file. Future quarters can reuse the builder by swapping the quarter label and template path.

## Context and Orientation

- Current flow (`src/news_coverage/workflow.py` and `agent_runner.py`) classifies, summarizes, formats Markdown, and ingests to JSONL under `data/ingest/{company}/{quarter}.jsonl`. Company inference is rudimentary (A24, Lionsgate, Unknown).
- Coverage schema lives at `docs/templates/coverage_schema.{json,md}` and defines sections/subheadings matching historical DOCX structure (Sections 0–5: Highlights, Org, Content/Deals/Distribution, Strategy & Misc, Investor Relations, M&A).
- No DOCX generation code or docx library exists before this work.
- Style/example DOCX files are under `docs/samples/news_coverage_docx/`; chosen template: `2025 Q2 Warner Bros Discovery News Coverage.docx`.
- Sample outputs in `docs/sample_outputs.md` show Title/Category/Content markdown, not DOCX.
- Tests expect pytest/flake8; code changes require updates to README and CHANGELOG per repo rules.
- You will provide a small set of article JSONs to re-run the agent pipeline; outputs should flow straight into DOCX generation.

## Plan of Work

1) **Template study & style extraction**
   - Inspect `2025 Q2 Warner Bros Discovery News Coverage.docx` to map section order, heading styles, paragraph spacing, list formats, cover header layout, and TOC conventions.
   - Define a style map (e.g., Title, Heading 1, Heading 2, body text/bullets) to recreate with `python-docx`.

2) **Keyword routing spec**
   - Codify the first-pass keyword/alias list per buyer (as provided below) and implement strong/weak detection rules.
   - Strong match: keyword in title OR first 400 chars of body OR URL host. Weak match: keyword elsewhere in body.
   - If multiple buyers are strong, include in all. If weak only, place in “Needs review” for those buyers.

   Keyword list v1 (case-insensitive):
   - Amazon: amazon, prime video, mgm, amazon mgm, freevee
   - Apple: apple, apple tv+, appletv, apple tv, tv plus
   - Comcast/NBCU: comcast, nbc, nbcu, peacock, universal, universal pictures, universal tv, usa network, syfy, bravo, telemundo, sky
   - Disney: disney, disney+, disney plus, walt disney, wdw, pixar, marvel, lucasfilm, espn, hulu, abc, fx, nat geo
   - Netflix: netflix, nflx
   - Paramount: paramount, paramount+, paramount plus, p+, cbs, showtime, mtv, nickelodeon, nick, pluto tv
   - Sony: sony, sony pictures, spe, crunchyroll, funimation, columbia pictures, tri-star, tristar, screen gems, playstation productions
   - WBD: warner bros, warner bros. discovery, wbd, wb, warner media, warner hbo, hbo, max, discovery, discovery+, tnt, tbs, cnn, dc studios, warner animation
   - A24: a24
   - Lionsgate: lionsgate, lions gate, starz, starzplay, starz play, grindstone

3) **Data intake & normalization**
   - Accept article inputs from two sources:
     a) Provided article JSONs (single-object files) to re-run through the agent pipeline for fresh summaries.
     b) Existing ingest JSONL files (`data/ingest/*/2025 Q4.jsonl`) as a fallback reference.
   - For each article, ensure required fields exist; if `published_at` is missing, route to “Needs review” instead of proceeding.
   - Re-run the agent pipeline on provided JSONs to get clean classification/summary. Do not mutate ingest JSONLs unless explicitly required.

4) **Section and ordering rules**
   - Map classifier `classification_notes` path to schema section/subheading; use existing `_parse_category_path` logic where possible.
   - Medium grouping inside Content/Strategy: Film, TV, International, Sports/Podcasts (when present), then subheading (Development, Greenlights, Dating, Renewals, Cancellations, etc.), newest→oldest by `published_at`.
   - Org, Investor Relations, and M&A follow schema headings; sort newest→oldest within subheading.

5) **Needs review pipeline**
   - Collect items that are: missing `published_at`, weak-only matches for a buyer, malformed summaries/bullets, or other validation issues.
   - Emit a single consolidated “Needs review” text/markdown file listing: buyer, title, URL, reason(s), and where it would have been placed.

6) **DOCX generation**
   - Add `python-docx` to dependencies.
   - Build a generator that, per buyer, creates `2025 Q4 <Buyer> News Coverage.docx` with:
     - Cover header: “Q4 2025 News & Updates” and “October – December 2025”.
     - Numbered sections 1–5 (skip 0 Highlights), matching template styles.
     - Medium/subheading grouping as above; bullet/paragraph styles consistent with template.
   - Preserve ASCII in generated text; avoid smart quotes.

7) **CLI entrypoint**
   - Add a Typer command (e.g., `python -m news_coverage.cli build-docx --articles <dir_or_files> --quarter "2025 Q4"`) to:
     - Load provided article JSONs, run the pipeline, apply routing, generate all buyer DOCXs, and emit the consolidated Needs review file.
     - Allow optional `--buyers` filter if needed.

8) **Docs and changelog**
   - Update README with DOCX generation instructions and dependencies.
   - Update relevant AGENTS guides (`docs/AGENTS.md`, `src/AGENTS.md`, `src/news_coverage/AGENTS.md`) if behavior changes.
   - Add CHANGELOG entry.

9) **Validation**
   - Run pytest/flake8 (required for code changes).
   - Smoke test the new CLI with 1–2 provided article JSONs to confirm DOCX creation and Needs review output.

## Concrete Steps

- Working dir: repo root.
- Study template: unzip/read styles from `docs/samples/news_coverage_docx/2025 Q2 Warner Bros Discovery News Coverage.docx`; note heading names and indentation.
- Add dependency: `python-docx` to `pyproject.toml` (project deps, not dev-only).
- Implement routing module for buyer matching (strong/weak logic and keyword map).
- Implement data loader that:
  - Ingests provided JSON files, re-runs agent pipeline, normalizes records, and keeps them in memory for DOCX generation.
  - Optionally reads existing JSONL for context but does not overwrite unless requested.
- Implement section builder that organizes articles per buyer using schema mapping and ordering rules; collect Needs review items.
- Implement DOCX writer using style map derived from the template; generate one DOCX per buyer plus a single Needs review text/markdown file.
- Extend CLI with a `build-docx` command; wire arguments for input paths, quarter, and optional buyer filter.
- Update README, AGENTS guides, CHANGELOG.
- Run `pytest` and `flake8`.
- Record outcomes in this plan’s Progress/Decision/Surprises/Outcomes sections.

## Validation and Acceptance

- CLI: `python -m news_coverage.cli build-docx --articles path/to/jsons --quarter "2025 Q4"` produces:
  - `docs/samples/news_coverage_docx/2025 Q4 <Buyer> News Coverage.docx` for each buyer with at least one strong/valid match.
  - A single `needs_review.txt` (or .md) listing blocked/weak items with reasons.
- Visual check: open one generated DOCX and confirm header text, section numbering, grouping, and styling closely match the WBD Q2 template.
- Tests: `pytest` passes; `flake8` clean.

## Idempotence and Recovery

- Re-running the CLI with the same inputs overwrites the generated DOCXs/Needs review file safely.
- No ingest files are mutated unless explicitly enabled; failures in one article should still produce other buyers’ docs and log issues in Needs review.

## Artifacts and Notes

- Paths to generated files (after run): `docs/samples/news_coverage_docx/2025 Q4 <Buyer> News Coverage.docx`, `docs/samples/news_coverage_docx/needs_review.txt`.
- Keep style observations from the template documented inline in code or as comments for future maintainers.

## Interfaces and Dependencies

- New dependency: `python-docx`.
- New CLI command: `build-docx` under `news_coverage.cli`.
- Uses existing agent pipeline (`agent_runner.run_with_agent`) for re-summarization; relies on `classification_notes` for section mapping.
- Keyword routing module exposes functions: `match_buyers(article) -> (strong_matches, weak_matches)`.
- DOCX writer consumes normalized records: title, summary bullets, section, subheading, medium lane, `published_at`, URL, buyer matches.
