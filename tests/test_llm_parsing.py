import io

import httpx
import pytest
from PIL import Image

from backend.app.llm import (
    LLMError,
    _has_model,
    _ollama_error,
    parse_chat_json,
    parse_listing_json,
    resize_image,
)

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


def test_resize_handles_webp():
    buf = io.BytesIO()
    Image.new("RGB", (900, 900), "green").save(buf, format="WEBP")
    assert Image.open(io.BytesIO(resize_image(buf.getvalue()))).format == "JPEG"


def test_resize_rejects_non_images():
    with pytest.raises(LLMError):
        resize_image(b"definitely not an image")


# ---------- chat parsing ----------

def test_chat_json_grounded():
    assert parse_chat_json('{"answer": "Yes, it is silver.", "answered_from_catalog": true}') == (
        "Yes, it is silver.",
        True,
    )


def test_chat_json_not_grounded():
    answer, grounded = parse_chat_json('{"answer": "I will ask.", "answered_from_catalog": false}')
    assert answer == "I will ask." and grounded is False


def test_chat_missing_flag_is_treated_as_not_grounded():
    assert parse_chat_json('{"answer": "Maybe."}')[1] is False


def test_chat_string_true_is_not_trusted():
    assert parse_chat_json('{"answer": "Yes.", "answered_from_catalog": "true"}')[1] is False


def test_chat_plain_prose_is_kept_but_not_grounded():
    assert parse_chat_json("It costs 500 rupees.") == ("It costs 500 rupees.", False)


def test_chat_empty_output_raises():
    with pytest.raises(LLMError):
        parse_chat_json("")


# ---------- model matching and error messages ----------

def test_untagged_model_matches_latest():
    assert _has_model(["moondream:latest", "gemma3:1b"], "moondream")


def test_tagged_model_must_match_exactly():
    assert _has_model(["gemma3:1b"], "gemma3:1b")
    assert not _has_model(["gemma3:4b"], "gemma3:1b")
    assert not _has_model(["gemma3:1b"], "")


def _response(status, body):
    return httpx.Response(status, json=body)


def test_multimodal_error_explains_the_fix():
    msg = _ollama_error(
        _response(400, {"error": "Multimodal data provided, but model does not support multimodal requests."}),
        "gemma3:1b",
    )
    assert "VISION_MODEL" in msg and "moondream" in msg


def test_missing_model_error_gives_pull_command():
    assert "ollama pull moondream" in _ollama_error(_response(404, {"error": "model not found"}), "moondream")


def test_unknown_error_shows_ollama_detail():
    assert "boom" in _ollama_error(_response(500, {"error": "boom"}), "gemma3:1b")
