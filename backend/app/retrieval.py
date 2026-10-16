"""Pick which catalog items to show the model for a buyer question.

A 1B model on a CPU has a small context window and a short attention span, so we
never hand it the whole catalog: only the few products that match the question.
Plain keyword overlap is enough for a seller's catalog of tens of items and needs
no embedding model (which would be another download on a CPU-only laptop).
"""
import re

from .models import Product

STOPWORDS = frozenset(
    """a an the is are was were be do does did can could will would you your yours i me my
    we us it its this that these those of in on at for to from with without and or but if
    any some what which who how many much have has had there here about please tell hi
    hello hey thanks thank also just really very""".split()
)


def tokenize(text: str) -> set[str]:
    """Lowercase words with a crude plural strip, so 'earrings' matches 'earring'."""
    tokens = set()
    for word in re.findall(r"[a-z0-9]+", (text or "").lower()):
        if word in STOPWORDS or len(word) < 2:
            continue
        if len(word) > 3 and word.endswith("s"):
            word = word[:-1]
        tokens.add(word)
    return tokens


def _strong_tokens(p: Product) -> set[str]:
    parts = [p.name, p.listing.title, p.keywords, p.category or "", " ".join(p.listing.tags)]
    return tokenize(" ".join(parts))


def _weak_tokens(p: Product) -> set[str]:
    parts = [p.listing.description, " ".join(p.listing.highlights), p.seller_notes, p.visual_notes]
    return tokenize(" ".join(parts))


def score(product: Product, question_tokens: set[str]) -> int:
    """Title, tags, keywords and category count triple; everything else counts once."""
    return 3 * len(question_tokens & _strong_tokens(product)) + len(
        question_tokens & _weak_tokens(product)
    )


def search(products: list[Product], question: str, limit: int = 3) -> list[Product]:
    tokens = tokenize(question)
    ranked = sorted(
        ((score(p, tokens), i, p) for i, p in enumerate(products)),
        key=lambda t: (-t[0], t[1]),
    )
    return [p for s, _, p in ranked if s > 0][:limit]


def format_facts(products: list[Product]) -> str:
    """Render products as plain text for the prompt."""
    blocks = []
    for p in products:
        lines = [f"[{p.id}] {p.listing.title}"]
        lines.append(f"Price: {p.price or 'not set by the seller'}")
        if p.category:
            lines.append(f"Category: {p.category}")
        lines.append(f"Description: {p.listing.description}")
        if p.listing.highlights:
            lines.append("Highlights: " + "; ".join(p.listing.highlights))
        lines.append(f"Seller's keywords: {p.keywords}")
        if p.seller_notes:
            lines.append(f"Details from the seller: {p.seller_notes}")
        elif p.listing.missing_info:
            lines.append(
                "Not known yet (tell the buyer you'll ask the seller): "
                + "; ".join(p.listing.missing_info)
            )
        if p.visual_notes:
            lines.append(f"What the photo shows (automatic): {p.visual_notes}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)
