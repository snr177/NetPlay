"""
CineShelf playback history.
Saves and restores playback positions for each video file.
"""

import json
import os
import time
from pathlib import Path
from typing import Optional

from app import settings


_history: dict = {}
_history_path: str = ""


def _load() -> None:
    global _history, _history_path
    _history_path = settings.get(
        "history_file",
        str(Path.home() / ".cineshelf_history.json"),
    )
    if os.path.exists(_history_path):
        try:
            with open(_history_path, "r", encoding="utf-8") as fh:
                _history = json.load(fh)
        except Exception:
            _history = {}
    else:
        _history = {}


def _save() -> None:
    if not _history_path:
        return
    try:
        with open(_history_path, "w", encoding="utf-8") as fh:
            json.dump(_history, fh, indent=2)
    except Exception as exc:
        print(f"[History] Could not save history: {exc}")


def save_position(path: str, position_ms: int, duration_ms: int) -> None:
    """Record the playback position for a file."""
    if not _history:
        _load()
    _history[path] = {
        "position_ms": position_ms,
        "duration_ms": duration_ms,
        "timestamp": time.time(),
    }
    _save()


def get_position(path: str) -> Optional[int]:
    """
    Return the saved playback position in milliseconds.
    Return None when no history entry exists.
    """
    if not _history:
        _load()
    entry = _history.get(path)
    if entry is None:
        return None
    pos = entry.get("position_ms", 0)
    dur = entry.get("duration_ms", 0)
    # Do not resume within the last 5 % of the video (treat as finished)
    if dur > 0 and pos > dur * 0.95:
        return None
    return pos


def get_recent(limit: int = 20) -> list:
    """
    Return the most recently played files sorted by timestamp descending.
    Each item is a dict with keys: path, position_ms, duration_ms, timestamp.
    """
    if not _history:
        _load()
    items = [
        {"path": path, **data}
        for path, data in _history.items()
        if os.path.exists(path)
    ]
    items.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    return items[:limit]


def clear(path: str) -> None:
    """Remove the history entry for a specific file."""
    if not _history:
        _load()
    _history.pop(path, None)
    _save()


def clear_all() -> None:
    """Remove all playback history."""
    global _history
    _history = {}
    _save()
