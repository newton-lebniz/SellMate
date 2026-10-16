from backend.app.models import Listing, Product
from backend.app.storage import Catalog


def make_product(name="Ring") -> Product:
    return Product(
        name=name,
        keywords="silver",
        listing=Listing(title=name, description="A ring."),
        model="gemma3:4b",
    )


def test_empty_catalog(tmp_path):
    assert Catalog(tmp_path / "c.json").all() == []


def test_add_and_get(tmp_path):
    cat = Catalog(tmp_path / "c.json")
    p = cat.add(make_product())
    assert cat.get(p.id).name == "Ring"


def test_persists_across_instances(tmp_path):
    path = tmp_path / "c.json"
    p = Catalog(path).add(make_product("Necklace"))
    assert [x.id for x in Catalog(path).all()] == [p.id]


def test_delete_returns_removed_product(tmp_path):
    cat = Catalog(tmp_path / "c.json")
    keep, drop = cat.add(make_product("Keep")), cat.add(make_product("Drop"))
    removed = cat.delete(drop.id)
    assert removed.id == drop.id
    assert [p.id for p in cat.all()] == [keep.id]


def test_delete_missing_returns_none(tmp_path):
    assert Catalog(tmp_path / "c.json").delete("nope") is None


def test_no_temp_files_left_behind(tmp_path):
    cat = Catalog(tmp_path / "c.json")
    cat.add(make_product())
    assert [f.name for f in tmp_path.iterdir()] == ["c.json"]
