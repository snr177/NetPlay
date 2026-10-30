"""
CineShelf keyboard shortcut manager.
Maps Qt key events to playback actions.
"""

from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtGui import QKeyEvent


class KeyboardManager(QObject):
    """
    Intercepts key events and emits named action signals.
    Install this as an event filter on the player widget.
    """

    action_play_pause    = Signal()
    action_seek_forward  = Signal()
    action_seek_backward = Signal()
    action_fullscreen    = Signal()
    action_exit_fullscreen = Signal()
    action_next_audio    = Signal()
    action_prev_audio    = Signal()
    action_next_ratio    = Signal()
    action_volume_up     = Signal()
    action_volume_down   = Signal()
    action_mute          = Signal()
    action_next_video    = Signal()
    action_prev_video    = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

    def handle_key_press(self, event: QKeyEvent) -> bool:
        """
        Process a key press event.
        Return True when the event is consumed; False otherwise.
        """
        key = event.key()
        modifiers = event.modifiers()

        if key == Qt.Key_Space:
            self.action_play_pause.emit()
            return True

        if key == Qt.Key_Right:
            self.action_seek_forward.emit()
            return True

        if key == Qt.Key_Left:
            self.action_seek_backward.emit()
            return True

        if key == Qt.Key_F:
            self.action_fullscreen.emit()
            return True

        if key == Qt.Key_Escape:
            self.action_exit_fullscreen.emit()
            return True

        if key == Qt.Key_B:
            if modifiers & Qt.ShiftModifier:
                self.action_prev_audio.emit()
            else:
                self.action_next_audio.emit()
            return True

        if key == Qt.Key_A:
            self.action_next_ratio.emit()
            return True

        if key == Qt.Key_Up:
            self.action_volume_up.emit()
            return True

        if key == Qt.Key_Down:
            self.action_volume_down.emit()
            return True

        if key == Qt.Key_M:
            self.action_mute.emit()
            return True

        if key == Qt.Key_N:
            self.action_next_video.emit()
            return True

        if key == Qt.Key_P:
            self.action_prev_video.emit()
            return True

        return False
