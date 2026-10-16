"""SellMate API. Run with: uvicorn backend.app.main:app --reload"""
import time
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles

from . import config
from .llm import LLMError, generate_listing, ollama_status, resize_image, to_b64
from .models import Product
from .storage import Catalog

config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="SellMate", version="0.1.0")
catalog = Catalog(config.CATALOG_FILE)


@app.get("/api/health")
def health() -> dict:
    return {"app": "sellmate", **ollama_status()}


@app.get("/api/products", response_model=list[Product])
def list_products():
    return list(reversed(catalog.all()))  # newest first


@app.get("/api/products/{product_id}", response_model=Product)
def get_product(product_id: str):
    product = catalog.get(product_id)
    if product is None:
        raise HTTPException(404, "Product not found.")
    return product


@app.delete("/api/products/{product_id}")
def delete_product(product_id: str) -> dict:
    removed = catalog.delete(product_id)
    if removed is None:
        raise HTTPException(404, "Product not found.")
    for url in removed.photos:
        (config.UPLOAD_DIR / Path(url).name).unlink(missing_ok=True)
    return {"deleted": product_id}


# Plain `def` (not async): FastAPI runs it in a worker thread, so the slow
# CPU inference call doesn't block other requests.
@app.post("/api/products", response_model=Product)
def create_product(
    photos: list[UploadFile] = File(...),
    keywords: str = Form(...),
    price: str | None = Form(None),
    category: str | None = Form(None),
):
    keywords = keywords.strip()
    price = (price or "").strip() or None
    category = (category or "").strip() or None

    if not keywords:
        raise HTTPException(422, "Add a few keywords so the model knows what it's looking at.")
    if len(keywords) > config.MAX_KEYWORDS_CHARS:
        raise HTTPException(422, f"Keep keywords under {config.MAX_KEYWORDS_CHARS} characters.")
    if not 1 <= len(photos) <= config.MAX_PHOTOS:
        raise HTTPException(422, f"Upload between 1 and {config.MAX_PHOTOS} photos.")

    limit = config.MAX_UPLOAD_MB * 1024 * 1024
    jpegs: list[bytes] = []
    for photo in photos:
        if not (photo.content_type or "").startswith("image/"):
            raise HTTPException(422, f"'{photo.filename}' is not an image.")
        raw = photo.file.read(limit + 1)
        if len(raw) > limit:
            raise HTTPException(413, f"'{photo.filename}' is larger than {config.MAX_UPLOAD_MB} MB.")
        try:
            jpegs.append(resize_image(raw))
        except LLMError as exc:
            raise HTTPException(422, str(exc)) from exc

    started = time.perf_counter()
    try:
        listing = generate_listing([to_b64(j) for j in jpegs], keywords, price, category)
    except LLMError as exc:
        raise HTTPException(502, str(exc)) from exc
    elapsed = round(time.perf_counter() - started, 1)

    # Only save photos once generation succeeded, so failures leave no orphans.
    photo_urls = []
    for jpeg in jpegs:
        name = f"{uuid4().hex}.jpg"
        (config.UPLOAD_DIR / name).write_bytes(jpeg)
        photo_urls.append(f"/uploads/{name}")

    product = Product(
        name=listing.title,
        keywords=keywords,
        price=price,
        category=category,
        photos=photo_urls,
        listing=listing,
        model=config.OLLAMA_MODEL,
        generation_seconds=elapsed,
    )
    return catalog.add(product)


# Static files last so the /api routes take priority.
app.mount("/uploads", StaticFiles(directory=config.UPLOAD_DIR), name="uploads")
app.mount("/", StaticFiles(directory=config.FRONTEND_DIR, html=True), name="frontend")
