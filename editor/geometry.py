"""Geometria pura usada pelas alças e pelos testes de precisão."""
from __future__ import annotations

from copy import deepcopy
from math import cos, radians, sin

from .project.models import ItemModel

HANDLES = ((0, 0), (.5, 0), (1, 0), (1, .5), (1, 1), (.5, 1), (0, 1), (0, .5))


def rotate(x: float, y: float, angle: float) -> tuple[float, float]:
    a = radians(angle)
    return x * cos(a) - y * sin(a), x * sin(a) + y * cos(a)


def local_to_page(m: ItemModel, x: float, y: float) -> tuple[float, float]:
    dx, dy = rotate(x, y, m.rotation)
    return m.x + dx, m.y + dy


def resize(m: ItemModel, handle: int, page_x: float, page_y: float,
           proportional: bool = False) -> ItemModel:
    """Redimensiona sem cruzar a âncora oposta, inclusive com rotação."""
    result = deepcopy(m)
    hx, hy = HANDLES[handle]
    ax, ay = 1 - hx, 1 - hy
    anchor_x, anchor_y = local_to_page(m, ax * m.width, ay * m.height)
    dx, dy = rotate(page_x - anchor_x, page_y - anchor_y, -m.rotation)
    minimum = 0.0 if m.kind in ("line", "arrow") else 1.0
    w = max(minimum, dx * (1 if hx == 1 else -1)) if hx != .5 else m.width
    h = max(minimum, dy * (1 if hy == 1 else -1)) if hy != .5 else m.height
    if proportional or m.keep_ratio or m.kind == "group":
        rw, rh = w / max(m.width, .001), h / max(m.height, .001)
        factor = rh if hx == .5 or m.width == 0 else rw if hy == .5 or m.height == 0 else max(rw, rh)
        denominator = max(m.width, m.height) if m.kind in ("line", "arrow") else min(m.width, m.height)
        factor = max(factor, 1 / max(.001, denominator))
        w, h = m.width * factor, m.height * factor
    if m.kind in ("line", "arrow") and w * w + h * h < 1:
        if hx != .5:
            w = 1
        else:
            h = 1
    result.width, result.height = w, h
    dx, dy = rotate(ax * w, ay * h, m.rotation)
    result.x, result.y = anchor_x - dx, anchor_y - dy
    if m.kind == "group":
        scale_children(result, w / m.width)
    return result


def scale_children(group: ItemModel, factor: float) -> None:
    """Escala uniforme de grupos, preservando a aparência relativa dos filhos."""
    for child in group.children:
        child.x *= factor
        child.y *= factor
        child.width *= factor
        child.height *= factor
        child.stroke_width *= factor
        child.font_size *= factor
        scale_children(child, factor)
