import pytest

from news_coverage.buyer_routing import BUYER_KEYWORDS, parse_buyers_of_interest


def test_parse_buyers_of_interest_defaults_to_all_buyers():
    assert parse_buyers_of_interest(None) == set(BUYER_KEYWORDS.keys())
    assert parse_buyers_of_interest("") == set(BUYER_KEYWORDS.keys())


def test_parse_buyers_of_interest_accepts_legacy_doc_names():
    assert parse_buyers_of_interest("Comcast,Warner Bros Discovery") == {
        "Comcast/NBCU",
        "WBD",
    }


def test_parse_buyers_of_interest_raises_on_unknown():
    with pytest.raises(ValueError, match="unknown buyer"):
        parse_buyers_of_interest("NotARealBuyer")
