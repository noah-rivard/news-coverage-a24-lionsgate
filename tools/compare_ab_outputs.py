import argparse
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


_DATE_LINK_RE = re.compile(
    r"\s*\(\[\d{1,2}/\d{1,2}(?:/\d{2,4})?\]\([^)]+\)\)\s*$"
)

_MOJIBAKE_REPLACEMENTS: Tuple[Tuple[str, str], ...] = (
    ("\u0192?Ts", "'s"),
    ("\u0192?~s", "'s"),
    ("\u0192?s", "'s"),
    ("\u0192?T", "'"),
    ("\u0192?o", '"'),
    ("\u0192??", '"'),
    ("\u0192?\u00dd", "--"),
    ("\u00e2\u20ac\u0153", '"'),
    ("\u00e2\u20ac\u009d", '"'),
    ("\u00e2\u20ac\u0099", "'"),
    ("\u00e2\u20ac\u0098", "'"),
    ("\u00e2\u20ac\u201d", "--"),
    ("\u00e2\u20ac\u201c", "-"),
    ("\u00c2", ""),
)


EXEC_PREFIXES = ("exit:", "promotion:", "hiring:", "new role:")


@dataclass(frozen=True)
class ParsedOut:
    title: str
    ordered_categories: List[str]
    lines_by_category: Dict[str, List[str]]


def _normalize_text(text: str) -> str:
    normalized = text
    for raw, cleaned in _MOJIBAKE_REPLACEMENTS:
        if raw in normalized:
            normalized = normalized.replace(raw, cleaned)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _strip_date_link(text: str) -> str:
    return _DATE_LINK_RE.sub("", text).strip()


def _parse_out_markdown(text: str) -> ParsedOut:
    title: str = ""
    ordered_categories: List[str] = []
    lines_by_category: Dict[str, List[str]] = {}

    current_category: Optional[str] = None
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.lower().startswith("title:"):
            title = line.split(":", 1)[1].strip()
            continue
        if line.lower().startswith("category:"):
            current_category = line.split(":", 1)[1].strip()
            if current_category not in lines_by_category:
                ordered_categories.append(current_category)
                lines_by_category[current_category] = []
            continue
        if line.lower().startswith("content:"):
            payload = line.split(":", 1)[1].strip()
            if current_category is None:
                continue
            lines_by_category[current_category].append(payload)
            continue
    return ParsedOut(
        title=title,
        ordered_categories=ordered_categories,
        lines_by_category=lines_by_category,
    )


def _is_exec_main_line(text: str) -> bool:
    lowered = (text or "").strip().lower()
    return any(lowered.startswith(p) for p in EXEC_PREFIXES)


def _extract_exec_name(text: str) -> str:
    raw = (text or "").strip()
    lower = raw.lower()
    for prefix in EXEC_PREFIXES:
        if lower.startswith(prefix):
            raw = raw[len(prefix) :].strip()
            break
    return raw.split(",", 1)[0].strip() if raw else ""


def _group_exec_items(lines: Iterable[str]) -> List[Tuple[str, List[str]]]:
    items: List[Tuple[str, List[str]]] = []
    current_main: Optional[str] = None
    current_notes: List[str] = []
    for line in lines:
        if _is_exec_main_line(line):
            if current_main is not None:
                items.append((current_main, current_notes))
            current_main = line
            current_notes = []
            continue
        if current_main is not None and (line or "").strip():
            current_notes.append(line.strip())
    if current_main is not None:
        items.append((current_main, current_notes))
    return items


def _html_bullets(lines: Iterable[str]) -> str:
    cleaned = [line.strip() for line in lines if (line or "").strip()]
    if not cleaned:
        return ""
    # ASCII-only marker so the report renders cleanly in editors/terminals.
    return "<br>".join([f"- {line}" for line in cleaned])


def _format_exec_item(main: str, notes: List[str]) -> str:
    parts = [main.strip()] + [n.strip() for n in notes if (n or "").strip()]
    return " ".join(parts).strip()


def _iter_out_files(path: Path, pattern: str) -> List[Path]:
    if path.is_file():
        return [path]
    if not path.exists():
        raise FileNotFoundError(str(path))
    return sorted(path.glob(pattern))


def _match_pairs(
    a_files: List[Path],
    b_files: List[Path],
) -> List[Tuple[Optional[Path], Optional[Path]]]:
    a_by_name = {p.name: p for p in a_files}
    b_by_name = {p.name: p for p in b_files}
    names = sorted(set(a_by_name.keys()) | set(b_by_name.keys()))
    return [(a_by_name.get(name), b_by_name.get(name)) for name in names]


def build_report(
    *,
    a_path: Path,
    b_path: Path,
    pattern: str,
    strip_links: bool,
    normalize_text: bool,
) -> str:
    a_files = _iter_out_files(a_path, pattern)
    b_files = _iter_out_files(b_path, pattern)
    pairs = _match_pairs(a_files, b_files)

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines: List[str] = [
        "# A/B output comparison",
        "",
        f"- Generated: {now}",
        f"- A: {a_path}",
        f"- B: {b_path}",
        f"- Pattern: {pattern}",
        "",
    ]

    for a_file, b_file in pairs:
        a_text = a_file.read_text(encoding="utf-8") if a_file else ""
        b_text = b_file.read_text(encoding="utf-8") if b_file else ""

        parsed_a = _parse_out_markdown(a_text)
        parsed_b = _parse_out_markdown(b_text)

        title = parsed_a.title or parsed_b.title or (a_file or b_file).name
        title = _normalize_text(title) if normalize_text else title
        lines.extend([f"## {title}", ""])
        lines.append(f"- A file: {a_file}" if a_file else "- A file: (missing)")
        lines.append(f"- B file: {b_file}" if b_file else "- B file: (missing)")
        lines.append("")

        categories_a = set(parsed_a.lines_by_category.keys())
        categories_b = set(parsed_b.lines_by_category.keys())
        only_a = sorted(categories_a - categories_b)
        only_b = sorted(categories_b - categories_a)
        if only_a:
            lines.append(f"- Categories only in A: {only_a}")
        if only_b:
            lines.append(f"- Categories only in B: {only_b}")
        if only_a or only_b:
            lines.append("")

        ordered = list(parsed_a.ordered_categories)
        for cat in parsed_b.ordered_categories:
            if cat not in ordered:
                ordered.append(cat)
        if not ordered:
            ordered = sorted(categories_a | categories_b)

        lines.extend(
            [
                "| Category | A (prefixed) | B (unprefixed) |",
                "|---|---|---|",
            ]
        )
        for category in ordered:
            a_lines = list(parsed_a.lines_by_category.get(category, []))
            b_lines = list(parsed_b.lines_by_category.get(category, []))
            if strip_links:
                a_lines = [_strip_date_link(x) for x in a_lines]
                b_lines = [_strip_date_link(x) for x in b_lines]
            if normalize_text:
                a_lines = [_normalize_text(x) for x in a_lines]
                b_lines = [_normalize_text(x) for x in b_lines]
            lines.append(f"| {category} | {_html_bullets(a_lines)} | {_html_bullets(b_lines)} |")

        lines.append("")

        exec_cat = "Org -> Exec Changes"
        if exec_cat in categories_a or exec_cat in categories_b:
            a_exec_lines = parsed_a.lines_by_category.get(exec_cat, [])
            b_exec_lines = parsed_b.lines_by_category.get(exec_cat, [])
            if strip_links:
                a_exec_lines = [_strip_date_link(x) for x in a_exec_lines]
                b_exec_lines = [_strip_date_link(x) for x in b_exec_lines]
            if normalize_text:
                a_exec_lines = [_normalize_text(x) for x in a_exec_lines]
                b_exec_lines = [_normalize_text(x) for x in b_exec_lines]

            a_items = _group_exec_items(a_exec_lines)
            b_items = _group_exec_items(b_exec_lines)

            def _items_by_name(items: List[Tuple[str, List[str]]]) -> Dict[str, str]:
                out: Dict[str, str] = {}
                for main, notes in items:
                    name = _extract_exec_name(main) or main
                    key = name
                    idx = 2
                    while key in out:
                        key = f"{name} ({idx})"
                        idx += 1
                    out[key] = _format_exec_item(main, notes)
                return out

            a_map = _items_by_name(a_items)
            b_map = _items_by_name(b_items)
            keys = list(a_map.keys())
            for k in b_map.keys():
                if k not in a_map:
                    keys.append(k)

            lines.extend(
                [
                    "### Exec Changes (paired)",
                    "",
                    "| Person | A (prefixed) | B (unprefixed) |",
                    "|---|---|---|",
                ]
            )
            for key in keys:
                a_val = a_map.get(key, "")
                b_val = b_map.get(key, "")
                lines.append(f"| {key} | {a_val} | {b_val} |")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a side-by-side A/B comparison report from per-article .out.md outputs."
        )
    )
    parser.add_argument("--a", required=True, help="Mode A path (file or directory).")
    parser.add_argument("--b", required=True, help="Mode B path (file or directory).")
    parser.add_argument(
        "--pattern",
        default="*.out.md",
        help="Glob pattern for directory inputs (default: *.out.md).",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write the markdown report.",
    )
    parser.add_argument(
        "--keep-links",
        action="store_true",
        help="Do not strip trailing date links like ([10/24](url)).",
    )
    parser.add_argument(
        "--no-normalize",
        action="store_true",
        help="Do not normalize common mojibake sequences in text.",
    )

    args = parser.parse_args()
    a_path = Path(args.a)
    b_path = Path(args.b)
    out_path = Path(args.output)

    report = build_report(
        a_path=a_path,
        b_path=b_path,
        pattern=args.pattern,
        strip_links=not args.keep_links,
        normalize_text=not args.no_normalize,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"[ok] wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
