"""
CineShelf application entry point.
Initialises settings and launches the main window.
"""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from app import settings
from ui.main_window import MainWindow


def run() -> int:
    """Initialise and run the CineShelf application. Return the exit code."""
    settings.load("config.json")

    app = QApplication(sys.argv)
    app.setApplicationName("CineShelf")
    app.setApplicationDisplayName("CineShelf")
    app.setOrganizationName("CineShelf")
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # Load stylesheet
    _apply_stylesheet(app)

    window = MainWindow()
    window.show()

    return app.exec()


def _apply_stylesheet(app: QApplication) -> None:
    """Load and apply the dark theme stylesheet."""
    import os
    qss_path = os.path.join(os.path.dirname(__file__), "..", "assets", "styles", "dark_theme.qss")
    qss_path = os.path.normpath(qss_path)
    try:
        with open(qss_path, "r", encoding="utf-8") as fh:
            app.setStyleSheet(fh.read())
    except FileNotFoundError:
        print(f"[Application] Stylesheet not found at {qss_path}. Using default style.")
    except Exception as exc:
        print(f"[Application] Could not load stylesheet: {exc}")
