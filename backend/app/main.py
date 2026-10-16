"""SellMate API. Run with: uvicorn backend.app.main:app --reload

Single-seller local tool: there is no login, so don't expose it to the internet as is.
"""
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles

from . import config
from .llm import (
    LLMError,
    answer_question,
    generate_listing,
    ollama_status,
    resize_image,
    to_b64,
)
from .models import ChatRequest, ChatResponse, Product, ProductUpdate, Question
from .retrieval import format_facts, search
from .storage import Catalog, QuestionLog

config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="SellMate", version="0.2.0")
catalog = Catalog(config.CATALOG_FILE)
questions = QuestionLog(config.QUESTIONS_FILE, config.MAX_LOGGED_QUESTIONS)


@app.get("/api/health")
def health() -> dict:
    return {"app": "sellmate", **ollama_status()}


# ---------- products ----------

@app.get("/api/products", response_model=list[Product])
def list_products():
    return list(reversed(catalog.all()))  # newest first


@app.get("/api/products/{product_id}", response_model=Product)
def get_product(product_id: str):
    product = catalog.get(product_id)
    if product is None:
        raise HTTPException(404, "Product not found.")
    return product


@app.patch("/api/products/{product_id}", response_model=Product)
def update_product(product_id: str, body: ProductUpdate):
    """Let the seller add the facts the photos couldn't show (and fix the price)."""
    changes = {}
    if "price" in body.model_fields_set:
        changes["price"] = (body.price or "").strip() or None
    if "seller_notes" in body.model_fields_set:
        changes["seller_notes"] = (body.seller_notes or "").strip()
    if not changes:
        raise HTTPException(422, "Nothing to update.")
    updated = catalog.update(product_id, **changes)
    if updated is None:
        raise HTTPException(404, "Product not found.")
    return updated


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

    try:
        result = generate_listing([to_b64(j) for j in jpegs], keywords, price, category)
    except LLMError as exc:
        raise HTTPException(502, str(exc)) from exc

    # Only save photos once generation succeeded, so failures leave no orphans.
    photo_urls = []
    for jpeg in jpegs:
        name = f"{uuid4().hex}.jpg"
        (config.UPLOAD_DIR / name).write_bytes(jpeg)
        photo_urls.append(f"/uploads/{name}")

    product = Product(
        name=result.listing.title,
        keywords=keywords,
        price=price,
        category=category,
        photos=photo_urls,
        listing=result.listing,
        visual_notes=result.visual_notes,
        model=config.OLLAMA_MODEL,
        vision_model=config.VISION_MODEL,
        vision_seconds=result.vision_seconds,
        writing_seconds=result.writing_seconds,
        generation_seconds=round(result.vision_seconds + result.writing_seconds, 1),
    )
    return catalog.add(product)


# ---------- buyer chat ----------

@app.post("/api/chat", response_model=ChatResponse)
def chat(body: ChatRequest):
    """Answer a buyer's question using only the seller's catalog."""
    message = body.message.strip()
    if not message:
        raise HTTPException(422, "Type a question first.")

    products = catalog.all()
    if not products:
        return ChatResponse(
            answer="This shop doesn't have any items yet. Please check back soon!",
            grounded=False,
        )

    focus = None
    if body.product_id:
        focus = next((p for p in products if p.id == body.product_id), None)
        if focus is None:
            raise HTTPException(404, "Product not found.")
        context = [focus]
    else:
        context = search(list(reversed(products)), message, config.MAX_CONTEXT_PRODUCTS)
        if not context:
            # Nothing matched (e.g. "what do you sell?"): show the newest few as an overview.
            context = list(reversed(products))[: config.MAX_CONTEXT_PRODUCTS]

    try:
        answer, grounded = answer_question(message, body.history, format_facts(context))
    except LLMError as exc:
        raise HTTPException(502, str(exc)) from exc

    if not grounded:
        # The assistant had to say "I don't know": keep the question for the seller.
        about = focus or (context[0] if len(context) == 1 else None)
        questions.add(
            Question(
                question=message,
                product_id=about.id if about else None,
                product_name=about.listing.title if about else None,
            )
        )
    return ChatResponse(answer=answer, grounded=grounded, product_ids=[p.id for p in context])


@app.get("/api/questions", response_model=list[Question])
def list_questions():
    return list(reversed(questions.all()))  # newest first


@app.delete("/api/questions/{question_id}")
def delete_question(question_id: str) -> dict:
    if not questions.delete(question_id):
        raise HTTPException(404, "Question not found.")
    return {"deleted": question_id}


# Static files last so the /api routes take priority.
app.mount("/uploads", StaticFiles(directory=config.UPLOAD_DIR), name="uploads")
app.mount("/", StaticFiles(directory=config.FRONTEND_DIR, html=True), name="frontend")
