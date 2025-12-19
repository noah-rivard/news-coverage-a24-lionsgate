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
        "title": "Sample headline",
        "source": "Variety",
        "url": "https://example.com/story",
        "published_at": "2025-01-15",
        "facts": [
            {
                "fact_id": "fact-1",
                "category_path": "Content, Deals, Distribution -> TV -> Development",
                "section": "Content / Deals / Distribution",
                "subheading": "Development",
                "company": "A24",
                "quarter": "2025 Q1",
                "published_at": "2025-01-15",
                "content_line": "First point",
                "summary_bullets": ["First point"],
            }
        ],
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
        "facts": [],
    }
    with pytest.raises(ValueError) as excinfo:
        schema.validate_article_payload(payload)
    assert "facts" in str(excinfo.value)


def test_validate_rejects_bad_quarter_pattern():
    payload = {
        "company": "Lionsgate",
        "quarter": "2025Q1",
        "title": "Bad quarter format",
        "source": "Deadline",
        "url": "https://example.com/lionsgate",
        "published_at": "2025-02-01",
        "facts": [
            {
                "fact_id": "fact-1",
                "category_path": "Content, Deals, Distribution -> TV -> Development",
                "section": "Content / Deals / Distribution",
                "subheading": "Development",
                "company": "Lionsgate",
                "quarter": "2025Q1",
                "published_at": "2025-02-01",
                "content_line": "First point",
                "summary_bullets": ["First point"],
            }
        ],
    }
    with pytest.raises(ValueError) as excinfo:
        schema.validate_article_payload(payload)
    assert "quarter" in str(excinfo.value)
