"""Talks to a local Ollama server. No cloud calls anywhere."""
import base64
import io
import json
import re

import httpx
from PIL import Image, ImageOps

from . import config
from .models import Listing
from .prompts import SYSTEM_PROMPT, build_listing_prompt


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

def parse_listing_json(text: str) -> Listing:
    """Small models sometimes wrap JSON in prose or code fences, so be forgiving."""
    data = None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        match = re.search(r"\{.*\}", text or "", re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                data = None
    if not isinstance(data, dict):
        raise LLMError("The model didn't return a usable listing. Please try again.")

    def as_list(value) -> list[str]:
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            return []
        return [str(v).strip() for v in value if str(v).strip()]

    title = str(data.get("title", "")).strip()[:70]
    description = str(data.get("description", "")).strip()
    if not title or not description:
        raise LLMError("The listing came back without a title or description.")

    tags = [t.lstrip("#").strip().lower() for t in as_list(data.get("tags"))]
    return Listing(
        title=title,
        description=description,
        highlights=as_list(data.get("highlights")),
        tags=[t for t in tags if t],
        missing_info=as_list(data.get("missing_info")),
    )


# ---------- Ollama ----------

def ollama_status() -> dict:
    """Is Ollama up, and is the configured model downloaded?"""
    status = {"ollama": False, "model": config.OLLAMA_MODEL, "model_ready": False}
    try:
        r = httpx.get(f"{config.OLLAMA_URL}/api/tags", timeout=3)
        r.raise_for_status()
    except httpx.HTTPError:
        return status
    status["ollama"] = True
    names = [m.get("name", "") for m in r.json().get("models", [])]
    wanted = config.OLLAMA_MODEL
    status["model_ready"] = any(n == wanted or n.split(":")[0] == wanted for n in names)
    return status


def generate_listing(
    images_b64: list[str],
    keywords: str,
    price: str | None = None,
    category: str | None = None,
) -> Listing:
    payload = {
        "model": config.OLLAMA_MODEL,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.4, "num_predict": 700},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_listing_prompt(keywords, price, category),
                "images": images_b64,
            },
        ],
    }
    try:
        r = httpx.post(
            f"{config.OLLAMA_URL}/api/chat", json=payload, timeout=config.OLLAMA_TIMEOUT
        )
    except httpx.ConnectError as exc:
        raise LLMError(
            "Can't reach Ollama. Start it with `ollama serve` and try again."
        ) from exc
    except httpx.TimeoutException as exc:
        raise LLMError(
            "The model took too long. On CPU, try one smaller photo or raise OLLAMA_TIMEOUT."
        ) from exc

    if r.status_code == 404:
        raise LLMError(f"Model not found. Run: ollama pull {config.OLLAMA_MODEL}")
    if r.status_code >= 400:
        raise LLMError(f"Ollama returned an error ({r.status_code}).")

    content = r.json().get("message", {}).get("content", "")
    return parse_listing_json(content)
