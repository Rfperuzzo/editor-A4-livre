"""Dados independentes da interface. Todas as distâncias estão em milímetros."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from uuid import uuid4

GEOMETRIC_KINDS = frozenset({"rectangle", "ellipse", "line", "arrow"})
TEXT_KINDS = GEOMETRIC_KINDS | {"text"}


def new_id() -> str:
    return uuid4().hex


@dataclass
class ItemModel:
    kind: str = "rectangle"
    id: str = field(default_factory=new_id)
    x: float = 20.0
    y: float = 20.0
    width: float = 40.0
    height: float = 30.0
    rotation: float = 0.0
    fill: str = "#ffdceafe"
    stroke: str = "#ff2563eb"
    stroke_width: float = 0.5
    opacity: float = 1.0
    locked: bool = False
    keep_ratio: bool = False
    text: str = "Texto"
    # Campo próprio: projetos antigos contêm "Texto" em todas as formas,
    # mas esse valor era ignorado. Mantê-lo separado evita rótulos inesperados.
    shape_text: str = ""
    font_family: str = "Arial"
    font_size: float = 12.0
    bold: bool = False
    italic: bool = False
    underline: bool = False
    text_color: str = "#ff172033"
    alignment: str = "left"
    vertical_alignment: str = "center"
    image: str = ""
    # A diagonal ascendente é necessária ao desenhar linhas de baixo para cima.
    flip_line: bool = False
    reverse_line: bool = False
    children: list[ItemModel] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Document:
    version: int = 1
    orientation: str = "portrait"
    grid: bool = False
    snap: bool = False
    grid_size: float = 5.0
    items: list[ItemModel] = field(default_factory=list)

    @property
    def page_size(self) -> tuple[float, float]:
        return (210.0, 297.0) if self.orientation == "portrait" else (297.0, 210.0)

    def to_dict(self) -> dict:
        return asdict(self)
