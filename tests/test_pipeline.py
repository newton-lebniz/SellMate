"""The two-stage pipeline: the exact flow that failed on a real laptop, tested with a fake Ollama."""
import json

import pytest

from backend.app import config, llm
from backend.app.models import ChatTurn

LISTING = json.dumps(
    {
        "title": "Beaded bracelet",
        "description": "A handmade bracelet.",
        "highlights": ["Handmade"],
        "tags": ["bracelet"],
        "missing_info": ["What is it made of?"],
    }
)


@pytest.fixture
def calls(monkeypatch):
    """Replace the Ollama call with a recorder."""
    recorded = []

    def fake_chat(model, messages, **options):
        recorded.append({"model": model, "messages": messages, **options})
        if model == "moondream":
            return "A beaded bracelet in blue and white."
        return LISTING

    monkeypatch.setattr(llm, "_chat", fake_chat)
    return recorded


def test_two_stage_looks_first_then_writes(calls, monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_MODEL", "gemma3:1b")
    monkeypatch.setattr(config, "VISION_MODEL", "moondream")

    result = llm.generate_listing(["IMG1", "IMG2"], "handmade bracelet", "₹100", "Jewellery")

    vision_calls = [c for c in calls if c["model"] == "moondream"]
    text_calls = [c for c in calls if c["model"] == "gemma3:1b"]
    assert len(vision_calls) == 2  # one call per photo
    assert len(text_calls) == 1
    # The text model never receives images (that was the original crash)...
    assert not any("images" in m for m in text_calls[0]["messages"])
    # ...but does receive what the vision model saw, plus the seller's own words.
    prompt = text_calls[0]["messages"][-1]["content"]
    assert "Photo 1: A beaded bracelet" in prompt and "Photo 2:" in prompt
    assert "handmade bracelet" in prompt and "₹100" in prompt
    assert result.listing.title == "Beaded bracelet"
    assert result.visual_notes.startswith("Photo 1:")


def test_single_model_mode_sends_photos_straight_to_the_text_model(calls, monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_MODEL", "gemma3:4b")
    monkeypatch.setattr(config, "VISION_MODEL", "")

    result = llm.generate_listing(["IMG1"], "bracelet")

    assert len(calls) == 1
    assert calls[0]["model"] == "gemma3:4b"
    assert calls[0]["messages"][-1]["images"] == ["IMG1"]
    assert result.visual_notes == ""


def test_same_model_for_both_roles_is_single_model_mode(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_MODEL", "gemma3:4b")
    monkeypatch.setattr(config, "VISION_MODEL", "gemma3:4b")
    assert llm.two_stage() is False


def test_empty_vision_output_is_an_error(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_MODEL", "gemma3:1b")
    monkeypatch.setattr(config, "VISION_MODEL", "moondream")
    monkeypatch.setattr(llm, "_chat", lambda *a, **k: "   ")
    with pytest.raises(llm.LLMError, match="photo 1"):
        llm.generate_listing(["IMG1"], "bracelet")


def test_seller_details_are_sent_as_confirmed_facts_and_photo_notes_as_looks_only(calls, monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_MODEL", "gemma3:1b")
    monkeypatch.setattr(config, "VISION_MODEL", "moondream")

    llm.generate_listing(["IMG1"], "bracelet", seller_notes="Sterling silver. Ships in 2 days.")

    prompt = [c for c in calls if c["model"] == "gemma3:1b"][0]["messages"][-1]["content"]
    confirmed, photo = prompt.split("PHOTO NOTES")
    assert "Seller's own details: Sterling silver. Ships in 2 days." in confirmed
    assert "SELLER-CONFIRMED FACTS" in confirmed
    assert "Photo 1:" in photo and "Sterling" not in photo


def test_rewrite_reuses_photo_notes_and_skips_the_vision_stage(calls, monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_MODEL", "gemma3:1b")
    monkeypatch.setattr(config, "VISION_MODEL", "moondream")

    result = llm.generate_listing(["IMG1"], "bracelet", visual_notes="Photo 1: earlier notes")

    assert [c["model"] for c in calls] == ["gemma3:1b"]  # moondream was never called
    assert "Photo 1: earlier notes" in calls[0]["messages"][-1]["content"]
    assert result.visual_notes == "Photo 1: earlier notes"
    assert result.vision_seconds < 1


def test_claim_guard_runs_on_every_generated_listing(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_MODEL", "gemma3:1b")
    monkeypatch.setattr(config, "VISION_MODEL", "moondream")
    risky = json.dumps(
        {
            "title": "Genuine Leather Cuff",
            "description": "A wide cuff. Made from genuine leather. Fits most wrists.",
            "highlights": ["Genuine leather"],
            "tags": ["cuff"],
            "missing_info": [],
        }
    )
    monkeypatch.setattr(llm, "_chat", lambda model, *a, **k: "A brown cuff." if model == "moondream" else risky)

    result = llm.generate_listing(["IMG1"], "cuff bracelet")

    assert "leather" not in result.listing.title.lower()
    assert "leather" not in result.listing.description.lower()
    assert result.listing.highlights == []
    assert "Fits most wrists." in result.listing.description  # the honest part survives
    assert "genuine" in result.listing.removed_claims


def test_answer_question_passes_facts_history_and_question(monkeypatch):
    seen = {}

    def fake_chat(model, messages, **options):
        seen["messages"] = messages
        seen["options"] = options
        return "It is blue."

    monkeypatch.setattr(llm, "_chat", fake_chat)
    history = [ChatTurn(role="user", content="hi"), ChatTurn(role="assistant", content="hello")]

    answer = llm.answer_question("What colour?", history, "[p1] Beaded bracelet. Blue.")

    assert answer == "It is blue."
    assert "json_mode" not in seen["options"]  # plain text: no flag for a small model to get wrong
    messages = seen["messages"]
    assert messages[0]["role"] == "system" and "[p1] Beaded bracelet" in messages[0]["content"]
    assert "I don't know yet" in messages[0]["content"]
    assert [m["role"] for m in messages[1:]] == ["user", "assistant", "user"]
    assert messages[-1]["content"] == "What colour?"


def test_history_is_trimmed_to_recent_turns(monkeypatch):
    seen = {}
    monkeypatch.setattr(llm, "_chat", lambda model, messages, **o: seen.update(n=len(messages)) or "ok")
    history = [ChatTurn(role="user", content=str(i)) for i in range(20)]
    llm.answer_question("q", history, "facts")
    assert seen["n"] == 1 + config.MAX_HISTORY_TURNS + 1  # system + recent history + question
