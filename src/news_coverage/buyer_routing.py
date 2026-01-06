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
    # Put broadcast brands first so title/lead hits become strong before
    # broader "paramount" body matches can short-circuit as weak.
    "Paramount": (
        "cbs",
        "showtime",
        "mtv",
        "nickelodeon",
        "nick",
        "pluto tv",
        "paramount",
        "paramount+",
        "paramount plus",
        "p+",
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

BUYER_DISPLAY_NAMES: Dict[str, str] = {
    # Align with the historical quarterly “News Coverage” doc naming.
    "Comcast/NBCU": "Comcast",
    "WBD": "Warner Bros Discovery",
}


def buyer_display_name(buyer: str) -> str:
    """Return the human-facing buyer label used in DOCX filenames."""
    return BUYER_DISPLAY_NAMES.get(buyer, buyer)


def _normalize_buyer_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()


_CANONICAL_BUYER_BY_NORMALIZED: Dict[str, str] = {
    _normalize_buyer_name(buyer): buyer for buyer in BUYER_KEYWORDS.keys()
}

_BUYER_ALIASES: Dict[str, str] = {
    # Comcast/NBCU aliases (common in legacy doc names).
    _normalize_buyer_name("Comcast"): "Comcast/NBCU",
    _normalize_buyer_name("NBCU"): "Comcast/NBCU",
    _normalize_buyer_name("NBCUniversal"): "Comcast/NBCU",
    _normalize_buyer_name("NBC Universal"): "Comcast/NBCU",
    _normalize_buyer_name("NBCU/Comcast"): "Comcast/NBCU",
    # WBD aliases (common in legacy doc names).
    _normalize_buyer_name("Warner Bros Discovery"): "WBD",
    _normalize_buyer_name("Warner Bros. Discovery"): "WBD",
    _normalize_buyer_name("Warner Brothers Discovery"): "WBD",
    _normalize_buyer_name("WarnerMedia"): "WBD",
}


def canonicalize_buyer_name(name: str) -> str | None:
    """
    Map a user-facing buyer name to our canonical buyer key (or None if unknown).
    """
    normalized = _normalize_buyer_name(name)
    if not normalized:
        return None
    if normalized in _CANONICAL_BUYER_BY_NORMALIZED:
        return _CANONICAL_BUYER_BY_NORMALIZED[normalized]
    return _BUYER_ALIASES.get(normalized)


def parse_buyers_of_interest(raw: str | None) -> set[str]:
    """
    Parse BUYERS_OF_INTEREST into a validated set of canonical buyers.

    When unset/blank, returns all buyers in BUYER_KEYWORDS.
    """
    known = set(BUYER_KEYWORDS.keys())
    if not raw or not raw.strip():
        return known

    parts = [p.strip() for p in raw.split(",") if p.strip()]
    selected: set[str] = set()
    unknown: list[str] = []
    for part in parts:
        canonical = canonicalize_buyer_name(part)
        if canonical is None:
            unknown.append(part)
        else:
            selected.add(canonical)

    if unknown:
        raise ValueError(
            "BUYERS_OF_INTEREST contains unknown buyer(s): {unknown}. "
            "Known buyers: {known}. Aliases include: Comcast (-> Comcast/NBCU), "
            "Warner Bros Discovery (-> WBD).".format(
                unknown=sorted(unknown), known=sorted(known)
            )
        )
    return selected


@dataclass(frozen=True)
class BuyerMatch:
    """Matches for a single buyer."""

    strong: Set[str]
    weak: Set[str]


@dataclass(frozen=True)
class BuyerScore:
    """Best match score and location for a buyer within an article."""

    buyer: str
    score: int
    earliest_pos: int
    matched_in: str


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
            pattern = rf"(?<!\w){re.escape(kw)}(?!\w)"
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


def _first_match_pos(pattern: str, text: str) -> int | None:
    """Return the first match position or None if not found."""
    match = re.search(pattern, text)
    return match.start() if match else None


def score_buyer_matches(article: Article, body: str | None = None) -> list[BuyerScore]:
    """
    Return best match scores per buyer, favoring earlier and stronger placements.

    Title matches outrank lead matches, which outrank URL host, which outrank body.
    Within a given location, earlier positions score higher.
    """
    title = _lower(article.title)
    url_host = _host_from_url(str(article.url))
    body_text = _lower(body or article.content or "")
    lead = body_text[:400]

    # Weighted bases keep title/lead ahead of deeper-body mentions.
    location_weights = (
        ("title", title, 3000),
        ("lead", lead, 2000),
        ("url", url_host, 1500),
        ("body", body_text, 1000),
    )

    scores: list[BuyerScore] = []
    for buyer, keywords in BUYER_KEYWORDS.items():
        best: BuyerScore | None = None
        for kw in keywords:
            pattern = rf"(?<!\w){re.escape(kw)}(?!\w)"
            for location, text, base in location_weights:
                pos = _first_match_pos(pattern, text)
                if pos is None:
                    continue
                score = max(0, base - pos)
                candidate = BuyerScore(
                    buyer=buyer, score=score, earliest_pos=pos, matched_in=location
                )
                if (
                    best is None
                    or candidate.score > best.score
                    or (
                        candidate.score == best.score
                        and candidate.earliest_pos < best.earliest_pos
                    )
                ):
                    best = candidate
        if best is not None:
            scores.append(best)
    return scores


def buyers_from_keywords(text: str) -> Set[str]:
    """
    Convenience helper to match buyers from arbitrary text (not used in CLI directly).
    """
    dummy_article = Article(title="", source="", url="https://example.com", content=text)
    match = match_buyers(dummy_article, body=text)
    return match.strong | match.weak
