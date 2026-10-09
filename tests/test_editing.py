import base64
from copy import deepcopy

import pytest
from PySide6.QtCore import QBuffer, QIODevice, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QTextCursor
from PySide6.QtWidgets import QApplication

from editor.geometry import local_to_page
from editor.project.models import ItemModel
from editor.project.serializer import load_project, save_project


def test_text_edit_duplicate_and_history(editor, qtbot):
    c, scene, view = editor
    m = ItemModel(kind="text", text="", fill="#00000000", stroke_width=0)
    c.add(m)
    graphic = scene.graphics[m.id]
    graphic.begin_text()
    graphic.text_editor.textCursor().insertText("Olá, mundo!\nSegunda linha")
    assert m.text == "Olá, mundo!\nSegunda linha"
    c.finish_text()
    assert c.stack.count() == 2
    c.set_property("bold", True)
    c.set_property("rotation", 90)
    c.set_property("width", 80)
    assert c.document.items[0].font_size == 12
    c.duplicate()
    original, copy = c.document.items
    assert copy.id != original.id and copy.text == original.text
    assert copy.x == original.x + 5 and copy.bold and copy.rotation == 90
    c.stack.undo()
    assert len(c.document.items) == 1
    c.stack.redo()
    assert len(c.document.items) == 2


def test_copy_paste_has_new_ids_and_preserves_style(editor):
    c, scene, _ = editor
    m = ItemModel(kind="ellipse", fill="#ff00aabb", opacity=.5)
    c.add(m)
    assert c.copy()
    c.paste()
    assert len(c.document.items) == 2
    clone = c.document.items[1]
    assert clone.id != m.id and clone.fill == m.fill and clone.opacity == .5
    c.delete()
    assert len(c.document.items) == 1
    c.stack.undo()
    assert len(c.document.items) == 2


def test_group_ungroup_world_coordinates(editor):
    c, scene, _ = editor
    a = ItemModel(x=30, y=40, rotation=45)
    b = ItemModel(kind="text", x=80, y=55, rotation=90)
    c.add(a)
    c.add(b)
    for item in scene.graphics.values(): item.setSelected(True)
    before = c.snapshot()
    c.group()
    assert len(c.document.items) == 1 and c.document.items[0].kind == "group"
    c.ungroup()
    assert c.document == before
    c.stack.undo()
    c.set_property("rotation", 90)
    c.set_property("width", c.document.items[0].width * 2)
    group = c.document.items[0]
    expected = [local_to_page(group, child.x, child.y) for child in group.children]
    sizes = [(m.width, m.height, m.font_size, m.rotation+90) for m in group.children]
    c.ungroup()
    for m, pos, size in zip(c.document.items, expected, sizes):
        assert (m.x, m.y) == pytest.approx(pos)
        assert (m.width, m.height, m.font_size, m.rotation) == pytest.approx(size)


def test_alignment_distribution_lock_and_layers(editor):
    c, scene, _ = editor
    for x in (10, 60, 140): c.add(ItemModel(x=x, y=x/2, width=10, height=10))
    for i in scene.graphics.values(): i.setSelected(True)
    c.align("top")
    assert {m.y for m in c.document.items} == {5}
    c.align("distribute_x")
    assert [m.x for m in c.document.items] == [10, 75, 140]
    scene.clearSelection()
    first = c.document.items[0]
    scene.graphics[first.id].setSelected(True)
    c.layer("front")
    assert c.document.items[-1].id == first.id
    c.toggle_lock(first.id)
    assert c.document.items[-1].locked
    assert not scene.graphics[first.id].isSelected()
    c.toggle_lock(first.id)
    assert scene.graphics[first.id].isSelected()


def png_data():
    image = QImage(30, 20, QImage.Format.Format_ARGB32)
    image.fill(QColor("#dc2626"))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def test_image_import_embedded_roundtrip(editor, tmp_path):
    c, scene, _ = editor
    path = tmp_path / "image.png"
    path.write_bytes(png_data())
    c.import_image(str(path))
    assert c.document.items[0].keep_ratio
    project = tmp_path / "test.a4livre"
    save_project(c.document, project)
    path.unlink()
    loaded = load_project(project)
    assert loaded == c.document
    assert base64.b64decode(loaded.items[0].image) == png_data()
    c.replace(loaded)
    assert not scene.graphics[loaded.items[0].id].pixmap.isNull()


def test_orientation_preserves_geometry_and_undo(editor):
    c, _, _ = editor
    c.add(ItemModel(x=47.25, y=92.75, width=23.4, height=76.1, rotation=33))
    before = deepcopy(c.document.items)
    c.set_page("orientation", "landscape")
    assert c.document.page_size == (297, 210)
    assert c.document.items == before
    c.stack.undo()
    assert c.document.page_size == (210, 297)
