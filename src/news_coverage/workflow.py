"""Workflow for summarizing entertainment news articles."""

from datetime import datetime, timezone
from typing import Iterable, List, Optional

from openai import OpenAI

from .config import get_settings
from .models import Article, ArticleSummary, SummaryBundle


def _format_prompt(articles: Iterable[Article]) -> str:
    """Build a concise prompt for the Responses API."""
    lines = [
        "You are an entertainment-news assistant. Summarize each article separately.",
        (
            "Return 3-5 bullet key points, describe tone (e.g., upbeat, critical), "
            "and give one-sentence takeaway."
        ),
    ]
    for idx, article in enumerate(articles, start=1):
        lines.append(f"\nArticle {idx}:")
        lines.append(f"Title: {article.title}")
        lines.append(f"Source: {article.source}")
        if article.published_at:
            lines.append(f"Published: {article.published_at.isoformat()}")
        lines.append(f"URL: {article.url}")
        lines.append("Content:")
        lines.append(article.content)
    return "\n".join(lines)


def build_client(api_key: Optional[str] = None) -> OpenAI:
    """Create an OpenAI client; separated for easier testing."""
    return OpenAI(api_key=api_key)


def summarize_articles(
    articles: List[Article], client: Optional[OpenAI] = None
) -> SummaryBundle:
    """
    Summarize a list of articles using the OpenAI Responses API.

    If no client is provided, a short offline summary is produced (useful for tests).
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)

    if not articles:
        return SummaryBundle(generated_at=now, articles=[])

    if client is None:
        # Offline deterministic fallback for tests and environments without API keys.
        summaries = [
            ArticleSummary(
                title=article.title,
                source=article.source,
                key_points=[article.content[:80] + "..."],
                tone="unknown",
                takeaway="Summary unavailable (offline mode).",
            )
            for article in articles
        ]
        return SummaryBundle(generated_at=now, articles=summaries)

    prompt = _format_prompt(articles)
    response = client.responses.create(
        model=settings.model,
        input=[
            {
                "role": "system",
                "content": "You produce crisp article summaries for non-technical readers.",
            },
            {"role": "user", "content": prompt},
        ],
        max_output_tokens=settings.max_tokens,
        temperature=settings.temperature,
    )

    text_output = getattr(response, "output_text", None) or str(response)
    # Split on "Article" markers to map summaries back; upgrade to structured parsing later.
    chunks = [
        chunk.strip() for chunk in text_output.split("Article") if chunk.strip()
    ]
    summaries: List[ArticleSummary] = []
    for article, chunk in zip(articles, chunks):
        points = [
            line.lstrip("-• ").strip()
            for line in chunk.splitlines()
            if line.strip().startswith(("-", "•"))
        ]
        summaries.append(
            ArticleSummary(
                title=article.title,
                source=article.source,
                key_points=points or [chunk[:120] + "..."],
                tone="unspecified",
                takeaway="See key points above.",
            )
        )

    return SummaryBundle(generated_at=now, articles=summaries)
