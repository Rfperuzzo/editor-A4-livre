"""Gera evidências visuais reproduzíveis com o próprio aplicativo.

Uso: python scripts/visual_check.py CAMINHO_DE_SAIDA
"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from editor.export.pdf_exporter import export_pdf
from editor.main_window import MainWindow
from editor.project.models import Document, ItemModel
from editor.project.serializer import save_project


def example() -> Document:
    def text(x, y, w, h, value, size=12, color="#ff172033", **kwargs):
        return ItemModel(kind="text", x=x, y=y, width=w, height=h, text=value,
                         font_size=size, text_color=color, fill="#00000000", stroke_width=0, **kwargs)
    image = QImage(360, 220, QImage.Format.Format_RGB32)
    image.fill(QColor("#dbeafe"))
    painter = QPainter(image)
    painter.setBrush(QColor("#2563eb"))
    painter.setPen(QColor("#2563eb"))
    painter.drawEllipse(85, 20, 180, 180)
    painter.setBrush(QColor("#fbbf24"))
    painter.setPen(QColor("#fbbf24"))
    painter.drawEllipse(210, 80, 100, 100)
    painter.end()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return Document(grid=True, items=[
        ItemModel(x=16, y=18, width=8, height=8, fill="#ff2563eb", stroke_width=0),
        text(29, 17, 155, 12, "EDITOR A4 LIVRE", 22, bold=True),
        text(16, 35, 180, 14, "Sua página. Suas ideias.\nUm espaço livre para criar, com medidas precisas.", 11),
        ItemModel(kind="line", x=16, y=54, width=178, height=0, stroke="#ff94a3b8", stroke_width=.3),
        ItemModel(x=16, y=65, width=82, height=65, fill="#ffeff6ff", stroke="#ff93c5fd", stroke_width=.5),
        text(23, 72, 70, 12, "01  DESENHE", 14, "#ff1d4ed8", bold=True),
        text(23, 89, 66, 32, "Formas independentes.\nTexto em qualquer posição.\nAlças que respeitam o zoom.", 11),
        ItemModel(kind="image", x=108, y=65, width=86, height=52.55,
                  image=base64.b64encode(bytes(buffer.data())).decode(), keep_ratio=True, stroke_width=0),
        text(108, 122, 90, 12, "Imagem incorporada ao projeto", 9, "#ff64748b"),
        ItemModel(kind="ellipse", x=25, y=151, width=52, height=36, fill="#ffccfbf1", stroke="#ff0d9488", stroke_width=.7),
        text(31, 162, 45, 15, "FORMAS", 13, "#ff0f766e", bold=True),
        ItemModel(kind="arrow", x=88, y=170, width=28, height=0, stroke="#ff2563eb", stroke_width=1),
        ItemModel(x=127, y=153, width=57, height=38, rotation=-10, fill="#fffee2e2", stroke="#ffef4444", stroke_width=.6),
        text(134, 162, 50, 12, "ROTAÇÃO", 13, "#ffb91c1c", rotation=-10, bold=True),
        text(16, 211, 178, 13, "PRONTO PARA SALVAR E IMPRIMIR", 15, bold=True),
        text(16, 230, 178, 27, "O projeto .a4livre preserva seus objetos editáveis.\nO PDF mantém o tamanho A4 e as formas vetoriais.\nTudo funciona offline, no seu computador.", 11),
        ItemModel(kind="line", x=16, y=272, width=178, height=0, stroke="#ffcbd5e1", stroke_width=.3),
        text(16, 277, 180, 10, "A4 210 × 297 mm   •   Página de demonstração", 9, "#ff64748b"),
    ])


def main():
    output = Path(sys.argv[1])
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    window = MainWindow()
    window.resize(1440, 1000)
    window.show()
    doc = example()
    window.controller.replace(doc)
    app.processEvents()
    window.view.fit_page()
    app.processEvents()
    window.scene.graphics[doc.items[12].id].setSelected(True)
    app.processEvents()
    window.grab().save(str(output / "interface.png"))
    save_project(doc, output / "demonstracao.a4livre")
    export_pdf(doc, output / "demonstracao.pdf")
    window.controller.stack.setClean()
    window.close()


if __name__ == "__main__":
    main()
