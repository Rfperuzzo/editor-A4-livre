import json

import pytest

from editor.project.models import Document, ItemModel
from editor.project.serializer import load_project, parse_document, save_project


def test_save_reopen_all_properties(tmp_path):
    child = ItemModel(kind="text", x=15.125, y=-10.6, width=70.12, height=19.76,
                      rotation=270, text="Ação\nTeste", bold=True, italic=True, underline=True,
                      font_size=18.5, alignment="right", locked=True, opacity=.4,
                      fill="#00ffffff", stroke_width=.27)
    doc = Document(orientation="landscape", grid=True, snap=True,
                   items=[ItemModel(kind="group", children=[child])])
    path = tmp_path / "teste.a4livre"
    save_project(doc, path)
    assert load_project(path) == doc


@pytest.mark.parametrize("change", [
    lambda d: d.update(version=99),
    lambda d: d.update(version=True),
    lambda d: d.update(orientation="other"),
    lambda d: d.update(grid="yes"),
    lambda d: d["items"][0].update(width=-1),
    lambda d: d["items"][0].update(x=float("nan")),
    lambda d: d["items"][0].update(rotation=float("inf")),
    lambda d: d["items"][0].update(kind="python"),
    lambda d: d["items"][0].update(fill="invalid"),
    lambda d: d["items"][0].update(locked="false"),
    lambda d: d["items"][0].update(kind="image", image="broken"),
    lambda d: d["items"].append(d["items"][0].copy()),
])
def test_reject_invalid_document(change):
    data = Document(items=[ItemModel()]).to_dict()
    change(data)
    with pytest.raises(ValueError): parse_document(data)


def test_atomic_write_failure_preserves_original(tmp_path, monkeypatch):
    path = tmp_path / "projeto.a4livre"
    original = Document()
    save_project(original, path)

    def fail(*args): raise OSError("Falha de gravação simulada")
    monkeypatch.setattr("editor.project.serializer.os.replace", fail)
    with pytest.raises(OSError): save_project(Document(items=[ItemModel()]), path)
    assert load_project(path) == original
    assert list(tmp_path.iterdir()) == [path]


def test_invalid_file_has_clear_error(tmp_path):
    path = tmp_path / "bad.a4livre"
    path.write_text("{invalid", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON válido"): load_project(path)
