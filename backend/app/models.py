"""Data schemas shared by the LLM layer, storage and the API."""
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


class Listing(BaseModel):
    """What the model writes for one product."""

    title: str
    description: str
    highlights: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    # Questions for the seller about details buyers care about but the photos don't show.
    missing_info: list[str] = Field(default_factory=list)


class Product(BaseModel):
    """A saved catalog entry."""

    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    name: str
    keywords: str
    price: str | None = None
    category: str | None = None
    photos: list[str] = Field(default_factory=list)
    listing: Listing
    model: str
    generation_seconds: float = 0.0
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
