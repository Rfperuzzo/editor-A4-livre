"""Autoteste opcional do binário empacotado, sem interação ou rede."""
from __future__ import annotations

import json
import platform
import traceback
from pathlib import Path

from PySide6.QtCore import QPointF, Qt, qVersion
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from pypdf import PdfReader

from .export.pdf_exporter import export_pdf
from .project.models import ItemModel
from .project.serializer import load_project, save_project


def run(window, directory: str) -> int:
    """Confirma GUI, mouse, histórico, persistência e PDF no próprio executável."""
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    report = {"python": platform.python_version(), "qt": qVersion(), "checks": []}
    try:
        c = window.controller
        c.add(ItemModel(x=40, y=55, width=45, height=30, rotation=30))
        window.view.set_zoom(100)
        window.view.centerOn(65, 70)
        QApplication.processEvents()
        item = window.scene.graphics[c.document.items[0].id]
        start = window.view.handles(item)[4].toPoint()
        end = window.view.mapFromScene(item.mapToScene(QPointF(60, 40)))
        QTest.mousePress(window.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(window.view.viewport(), end)
        QTest.mouseRelease(window.view.viewport(), Qt.MouseButton.LeftButton, pos=end)
        assert c.document.items[0].width > 55
        report["checks"].append("mouse_resize_rotated")
        c.stack.undo()
        assert c.document.items[0].width == 45
        c.stack.redo()
        report["checks"].append("undo_redo")
        uid = c.document.items[0].id
        c.add(ItemModel(kind="ellipse", x=115, y=60, width=60, height=40, shape_text="Segunda figura"))
        window.open_figure_editor(uid)
        dialog = window.figure_editor
        assert dialog and dialog.isVisible()
        dialog.text.setPlainText("Minha figura")
        dialog.center.click()
        dialog.draft.fill = "#fffbbf24"
        dialog.update_draft()
        dialog.accept()
        assert c.document.items[0].shape_text == "Minha figura"
        assert c.document.items[0].fill == "#fffbbf24"
        assert c.document.items[1].shape_text == "Segunda figura"
        report["checks"].append("individual_figure_editor")
        c.add(ItemModel(kind="text", x=35, y=25, width=140, height=20, text="Editor A4 Livre", font_size=20,
                        fill="#00000000", stroke_width=0))
        save_project(c.document, target / "smoke.a4livre")
        assert load_project(target / "smoke.a4livre") == c.document
        report["checks"].append("project_roundtrip")
        export_pdf(c.document, target / "smoke.pdf")
        page = PdfReader(target / "smoke.pdf").pages[0]
        assert abs(float(page.mediabox.width) - 210 * 72 / 25.4) < .001
        assert "Editor" in page.extract_text()
        assert "Minha figura" in page.extract_text()
        assert "Segunda figura" in page.extract_text()
        report["checks"].append("vector_a4_pdf")
        window.view.fit_page()
        QApplication.processEvents()
        window.grab().save(str(target / "smoke-window.png"))
        report["ok"] = True
    except Exception:
        report["ok"] = False
        report["error"] = traceback.format_exc()
    (target / "smoke-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    window.controller.stack.setClean()
    window.close()
    return 0 if report["ok"] else 1
