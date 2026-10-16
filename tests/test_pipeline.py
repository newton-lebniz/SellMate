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


def test_answer_question_passes_facts_history_and_question(monkeypatch):
    seen = {}

    def fake_chat(model, messages, **options):
        seen["messages"] = messages
        return '{"answer": "It is blue.", "answered_from_catalog": true}'

    monkeypatch.setattr(llm, "_chat", fake_chat)
    history = [ChatTurn(role="user", content="hi"), ChatTurn(role="assistant", content="hello")]

    answer, grounded = llm.answer_question("What colour?", history, "[p1] Beaded bracelet. Blue.")

    assert (answer, grounded) == ("It is blue.", True)
    messages = seen["messages"]
    assert messages[0]["role"] == "system" and "[p1] Beaded bracelet" in messages[0]["content"]
    assert [m["role"] for m in messages[1:]] == ["user", "assistant", "user"]
    assert messages[-1]["content"] == "What colour?"


def test_history_is_trimmed_to_recent_turns(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        llm,
        "_chat",
        lambda model, messages, **o: seen.update(n=len(messages)) or '{"answer": "ok", "answered_from_catalog": true}',
    )
    history = [ChatTurn(role="user", content=str(i)) for i in range(20)]
    llm.answer_question("q", history, "facts")
    assert seen["n"] == 1 + config.MAX_HISTORY_TURNS + 1  # system + recent history + question
