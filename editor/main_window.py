"""Janela principal, comandos de arquivo e integração com o Windows."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QPainter, QTextCursor
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (QApplication, QComboBox, QDockWidget, QFileDialog, QInputDialog,
                              QLabel, QMainWindow, QMessageBox, QSpinBox, QToolBar)

from .canvas import CanvasScene, CanvasView
from .controller import Controller
from .export.pdf_exporter import configure_page, export_pdf, render_document
from .figure_editor import FigureEditor
from .project.models import Document, GEOMETRIC_KINDS
from .project.serializer import load_project, save_project
from .properties_panel import PropertiesPanel
from .theme import apply_theme


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        apply_theme()
        self.path: Path | None = None
        self.figure_editor = None
        self.controller = Controller(self)
        self.controller.item_editor_requested.connect(self.open_figure_editor)
        self.scene = CanvasScene(self.controller)
        QApplication.instance().aboutToQuit.connect(self.shutdown)
        self.view = CanvasView(self.scene)
        self.setCentralWidget(self.view)
        self.resize(1440, 930)
        self.setMinimumSize(950, 640)
        self.actions = {}
        self.make_actions()
        self.make_menus()
        self.make_toolbars()
        self.properties = PropertiesPanel(self.controller)
        dock = QDockWidget("Documento", self)
        dock.setObjectName("properties")
        dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        dock.setWidget(self.properties)
        dock.setMinimumWidth(295)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.controller.changed.connect(self.refresh)
        self.controller.content_changed.connect(self.refresh_title)
        self.controller.stack.cleanChanged.connect(self.refresh_title)
        self.controller.stack.canUndoChanged.connect(self.actions["undo"].setEnabled)
        self.controller.stack.canRedoChanged.connect(self.actions["redo"].setEnabled)
        self.scene.selectionChanged.connect(self.refresh_selection)
        self.statusBar().showMessage("Selecione uma ferramenta e desenhe na folha. Medidas em milímetros.")
        self.page_info = QLabel()
        self.statusBar().addPermanentWidget(self.page_info)
        self.setStyleSheet("""
            QMainWindow, QDockWidget { background: #f8fafc; color: #172033; }
            QToolBar { background: #ffffff; border: none; border-bottom: 1px solid #dbe2ed; spacing: 4px; padding: 5px; }
            QToolButton { padding: 6px 8px; border-radius: 5px; }
            QToolButton:hover, QPushButton:hover { background: #e8efff; }
            QToolButton:checked { background: #dbeafe; color: #1d4ed8; }
            QGroupBox { font-weight: 600; border: 1px solid #dbe2ed; border-radius: 6px; margin-top: 12px; padding-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 9px; }
            QDoubleSpinBox, QSpinBox, QComboBox { padding: 4px; min-height: 22px; }
            QPushButton { padding: 5px 8px; border: 1px solid #cbd5e1; border-radius: 4px; background: white; }
            QTabWidget::pane { border: none; } QTabBar::tab { padding: 9px 12px; }
            QStatusBar { background: #f1f5f9; color: #475569; }
        """)
        self.refresh()
        QTimer.singleShot(0, self.view.fit_page)

    def action(self, key, text, callback, shortcut=None, checkable=False):
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.setCheckable(checkable)
        action.triggered.connect(lambda checked=False: self.safe(lambda: callback(checked) if checkable else callback()))
        self.actions[key] = action
        self.addAction(action)
        return action

    def safe(self, callback):
        try:
            return callback()
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.critical(self, "Não foi possível concluir", str(exc))
            return False

    def open_figure_editor(self, uid: str) -> None:
        """Janela por figura; a confirmação aplica apenas ao objeto que a abriu."""
        if self.figure_editor is not None:
            self.figure_editor.raise_()
            self.figure_editor.activateWindow()
            return
        model = next((m for m in self.controller.document.items if m.id == uid), None)
        if model is None or model.kind not in GEOMETRIC_KINDS or model.locked:
            return
        self.view.cancel_gesture()
        self.controller.finish_text()
        self.scene.clearSelection()
        self.scene.graphics[uid].setSelected(True)
        dialog = FigureEditor(model, self)
        if self.testAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen):
            dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        self.figure_editor = dialog

        def complete(result):
            self.figure_editor = None
            if result == FigureEditor.DialogCode.Accepted:
                self.safe(lambda: self.controller.edit_figure(uid, dialog.draft))
            dialog.deleteLater()
            self.view.setFocus()
        dialog.finished.connect(complete)
        dialog.open()

    def make_actions(self):
        c = self.controller
        for key, label, callback, shortcut in (
            ("new", "Novo", self.new, "Ctrl+N"), ("open", "Abrir…", self.open, "Ctrl+O"),
            ("save", "Salvar", self.save, "Ctrl+S"), ("save_as", "Salvar como…", lambda: self.save(True), "Ctrl+Shift+S"),
            ("undo", "Desfazer", lambda: self.edit("undo"), "Ctrl+Z"),
            ("redo", "Refazer", lambda: self.edit("redo"), "Ctrl+Y"),
            ("copy", "Copiar", lambda: self.edit("copy"), "Ctrl+C"),
            ("paste", "Colar", lambda: self.edit("paste"), "Ctrl+V"),
            ("cut", "Recortar", lambda: self.edit("cut"), "Ctrl+X"),
            ("delete", "Excluir", lambda: self.edit("delete"), "Delete"),
            ("select_all", "Selecionar tudo", lambda: self.edit("select_all"), "Ctrl+A"),
            ("duplicate", "Duplicar", c.duplicate, "Ctrl+D"),
            ("group", "Agrupar", c.group, "Ctrl+G"),
            ("ungroup", "Desagrupar", c.ungroup, "Ctrl+Shift+G"),
            ("front", "Trazer para frente", lambda: c.layer("front"), None),
            ("back", "Enviar para trás", lambda: c.layer("back"), None),
            ("lock", "Bloquear seleção", lambda: c.set_property("locked", True), "Ctrl+L"),
            ("image", "Inserir imagem…", self.import_image, "Ctrl+I"),
            ("pdf", "Exportar PDF…", self.pdf, "Ctrl+E"),
            ("print", "Imprimir…", self.print_document, "Ctrl+P"),
            ("fit", "Ajustar página", self.view.fit_page, "Ctrl+0"),
        ):
            self.action(key, label, callback, shortcut)
        for key, label in (("left", "À esquerda"), ("center_x", "Centralizar horizontalmente"),
                           ("right", "À direita"), ("top", "Ao topo"), ("center_y", "Centralizar verticalmente"),
                           ("bottom", "À base"), ("distribute_x", "Distribuir horizontalmente"),
                           ("distribute_y", "Distribuir verticalmente")):
            self.action(key, label, lambda mode=key: c.align(mode))
        self.action("grid", "Grade", lambda v: c.set_page("grid", v), checkable=True)
        self.action("snap", "Ajustar à grade", lambda v: c.set_page("snap", v), checkable=True)
        self.actions["undo"].setEnabled(False)
        self.actions["redo"].setEnabled(False)

    def make_menus(self):
        for title, keys in (
            ("Arquivo", ["new", "open", "save", "save_as", "pdf", "print"]),
            ("Editar", ["undo", "redo", "cut", "copy", "paste", "duplicate", "delete", "select_all"]),
            ("Organizar", ["group", "ungroup", "front", "back", "lock", "left", "center_x", "right",
                           "top", "center_y", "bottom", "distribute_x", "distribute_y"]),
            ("Visualizar", ["fit", "grid", "snap"]),
        ):
            menu = self.menuBar().addMenu(title)
            for key in keys:
                menu.addAction(self.actions[key])
        help_menu = self.menuBar().addMenu("Ajuda")
        help_menu.addAction("Como usar", self.help)

    def make_toolbars(self):
        top = QToolBar("Arquivo e edição", self)
        top.setMovable(False)
        self.addToolBar(top)
        for keys in (("new", "open", "save", "save_as"), ("undo", "redo"),
                     ("copy", "paste", "duplicate"), ("group", "ungroup"), ("pdf", "print")):
            for key in keys:
                top.addAction(self.actions[key])
            top.addSeparator()
        self.addToolBarBreak()
        page = QToolBar("Página", self)
        page.setMovable(False)
        self.addToolBar(page)
        page.addWidget(QLabel("  A4  "))
        self.orientation = QComboBox()
        self.orientation.addItem("Retrato · 210 × 297 mm", "portrait")
        self.orientation.addItem("Paisagem · 297 × 210 mm", "landscape")
        self.orientation.currentIndexChanged.connect(self.orientation_changed)
        page.addWidget(self.orientation)
        page.addSeparator()
        page.addWidget(QLabel(" Zoom  "))
        self.zoom = QSpinBox()
        self.zoom.setRange(25, 400)
        self.zoom.setSuffix(" %")
        self.zoom.setSingleStep(25)
        self.zoom.setValue(100)
        self.zoom.valueChanged.connect(self.view.set_zoom)
        self.view.zoom_changed.connect(self.zoom.setValue)
        page.addWidget(self.zoom)
        for key in ("fit", "grid", "snap"):
            page.addAction(self.actions[key])
        tools = QToolBar("Ferramentas", self)
        tools.setMovable(False)
        tools.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, tools)
        self.tool_group = QActionGroup(self)
        self.tool_actions = {}
        for key, label in (("select", "↖  Seleção"), ("rectangle", "▭  Retângulo"), ("square", "□  Quadrado"),
                           ("circle", "○  Círculo"), ("ellipse", "⬭  Elipse"), ("line", "╱  Linha"),
                           ("arrow", "↗  Seta"), ("text", "T  Texto")):
            action = QAction(label, self)
            action.setCheckable(True)
            action.triggered.connect(lambda checked, tool=key: self.view.set_tool(tool))
            self.tool_group.addAction(action)
            tools.addAction(action)
            self.tool_actions[key] = action
        self.tool_actions["select"].setChecked(True)
        self.view.tool_finished.connect(lambda: self.tool_actions["select"].setChecked(True))
        tools.addSeparator()
        tools.addAction(self.actions["image"])

    def orientation_changed(self):
        value = self.orientation.currentData()
        if value != self.controller.document.orientation:
            self.controller.set_page("orientation", value)
            self.view.fit_page()

    def refresh_title(self):
        dirty = not self.controller.stack.isClean() or (self.controller.text_before is not None and
                 self.controller.text_before != self.controller.document)
        name = self.path.name if self.path else "Sem título"
        self.setWindowTitle(f"{'● ' if dirty else ''}{name} — Editor A4 Livre")

    def refresh(self):
        self.refresh_title()
        doc = self.controller.document
        self.orientation.blockSignals(True)
        self.orientation.setCurrentIndex(self.orientation.findData(doc.orientation))
        self.orientation.blockSignals(False)
        for key in ("grid", "snap"):
            self.actions[key].setChecked(getattr(doc, key))
        w, h = doc.page_size
        self.page_info.setText(f"A4 · {w:g} × {h:g} mm  |  {len(doc.items)} objetos  ")
        self.refresh_selection()
        self.view.viewport().update()

    def refresh_selection(self):
        count = len(self.controller.selected())
        for key in ("duplicate", "group", "ungroup", "front", "back", "lock", "left", "right", "top", "bottom",
                    "center_x", "center_y", "distribute_x", "distribute_y"):
            self.actions[key].setEnabled(count >= (3 if key.startswith("distribute") else 2 if key in
                                                 ("group", "left", "right", "top", "bottom", "center_x", "center_y") else 1))
        self.actions["ungroup"].setEnabled(any(i.model.kind == "group" for i in self.controller.selected()))

    def edit(self, operation):
        c = self.controller
        active = c.text_item
        if active and active.text_editor and active.text_editor.hasFocus():
            editor = active.text_editor
            cursor = editor.textCursor()
            if operation in ("copy", "cut"):
                QApplication.clipboard().setText(cursor.selectedText().replace("\u2029", "\n"))
                if operation == "cut": cursor.removeSelectedText()
            elif operation == "paste": cursor.insertText(QApplication.clipboard().text())
            elif operation == "delete": cursor.deleteChar()
            elif operation == "select_all": cursor.select(QTextCursor.SelectionType.Document)
            elif operation == "undo": editor.document().undo()
            elif operation == "redo": editor.document().redo()
            editor.setTextCursor(cursor)
            return
        c.finish_text()
        if operation == "undo": c.stack.undo()
        elif operation == "redo": c.stack.redo()
        elif operation == "copy": c.copy()
        elif operation == "paste": c.paste()
        elif operation == "cut":
            if c.copy(): c.delete()
        elif operation == "delete": c.delete()
        elif operation == "select_all":
            for item in self.scene.graphics.values():
                if not item.model.locked: item.setSelected(True)

    def confirm_unsaved(self) -> bool:
        self.controller.finish_text()
        if self.controller.stack.isClean():
            return True
        result = QMessageBox.question(self, "Alterações não salvas", "Deseja salvar as alterações do projeto?",
                                      QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard |
                                      QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Save)
        if result == QMessageBox.StandardButton.Save:
            return bool(self.safe(self.save))
        return result == QMessageBox.StandardButton.Discard

    def new(self):
        if self.confirm_unsaved():
            self.view.cancel_gesture()
            self.path = None
            self.controller.replace(Document())
            self.view.fit_page()

    def open(self):
        path, _ = QFileDialog.getOpenFileName(self, "Abrir projeto", "", "Editor A4 Livre (*.a4livre)")
        if path:
            self.open_path(path)

    def open_path(self, path: str):
        document = load_project(path)
        if self.confirm_unsaved():
            self.view.cancel_gesture()
            self.path = Path(path)
            self.controller.replace(document)
            self.view.fit_page()

    def save(self, save_as=False):
        self.controller.finish_text()
        path = self.path
        if save_as or path is None:
            chosen, _ = QFileDialog.getSaveFileName(self, "Salvar projeto", str(path or "Projeto.a4livre"),
                                                   "Editor A4 Livre (*.a4livre)")
            if not chosen:
                return False
            path = Path(chosen)
            if path.suffix.lower() != ".a4livre":
                path = path.with_name(path.name + ".a4livre")
        save_project(self.controller.document, path)
        self.path = path
        self.controller.stack.setClean()
        self.refresh_title()
        self.statusBar().showMessage(f"Projeto salvo: {path.name}", 5000)
        return True

    def import_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Inserir imagem", "", "Imagens (*.png *.jpg *.jpeg)")
        if path:
            self.controller.import_image(path)

    def pdf(self):
        self.controller.finish_text()
        suggested = str(self.path.with_suffix(".pdf")) if self.path else "Projeto.pdf"
        path, _ = QFileDialog.getSaveFileName(self, "Exportar PDF A4", suggested, "PDF (*.pdf)")
        if path:
            if not path.lower().endswith(".pdf"):
                path += ".pdf"
            export_pdf(self.controller.document, path)
            self.statusBar().showMessage("PDF A4 exportado em tamanho real.", 5000)

    def print_document(self):
        self.controller.finish_text()
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        configure_page(printer, self.controller.document)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() != QPrintDialog.DialogCode.Accepted:
            return
        choice, ok = QInputDialog.getItem(self, "Escala de impressão",
                    "Tamanho real pode recortar conteúdo nas margens físicas da impressora.",
                    ["Tamanho real · 100%", "Ajustar à área imprimível"], 0, False)
        if not ok:
            return
        printable = QRectF(printer.pageLayout().paintRectPixels(printer.resolution()))
        printer.setFullPage(True)
        w, h = self.controller.document.page_size
        scale = printer.resolution() / 25.4
        target = QRectF(0, 0, w * scale, h * scale)
        if choice.startswith("Ajustar"):
            factor = min(printable.width() / target.width(), printable.height() / target.height())
            target.setSize(target.size() * factor)
            target.moveCenter(printable.center())
        painter = QPainter()
        if not painter.begin(printer):
            raise OSError("Não foi possível iniciar a impressão.")
        try:
            render_document(self.controller.document, painter, target)
        finally:
            painter.end()

    def help(self):
        QMessageBox.information(self, "Como usar", "1. Selecione uma ferramenta e arraste na página.\n"
            "2. Use as oito alças para redimensionar; Shift mantém a proporção.\n"
            "3. Use a alça circular para girar; Shift ajusta em passos de 15°.\n"
            "4. Edite as medidas em mm no painel à direita.\n"
            "5. Ao criar uma figura, o editor de texto e cores abre automaticamente.\n"
            "   Duplo clique na figura reabre seu editor individual.\n"
            "   Duplo clique em texto livre permite escrever; Esc encerra.\n"
            "6. Ctrl seleciona vários; arraste no fundo para selecionar por área.\n"
            "7. Use Organizar para alinhar, distribuir e ordenar.\n"
            "8. Na aba Camadas, dê duplo clique para bloquear/desbloquear.\n"
            "9. Ctrl+S salva o projeto; Ctrl+E exporta PDF A4.\n\n"
            "Setas movem 1 mm; Shift+seta move 10 mm. Ctrl+roda altera o zoom.\n"
            "O PDF inclui somente o conteúdo dentro da folha. Texto excedente à caixa é recortado.")

    def closeEvent(self, event):
        if self.confirm_unsaved():
            self.shutdown()
            event.accept()
        else:
            event.ignore()

    def shutdown(self):
        # Destruir a cena remove itens selecionados; não notificar painéis
        # durante a destruição dos objetos C++ pertencentes à janela.
        self.scene.blockSignals(True)
