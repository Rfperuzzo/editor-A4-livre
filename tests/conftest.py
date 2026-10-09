import pytest

from editor.canvas import CanvasScene, CanvasView
from editor.controller import Controller


@pytest.fixture
def editor(qtbot):
    controller = Controller()
    scene = CanvasScene(controller)
    view = CanvasView(scene)
    view.resize(1100, 800)
    qtbot.addWidget(view)
    view.show()
    qtbot.waitExposed(view)
    return controller, scene, view
