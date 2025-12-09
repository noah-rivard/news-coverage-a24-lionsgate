"""Agent-driven orchestration of the news coverage pipeline using the Agents SDK."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Optional

from agents import Agent, Runner, function_tool, OpenAIResponsesModel
from openai import AsyncOpenAI, OpenAI

from .config import get_settings
from .models import Article
from .workflow import (
    ClassificationResult,
    IngestResult,
    PipelineResult,
    SummaryResult,
    build_client,
    classify_article,
    format_markdown,
    ingest_article,
    summarize_article,
    _require_api_key,
    _route_prompt_and_formatter,
)


@dataclass
class PipelineContext:
    """State shared across tools during a single agent run."""

    article: Article
    client: OpenAI
    skip_duplicate: bool = False
    classification: ClassificationResult | None = None
    summary: SummaryResult | None = None
    markdown: str | None = None
    ingest: IngestResult | None = None


def _build_clients(user_client: Optional[OpenAI]) -> tuple[OpenAI, AsyncOpenAI]:
    """Return (sync_client, async_client) using provided client or env key."""
    settings = get_settings()
    api_key = _require_api_key(settings)
    sync_client = user_client or build_client(api_key)
    async_client = AsyncOpenAI(api_key=api_key)
    return sync_client, async_client


def _make_tools(context: PipelineContext):
    """Create function tools that operate on the shared pipeline context."""

    @function_tool(name_override="classify_article")
    def classify() -> dict:
        """Classify the article in context and store the result."""
        context.classification = classify_article(context.article, context.client)
        return dataclasses.asdict(context.classification)

    @function_tool(name_override="summarize_article")
    def summarize() -> dict:
        """Summarize the article using the routed prompt and store bullets."""
        if context.classification is None:
            raise RuntimeError("Classification missing; run classify_article first.")
        prompt_name, _ = _route_prompt_and_formatter(context.classification)
        context.summary = summarize_article(context.article, prompt_name, context.client)
        return dataclasses.asdict(context.summary)

    @function_tool(name_override="format_markdown")
    def format_markdown_tool() -> str:
        """Format the summary into delivery-ready markdown and store it."""
        if context.classification is None or context.summary is None:
            raise RuntimeError("Classification and summary required before formatting.")
        context.markdown = format_markdown(context.article, context.classification, context.summary)
        return context.markdown

    @function_tool(name_override="ingest_article")
    def ingest() -> dict:
        """Validate and store the article; respects skip_duplicate flag in context."""
        if context.classification is None or context.summary is None:
            raise RuntimeError("Classification and summary required before ingest.")
        context.ingest = ingest_article(
            context.article,
            context.classification,
            context.summary,
            skip_duplicate=context.skip_duplicate,
        )
        return {
            "stored_path": str(context.ingest.stored_path),
            "duplicate_of": context.ingest.duplicate_of,
        }

    return [classify, summarize, format_markdown_tool, ingest]


def run_with_agent(
    article: Article,
    client: Optional[OpenAI] = None,
    *,
    skip_duplicate: bool = False,
    runner: Optional[Runner] = None,
) -> PipelineResult:
    """
    Run a single article through the manager agent (Agents SDK).

    The manager agent calls tools that share a PipelineContext, ensuring
    classification, summarization, formatting, and ingest occur in order.
    """
    settings = get_settings()
    sync_client, async_client = _build_clients(client)
    context = PipelineContext(article=article, client=sync_client, skip_duplicate=skip_duplicate)

    tools = _make_tools(context)
    instructions = (
        "You are the manager for a news coverage pipeline. The article is already loaded "
        "in context.article; never ask for it from the user. Call these tools in order: "
        "classify_article -> summarize_article -> format_markdown -> ingest_article. "
        "After ingest, respond with the markdown exactly as returned by format_markdown."
    )
    agent = Agent(
        name="manager",
        instructions=instructions,
        tools=tools,
        model=OpenAIResponsesModel(settings.manager_model, async_client),
        output_type=str,
    )

    active_runner = runner or Runner()
    result = active_runner.run_sync(
        agent,
        input="Process the provided article in context.article",
        context=context,
        max_turns=8,
    )

    if not context.classification or not context.summary or not context.ingest:
        raise RuntimeError("Agent run did not complete all pipeline steps.")

    markdown_text = context.markdown or (
        result.final_output if isinstance(result.final_output, str) else ""
    )

    return PipelineResult(
        markdown=markdown_text,
        classification=context.classification,
        summary=context.summary,
        ingest=context.ingest,
    )
