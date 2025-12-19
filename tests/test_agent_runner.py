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
    def __init__(self, context, final_output=""):
        self.context_wrapper = type("Ctx", (), {"context": context})
        self.final_output = final_output


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
    # Ensure the manager agent was constructed with the expected tools.
    starting_agent = runner.calls[0][0]
    assert starting_agent.name == "manager"
    assert len(starting_agent.tools) == 4
    assert "Title: Sample Story" in final_path.read_text(encoding="utf-8")


def test_run_with_agent_respects_skip_duplicate(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AGENT_TRACE_PATH", "")
    final_path = tmp_path / "final_output.md"
    monkeypatch.setenv("FINAL_OUTPUT_PATH", str(final_path))
    classification, summary, ingest, markdown = _make_stubs(tmp_path)
    ingest_dup = IngestResult(stored_path=ingest.stored_path, duplicate_of="existing")

    class SkipAwareRunner(FakeRunner):
        def run_sync(self, starting_agent, input, context=None, **kwargs):
            chosen_ingest = ingest if context.skip_duplicate else ingest_dup
            self.ingest = chosen_ingest
            return super().run_sync(starting_agent, input, context, **kwargs)

    runner = SkipAwareRunner(classification, summary, ingest, markdown)

    article = Article(
        title="Another Story",
        source="Demo",
        url="https://example.com/other",
        content="Lionsgate moves into animation.",
    )

    result = run_with_agent(article, runner=runner, skip_duplicate=True)
    assert result.ingest.duplicate_of is None
    first_len = final_path.read_bytes()

    result_dup = run_with_agent(article, runner=runner, skip_duplicate=False)
    assert result_dup.ingest.duplicate_of == "existing"
    assert final_path.read_bytes() == first_len


def test_run_with_agent_batch_collects_errors(monkeypatch, tmp_path):
    good_article, good_result = _make_pipeline_result(tmp_path, "Good")
    bad_article, _ = _make_pipeline_result(tmp_path, "Bad")
    calls = []

    def fake_run(article, *, skip_duplicate=False, **_kwargs):
        calls.append((article.title, skip_duplicate))
        if article.title == "Bad":
            raise RuntimeError("boom")
        return good_result

    monkeypatch.setattr(agent_runner, "run_with_agent", fake_run)

    batch = run_with_agent_batch(
        [good_article, bad_article],
        skip_duplicate=[False, True],
        max_workers=2,
    )

    assert len(batch.items) == 2
    assert batch.items[0].result is not None
    assert batch.items[1].error == "boom"
    assert dict(calls)["Good"] is False
    assert dict(calls)["Bad"] is True
