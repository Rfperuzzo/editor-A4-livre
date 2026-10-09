"""Renderização vetorial independente das decorações e do zoom do editor."""
from __future__ import annotations

import os
import tempfile
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import RectangleObject

from PySide6.QtCore import QMarginsF, QRectF, Qt
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter
from PySide6.QtWidgets import QGraphicsScene

from ..items.base_item import GraphicItem
from ..project.models import Document


def configure_page(device, document: Document) -> None:
    orientation = (QPageLayout.Orientation.Portrait if document.orientation == "portrait"
                   else QPageLayout.Orientation.Landscape)
    device.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), orientation,
                                     QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter))


def render_document(document: Document, painter: QPainter, target: QRectF) -> None:
    """Desenha uma cena limpa em qualquer QPaintDevice com a mesma geometria."""
    scene = QGraphicsScene()
    w, h = document.page_size
    source = QRectF(0, 0, w, h)
    scene.setSceneRect(source)
    for index, model in enumerate(document.items):
        item = GraphicItem(model)
        scene.addItem(item)
        item.setZValue(index)
    painter.save()
    painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing |
                           QPainter.RenderHint.SmoothPixmapTransform)
    painter.setClipRect(target)
    scene.render(painter, target, source, Qt.AspectRatioMode.IgnoreAspectRatio)
    painter.restore()


def export_pdf(document: Document, path: str | Path) -> None:
    """PDF A4 em tamanho real, publicado atomicamente após finalizar o painter."""
    path = Path(path)
    fd, temp = tempfile.mkstemp(dir=path.parent, suffix=".pdf")
    os.close(fd)
    try:
        writer = QPdfWriter(temp)
        writer.setResolution(1200)
        writer.setTitle("Editor A4 Livre")
        writer.setCreator("Editor A4 Livre")
        configure_page(writer, document)
        painter = QPainter()
        if not painter.begin(writer):
            raise OSError("Não foi possível iniciar a exportação PDF.")
        try:
            w, h = document.page_size
            render_document(document, painter, QRectF(0, 0, w * 1200 / 25.4, h * 1200 / 25.4))
        finally:
            ended = painter.end()
        del writer
        if not ended or Path(temp).stat().st_size == 0:
            raise OSError("Falha ao finalizar o PDF.")
        # O backend PDF do Qt arredonda o MediaBox a pontos inteiros (595 × 842).
        # Corrigir apenas a caixa física e a origem superior, sem rasterizar nem
        # escalar o conteúdo, mantém as medidas exatas também na borda da folha.
        pdf = PdfReader(BytesIO(Path(temp).read_bytes()))
        normalized = PdfWriter()
        page = normalized.add_page(pdf.pages[0])
        width_pt, height_pt = w * 72 / 25.4, h * 72 / 25.4
        page.add_transformation(Transformation().translate(0, height_pt - float(page.mediabox.height)))
        page.mediabox = RectangleObject((0, 0, width_pt, height_pt))
        page.cropbox = RectangleObject((0, 0, width_pt, height_pt))
        normalized.add_metadata({"/Title": "Editor A4 Livre", "/Creator": "Editor A4 Livre"})
        normalized.write(temp)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
