"""Tiny JSON-file stores. One seller, one laptop, tens of items: no database needed."""
import json
import os
import tempfile
import threading
from pathlib import Path

from .models import Product, Question


def _atomic_write_json(path: Path, items: list[dict]) -> None:
    # Write to a temp file, then replace: a crash can't leave a half-written file.
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _read_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class Catalog:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> list[Product]:
        return [Product.model_validate(item) for item in _read_json(self.path)]

    def _write(self, products: list[Product]) -> None:
        _atomic_write_json(self.path, [p.model_dump() for p in products])

    def add(self, product: Product) -> Product:
        with self._lock:
            products = self._read()
            products.append(product)
            self._write(products)
        return product

    def all(self) -> list[Product]:
        with self._lock:
            return self._read()

    def get(self, product_id: str) -> Product | None:
        return next((p for p in self.all() if p.id == product_id), None)

    def update(self, product_id: str, **fields) -> Product | None:
        """Change fields on one product and return it (None if it doesn't exist)."""
        with self._lock:
            products = self._read()
            for i, product in enumerate(products):
                if product.id == product_id:
                    products[i] = product.model_copy(update=fields)
                    self._write(products)
                    return products[i]
        return None

    def delete(self, product_id: str) -> Product | None:
        """Remove a product and return it (so the caller can clean up its photos)."""
        with self._lock:
            products = self._read()
            removed = next((p for p in products if p.id == product_id), None)
            if removed is None:
                return None
            self._write([p for p in products if p.id != product_id])
            return removed


class QuestionLog:
    """Buyer questions the assistant couldn't answer, kept for the seller. Capped in size."""

    def __init__(self, path: Path, max_items: int = 100):
        self.path = Path(path)
        self.max_items = max_items
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> list[Question]:
        return [Question.model_validate(item) for item in _read_json(self.path)]

    def add(self, question: Question) -> Question:
        with self._lock:
            items = self._read()
            items.append(question)
            items = items[-self.max_items:]
            _atomic_write_json(self.path, [q.model_dump() for q in items])
        return question

    def all(self) -> list[Question]:
        with self._lock:
            return self._read()

    def delete(self, question_id: str) -> bool:
        with self._lock:
            items = self._read()
            kept = [q for q in items if q.id != question_id]
            if len(kept) == len(items):
                return False
            _atomic_write_json(self.path, [q.model_dump() for q in kept])
            return True
