"""
CineShelf metadata service.
Reads VLC media metadata in a background thread and updates ScanResults.
"""

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from services.library_scanner import ScanResult


class _MetaWorker(QRunnable):
    """Reads VLC metadata for a single media file."""

    def __init__(self, result: ScanResult, signals: "MetadataService"):
        super().__init__()
        self._result = result
        self._signals = signals
        self.setAutoDelete(True)

    def run(self):
        try:
            import vlc
            inst = vlc.Instance("--no-xlib", "--quiet")
            media = inst.media_new(self._result.path)
            media.parse_with_options(vlc.MediaParseFlag.local, 5000)

            duration = media.get_duration()
            if duration > 0:
                self._result.duration_ms = duration

            # Try reading track description for resolution/codec info
            tracks = media.tracks_get()
            if tracks:
                for track in tracks:
                    if track.type == vlc.TrackType.Video:
                        w = track.video.contents.width
                        h = track.video.contents.height
                        if w and h:
                            self._result.resolution = f"{w}×{h}"
                        codec = track.codec
                        if codec:
                            self._result.video_codec = _fourcc(codec)
                    elif track.type == vlc.TrackType.Audio:
                        codec = track.codec
                        if codec:
                            self._result.audio_codec = _fourcc(codec)

            media.release()
            inst.release()
        except Exception as exc:
            pass  # Silently ignore metadata errors; leave defaults

        self._signals.metadata_ready.emit(self._result)


def _fourcc(code: int) -> str:
    """Convert a libVLC 32-bit codec code to a readable string."""
    try:
        return bytes([
            (code >> 0) & 0xFF,
            (code >> 8) & 0xFF,
            (code >> 16) & 0xFF,
            (code >> 24) & 0xFF,
        ]).decode("ascii", errors="replace").strip()
    except Exception:
        return ""


class MetadataService(QObject):
    """
    Fetches media metadata for ScanResult objects in background threads.
    """

    metadata_ready = Signal(object)   # ScanResult

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()
        self._pool.setMaxThreadCount(4)

    def fetch(self, result: ScanResult) -> None:
        """Schedule asynchronous metadata loading for a ScanResult."""
        worker = _MetaWorker(result, self)
        self._pool.start(worker)
