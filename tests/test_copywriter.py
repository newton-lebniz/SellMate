from backend.app.copywriter import build_platform_copy
from backend.app.models import Listing, Product


def product(**overrides) -> Product:
    base = dict(
        name="Beaded bracelet",
        keywords="handmade bracelet",
        price="₹799",
        category="Jewellery",
        seller_notes="Ships in 2 days.",
        listing=Listing(
            title="Beaded bracelet",
            description="Three stacking bracelets.",
            highlights=["Set of three", "Stretch fit"],
            tags=["bracelet", "beaded jewelry", "gift!"],
        ),
        model="gemma3:1b",
    )
    base.update(overrides)
    return Product(**base)


def test_whatsapp_copy_has_bold_title_price_and_details():
    text = build_platform_copy(product()).whatsapp
    assert text.startswith("*Beaded bracelet*")
    assert "• Set of three" in text
    assert "Price: ₹799" in text and "Ships in 2 days." in text


def test_instagram_copy_ends_with_clean_hashtags():
    text = build_platform_copy(product()).instagram
    last_line = text.splitlines()[-1]
    assert last_line == "#bracelet #beadedjewelry #gift #jewellery"
    assert "DM to order." in text


def test_reddit_copy_uses_markdown_and_has_no_hashtags():
    copy = build_platform_copy(product())
    assert copy.reddit_title == "Beaded bracelet"
    assert "- Set of three" in copy.reddit_body
    assert "#" not in copy.reddit_body
    assert any("rules" in r for r in copy.reminders)


def test_price_and_details_are_left_out_when_missing():
    copy = build_platform_copy(product(price=None, seller_notes=""))
    assert "Price" not in copy.whatsapp and "Ships" not in copy.whatsapp
    assert "Price" not in copy.instagram


def test_reddit_title_is_capped_at_300_characters():
    long = product(listing=Listing(title="x" * 70, description="d"))
    assert len(build_platform_copy(long).reddit_title) <= 300


def test_hashtags_are_deduplicated_and_limited_to_eight():
    tags = [f"tag{i}" for i in range(12)] + ["tag1"]
    out = build_platform_copy(product(listing=Listing(title="t", description="d", tags=tags))).instagram
    hashtags = out.splitlines()[-1].split()
    assert len(hashtags) == 8 and len(set(hashtags)) == 8
