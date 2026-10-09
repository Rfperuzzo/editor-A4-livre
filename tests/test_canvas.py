import pytest
from PySide6.QtCore import QPointF, Qt

from editor.geometry import HANDLES, local_to_page
from editor.project.models import ItemModel


@pytest.mark.parametrize("zoom", [25, 100, 400])
@pytest.mark.parametrize("angle", [0, 45, 90, 270])
@pytest.mark.parametrize("handle", range(8))
def test_mouse_resize_all_handles(editor, qtbot, zoom, angle, handle):
    c, scene, view = editor
    m = ItemModel(width=20, height=16, rotation=angle, x=90, y=110)
    c.add(m)
    view.set_zoom(zoom)
    view.centerOn(90, 110)
    qtbot.wait(5)
    item = scene.graphics[m.id]
    hx, hy = HANDLES[handle]
    anchor = local_to_page(m, (1-hx)*m.width, (1-hy)*m.height)
    start = view.handles(item)[handle].toPoint()
    target = local_to_page(m, hx*m.width + (5 if hx == 1 else -5 if hx == 0 else 0),
                           hy*m.height + (4 if hy == 1 else -4 if hy == 0 else 0))
    end = view.mapFromScene(QPointF(*target))
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(view.viewport(), end)
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    n = c.document.items[0]
    assert local_to_page(n, (1-hx)*n.width, (1-hy)*n.height) == pytest.approx(anchor, abs=1e-8)
    assert n.width == pytest.approx(20 if hx == .5 else 25, abs=1.2)
    assert n.height == pytest.approx(16 if hy == .5 else 20, abs=1.2)
    assert c.stack.count() == 2
    c.stack.undo()
    assert c.document.items[0].width == 20
    assert c.document.items[0].height == 16
    c.stack.redo()
    assert c.document.items[0] == n


def test_draw_move_ellipse_and_cancel(editor, qtbot):
    c, scene, view = editor
    view.set_tool("ellipse")
    start = view.mapFromScene(QPointF(40, 40))
    end = view.mapFromScene(QPointF(70, 60))
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(view.viewport(), end)
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    assert c.document.items[0].kind == "ellipse"
    assert c.document.items[0].width == pytest.approx(30, abs=.5)
    point = view.mapFromScene(QPointF(55, 50))
    target = view.mapFromScene(QPointF(60, 57))
    before = c.snapshot()
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    qtbot.mouseMove(view.viewport(), target)
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=target)
    assert c.document.items[0].x > before.items[0].x
    c.stack.undo()
    assert c.document == before


def test_mouse_rotate_preserves_center(editor, qtbot):
    c, scene, view = editor
    m = ItemModel(x=60, y=70, width=40, height=30)
    c.add(m)
    view.centerOn(80, 85)
    item = scene.graphics[m.id]
    center = local_to_page(m, 20, 15)
    start = view.rotation_handle(item).toPoint()
    end = view.mapFromScene(QPointF(center[0]+40, center[1]))
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(view.viewport(), end)
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    assert local_to_page(m, 20, 15) == pytest.approx(center)
    assert m.rotation == pytest.approx(90, abs=1)
    assert c.stack.count() == 2


def test_rubber_selection_and_ctrl_click(editor, qtbot):
    c, scene, view = editor
    a, b = ItemModel(x=45, y=45, width=20, height=15), ItemModel(x=80, y=50, width=20, height=15)
    c.add(a)
    c.add(b)
    scene.clearSelection()
    start, end = view.mapFromScene(QPointF(40, 40)), view.mapFromScene(QPointF(105, 70))
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(view.viewport(), end)
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    assert len(c.selected()) == 2
    qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier,
                     pos=view.mapFromScene(QPointF(55, 52)))
    assert [i.model.id for i in c.selected()] == [b.id]


def test_arrow_points_to_drag_endpoint(editor, qtbot):
    c, scene, view = editor
    view.set_tool("arrow")
    start, end = view.mapFromScene(QPointF(85, 70)), view.mapFromScene(QPointF(45, 40))
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(view.viewport(), end)
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    item = next(iter(scene.graphics.values()))
    _, tip = item.line_points()
    page_tip = item.mapToScene(tip)
    assert (page_tip.x(), page_tip.y()) == pytest.approx((45, 40), abs=.3)
