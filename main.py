"""Ponto de entrada do aplicativo desktop e do executável Windows."""
import sys

from PySide6.QtCore import QLocale, QTimer, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from editor.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Editor A4 Livre")
    app.setOrganizationName("Editor A4 Livre")
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    QLocale.setDefault(QLocale(QLocale.Language.Portuguese, QLocale.Country.Brazil))
    window = MainWindow()
    if len(sys.argv) >= 3 and sys.argv[1] == "--smoke-test":
        from editor.smoke import run
        window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        window.show()
        QTimer.singleShot(50, lambda: app.exit(run(window, sys.argv[2])))
        return app.exec()
    window.show()
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        window.safe(lambda: window.open_path(sys.argv[1]))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
