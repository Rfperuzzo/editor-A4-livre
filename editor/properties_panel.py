"""Painel de propriedades em unidades físicas e lista de camadas."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFontComboBox,
                              QFormLayout, QGroupBox, QLabel, QListWidget, QListWidgetItem,
                              QPushButton, QScrollArea, QSpinBox, QTabWidget, QVBoxLayout, QWidget)

LABELS = {"rectangle": "Retângulo", "ellipse": "Elipse", "line": "Linha", "arrow": "Seta",
          "text": "Texto", "image": "Imagem", "group": "Grupo"}


class PropertiesPanel(QTabWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.refreshing = False
        self.fields = {}
        root = QWidget()
        layout = QVBoxLayout(root)
        self.title = QLabel("Selecione um objeto")
        self.title.setStyleSheet("font-weight: 600; font-size: 15px; padding: 6px 0;")
        layout.addWidget(self.title)
        self.geometry_box, geometry = self.section(layout, "Posição e tamanho · mm")
        for key, label, low, high, suffix in (
                ("x", "X", -100000, 100000, " mm"), ("y", "Y", -100000, 100000, " mm"),
                ("width", "Largura", 0, 100000, " mm"), ("height", "Altura", 0, 100000, " mm"),
                ("rotation", "Rotação", -3600, 3600, "°")):
            field = self.spin(low, high, suffix)
            self.fields[key] = field
            geometry.addRow(label, field)
            field.editingFinished.connect(lambda k=key, f=field: self.change(k, f.value()))
        self.ratio = QCheckBox("Manter proporção")
        geometry.addRow(self.ratio)
        self.ratio.toggled.connect(lambda v: self.change("keep_ratio", v))
        self.style_box, style = self.section(layout, "Aparência")
        self.style_form = style
        self.colors = {}
        for key, label in (("fill", "Preenchimento"), ("stroke", "Borda / linha"), ("text_color", "Cor do texto")):
            button = QPushButton("Escolher cor")
            button.clicked.connect(lambda checked=False, k=key: self.color(k))
            self.colors[key] = button
            style.addRow(label, button)
        for key, label, low, high, suffix in (("stroke_width", "Espessura", 0, 1000, " mm"),
                                             ("opacity", "Opacidade", 0, 100, " %")):
            field = self.spin(low, high, suffix)
            self.fields[key] = field
            style.addRow(label, field)
            field.editingFinished.connect(lambda k=key, f=field: self.change(k, f.value()/100 if k == "opacity" else f.value()))
        self.order = QSpinBox()
        self.order.setMinimum(1)
        self.order.editingFinished.connect(lambda: None if self.refreshing else controller.reorder(self.order.value()-1))
        style.addRow("Camada", self.order)
        self.lock = QPushButton("Bloquear seleção")
        self.lock.clicked.connect(lambda: controller.set_property("locked", True))
        style.addRow(self.lock)
        self.text_box, text = self.section(layout, "Texto")
        self.font = QFontComboBox()
        self.font.currentFontChanged.connect(lambda f: self.change("font_family", f.family()))
        text.addRow("Fonte", self.font)
        size = self.spin(1, 2000, " pt")
        self.fields["font_size"] = size
        size.editingFinished.connect(lambda: self.change("font_size", size.value()))
        text.addRow("Tamanho", size)
        for key, label in (("bold", "Negrito"), ("italic", "Itálico"), ("underline", "Sublinhado")):
            check = QCheckBox(label)
            check.toggled.connect(lambda v, k=key: self.change(k, v))
            self.fields[key] = check
            text.addRow(check)
        self.alignment = QComboBox()
        for label, value in (("Esquerda", "left"), ("Centro", "center"), ("Direita", "right")):
            self.alignment.addItem(label, value)
        self.alignment.currentIndexChanged.connect(lambda: self.change("alignment", self.alignment.currentData()))
        text.addRow("Alinhamento", self.alignment)
        tip = QLabel("Duplo clique para editar o texto.\nShift nas alças mantém a proporção.\nDuplo clique na camada bloqueia/desbloqueia.")
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #64748b; font-size: 11px; padding-top: 8px;")
        layout.addWidget(tip)
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(root)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.addTab(scroll, "Propriedades")
        layer_root = QWidget()
        layers_layout = QVBoxLayout(layer_root)
        layers_layout.addWidget(QLabel("Frente → fundo\nDuplo clique: bloquear / desbloquear"))
        self.layers = QListWidget()
        self.layers.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.layers.itemSelectionChanged.connect(self.select_layers)
        self.layers.itemDoubleClicked.connect(lambda item: controller.toggle_lock(item.data(Qt.ItemDataRole.UserRole)))
        layers_layout.addWidget(self.layers)
        self.addTab(layer_root, "Camadas")
        controller.changed.connect(self.refresh)
        controller.scene.selectionChanged.connect(lambda: self.refresh(False))
        self.refresh()

    @staticmethod
    def section(layout, title):
        group = QGroupBox(title)
        form = QFormLayout(group)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.addWidget(group)
        return group, form

    @staticmethod
    def spin(low, high, suffix):
        field = QDoubleSpinBox()
        field.setRange(low, high)
        field.setDecimals(2)
        field.setSuffix(suffix)
        field.setKeyboardTracking(False)
        field.setMinimumWidth(120)
        return field

    def change(self, key, value):
        if not self.refreshing:
            if key in ("width", "height"):
                selected = self.controller.selected()
                if selected and selected[0].model.kind in ("line", "arrow"):
                    other = selected[0].model.height if key == "width" else selected[0].model.width
                    value = max(value, 1 if other < 1 else 0)
                else:
                    value = max(1, value)
            self.controller.set_property(key, value)

    def color(self, key):
        selected = self.controller.selected()
        if not selected:
            return
        current = QColor(getattr(selected[0].model, key))
        color = QColorDialog.getColor(current, self, "Escolher cor", QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid():
            self.change(key, color.name(QColor.NameFormat.HexArgb))

    def refresh(self, rebuild_layers=True):
        if self.refreshing:
            return
        self.refreshing = True
        selected = self.controller.selected()
        ids = {i.model.id for i in selected}
        self.layers.blockSignals(True)
        if rebuild_layers:
            self.layers.clear()
            for index, m in reversed(list(enumerate(self.controller.document.items))):
                label = f'{index+1}  {"🔒 " if m.locked else ""}{LABELS[m.kind]}'
                if m.kind == "text":
                    label += f" · {m.text[:24]}"
                row = QListWidgetItem(label)
                row.setData(Qt.ItemDataRole.UserRole, m.id)
                self.layers.addItem(row)
                row.setSelected(m.id in ids)
        else:
            locked = {m.id for m in self.controller.document.items if m.locked}
            for index in range(self.layers.count()):
                row = self.layers.item(index)
                uid = row.data(Qt.ItemDataRole.UserRole)
                row.setSelected(uid in ids or (uid in locked and row.isSelected()))
        self.layers.blockSignals(False)
        self.geometry_box.setEnabled(len(selected) == 1)
        self.style_box.setEnabled(bool(selected))
        self.text_box.setVisible(bool(selected) and all(i.model.kind == "text" for i in selected))
        self.order.setEnabled(len(selected) == 1)
        kinds = {i.model.kind for i in selected}
        self.style_form.setRowVisible(self.colors["text_color"], "text" in kinds)
        self.style_form.setRowVisible(self.colors["fill"], bool(kinds & {"rectangle", "ellipse", "text"}))
        has_border = bool(kinds - {"group"})
        self.style_form.setRowVisible(self.colors["stroke"], has_border)
        self.style_form.setRowVisible(self.fields["stroke_width"], has_border)
        self.title.setText("Selecione um objeto" if not selected else
                           LABELS[selected[0].model.kind] if len(selected) == 1 else f"{len(selected)} objetos selecionados")
        if selected:
            m = selected[0].model
            for key, widget in self.fields.items():
                value = getattr(m, key)
                if isinstance(widget, QCheckBox):
                    widget.setChecked(value)
                else:
                    widget.setValue(value * 100 if key == "opacity" else value)
            self.ratio.setChecked(m.keep_ratio or m.kind == "group")
            self.ratio.setEnabled(m.kind != "group")
            self.font.setCurrentText(m.font_family)
            self.alignment.setCurrentIndex(self.alignment.findData(m.alignment))
            self.order.setMaximum(max(1, len(self.controller.document.items)))
            self.order.setValue(self.controller.document.items.index(m) + 1)
            for key, button in self.colors.items():
                color = QColor(getattr(m, key))
                button.setText("Transparente" if color.alpha() == 0 else color.name())
                button.setStyleSheet(f"border-left: 18px solid {color.name()};")
        self.refreshing = False

    def select_layers(self):
        if self.refreshing:
            return
        self.refreshing = True
        ids = {i.data(Qt.ItemDataRole.UserRole) for i in self.layers.selectedItems()}
        for uid, graphic in self.controller.scene.graphics.items():
            graphic.setSelected(uid in ids and not graphic.model.locked)
        self.refreshing = False
        self.refresh(False)
