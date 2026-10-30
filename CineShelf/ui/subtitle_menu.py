"""
CineShelf subtitle selection menu.
"""

from typing import List, Dict
from PySide6.QtWidgets import QMenu, QAction, QActionGroup
from PySide6.QtCore import Signal, QObject


class SubtitleMenu(QObject):
    """
    Builds and manages a QMenu for subtitle track selection and import.
    Emits:
        track_selected(track_id)  — user picked an embedded track
        import_file()             — user wants to import a file
        import_url()              — user wants to paste a URL
    """

    track_selected = Signal(int)
    import_file    = Signal()
    import_url     = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._menu = QMenu("Subtitles")
        self._group = QActionGroup(self._menu)
        self._group.setExclusive(True)

    def get_menu(self) -> QMenu:
        return self._menu

    def populate(self, tracks: List[Dict], current_id: int) -> None:
        """Rebuild the menu with the given track list."""
        self._menu.clear()
        for action in self._group.actions():
            self._group.removeAction(action)

        self._menu.addAction(self._make_header("Subtitles"))
        self._menu.addSeparator()

        # Disable option (id = -1 in VLC)
        disable_action = QAction("Disable", self._menu)
        disable_action.setCheckable(True)
        disable_action.setChecked(current_id == -1)
        disable_action.setData(-1)
        disable_action.triggered.connect(self._on_triggered)
        self._group.addAction(disable_action)
        self._menu.addAction(disable_action)

        if tracks:
            self._menu.addSeparator()
            for i, track in enumerate(tracks):
                if track["id"] == -1:
                    continue  # Skip the disable entry from VLC list
                label = f"{i + 1}.  {track.get('name', f'Track {track[\"id\"]}')}"
                action = QAction(label, self._menu)
                action.setCheckable(True)
                action.setChecked(track["id"] == current_id)
                action.setData(track["id"])
                action.triggered.connect(self._on_triggered)
                self._group.addAction(action)
                self._menu.addAction(action)

        self._menu.addSeparator()
        import_file_action = QAction("Import subtitle file…", self._menu)
        import_file_action.triggered.connect(self.import_file.emit)
        self._menu.addAction(import_file_action)

        import_url_action = QAction("Paste subtitle URL…", self._menu)
        import_url_action.triggered.connect(self.import_url.emit)
        self._menu.addAction(import_url_action)

    def _make_header(self, text: str) -> QAction:
        header = QAction(text)
        header.setEnabled(False)
        font = header.font()
        font.setBold(True)
        header.setFont(font)
        return header

    def _on_triggered(self) -> None:
        action = self.sender()
        if action and action.data() is not None:
            self.track_selected.emit(int(action.data()))
