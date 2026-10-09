"""Editor individual de texto e cores, com prévia da figura e cancelamento seguro."""
from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox,
                              QDoubleSpinBox, QFontComboBox, QFormLayout, QGraphicsScene,
                              QGraphicsView, QGroupBox, QHBoxLayout, QLabel, QPlainTextEdit,
                              QPushButton, QVBoxLayout, QWidget)

from .items.base_item import GraphicItem
from .project.models import ItemModel
from .properties_panel import LABELS


class FigurePreview(QGraphicsView):
    """Ajusta a figura depois que o layout define o tamanho real da prévia."""

    def __init__(self, scene):
        super().__init__(scene)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


class FigureEditor(QDialog):
    """Rascunho por ID: nenhuma alteração alcança outra figura ou o projeto ao cancelar."""

    def __init__(self, model: ItemModel, parent=None):
        super().__init__(parent)
        self.uid = model.id
        self.draft = deepcopy(model)
        self.setWindowTitle(f"Editar {LABELS[model.kind].lower()} — texto e cores")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(720, 610)
        self.setMinimumSize(620, 530)
        root = QVBoxLayout(self)
        note = QLabel("Escreva o texto desta figura e escolha o alinhamento e as cores.")
        note.setWordWrap(True)
        root.addWidget(note)
        self.text = QPlainTextEdit()
        self.text.setObjectName("figureText")
        self.text.setPlaceholderText("Digite aqui o texto que aparecerá na figura…")
        self.text.setPlainText(model.shape_text)
        self.text.setMaximumHeight(110)
        root.addWidget(self.text)
        middle = QHBoxLayout()
        settings = QGroupBox("Texto e cores desta figura")
        form = QFormLayout(settings)
        self.font = QFontComboBox()
        self.font.setCurrentFont(QFont(model.font_family))
        form.addRow("Fonte", self.font)
        self.size = QDoubleSpinBox()
        self.size.setRange(1, 2000)
        self.size.setDecimals(2)
        self.size.setSuffix(" pt")
        self.size.setKeyboardTracking(False)
        self.size.setValue(model.font_size)
        form.addRow("Tamanho", self.size)
        self.bold, self.italic, self.underline = (QCheckBox(label) for label in ("Negrito", "Itálico", "Sublinhado"))
        formats = QWidget()
        formats_layout = QHBoxLayout(formats)
        formats_layout.setContentsMargins(0, 0, 0, 0)
        for key in ("bold", "italic", "underline"):
            check = getattr(self, key)
            check.setChecked(getattr(model, key))
            formats_layout.addWidget(check)
        form.addRow(formats)
        self.alignment = QComboBox()
        for label, value in (("Esquerda", "left"), ("Centro", "center"), ("Direita", "right")):
            self.alignment.addItem(label, value)
        self.alignment.setCurrentIndex(self.alignment.findData(model.alignment))
        form.addRow("Horizontal", self.alignment)
        self.vertical = QComboBox()
        for label, value in (("Topo", "top"), ("Centro", "center"), ("Base", "bottom")):
            self.vertical.addItem(label, value)
        self.vertical.setCurrentIndex(self.vertical.findData(model.vertical_alignment))
        form.addRow("Vertical", self.vertical)
        self.center = QPushButton("Centralizar texto na figura")
        form.addRow(self.center)
        self.colors = {}
        for key, label in (("text_color", "Cor do texto"), ("fill", "Preenchimento"), ("stroke", "Borda / linha")):
            if key == "fill" and model.kind in ("line", "arrow"):
                continue
            button = QPushButton()
            button.clicked.connect(lambda checked=False, k=key: self.choose_color(k))
            self.colors[key] = button
            form.addRow(label, button)
        middle.addWidget(settings)
        preview_box = QGroupBox("Prévia")
        preview_layout = QVBoxLayout(preview_box)
        self.preview_scene = QGraphicsScene(self)
        # Geometria local; a prévia é centralizada sem alterar posição no projeto.
        self.preview_model = deepcopy(model)
        self.preview_model.x = self.preview_model.y = self.preview_model.rotation = 0
        self.preview_model.opacity = 1
        self.preview_item = GraphicItem(self.preview_model)
        self.preview_scene.addItem(self.preview_item)
        self.preview = FigurePreview(self.preview_scene)
        self.preview.setMinimumWidth(220)
        self.preview.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.preview.setBackgroundBrush(QColor("#ffffff"))
        self.preview.setInteractive(False)
        preview_layout.addWidget(self.preview)
        tip = QLabel("A fonte mantém seu tamanho ao redimensionar a figura.\n"
                     "Texto excedente à área interna é recortado.")
        tip.setWordWrap(True)
        preview_layout.addWidget(tip)
        middle.addWidget(preview_box, 1)
        root.addLayout(middle, 1)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Aplicar")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)
        self.text.textChanged.connect(self.update_draft)
        self.font.currentFontChanged.connect(self.update_draft)
        self.size.valueChanged.connect(self.update_draft)
        self.alignment.currentIndexChanged.connect(self.update_draft)
        self.vertical.currentIndexChanged.connect(self.update_draft)
        for check in (self.bold, self.italic, self.underline):
            check.toggled.connect(self.update_draft)
        self.center.clicked.connect(self.center_text)
        self.update_draft()
        QTimer.singleShot(0, self.text.setFocus)

    def update_draft(self, *args) -> None:
        m = self.draft
        # Limite igual ao formato do projeto, inclusive ao colar no editor.
        content = self.text.toPlainText()
        if len(content) > 1_000_000:
            self.text.blockSignals(True)
            self.text.setPlainText(content[:1_000_000])
            self.text.blockSignals(False)
            content = content[:1_000_000]
        m.shape_text = content
        m.font_family = self.font.currentFont().family()
        m.font_size = self.size.value()
        for key in ("bold", "italic", "underline"):
            setattr(m, key, getattr(self, key).isChecked())
        m.alignment = self.alignment.currentData()
        m.vertical_alignment = self.vertical.currentData()
        for key in ("shape_text", "font_family", "font_size", "bold", "italic", "underline",
                    "alignment", "vertical_alignment", "text_color", "fill", "stroke"):
            setattr(self.preview_model, key, getattr(m, key))
        self.preview_item.sync()
        self.fit_preview()
        self.update_color_buttons()

    def center_text(self) -> None:
        self.alignment.setCurrentIndex(self.alignment.findData("center"))
        self.vertical.setCurrentIndex(self.vertical.findData("center"))

    def choose_color(self, key: str) -> None:
        color = QColorDialog.getColor(QColor(getattr(self.draft, key)), self, "Escolher cor",
                                      QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid():
            setattr(self.draft, key, color.name(QColor.NameFormat.HexArgb))
            self.update_draft()

    def update_color_buttons(self) -> None:
        for key, button in self.colors.items():
            color = QColor(getattr(self.draft, key))
            button.setText("Transparente" if color.alpha() == 0 else color.name())
            button.setStyleSheet(f"border-left: 18px solid {color.name()};")

    def fit_preview(self) -> None:
        rect = self.preview_item.boundingRect().adjusted(-3, -3, 3, 3)
        self.preview_scene.setSceneRect(rect)
        self.preview.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "preview"):
            self.fit_preview()
