"""Orchestrates loading articles, routing to buyers, and producing DOCX outputs."""

from __future__ import annotations

import dataclasses
import json
from datetime import date
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List

from .agent_runner import run_with_agent
from .buyer_routing import BuyerMatch, match_buyers
from .docx_builder import BuyerReport, CoverageEntry, build_docx
from .models import Article


@dataclass
class ReviewItem:
    title: str
    url: str
    buyer: str
    reason: str


@dataclass
class BuildResult:
    buyer_reports: Dict[str, BuyerReport] = field(default_factory=dict)
    reviews: List[ReviewItem] = field(default_factory=list)


def _load_article_file(path: Path) -> Article:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        if len(data) != 1:
            raise ValueError(f"{path} must contain exactly one article object.")
        data = data[0]
    return Article(**data)


def _infer_medium(category_path: str) -> str:
    lower = category_path.lower()
    if "film" in lower or "movie" in lower or "theatrical" in lower:
        return "Film"
    if "tv" in lower or "television" in lower or "series" in lower:
        return "TV"
    if "specials" in lower:
        return "Specials"
    if "international" in lower:
        return "International"
    if "sports" in lower or "podcast" in lower:
        return "Sports/Podcasts"
    return "General"


def _as_fact_dict(fact) -> dict:
    if dataclasses.is_dataclass(fact):
        return dataclasses.asdict(fact)
    if isinstance(fact, dict):
        return fact
    raise TypeError(f"Unsupported fact type: {type(fact)!r}")


def _is_content_list_fact(fact: dict) -> bool:
    if fact.get("section") != "Content / Deals / Distribution":
        return False
    return fact.get("subheading") in {
        "Development",
        "Greenlights",
        "Pickups",
        "Dating",
        "Renewals",
        "Cancellations",
    }


def _is_interview_or_commentary_fact(fact: dict) -> bool:
    content_line = (fact.get("content_line") or "").strip().lower()
    return content_line.startswith("interview:") or content_line.startswith("commentary:")


def _build_coverage_entry(article: Article, fact) -> CoverageEntry:
    fact_dict = _as_fact_dict(fact)
    published_at = fact_dict.get("published_at") or (
        article.published_at.date() if article.published_at else None
    )
    if isinstance(published_at, str):
        published_at = date.fromisoformat(published_at)
    if not published_at:
        raise ValueError("Published date missing.")
    category_path = fact_dict["category_path"]
    section = fact_dict["section"]
    subheading = fact_dict.get("subheading")
    summary_bullets = list(fact_dict.get("summary_bullets") or [])
    content_line = (fact_dict.get("content_line") or "").strip()
    is_list_fact = _is_content_list_fact(fact_dict) and ":" in content_line
    is_interview_fact = _is_interview_or_commentary_fact(fact_dict)
    is_general_news_fact = (
        fact_dict.get("subheading") == "General News & Strategy"
        and fact_dict.get("section")
        in {"Content / Deals / Distribution", "Strategy & Miscellaneous News"}
        and bool(content_line)
    )
    is_non_content_fact = (
        fact_dict.get("section") in {"Org", "M&A", "Investor Relations", "Highlights"}
        and bool(content_line)
    )
    if is_list_fact:
        title = content_line
        summary_lines = [line.strip() for line in summary_bullets[1:2] if (line or "").strip()]
    elif is_interview_fact:
        title = content_line or article.title
        summary_lines = [line.strip() for line in summary_bullets[1:] if (line or "").strip()]
    elif is_general_news_fact:
        title = content_line
        summary_lines = [line.strip() for line in summary_bullets[1:4] if (line or "").strip()]
    elif is_non_content_fact:
        title = content_line
        summary_lines = [line.strip() for line in summary_bullets[1:4] if (line or "").strip()]
    else:
        title = article.title
        summary = " ".join([b.strip() for b in summary_bullets[:3] if (b or "").strip()])
        summary_lines = [summary] if summary else []
    medium = _infer_medium(category_path)
    return CoverageEntry(
        title=title,
        url=str(article.url),
        published_at=published_at,
        section=section,
        subheading=subheading,
        medium=medium,
        summary_lines=summary_lines,
    )


def _collect_article_paths(inputs: Iterable[Path]) -> List[Path]:
    paths: List[Path] = []
    for path in inputs:
        if path.is_dir():
            paths.extend(sorted(p for p in path.iterdir() if p.suffix.lower() == ".json"))
        else:
            paths.append(path)
    return paths


def build_reports(
    article_paths: Iterable[Path],
    *,
    quarter_label: str,
    output_dir: Path,
) -> BuildResult:
    """
    Build buyer reports and a needs-review list from provided article JSON files.
    """
    result = BuildResult()
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in _collect_article_paths(article_paths):
        article = _load_article_file(path)
        run = run_with_agent(article)
        facts = run.summary.facts or [
            {
                "category_path": run.classification.category,
                "section": run.classification.section,
                "subheading": run.classification.subheading,
                "published_at": article.published_at.date() if article.published_at else None,
                "summary_bullets": run.summary.bullets,
            }
        ]

        match: BuyerMatch = match_buyers(article, body=article.content)

        # Missing dates go straight to review for all matched buyers (or Unknown if none).
        if article.published_at is None:
            targets = match.strong or match.weak or {"Unknown"}
            for buyer in targets:
                result.reviews.append(
                    ReviewItem(
                        title=article.title,
                        url=str(article.url),
                        buyer=buyer,
                        reason="Missing published_at; cannot place.",
                    )
                )
            continue

        for fact in facts:
            try:
                entry = _build_coverage_entry(article, fact)
            except ValueError as exc:
                targets = match.strong or match.weak or {"Unknown"}
                for buyer in targets:
                    result.reviews.append(
                        ReviewItem(
                            title=article.title,
                            url=str(article.url),
                            buyer=buyer,
                            reason=str(exc),
                        )
                    )
                continue

            # Add to strong matches immediately.
            for buyer in match.strong:
                report = result.buyer_reports.setdefault(buyer, BuyerReport(buyer=buyer))
                report.entries.append(entry)

            # Weak matches logged to review.
            for buyer in match.weak:
                result.reviews.append(
                    ReviewItem(
                        title=article.title,
                        url=str(article.url),
                        buyer=buyer,
                        reason="Weak keyword match; please confirm inclusion.",
                    )
                )

    # Render DOCXs
    for buyer, report in result.buyer_reports.items():
        output_path = output_dir / f"{quarter_label} {buyer} News Coverage.docx"
        build_docx(report, output_path, quarter_label)

    # Write consolidated needs-review file
    needs_review_path = output_dir / "needs_review.txt"
    if result.reviews:
        lines = []
        for item in result.reviews:
            lines.append(f"{item.buyer}: {item.title} ({item.url}) -- {item.reason}")
        needs_review_path.write_text("\n".join(lines), encoding="utf-8")
    else:
        needs_review_path.write_text("No review items.\n", encoding="utf-8")

    return result
