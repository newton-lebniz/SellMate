"""Claim guard. The fixture is the real listing Gemma wrote on the first live test."""
import json
from pathlib import Path

import pytest

from backend.app.claims import guard, seller_text
from backend.app.models import Listing

REAL = json.loads((Path(__file__).parent / "fixtures" / "day2_bracelet.json").read_text())


def real_listing() -> Listing:
    return Listing.model_validate(REAL["listing"])


def supplied(notes: str = "") -> str:
    return seller_text(REAL["keywords"], REAL["category"], notes)


def make(title="Bracelet", description="A bracelet.", tags=None, highlights=None) -> Listing:
    return Listing(title=title, description=description, tags=tags or [], highlights=highlights or [])


# ---------- the real listing ----------

def test_colour_is_not_turned_into_a_metal_in_the_title_or_tags():
    out = guard(real_listing(), supplied())
    assert out.title == "Handcrafted Silver-coloured Bracelet Trio"
    assert "silver-coloured bracelet" in out.tags
    assert "silver bracelet" not in out.tags
    assert out.check_claims == ["silver"]


def test_unsupported_technique_is_cut_but_the_visible_details_stay():
    out = guard(real_listing(), supplied())
    assert "hand-tied" not in out.description.lower()
    assert "gold, silver, and white" in out.description  # a colour list is fine
    assert out.removed_claims == ["hand-tied"]


def test_handmade_survives_because_the_seller_typed_it():
    out = guard(real_listing(), supplied())
    assert "Handcrafted" in out.title
    assert "handmade bracelet" in out.tags
    assert "handmade" not in out.removed_claims


def test_the_seller_is_asked_about_what_was_removed_or_softened():
    out = guard(real_listing(), supplied())
    text = " ".join(out.missing_info)
    assert "hand-tied" in text
    assert "'silver' the real metal" in text
    assert "What is the material of the bracelets?" in out.missing_info  # the model's own question stays


def test_confirming_the_details_brings_the_claims_back():
    out = guard(real_listing(), supplied("Sterling silver, hand-tied with cotton thread."))
    assert out.title == "Handcrafted Silver Bracelet Trio"
    assert out.removed_claims == [] and out.check_claims == []
    assert "hand-tied" in out.description


# ---------- hard claims ----------

@pytest.mark.parametrize(
    "claim_text, supplied_text, kept",
    [
        ("Made from leather.", "wallet", False),
        ("Made from leather.", "leather wallet", True),
        ("Soft cotton fabric.", "cotton scarf", True),
        ("Soft cotton fabric.", "scarf", False),
        ("Sterling silver ring.", "ring", False),
        ("Sterling silver ring.", "sterling silver ring", True),
        ("Hypoallergenic earrings.", "earrings", False),
        ("Hypoallergenic earrings.", "hypoallergenic earrings", True),
        ("Plated in gold.", "ring", True),  # no 'gold-plated' phrase, so not a plating claim
    ],
)
def test_hard_claims_need_seller_support(claim_text, supplied_text, kept):
    out = guard(make(description=f"A ring. {claim_text} Nice."), supplied_text)
    assert (claim_text in out.description) is kept


@pytest.mark.parametrize(
    "claim_text, supplied_text",
    [
        ("Made from genuine leather.", "leather wallet"),  # 'genuine' is a stronger claim than 'leather'
        ("Hypoallergenic earrings.", "nickel free earrings"),  # one quality word doesn't vouch for another
        ("Real gold chain.", "gold plated chain"),  # plated is not real
        ("Beautiful hand-tied knots.", "hand woven mat"),  # one technique doesn't confirm another
        ("Beautiful hand-tied knots.", "handmade mat"),  # 'handmade' doesn't confirm a specific technique
    ],
)
def test_one_confirmed_claim_does_not_vouch_for_a_different_one(claim_text, supplied_text):
    out = guard(make(description=f"A thing. {claim_text} Nice."), supplied_text)
    assert claim_text not in out.description


def test_unrelated_words_are_not_flagged():
    listing = make(description="A pure white background. Glassy finish.", title="Plain band")
    out = guard(listing, "band")
    assert out == listing  # 'pure white' is a colour, 'glassy' is not 'glass'


def test_highlights_and_tags_with_unsupported_claims_are_dropped():
    listing = make(highlights=["Real leather", "Three pieces"], tags=["leather", "gift"])
    out = guard(listing, "wallet")
    assert out.highlights == ["Three pieces"]
    assert out.tags == ["gift"]


def test_title_is_cleaned_when_a_claim_is_removed():
    out = guard(make(title="Genuine Leather Wallet"), "wallet")
    assert out.title == "Wallet"


def test_description_never_ends_up_empty():
    out = guard(make(description="Made of real leather."), "wallet")
    assert "photos" in out.description.lower()


# ---------- soft claims ----------

def test_gold_in_a_colour_list_is_not_flagged():
    out = guard(make(title="Beaded set", description="Colours: gold, silver, white."), "beaded set")
    assert out.check_claims == []


def test_already_coloured_wording_is_left_alone():
    out = guard(make(title="Silver-coloured ring"), "ring")
    assert out.title == "Silver-coloured ring" and out.check_claims == []


def test_seller_confirming_the_metal_clears_the_flag():
    assert guard(make(title="Silver ring"), "silver ring").check_claims == []


def test_clean_listing_is_returned_untouched():
    listing = make(title="Blue ceramic mug".replace("ceramic", "").strip(), description="A blue mug.")
    assert guard(listing, "mug") == listing


def test_seller_text_ignores_photo_notes():
    assert "silver" not in seller_text("bracelets", "jewelry", "").lower()
