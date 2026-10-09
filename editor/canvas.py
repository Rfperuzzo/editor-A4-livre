"""Página, réguas e gestos de mouse. Decorações nunca fazem parte do documento."""
from __future__ import annotations

from copy import deepcopy
from math import atan2, degrees, floor

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from .geometry import HANDLES, local_to_page, resize, rotate
from .items.base_item import GraphicItem
from .project.models import ItemModel


class CanvasScene(QGraphicsScene):
    def __init__(self, controller):
        super().__init__(controller)
        self.controller = controller
        controller.scene = self
        self.graphics: dict[str, GraphicItem] = {}
        self.rebuild()

    def rebuild(self, selected=()) -> None:
        self.blockSignals(True)
        self.clear()
        self.graphics = {}
        w, h = self.controller.document.page_size
        self.setSceneRect(-30, -30, w + 60, h + 60)
        for index, m in enumerate(self.controller.document.items):
            graphic = GraphicItem(m)
            self.addItem(graphic)
            graphic.setZValue(index)
            self.graphics[m.id] = graphic
            if m.id in selected and not m.locked:
                graphic.setSelected(True)
        self.blockSignals(False)
        self.selectionChanged.emit()
        self.update()

    def drawBackground(self, painter, rect) -> None:
        painter.fillRect(rect, QColor("#e5e9ef"))
        w, h = self.controller.document.page_size
        page = QRectF(0, 0, w, h)
        painter.fillRect(page.translated(1.5, 1.5), QColor("#c7ced9"))
        painter.fillRect(page, QColor("white"))
        pen = QPen(QColor("#bcc5d3"), 0)
        painter.setPen(pen)
        painter.drawRect(page)
        doc = self.controller.document
        if doc.grid:
            painter.save()
            painter.setClipRect(page)
            painter.setPen(QPen(QColor("#e5eaf0"), 0))
            step = doc.grid_size
            for x in range(1, int(w / step) + 1):
                painter.drawLine(QPointF(x * step, 0), QPointF(x * step, h))
            for y in range(1, int(h / step) + 1):
                painter.drawLine(QPointF(0, y * step), QPointF(w, y * step))
            painter.restore()


class CanvasView(QGraphicsView):
    zoom_changed = Signal(int)
    tool_finished = Signal()

    def __init__(self, scene: CanvasScene):
        super().__init__(scene)
        self.controller = scene.controller
        self.tool = "select"
        self.zoom = 100
        self.mode = None
        self.preview = None
        self.before = None
        self.guides = []
        self.rubber = None
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing |
                            QPainter.RenderHint.SmoothPixmapTransform)
        self.setMouseTracking(True)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.set_zoom(100)
        scene.selectionChanged.connect(self.viewport().update)

    def set_zoom(self, percent: int) -> None:
        self.zoom = max(25, min(400, int(percent)))
        self.resetTransform()
        self.scale(96 / 25.4 * self.zoom / 100, 96 / 25.4 * self.zoom / 100)
        self.zoom_changed.emit(self.zoom)
        self.viewport().update()

    def fit_page(self) -> None:
        w, h = self.controller.document.page_size
        factor = min((self.viewport().width() - 70) / w, (self.viewport().height() - 70) / h)
        self.set_zoom(int(factor / (96 / 25.4) * 100))
        self.centerOn(w / 2, h / 2)

    def set_tool(self, tool: str) -> None:
        self.controller.finish_text()
        self.cancel_gesture()
        self.tool = tool
        self.viewport().setCursor(Qt.CursorShape.ArrowCursor if tool == "select" else Qt.CursorShape.CrossCursor)

    def handles(self, item: GraphicItem) -> list[QPointF]:
        return [QPointF(self.mapFromScene(item.mapToScene(QPointF(x * item.model.width, y * item.model.height))))
                for x, y in HANDLES]

    def rotation_handle(self, item: GraphicItem) -> QPointF:
        top = self.handles(item)[1]
        dx, dy = rotate(0, -28, item.model.rotation)
        return top + QPointF(dx, dy)

    def handle_at(self, point: QPointF):
        selected = self.controller.selected()
        if len(selected) != 1 or selected[0].model.locked:
            return None
        item = selected[0]
        positions = self.handles(item) + [self.rotation_handle(item)]
        index = min(range(len(positions)), key=lambda i: (point.x()-positions[i].x())**2 +
                    (point.y()-positions[i].y())**2)
        pos = positions[index]
        if abs(point.x() - pos.x()) <= 7 and abs(point.y() - pos.y()) <= 7:
            return item, index
        return None

    def hit(self, point: QPointF):
        for item in self.scene().items(point):
            while item.parentItem():
                item = item.parentItem()
            if isinstance(item, GraphicItem) and not item.model.locked:
                return item
        return None

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        p = self.mapToScene(event.position().toPoint())
        self.start = p
        active_text = self.controller.text_item
        if active_text and active_text.contains(active_text.mapFromScene(p)):
            super().mousePressEvent(event)
            return
        self.controller.finish_text()
        self.setFocus()
        if self.tool != "select":
            w, h = self.controller.document.page_size
            if not QRectF(0, 0, w, h).contains(p):
                return
            self.mode = "draw"
            kind = {"square": "rectangle", "circle": "ellipse"}.get(self.tool, self.tool)
            m = ItemModel(kind=kind, x=p.x(), y=p.y(), width=1, height=1)
            if kind == "text":
                m.fill, m.stroke_width = "#00000000", 0
            self.preview = GraphicItem(m)
            self.scene().addItem(self.preview)
            return
        handle = self.handle_at(event.position())
        if handle:
            self.active, self.handle_index = handle
            self.original = deepcopy(self.active.model)
            self.before = self.controller.snapshot()
            self.mode = "rotate" if self.handle_index == 8 else "resize"
            return
        item = self.hit(p)
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        if item:
            if ctrl:
                item.setSelected(not item.isSelected())
                if not item.isSelected():
                    return
            elif not item.isSelected():
                self.scene().clearSelection()
                item.setSelected(True)
            self.mode = "move"
            self.before = self.controller.snapshot()
            self.moving = [(i, i.model.x, i.model.y) for i in self.controller.selected()]
        else:
            self.prior_selection = {i.model.id for i in self.controller.selected()} if ctrl else set()
            if not ctrl:
                self.scene().clearSelection()
            self.mode = "rubber"
            self.rubber = QRectF(p, p)
        self.viewport().update()

    def snap_move(self, dx: float, dy: float) -> tuple[float, float]:
        self.guides = []
        doc = self.controller.document
        primary, ox, oy = self.moving[0]
        if doc.snap:
            step = doc.grid_size
            return round((ox + dx) / step) * step - ox, round((oy + dy) / step) * step - oy
        # Guias magnéticas em coordenadas físicas, com tolerância constante na tela.
        tolerance = 5 / self.transform().m11()
        bounds = primary.mapRectToScene(QRectF(0, 0, primary.model.width, primary.model.height))
        bounds.translate(ox + dx - primary.model.x, oy + dy - primary.model.y)
        moving_ids = {i.model.id for i, _, _ in self.moving}
        w, h = doc.page_size
        xs, ys = [0, w / 2, w], [0, h / 2, h]
        for i in self.scene().graphics.values():
            if i.model.id in moving_ids:
                continue
            r = i.mapRectToScene(QRectF(0, 0, i.model.width, i.model.height))
            xs.extend([r.left(), r.center().x(), r.right()])
            ys.extend([r.top(), r.center().y(), r.bottom()])
        best_x = min(((abs(t - x), t - x, t) for t in xs
                      for x in (bounds.left(), bounds.center().x(), bounds.right())), key=lambda v: v[0])
        best_y = min(((abs(t - y), t - y, t) for t in ys
                      for y in (bounds.top(), bounds.center().y(), bounds.bottom())), key=lambda v: v[0])
        if best_x[0] < tolerance:
            dx += best_x[1]
            self.guides.append(("x", best_x[2]))
        if best_y[0] < tolerance:
            dy += best_y[1]
            self.guides.append(("y", best_y[2]))
        return dx, dy

    def mouseMoveEvent(self, event) -> None:
        p = self.mapToScene(event.position().toPoint())
        if not self.mode:
            self.viewport().setCursor(Qt.CursorShape.CrossCursor if self.tool != "select" or self.handle_at(event.position())
                                      else Qt.CursorShape.ArrowCursor)
            super().mouseMoveEvent(event)
            return
        if self.mode == "draw":
            m = self.preview.model
            dx, dy = p.x() - self.start.x(), p.y() - self.start.y()
            if self.tool in ("square", "circle") or event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                size = max(abs(dx), abs(dy))
                dx, dy = size * (-1 if dx < 0 else 1), size * (-1 if dy < 0 else 1)
            m.x, m.y = self.start.x() + min(0, dx), self.start.y() + min(0, dy)
            minimum = 0 if m.kind in ("line", "arrow") else 1
            m.width, m.height = max(minimum, abs(dx)), max(minimum, abs(dy))
            m.flip_line = dx * dy < 0
            m.reverse_line = dx < 0 or (dx == 0 and dy < 0)
            self.preview.sync()
        elif self.mode == "resize":
            if self.controller.document.snap:
                step = self.controller.document.grid_size
                p = QPointF(round(p.x() / step) * step, round(p.y() / step) * step)
            model = resize(self.original, self.handle_index, p.x(), p.y(),
                           bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier))
            self.active.model.__dict__.update(model.__dict__)
            self.active.sync()
        elif self.mode == "rotate":
            m = self.original
            cx, cy = local_to_page(m, m.width / 2, m.height / 2)
            initial = atan2(self.start.y() - cy, self.start.x() - cx)
            angle = m.rotation + degrees(atan2(p.y() - cy, p.x() - cx) - initial)
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                angle = round(angle / 15) * 15
            dx, dy = rotate(m.width / 2, m.height / 2, angle)
            self.active.model.rotation = angle % 360
            self.active.model.x, self.active.model.y = cx - dx, cy - dy
            self.active.sync()
        elif self.mode == "move":
            dx, dy = self.snap_move(p.x() - self.start.x(), p.y() - self.start.y())
            for item, x, y in self.moving:
                item.model.x, item.model.y = x + dx, y + dy
                item.sync()
        elif self.mode == "rubber":
            self.rubber = QRectF(self.start, p).normalized()
            for item in self.scene().graphics.values():
                if not item.model.locked:
                    item.setSelected(item.model.id in self.prior_selection or self.rubber.intersects(item.sceneBoundingRect()))
        self.viewport().update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton or not self.mode:
            super().mouseReleaseEvent(event)
            return
        mode, self.mode = self.mode, None
        if mode == "draw":
            m = self.preview.model
            self.scene().removeItem(self.preview)
            self.preview = None
            if m.width <= 1 and m.height <= 1:
                m.width, m.height = (55, 18) if m.kind == "text" else (30, 30)
            self.controller.add(m)
            self.tool = "select"
            self.tool_finished.emit()
            if m.kind == "text":
                self.scene().graphics[m.id].begin_text()
        elif mode in ("move", "resize", "rotate"):
            self.controller.record(self.before, {"move": "Move objetos", "resize": "Redimensiona objeto",
                                                  "rotate": "Rotaciona objeto"}[mode])
        self.before = None
        self.rubber = None
        self.guides = []
        self.viewport().update()

    def mouseDoubleClickEvent(self, event) -> None:
        item = self.hit(self.mapToScene(event.position().toPoint()))
        if item and item.text_editor:
            self.mode = None
            item.begin_text()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def cancel_gesture(self) -> None:
        if self.preview:
            self.scene().removeItem(self.preview)
            self.preview = None
        if self.before:
            self.controller.restore(self.before)
        self.before = None
        self.mode = None
        self.rubber = None
        self.guides = []
        self.viewport().update()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape and not self.controller.text_item:
            self.cancel_gesture()
            self.set_tool("select")
            self.tool_finished.emit()
            return
        directions = {Qt.Key.Key_Left: (-1, 0), Qt.Key.Key_Right: (1, 0),
                      Qt.Key.Key_Up: (0, -1), Qt.Key.Key_Down: (0, 1)}
        if event.key() in directions and not self.controller.text_item:
            dx, dy = directions[event.key()]
            step = 10 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
            models = [i.model for i in self.controller.selected()]

            def move():
                for m in models:
                    m.x += dx * step
                    m.y += dy * step
            self.controller.mutate("Move objetos", move)
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.set_zoom(self.zoom + (10 if event.angleDelta().y() > 0 else -10))
            event.accept()
        else:
            super().wheelEvent(event)

    def drawForeground(self, painter, rect) -> None:
        painter.save()
        painter.resetTransform()
        painter.setPen(QPen(QColor("#2563eb"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        selected = self.controller.selected()
        for item in selected:
            points = self.handles(item)
            painter.drawPolygon(QPolygonF([points[i] for i in (0, 2, 4, 6)]))
            if len(selected) == 1:
                painter.setBrush(QColor("white"))
                for p in points:
                    painter.drawRect(QRectF(p.x() - 4, p.y() - 4, 8, 8))
                rp = self.rotation_handle(item)
                painter.drawLine(points[1], rp)
                painter.drawEllipse(rp, 5, 5)
                painter.setBrush(Qt.BrushStyle.NoBrush)
        if self.rubber:
            painter.setBrush(QColor(37, 99, 235, 30))
            painter.drawRect(QRectF(self.mapFromScene(self.rubber.topLeft()), self.mapFromScene(self.rubber.bottomRight())))
        painter.setPen(QPen(QColor("#db2777"), 1, Qt.PenStyle.DashLine))
        w, h = self.controller.document.page_size
        for axis, v in self.guides:
            a, b = (QPointF(v, 0), QPointF(v, h)) if axis == "x" else (QPointF(0, v), QPointF(w, v))
            painter.drawLine(self.mapFromScene(a), self.mapFromScene(b))
        self.draw_rulers(painter)
        painter.restore()

    def draw_rulers(self, painter: QPainter) -> None:
        width, height = self.viewport().width(), self.viewport().height()
        painter.fillRect(0, 0, width, 22, QColor("#f8fafc"))
        painter.fillRect(0, 0, 22, height, QColor("#f8fafc"))
        painter.setPen(QColor("#64748b"))
        font = QFont("Segoe UI")
        font.setPixelSize(10)
        painter.setFont(font)
        w, h = self.controller.document.page_size
        step = 10 if self.zoom < 50 else 5 if self.zoom < 150 else 1
        for x in range(0, int(w) + 1, step):
            px = self.mapFromScene(QPointF(x, 0)).x()
            if px < 23 or px > width:
                continue
            painter.drawLine(px, 22, px, 14 if x % 10 == 0 else 18)
            if x % 10 == 0:
                painter.drawText(px + 2, 10, str(x // 10))
        for y in range(0, int(h) + 1, step):
            py = self.mapFromScene(QPointF(0, y)).y()
            if py < 23 or py > height:
                continue
            painter.drawLine(22, py, 14 if y % 10 == 0 else 18, py)
            if y % 10 == 0:
                painter.drawText(1, py - 2, str(y // 10))
        painter.fillRect(0, 0, 22, 22, QColor("#e9eef5"))
        painter.drawText(2, 14, "cm")
