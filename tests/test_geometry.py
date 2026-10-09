import math
import pytest

from editor.geometry import HANDLES, local_to_page, resize
from editor.project.models import ItemModel


@pytest.mark.parametrize("angle", [0, 45, 90, 270])
@pytest.mark.parametrize("handle", range(8))
def test_resize_preserves_opposite_anchor(angle, handle):
    m = ItemModel(x=31, y=49, width=40, height=30, rotation=angle)
    hx, hy = HANDLES[handle]
    anchor = local_to_page(m, (1-hx)*m.width, (1-hy)*m.height)
    target = local_to_page(m, hx*40 + (10 if hx == 1 else -10 if hx == 0 else 0),
                           hy*30 + (8 if hy == 1 else -8 if hy == 0 else 0))
    n = resize(m, handle, *target)
    assert local_to_page(n, (1-hx)*n.width, (1-hy)*n.height) == pytest.approx(anchor)
    assert n.width == pytest.approx(40 if hx == .5 else 50)
    assert n.height == pytest.approx(30 if hy == .5 else 38)


def test_square_becomes_rectangle_and_shift_keeps_ratio():
    square = ItemModel(width=30, height=30)
    assert resize(square, 3, 70, 35).width == 50
    assert resize(square, 3, 70, 35).height == 30
    shifted = resize(square, 4, 80, 60, True)
    assert shifted.width == shifted.height


def test_minimum_and_horizontal_line():
    m = ItemModel()
    assert resize(m, 0, 200, 200).width == 1
    line = ItemModel(kind="line", width=30, height=0)
    changed = resize(line, 3, 60, 20)
    assert changed.height == 0 and math.hypot(changed.width, changed.height) >= 1


def test_shift_on_horizontal_line_preserves_zero_height():
    line = ItemModel(kind="line", width=30, height=0)
    changed = resize(line, 3, 60, 20, True)
    assert changed.width == 40 and changed.height == 0
