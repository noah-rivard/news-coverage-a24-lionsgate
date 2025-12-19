"""Agent-driven orchestration of the news coverage pipeline using the Agents SDK."""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from agents import Agent, Runner, function_tool, OpenAIResponsesModel
from openai import AsyncOpenAI, OpenAI

from .config import get_settings
from .file_lock import locked_path
from .models import Article
from .workflow import (
    ClassificationResult,
    IngestResult,
    PipelineResult,
    SummaryResult,
    build_client,
    classify_article,
    append_final_output_entry,
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
    trace_events: list[dict[str, Any]] = dataclasses.field(default_factory=list)


@dataclass
class BatchItemResult:
    index: int
    article: Article
    result: PipelineResult | None
    error: str | None


@dataclass
class BatchRunResult:
    items: list[BatchItemResult]

    @property
    def successes(self) -> list[BatchItemResult]:
        return [item for item in self.items if item.error is None]

    @property
    def failures(self) -> list[BatchItemResult]:
        return [item for item in self.items if item.error is not None]


def _serialize_for_trace(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return _serialize_for_trace(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {k: _serialize_for_trace(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_for_trace(v) for v in value]
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except TypeError:
            pass
    if isinstance(value, Path):
        return str(value)
    return value


def _format_trace_log(
    *,
    created_at: datetime,
    duration_ms: int,
    model: str,
    instructions: str,
    input_text: str,
    raw_content: str | None,
    tool_events: list[dict[str, Any]],
    final_output: str,
) -> str:
    lines: list[str] = [
        "POST",
        "/v1/responses",
        "response",
        "unknown",
        f"{duration_ms}ms",
        "Properties",
        "Created",
        created_at.strftime("%b %d, %Y, %I:%M %p UTC"),
        "ID",
        "unknown",
        "Model",
        model,
        "Tokens",
        "unknown",
        "Functions",
        "classify_article",
        "()",
        "summarize_article",
        "()",
        "format_markdown",
        "()",
        "ingest_article",
        "()",
        "Configuration",
        "Response",
        "text",
        "Reasoning effort",
        "unknown",
        "Verbosity",
        "unknown",
        "Instructions",
        "System Instructions",
        instructions,
        "Input",
        "user",
        input_text,
        "Article Content",
        raw_content or "",
    ]

    for event in tool_events:
        tool_name = event.get("tool", "unknown")
        output_value = event.get("output")
        output_text = json.dumps(output_value, ensure_ascii=True)
        lines.extend(
            [
                "Function call",
                "Arguments",
                f"{tool_name}()",
                "Output",
                output_text,
            ]
        )

    lines.extend(
        [
            "Output",
            "assistant",
            final_output,
        ]
    )
    return "\n".join(lines)


def _append_trace_log(trace_text: str, destination: str | Path) -> None:
    path = Path(destination).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with locked_path(path):
        existing_text = path.read_text(encoding="utf-8") if path.exists() else ""
        needs_spacing = bool(existing_text.strip())
        trailing_newlines = len(existing_text) - len(existing_text.rstrip("\n"))
        spacer_count = max(0, 2 - trailing_newlines) if needs_spacing else 0
        spacer = "\n" * spacer_count
        with path.open("a", encoding="utf-8") as f:
            f.write(f"{spacer}{trace_text}\n")


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
        payload = dataclasses.asdict(context.classification)
        context.trace_events.append({"tool": "classify_article", "output": payload})
        return payload

    @function_tool(name_override="summarize_article")
    def summarize() -> dict:
        """Summarize the article using the routed prompt and store bullets."""
        if context.classification is None:
            raise RuntimeError("Classification missing; run classify_article first.")
        prompt_name, _ = _route_prompt_and_formatter(context.classification)
        context.summary = summarize_article(context.article, prompt_name, context.client)
        if not context.summary.facts:
            from .workflow import _assemble_facts

            context.summary.facts = _assemble_facts(
                context.summary.bullets, context.classification, context.article
            )
        payload = _serialize_for_trace(context.summary)
        context.trace_events.append({"tool": "summarize_article", "output": payload})
        return payload

    @function_tool(name_override="format_markdown")
    def format_markdown_tool() -> str:
        """Format the summary into delivery-ready markdown and store it."""
        if context.classification is None or context.summary is None:
            raise RuntimeError("Classification and summary required before formatting.")
        context.markdown = format_markdown(context.article, context.classification, context.summary)
        context.trace_events.append({"tool": "format_markdown", "output": context.markdown})
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
        payload = {
            "stored_path": str(context.ingest.stored_path),
            "duplicate_of": context.ingest.duplicate_of,
        }
        context.trace_events.append({"tool": "ingest_article", "output": payload})
        return payload

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
    input_text = "Process the provided article in context.article"
    start_time = datetime.now(timezone.utc)
    result = active_runner.run_sync(
        agent,
        input=input_text,
        context=context,
        max_turns=8,
    )
    end_time = datetime.now(timezone.utc)
    duration_ms = max(0, int((end_time - start_time).total_seconds() * 1000))

    if not context.classification or not context.summary or not context.ingest:
        raise RuntimeError("Agent run did not complete all pipeline steps.")

    markdown_text = context.markdown or (
        result.final_output if isinstance(result.final_output, str) else ""
    )

    if settings.agent_trace_path:
        trace_text = _format_trace_log(
            created_at=start_time,
            duration_ms=duration_ms,
            model=settings.manager_model,
            instructions=instructions,
            input_text=input_text,
            raw_content=context.article.content,
            tool_events=[
                {
                    "tool": event.get("tool"),
                    "output": _serialize_for_trace(event.get("output")),
                }
                for event in context.trace_events
            ],
            final_output=markdown_text,
        )
        _append_trace_log(trace_text, settings.agent_trace_path)

    if not context.ingest.duplicate_of:
        append_final_output_entry(article, context.classification, context.summary)

    return PipelineResult(
        markdown=markdown_text,
        classification=context.classification,
        summary=context.summary,
        ingest=context.ingest,
    )


def run_with_agent_batch(
    articles: list[Article],
    *,
    skip_duplicate: bool | list[bool] = False,
    max_workers: int = 4,
    runner_factory: Callable[[], Runner] | None = None,
) -> BatchRunResult:
    """
    Run multiple articles through the manager agent in parallel.

    Each article is processed independently; failures are captured alongside successes
    instead of aborting the entire batch.
    """
    if max_workers < 1:
        raise ValueError("max_workers must be >= 1.")
    if not articles:
        return BatchRunResult(items=[])

    if isinstance(skip_duplicate, list):
        if len(skip_duplicate) != len(articles):
            raise ValueError("skip_duplicate list must match number of articles.")
        skip_flags = list(skip_duplicate)
    else:
        skip_flags = [skip_duplicate] * len(articles)

    worker_count = min(max_workers, len(articles))
    outcomes: list[BatchItemResult | None] = [None] * len(articles)

    def _run_single(idx: int, article: Article) -> PipelineResult:
        runner = runner_factory() if runner_factory else None
        return run_with_agent(article, skip_duplicate=skip_flags[idx], runner=runner)

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_map = {
            executor.submit(_run_single, idx, article): idx
            for idx, article in enumerate(articles)
        }
        for future in as_completed(future_map):
            idx = future_map[future]
            article = articles[idx]
            try:
                result = future.result()
                outcomes[idx] = BatchItemResult(
                    index=idx, article=article, result=result, error=None
                )
            except Exception as exc:
                outcomes[idx] = BatchItemResult(
                    index=idx, article=article, result=None, error=str(exc)
                )

    return BatchRunResult(items=[item for item in outcomes if item is not None])
