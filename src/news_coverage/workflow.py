"""Coordinator-driven workflow for entertainment news coverage.

A single coordinator orchestrates specialist steps:
- classify (section/subheading via fine-tuned model + heuristics for company/quarter)
- summarize (prompt-routed)
- format (Markdown bullets)
- ingest (schema validation + JSONL storage)

Defaults call the OpenAI API and therefore need `OPENAI_API_KEY`, but injected tools
and/or a provided client allow offline or preconfigured usage for tests.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
import re
from typing import Callable, List, Optional

from openai import OpenAI

from .config import get_settings
from .buyer_routing import BUYER_KEYWORDS, match_buyers
from .file_lock import locked_path
from .models import Article
from .schema import validate_article_payload
from .server import _ensure_parent, _jsonl_path

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
_DATE_TEXT_PATTERN = r"(0?[1-9]|1[0-2])/(0?[1-9]|[12][0-9]|3[01])(?:/(\d{2}|\d{4}))?"
DATE_PAREN_PATTERN = re.compile(rf"\(\s*{_DATE_TEXT_PATTERN}\s*\)")
DATE_LINK_PAREN_PATTERN = re.compile(rf"\(\s*\[\s*{_DATE_TEXT_PATTERN}\s*\]\(")


# --- Data containers -------------------------------------------------------

@dataclass
class ClassificationResult:
    category: str
    section: str
    subheading: str | None
    confidence: float | None
    company: str
    quarter: str


@dataclass
class SummaryResult:
    bullets: List[str]
    facts: List["FactResult"]
    tone: str | None = None
    takeaway: str | None = None


@dataclass
class FactResult:
    fact_id: str
    category_path: str
    section: str
    subheading: str | None
    company: str
    quarter: str
    published_at: date
    content_line: str
    summary_bullets: List[str]


@dataclass
class IngestResult:
    stored_path: Path
    duplicate_of: str | None = None


@dataclass
class PipelineResult:
    markdown: str
    classification: ClassificationResult
    summary: SummaryResult
    ingest: IngestResult


# --- Helpers --------------------------------------------------------------

def build_client(api_key: Optional[str] = None) -> OpenAI:
    """Create an OpenAI client; separated for easier testing."""
    return OpenAI(api_key=api_key)


def _require_api_key(settings) -> str:
    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is required. Set it in the environment or .env file."
        )
    return settings.openai_api_key


def _infer_quarter(published_at: datetime) -> str:
    q = (published_at.month - 1) // 3 + 1
    return f"{published_at.year} Q{q}"


def _infer_company(article: Article) -> str:
    """
    Infer the primary buyer/company from the article using keyword routing.

    Strong matches come from the title, URL host, or the first ~400 chars of
    the body; weak matches come from the rest of the body. We pick the first
    match according to the BUYER_KEYWORDS priority order; fall back to Unknown.
    """

    priority = list(BUYER_KEYWORDS.keys())
    matches = match_buyers(article)

    for buyer in priority:
        if buyer in matches.strong:
            return buyer
    for buyer in priority:
        if buyer in matches.weak:
            return buyer
    return "Unknown"


def _normalize_category(raw: str | dict) -> tuple[str, float | None]:
    """Accept JSON or plain path; return path string and optional confidence."""
    if isinstance(raw, dict):
        return raw.get("category", ""), raw.get("confidence")
    if not isinstance(raw, str):
        return "", None
    txt = raw.strip()
    if txt.startswith("{"):
        try:
            data = json.loads(txt)
            return data.get("category", ""), data.get("confidence")
        except json.JSONDecodeError:
            pass
    return txt, None


def _normalize_highlights(section: str) -> str:
    if section.lower().startswith("highlights"):
        return "Highlights"
    return section


def _format_category_display(category_path: str) -> str:
    """
    Render the classifier category path for display.

    Examples:
    - "Content, Deals & Distribution -> TV -> Development"
      becomes "Content, Deals, Distribution -> TV -> Development"
    - Unknown or empty paths fall back to "General News & Strategy".
    """
    if not category_path:
        return "General News & Strategy"

    raw_parts = [part.strip() for part in category_path.split("->")]
    parts: list[str] = []
    for idx, part in enumerate(raw_parts):
        if idx == 0 and part.startswith("Content, Deals & Distribution"):
            parts.append("Content, Deals, Distribution")
            continue
        if part == "Deals & Distribution":
            parts.append("Deals, Distribution")
            continue
        slash_parts = [p.strip() for p in part.split("/") if p.strip()]
        if len(slash_parts) > 1:
            parts.extend(slash_parts)
        else:
            parts.append(part)
    return " -> ".join(parts)


def _parse_category_path(path: str) -> tuple[str, str | None]:
    """
    Map classifier path to schema section/subheading.
    Example input: "Content, Deals & Distribution -> TV -> Greenlights"
    """
    allowed_subheadings = {
        "General News & Strategy",
        "Exec Changes",
        "Development",
        "Greenlights",
        "Pickups",
        "Dating",
        "Renewals",
        "Cancellations",
        "Film",
        "TV",
        "International",
        "Sports",
        "Podcasts",
        "Strategy",
        "Misc. News",
        "Quarterly Earnings",
        "Company Materials",
        "News Coverage",
        "Analyst Perspective",
        "IR Conferences",
        "None",
    }
    if not path:
        return "Strategy & Miscellaneous News", "General News & Strategy"
    parts = [p.strip() for p in path.split("->")]
    top = parts[0]
    section_map = {
        "Content, Deals & Distribution": "Content / Deals / Distribution",
        "Strategy & Miscellaneous News": "Strategy & Miscellaneous News",
        "Investor Relations": "Investor Relations",
        "Org": "Org",
        "M&A": "M&A",
        "Highlights From The Quarter": "Highlights",
        "Highlights From This Quarter": "Highlights",
        "Highlights": "Highlights",
    }
    section = section_map.get(top, top)
    subheading = parts[-1] if len(parts) > 1 else None
    subheading = subheading if subheading != section else None
    # Default fallback when classifier gives a deep path like "... -> General News & Strategy"
    if not subheading and len(parts) > 1:
        subheading = parts[1]
    if subheading:
        lowered = subheading.lower()
        if lowered.startswith("analyst"):
            subheading = "Analyst Perspective"
        elif "conference" in lowered:
            subheading = "IR Conferences"
        elif "misc" in lowered:
            subheading = "Misc. News"
        elif lowered.startswith("strategy"):
            subheading = "Strategy"
        if subheading not in allowed_subheadings:
            subheading = "General News & Strategy"
    return _normalize_highlights(section), subheading


def _load_prompt_file(filename: str) -> str:
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8")


def _split_bullets(text: str) -> List[str]:
    bullets: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped[0] in "-•–—*":
            stripped = stripped.lstrip("-•–—* ").strip()
        bullets.append(stripped)
    return bullets


def _response_text_or_raise(response: object, *, step: str) -> str:
    """Extract response text or raise a clear error when output is missing."""
    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text
    if isinstance(text, str) and text == "":
        # Treat explicit empty text as missing output.
        text = None

    status = getattr(response, "status", None)
    if status == "incomplete":
        details = getattr(response, "incomplete_details", None)
        reason = getattr(details, "reason", None) if details else None
        hint = ""
        if reason == "max_output_tokens":
            hint = (
                " Increase MAX_TOKENS, unset it (or set to 0) to remove the cap, "
                "or reduce the article length."
            )
        raise RuntimeError(
            f"{step} response incomplete (reason={reason}).{hint}"
        )

    err = getattr(response, "error", None)
    if err:
        raise RuntimeError(f"{step} response error: {err}")

    raise RuntimeError(f"{step} response missing output text.")


# --- Fact parsing helpers -------------------------------------------------

FACT_LABEL_MAP: dict[str, str] = {
    "greenlights": "Greenlights",
    "greenlight": "Greenlights",
    "renewals": "Renewals",
    "renewal": "Renewals",
    "development": "Development",
    "pickup": "Pickups",
    "pickups": "Pickups",
    "cancellations": "Cancellations",
    "cancellation": "Cancellations",
    "dating": "Dating",
    "exec changes": "Exec Changes",
    "exec change": "Exec Changes",
    "general": "General News & Strategy",
}


def _label_from_bullet(text: str) -> tuple[str | None, str]:
    """
    Extract a leading label like 'Greenlights: Foo' -> ('Greenlights', 'Foo').
    If no label is found, returns (None, original_text).
    """
    if ":" in text:
        possible, rest = text.split(":", 1)
        key = possible.strip().lower()
        if key in FACT_LABEL_MAP:
            return FACT_LABEL_MAP[key], rest.strip()
    return None, text.strip()


def _build_fact_category(base_category: str, label: str | None) -> tuple[str, str, str | None]:
    """
    Combine the classifier's base path with the label-derived subheading.
    Keeps the top-level/medium from the classifier when available.
    """
    if not base_category:
        return "General News & Strategy", "Strategy & Miscellaneous News", "General News & Strategy"
    parts_full = [p.strip() for p in base_category.split("->")]
    base_parts = parts_full[:-1] if len(parts_full) > 1 else parts_full
    fallback_sub = parts_full[-1] if parts_full else None
    subheading = label or fallback_sub
    category_path = " -> ".join(base_parts + ([subheading] if subheading else []))
    section, parsed_sub = _parse_category_path(category_path)
    return category_path, section, parsed_sub


def _assemble_facts(
    bullets: List[str],
    classification: "ClassificationResult",
    article: Article,
) -> List[FactResult]:
    """
    Turn labeled bullets into FactResult objects, preserving order.
    """
    facts: List[FactResult] = []
    for idx, raw in enumerate(bullets, start=1):
        label, content = _label_from_bullet(raw)
        category_path, section, subheading = _build_fact_category(classification.category, label)
        fact = FactResult(
            fact_id=f"fact-{idx}",
            category_path=category_path,
            section=section,
            subheading=subheading,
            company=classification.company,
            quarter=classification.quarter,
            published_at=article.published_at.date() if article.published_at else date.today(),
            content_line=content,
            summary_bullets=[content],
        )
        facts.append(fact)
    return facts


def _fallback_fact_for_empty_summary(
    article: Article,
    classification: "ClassificationResult",
    summary: "SummaryResult",
) -> FactResult:
    content_line = (summary.takeaway or "").strip()
    if not content_line:
        content_line = next((b.strip() for b in summary.bullets if b.strip()), "")
    if not content_line:
        content_line = article.title.strip()
    if not content_line:
        content_line = "Summary unavailable."

    category_path = (
        classification.category or "Strategy & Miscellaneous News -> General News & Strategy"
    )
    section, subheading = _parse_category_path(category_path)
    published_at = article.published_at.date() if article.published_at else date.today()
    return FactResult(
        fact_id="fact-1",
        category_path=category_path,
        section=section,
        subheading=subheading or "General News & Strategy",
        company=classification.company,
        quarter=classification.quarter,
        published_at=published_at,
        content_line=content_line,
        summary_bullets=[content_line],
    )


def _facts_for_article(
    article: Article,
    classification: "ClassificationResult",
    summary: "SummaryResult",
) -> List[FactResult]:
    facts = summary.facts or _assemble_facts(summary.bullets, classification, article)
    return facts or [_fallback_fact_for_empty_summary(article, classification, summary)]


def _extract_summary_chunks(text: str, expected_count: int) -> List[str]:
    """
    Split a multi-article model response into one chunk per article.

    The original implementation assumed the model would echo literal
    "Article <n>" markers and then zipped the resulting list with the
    requested articles. When the model returned a single block (or used
    different phrasing), the zip silently dropped articles beyond the
    last chunk. This helper enforces a 1:1 mapping and raises when the
    output cannot be aligned, preventing silent data loss.
    """

    markers = list(
        re.finditer(r"(?im)^\s*(?:article|story)\s*\d+\s*[:\-]\s*", text)
    )
    chunks: List[str] = []
    if markers:
        for idx, match in enumerate(markers):
            start = match.end()
            end = markers[idx + 1].start() if idx + 1 < len(markers) else len(text)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

    if not chunks:
        chunks = [block.strip() for block in re.split(r"\n{2,}", text) if block.strip()]

    if expected_count == 1:
        return [text.strip()]

    if len(chunks) != expected_count:
        raise ValueError(
            "Model returned {got} summary block(s) for {expected} article(s); "
            "cannot align summaries safely.".format(
                got=len(chunks), expected=expected_count
            )
        )

    return chunks


# --- Tool implementations -------------------------------------------------


def classify_article(article: Article, client: OpenAI) -> ClassificationResult:
    settings = get_settings()
    system_prompt = (
        "You are a news-trade classifier.\n"
        "Return exactly one JSON object with two keys:\n\n"
        '{"category":"<full_path_string>", "confidence":<0-1 float>}\n'
        "Use the exact category spelling and arrows -> from the allowed set.\n\n"
        "confidence = probability (0-1) that the chosen category is correct, "
        "rounded to two decimals.\n\n"
        "No other keys, no extra text."
    )
    user_prompt = (
        f"Title: {article.title}\n"
        f"Source: {article.source}\n"
        f"Content: {article.content[:4000]}"
    )
    response = client.responses.create(
        model=settings.classifier_model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_output_tokens=200,
        temperature=0.0,
    )
    category_raw = _response_text_or_raise(response, step="Classifier")
    category, conf = _normalize_category(category_raw)
    section, subheading = _parse_category_path(category)
    company = _infer_company(article)
    if not article.published_at:
        raise ValueError("published_at is required to infer quarter.")
    quarter = _infer_quarter(article.published_at)
    return ClassificationResult(
        category=category,
        section=section,
        subheading=subheading,
        confidence=conf,
        company=company,
        quarter=quarter,
    )


def summarize_article(article: Article, prompt_name: str, client: OpenAI) -> SummaryResult:
    settings = get_settings()
    prompt_text = _load_prompt_file(prompt_name)
    user_message = (
        f"Title: {article.title}\nSource: {article.source}\n"
        f"Published: {article.published_at.isoformat() if article.published_at else 'unknown'}\n\n"
        f"{article.content}"
    )
    request_kwargs = {
        "model": settings.summarizer_model,
        "input": [
            {"role": "system", "content": prompt_text},
            {"role": "user", "content": user_message},
        ],
    }
    if settings.max_tokens and settings.max_tokens > 0:
        request_kwargs["max_output_tokens"] = settings.max_tokens
    # gpt-5-mini rejects the temperature parameter; omit it for compatibility.
    if settings.summarizer_model != "gpt-5-mini":
        request_kwargs["temperature"] = settings.temperature

    response = client.responses.create(**request_kwargs)
    text_output = _response_text_or_raise(response, step="Summarizer")
    bullets = _split_bullets(text_output)
    return SummaryResult(bullets=bullets, facts=[])


def summarize_articles_batch(
    articles: List[Article],
    prompt_names: List[str] | str,
    client: OpenAI,
) -> List[SummaryResult]:
    """
    Summarize multiple articles in a single model call, preserving order.

    If the model response cannot be aligned one-to-one with the input
    list of articles, a ValueError is raised instead of silently dropping
    items, preventing data loss.
    """

    if not articles:
        return []

    settings = get_settings()
    if isinstance(prompt_names, str):
        prompt_list = [prompt_names] * len(articles)
    else:
        prompt_list = list(prompt_names)

    if len(prompt_list) != len(articles):
        raise ValueError("prompt_names must match number of articles.")

    prompt_texts = [_load_prompt_file(name) for name in prompt_list]
    system_prompt = (
        "You will receive multiple articles. Each article includes its own "
        "instructions. For every article, follow the provided instructions to "
        "produce bullet points, and label each block as 'Article <n>:'."
    )

    user_sections = []
    for idx, article in enumerate(articles, start=1):
        published = article.published_at.isoformat() if article.published_at else "unknown"
        user_sections.append(
            f"Article {idx}\nInstructions:\n{prompt_texts[idx - 1]}\n\n"
            f"Title: {article.title}\nSource: {article.source}\n"
            f"Published: {published}\n\n{article.content}"
        )

    request_kwargs = {
        "model": settings.summarizer_model,
        "input": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "\n\n".join(user_sections)},
        ],
    }
    if settings.max_tokens and settings.max_tokens > 0:
        request_kwargs["max_output_tokens"] = settings.max_tokens * max(1, len(articles))
    if settings.summarizer_model != "gpt-5-mini":
        request_kwargs["temperature"] = settings.temperature

    response = client.responses.create(**request_kwargs)
    text_output = _response_text_or_raise(response, step="Summarizer (batch)")
    chunks = _extract_summary_chunks(text_output, len(articles))
    return [SummaryResult(bullets=_split_bullets(chunk), facts=[]) for chunk in chunks]


def _format_date_for_display(dt: date) -> str:
    """Return M/D (no leading zeros) for display alongside coverage links."""
    return f"{dt.month}/{dt.day}"


def _format_iso_timestamp(dt: datetime | None) -> str:
    """Return an ISO 8601 timestamp; assume UTC when naive or missing."""
    if dt is None:
        return datetime.now(timezone.utc).isoformat()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).isoformat()
    return dt.isoformat()


def _final_output_path() -> Path:
    """
    Resolve the target markdown file for appended final outputs.

    Defaults to docs/templates/final_output.md at the repo root, but can be
    overridden via FINAL_OUTPUT_PATH for tests or alternative deployments.
    """
    settings = get_settings()
    if settings.final_output_path:
        return Path(settings.final_output_path).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "docs" / "templates" / "final_output.md"


def _ordered_buyers(buyers: set[str]) -> list[str]:
    """Return buyer names ordered by keyword priority, then alphabetically for extras."""
    priority = list(BUYER_KEYWORDS.keys())
    ordered = [b for b in priority if b in buyers]
    extras = sorted(buyers - set(priority))
    return ordered + extras


def _format_summary_lines(bullets: list[str], date_link: str, url: str) -> list[str]:
    """Return summary lines, linking/adding the article date where needed."""

    if not bullets:
        return [""]

    lines: list[str] = []
    for bullet in bullets:
        text = bullet.strip()
        if not text:
            lines.append(text)
            continue
        text = _linkify_date_parentheticals(text, url)
        if text and not _has_date_marker(text):
            text = f"{text} ({date_link})"
        lines.append(text)
    return lines


def _fact_summary_bullets(fact: "FactResult") -> list[str]:
    """
    Return the list of summary bullet strings to render for a fact.

    Prefer `summary_bullets` when present (new schema); fall back to
    `content_line` for backward compatibility.
    """
    bullets = [b for b in (fact.summary_bullets or []) if (b or "").strip()]
    if bullets:
        return bullets
    text = (fact.content_line or "").strip()
    return [text] if text else []


def format_final_output_entry(
    article: Article, classification: ClassificationResult, summary: SummaryResult
) -> str:
    """
    Compose the final-output block used for the markdown log file.

    Mirrors the delivery layout the user requested, with matched buyers,
    one article title, one or more fact blocks (Category + a bulleted Content
    list), an ISO timestamp, and the source URL.

    The Content section is always a bullet list to avoid ambiguous parsing
    when a single fact contains multiple summary bullets.
    """
    matches = match_buyers(article)
    buyer_set = set(matches.strong) | set(matches.weak)
    if classification.company and classification.company != "Unknown":
        buyer_set.add(classification.company)
    ordered_buyers = _ordered_buyers(buyer_set)

    publish_date = article.published_at.date() if article.published_at else date.today()
    date_display = _format_date_for_display(publish_date)
    date_link = f"[{date_display}]({article.url})"
    url = str(article.url)
    facts = _facts_for_article(article, classification, summary)

    iso_timestamp = _format_iso_timestamp(article.published_at)

    lines = [
        f"Matched buyers: {ordered_buyers}",
        "",
        f"Title: {article.title}",
    ]

    for fact in facts:
        category_display = _format_category_display(fact.category_path)
        content_lines = _format_summary_lines(_fact_summary_bullets(fact), date_link, url)
        lines.extend(
            [
                "",
                f"Category: {category_display}",
                "",
                "Content:",
                *([f"- {line}" for line in content_lines] if content_lines else ["-"]),
            ]
        )

    lines.extend(
        [
            "",
            f"Date: ({iso_timestamp})",
            "",
            f"URL: {article.url}",
        ]
    )
    return "\n".join(lines)


def append_final_output_entry(
    article: Article,
    classification: ClassificationResult,
    summary: SummaryResult,
    *,
    destination: Path | None = None,
) -> Path:
    """Append a formatted final-output block to the configured markdown file."""
    entry = format_final_output_entry(article, classification, summary)
    target = destination or _final_output_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with locked_path(target):
        existing_text = target.read_text(encoding="utf-8") if target.exists() else ""
        needs_spacing = bool(existing_text.strip())
        trailing_newlines = len(existing_text) - len(existing_text.rstrip("\n"))
        spacer_count = max(0, 2 - trailing_newlines) if needs_spacing else 0
        spacer = "\n" * spacer_count
        with target.open("a", encoding="utf-8") as f:
            f.write(f"{spacer}{entry}\n")
    return target


def _has_date_parenthetical(text: str) -> bool:
    """Return True when the string already contains a date in parenthesis (M/D[/YY])."""

    return bool(DATE_PAREN_PATTERN.search(text))


def _has_date_marker(text: str) -> bool:
    """
    Return True when the string contains a date marker.

    Supported markers:
    - Plain parenthetical: "(M/D)" or "(M/D/YY)"
    - Linked parenthetical: "([M/D](URL))" or "([M/D/YY](URL))"
    """

    return bool(DATE_PAREN_PATTERN.search(text) or DATE_LINK_PAREN_PATTERN.search(text))


def _linkify_date_parentheticals(text: str, url: str) -> str:
    """Replace plain date parentheticals like "(12/17)" with "([12/17](URL))"."""

    def _replace(match: re.Match[str]) -> str:
        month = int(match.group(1))
        day = int(match.group(2))
        year = match.group(3)
        date_text = f"{month}/{day}" + (f"/{year}" if year else "")
        return f"([{date_text}]({url}))"

    return DATE_PAREN_PATTERN.sub(_replace, text)


def format_markdown(
    article: Article, classification: ClassificationResult, summary: SummaryResult
) -> str:
    """Render delivery-friendly markdown with Title/Category/Content lines."""
    date_value = article.published_at.date() if article.published_at else date.today()
    date_text = _format_date_for_display(date_value)
    date_link = f"[{date_text}]({article.url})"
    url = str(article.url)
    facts = _facts_for_article(article, classification, summary)

    lines = [f"Title: {article.title}"]
    for fact in facts:
        category_display = _format_category_display(fact.category_path)
        content_lines = _format_summary_lines(_fact_summary_bullets(fact), date_link, url)
        lines.append(f"Category: {category_display}")
        lines.extend([f"Content: {line}" for line in (content_lines or [""])])
    return "\n".join(lines)


def ingest_article(
    article: Article,
    classification: ClassificationResult,
    summary: SummaryResult,
) -> IngestResult:
    facts = _facts_for_article(article, classification, summary)
    schema_payload = {
        "company": classification.company,
        "quarter": classification.quarter,
        "title": article.title,
        "source": article.source,
        "url": str(article.url),
        "published_at": (
            article.published_at.date().isoformat()
            if article.published_at
            else date.today().isoformat()
        ),
        "classification_notes": classification.category,
        "facts": [
            {
                "fact_id": fact.fact_id,
                "category_path": fact.category_path,
                "section": fact.section,
                "subheading": fact.subheading or "General News & Strategy",
                "company": fact.company,
                "quarter": fact.quarter,
                "published_at": fact.published_at.isoformat(),
                "content_line": fact.content_line,
                "summary_bullets": fact.summary_bullets,
            }
            for fact in facts
        ],
    }
    validated = validate_article_payload(schema_payload)
    path = _jsonl_path(validated["company"], validated["quarter"])
    with locked_path(path):
        _ensure_parent(path)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(validated, ensure_ascii=False))
            f.write("\n")
    return IngestResult(stored_path=path, duplicate_of=None)


# --- Coordinator ----------------------------------------------------------

ClassifierFn = Callable[[Article, OpenAI], ClassificationResult]
SummarizerFn = Callable[[Article, str, OpenAI], SummaryResult]
FormatterFn = Callable[[Article, ClassificationResult, SummaryResult], str]
IngestFn = Callable[[Article, ClassificationResult, SummaryResult], IngestResult]


# Routing rules are applied in order; the first match wins.
@dataclass(frozen=True)
class RoutingRule:
    name: str
    match_any: tuple[str, ...]
    prompt: str
    formatter: str = "markdown"


DEFAULT_PROMPT = "general_news.txt"
DEFAULT_FORMATTER = "markdown"

# Maps formatter name to callable to keep the routing table declarative.


def format_content_deals(
    article: Article, classification: ClassificationResult, summary: SummaryResult
) -> str:
    """Render multi-title content-deals output.

    The summarizer is expected to emit one line per title. We preserve accents and
    spacing, only appending the article publish date when a line omits a date
    parenthetical. Dates use M/D without leading zeros, per downstream delivery
    requirements.
    """

    publish_date = article.published_at.date() if article.published_at else date.today()
    date_text = _format_date_for_display(publish_date)
    url = str(article.url)
    date_link = f"[{date_text}]({url})"

    rendered_lines: list[str] = []
    for line in summary.bullets:
        trimmed = line.strip()
        if not trimmed:
            continue
        trimmed = _linkify_date_parentheticals(trimmed, url)
        # Append date only when a date marker is missing (ignore other parentheses).
        if not _has_date_marker(trimmed):
            trimmed = f"{trimmed} ({date_link})"
        rendered_lines.append(trimmed)

    return "\n".join(rendered_lines)


FORMATTERS: dict[str, FormatterFn] = {
    "markdown": format_markdown,
    "content_deals": format_content_deals,
}


ROUTING_RULES: tuple[RoutingRule, ...] = (
    RoutingRule("exec_changes", ("exec changes",), "exec_changes.txt"),
    RoutingRule("interview", ("interview",), "interview.txt"),
    RoutingRule("commentary", ("strategy", "commentary"), "commentary.txt"),
    RoutingRule(
        "content_formatter",
        ("greenlights", "development", "renewals", "cancellations", "pickups"),
        "content_formatter.txt",
    ),
)


def _route_prompt_and_formatter(
    classification: ClassificationResult,
    *,
    confidence_floor: float | None = None,
) -> tuple[str, FormatterFn]:
    """
    Choose the prompt and formatter based on classifier output.

    Falls back to the general-news prompt when confidence is below the configured
    floor (or missing) to avoid misrouting.
    """

    settings = get_settings()
    floor = confidence_floor if confidence_floor is not None else settings.routing_confidence_floor
    # If the classifier does not return a confidence score, assume it is confident
    # enough to use the routed prompt instead of falling back to general news.
    if classification.confidence is not None and classification.confidence < floor:
        return DEFAULT_PROMPT, FORMATTERS[DEFAULT_FORMATTER]

    category_lower = classification.category.lower()

    # International content deals / slate announcements should use the content-deals
    # formatter, which preserves multiple titles from the summarizer output.
    if (
        classification.section == "Content / Deals / Distribution"
        and "international" in category_lower
    ):
        return "content_deals.txt", FORMATTERS["content_deals"]

    for rule in ROUTING_RULES:
        if any(token in category_lower for token in rule.match_any):
            formatter_fn = FORMATTERS.get(rule.formatter, FORMATTERS[DEFAULT_FORMATTER])
            return rule.prompt, formatter_fn

    return DEFAULT_PROMPT, FORMATTERS[DEFAULT_FORMATTER]


def _route_prompts_for_batch(
    classifications: List[ClassificationResult],
    *,
    confidence_floor: float | None = None,
) -> List[str]:
    """Return a list of prompt names applying the same routing logic per article."""
    prompts: List[str] = []
    for cls in classifications:
        prompt, _ = _route_prompt_and_formatter(cls, confidence_floor=confidence_floor)
        prompts.append(prompt)
    return prompts


def process_article(
    article: Article,
    client: Optional[OpenAI] = None,
    *,
    classifier_fn: ClassifierFn | None = None,
    summarizer_fn: SummarizerFn | None = None,
    formatter_fn: FormatterFn | None = None,
    ingest_fn: IngestFn | None = None,
) -> PipelineResult:
    """
    Run the full pipeline for a single article.

    Raises on any failure. Always ingests and appends the result.
    """
    settings = get_settings()
    classifier_fn = classifier_fn or classify_article
    summarizer_fn = summarizer_fn or summarize_article
    formatter_fn = formatter_fn
    ingest_fn = ingest_fn or ingest_article

    needs_openai_client = client is None and (
        classifier_fn is classify_article or summarizer_fn is summarize_article
    )
    if needs_openai_client:
        api_key = _require_api_key(settings)
        client = build_client(api_key)

    classification = classifier_fn(article, client)
    prompt_name, routed_formatter = _route_prompt_and_formatter(classification)
    active_formatter = formatter_fn or routed_formatter
    summary = summarizer_fn(article, prompt_name, client)
    if not summary.facts:
        summary.facts = _assemble_facts(summary.bullets, classification, article)
    markdown = active_formatter(article, classification, summary)
    ingest_result = ingest_fn(article, classification, summary)

    append_final_output_entry(article, classification, summary)

    return PipelineResult(
        markdown=markdown,
        classification=classification,
        summary=summary,
        ingest=ingest_result,
    )
