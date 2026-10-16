"""A tiny JSON-file catalog. One seller, one laptop, tens of items: no database needed."""
import json
import os
import tempfile
import threading
from pathlib import Path

from .models import Product


class Catalog:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> list[Product]:
        if not self.path.exists():
            return []
        with open(self.path, encoding="utf-8") as f:
            return [Product.model_validate(item) for item in json.load(f)]

    def _write(self, products: list[Product]) -> None:
        # Write to a temp file, then replace: a crash can't leave a half-written catalog.
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump([p.model_dump() for p in products], f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

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

    def delete(self, product_id: str) -> Product | None:
        """Remove a product and return it (so the caller can clean up its photos)."""
        with self._lock:
            products = self._read()
            removed = next((p for p in products if p.id == product_id), None)
            if removed is None:
                return None
            self._write([p for p in products if p.id != product_id])
            return removed
