"""API tests. The model call is stubbed, so Ollama is not needed."""
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app import config, main
from backend.app.llm import LLMError
from backend.app.models import Listing
from backend.app.storage import Catalog


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(main, "catalog", Catalog(tmp_path / "catalog.json"))
    monkeypatch.setattr(
        main,
        "generate_listing",
        lambda *a, **k: Listing(title="Test ring", description="A nice ring.", missing_info=["Size?"]),
    )
    return TestClient(main.app)


def png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (50, 50), "blue").save(buf, format="PNG")
    return buf.getvalue()


def post(client, **overrides):
    files = overrides.pop("files", [("photos", ("a.png", png_bytes(), "image/png"))])
    data = {"keywords": "silver ring", **overrides}
    return client.post("/api/products", files=files, data=data)


def test_create_list_delete_roundtrip(client):
    res = post(client, price="₹500")
    assert res.status_code == 200
    product = res.json()
    assert product["name"] == "Test ring"
    assert product["price"] == "₹500"
    assert product["listing"]["missing_info"] == ["Size?"]

    assert len(client.get("/api/products").json()) == 1
    assert client.delete(f"/api/products/{product['id']}").status_code == 200
    assert client.get("/api/products").json() == []


def test_rejects_non_image(client):
    res = post(client, files=[("photos", ("a.txt", b"hello", "text/plain"))])
    assert res.status_code == 422


def test_rejects_too_many_photos(client):
    files = [("photos", (f"{i}.png", png_bytes(), "image/png")) for i in range(4)]
    assert post(client, files=files).status_code == 422


def test_rejects_blank_keywords(client):
    assert post(client, keywords="   ").status_code == 422


def test_model_failure_returns_502_and_saves_nothing(client, monkeypatch):
    def boom(*a, **k):
        raise LLMError("Can't reach Ollama.")

    monkeypatch.setattr(main, "generate_listing", boom)
    res = post(client)
    assert res.status_code == 502
    assert "Ollama" in res.json()["detail"]
    assert client.get("/api/products").json() == []


def test_unknown_product_404(client):
    assert client.get("/api/products/nope").status_code == 404
