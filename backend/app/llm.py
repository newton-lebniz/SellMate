"""Talks to a local Ollama server. No cloud calls anywhere.

Two-stage pipeline, so a small CPU-friendly setup works:
  1. a tiny vision model (Moondream) describes each photo
  2. a text model (Gemma) writes the listing from that description + the seller's words
If VISION_MODEL is empty, photos go straight to the text model instead (that needs a
vision-capable model such as gemma3:4b).
"""
import base64
import io
import json
import re
import time
from dataclasses import dataclass

import httpx
from PIL import Image, ImageOps

from . import config
from .claims import guard, seller_text
from .models import ChatTurn, Listing
from .prompts import (
    SYSTEM_PROMPT,
    VISION_PROMPT,
    build_chat_system_prompt,
    build_listing_prompt,
)


class LLMError(RuntimeError):
    """Raised when the model can't be reached or returns something unusable."""


# ---------- images ----------

def resize_image(raw: bytes) -> bytes:
    """Downscale and re-encode as JPEG.

    Two benefits: CPU inference is much faster on small images, and re-encoding
    drops EXIF metadata (including GPS location) from the seller's photos.
    """
    try:
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img)
    except Exception as exc:
        raise LLMError("That file doesn't look like a valid image.") from exc
    img = img.convert("RGB")
    img.thumbnail((config.MAX_IMAGE_SIDE, config.MAX_IMAGE_SIDE))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def to_b64(jpeg_bytes: bytes) -> str:
    return base64.b64encode(jpeg_bytes).decode("ascii")


# ---------- parsing ----------

def _extract_json(text: str) -> dict | None:
    """Small models sometimes wrap JSON in prose or code fences, so be forgiving."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        match = re.search(r"\{.*\}", text or "", re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _as_list(value) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()]


def parse_listing_json(text: str) -> Listing:
    data = _extract_json(text)
    if data is None:
        raise LLMError("The model didn't return a usable listing. Please try again.")

    title = str(data.get("title", "")).strip()[:70]
    description = str(data.get("description", "")).strip()
    if not title or not description:
        raise LLMError("The listing came back without a title or description.")

    tags = [t.lstrip("#").strip().lower() for t in _as_list(data.get("tags"))]
    return Listing(
        title=title,
        description=description,
        highlights=_as_list(data.get("highlights")),
        tags=[t for t in tags if t],
        missing_info=_as_list(data.get("missing_info")),
    )


def clean_chat_answer(text: str) -> str:
    """The chat model replies in plain text. If a small model wraps it in JSON anyway
    (it sometimes does), pull the answer out instead of showing braces to a buyer."""
    data = _extract_json(text)
    if data is not None:
        for key in ("answer", "reply", "response"):
            if str(data.get(key, "")).strip():
                return str(data[key]).strip()
    plain = (text or "").strip()
    plain = re.sub(r"^(assistant|answer)\s*:\s*", "", plain, flags=re.IGNORECASE)
    if not plain or plain.startswith("{"):
        raise LLMError("The assistant didn't produce an answer. Please try again.")
    return plain


# ---------- Ollama plumbing ----------

def _has_model(installed: list[str], wanted: str) -> bool:
    """'moondream' matches 'moondream:latest'; 'gemma3:1b' must match exactly."""
    if not wanted:
        return False
    for name in installed:
        if name == wanted or (":" not in wanted and name == f"{wanted}:latest"):
            return True
    return False


def two_stage() -> bool:
    return bool(config.VISION_MODEL) and config.VISION_MODEL != config.OLLAMA_MODEL


def ollama_status() -> dict:
    """Is Ollama up, and are the models we need downloaded (and able to see)?"""
    needs_vision = bool(config.VISION_MODEL)
    status = {
        "ollama": False,
        "mode": "two-stage" if two_stage() else "single-model",
        "text_model": config.OLLAMA_MODEL,
        "text_ready": False,
        "vision_model": config.VISION_MODEL or config.OLLAMA_MODEL,
        "vision_ready": False,
    }
    try:
        r = httpx.get(f"{config.OLLAMA_URL}/api/tags", timeout=3)
        r.raise_for_status()
    except httpx.HTTPError:
        return status
    status["ollama"] = True
    installed = [m.get("name", "") for m in r.json().get("models", [])]
    status["text_ready"] = _has_model(installed, config.OLLAMA_MODEL)

    vision_name = config.VISION_MODEL or config.OLLAMA_MODEL
    status["vision_ready"] = _has_model(installed, vision_name)
    if status["vision_ready"] and not needs_vision:
        # Single-model mode: the text model must really accept images.
        status["vision_ready"] = _model_can_see(vision_name)
    return status


def _model_can_see(model: str) -> bool:
    """Newer Ollama versions list capabilities in /api/show. If it's not listed, assume yes."""
    try:
        r = httpx.post(f"{config.OLLAMA_URL}/api/show", json={"model": model}, timeout=5)
        caps = r.json().get("capabilities")
    except (httpx.HTTPError, ValueError):
        return True
    return True if not caps else "vision" in caps


def _ollama_error(response: httpx.Response, model: str) -> str:
    try:
        detail = str(response.json().get("error", ""))
    except ValueError:
        detail = ""
    low = detail.lower()
    if response.status_code == 404 or "not found" in low:
        return f"Model '{model}' not found. Run: ollama pull {model}"
    if "multimodal" in low or "image" in low:
        return (
            f"'{model}' can't read images. Set VISION_MODEL to a vision model "
            "(run `ollama pull moondream`, then restart SellMate)."
        )
    return f"Ollama error {response.status_code}: {detail or 'no details given'}"


def _chat(
    model: str,
    messages: list[dict],
    *,
    json_mode: bool = False,
    num_predict: int = 700,
    temperature: float = 0.4,
) -> str:
    payload = {
        "model": model,
        "stream": False,
        "messages": messages,
        "options": {"temperature": temperature, "num_predict": num_predict},
    }
    if json_mode:
        payload["format"] = "json"
    try:
        r = httpx.post(
            f"{config.OLLAMA_URL}/api/chat", json=payload, timeout=config.OLLAMA_TIMEOUT
        )
    except httpx.ConnectError as exc:
        raise LLMError(
            f"Can't reach Ollama at {config.OLLAMA_URL}. Start it with `ollama serve`."
        ) from exc
    except httpx.TimeoutException as exc:
        raise LLMError(
            "The model took too long. On CPU, try one smaller photo or raise OLLAMA_TIMEOUT."
        ) from exc
    if r.status_code != 200:
        raise LLMError(_ollama_error(r, model))
    return r.json().get("message", {}).get("content", "") or ""


# ---------- listing generation ----------

@dataclass
class Generation:
    listing: Listing
    visual_notes: str
    vision_seconds: float
    writing_seconds: float


def describe_photos(images_b64: list[str]) -> str:
    """Stage 1: one call per photo (small vision models handle one image at a time)."""
    notes = []
    for i, image in enumerate(images_b64, start=1):
        text = _chat(
            config.VISION_MODEL,
            [{"role": "user", "content": VISION_PROMPT, "images": [image]}],
            num_predict=160,
            temperature=0.2,
        ).strip()
        if not text:
            raise LLMError(f"The vision model returned nothing for photo {i}.")
        notes.append(f"Photo {i}: {text}")
    return "\n".join(notes)


def generate_listing(
    images_b64: list[str],
    keywords: str,
    price: str | None = None,
    category: str | None = None,
    seller_notes: str = "",
    visual_notes: str | None = None,
) -> Generation:
    """Write a listing. Pass visual_notes to reuse an earlier look at the photos (a rewrite
    after the seller added details then skips the slow vision stage)."""
    started = time.perf_counter()
    notes = ""
    if two_stage():
        notes = visual_notes or describe_photos(images_b64)
        user = {
            "role": "user",
            "content": build_listing_prompt(keywords, price, category, notes, seller_notes),
        }
    else:
        user = {
            "role": "user",
            "content": build_listing_prompt(keywords, price, category, None, seller_notes),
            "images": images_b64,
        }
    vision_done = time.perf_counter()

    text = _chat(
        config.OLLAMA_MODEL,
        [{"role": "system", "content": SYSTEM_PROMPT}, user],
        json_mode=True,
        num_predict=700,
    )
    # Deterministic check: nothing the seller didn't confirm survives as a fact.
    listing = guard(parse_listing_json(text), seller_text(keywords, category, seller_notes))
    finished = time.perf_counter()
    return Generation(
        listing=listing,
        visual_notes=notes,
        vision_seconds=round(vision_done - started, 1),
        writing_seconds=round(finished - vision_done, 1),
    )


# ---------- buyer chat ----------

def answer_question(question: str, history: list[ChatTurn], facts: str) -> str:
    """Answer a buyer's question from the given catalog facts (plain text)."""
    messages = [{"role": "system", "content": build_chat_system_prompt(facts)}]
    for turn in history[-config.MAX_HISTORY_TURNS:]:
        messages.append({"role": turn.role, "content": turn.content})
    messages.append({"role": "user", "content": question})
    text = _chat(config.OLLAMA_MODEL, messages, num_predict=200, temperature=0.2)
    if config.DEBUG:
        print(f"[sellmate debug] question={question!r}\n[sellmate debug] raw reply={text!r}")
    return clean_chat_answer(text)
