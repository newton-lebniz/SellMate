"""Claim guard: stop the listing from asserting things nobody confirmed.

A photo can show colours and shapes. It cannot show what something is made of or how it
was made. On the first live test, Moondream reported three bracelets that were gold,
silver and white (colours), and Gemma wrote "Silver Bracelet" and tagged it
"silver bracelet", which a buyer reads as the metal, while the seller's own notes said
the material was unconfirmed.

Prompts alone don't stop a 1B model doing that, so this is a deterministic check that
runs on every generated listing. It compares what the listing claims with what the SELLER
supplied (keywords, category, details). Photo notes don't count as confirmation.

  HARD claims (material, technique, quality words): removed if unsupported.
  SOFT claims ("silver", "gold": colour or metal?): kept, but the title and tags say
  "silver-coloured" and the seller is asked.
"""
import re
from dataclasses import dataclass

from .models import Listing


@dataclass(frozen=True)
class Claim:
    name: str  # what we call it when we tell the seller
    pattern: re.Pattern
    ask: str  # the question we put to the seller


def _claim(name: str, pattern: str, ask: str) -> Claim:
    return Claim(name, re.compile(pattern, re.IGNORECASE), ask)


def _material(word: str, pattern: str | None = None) -> Claim:
    return _claim(word, rf"\b{pattern or word}\b", f"Is it really {word}? If yes, add it to your details.")


def _technique(word: str, pattern: str | None = None) -> Claim:
    return _claim(
        f"hand-{word}",
        rf"\bhand[\s-]?{pattern or word}\b",
        f"Is it really hand-{word}? If yes, say how it was made in your details.",
    )


def _quality(name: str, pattern: str) -> Claim:
    return _claim(name, rf"\b({pattern})\b", f"Can you vouch for '{name}'? If yes, add it to your details.")


HARD: list[Claim] = [
    _claim(
        "handmade",
        r"\bhand[\s-]?(made|crafted)\b|\bmade by hand\b|\bcrafted\b|\bartisan(al)?\b",
        "Is it really handmade? If yes, say so in your details.",
    ),
    # One claim per technique: "hand-woven" must not confirm "hand-tied".
    _technique("tied"),
    _technique("woven"),
    _technique("knitted", r"knit(ted)?"),
    _technique("stitched"),
    _technique("beaded"),
    _technique("painted"),
    _technique("poured"),
    _technique("carved"),
    _technique("embroidered"),
    _technique("dyed"),
    # Real and plated are different claims: "gold-plated" must not confirm "real gold".
    _claim(
        "real gold or silver",
        r"\b(real|genuine|pure|solid|sterling|hallmarked)\s+(gold|silver)\b|\b925\b",
        "Is it real gold or silver? Add the exact material to your details.",
    ),
    _claim(
        "plated metal",
        r"\b(gold|silver)[\s-]plated\b",
        "Is it plated? Add the exact material and coating to your details.",
    ),
    # One claim per quality word: "nickel free" must not confirm "hypoallergenic".
    _quality("genuine", r"genuine|authentic"),
    _quality("certified", r"certified|hallmark(ed)?"),
    _quality("hypoallergenic", r"hypoallergenic"),
    _quality("nickel-free", r"nickel[\s-]free"),
    _quality("lead-free", r"lead[\s-]free"),
    _quality("waterproof", r"waterproof|water[\s-]resistant"),
    _quality("sweatproof", r"sweat[\s-]?proof"),
    _quality("tarnish-free", r"tarnish[\s-]free|anti[\s-]tarnish"),
    _quality("organic", r"organic"),
    _material("leather"),
    _material("cotton"),
    _material("silk"),
    _material("wool"),
    _material("linen"),
    _material("wood", r"wood(en)?"),
    _material("bamboo"),
    _material("glass"),
    _material("ceramic"),
    _material("clay"),
    _material("pearl", r"pearls?"),
    _material("diamond", r"diamonds?"),
    _material("steel", r"(stainless\s+)?steel"),
    _material("brass"),
    _material("resin"),
    _material("crystal", r"crystals?"),
    _material("gemstone", r"gem(stone)?s?"),
]

# "silver" and "gold" are also plain colours. A bare "silver bracelet" is read as the metal.
_NOT_A_COLOUR_WORD = r"(?![\s-]*(colou?r(ed|s)?|tone[ds]?|finish))"
SOFT: list[Claim] = [
    _claim(
        word,
        rf"\b{word}\b{_NOT_A_COLOUR_WORD}",
        f"Is '{word}' the real metal, or just the colour? Add the material to your details.",
    )
    for word in ("silver", "gold", "copper", "bronze")
]

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def seller_text(keywords: str, category: str | None, seller_notes: str) -> str:
    """Everything the seller told us. Photo notes are deliberately not included."""
    return " ".join(part for part in (keywords, category or "", seller_notes) if part)


def _listing_text(listing: Listing) -> str:
    return " ".join([listing.title, listing.description, *listing.highlights, *listing.tags])


def _unsupported(claims: list[Claim], listing_text: str, supplied: str) -> list[Claim]:
    return [c for c in claims if c.pattern.search(listing_text) and not c.pattern.search(supplied)]


def _tidy(text: str) -> str:
    text = re.sub(r"\s{2,}", " ", text)
    return re.sub(r"\s+([,.;:])", r"\1", text).strip(" ,;:-")


def _drop_sentences(description: str, claims: list[Claim]) -> str:
    paragraphs = []
    for paragraph in description.split("\n\n"):
        kept = [
            s for s in _SENTENCE_END.split(paragraph.strip())
            if s and not any(c.pattern.search(s) for c in claims)
        ]
        if kept:
            paragraphs.append(" ".join(kept))
    return "\n\n".join(paragraphs)


def _colourise(text: str, claims: list[Claim]) -> str:
    """'Silver Bracelet' -> 'Silver-coloured Bracelet' for claims nobody confirmed."""
    for claim in claims:
        text = claim.pattern.sub(lambda m: f"{m.group(0)}-coloured", text)
    return text


def guard(listing: Listing, supplied: str) -> Listing:
    """Return the listing with unconfirmed claims removed or softened, and the seller asked."""
    text = _listing_text(listing)
    hard = _unsupported(HARD, text, supplied)
    # "silver" inside a colour list ("gold, silver and white") is just a colour. In the title
    # or tags it reads as the material, so only check those places.
    headline = " ".join([listing.title, *listing.tags])
    soft = _unsupported(SOFT, headline, supplied)
    if not hard and not soft:
        return listing

    title, description = listing.title, listing.description
    highlights, tags = list(listing.highlights), list(listing.tags)

    if hard:
        for claim in hard:
            title = claim.pattern.sub("", title)
        title = _tidy(title) or "New item"
        description = _drop_sentences(description, hard) or (
            "See the photos for details. Ask the seller about the material and how it was made."
        )
        highlights = [h for h in highlights if not any(c.pattern.search(h) for c in hard)]
        tags = [t for t in tags if not any(c.pattern.search(t) for c in hard)]

    if soft:
        title = _colourise(title, soft)
        tags = [_colourise(t, soft) for t in tags]

    questions = list(listing.missing_info)
    for claim in [*hard, *soft]:
        if claim.ask not in questions:
            questions.append(claim.ask)

    return listing.model_copy(
        update={
            "title": title[:70],
            "description": description,
            "highlights": highlights,
            "tags": tags,
            "missing_info": questions[:6],
            "removed_claims": [c.name for c in hard],
            "check_claims": [c.name for c in soft],
        }
    )
