"""
CineShelf audio track selection menu.
"""

from typing import List, Dict
from PySide6.QtWidgets import QMenu, QAction, QActionGroup
from PySide6.QtCore import Signal, QObject


class AudioMenu(QObject):
    """
    Builds and manages a QMenu for audio track selection.
    Emits track_selected(track_id) when the user picks a track.
    """

    track_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._menu = QMenu("Audio Tracks")
        self._group = QActionGroup(self._menu)
        self._group.setExclusive(True)

    def get_menu(self) -> QMenu:
        return self._menu

    def populate(self, tracks: List[Dict], current_id: int) -> None:
        """Rebuild the menu with the given track list."""
        self._menu.clear()
        # Remove old actions from the group
        for action in self._group.actions():
            self._group.removeAction(action)

        if not tracks:
            action = QAction("No audio tracks", self._menu)
            action.setEnabled(False)
            self._menu.addAction(action)
            return

        self._menu.addAction(self._make_header("Audio Tracks"))
        self._menu.addSeparator()

        for i, track in enumerate(tracks):
            label = f"{i + 1}.  {track.get('name', f'Track {track[\"id\"]}')}"
            action = QAction(label, self._menu)
            action.setCheckable(True)
            action.setChecked(track["id"] == current_id)
            action.setData(track["id"])
            action.triggered.connect(self._on_triggered)
            self._group.addAction(action)
            self._menu.addAction(action)

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
