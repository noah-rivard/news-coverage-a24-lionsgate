"""Helpers to load and validate the coverage JSON schema."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError


def _project_root() -> Path:
    # __file__ -> src/news_coverage/schema.py; repo root is three levels up
    return Path(__file__).resolve().parents[2]


def default_schema_path() -> Path:
    """Return the path to the canonical coverage schema file."""
    return _project_root() / "docs" / "templates" / "coverage_schema.json"


@lru_cache(maxsize=1)
def load_schema(path: Optional[Path | str] = None) -> Dict[str, Any]:
    """Load and cache the coverage schema as a dictionary."""
    schema_path = Path(path) if path else default_schema_path()
    return json.loads(schema_path.read_text(encoding="utf-8"))


def format_errors(errors: Iterable[ValidationError]) -> str:
    """Turn jsonschema errors into a concise human-readable string."""
    parts = []
    for err in errors:
        location = ".".join(str(piece) for piece in err.absolute_path) or "<root>"
        parts.append(f"{location}: {err.message}")
    return "; ".join(parts)


def validate_article_payload(
    payload: Dict[str, Any], schema: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Validate a payload against the coverage schema.

    Raises ValueError with a readable message if validation fails.
    """
    schema_dict = schema or load_schema()
    validator = Draft202012Validator(schema_dict, format_checker=FormatChecker())
    errors = list(validator.iter_errors(payload))
    if errors:
        raise ValueError(f"Schema validation failed: {format_errors(errors)}")
    return payload
