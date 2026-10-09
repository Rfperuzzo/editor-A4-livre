"""Um comando por transação de edição, incluindo gestos contínuos."""
from copy import deepcopy

from PySide6.QtGui import QUndoCommand


class DocumentCommand(QUndoCommand):
    def __init__(self, controller, before, after, label: str, before_selected: list[str], after_selected: list[str]):
        super().__init__(label)
        self.controller = controller
        self.before, self.after = deepcopy(before), deepcopy(after)
        self.before_selected = before_selected
        self.after_selected = after_selected
        self.first = True

    def undo(self) -> None:
        self.controller.restore(self.before, self.before_selected)

    def redo(self) -> None:
        if self.first:
            self.first = False
        else:
            self.controller.restore(self.after, self.after_selected)
