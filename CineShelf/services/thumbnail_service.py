"""
CineShelf thumbnail service.
Generates video thumbnails using libVLC in background threads.
"""

import os
import hashlib
import time
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from app import settings


THUMB_DIR = os.path.join(
    os.path.expanduser("~"), ".cache", "cineshelf", "thumbnails"
)
THUMB_W = settings.get("thumbnail_width", 320)
THUMB_H = settings.get("thumbnail_height", 180)


class _ThumbWorker(QRunnable):
    """Generates a thumbnail for a single video file using libVLC."""

    def __init__(self, path: str, signals: "ThumbnailService"):
        super().__init__()
        self._path = path
        self._signals = signals
        self.setAutoDelete(True)

    def run(self):
        thumb_path = _thumb_path(self._path)
        if os.path.exists(thumb_path):
            self._signals.thumbnail_ready.emit(self._path, thumb_path)
            return

        try:
            import vlc
            os.makedirs(THUMB_DIR, exist_ok=True)

            inst = vlc.Instance("--no-xlib", "--quiet", "--vout=dummy")
            player = inst.media_player_new()
            media = inst.media_new(self._path)
            player.set_media(media)
            player.play()

            # Wait for playback to start
            for _ in range(50):
                state = player.get_state()
                if state in (vlc.State.Playing, vlc.State.Paused, vlc.State.Ended):
                    break
                time.sleep(0.1)

            duration = player.get_length()
            if duration > 0:
                seek_ms = min(duration // 4, 30000)
                player.set_time(seek_ms)
                time.sleep(0.5)

            result = player.video_take_snapshot(0, thumb_path, THUMB_W, THUMB_H)
            player.stop()
            player.release()
            media.release()
            inst.release()

            if result == 0 and os.path.exists(thumb_path):
                self._signals.thumbnail_ready.emit(self._path, thumb_path)
            else:
                self._signals.thumbnail_ready.emit(self._path, "")
        except Exception as exc:
            self._signals.thumbnail_ready.emit(self._path, "")


def _thumb_path(media_path: str) -> str:
    """Return the cached thumbnail path for a media file."""
    key = hashlib.sha1(media_path.encode()).hexdigest()
    return os.path.join(THUMB_DIR, f"{key}.png")


class ThumbnailService(QObject):
    """
    Generates video thumbnails asynchronously.
    Emits thumbnail_ready(media_path, thumb_path) when done.
    """

    thumbnail_ready = Signal(str, str)   # media_path, thumb_path (empty = failed)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()
        self._pool.setMaxThreadCount(2)

    def request(self, media_path: str) -> None:
        """Schedule thumbnail generation for a media file."""
        worker = _ThumbWorker(media_path, self)
        self._pool.start(worker)
