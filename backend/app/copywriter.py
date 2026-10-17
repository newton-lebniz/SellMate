"""Turn a saved listing into ready-to-paste posts for WhatsApp, Instagram and Reddit.

Deliberately NOT done by the model: the listing was already written (and claim-checked)
once. Re-asking a 1B model to rewrite it three times would cost minutes of CPU time and
give it three more chances to invent something. These are plain templates.
"""
import re

from pydantic import BaseModel, Field

from .models import Product

REDDIT_REMINDERS = [
    "Every subreddit has its own rules about selling and self-promotion. Read the sidebar "
    "and ask a moderator if you're unsure.",
    "Don't post your phone number or address in a public post. Use Reddit chat or comments.",
]


class PlatformCopy(BaseModel):
    whatsapp: str
    instagram: str
    reddit_title: str
    reddit_body: str
    reminders: list[str] = Field(default_factory=list)


def _hashtag(tag: str) -> str:
    cleaned = re.sub(r"[^0-9a-z]+", "", tag.lower())
    return f"#{cleaned}" if cleaned else ""


def _hashtags(product: Product, limit: int = 8) -> list[str]:
    seen: list[str] = []
    for tag in [*product.listing.tags, product.category or ""]:
        h = _hashtag(tag)
        if h and h not in seen:
            seen.append(h)
    return seen[:limit]


def _body(product: Product) -> list[str]:
    """Description, highlights and the seller's own details, as plain lines."""
    return [product.listing.description.strip()]


def build_platform_copy(product: Product) -> PlatformCopy:
    listing = product.listing
    details = product.seller_notes.strip()
    price = f"Price: {product.price}" if product.price else ""

    # WhatsApp: *bold* title, short lines, easy to read on a phone.
    wa = [f"*{listing.title}*", "", *_body(product)]
    if listing.highlights:
        wa += ["", *[f"• {h}" for h in listing.highlights]]
    if details:
        wa += ["", details]
    if price:
        wa += ["", price]
    wa += ["", "Message me to order."]

    # Instagram: caption first, hashtags after a gap. (Instagram allows up to 30.)
    ig = [listing.title, "", *_body(product)]
    if details:
        ig += ["", details]
    if price:
        ig += ["", price]
    ig += ["", "DM to order."]
    tags = _hashtags(product)
    if tags:
        ig += ["", " ".join(tags)]

    # Reddit: markdown body, no hashtags.
    rb = [*_body(product)]
    if listing.highlights:
        rb += ["", *[f"- {h}" for h in listing.highlights]]
    if details:
        rb += ["", details]
    if price:
        rb += ["", f"**{price}**"]
    rb += ["", "Happy to answer questions in the comments."]

    return PlatformCopy(
        whatsapp="\n".join(wa).strip(),
        instagram="\n".join(ig).strip(),
        reddit_title=listing.title[:300],
        reddit_body="\n".join(rb).strip(),
        reminders=REDDIT_REMINDERS,
    )
