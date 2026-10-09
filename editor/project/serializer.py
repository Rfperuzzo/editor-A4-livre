"""Formato JSON validado; escrita atômica; nunca executa conteúdo do projeto."""
from __future__ import annotations

import base64
import json
import math
import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QColor, QImageReader

from .models import Document, ItemModel

MAX_FILE = 100 * 1024 * 1024
MAX_IMAGE = 25 * 1024 * 1024
MAX_PIXELS = 40_000_000
KINDS = {"rectangle", "ellipse", "line", "arrow", "text", "image", "group"}


def image_bytes(encoded: str) -> bytes:
    if not isinstance(encoded, str) or len(encoded) > MAX_IMAGE * 1.34:
        raise ValueError("Imagem incorporada muito grande.")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("Imagem incorporada inválida.") from exc
    buffer = QBuffer()
    buffer.setData(QByteArray(data))
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buffer)
    size = reader.size()
    if bytes(reader.format()).lower() not in (b"png", b"jpeg", b"jpg"):
        raise ValueError("Utilize imagens PNG ou JPEG.")
    if not size.isValid() or size.width() * size.height() > MAX_PIXELS:
        raise ValueError("Imagem inválida ou acima de 40 megapixels.")
    if reader.read().isNull():
        raise ValueError("Não foi possível decodificar a imagem.")
    return data


def number(value: object, name: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Valor inválido: {name}.")
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"Valor fora do limite: {name}.")
    return float(value)


def parse_document(data: object) -> Document:
    """Valida toda a árvore antes de expor o documento à interface."""
    if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
        raise ValueError("Formato ou versão de projeto não suportado.")
    if data.get("orientation") not in ("portrait", "landscape"):
        raise ValueError("Orientação de página inválida.")
    ids: set[str] = set()

    def parse_item(raw: object, depth: int = 0) -> ItemModel:
        if depth > 20 or len(ids) >= 5000 or not isinstance(raw, dict):
            raise ValueError("Estrutura de objetos inválida ou muito complexa.")
        if not isinstance(raw.get("kind"), str) or raw["kind"] not in KINDS:
            raise ValueError("Tipo de objeto desconhecido.")
        uid = raw.get("id")
        if not isinstance(uid, str) or not 1 <= len(uid) <= 128 or uid in ids:
            raise ValueError("Identificador de objeto inválido ou duplicado.")
        ids.add(uid)
        m = ItemModel(kind=raw["kind"], id=uid)
        for name in ("x", "y", "rotation"):
            setattr(m, name, number(raw.get(name, getattr(m, name)), name, -100000, 100000))
        for name in ("width", "height"):
            setattr(m, name, number(raw.get(name), name, 0, 100000))
        if m.kind in ("line", "arrow"):
            if math.hypot(m.width, m.height) < .001:
                raise ValueError("Linha sem comprimento.")
        elif min(m.width, m.height) <= 0:
            raise ValueError("Objeto sem dimensões.")
        for name, bounds in {"opacity": (0, 1), "stroke_width": (0, 1000),
                             "font_size": (.01, 100000)}.items():
            setattr(m, name, number(raw.get(name, getattr(m, name)), name, *bounds))
        for name in ("locked", "keep_ratio", "bold", "italic", "underline", "flip_line", "reverse_line"):
            value = raw.get(name, getattr(m, name))
            if type(value) is not bool:
                raise ValueError(f"Valor inválido: {name}.")
            setattr(m, name, value)
        for name in ("fill", "stroke", "text_color"):
            value = raw.get(name, getattr(m, name))
            if not isinstance(value, str) or len(value) > 32 or not QColor(value).isValid():
                raise ValueError("Cor inválida.")
            setattr(m, name, value)
        for name, limit in (("text", 1_000_000), ("font_family", 200)):
            value = raw.get(name, getattr(m, name))
            if not isinstance(value, str) or len(value) > limit:
                raise ValueError(f"Conteúdo inválido: {name}.")
            setattr(m, name, value)
        m.alignment = raw.get("alignment", "left")
        if m.alignment not in ("left", "center", "right"):
            raise ValueError("Alinhamento inválido.")
        if m.kind == "image":
            m.image = raw.get("image", "")
            image_bytes(m.image)
        children = raw.get("children", [])
        if not isinstance(children, list) or (children and m.kind != "group"):
            raise ValueError("Grupo inválido.")
        m.children = [parse_item(c, depth + 1) for c in children]
        if m.kind == "group" and not m.children:
            raise ValueError("Grupo vazio.")
        return m

    items = data.get("items")
    if not isinstance(items, list):
        raise ValueError("Lista de objetos inválida.")
    for name in ("grid", "snap"):
        if type(data.get(name, False)) is not bool:
            raise ValueError("Configuração de página inválida.")
    return Document(orientation=data["orientation"], grid=data.get("grid", False),
                    snap=data.get("snap", False),
                    grid_size=number(data.get("grid_size", 5), "grade", 1, 50),
                    items=[parse_item(i) for i in items])


def load_project(path: str | Path) -> Document:
    path = Path(path)
    if path.stat().st_size > MAX_FILE:
        raise ValueError("Projeto acima do limite de 100 MB.")
    try:
        return parse_document(json.loads(path.read_text(encoding="utf-8")))
    except (RecursionError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("O arquivo não contém um projeto JSON válido.") from exc


def save_project(document: Document, path: str | Path) -> None:
    """Substitui o destino apenas após concluir a gravação do arquivo temporário."""
    path = Path(path)
    content = json.dumps(document.to_dict(), ensure_ascii=False, allow_nan=False, indent=2)
    if len(content.encode("utf-8")) > MAX_FILE:
        raise ValueError("Projeto acima do limite de 100 MB.")
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
