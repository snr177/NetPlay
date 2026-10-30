"""
CineShelf main window.
Manages switching between the Home page and the Player page.
"""

from PySide6.QtWidgets import QMainWindow, QStackedWidget, QMessageBox
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QCloseEvent

from core.playback_controller import PlaybackController
from ui.home_page import HomePage
from ui.player_page import PlayerPage
from ui.dialogs import ResumeDialog
from services.library_scanner import ScanResult
from services import playback_history
from app import settings

# Page indices
PAGE_HOME   = 0
PAGE_PLAYER = 1


def _ms_to_label(ms: int) -> str:
    total_s = ms // 1000
    h = total_s // 3600
    m = (total_s % 3600) // 60
    s = total_s % 60
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


class MainWindow(QMainWindow):
    """The application's single top-level window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CineShelf")
        self.resize(1280, 720)
        self.setMinimumSize(QSize(800, 500))
        self.setAcceptDrops(True)

        # Shared playback controller
        self._controller = PlaybackController(self)

        # Page stack
        self._stack = QStackedWidget(self)
        self.setCentralWidget(self._stack)

        self._home_page   = HomePage(self)
        self._player_page = PlayerPage(self._controller, self)

        self._stack.addWidget(self._home_page)    # index 0
        self._stack.addWidget(self._player_page)  # index 1

        self._connect_signals()
        self._show_home()

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _connect_signals(self):
        self._home_page.play_requested.connect(self._on_play_requested)
        self._player_page.back_requested.connect(self._on_back_to_home)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _show_home(self) -> None:
        self._stack.setCurrentIndex(PAGE_HOME)

    def _show_player(self) -> None:
        self._stack.setCurrentIndex(PAGE_PLAYER)
        self._player_page.setFocus()

    # ------------------------------------------------------------------
    # Play request handling
    # ------------------------------------------------------------------

    def _on_play_requested(self, result: ScanResult) -> None:
        """Handle a video selection from the home page."""
        saved_pos = playback_history.get_position(result.path)
        start_ms = 0

        if saved_pos and saved_pos > 0:
            dlg = ResumeDialog(result.name, _ms_to_label(saved_pos), self)
            dlg.exec()
            if dlg.choice == ResumeDialog.RESUME:
                start_ms = saved_pos

        # Pass the full playlist and current index to the player
        all_results = self._home_page._all_results
        try:
            idx = all_results.index(result)
        except ValueError:
            idx = -1

        self._player_page.set_playlist(all_results, idx)
        self._player_page.play_result(result, start_ms=start_ms)
        self._show_player()

    def _on_back_to_home(self) -> None:
        """Save playback position and return to the library."""
        self._player_page.save_position()
        self._controller.stop()
        self._show_home()

    # ------------------------------------------------------------------
    # Drag and drop at window level
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                result = ScanResult(path)
                self._on_play_requested(result)
                break

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        self._player_page.save_position()
        self._controller.release()
        settings.save()
        super().closeEvent(event)
