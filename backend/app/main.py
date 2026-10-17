"""SellMate API. Run with: uvicorn backend.app.main:app --reload

Single-seller local tool: there is no login, so don't expose it to the internet as is.
"""
import base64
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles

from . import config
from .copywriter import PlatformCopy, build_platform_copy
from .handoff import is_price_question, looks_unsure
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

app = FastAPI(title="SellMate", version="0.3.0")
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


@app.post("/api/products/{product_id}/regenerate", response_model=Product)
def regenerate_product(product_id: str):
    """Rewrite the listing using the seller's saved details.

    The photos were already looked at, so in two-stage mode the saved photo notes are
    reused and only the (faster) writing stage runs again.
    """
    product = catalog.get(product_id)
    if product is None:
        raise HTTPException(404, "Product not found.")
    images = []
    for url in product.photos:
        path = config.UPLOAD_DIR / Path(url).name
        if not path.exists():
            raise HTTPException(409, "The original photos are missing, so the listing can't be rewritten.")
        images.append(base64.b64encode(path.read_bytes()).decode("ascii"))
    try:
        result = generate_listing(
            images,
            product.keywords,
            product.price,
            product.category,
            seller_notes=product.seller_notes,
            visual_notes=product.visual_notes or None,
        )
    except LLMError as exc:
        raise HTTPException(502, str(exc)) from exc
    return catalog.update(
        product_id,
        name=result.listing.title,
        listing=result.listing,
        visual_notes=result.visual_notes or product.visual_notes,
        model=config.OLLAMA_MODEL,
        vision_model=config.VISION_MODEL,
        vision_seconds=result.vision_seconds,
        writing_seconds=result.writing_seconds,
        generation_seconds=round(result.vision_seconds + result.writing_seconds, 1),
    )


@app.get("/api/products/{product_id}/copy", response_model=PlatformCopy)
def platform_copy(product_id: str):
    """Ready-to-paste text for WhatsApp, Instagram and Reddit (templates, no model call)."""
    product = catalog.get(product_id)
    if product is None:
        raise HTTPException(404, "Product not found.")
    return build_platform_copy(product)


# ---------- buyer chat ----------

def _hand_off(message: str, product: Product | None) -> None:
    """Keep a question the assistant couldn't answer, for the seller."""
    questions.add_or_bump(
        Question(
            question=message,
            product_id=product.id if product else None,
            product_name=product.listing.title if product else None,
        )
    )


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
            answered=False,
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

    # The one item this question is about, if we can tell.
    target = focus or (context[0] if len(context) == 1 else None)
    ids = [p.id for p in context]

    # Price is a field, not something to ask a 1B model about: instant and always right.
    if target is not None and is_price_question(message):
        if target.price:
            return ChatResponse(
                answer=f"The price of {target.listing.title} is {target.price}.",
                answered=True,
                product_ids=ids,
            )
        _hand_off(message, target)
        return ChatResponse(
            answer="I don't know yet, the seller hasn't set a price. I've passed your question on.",
            answered=False,
            product_ids=ids,
        )

    try:
        answer = answer_question(message, body.history, format_facts(context))
    except LLMError as exc:
        raise HTTPException(502, str(exc)) from exc

    # Decided by what the answer says, not by a flag the model fills in (see handoff.py).
    answered = not looks_unsure(answer)
    if not answered:
        _hand_off(message, target)
    return ChatResponse(answer=answer, answered=answered, product_ids=ids)


@app.get("/api/questions", response_model=list[Question])
def list_questions():
    return list(reversed(questions.all()))  # most recently asked first


@app.delete("/api/questions/{question_id}")
def delete_question(question_id: str) -> dict:
    if not questions.delete(question_id):
        raise HTTPException(404, "Question not found.")
    return {"deleted": question_id}


# Static files last so the /api routes take priority.
app.mount("/uploads", StaticFiles(directory=config.UPLOAD_DIR), name="uploads")
app.mount("/", StaticFiles(directory=config.FRONTEND_DIR, html=True), name="frontend")
