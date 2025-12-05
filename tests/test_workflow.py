import pytest
from news_coverage.models import Article
from news_coverage.workflow import (
    ClassificationResult,
    IngestResult,
    PipelineResult,
    SummaryResult,
    format_markdown,
    process_article,
    summarize_article,
    summarize_articles_batch,
)


def test_process_article_uses_injected_tools(tmp_path):
    article = Article(
        title="Sample Story",
        source="Demo",
        url="https://example.com",
        content="A24 and Lionsgate expand their partnership.",
    )

    def fake_classify(a, client):
        return ClassificationResult(
            category="Content, Deals & Distribution -> TV -> Development",
            section="Content / Deals / Distribution",
            subheading="Development",
            confidence=0.9,
            company="A24",
            quarter="2025 Q1",
        )

    def fake_summarize(a, prompt, client):
        return SummaryResult(bullets=["Point one", "Point two"])

    def fake_ingest(a, cls, summary):
        path = tmp_path / "data" / "ingest" / "A24" / "2025 Q1.jsonl"
        return IngestResult(stored_path=path, duplicate_of=None)

    result = process_article(
        article,
        client=None,
        classifier_fn=fake_classify,
        summarizer_fn=fake_summarize,
        formatter_fn=format_markdown,
        ingest_fn=fake_ingest,
    )

    assert isinstance(result, PipelineResult)
    assert "Point one" in result.markdown
    assert result.classification.company == "A24"
    assert result.ingest.duplicate_of is None


def test_parse_category_normalizes_ir_conference(monkeypatch):
    from news_coverage import workflow

    section, sub = workflow._parse_category_path(
        "Investor Relations -> General News & Strategy -> IR Conferences"
    )
    assert section == "Investor Relations"
    assert sub == "IR Conferences"


def test_summarize_article_omits_temperature_for_gpt5mini(monkeypatch):
    from news_coverage import workflow

    article = Article(
        title="Sample Story",
        source="Demo",
        url="https://example.com",
        content="A24 and Lionsgate expand their partnership.",
    )

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("SUMMARIZER_MODEL", "gpt-5-mini")
    monkeypatch.setattr(workflow, "_load_prompt_file", lambda _: "Prompt")

    captured = {}

    class DummyResponse:
        output_text = "- bullet one\n- bullet two"

    class DummyResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return DummyResponse()

    class DummyClient:
        responses = DummyResponses()

    result = summarize_article(article, "commentary.txt", DummyClient())

    assert "temperature" not in captured
    assert result.bullets == ["bullet one", "bullet two"]


def _fake_client(text_output: str):
    class _Resp:
        def __init__(self, text):
            self.output_text = text

    class _Responses:
        def __init__(self, text):
            self._text = text

        def create(self, **kwargs):
            return _Resp(self._text)

    class _Client:
        def __init__(self, text):
            self.responses = _Responses(text)

    return _Client(text_output)


def test_summarize_articles_batch_raises_on_missing_chunks():
    articles = [
        Article(title="One", source="Src", url="https://a.com", content="A"),
        Article(title="Two", source="Src", url="https://b.com", content="B"),
    ]
    client = _fake_client("Only one block")

    with pytest.raises(ValueError):
        summarize_articles_batch(articles, "general_news.txt", client)


def test_summarize_articles_batch_preserves_all_articles():
    articles = [
        Article(title="One", source="Src", url="https://a.com", content="A"),
        Article(title="Two", source="Src", url="https://b.com", content="B"),
    ]
    text = "Article 1:\n- first\n\nArticle 2:\n- second"
    client = _fake_client(text)

    summaries = summarize_articles_batch(articles, "general_news.txt", client)

    assert len(summaries) == 2
    assert summaries[0].bullets == ["first"]
    assert summaries[1].bullets == ["second"]
