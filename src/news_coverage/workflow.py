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
from datetime import date, datetime
from pathlib import Path
import re
from typing import Callable, List, Optional

from openai import OpenAI

from .config import get_settings
from .models import Article
from .schema import validate_article_payload
from .server import _ensure_parent, _is_duplicate, _jsonl_path

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


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
    tone: str | None = None
    takeaway: str | None = None


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
    text = f"{article.title} {article.content}".lower()
    if "a24" in text:
        return "A24"
    if "lionsgate" in text or "lions gate" in text:
        return "Lionsgate"
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
    Render the classifier category path using arrows and friendly splits.

    Examples:
    - "Content, Deals & Distribution -> TV -> Development"
      becomes "Content -> Deals -> Distribution -> TV -> Development"
    - Unknown or empty paths fall back to "General News & Strategy".
    """
    if not category_path:
        return "General News & Strategy"

    raw_parts = [part.strip() for part in category_path.split("->")]
    parts: list[str] = []
    for idx, part in enumerate(raw_parts):
        if idx == 0 and part.startswith("Content, Deals & Distribution"):
            parts.extend(["Content", "Deals", "Distribution"])
            continue
        if part == "Deals & Distribution":
            parts.extend(["Deals", "Distribution"])
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
    category_raw = getattr(response, "output_text", "") or str(response)
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
        "max_output_tokens": settings.max_tokens,
    }
    # gpt-5-mini rejects the temperature parameter; omit it for compatibility.
    if settings.summarizer_model != "gpt-5-mini":
        request_kwargs["temperature"] = settings.temperature

    response = client.responses.create(**request_kwargs)
    text_output = getattr(response, "output_text", "") or str(response)
    bullets = _split_bullets(text_output)
    return SummaryResult(bullets=bullets)


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
        "max_output_tokens": settings.max_tokens * max(1, len(articles)),
    }
    if settings.summarizer_model != "gpt-5-mini":
        request_kwargs["temperature"] = settings.temperature

    response = client.responses.create(**request_kwargs)
    text_output = getattr(response, "output_text", "") or str(response)
    chunks = _extract_summary_chunks(text_output, len(articles))
    return [SummaryResult(bullets=_split_bullets(chunk)) for chunk in chunks]


def _format_date_for_display(dt: date) -> str:
    """Return M/D (no leading zeros) for display alongside coverage links."""
    return f"{dt.month}/{dt.day}"


def format_markdown(
    article: Article, classification: ClassificationResult, summary: SummaryResult
) -> str:
    """Render delivery-friendly markdown with Title/Category/Content lines."""
    category_display = _format_category_display(classification.category)
    date_value = article.published_at.date() if article.published_at else date.today()
    date_text = _format_date_for_display(date_value)
    date_link = f"[{date_text}]({article.url})"
    content_summary = summary.bullets[0] if summary.bullets else ""

    lines = [
        f"Title: {article.title}",
        f"Category: {category_display}",
        f"Content: {content_summary} ({date_link})",
    ]
    return "\n".join(lines)


def ingest_article(
    article: Article,
    classification: ClassificationResult,
    summary: SummaryResult,
    *,
    skip_duplicate: bool = False,
) -> IngestResult:
    schema_payload = {
        "company": classification.company,
        "quarter": classification.quarter,
        "section": classification.section,
        "title": article.title,
        "source": article.source,
        "url": str(article.url),
        "published_at": (
            article.published_at.date().isoformat()
            if article.published_at
            else date.today().isoformat()
        ),
        "subheading": classification.subheading or "General News & Strategy",
        "summary": " ".join(summary.bullets[:3]) if summary.bullets else "",
        "bullet_points": summary.bullets,
        "classification_notes": classification.category,
    }
    validated = validate_article_payload(schema_payload)
    path = _jsonl_path(validated["company"], validated["quarter"])
    duplicate_id = None if skip_duplicate else _is_duplicate(path, validated["url"])
    if duplicate_id:
        return IngestResult(stored_path=path, duplicate_of=duplicate_id)

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
FORMATTERS: dict[str, FormatterFn] = {"markdown": format_markdown}


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

    Raises on any failure. If a duplicate is detected, returns result with duplicate_of set.
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
    markdown = active_formatter(article, classification, summary)
    ingest_result = ingest_fn(article, classification, summary)

    return PipelineResult(
        markdown=markdown,
        classification=classification,
        summary=summary,
        ingest=ingest_result,
    )
