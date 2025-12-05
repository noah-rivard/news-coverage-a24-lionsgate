"""Command-line entry points for the news coverage workflow."""

import json
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint
from rich.table import Table

from .config import get_settings
from .models import Article
from .workflow import build_client, summarize_articles

app = typer.Typer(
    help="Summarize entertainment news articles with OpenAI Agents."
)


def _load_articles(path: Optional[Path]) -> list[Article]:
    if path is None:
        # Provide stub data for quick demos
        return [
            Article(
                title="Example headline",
                source="SampleWire",
                url="https://example.com/story",
                content=(
                    "A24 and Lionsgate announced a new partnership for distribution "
                    "and streaming rights."
                ),
            )
        ]
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Article(**item) for item in data]


@app.command()
def run(
    path: Optional[Path] = typer.Argument(
        None, help="Path to JSON list of articles."
    )
):
    """Summarize articles from a JSON file or built-in sample."""
    settings = get_settings()
    articles = _load_articles(path)

    if settings.openai_api_key:
        client = build_client(settings.openai_api_key)
    else:
        client = None
        rprint(
            "[yellow]OPENAI_API_KEY not set; using offline fallback summaries.[/yellow]"
        )

    bundle = summarize_articles(articles, client=client)

    table = Table(title="Article Summaries")
    table.add_column("Title")
    table.add_column("Source")
    table.add_column("Key Points")
    table.add_column("Takeaway")

    for summary in bundle.articles:
        table.add_row(
            summary.title,
            summary.source,
            "\n".join(summary.key_points),
            summary.takeaway,
        )

    rprint(table)


def main():
    app()


if __name__ == "__main__":
    main()
