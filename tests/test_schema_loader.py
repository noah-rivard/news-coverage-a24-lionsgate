import pytest

from news_coverage import schema


def test_loads_default_schema():
    loaded = schema.load_schema()
    assert loaded.get("title") == "CoverageArticle"
    assert "properties" in loaded


def test_validate_accepts_minimal_valid_payload():
    payload = {
        "company": "A24",
        "quarter": "2025 Q1",
        "section": "Highlights",
        "title": "Sample headline",
        "source": "Variety",
        "url": "https://example.com/story",
        "published_at": "2025-01-15",
    }
    validated = schema.validate_article_payload(payload)
    assert validated == payload


def test_validate_rejects_missing_required_field():
    payload = {
        "company": "A24",
        "quarter": "2025 Q1",
        "title": "Missing section",
        "source": "Variety",
        "url": "https://example.com/story",
        "published_at": "2025-01-15",
    }
    with pytest.raises(ValueError) as excinfo:
        schema.validate_article_payload(payload)
    assert "section" in str(excinfo.value)


def test_validate_rejects_bad_quarter_pattern():
    payload = {
        "company": "Lionsgate",
        "quarter": "2025Q1",
        "section": "Highlights",
        "title": "Bad quarter format",
        "source": "Deadline",
        "url": "https://example.com/lionsgate",
        "published_at": "2025-02-01",
    }
    with pytest.raises(ValueError) as excinfo:
        schema.validate_article_payload(payload)
    assert "quarter" in str(excinfo.value)
