"""DOCX generation for multi-buyer news coverage reports."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt


SECTION_TITLES: List[Tuple[str, str]] = [
    ("Org", "Org"),
    ("Content / Deals / Distribution", "Content, Deals & Distribution"),
    ("Strategy & Miscellaneous News", "Strategy & Miscellaneous News"),
    ("Investor Relations", "Investor Relations"),
    ("M&A", "M&A"),
]

MEDIUM_ORDER = ("Film", "TV", "International", "Sports/Podcasts", "General")


@dataclass
class CoverageEntry:
    title: str
    url: str
    published_at: date
    section: str
    subheading: str | None
    medium: str
    summary: str


@dataclass
class BuyerReport:
    buyer: str
    entries: List[CoverageEntry] = field(default_factory=list)


def _month_range_text(quarter_label: str) -> str:
    mapping = {
        "Q1": "January – March",
        "Q2": "April – June",
        "Q3": "July – September",
        "Q4": "October – December",
    }
    try:
        q = quarter_label.strip().split()[1]
    except Exception:
        return "January – March"
    return mapping.get(q, "January – March")


def _format_md(dt: date) -> str:
    return f"{dt.month}/{dt.day}"


def _group_entries(entries: Sequence[CoverageEntry]) -> Dict[str, Dict[str, List[CoverageEntry]]]:
    """
    Group entries by section -> medium, sorted newest to oldest.
    Returns nested dict: {section: {medium: [entries...]}}
    """
    grouped: Dict[str, Dict[str, List[CoverageEntry]]] = defaultdict(lambda: defaultdict(list))
    for e in entries:
        grouped[e.section][e.medium].append(e)

    for section_map in grouped.values():
        for medium, items in section_map.items():
            section_map[medium] = sorted(items, key=lambda i: i.published_at, reverse=True)
    return grouped


def _set_title_styles(doc: Document) -> None:
    """
    Apply minimal styling to approximate the reference docs without embedding custom themes.
    Keeps ASCII; uses Calibri 14/12 for header/subheader for readability.
    """
    title_style = doc.styles["Title"]
    title_font = title_style.font
    title_font.name = "Calibri"
    title_font.size = Pt(20)

    try:
        title_style._element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    except Exception:
        pass


def build_docx(report: BuyerReport, output_path: Path, quarter_label: str) -> None:
    """Render a single buyer DOCX."""
    doc = Document()
    _set_title_styles(doc)

    # Cover/header
    title = doc.add_heading(f"{quarter_label} News & Updates", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    sub = doc.add_paragraph(f"{_month_range_text(quarter_label)} {quarter_label.split()[0]}")
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER

    grouped = _group_entries(report.entries)

    for idx, (section_key, section_display) in enumerate(SECTION_TITLES, start=1):
        if section_key not in grouped:
            continue
        doc.add_heading(f"{idx}. {section_display}", level=1)
        section_entries = grouped[section_key]

        # Only Content & Strategy get medium grouping emphasis
        if section_key in {"Content / Deals / Distribution", "Strategy & Miscellaneous News"}:
            medium_order = MEDIUM_ORDER
        else:
            medium_order = ("General",)

        for medium in medium_order:
            if medium not in section_entries:
                continue
            if section_key in {"Content / Deals / Distribution", "Strategy & Miscellaneous News"}:
                doc.add_heading(medium, level=2)
            for entry in section_entries[medium]:
                bullet = doc.add_paragraph(style="List Bullet")
                bullet.add_run(f"{entry.title} ({_format_md(entry.published_at)})")
                if entry.subheading:
                    bullet.add_run(f" — {entry.subheading}")
                summary_para = doc.add_paragraph(entry.summary)
                summary_para.style = "List Bullet"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path)
