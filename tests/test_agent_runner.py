from pathlib import Path

from news_coverage import agent_runner
from news_coverage.agent_runner import run_with_agent, run_with_agent_batch
from news_coverage.models import Article
from news_coverage.workflow import (
    ClassificationResult,
    SummaryResult,
    IngestResult,
    PipelineResult,
)


class FakeResult:
    def __init__(self, context, final_output="", raw_responses=None, last_response_id=None):
        self.context_wrapper = type("Ctx", (), {"context": context})
        self.final_output = final_output
        self.raw_responses = raw_responses or []
        self.last_response_id = last_response_id


class FakeRunner:
    def __init__(self, classification, summary, ingest, markdown):
        self.calls = []
        self.classification = classification
        self.summary = summary
        self.ingest = ingest
        self.markdown = markdown

    def run_sync(self, starting_agent, input, context=None, **kwargs):
        self.calls.append((starting_agent, input, kwargs))
        context.classification = self.classification
        context.summary = self.summary
        context.ingest = self.ingest
        context.markdown = self.markdown
        return FakeResult(context, final_output=self.markdown)


def _make_stubs(tmp_path: Path):
    classification = ClassificationResult(
        category="Content, Deals & Distribution -> TV -> Development",
        section="Content / Deals / Distribution",
        subheading="Development",
        confidence=0.9,
        company="A24",
        quarter="2025 Q4",
    )
    summary = SummaryResult(bullets=["First point", "Second point"], facts=[])
    ingest = IngestResult(
        stored_path=tmp_path / "data" / "ingest" / "A24" / "2025 Q4.jsonl",
        duplicate_of=None,
    )
    markdown = (
        "Title: Sample\n"
        "Category: Content -> Deals -> Distribution -> TV -> Development\n"
        "Content: First point ([12/5](https://example.com))"
    )
    return classification, summary, ingest, markdown


def _make_pipeline_result(tmp_path: Path, title: str) -> tuple[Article, PipelineResult]:
    article = Article(
        title=title,
        source="Demo",
        url=f"https://example.com/{title.lower()}",
        content="Body text.",
    )
    classification = ClassificationResult(
        category="Strategy & Miscellaneous News -> General News & Strategy",
        section="Strategy & Miscellaneous News",
        subheading="General News & Strategy",
        confidence=0.8,
        company="A24",
        quarter="2025 Q4",
    )
    summary = SummaryResult(bullets=[f"{title} summary"], facts=[])
    ingest = IngestResult(
        stored_path=tmp_path / "data" / "ingest" / "A24" / "2025 Q4.jsonl",
        duplicate_of=None,
    )
    markdown = f"Title: {title}"
    result = PipelineResult(
        markdown=markdown,
        classification=classification,
        summary=summary,
        ingest=ingest,
    )
    return article, result


def test_run_with_agent_uses_runner_and_context(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AGENT_TRACE_PATH", "")
    final_path = tmp_path / "final_output.md"
    monkeypatch.setenv("FINAL_OUTPUT_PATH", str(final_path))
    classification, summary, ingest, markdown = _make_stubs(tmp_path)
    runner = FakeRunner(classification, summary, ingest, markdown)

    article = Article(
        title="Sample Story",
        source="Demo",
        url="https://example.com/story",
        content="A24 expands its slate.",
    )

    result = run_with_agent(article, runner=runner)

    assert result.classification == classification
    assert result.summary == summary
    assert result.ingest == ingest
    assert result.markdown == markdown
    assert isinstance(result.openai_response_ids, dict)
    # Ensure the manager agent was constructed with the expected tools.
    starting_agent = runner.calls[0][0]
    assert starting_agent.name == "manager"
    assert len(starting_agent.tools) == 4
    assert "Title: Sample Story" in final_path.read_text(encoding="utf-8")


def test_run_with_agent_records_manager_response_ids(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AGENT_TRACE_PATH", "")
    final_path = tmp_path / "final_output.md"
    monkeypatch.setenv("FINAL_OUTPUT_PATH", str(final_path))
    classification, summary, ingest, markdown = _make_stubs(tmp_path)

    class StubModelResponse:
        def __init__(self, response_id: str):
            self.response_id = response_id

    class RunnerWithResponses(FakeRunner):
        def run_sync(self, starting_agent, input, context=None, **kwargs):
            self.calls.append((starting_agent, input, kwargs))
            context.classification = self.classification
            context.summary = self.summary
            context.ingest = self.ingest
            context.markdown = self.markdown
            return FakeResult(
                context,
                final_output=self.markdown,
                raw_responses=[StubModelResponse("resp_a"), StubModelResponse("resp_b")],
                last_response_id="resp_b",
            )

    runner = RunnerWithResponses(classification, summary, ingest, markdown)
    article = Article(
        title="Sample Story",
        source="Demo",
        url="https://example.com/story",
        content="A24 expands its slate.",
    )

    result = run_with_agent(article, runner=runner)
    assert result.openai_response_ids["manager_agent"] == ["resp_a", "resp_b"]


def test_run_with_agent_batch_collects_errors(monkeypatch, tmp_path):
    good_article, good_result = _make_pipeline_result(tmp_path, "Good")
    bad_article, _ = _make_pipeline_result(tmp_path, "Bad")
    calls = []

    def fake_run(article, **_kwargs):
        calls.append(article.title)
        if article.title == "Bad":
            raise RuntimeError("boom")
        return good_result

    monkeypatch.setattr(agent_runner, "run_with_agent", fake_run)

    batch = run_with_agent_batch(
        [good_article, bad_article],
        max_workers=2,
    )

    assert len(batch.items) == 2
    assert batch.items[0].result is not None
    assert batch.items[1].error == "boom"
    assert set(calls) == {"Good", "Bad"}
