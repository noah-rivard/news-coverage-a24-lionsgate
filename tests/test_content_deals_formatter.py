import datetime
import pytest

from src.news_coverage.models import Article
from src.news_coverage.workflow import (
    ClassificationResult,
    SummaryResult,
    format_content_deals,
    _route_prompt_and_formatter,
)


@pytest.fixture()
def sample_article():
    return Article(
        title="Netflix Brazil slate",
        source="Variety",
        url="https://example.com/variety-slate",
        published_at=datetime.datetime(2025, 12, 9, 23, 0, 0),
        content="placeholder body",
    )


def test_format_content_deals_preserves_lines_and_dates(sample_article):
    classification = ClassificationResult(
        category="Content, Deals & Distribution -> International -> Greenlights -> TV",
        section="Content / Deals / Distribution",
        subheading="International",
        confidence=0.9,
        company="Netflix",
        quarter="2025 Q4",
    )
    bullets = [
        "[Brazil] The Pilgrimage: Netflix, drama (12/9)",
        "[Brazil] A Estranha na Cama: Netflix, psychological thriller (12/9)",
        "[Brazil] Rauls: Netflix, crime drama (12/9)",
        "[Brazil] Habeas Corpus: Netflix, legal drama (12/9)",
        "[Brazil] Os 12 Signos de Valentina: Netflix, romantic comedy (12/9)",
        "[Brazil] As Crianças Estão de Volta: Netflix, family drama (12/9)",
        "[Brazil] Sua Mãe Te Conhece: Netflix, reality competition (12/9)",
    ]
    summary = SummaryResult(bullets=bullets)

    rendered = format_content_deals(sample_article, classification, summary)

    assert rendered == "\n".join(bullets)


def test_format_content_deals_appends_date_when_parentheses_are_not_dates(sample_article):
    classification = ClassificationResult(
        category="Content, Deals & Distribution -> International -> Greenlights -> TV",
        section="Content / Deals / Distribution",
        subheading="International",
        confidence=0.9,
        company="Netflix",
        quarter="2025 Q4",
    )
    bullets = [
        "[Brazil] The Pilgrimage (Director's Cut): Netflix, drama",
        "[Brazil] Rauls (Festival Cut): Netflix, crime drama (12/9)",
    ]
    summary = SummaryResult(bullets=bullets)

    rendered = format_content_deals(sample_article, classification, summary)

    assert rendered.splitlines() == [
        "[Brazil] The Pilgrimage (Director's Cut): Netflix, drama (12/9)",
        "[Brazil] Rauls (Festival Cut): Netflix, crime drama (12/9)",
    ]


def test_route_uses_content_deals_formatter_for_international_deals(sample_article):
    classification = ClassificationResult(
        category="Content, Deals & Distribution -> International -> Greenlights -> TV",
        section="Content / Deals / Distribution",
        subheading="International",
        confidence=None,
        company="Netflix",
        quarter="2025 Q4",
    )
    prompt_name, formatter_fn = _route_prompt_and_formatter(classification)

    assert prompt_name == "content_deals.txt"
    assert formatter_fn.__name__ == "format_content_deals"
