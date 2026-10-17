"""Data schemas shared by the LLM layer, storage and the API."""
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Listing(BaseModel):
    """What the model writes for one product."""

    title: str
    description: str
    highlights: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    # Questions for the seller about details buyers care about but the photos don't show.
    missing_info: list[str] = Field(default_factory=list)
    # Set by the claim guard (claims.py), not by the model:
    removed_claims: list[str] = Field(default_factory=list)  # taken out: nobody confirmed them
    check_claims: list[str] = Field(default_factory=list)  # kept, but the seller should confirm


class Product(BaseModel):
    """A saved catalog entry."""

    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    name: str
    keywords: str
    price: str | None = None
    category: str | None = None
    photos: list[str] = Field(default_factory=list)
    listing: Listing
    # What the vision model saw (automatic, can be imperfect).
    visual_notes: str = ""
    # Facts the seller typed in themselves. These are the most trusted source for buyer chat.
    seller_notes: str = ""
    model: str
    vision_model: str = ""
    vision_seconds: float = 0.0
    writing_seconds: float = 0.0
    generation_seconds: float = 0.0  # total
    created_at: str = Field(default_factory=_now)


class ProductUpdate(BaseModel):
    """Fields a seller can edit after the listing is written."""

    price: str | None = Field(default=None, max_length=40)
    seller_notes: str | None = Field(default=None, max_length=800)


# ---------- buyer chat ----------

class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=1200)  # assistant replies can be longer than a buyer's question


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    history: list[ChatTurn] = Field(default_factory=list, max_length=40)
    product_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    # False when the assistant had to hand the question to the seller.
    answered: bool
    product_ids: list[str] = Field(default_factory=list)


class Question(BaseModel):
    """A buyer question the assistant could not answer; the seller sees these."""

    id: str = Field(default_factory=lambda: uuid4().hex[:10])
    question: str
    product_id: str | None = None
    product_name: str | None = None
    count: int = 1  # the same question asked again bumps this instead of adding a row
    created_at: str = Field(default_factory=_now)
    last_asked_at: str = Field(default_factory=_now)
