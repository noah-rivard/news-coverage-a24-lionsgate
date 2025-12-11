from datetime import datetime

from news_coverage.models import Article
from news_coverage.workflow import _infer_company


def make_article(title: str, content: str = "", url: str = "https://example.com") -> Article:
    body = content or title
    return Article(
        title=title,
        source="TestWire",
        url=url,
        published_at=datetime(2025, 12, 10),
        content=body,
    )


def test_infer_company_netflix_title():
    article = make_article("Netflix orders new comedy special from Mike Epps")
    assert _infer_company(article) == "Netflix"


def test_infer_company_wbd_from_url_host():
    article = make_article(
        title="Max announces documentary slate",
        content="",
        url="https://www.hbo.com/shows/new-doc",
    )
    assert _infer_company(article) == "WBD"


def test_infer_company_prefers_priority_when_multiple():
    article = make_article(
        title="Apple TV+ and A24 partner with Lionsgate on thriller",
        content="Joint production between A24, Lionsgate, and Apple.",
    )
    # Apple appears first in the buyer priority ordering.
    assert _infer_company(article) == "Apple"


def test_infer_company_unknown_when_no_match():
    article = make_article(
        title="Regional film festival announces new programming team",
        content="The festival focuses on emerging voices and indie filmmakers.",
    )
    assert _infer_company(article) == "Unknown"


def test_infer_company_ignores_substring_noise():
    article = make_article(
        title="Maxwell releases new album ahead of tour",
        content="Soul singer Maxwell previewed tracks from his upcoming record.",
    )
    assert _infer_company(article) == "Unknown"
