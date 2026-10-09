import base64

import pymupdf
import pytest
from pypdf import PdfReader
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QColor, QImage

from editor.export.pdf_exporter import export_pdf
from editor.project.models import Document, ItemModel
from editor.project.serializer import load_project, save_project


@pytest.mark.parametrize("orientation,size", [("portrait", (210, 297)), ("landscape", (297, 210))])
def test_pdf_a4_vector_geometry_and_text(qapp, tmp_path, orientation, size):
    doc = Document(orientation=orientation, grid=True, snap=True, items=[
        ItemModel(x=20, y=30, width=40, height=25, fill="#ffdc2626", stroke_width=0),
        ItemModel(kind="text", x=25, y=80, width=130, height=30, text="Editor A4 Livre",
                  font_size=18, fill="#00000000", stroke_width=0),
    ])
    path = tmp_path / "test.pdf"
    export_pdf(doc, path)
    pdf = PdfReader(path)
    assert len(pdf.pages) == 1
    page = pdf.pages[0]
    assert (float(page.mediabox.width), float(page.mediabox.height)) == pytest.approx(
        [mm * 72 / 25.4 for mm in size], abs=.1)
    assert len(page.images) == 0  # Sem screenshot da folha.
    with pymupdf.open(path) as rendered:
        p = rendered[0]
        drawings = p.get_drawings()
        red = [d for d in drawings if d["fill"] and d["fill"][0] > .8 and d["fill"][1] < .3]
        assert len(red) == 1
        r = red[0]["rect"]
        assert tuple(r) == pytest.approx([v * 72 / 25.4 for v in (20, 30, 60, 55)], abs=.1)
        assert "Editor A4 Livre" in p.get_text()
        spans = [s for b in p.get_text("dict")["blocks"] if "lines" in b for l in b["lines"] for s in l["spans"]]
        assert spans[0]["size"] == pytest.approx(18, abs=.1)
        # Fundo branco, nenhuma grade, mesmo com grid=True no documento.
        pix = p.get_pixmap(matrix=pymupdf.Matrix(1, 1), alpha=False)
        assert pix.pixel(100, 100)[:3] == (220, 38, 38)
        assert pix.pixel(15, 15)[:3] == (255, 255, 255)


def test_end_to_end_group_image_roundtrip_pdf(editor, tmp_path):
    c, scene, view = editor
    c.add(ItemModel(x=20, y=20, width=50, height=30, rotation=15))
    c.add(ItemModel(kind="text", x=25, y=25, width=50, height=20, text="Olá A4", fill="#00000000", stroke_width=0))
    for item in scene.graphics.values(): item.setSelected(True)
    c.group()
    c.set_property("rotation", 30)
    c.set_property("width", 90)
    image = QImage(16, 16, QImage.Format.Format_RGB32)
    image.fill(QColor("#2563eb"))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    c.add(ItemModel(kind="image", x=100, y=100, width=20, height=20,
                    image=base64.b64encode(bytes(buffer.data())).decode(), stroke_width=0))
    path = tmp_path / "roundtrip.a4livre"
    save_project(c.document, path)
    reopened = load_project(path)
    assert reopened == c.document
    c.replace(reopened)
    pdf = tmp_path / "roundtrip.pdf"
    export_pdf(c.document, pdf)
    assert len(PdfReader(pdf).pages[0].images) == 1
    with pymupdf.open(pdf) as output:
        assert "Olá A4" in output[0].get_text()


def test_pdf_does_not_modify_live_selection(editor, tmp_path):
    c, scene, view = editor
    m = ItemModel()
    c.add(m)
    view.set_zoom(400)
    before = c.snapshot()
    export_pdf(c.document, tmp_path / "output.pdf")
    assert c.document == before
    assert scene.graphics[m.id].isSelected()
    assert view.zoom == 400
