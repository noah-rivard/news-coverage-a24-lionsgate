"""Buyer keyword routing for multi-buyer DOCX generation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Set, Tuple
from urllib.parse import urlparse

from .models import Article


# Case-insensitive keyword lists per buyer.
BUYER_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "Amazon": ("amazon", "prime video", "mgm", "amazon mgm", "freevee"),
    "Apple": ("apple", "apple tv+", "appletv", "tv", "tv plus"),
    "Comcast/NBCU": (
        "comcast",
        "nbc",
        "nbcu",
        "peacock",
        "universal",
        "universal pictures",
        "universal tv",
        "usa network",
        "syfy",
        "bravo",
        "telemundo",
        "sky",
    ),
    "Disney": (
        "disney",
        "disney+",
        "disney plus",
        "walt disney",
        "wdw",
        "pixar",
        "marvel",
        "lucasfilm",
        "espn",
        "hulu",
        "abc",
        "fx",
        "nat geo",
    ),
    "Netflix": ("netflix", "nflx"),
    "Paramount": (
        "paramount",
        "paramount+",
        "paramount plus",
        "p+",
        "cbs",
        "showtime",
        "mtv",
        "nickelodeon",
        "nick",
        "pluto tv",
    ),
    "Sony": (
        "sony",
        "sony pictures",
        "spe",
        "crunchyroll",
        "funimation",
        "columbia pictures",
        "tri-star",
        "tristar",
        "screen gems",
        "playstation productions",
    ),
    "WBD": (
        "warner bros",
        "warner bros. discovery",
        "wbd",
        "wb",
        "warner media",
        "warner hbo",
        "hbo",
        "max",
        "discovery",
        "discovery+",
        "tnt",
        "tbs",
        "cnn",
        "dc studios",
        "warner animation",
    ),
    "A24": ("a24",),
    "Lionsgate": (
        "lionsgate",
        "lions gate",
        "starz",
        "starzplay",
        "starz play",
        "grindstone",
    ),
}


@dataclass(frozen=True)
class BuyerMatch:
    """Matches for a single buyer."""

    strong: Set[str]
    weak: Set[str]


def _lower(text: str) -> str:
    return text.lower()


def _host_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def match_buyers(article: Article, body: str | None = None) -> BuyerMatch:
    """
    Return strong and weak buyer matches for an article.

    Strong: keyword appears in title, in first 400 chars of body, or in URL host.
    Weak: keyword appears elsewhere in body (but not already strong).
    """

    title = _lower(article.title)
    url_host = _host_from_url(str(article.url))
    body_text = _lower(body or article.content or "")
    lead = body_text[:400]

    strong: Set[str] = set()
    weak: Set[str] = set()

    for buyer, keywords in BUYER_KEYWORDS.items():
        for kw in keywords:
            # Use regex word-ish match to avoid substring noise (e.g., "max" vs "maxwell")
            pattern = rf"(?<!\\w){re.escape(kw)}(?!\\w)"
            if (
                re.search(pattern, title)
                or re.search(pattern, lead)
                or re.search(pattern, url_host)
            ):
                strong.add(buyer)
                break
            if buyer not in strong and re.search(pattern, body_text):
                weak.add(buyer)
                break

    # Remove duplicates in weak that are strong
    weak -= strong
    return BuyerMatch(strong=strong, weak=weak)


def buyers_from_keywords(text: str) -> Set[str]:
    """
    Convenience helper to match buyers from arbitrary text (not used in CLI directly).
    """
    dummy_article = Article(title="", source="", url="https://example.com", content=text)
    match = match_buyers(dummy_article, body=text)
    return match.strong | match.weak
