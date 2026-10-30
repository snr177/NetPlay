"""
CineShelf playback controller.
Bridges the VLC backend with the Qt UI using signals and slots.
"""

from PySide6.QtCore import QObject, Signal, QTimer
from core.vlc_backend import VLCBackend
from app import settings


class PlaybackController(QObject):
    """
    High-level playback control object.

    Emits Qt signals from VLC event callbacks, marshalling between
    the VLC internal thread and the Qt main thread.
    """

    # Signals emitted to the UI
    playing = Signal()
    paused = Signal()
    stopped = Signal()
    end_reached = Signal()
    error_occurred = Signal()
    time_updated = Signal(int, int)   # current_ms, duration_ms
    volume_changed = Signal(int)
    mute_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.backend = VLCBackend()
        self._duration_ms: int = 0
        self._seek_step: int = settings.get("seek_step", 5)

        # Poll timer — VLC time_changed fires on the VLC thread.
        # We poll on the Qt thread to keep UI updates safe.
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(500)
        self._poll_timer.timeout.connect(self._poll_state)

        # Register VLC callbacks
        self.backend.on("end_reached", self._cb_end_reached)
        self.backend.on("error",       self._cb_error)
        self.backend.on("playing",     self._cb_playing)
        self.backend.on("paused",      self._cb_paused)
        self.backend.on("stopped",     self._cb_stopped)

        # Pending signals (marshalled from VLC thread via single-shot timers)
        self._pending: list = []

    # ------------------------------------------------------------------
    # VLC thread callbacks — marshal to Qt main thread
    # ------------------------------------------------------------------

    def _cb_playing(self):
        QTimer.singleShot(0, self.playing.emit)
        QTimer.singleShot(0, self._poll_timer.start)

    def _cb_paused(self):
        QTimer.singleShot(0, self.paused.emit)

    def _cb_stopped(self):
        QTimer.singleShot(0, self.stopped.emit)
        QTimer.singleShot(0, self._poll_timer.stop)

    def _cb_end_reached(self):
        QTimer.singleShot(0, self.end_reached.emit)
        QTimer.singleShot(0, self._poll_timer.stop)

    def _cb_error(self):
        QTimer.singleShot(0, self.error_occurred.emit)
        QTimer.singleShot(0, self._poll_timer.stop)

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    def _poll_state(self):
        current = self.backend.get_time_ms()
        duration = self.backend.get_duration_ms()
        self._duration_ms = duration
        self.time_updated.emit(current, duration)

    # ------------------------------------------------------------------
    # Media loading
    # ------------------------------------------------------------------

    def open_file(self, path: str) -> bool:
        """Load a media file and start playback. Return True on success."""
        self.backend.stop()
        ok = self.backend.load_media(path)
        if ok:
            self.backend.play()
        return ok

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def play(self):
        self.backend.play()
        self._poll_timer.start()

    def pause(self):
        self.backend.pause()

    def stop(self):
        self.backend.stop()
        self._poll_timer.stop()

    def toggle_play_pause(self):
        self.backend.toggle_play_pause()
        if self.backend.is_playing():
            self._poll_timer.start()

    def is_playing(self) -> bool:
        return self.backend.is_playing()

    # ------------------------------------------------------------------
    # Seeking
    # ------------------------------------------------------------------

    def seek_to_ms(self, ms: int):
        self.backend.set_time_ms(ms)

    def seek_forward(self):
        self.backend.seek_forward(self._seek_step)

    def seek_backward(self):
        self.backend.seek_backward(self._seek_step)

    # ------------------------------------------------------------------
    # Volume
    # ------------------------------------------------------------------

    def get_volume(self) -> int:
        return self.backend.get_volume()

    def set_volume(self, vol: int):
        self.backend.set_volume(vol)
        self.volume_changed.emit(vol)

    def increase_volume(self):
        step = settings.get("volume_step", 5)
        self.set_volume(min(200, self.get_volume() + step))

    def decrease_volume(self):
        step = settings.get("volume_step", 5)
        self.set_volume(max(0, self.get_volume() - step))

    def toggle_mute(self):
        self.backend.toggle_mute()
        self.mute_changed.emit(self.backend.is_muted())

    def is_muted(self) -> bool:
        return self.backend.is_muted()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def release(self):
        self._poll_timer.stop()
        self.backend.release()
