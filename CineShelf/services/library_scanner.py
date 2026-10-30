"""
CineShelf library scanner.
Scans a directory for media files in a background thread.
"""

import os
from pathlib import Path
from typing import List

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, QTimer

from app import settings


class ScanResult:
    """Holds metadata for a single discovered media file."""

    def __init__(self, path: str):
        self.path = path
        self.filename = os.path.basename(path)
        self.name = os.path.splitext(self.filename)[0]
        self.extension = os.path.splitext(self.filename)[1].lower()
        self.size_bytes: int = 0
        self.duration_ms: int = 0
        self.thumbnail_path: str = ""
        self.resolution: str = ""
        self.video_codec: str = ""
        self.audio_codec: str = ""
        self.container: str = self.extension.lstrip(".")

    def size_label(self) -> str:
        if self.size_bytes == 0:
            return ""
        mb = self.size_bytes / (1024 * 1024)
        if mb >= 1024:
            return f"{mb / 1024:.1f} GB"
        return f"{mb:.0f} MB"

    def duration_label(self) -> str:
        if self.duration_ms <= 0:
            return ""
        total_s = self.duration_ms // 1000
        hours = total_s // 3600
        minutes = (total_s % 3600) // 60
        seconds = total_s % 60
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"


class _ScanWorker(QRunnable):
    """Background worker that walks a directory and finds media files."""

    def __init__(self, folder: str, signals: "LibraryScanner"):
        super().__init__()
        self._folder = folder
        self._signals = signals
        self.setAutoDelete(True)

    def run(self):
        extensions = set(settings.get("scan_extensions", []))
        results: List[ScanResult] = []
        try:
            root = Path(self._folder)
            if not root.exists():
                self._signals.scan_error.emit(f"Folder not found: {self._folder}")
                return
            for entry in sorted(root.rglob("*")):
                if not entry.is_file():
                    continue
                if entry.suffix.lower() not in extensions:
                    continue
                result = ScanResult(str(entry))
                try:
                    result.size_bytes = entry.stat().st_size
                except OSError:
                    pass
                results.append(result)
        except Exception as exc:
            self._signals.scan_error.emit(str(exc))
            return
        self._signals.scan_finished.emit(results)


class LibraryScanner(QObject):
    """
    Scans a media folder in a background thread pool.
    Emits scan_finished when all files are found.
    """

    scan_started = Signal()
    scan_finished = Signal(list)   # list[ScanResult]
    scan_error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()

    def scan(self, folder: str) -> None:
        """Start an asynchronous scan of the given folder."""
        self.scan_started.emit()
        worker = _ScanWorker(folder, self)
        self._pool.start(worker)
