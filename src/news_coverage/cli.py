"""Command-line entry points for the news coverage workflow."""

import json
import dataclasses
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Any

import typer
from rich import print as rprint

from .models import Article
from .workflow import ingest_article, process_article
from .agent_runner import run_with_agent

app = typer.Typer(
    help="Run the coordinator pipeline for a single entertainment news article."
)


def _load_article(path: Optional[Path]) -> Article:
    if path is None:
        raise typer.BadParameter("Provide a JSON file containing exactly one article.")
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        if len(data) != 1:
            raise typer.BadParameter("The JSON file must contain exactly one article.")
        data = data[0]
    return Article(**data)


def _to_plain(value: Any) -> Any:
    """
    Convert dataclasses, Paths, and date-like objects into JSON-serializable primitives.
    Sets are returned as lists to avoid JSON serialization errors.
    """
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if dataclasses.is_dataclass(value):
        return _to_plain(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {k: _to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_plain(item) for item in value]
    return value


def _write_output(out_path: Path, markdown: str, json_payload: dict) -> None:
    suffix = out_path.suffix.lower()
    if suffix == ".json":
        out_path.write_text(
            json.dumps(json_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    else:
        out_path.write_text(markdown, encoding="utf-8")


@app.command()
def run(
    path: Optional[Path] = typer.Argument(None, help="Path to a JSON article payload."),
    out: Optional[Path] = typer.Option(
        None,
        "--out",
        "-o",
        help="Optional path to write output (.md or .json). Defaults to stdout (Markdown).",
    ),
    mode: str = typer.Option(
        "agent",
        "--mode",
        "-m",
        help="Pipeline mode: 'agent' (Agents SDK manager) or 'direct' (legacy).",
        case_sensitive=False,
    ),
):
    """Run one article through classify -> summarize -> format -> ingest."""
    article = _load_article(path)
    debug_root = Path(__file__).resolve().parents[2] / "data" / "samples" / "debug"
    is_debug_fixture = False
    if path:
        try:
            is_debug_fixture = path.resolve().is_relative_to(debug_root)
        except AttributeError:  # python <3.9 fallback
            is_debug_fixture = str(debug_root) in str(path.resolve())

    def ingest_wrapper(a, cls, summary):
        return ingest_article(a, cls, summary, skip_duplicate=is_debug_fixture)

    mode_normalized = mode.lower()
    if mode_normalized not in {"agent", "direct"}:
        raise typer.BadParameter("mode must be 'agent' or 'direct'.")

    if mode_normalized == "agent":
        result = run_with_agent(article, skip_duplicate=is_debug_fixture)
    else:
        result = process_article(article, ingest_fn=ingest_wrapper)

    if result.ingest.duplicate_of:
        rprint(
            "[yellow]Duplicate detected; matches "
            f"{result.ingest.duplicate_of}. Stored path: "
            f"{result.ingest.stored_path}[/yellow]"
        )
    else:
        rprint(f"[green]Stored at {result.ingest.stored_path}[/green]")

    if out:
        _write_output(out, result.markdown, _to_plain(result))
        rprint(f"[cyan]Wrote output to {out}[/cyan]")
    else:
        rprint(result.markdown)


def main():
    app()


if __name__ == "__main__":
    main()
