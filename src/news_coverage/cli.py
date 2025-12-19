"""Command-line entry points for the news coverage workflow."""

import json
import dataclasses
import os
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed

import typer
from rich import print as rprint

from .models import Article
from .workflow import ingest_article, process_article
from .agent_runner import run_with_agent, run_with_agent_batch
from .coverage_builder import build_reports

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


def _collect_article_paths(inputs: List[Path]) -> List[Path]:
    paths: List[Path] = []
    for path in inputs:
        if path.is_dir():
            paths.extend(sorted(p for p in path.iterdir() if p.suffix.lower() == ".json"))
        else:
            paths.append(path)
    return paths


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


def _batch_output_path(outdir: Path, path: Path, index: int, fmt: str) -> Path:
    suffix = ".json" if fmt == "json" else ".md"
    safe_name = f"{index:03d}-{path.stem}{suffix}"
    return outdir / safe_name


def _default_trace_path() -> Path:
    traces_dir = Path(__file__).resolve().parents[2] / "docs" / "traces"
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return traces_dir / f"agent-trace-{timestamp}.log"


@app.callback(invoke_without_command=True)
def run(
    ctx: typer.Context,
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
    trace: bool = typer.Option(
        False,
        "--trace",
        help="Append a manager-agent trace log for this run under docs/traces.",
    ),
    trace_path: Optional[Path] = typer.Option(
        None,
        "--trace-path",
        help="Optional path to write the agent trace log (overrides --trace default).",
    ),
):
    """
    Default command: run one article through classify -> summarize -> format -> ingest.

    When a subcommand (e.g., build-docx) is invoked, this callback exits early.
    """
    if ctx.invoked_subcommand:
        return

    article = _load_article(path)

    def ingest_wrapper(a, cls, summary):
        return ingest_article(a, cls, summary)

    mode_normalized = mode.lower()
    if mode_normalized not in {"agent", "direct"}:
        raise typer.BadParameter("mode must be 'agent' or 'direct'.")

    if mode_normalized == "agent":
        if trace or trace_path:
            resolved_trace = trace_path or _default_trace_path()
            os.environ["AGENT_TRACE_PATH"] = str(resolved_trace)
        result = run_with_agent(article)
    else:
        if trace or trace_path:
            raise typer.BadParameter("Trace logging is only available in --mode agent.")
        result = process_article(article, ingest_fn=ingest_wrapper)

    rprint(f"[green]Stored at {result.ingest.stored_path}[/green]")

    if out:
        _write_output(out, result.markdown, _to_plain(result))
        rprint(f"[cyan]Wrote output to {out}[/cyan]")
    else:
        rprint(result.markdown)


@app.command("batch")
def batch_command(
    articles: List[Path] = typer.Argument(
        ...,
        help="One or more article JSON files or directories containing JSON files.",
    ),
    outdir: Optional[Path] = typer.Option(
        None,
        "--outdir",
        "-o",
        help="Optional directory to write per-article outputs (.md or .json).",
    ),
    output_format: str = typer.Option(
        "md",
        "--format",
        "-f",
        help="Output format when writing files: md or json.",
        case_sensitive=False,
    ),
    concurrency: int = typer.Option(
        4,
        "--concurrency",
        "-c",
        help="Number of articles to process in parallel.",
    ),
    mode: str = typer.Option(
        "agent",
        "--mode",
        "-m",
        help="Pipeline mode: 'agent' (Agents SDK manager) or 'direct' (legacy).",
        case_sensitive=False,
    ),
    trace: bool = typer.Option(
        False,
        "--trace",
        help="Append a manager-agent trace log for this run under docs/traces.",
    ),
    trace_path: Optional[Path] = typer.Option(
        None,
        "--trace-path",
        help="Optional path to write the agent trace log (overrides --trace default).",
    ),
):
    """
    Run multiple articles through the pipeline in parallel.
    """
    if concurrency < 1:
        raise typer.BadParameter("concurrency must be >= 1.")

    mode_normalized = mode.lower()
    if mode_normalized not in {"agent", "direct"}:
        raise typer.BadParameter("mode must be 'agent' or 'direct'.")

    fmt = output_format.lower()
    if fmt not in {"md", "json"}:
        raise typer.BadParameter("format must be 'md' or 'json'.")

    paths = _collect_article_paths(articles)
    if not paths:
        raise typer.BadParameter("No JSON article files found.")

    if outdir:
        outdir.mkdir(parents=True, exist_ok=True)

    if mode_normalized == "agent":
        if trace or trace_path:
            resolved_trace = trace_path or _default_trace_path()
            os.environ["AGENT_TRACE_PATH"] = str(resolved_trace)
    elif trace or trace_path:
        raise typer.BadParameter("Trace logging is only available in --mode agent.")

    outcomes: list[dict | None] = [None] * len(paths)
    tasks: list[tuple[int, Path, Article]] = []

    for idx, path in enumerate(paths):
        try:
            article = _load_article(path)
        except Exception as exc:
            outcomes[idx] = {"index": idx, "path": path, "result": None, "error": str(exc)}
            continue

        tasks.append((idx, path, article))

    if tasks:
        if mode_normalized == "agent":
            batch = run_with_agent_batch(
                [task[2] for task in tasks],
                max_workers=concurrency,
            )
            for task, item in zip(tasks, batch.items):
                idx, path, _ = task
                outcomes[idx] = {
                    "index": idx,
                    "path": path,
                    "result": item.result,
                    "error": item.error,
                }
        else:
            worker_count = min(concurrency, len(tasks))

            def _run_direct(article: Article):
                def ingest_wrapper(a, cls, summary):
                    return ingest_article(a, cls, summary)

                return process_article(article, ingest_fn=ingest_wrapper)

            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                future_map = {
                    executor.submit(_run_direct, article): idx
                    for idx, _, article in tasks
                }
                for future in as_completed(future_map):
                    idx = future_map[future]
                    path = paths[idx]
                    try:
                        result = future.result()
                        outcomes[idx] = {
                            "index": idx,
                            "path": path,
                            "result": result,
                            "error": None,
                        }
                    except Exception as exc:
                        outcomes[idx] = {
                            "index": idx,
                            "path": path,
                            "result": None,
                            "error": str(exc),
                        }

    successes = [item for item in outcomes if item and item["error"] is None]
    failures = [item for item in outcomes if item and item["error"]]

    for item in outcomes:
        if not item:
            continue
        idx = item["index"]
        path = item["path"]
        result = item["result"]
        error = item["error"]
        if error:
            rprint(f"[red]Failed {path}: {error}[/red]")
            continue
        rprint(f"[green]Stored at {result.ingest.stored_path}[/green]")

        if outdir:
            out_path = _batch_output_path(outdir, path, idx, fmt)
            _write_output(out_path, result.markdown, _to_plain(result))
            rprint(f"[cyan]Wrote output to {out_path}[/cyan]")
        else:
            rprint(f"[cyan]--- {path} ---[/cyan]")
            rprint(result.markdown)

    rprint(
        f"[cyan]Batch complete: {len(successes)} succeeded, {len(failures)} failed.[/cyan]"
    )
    if failures:
        raise typer.Exit(code=1)


@app.command("build-docx")
def build_docx_command(
    articles: List[Path] = typer.Argument(
        ...,
        help="One or more article JSON files or directories containing JSON files.",
    ),
    quarter: str = typer.Option("2025 Q4", help='Quarter label, e.g., "2025 Q4".'),
    outdir: Path = typer.Option(
        Path("docs/samples/news_coverage_docx"),
        "--outdir",
        help="Directory to write generated DOCX files and needs_review.txt.",
    ),
):
    """
    Build multi-buyer News Coverage DOCX files for the given quarter.

    Notes:
    - Highlights are not auto-generated.
    - Articles missing published_at are written to needs_review.txt.
    - Weak keyword matches are flagged to needs_review.txt.
    """
    rprint("[cyan]Building buyer DOCXs...[/cyan]")
    build_reports(articles, quarter_label=quarter, output_dir=outdir)
    rprint(f"[green]Done. Files written under {outdir}[/green]")


def main():
    app()


if __name__ == "__main__":
    main()
