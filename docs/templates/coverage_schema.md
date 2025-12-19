# Coverage Schema (Major Buyers)

This schema defines the payload the Chrome extension (and any other intake) must send to the backend. It mirrors the structure used in prior quarterly coverage docs so we can drop items into the right section without manual cleanup.

## Top-level fields

- `company` (required): one of the major buyers `Amazon | Apple | Comcast/NBCU | Disney | Netflix | Paramount | Sony | WBD | A24 | Lionsgate | Unknown`. Use `Unknown` when no clear match.
- `company_match_confidence`: 0-1 score from the classifier.
- `company_raw`: The literal string matched in the article (useful for imprints or label names).
- `quarter` (required): Calendar quarter label in `YYYY Q#` form (e.g., `2025 Q1`).
- `quarter_inferred_from`: `published_at` (default), `title`, or `user_override`.
- `title` (required): Article headline.
- `dek`: Optional subheadline.
- `source` (required): Publisher name (Deadline, Variety, etc.).
- `url` (required): Canonical article URL.
- `published_at` (required): Publication date `YYYY-MM-DD` (inherited by all facts).
- `captured_at`: When the extension grabbed it (ISO date-time).
- `byline`: Author text.
- `body`: Plain-text article body (for re-summarization).
- `summary` (deprecated): Single-summary text for legacy single-category runs. Prefer `facts[].summary_bullets`.
- `bullet_points` (deprecated): Single bullet list for legacy single-category runs. Prefer `facts[].summary_bullets`.
- `tags`, `people`, `works`, `geography`, `language`: Optional metadata for filtering and deduping.
- `is_highlight_candidate`: Flag to bubble items into the Highlights section.
- `importance`: `high | medium | low` ordering hint.
- `classification_notes`: Free-text notes on why the article-level classification was chosen.
- `ingest_source`: `chrome_extension | feedly | manual_upload | test_fixture`.
- `ingest_version`: Version of the ingest tool/extension.
- `duplicate_of`: Present when the ingest step skipped the article because the URL was already stored for the same company/quarter.
- `facts` (required): Array of fact objects capturing per-fact category and summary. Order is preserved from the model output. Must contain at least one fact.

## Fact fields (inside `facts[]`)

- `fact_id` (required): Stable identifier within the article (e.g., `fact-1`).
- `category_path` (required): Full classifier-style path with arrows (e.g., `Content, Deals, Distribution -> TV -> Renewals`).
- `section` (required): One of `Highlights | Org | Content / Deals / Distribution | Strategy & Miscellaneous News | Investor Relations | M&A` derived from `category_path`.
- `subheading`: One of `General News & Strategy | Exec Changes | Development | Greenlights | Pickups | Dating | Renewals | Cancellations | Film | TV | International | Sports | Podcasts | Strategy | Quarterly Earnings | Company Materials | News Coverage | None`.
- `company`: Company for this fact; defaults to the article-level company if not provided.
- `quarter`: Quarter for this fact; defaults to the article-level quarter if not provided.
- `published_at`: Article publish date (carried through for convenience; no per-fact dating logic).
- `content_line` (required): Lead line for this fact (used in Category/Content display).
- `summary_bullets` (required): Bullet list for this fact (first bullet mirrors `content_line`).

## Quarter inference rules (calendar, not fiscal)

- Q1 = Jan 1-Mar 31
- Q2 = Apr 1-Jun 30
- Q3 = Jul 1-Sep 30
- Q4 = Oct 1-Dec 31

Default: derive from `published_at` in the article's local timezone when available; otherwise treat the date as UTC. If the article title explicitly states a quarter (e.g., "Q3 2025 earnings"), prefer that and set `quarter_inferred_from` to `title`. The user can override in the popup; mark overrides with `user_override`.

## Section mapping cheatsheet

- Highlights: Only the 3-7 most significant items per quarter; set `is_highlight_candidate=true`.
- Org: `Exec Changes` subheading; promotions, hires, exits.
- Content / Deals / Distribution: Use `General News & Strategy`, `Development`, `Greenlights`, `Pickups`, `Dating`, `Renewals`, `Cancellations`, optionally `Film`, `TV`, `International`, `Sports`, `Podcasts` when the article is clearly medium-specific.
- Strategy & Miscellaneous News: Broader corporate strategy, product shifts, partnerships that are not content-specific.
- Investor Relations: `Quarterly Earnings`, `Company Materials` (reports, calls), `News Coverage` (press recaps of earnings).
- M&A: Acquisitions, divestitures, significant equity investments; use when the deal is company-level, not just title-level rights.

## Example payload (matches the JSON Schema example)

```
{
  "id": "b7c2c1c0-6e3b-4c9c-8f91-6a6fd7c6d5f9",
  "company": "A24",
  "company_match_confidence": 0.88,
  "company_raw": "A24",
  "quarter": "2025 Q1",
  "quarter_inferred_from": "published_at",
  "title": "A24 expands theatrical slate with new genre label",
  "dek": "Indie powerhouse eyes horror-first pipeline",
  "source": "Variety",
  "url": "https://www.variety.com/a24-expands-genre-label",
  "published_at": "2025-01-15",
  "captured_at": "2025-12-04T23:22:00Z",
  "byline": "Jane Reporter",
  "facts": [
    {
      "fact_id": "fact-1",
      "category_path": "Content, Deals & Distribution -> Film -> Greenlights",
      "section": "Content / Deals / Distribution",
      "subheading": "Greenlights",
      "company": "A24",
      "quarter": "2025 Q1",
      "published_at": "2025-01-15",
      "content_line": "A24 is launching a new horror-focused label with multiple greenlit projects.",
      "summary_bullets": [
        "A24 is launching a new horror-focused label with multiple greenlit projects."
      ]
    }
  ],
  "tags": ["horror", "slate", "label"],
  "people": ["Daniel Katz"],
  "works": ["New Horror Project"],
  "geography": ["US"],
  "language": "en",
  "is_highlight_candidate": true,
  "importance": "high",
  "classification_notes": "Matched company by exact name; section chosen via keyword 'slate' + 'label'.",
  "ingest_source": "chrome_extension",
  "ingest_version": "0.1.0"
}
```

## Usage guidance

- If the classifier cannot decide the subheading, default to `General News & Strategy` and set `classification_notes`.
- If multiple companies appear, pick the primary focus; when coverage is balanced, default to the highest-priority buyer from the list above or set `company="Unknown"` and let the reviewer choose.
- When the article predates the target quarter but is still contextually relevant (e.g., a deal announced last quarter), keep the original `published_at` but allow the reviewer to override `quarter` in the popup.
- Strip page-number artifacts like "Error! No bookmark name given." when generating section headers.
- Keep fields ASCII; avoid smart quotes to prevent encoding mismatches in downstream DOCX generation.

## File locations

- JSON Schema: `docs/templates/coverage_schema.json`
- Human-readable guide (this file): `docs/templates/coverage_schema.md`
