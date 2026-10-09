"""Objetos gráficos: pintura comum ao editor, ao PDF e à impressão."""
from __future__ import annotations

import base64
from math import atan2, cos, sin

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QKeySequence, QPainter,
                          QPainterPath, QPainterPathStroker, QPen, QPixmap, QPolygonF,
                          QTextCursor, QTextOption)
from PySide6.QtWidgets import QApplication, QGraphicsItem, QGraphicsObject, QGraphicsTextItem

from ..project.models import GEOMETRIC_KINDS, TEXT_KINDS, ItemModel

TEXT_SCALE = 25.4 / (72 * 4)


class TextEditor(QGraphicsTextItem):
    """Texto simples formatado por caixa; colagem nunca carrega recursos externos."""

    def __init__(self, owner: GraphicItem):
        super().__init__(owner)
        self.owner = owner
        self.setScale(TEXT_SCALE)
        self.document().setDocumentMargin(0)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setAcceptDrops(False)
        self.document().contentsChanged.connect(self.changed)
        self.document().documentLayout().documentSizeChanged.connect(self.reposition)
        self.updating = False

    def changed(self) -> None:
        if not self.updating:
            self.owner.model.text = self.toPlainText()
            if self.scene() and hasattr(self.scene(), "controller"):
                self.scene().controller.content_changed.emit()

    def reposition(self, size=None) -> None:
        """Mantém o texto da figura alinhado mesmo após mudar fonte ou quebra."""
        if self.owner.model.kind not in GEOMETRIC_KINDS:
            return
        rect = self.owner.text_rect()
        height = self.document().size().height() * TEXT_SCALE
        spare = max(0, rect.height() - height)
        alignment = self.owner.model.vertical_alignment
        offset = spare / 2 if alignment == "center" else spare if alignment == "bottom" else 0
        self.setPos(rect.left(), rect.top() + offset)

    def paint(self, painter, option, widget=None) -> None:
        painter.save()
        # A altura do QTextDocument não é limitada por setTextWidth.
        # Recortar explicitamente também atende rótulos de linhas horizontais.
        rect = self.mapRectFromParent(self.owner.text_rect())
        painter.setClipRect(rect, Qt.ClipOperation.IntersectClip)
        super().paint(painter, option, widget)
        painter.restore()

    def keyPressEvent(self, event) -> None:
        if event.matches(QKeySequence.StandardKey.Paste):
            self.textCursor().insertText(QApplication.clipboard().text())
            event.accept()
        elif event.key() == Qt.Key.Key_Escape:
            self.clearFocus()
            event.accept()
        else:
            super().keyPressEvent(event)

    def insertFromMimeData(self, source) -> None:
        self.textCursor().insertText(source.text())

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        if self.scene() and hasattr(self.scene(), "controller"):
            self.scene().controller.finish_text()


class GraphicItem(QGraphicsObject):
    """Representação de um modelo; transformações são sempre medidas em mm."""

    def __init__(self, model: ItemModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.text_editor: TextEditor | None = None
        self.pixmap = QPixmap()
        self.children_graphics: list[GraphicItem] = []
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, parent is None and not model.locked)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        if model.kind in TEXT_KINDS:
            if model.kind not in ("line", "arrow"):
                self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape)
            self.text_editor = TextEditor(self)
        elif model.kind == "image":
            self.pixmap.loadFromData(base64.b64decode(model.image))
        for index, child in enumerate(model.children):
            graphic = GraphicItem(child, self)
            graphic.setZValue(index)
            self.children_graphics.append(graphic)
        self.sync()

    def sync(self) -> None:
        self.prepareGeometryChange()
        m = self.model
        self.setPos(m.x, m.y)
        self.setRotation(m.rotation)
        self.setOpacity(m.opacity)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, self.parentItem() is None and not m.locked)
        if self.text_editor:
            text = self.text_editor
            text.updating = True
            content = m.text if m.kind == "text" else m.shape_text
            if text.toPlainText() != content:
                text.setPlainText(content)
            font = QFont(m.font_family)
            font.setPixelSize(max(1, round(m.font_size * 4)))
            font.setBold(m.bold)
            font.setItalic(m.italic)
            font.setUnderline(m.underline)
            text.setFont(font)
            text.setDefaultTextColor(QColor(m.text_color))
            rect = self.text_rect()
            text.setTextWidth(rect.width() / TEXT_SCALE)
            option = text.document().defaultTextOption()
            option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
            option.setAlignment({"left": Qt.AlignmentFlag.AlignLeft,
                                 "center": Qt.AlignmentFlag.AlignHCenter,
                                 "right": Qt.AlignmentFlag.AlignRight}[m.alignment])
            text.document().setDefaultTextOption(option)
            text.reposition()
            text.updating = False
        for graphic, child in zip(self.children_graphics, m.children):
            graphic.model = child
            graphic.sync()
        self.update()

    def boundingRect(self) -> QRectF:
        extra = max(.5, self.model.stroke_width / 2)
        rect = QRectF(0, 0, self.model.width, self.model.height).adjusted(-extra, -extra, extra, extra)
        if self.model.kind in ("line", "arrow") and self.model.shape_text:
            rect = rect.united(self.text_rect())
        return rect

    def text_rect(self) -> QRectF:
        """Área legível dentro da forma; rótulos de linhas ficam no seu centro."""
        m = self.model
        if m.kind in ("line", "arrow"):
            w, h = max(24, m.width), max(12, m.height)
            return QRectF((m.width-w)/2, (m.height-h)/2, w, h)
        if m.kind == "text":
            return QRectF(0, 0, m.width, m.height)
        # Retângulo inscrito na elipse evita cortar texto nas bordas curvas.
        factor = .7071067811865476 if m.kind == "ellipse" else 1
        w, h = m.width * factor, m.height * factor
        padding = min(2, w/4, h/4)
        return QRectF((m.width-w)/2 + padding, (m.height-h)/2 + padding,
                      max(.01, w-2*padding), max(.01, h-2*padding))

    def line_points(self) -> tuple[QPointF, QPointF]:
        m = self.model
        a, b = ((QPointF(0, m.height), QPointF(m.width, 0)) if m.flip_line else
                (QPointF(0, 0), QPointF(m.width, m.height)))
        return (b, a) if m.reverse_line else (a, b)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        m = self.model
        if m.kind in ("line", "arrow"):
            a, b = self.line_points()
            path.moveTo(a)
            path.lineTo(b)
            stroker = QPainterPathStroker()
            stroker.setWidth(max(2, m.stroke_width))
            outline = stroker.createStroke(path)
            if m.shape_text:
                outline.addRect(self.text_rect())
            return outline
        if m.kind == "ellipse":
            path.addEllipse(QRectF(0, 0, m.width, m.height))
        else:
            path.addRect(QRectF(0, 0, m.width, m.height))
        return path

    def paint(self, painter: QPainter, option, widget=None) -> None:
        m = self.model
        if m.kind == "group":
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(m.stroke), m.stroke_width)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen if m.stroke_width > 0 else Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(m.fill)))
        rect = QRectF(0, 0, m.width, m.height)
        if m.kind == "ellipse":
            painter.drawEllipse(rect)
        elif m.kind in ("rectangle", "text"):
            painter.drawRect(rect)
        elif m.kind in ("line", "arrow"):
            a, b = self.line_points()
            painter.drawLine(a, b)
            if m.kind == "arrow":
                angle = atan2(b.y() - a.y(), b.x() - a.x())
                length = min(max(2.5, m.stroke_width * 5), max(m.width, m.height) / 2)
                points = [b, b - QPointF(cos(angle - .45), sin(angle - .45)) * length,
                          b - QPointF(cos(angle + .45), sin(angle + .45)) * length]
                painter.setBrush(QColor(m.stroke))
                painter.drawPolygon(QPolygonF(points))
        elif m.kind == "image":
            painter.drawPixmap(rect, self.pixmap, QRectF(self.pixmap.rect()))
            if m.stroke_width:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(rect)

    def begin_text(self) -> None:
        if not self.text_editor or self.model.locked:
            return
        if self.model.kind in GEOMETRIC_KINDS:
            if self.parentItem() is None:
                self.scene().controller.item_editor_requested.emit(self.model.id)
            return
        self.scene().controller.begin_text(self)
        self.text_editor.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.text_editor.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.text_editor.setFocus(Qt.FocusReason.MouseFocusReason)
        cursor = self.text_editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.text_editor.setTextCursor(cursor)
