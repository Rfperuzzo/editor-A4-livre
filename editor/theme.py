"""Paleta clara consistente, inclusive quando o Windows está em modo escuro."""
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def apply_theme() -> None:
    app = QApplication.instance()
    palette = QPalette()
    colors = {
        QPalette.ColorRole.Window: "#f8fafc", QPalette.ColorRole.WindowText: "#172033",
        QPalette.ColorRole.Base: "#ffffff", QPalette.ColorRole.AlternateBase: "#f1f5f9",
        QPalette.ColorRole.ToolTipBase: "#ffffff", QPalette.ColorRole.ToolTipText: "#172033",
        QPalette.ColorRole.Text: "#172033", QPalette.ColorRole.Button: "#f1f5f9",
        QPalette.ColorRole.ButtonText: "#172033", QPalette.ColorRole.BrightText: "#ffffff",
        QPalette.ColorRole.Highlight: "#2563eb", QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.Link: "#2563eb", QPalette.ColorRole.PlaceholderText: "#64748b",
    }
    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor("#94a3b8"))
    app.setPalette(palette)
