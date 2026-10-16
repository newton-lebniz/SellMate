import io

import pytest
from PIL import Image

from backend.app.llm import LLMError, parse_listing_json, resize_image

GOOD = (
    '{"title": "Oxidised silver jhumkas", "description": "Handmade earrings.", '
    '"highlights": ["Handmade", "Lightweight"], "tags": ["#Silver", "jhumka"], '
    '"missing_info": ["What is the earring length?"]}'
)


def test_parses_clean_json():
    listing = parse_listing_json(GOOD)
    assert listing.title == "Oxidised silver jhumkas"
    assert listing.missing_info == ["What is the earring length?"]


def test_normalises_tags():
    assert parse_listing_json(GOOD).tags == ["silver", "jhumka"]


def test_extracts_json_from_code_fence():
    listing = parse_listing_json(f"Sure! Here you go:\n```json\n{GOOD}\n```")
    assert listing.title.startswith("Oxidised")


def test_title_is_capped_at_70_chars():
    text = GOOD.replace("Oxidised silver jhumkas", "x" * 200)
    assert len(parse_listing_json(text).title) == 70


def test_single_string_becomes_list():
    text = GOOD.replace('["What is the earring length?"]', '"What is the earring length?"')
    assert parse_listing_json(text).missing_info == ["What is the earring length?"]


@pytest.mark.parametrize("bad", ["", "not json at all", "[1, 2]", '{"title": "", "description": ""}'])
def test_rejects_unusable_output(bad):
    with pytest.raises(LLMError):
        parse_listing_json(bad)


def test_resize_shrinks_and_outputs_jpeg():
    img = Image.new("RGB", (2000, 1000), "red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    out = Image.open(io.BytesIO(resize_image(buf.getvalue())))
    assert out.format == "JPEG"
    assert max(out.size) <= 640


def test_resize_rejects_non_images():
    with pytest.raises(LLMError):
        resize_image(b"definitely not an image")
