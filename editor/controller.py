"""Transações de edição e coordenação entre documento, cena e histórico."""
from __future__ import annotations

import base64
import json
from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QMimeData, QObject, QRectF, Signal
from PySide6.QtGui import QImage, QUndoStack
from PySide6.QtWidgets import QApplication

from .commands.undo_commands import DocumentCommand
from .geometry import rotate, scale_children
from .items.base_item import GraphicItem
from .project.models import Document, ItemModel, new_id
from .project.serializer import MAX_FILE, MAX_IMAGE, image_bytes, parse_document

MIME = "application/x-editor-a4-livre+json"


class Controller(QObject):
    changed = Signal()
    content_changed = Signal()
    item_editor_requested = Signal(str)

    # Somente estas propriedades podem ser alteradas pelo editor de uma figura.
    FIGURE_FIELDS = ("shape_text", "font_family", "font_size", "bold", "italic", "underline",
                     "alignment", "vertical_alignment", "text_color", "fill", "stroke")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.document = Document()
        self.scene = None
        self.stack = QUndoStack(self)
        self.stack.setUndoLimit(150)
        self.text_before = None
        self.text_item = None

    def selected(self) -> list[GraphicItem]:
        return sorted([i for i in self.scene.selectedItems() if isinstance(i, GraphicItem)
                       and i.parentItem() is None], key=lambda i: i.zValue())

    def snapshot(self) -> Document:
        return deepcopy(self.document)

    def restore(self, document: Document, selected=()) -> None:
        self.document = deepcopy(document)
        self.scene.rebuild(selected)
        self.changed.emit()

    def record(self, before: Document, label: str, before_selected=None) -> None:
        if before != self.document:
            after_selected = [i.model.id for i in self.selected()]
            self.stack.push(DocumentCommand(self, before, self.document, label,
                                            after_selected if before_selected is None else before_selected,
                                            after_selected))
            self.changed.emit()

    def mutate(self, label: str, callback, selected=None) -> None:
        self.finish_text()
        before = self.snapshot()
        before_selected = [i.model.id for i in self.selected()]
        ids = selected if selected is not None else before_selected
        callback()
        self.scene.rebuild(ids)
        self.record(before, label, before_selected)

    def replace(self, document: Document) -> None:
        self.finish_text()
        self.document = document
        self.stack.clear()
        self.scene.rebuild()
        self.stack.setClean()
        self.changed.emit()

    def add(self, model: ItemModel) -> None:
        self.mutate("Insere objeto", lambda: self.document.items.append(model), [model.id])

    def edit_figure(self, uid: str, draft: ItemModel) -> None:
        """Aplica uma edição exclusivamente ao ID aberto, em uma ação de histórico."""
        model = next((m for m in self.document.items if m.id == uid), None)
        if model is None or model.locked or model.kind != draft.kind:
            return

        def change():
            for name in self.FIGURE_FIELDS:
                setattr(model, name, getattr(draft, name))
        self.mutate("Edita texto e cores da figura", change, [uid])

    def begin_text(self, item: GraphicItem) -> None:
        self.finish_text()
        self.text_before = self.snapshot()
        self.text_item = item

    def finish_text(self) -> None:
        if self.text_before is None:
            return
        before, self.text_before = self.text_before, None
        item, self.text_item = self.text_item, None
        if item and item.text_editor:
            item.text_editor.clearFocus()
        self.record(before, "Edita texto")

    def delete(self) -> None:
        ids = {i.model.id for i in self.selected() if not i.model.locked}
        self.mutate("Exclui objetos", lambda: setattr(self.document, "items",
                    [m for m in self.document.items if m.id not in ids]), [])

    def copy(self) -> bool:
        items = self.selected()
        if not items:
            return False
        data = Document(items=[deepcopy(i.model) for i in items]).to_dict()
        mime = QMimeData()
        mime.setData(MIME, json.dumps(data, ensure_ascii=False).encode("utf-8"))
        QApplication.clipboard().setMimeData(mime)
        return True

    def paste(self) -> None:
        mime = QApplication.clipboard().mimeData()
        if not mime.hasFormat(MIME):
            return
        raw = bytes(mime.data(MIME))
        if len(raw) > MAX_FILE:
            raise ValueError("Conteúdo da área de transferência muito grande.")
        try:
            doc = parse_document(json.loads(raw))
        except (UnicodeError, RecursionError, json.JSONDecodeError) as exc:
            raise ValueError("Conteúdo inválido na área de transferência.") from exc
        self.insert_copies(doc.items)

    def insert_copies(self, items: list[ItemModel]) -> None:
        copies = deepcopy(items)

        def renew(m):
            m.id = new_id()
            for child in m.children:
                renew(child)

        for m in copies:
            renew(m)
            m.x += 5
            m.y += 5
            m.locked = False
        self.mutate("Duplica objetos", lambda: self.document.items.extend(copies), [m.id for m in copies])

    def duplicate(self) -> None:
        self.insert_copies([i.model for i in self.selected()])

    def set_property(self, name: str, value) -> None:
        models = [i.model for i in self.selected() if not i.model.locked or name == "locked"]

        def change():
            for m in models:
                if name == "rotation":
                    dx, dy = rotate(m.width / 2, m.height / 2, m.rotation)
                    nx, ny = rotate(m.width / 2, m.height / 2, value)
                    m.x += dx - nx
                    m.y += dy - ny
                    m.rotation = value
                elif name in ("width", "height") and (m.kind == "group" or m.keep_ratio) and getattr(m, name) > 0:
                    factor = value / max(.001, getattr(m, name))
                    m.width *= factor
                    m.height *= factor
                    if m.kind == "group":
                        scale_children(m, factor)
                else:
                    setattr(m, name, value)
        self.mutate("Altera propriedade", change)

    def set_page(self, name: str, value) -> None:
        self.mutate("Configura página", lambda: setattr(self.document, name, value))

    def group(self) -> None:
        items = [i for i in self.selected() if not i.model.locked]
        if len(items) < 2:
            return
        bounds = items[0].mapRectToScene(QRectF(0, 0, items[0].model.width, items[0].model.height))
        for i in items[1:]:
            bounds = bounds.united(i.mapRectToScene(QRectF(0, 0, i.model.width, i.model.height)))
        models = [i.model for i in items]
        group = ItemModel(kind="group", x=bounds.x(), y=bounds.y(), width=max(1, bounds.width()),
                          height=max(1, bounds.height()), fill="#00000000", stroke_width=0,
                          keep_ratio=True, children=models)

        def change():
            ids = {m.id for m in models}
            top = max(self.document.items.index(m) for m in models)
            remaining_before = sum(m.id not in ids for m in self.document.items[:top])
            self.document.items = [m for m in self.document.items if m.id not in ids]
            for m in models:
                m.x -= group.x
                m.y -= group.y
            self.document.items.insert(remaining_before, group)
        self.mutate("Agrupa objetos", change, [group.id])

    def ungroup(self) -> None:
        groups = [i.model for i in self.selected() if i.model.kind == "group" and not i.model.locked]
        ids = []

        def change():
            for g in groups:
                index = self.document.items.index(g)
                self.document.items.remove(g)
                for offset, child in enumerate(g.children):
                    dx, dy = rotate(child.x, child.y, g.rotation)
                    child.x, child.y = g.x + dx, g.y + dy
                    child.rotation += g.rotation
                    child.opacity *= g.opacity
                    self.document.items.insert(index + offset, child)
                    ids.append(child.id)
        self.mutate("Desagrupa objetos", change, ids)

    def layer(self, direction: str) -> None:
        ids = {i.model.id for i in self.selected() if not i.model.locked}

        def change():
            selected = [m for m in self.document.items if m.id in ids]
            others = [m for m in self.document.items if m.id not in ids]
            self.document.items = others + selected if direction == "front" else selected + others
        self.mutate("Ordena camadas", change)

    def reorder(self, index: int) -> None:
        selected = self.selected()
        if len(selected) != 1 or selected[0].model.locked:
            return
        m = selected[0].model

        def change():
            self.document.items.remove(m)
            self.document.items.insert(max(0, min(index, len(self.document.items))), m)
        self.mutate("Ordena camada", change)

    def align(self, mode: str) -> None:
        items = [i for i in self.selected() if not i.model.locked]
        if len(items) < 2:
            return
        pairs = [(i.model, i.mapRectToScene(QRectF(0, 0, i.model.width, i.model.height))) for i in items]
        union = QRectF(pairs[0][1])
        for _, r in pairs[1:]:
            union = union.united(r)

        def change():
            if mode in ("distribute_x", "distribute_y"):
                if len(pairs) < 3:
                    return
                horizontal = mode == "distribute_x"
                ordered = sorted(pairs, key=lambda p: p[1].center().x() if horizontal else p[1].center().y())
                coords = [r.center().x() if horizontal else r.center().y() for _, r in ordered]
                step = (coords[-1] - coords[0]) / (len(coords) - 1)
                for index, (m, r) in enumerate(ordered[1:-1], 1):
                    if horizontal:
                        m.x += coords[0] + index * step - r.center().x()
                    else:
                        m.y += coords[0] + index * step - r.center().y()
            else:
                for m, r in pairs:
                    if mode == "left": m.x += union.left() - r.left()
                    elif mode == "right": m.x += union.right() - r.right()
                    elif mode == "top": m.y += union.top() - r.top()
                    elif mode == "bottom": m.y += union.bottom() - r.bottom()
                    elif mode == "center_x": m.x += union.center().x() - r.center().x()
                    elif mode == "center_y": m.y += union.center().y() - r.center().y()
        self.mutate("Alinha objetos", change)

    def toggle_lock(self, uid: str) -> None:
        m = next((m for m in self.document.items if m.id == uid), None)
        if m:
            self.mutate("Bloqueia/desbloqueia", lambda: setattr(m, "locked", not m.locked), [uid])

    def import_image(self, path: str) -> None:
        if Path(path).stat().st_size > MAX_IMAGE:
            raise ValueError("Imagem acima do limite de 25 MB.")
        encoded = base64.b64encode(Path(path).read_bytes()).decode("ascii")
        data = image_bytes(encoded)
        image = QImage.fromData(data)
        w = min(100, image.width() * 25.4 / 96)
        h = w * image.height() / image.width()
        if h > 150:
            w *= 150 / h
            h = 150
        self.add(ItemModel(kind="image", image=encoded, width=w, height=h,
                           keep_ratio=True, fill="#00000000", stroke_width=0))
