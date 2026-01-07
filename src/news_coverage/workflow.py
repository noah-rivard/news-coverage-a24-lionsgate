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

from contextlib import contextmanager
from contextvars import ContextVar
import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
import re
from typing import Callable, Iterator, List, Optional

from openai import OpenAI

from .config import get_settings
from .buyer_routing import (
    BUYER_KEYWORDS,
    buyers_from_keywords,
    match_buyers,
    parse_buyers_of_interest,
    score_buyer_matches,
)
from .file_lock import locked_path
from .models import Article
from .schema import validate_article_payload
from .server import _ensure_parent, _jsonl_contains_url, _jsonl_path

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
_DATE_TEXT_PATTERN = r"(0?[1-9]|1[0-2])/(0?[1-9]|[12][0-9]|3[01])(?:/(\d{2}|\d{4}))?"
DATE_PAREN_PATTERN = re.compile(rf"\(\s*{_DATE_TEXT_PATTERN}\s*\)")
DATE_LINK_PAREN_PATTERN = re.compile(rf"\(\s*\[\s*{_DATE_TEXT_PATTERN}\s*\]\(")
SUMMARY_RETRY_CHAR_LIMITS = (12000, 6000)
_DATE_LINK_TAIL_PATTERN = re.compile(
    rf"\s*\(\s*\[\s*{_DATE_TEXT_PATTERN}\s*\]\([^)]+\)\s*\)\s*$"
)
_DATE_PAREN_TAIL_PATTERN = re.compile(rf"\s*\(\s*{_DATE_TEXT_PATTERN}\s*\)\s*$")


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
    openai_response_ids: dict[str, list[str]] = field(default_factory=dict)


OpenAIResponseIdMap = dict[str, list[str]]
_OPENAI_RESPONSE_IDS: ContextVar[OpenAIResponseIdMap | None] = ContextVar(
    "news_coverage_openai_response_ids", default=None
)


def _record_openai_response_id(step: str, response: object) -> None:
    response_id_map = _OPENAI_RESPONSE_IDS.get()
    if response_id_map is None:
        return
    response_id = getattr(response, "id", None)
    if not response_id:
        return
    response_id_map.setdefault(step, []).append(str(response_id))


@contextmanager
def collect_openai_response_ids() -> Iterator[OpenAIResponseIdMap]:
    """
    Collect `response.id` values from OpenAI Responses calls made inside the context.

    Call sites record IDs opportunistically; injected tools that don't use the OpenAI
    client will leave the mapping empty.
    """
    mapping: OpenAIResponseIdMap = {}
    token = _OPENAI_RESPONSE_IDS.set(mapping)
    try:
        yield mapping
    finally:
        _OPENAI_RESPONSE_IDS.reset(token)


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


_MOJIBAKE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("\u0192?Ts", "'s"),  # "ƒ?Ts" -> "'s"
    ("\u0192?~s", "'s"),  # "ƒ?~s" -> "'s"
    ("\u0192?s", "'s"),  # "ƒ?s" -> "'s"
    ("\u0192?T", "'"),  # "ƒ?T" -> "'"
    ("\u0192?o", '"'),  # "ƒ?o" -> '"'
    ("\u0192??", '"'),  # "ƒ??" -> '"'
    ("\u0192?\u00dd", "--"),  # "ƒ?Ý" -> "--"
    ("\u00e2\u20ac\u0153", '"'),  # "â€œ" -> '"'
    ("\u00e2\u20ac\u009d", '"'),  # "â€�" -> '"'
    ("\u00e2\u20ac\u0099", "'"),  # "â€™" -> "'"
    ("\u00e2\u20ac\u0098", "'"),  # "â€˜" -> "'"
    ("\u00e2\u20ac\u201d", "--"),  # "â€”" -> "--"
    ("\u00e2\u20ac\u201c", "-"),  # "â€“" -> "-"
    ("\u00c2", ""),  # stray "Â"
)


def normalize_article_text(text: str) -> tuple[str, int]:
    """
    Normalize common mojibake sequences into ASCII-safe punctuation.

    Returns the normalized text and a count of replacements performed.
    """
    if not text:
        return text, 0
    normalized = text
    replacements = 0
    for raw, cleaned in _MOJIBAKE_REPLACEMENTS:
        if raw in normalized:
            replacements += normalized.count(raw)
            normalized = normalized.replace(raw, cleaned)
    return normalized, replacements


def normalize_article(article: Article) -> tuple[Article, str | None]:
    """
    Return an Article with normalized title/content plus a short note for logs.
    """
    title, title_replacements = normalize_article_text(article.title or "")
    content, content_replacements = normalize_article_text(article.content or "")
    replacements = title_replacements + content_replacements
    if replacements == 0 and title == article.title and content == article.content:
        return article, None
    length_delta = (len(title) - len(article.title)) + (len(content) - len(article.content))
    fields = []
    if title != article.title:
        fields.append("title")
    if content != article.content:
        fields.append("content")
    note = (
        "Normalization: applied; fields={fields}; replacements={count}; length_delta={delta}"
    ).format(fields=",".join(fields), count=replacements, delta=length_delta)
    normalized_article = Article(
        title=title,
        source=article.source,
        url=article.url,
        published_at=article.published_at,
        content=content,
    )
    return normalized_article, note


def _infer_quarter(published_at: datetime) -> str:
    q = (published_at.month - 1) // 3 + 1
    return f"{published_at.year} Q{q}"


def _infer_company(article: Article) -> str:
    """
    Infer the primary buyer/company from the article using keyword routing.

    Prefer matches in the title or lead over deeper body-only mentions,
    using buyer keyword priority only as a tie-breaker.
    """
    scores = score_buyer_matches(article)
    if not scores:
        return "Unknown"
    priority = list(BUYER_KEYWORDS.keys())
    priority_index = {buyer: idx for idx, buyer in enumerate(priority)}
    scores_sorted = sorted(
        scores,
        key=lambda score: (
            -score.score,
            score.earliest_pos,
            priority_index.get(score.buyer, 9999),
        ),
    )
    return scores_sorted[0].buyer


def build_classification_override(
    article: Article,
    *,
    category: str,
    company: str | None = None,
    quarter: str | None = None,
    confidence: float | None = 1.0,
) -> "ClassificationResult":
    """
    Build a ClassificationResult without calling the classifier.

    Intended for manual rerouting when a user wants to force a specific
    category/prompt path for a given article.
    """
    category_path = str(category or "").strip()
    if not category_path:
        raise ValueError("override category is required.")
    section, subheading = _parse_category_path(category_path)

    derived_company = company.strip() if company else _infer_company(article)
    if quarter:
        derived_quarter = quarter.strip()
    else:
        if not article.published_at:
            raise ValueError("published_at is required to infer quarter.")
        derived_quarter = _infer_quarter(article.published_at)

    return ClassificationResult(
        category=category_path,
        section=section,
        subheading=subheading,
        confidence=confidence,
        company=derived_company,
        quarter=derived_quarter,
    )


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


def _apply_exec_change_qualifiers(bullets: List[str], article: Article) -> List[str]:
    """
    Ensure exec-change summaries preserve a "former" qualifier when present.

    We only add "former" when the article text explicitly uses it near the name.
    """
    if not bullets:
        return bullets
    text = f"{article.title}\n{article.content}".lower()
    updated: List[str] = []
    pattern = re.compile(
        r"^(Exit|Promotion|Hiring|New Role):\s+([^,]+),\s+([^()]+)"
    )
    for bullet in bullets:
        if "former" in bullet.lower():
            updated.append(bullet)
            continue
        match = pattern.match(bullet)
        if not match:
            updated.append(bullet)
            continue
        name = match.group(2).strip().lower()
        if not name:
            updated.append(bullet)
            continue
        name_pattern = re.escape(name)
        if re.search(rf"former\s+[^\n]{{0,60}}{name_pattern}", text):
            prefix, rest = bullet.split(",", 1)
            rest = rest.lstrip()
            bullet = f"{prefix}, former {rest}"
        updated.append(bullet)
    return updated


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


def _incomplete_reason(response: object) -> str | None:
    status = getattr(response, "status", None)
    if status != "incomplete":
        return None
    details = getattr(response, "incomplete_details", None)
    return getattr(details, "reason", None) if details else None


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
    def _is_interview_or_commentary(lines: List[str]) -> bool:
        if not lines:
            return False
        first = (lines[0] or "").strip().lower()
        return first.startswith("interview:") or first.startswith("commentary:")

    def _is_content_list_category(cls: "ClassificationResult") -> bool:
        if cls.section != "Content / Deals / Distribution":
            return False
        if cls.subheading in {
            "Development",
            "Greenlights",
            "Pickups",
            "Dating",
            "Renewals",
            "Cancellations",
        }:
            return True
        lower = (cls.category or "").lower()
        return any(
            token in lower
            for token in (
                "development",
                "greenlights",
                "pickups",
                "dating",
                "renewals",
                "cancellations",
            )
        )

    def _looks_like_title_item_line(text: str) -> bool:
        if ":" not in text:
            return False
        possible, rest = text.split(":", 1)
        possible = possible.strip()
        rest = rest.strip()
        if not possible or not rest:
            return False
        # Avoid treating explicit label prefixes (e.g., "Greenlights:") as title items.
        if possible.lower() in FACT_LABEL_MAP:
            return False
        return True

    published_at = article.published_at.date() if article.published_at else date.today()

    cleaned = [(b or "").strip() for b in bullets if (b or "").strip()]

    exec_change_note_mode = os.getenv("EXEC_CHANGE_NOTE_MODE", "prefixed").strip().lower()
    allow_unprefixed_exec_notes = exec_change_note_mode in {"unprefixed", "unprefixed_followon"}

    def _parse_note_line(text: str) -> str | None:
        lowered = text.strip().lower()
        if lowered.startswith("note:"):
            return text.split(":", 1)[1].strip()
        if lowered.startswith("note -"):
            return text.split("-", 1)[1].strip()
        if lowered.startswith(("note—", "note–")):
            if "—" in text:
                return text.split("—", 1)[1].strip()
            return text.split("–", 1)[1].strip()
        return None

    def _normalize_category_path(path: str) -> str:
        return " -> ".join([p.strip() for p in path.split("->") if p.strip()])

    def _parse_explicit_category_path_line(text: str) -> tuple[str, str, bool] | None:
        """
        Parse an explicit category-path override line:

          <Full Category Path> : <content line>

        Where the prefix contains at least one "->" arrow. This is the most general,
        routing-independent mechanism and works for any section (Org/M&A/IR/Strategy/etc).
        """
        match = re.match(r"(?is)^\s*(.+?\-\>.+?)\s*[:\-]\s*(.+?)\s*$", text)
        if not match:
            return None
        raw_path, payload = match.groups()
        payload = (payload or "").strip()
        if not payload:
            return None
        category_path = _normalize_category_path(raw_path)
        return category_path, payload, False

    def _parse_content_routed_line(text: str) -> tuple[str, str, bool] | None:
        """
        Parse a routing override line for Content / Deals / Distribution facts.

        Supported formats (case-insensitive):
        - "<Medium> GNS: <sentence>"  (GNS == General News & Strategy)
        - "<Medium> <Subheading>: <line>" where Subheading is one of
          Development/Greenlights/Pickups/Dating/Renewals/Cancellations
        - Separator may be ":" or "-" (e.g., "TV GNS - <sentence>")
        """
        match = re.match(
            r"(?is)^\s*"
            r"(tv|film|specials|international|sports|podcasts)\s+"
            r"(gns|general\s+news\s*&\s*strategy|development|greenlights|pickups|dating|renewals|"
            r"cancellations)\s*"
            r"[:\-]\s*(.+?)\s*$",
            text,
        )
        if not match:
            return None
        medium_raw, kind_raw, payload = match.groups()
        medium_raw = medium_raw.strip().lower()
        payload = (payload or "").strip()
        if not payload:
            return None

        medium_map = {
            "tv": "TV",
            "film": "Film",
            "specials": "Specials",
            "international": "International",
            "sports": "Sports",
            "podcasts": "Podcasts",
        }
        kind_raw = kind_raw.strip().lower()
        if kind_raw in {"gns", "general news & strategy"}:
            subheading = "General News & Strategy"
            is_gns_line = True
        else:
            subheading = kind_raw.title()
            is_gns_line = False

        category_path = (
            f"Content, Deals & Distribution -> {medium_map[medium_raw]} -> {subheading}"
        )
        return category_path, payload, is_gns_line

    def _parse_non_content_routed_line(text: str) -> tuple[str, str, bool] | None:
        """
        Parse routing override lines for non-Content sections.

        Supported formats (case-insensitive):
        - "M&A: <sentence>" or "M&A GNS: <sentence>"
        - "IR <Subheading>: <sentence>" or "Investor Relations <Subheading>: <sentence>"
        - "Strategy <Subheading>: <sentence>" or
          "Strategy & Miscellaneous News <Subheading>: <sentence>"
        - "Highlights: <sentence>"
        """
        match = re.match(
            r"(?is)^\s*(m\s*&\s*a|m&a)\s*"
            r"(?:gns|general\s+news\s*&\s*strategy)?\s*[:\-]\s*(.+?)\s*$",
            text,
        )
        if match:
            payload = (match.group(2) or "").strip()
            if payload:
                return "M&A -> General News & Strategy", payload, False

        match = re.match(
            r"(?is)^\s*(ir|investor\s+relations)\s+"
            r"(quarterly\s+earnings|earnings|company\s+materials|news\s+coverage|"
            r"ir\s+conferences|analyst\s+perspective|gns|general\s+news\s*&\s*strategy)\s*"
            r"[:\-]\s*(.+?)\s*$",
            text,
        )
        if match:
            _, kind, payload = match.groups()
            payload = (payload or "").strip()
            if not payload:
                return None
            kind = kind.strip().lower()
            if kind in {"quarterly earnings", "earnings"}:
                sub = "Quarterly Earnings"
            elif kind == "company materials":
                sub = "Company Materials"
            elif kind == "news coverage":
                sub = "News Coverage"
            elif kind == "ir conferences":
                sub = "IR Conferences"
            elif kind == "analyst perspective":
                sub = "Analyst Perspective"
            else:
                sub = "General News & Strategy"
            return (
                f"Investor Relations -> General News & Strategy -> {sub}",
                payload,
                False,
            )

        match = re.match(
            r"(?is)^\s*(strategy|strategy\s*&\s*miscellaneous\s+news)\s+"
            r"(strategy|misc\.\s*news|misc\s+news|gns|general\s+news\s*&\s*strategy)\s*"
            r"[:\-]\s*(.+?)\s*$",
            text,
        )
        if match:
            _, kind, payload = match.groups()
            payload = (payload or "").strip()
            if not payload:
                return None
            kind = kind.strip().lower()
            if kind.startswith("misc"):
                sub = "Misc. News"
            elif kind == "strategy":
                sub = "Strategy"
            else:
                sub = "General News & Strategy"
            return (
                f"Strategy & Miscellaneous News -> General News & Strategy -> {sub}",
                payload,
                False,
            )

        match = re.match(
            r"(?is)^\s*(strategy|strategy\s*&\s*miscellaneous\s+news)\s*[:\-]\s*(.+?)\s*$",
            text,
        )
        if match:
            payload = (match.group(2) or "").strip()
            if payload:
                return (
                    "Strategy & Miscellaneous News -> General News & Strategy -> Strategy",
                    payload,
                    False,
                )

        match = re.match(r"(?is)^\s*highlights\s*[:\-]\s*(.+?)\s*$", text)
        if match:
            payload = (match.group(1) or "").strip()
            if payload:
                return "Highlights -> General News & Strategy", payload, False

        return None

    def _is_exec_change_line(text: str) -> bool:
        lowered = text.lower()
        return any(
            lowered.startswith(prefix)
            for prefix in ("exit:", "promotion:", "hiring:", "new role:")
        )

    gns_lines_by_category_path: dict[str, list[str]] = {}
    gns_category_order: list[str] = []
    routed_facts: list[FactResult] = []
    remaining: list[str] = []
    exec_facts: list[FactResult] = []
    note_target: FactResult | None = None
    gns_note_target_path: str | None = None
    for line in cleaned:
        note_payload = _parse_note_line(line)
        if note_payload is not None:
            if note_target is not None:
                if note_payload:
                    note_target.summary_bullets.append(note_payload)
                continue
            if gns_note_target_path is not None:
                if (
                    note_payload
                    and gns_note_target_path in gns_lines_by_category_path
                ):
                    gns_lines_by_category_path[gns_note_target_path].append(note_payload)
                continue
            if note_payload:
                remaining.append(note_payload)
            continue

        routed = _parse_explicit_category_path_line(line)
        if routed is None:
            routed = _parse_content_routed_line(line)
        if routed is None:
            routed = _parse_non_content_routed_line(line)

        # Allow unprefixed follow-up notes for routed facts, as long as the line
        # does not contain ":" (to avoid swallowing list-style title lines) and
        # does not look like a new routed fact.
        if (
            note_target is not None
            and (
                note_target.category_path != "Org -> Exec Changes"
                or allow_unprefixed_exec_notes
            )
            and ":" not in line
            and routed is None
            and not _is_exec_change_line(line)
        ):
            note_target.summary_bullets.append(line)
            continue
        if (
            gns_note_target_path is not None
            and ":" not in line
            and routed is None
            and not _is_exec_change_line(line)
            and gns_note_target_path in gns_lines_by_category_path
        ):
            gns_lines_by_category_path[gns_note_target_path].append(line)
            continue

        note_target = None
        gns_note_target_path = None

        if routed is not None:
            category_path, content, is_gns_line = routed
            if is_gns_line:
                if category_path not in gns_lines_by_category_path:
                    gns_lines_by_category_path[category_path] = []
                    gns_category_order.append(category_path)
                gns_lines_by_category_path[category_path].append(content)
                gns_note_target_path = category_path
            else:
                section, parsed_subheading = _parse_category_path(category_path)
                routed_facts.append(
                    FactResult(
                        fact_id=f"fact-{len(routed_facts) + 1}",
                        category_path=category_path,
                        section=section,
                        subheading=parsed_subheading,
                        company=classification.company,
                        quarter=classification.quarter,
                        published_at=published_at,
                        content_line=content,
                        summary_bullets=[content],
                    )
                )
                note_target = routed_facts[-1]
            continue
        if _is_exec_change_line(line):
            exec_category_path = "Org -> Exec Changes"
            exec_section, exec_subheading = _parse_category_path(exec_category_path)
            exec_facts.append(
                FactResult(
                    fact_id=f"fact-{len(exec_facts) + 1}",
                    category_path=exec_category_path,
                    section=exec_section,
                    subheading=exec_subheading,
                    company=classification.company,
                    quarter=classification.quarter,
                    published_at=published_at,
                    content_line=line,
                    summary_bullets=[line],
                )
            )
            note_target = exec_facts[-1]
            continue
        remaining.append(line)

    base_facts: list[FactResult]

    if _is_interview_or_commentary(remaining):
        header = remaining[0]
        base_facts = [
            FactResult(
                fact_id="fact-1",
                category_path=classification.category,
                section=classification.section,
                subheading=classification.subheading,
                company=classification.company,
                quarter=classification.quarter,
                published_at=published_at,
                content_line=header,
                summary_bullets=remaining,
            )
        ]
    elif _is_content_list_category(classification):
        facts: List[FactResult] = []
        current: FactResult | None = None
        next_id = 1
        for text in remaining:
            note_payload = _parse_note_line(text)
            if note_payload is not None and current is not None:
                if note_payload:
                    if len(current.summary_bullets) < 2:
                        current.summary_bullets.append(note_payload)
                    else:
                        current.summary_bullets[-1] = (
                            current.summary_bullets[-1].rstrip() + " " + note_payload
                        ).strip()
                continue
            if current is None or _looks_like_title_item_line(text):
                fact = FactResult(
                    fact_id=f"fact-{next_id}",
                    category_path=classification.category,
                    section=classification.section,
                    subheading=classification.subheading,
                    company=classification.company,
                    quarter=classification.quarter,
                    published_at=published_at,
                    content_line=text,
                    summary_bullets=[text],
                )
                facts.append(fact)
                current = fact
                next_id += 1
                continue

            # Attach one optional note line to the previous title item. If the model
            # emits more than one, coalesce extras into the note line.
            if len(current.summary_bullets) < 2:
                current.summary_bullets.append(text)
            else:
                current.summary_bullets[-1] = (
                    current.summary_bullets[-1].rstrip() + " " + text
                ).strip()
        base_facts = list(facts)
    else:
        facts: list[FactResult] = []
        current: FactResult | None = None
        next_id = 1
        for raw in remaining:
            note_payload = _parse_note_line(raw)
            if note_payload is not None:
                if current is not None and note_payload:
                    current.summary_bullets.append(note_payload)
                    continue
                raw = note_payload or ""
            if not raw.strip():
                continue
            label, content = _label_from_bullet(raw)
            category_path, section, subheading = _build_fact_category(
                classification.category, label
            )
            current = FactResult(
                fact_id=f"fact-{next_id}",
                category_path=category_path,
                section=section,
                subheading=subheading,
                company=classification.company,
                quarter=classification.quarter,
                published_at=published_at,
                content_line=content,
                summary_bullets=[content],
            )
            facts.append(current)
            next_id += 1
        base_facts = facts

    facts = exec_facts + base_facts + routed_facts

    for category_path in gns_category_order:
        lines = gns_lines_by_category_path.get(category_path) or []
        if not lines:
            continue
        section, subheading = _parse_category_path(category_path)
        facts.append(
            FactResult(
                fact_id=f"fact-{len(facts) + 1}",
                category_path=category_path,
                section=section,
                subheading=subheading,
                company=classification.company,
                quarter=classification.quarter,
                published_at=published_at,
                content_line=lines[0],
                summary_bullets=lines,
            )
        )
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
    if not facts:
        fallback = _fallback_fact_for_empty_summary(article, classification, summary)
        settings = get_settings()
        mode = (settings.fact_buyer_guardrail_mode or "section").strip().lower()
        if mode == "strict":
            return _apply_fact_buyer_guardrail(article, classification, summary, [fallback])
        return [fallback]
    return _apply_fact_buyer_guardrail(article, classification, summary, facts)


def _fact_mentions_in_scope_buyer(fact: FactResult, in_scope: set[str]) -> bool:
    """
    Return True when any line for this fact mentions an in-scope buyer keyword.
    """
    candidates = [fact.content_line] + list(fact.summary_bullets or [])
    for text in candidates:
        cleaned = (text or "").strip()
        if not cleaned:
            continue
        if buyers_from_keywords(cleaned) & in_scope:
            return True
    return False


def _apply_fact_buyer_guardrail(
    article: Article,
    classification: "ClassificationResult",
    summary: "SummaryResult",
    facts: List[FactResult],
) -> List[FactResult]:
    """
    Filter facts so cross-section noise doesn't leak into coverage output.

    This is primarily aimed at hybrid articles where the summarizer emits
    explicit override lines (e.g., "M&A: ...") that are not about any buyer
    we track.
    """
    settings = get_settings()
    mode = (settings.fact_buyer_guardrail_mode or "section").strip().lower()
    if mode in {"off", "0", "false", "disabled"}:
        return facts
    if mode not in {"section", "strict"}:
        raise ValueError(
            f"FACT_BUYER_GUARDRAIL_MODE must be one of off, section, strict (got {mode!r})."
        )

    in_scope = parse_buyers_of_interest(settings.buyers_of_interest)
    kept: list[FactResult] = []
    base_section = classification.section

    for fact in facts:
        if mode == "section" and fact.section == base_section:
            kept.append(fact)
            continue
        if _fact_mentions_in_scope_buyer(fact, in_scope):
            kept.append(fact)

    if kept:
        return kept

    # If everything is filtered, fall back to a single safe fact to satisfy
    # the ingest schema, while making the buyer linkage explicit when possible.
    fallback = _fallback_fact_for_empty_summary(article, classification, summary)
    mentions_in_scope = _fact_mentions_in_scope_buyer(fallback, in_scope)
    if (
        classification.company
        and classification.company in in_scope
        and not mentions_in_scope
    ):
        prefixed = f"{classification.company}: {fallback.content_line}".strip()
        fallback.content_line = prefixed
        fallback.summary_bullets = [prefixed]
        mentions_in_scope = True

    if mode == "strict" and not mentions_in_scope:
        raise ValueError(
            "Strict buyer guardrail removed all facts and no in-scope fallback could be produced "
            f"(company={classification.company!r}, in_scope={sorted(in_scope)!r})."
        )
    return [fallback]


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
        store=settings.openai_store,
    )
    _record_openai_response_id("classifier", response)
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


def _summarizer_content_limits(text: str | None) -> list[int | None]:
    limits: list[int | None] = [None]
    if not text:
        return limits
    length = len(text)
    for limit in SUMMARY_RETRY_CHAR_LIMITS:
        if length > limit:
            limits.append(limit)
    return limits


def _truncate_content(text: str, limit: int | None) -> str:
    if not text or not limit or len(text) <= limit:
        return text
    trimmed = text[:limit]
    if " " in trimmed:
        trimmed = trimmed.rsplit(" ", 1)[0]
    return trimmed


def _summarizer_user_message(article: Article, content_limit: int | None) -> str:
    content = article.content or ""
    if content_limit:
        content = _truncate_content(content, content_limit)
    published = article.published_at.isoformat() if article.published_at else "unknown"
    return (
        f"Title: {article.title}\nSource: {article.source}\n"
        f"Published: {published}\n\n{content}"
    )


def _summarizer_request_kwargs(settings, messages: list[dict[str, str]]) -> dict:
    request_kwargs = {
        "model": settings.summarizer_model,
        "input": messages,
        "store": settings.openai_store,
    }
    if settings.max_tokens and settings.max_tokens > 0:
        request_kwargs["max_output_tokens"] = settings.max_tokens
    if settings.summarizer_model != "gpt-5-mini":
        request_kwargs["temperature"] = settings.temperature
    return request_kwargs


def summarize_article(article: Article, prompt_name: str, client: OpenAI) -> SummaryResult:
    settings = get_settings()
    prompt_text = _load_prompt_file(prompt_name)
    content_limits = _summarizer_content_limits(article.content)
    response = None
    for idx, limit in enumerate(content_limits):
        user_message = _summarizer_user_message(article, limit)
        request_kwargs = _summarizer_request_kwargs(
            settings,
            [
                {"role": "system", "content": prompt_text},
                {"role": "user", "content": user_message},
            ],
        )
        response = client.responses.create(**request_kwargs)
        _record_openai_response_id("summarizer", response)
        reason = _incomplete_reason(response)
        if reason == "max_output_tokens" and idx + 1 < len(content_limits):
            continue
        break
    text_output = _response_text_or_raise(response, step="Summarizer")
    bullets = _split_bullets(text_output)
    if prompt_name == "exec_changes.txt":
        bullets = _apply_exec_change_qualifiers(bullets, article)
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

    max_len = max(len(article.content or "") for article in articles)
    content_limits = [None]
    for limit in SUMMARY_RETRY_CHAR_LIMITS:
        if max_len > limit:
            content_limits.append(limit)

    response = None
    for idx, limit in enumerate(content_limits):
        user_sections = []
        for article_idx, article in enumerate(articles, start=1):
            published = article.published_at.isoformat() if article.published_at else "unknown"
            content = article.content or ""
            if limit:
                content = _truncate_content(content, limit)
            user_sections.append(
                f"Article {article_idx}\nInstructions:\n{prompt_texts[article_idx - 1]}\n\n"
                f"Title: {article.title}\nSource: {article.source}\n"
                f"Published: {published}\n\n{content}"
            )
        request_kwargs = _summarizer_request_kwargs(
            settings,
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "\n\n".join(user_sections)},
            ],
        )
        if settings.max_tokens and settings.max_tokens > 0:
            request_kwargs["max_output_tokens"] = settings.max_tokens * max(1, len(articles))
        response = client.responses.create(**request_kwargs)
        _record_openai_response_id("summarizer_batch", response)
        reason = _incomplete_reason(response)
        if reason == "max_output_tokens" and idx + 1 < len(content_limits):
            continue
        break

    text_output = _response_text_or_raise(response, step="Summarizer (batch)")
    chunks = _extract_summary_chunks(text_output, len(articles))
    summaries: list[SummaryResult] = []
    for article, prompt_name, chunk in zip(articles, prompt_list, chunks):
        bullets = _split_bullets(chunk)
        if prompt_name == "exec_changes.txt":
            bullets = _apply_exec_change_qualifiers(bullets, article)
        summaries.append(SummaryResult(bullets=bullets, facts=[]))
    return summaries


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


def _strip_trailing_date_marker(text: str) -> str:
    """
    Remove a trailing (M/D[/YY]) or ([M/D[/YY]](url)) parenthetical.

    Used when rendering exec-change note lines inline so the publish date appears
    only once per bullet.
    """
    stripped = (text or "").strip()
    if not stripped:
        return stripped
    stripped = _DATE_LINK_TAIL_PATTERN.sub("", stripped).strip()
    stripped = _DATE_PAREN_TAIL_PATTERN.sub("", stripped).strip()
    return stripped


def _format_exec_change_lines(fact: "FactResult", date_link: str, url: str) -> list[str]:
    """
    Render exec-change facts as a single line, appending any note text after the date.

    This mirrors the manual DOCX style (main item + (M/D) + appended clause) and
    avoids repeating the date marker on the follow-on note sentence.
    """
    bullets = [b for b in (fact.summary_bullets or []) if (b or "").strip()]
    if not bullets:
        text = (fact.content_line or "").strip()
        return [_format_summary_lines([text], date_link, url)[0]] if text else [""]

    main = _linkify_date_parentheticals(bullets[0].strip(), url)
    if main and not _has_date_marker(main):
        main = f"{main} ({date_link})"

    notes = [_strip_trailing_date_marker(_linkify_date_parentheticals(b, url)) for b in bullets[1:]]
    notes = [n.strip() for n in notes if (n or "").strip()]
    if notes:
        return [f"{main} {' '.join(notes)}".strip()]
    return [main]


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
    buyer_set = set(matches.strong)
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
        if fact.category_path == "Org -> Exec Changes":
            content_lines = _format_exec_change_lines(fact, date_link, url)
        else:
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
        if fact.category_path == "Org -> Exec Changes":
            content_lines = _format_exec_change_lines(fact, date_link, url)
        else:
            content_lines = _format_summary_lines(_fact_summary_bullets(fact), date_link, url)
        lines.append(f"Category: {category_display}")
        lines.extend([f"Content: {line}" for line in (content_lines or [""])])
    return "\n".join(lines)


def ingest_article(
    article: Article,
    classification: ClassificationResult,
    summary: SummaryResult,
    *,
    dedupe: bool = True,
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
    duplicate_of = None
    with locked_path(path):
        _ensure_parent(path)
        if dedupe and _jsonl_contains_url(path, validated["url"]):
            duplicate_of = validated["url"]
        else:
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(validated, ensure_ascii=False))
                f.write("\n")
    return IngestResult(stored_path=path, duplicate_of=duplicate_of)


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
            prompt_name = rule.prompt
            if prompt_name == "exec_changes.txt":
                mode = os.getenv("EXEC_CHANGE_NOTE_MODE", "prefixed").strip().lower()
                if mode in {"unprefixed", "unprefixed_followon"}:
                    prompt_name = "exec_changes_unprefixed_note.txt"
            return prompt_name, formatter_fn

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
    article, _ = normalize_article(article)
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

    with collect_openai_response_ids() as openai_response_ids:
        classification = classifier_fn(article, client)
        prompt_name, routed_formatter = _route_prompt_and_formatter(classification)
        active_formatter = formatter_fn or routed_formatter
        summary = summarizer_fn(article, prompt_name, client)
        if not summary.facts:
            summary.facts = _assemble_facts(summary.bullets, classification, article)
        markdown = active_formatter(article, classification, summary)
        ingest_result = ingest_fn(article, classification, summary)

    if not ingest_result.duplicate_of:
        append_final_output_entry(article, classification, summary)

    return PipelineResult(
        markdown=markdown,
        classification=classification,
        summary=summary,
        ingest=ingest_result,
        openai_response_ids=openai_response_ids,
    )
