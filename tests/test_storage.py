from backend.app.models import Listing, Product, Question
from backend.app.storage import Catalog, QuestionLog


def make_product(name="Ring") -> Product:
    return Product(
        name=name,
        keywords="silver",
        listing=Listing(title=name, description="A ring."),
        model="gemma3:1b",
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


def test_update_changes_only_the_given_fields(tmp_path):
    cat = Catalog(tmp_path / "c.json")
    p = cat.add(make_product())
    updated = cat.update(p.id, seller_notes="Sterling silver")
    assert updated.seller_notes == "Sterling silver"
    assert updated.name == "Ring"
    assert Catalog(tmp_path / "c.json").get(p.id).seller_notes == "Sterling silver"


def test_update_missing_returns_none(tmp_path):
    assert Catalog(tmp_path / "c.json").update("nope", price="1") is None


def test_old_catalog_files_without_new_fields_still_load(tmp_path):
    """Day 1 catalogs have no seller_notes / visual_notes; they must not break."""
    import json

    old = make_product().model_dump()
    for field in ("seller_notes", "visual_notes", "vision_model", "vision_seconds", "writing_seconds"):
        old.pop(field)
    path = tmp_path / "c.json"
    path.write_text(json.dumps([old]))
    loaded = Catalog(path).all()[0]
    assert loaded.seller_notes == "" and loaded.visual_notes == ""


def test_question_log_add_list_delete(tmp_path):
    log = QuestionLog(tmp_path / "q.json")
    q = log.add(Question(question="Is it nickel free?"))
    assert [x.question for x in log.all()] == ["Is it nickel free?"]
    assert log.delete(q.id) is True
    assert log.delete(q.id) is False
    assert log.all() == []


def test_question_log_keeps_only_the_newest(tmp_path):
    log = QuestionLog(tmp_path / "q.json", max_items=3)
    for i in range(5):
        log.add(Question(question=f"q{i}"))
    assert [q.question for q in log.all()] == ["q2", "q3", "q4"]
