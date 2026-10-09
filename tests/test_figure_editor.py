"""Fluxo real: criação automática, edição individual e persistência do texto."""
from copy import deepcopy

import pymupdf
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QDialogButtonBox, QMessageBox

from editor.figure_editor import FigureEditor
from editor.main_window import MainWindow
from editor.project.models import Document, ItemModel
from editor.project.serializer import load_project, parse_document, save_project
from editor.export.pdf_exporter import export_pdf


@pytest.fixture
def window(qtbot):
    w = MainWindow()

    def close(widget):
        if widget.figure_editor:
            widget.figure_editor.reject()
        widget.controller.finish_text()
        widget.controller.stack.setClean()

    qtbot.addWidget(w, before_close_func=close)
    w.show()
    qtbot.waitExposed(w)
    return w


@pytest.mark.parametrize("tool", ["rectangle", "square", "circle", "ellipse", "line", "arrow"])
def test_new_shape_opens_own_editor(window, qtbot, tool):
    view = window.view
    view.set_tool(tool)
    start, end = view.mapFromScene(QPointF(40, 40)), view.mapFromScene(QPointF(95, 80))
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(view.viewport(), end)
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    qtbot.waitUntil(lambda: window.figure_editor is not None)
    dialog = window.figure_editor
    qtbot.waitExposed(dialog)
    assert dialog.isVisible()
    assert dialog.uid == window.controller.document.items[0].id
    assert dialog.text.toPlainText() == ""
    qtbot.keyClicks(dialog.text, "Minha figura")
    qtbot.mouseClick(dialog.center, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(dialog.buttons.button(QDialogButtonBox.StandardButton.Ok), Qt.MouseButton.LeftButton)
    m = window.controller.document.items[0]
    assert m.shape_text == "Minha figura"
    assert m.alignment == m.vertical_alignment == "center"
    assert window.figure_editor is None
    assert window.controller.stack.count() == 2  # criação e edição, um comando cada


def test_edit_isolated_by_id_colors_and_undo(window, qtbot, monkeypatch):
    c = window.controller
    a, b = ItemModel(shape_text="Primeira"), ItemModel(kind="ellipse", x=85, shape_text="Segunda")
    c.add(a)
    c.add(b)
    second = deepcopy(b)
    window.open_figure_editor(a.id)
    dialog = window.figure_editor
    dialog.text.setPlainText("Só a primeira\nOutra linha")
    dialog.size.setValue(16)
    dialog.bold.setChecked(True)
    qtbot.mouseClick(dialog.center, Qt.MouseButton.LeftButton)
    monkeypatch.setattr(QColorDialog, "getColor", lambda *args: QColor("#fbbf24"))
    qtbot.mouseClick(dialog.colors["fill"], Qt.MouseButton.LeftButton)
    monkeypatch.setattr(QColorDialog, "getColor", lambda *args: QColor("#dc2626"))
    qtbot.mouseClick(dialog.colors["text_color"], Qt.MouseButton.LeftButton)
    assert dialog.preview_model.shape_text == "Só a primeira\nOutra linha"
    assert c.document.items[0].shape_text == "Primeira"  # rascunho até Aplicar
    # Mesmo se uma seleção externa mudar, o editor permanece ligado ao ID aberto.
    window.scene.clearSelection()
    window.scene.graphics[b.id].setSelected(True)
    qtbot.mouseClick(dialog.buttons.button(QDialogButtonBox.StandardButton.Ok), Qt.MouseButton.LeftButton)
    edited = c.document.items[0]
    assert edited.shape_text == "Só a primeira\nOutra linha"
    assert edited.fill == "#fffbbf24" and edited.text_color == "#ffdc2626"
    assert edited.font_size == 16 and edited.bold
    assert c.document.items[1] == second
    c.stack.undo()
    assert c.document.items[0].shape_text == "Primeira"
    assert c.document.items[1] == second
    c.stack.redo()
    assert c.document.items[0] == edited and c.document.items[1] == second


def test_cancel_keeps_created_figure_and_discards_draft(window, qtbot):
    c = window.controller
    m = ItemModel(shape_text="Original", fill="#ff112233")
    c.add(m)
    before = c.snapshot()
    count = c.stack.count()
    window.open_figure_editor(m.id)
    dialog = window.figure_editor
    dialog.text.setPlainText("Não salvar")
    dialog.bold.setChecked(True)
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    assert c.document == before
    assert c.stack.count() == count
    assert window.figure_editor is None


def test_double_click_and_panel_reopen_individual_editor(window, qtbot):
    c = window.controller
    m = ItemModel(width=65, height=45, shape_text="Reabrir")
    c.add(m)
    view = window.view
    position = view.mapFromScene(QPointF(m.x+32, m.y+22))
    qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=position)
    qtbot.mouseDClick(view.viewport(), Qt.MouseButton.LeftButton, pos=position)
    assert window.figure_editor is not None and window.figure_editor.uid == m.id
    window.figure_editor.reject()
    assert window.properties.edit_figure.isVisible()
    qtbot.mouseClick(window.properties.edit_figure, Qt.MouseButton.LeftButton)
    assert window.figure_editor.uid == m.id
    window.figure_editor.reject()


def test_locked_shape_cannot_open_editor(window):
    m = ItemModel(locked=True)
    window.controller.add(m)
    window.open_figure_editor(m.id)
    assert window.figure_editor is None


def test_preview_fits_after_dialog_layout_and_resize(window, qtbot):
    m = ItemModel(width=74, height=46, shape_text="Minha figura")
    window.controller.add(m)
    window.open_figure_editor(m.id)
    dialog = window.figure_editor
    qtbot.waitExposed(dialog)
    qtbot.wait(10)
    for size in ((720, 610), (900, 650)):
        dialog.resize(*size)
        qtbot.wait(10)
        rect = dialog.preview.mapFromScene(dialog.preview_item.boundingRect()).boundingRect()
        assert rect.left() >= 0 and rect.top() >= 0
        assert rect.right() < dialog.preview.viewport().width()
        assert rect.bottom() < dialog.preview.viewport().height()


def test_old_projects_keep_shapes_blank(qapp):
    data = Document(items=[ItemModel(), ItemModel(kind="text")]).to_dict()
    for raw in data["items"]:
        raw.pop("shape_text")
        raw.pop("vertical_alignment")
    doc = parse_document(data)
    assert doc.items[0].shape_text == ""
    assert doc.items[1].text == "Texto"


@pytest.mark.parametrize("field,value", [("shape_text", []), ("vertical_alignment", "invalid")])
def test_invalid_new_fields_rejected(field, value):
    data = Document(items=[ItemModel()]).to_dict()
    data["items"][0][field] = value
    with pytest.raises(ValueError):
        parse_document(data)


def test_shape_text_duplicate_resize_group_save_and_pdf(editor, tmp_path):
    c, scene, view = editor
    a = ItemModel(x=20, y=30, width=70, height=40, shape_text="Primeira figura", alignment="center",
                  vertical_alignment="center", text_color="#ffdc2626", font_size=14, fill="#ffeff6ff")
    b = ItemModel(kind="ellipse", x=110, y=30, width=70, height=50, shape_text="Segunda figura",
                  alignment="center", vertical_alignment="center", font_size=14)
    c.add(a)
    c.add(b)
    c.duplicate()
    assert c.document.items[-1].shape_text == "Segunda figura"
    c.set_property("width", 90)
    assert c.document.items[-1].font_size == 14
    for item in scene.graphics.values(): item.setSelected(True)
    c.group()
    c.ungroup()
    path = tmp_path / "figuras.a4livre"
    save_project(c.document, path)
    loaded = load_project(path)
    assert loaded == c.document
    pdf_path = tmp_path / "figuras.pdf"
    export_pdf(loaded, pdf_path)
    with pymupdf.open(pdf_path) as pdf:
        text = pdf[0].get_text()
        assert "Primeira figura" in text and text.count("Segunda figura") == 2
        span = next(s for b in pdf[0].get_text("dict")["blocks"] if "lines" in b
                    for l in b["lines"] for s in l["spans"] if s["text"] == "Primeira figura")
        center_x = (span["bbox"][0] + span["bbox"][2]) / 2
        assert center_x == pytest.approx((a.x+a.width/2)*72/25.4, abs=1)
        assert span["color"] == 0xdc2626
        assert span["size"] == pytest.approx(14, abs=.1)


@pytest.mark.parametrize("kind", ["rectangle", "ellipse", "line", "arrow"])
@pytest.mark.parametrize("vertical", ["top", "center", "bottom"])
def test_label_layout_stays_inside_area(editor, kind, vertical):
    c, scene, view = editor
    m = ItemModel(kind=kind, width=60, height=0 if kind in ("line", "arrow") else 45,
                  shape_text="Linha 1\nLinha 2", alignment="center", vertical_alignment=vertical)
    c.add(m)
    graphic = scene.graphics[m.id]
    text = graphic.text_editor
    rect = graphic.text_rect()
    content_height = text.document().size().height() * text.scale()
    assert text.pos().x() == pytest.approx(rect.left())
    offset = max(0, rect.height()-content_height)
    expected_y = rect.top() + (offset/2 if vertical == "center" else offset if vertical == "bottom" else 0)
    assert text.pos().y() == pytest.approx(expected_y)
