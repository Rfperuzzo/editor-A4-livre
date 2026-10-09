import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QMessageBox

from editor.main_window import MainWindow
from editor.project.models import ItemModel


@pytest.fixture
def window(qtbot):
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda widget: (widget.controller.finish_text(), widget.controller.stack.setClean()))
    w.show()
    qtbot.waitExposed(w)
    yield w
    w.controller.finish_text()
    w.controller.stack.setClean()


def test_window_properties_and_text_shortcuts(window, qtbot):
    c = window.controller
    c.add(ItemModel(kind="text", text="Teste de texto"))
    field = window.properties.fields["width"]
    field.setValue(80)
    field.editingFinished.emit()
    assert c.document.items[0].width == 80
    item = window.scene.graphics[c.document.items[0].id]
    item.begin_text()
    window.edit("select_all")
    window.edit("copy")
    window.edit("cut")
    assert len(c.document.items) == 1
    assert c.document.items[0].text == ""
    window.edit("paste")
    assert c.document.items[0].text == "Teste de texto"
    c.finish_text()
    window.actions["duplicate"].trigger()
    assert len(c.document.items) == 2


def test_save_cancel_and_invalid_open_preserve_document(window, tmp_path, monkeypatch):
    c = window.controller
    c.add(ItemModel())
    before = c.snapshot()
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Cancel)
    window.new()
    assert c.document == before
    bad = tmp_path / "bad.a4livre"
    bad.write_text("bad", encoding="utf-8")
    with pytest.raises(ValueError): window.open_path(str(bad))
    assert c.document == before
    window.path = tmp_path / "good.a4livre"
    assert window.save()
    assert c.stack.isClean()
    window.new()
    assert c.document.items == []
    window.open_path(str(tmp_path / "good.a4livre"))
    assert c.document == before


def test_actual_keyboard_text_edit_and_delete(window, qtbot):
    c = window.controller
    c.add(ItemModel(kind="text", text="Original"))
    item = window.scene.graphics[c.document.items[0].id]
    item.begin_text()
    qtbot.keyClick(window.view.viewport(), Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    qtbot.keyClicks(window.view.viewport(), "Novo texto")
    assert c.document.items[0].text == "Novo texto"
    qtbot.keyClick(window.view.viewport(), Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    qtbot.keyClick(window.view.viewport(), Qt.Key.Key_Delete)
    assert len(c.document.items) == 1 and c.document.items[0].text == ""
    qtbot.keyClick(window.view.viewport(), Qt.Key.Key_Escape)


@pytest.mark.parametrize("fit", [False, True])
def test_print_to_pdf_device(window, tmp_path, monkeypatch, fit):
    import pymupdf
    from PySide6.QtCore import QMarginsF
    from PySide6.QtGui import QPageLayout
    from PySide6.QtPrintSupport import QPrinter
    from PySide6.QtWidgets import QDialog, QInputDialog
    path = tmp_path / "print.pdf"
    window.controller.add(ItemModel(x=20, y=30, width=40, height=25, fill="#ffdc2626", stroke_width=0))

    class PrintDialog:
        DialogCode = QDialog.DialogCode

        def __init__(self, printer, parent):
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(str(path))
            printer.setPageMargins(QMarginsF(10, 10, 10, 10), QPageLayout.Unit.Millimeter)

        def exec(self): return QDialog.DialogCode.Accepted

    monkeypatch.setattr("editor.main_window.QPrintDialog", PrintDialog)
    monkeypatch.setattr(QInputDialog, "getItem", lambda *args: ("Ajustar" if fit else "Tamanho real", True))
    window.print_document()
    with pymupdf.open(path) as document:
        drawing = document[0].get_drawings()[0]["rect"]
        if fit:
            assert drawing.width < 40 * 72 / 25.4
        else:
            assert drawing.width == pytest.approx(40 * 72 / 25.4, abs=.1)


def test_unlock_by_double_click_on_layer(window, qtbot):
    c = window.controller
    m = ItemModel(locked=True)
    c.add(m)
    window.properties.setCurrentIndex(1)
    qtbot.wait(10)
    layers = window.properties.layers
    row = layers.item(0)
    position = layers.visualItemRect(row).center()
    qtbot.mouseClick(layers.viewport(), Qt.MouseButton.LeftButton, pos=position)
    qtbot.mouseDClick(layers.viewport(), Qt.MouseButton.LeftButton, pos=position)
    assert not c.document.items[0].locked
