from backend.app.models import Listing, Product
from backend.app.retrieval import format_facts, search, tokenize


def product(title, keywords="", description="", tags=None, notes="", missing=None, price=None):
    return Product(
        name=title,
        keywords=keywords,
        price=price,
        seller_notes=notes,
        listing=Listing(
            title=title,
            description=description or title,
            tags=tags or [],
            missing_info=missing or [],
        ),
        model="gemma3:1b",
    )


def test_tokenize_drops_stopwords_and_plurals():
    assert tokenize("Do you have the Earrings?") == {"earring"}


def test_search_ranks_the_matching_product_first():
    ring = product("Silver ring", keywords="silver handmade")
    bag = product("Linen tote bag", keywords="linen eco")
    assert search([bag, ring], "is the silver ring real?") == [ring]


def test_title_matches_outweigh_description_matches():
    in_title = product("Brass bangle", description="A bangle.")
    in_description = product("Gift item", description="Comes with a brass bangle box.")
    assert search([in_description, in_title], "brass")[0] is in_title


def test_seller_notes_are_searchable():
    ring = product("Plain item", notes="Sterling silver, size 7")
    assert search([ring], "what size is it") == [ring]


def test_no_match_returns_empty_so_the_caller_can_fall_back():
    assert search([product("Silver ring")], "do you deliver to Mumbai?") == []


def test_limit_is_respected():
    items = [product(f"Silver ring {i}", keywords="silver") for i in range(6)]
    assert len(search(items, "silver", limit=3)) == 3


def test_facts_prefer_seller_notes_over_open_questions():
    with_notes = product("Ring", notes="Nickel free.", missing=["Is it nickel free?"], price="₹500")
    text = format_facts([with_notes])
    assert "Details from the seller: Nickel free." in text
    assert "Not known yet" not in text
    assert "Price: ₹500" in text


def test_facts_flag_unknowns_when_the_seller_hasnt_answered():
    text = format_facts([product("Ring", missing=["What size is it?"])])
    assert "Not known yet" in text and "What size is it?" in text
    assert "Price: not set by the seller" in text
