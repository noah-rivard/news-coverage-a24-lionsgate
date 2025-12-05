from news_coverage.models import Article
from news_coverage.workflow import summarize_articles


def test_summarize_articles_offline_fallback():
    articles = [
        Article(
            title="Sample Story",
            source="Demo",
            url="https://example.com",
            content=(
                "A24 and Lionsgate expand their partnership across streaming "
                "and theatrical windows."
            ),
        )
    ]

    bundle = summarize_articles(articles, client=None)

    assert len(bundle.articles) == 1
    summary = bundle.articles[0]
    assert summary.title == "Sample Story"
    assert summary.key_points
    assert "offline" in summary.takeaway.lower()
