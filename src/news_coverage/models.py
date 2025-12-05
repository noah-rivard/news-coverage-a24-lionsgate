"""Data models for news coverage workflow."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, HttpUrl, Field


class Article(BaseModel):
    """Normalized representation of an entertainment news article."""

    title: str
    source: str
    url: HttpUrl
    published_at: Optional[datetime] = Field(
        None, description="Publication timestamp; optional if unknown."
    )
    content: str = Field(..., description="Full text or main body of the article.")


class ArticleSummary(BaseModel):
    """Structured summary for a single article."""

    title: str
    source: str
    key_points: List[str]
    tone: str
    takeaway: str


class SummaryBundle(BaseModel):
    """Aggregated result for a batch of articles."""

    generated_at: datetime
    articles: List[ArticleSummary]
