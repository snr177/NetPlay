"""
CineShelf settings manager.
Loads configuration from config.json and provides runtime settings.
"""

import json
import os
from pathlib import Path


_DEFAULT_CONFIG = {
    "media_folder": str(Path.home() / "Downloads"),
    "volume": 80,
    "aspect_ratio": "Auto",
    "subtitle_temp_dir": "/tmp/cineshelf_subtitles",
    "history_file": str(Path.home() / ".cineshelf_history.json"),
    "scan_extensions": [
        ".mp4", ".mkv", ".avi", ".mov", ".wmv",
        ".webm", ".mpeg", ".mpg", ".ts", ".m2ts", ".flv",
        ".mp3", ".aac", ".flac", ".wav", ".ogg", ".m4a"
    ],
    "subtitle_extensions": [".srt", ".ass", ".ssa", ".vtt", ".sub"],
    "seek_step": 5,
    "volume_step": 5,
    "controls_hide_delay_ms": 3000,
    "thumbnail_width": 320,
    "thumbnail_height": 180,
    "max_subtitle_download_bytes": 5242880,
    "subtitle_download_timeout": 15
}

_config: dict = {}


def load(config_path: str = "config.json") -> None:
    """Load settings from a JSON config file. Fall back to defaults on error."""
    global _config
    _config = dict(_DEFAULT_CONFIG)
    try:
        path = Path(config_path)
        if path.exists():
            with open(path, "r", encoding="utf-8") as fh:
                user_cfg = json.load(fh)
            _config.update(user_cfg)
    except Exception as exc:
        print(f"[Settings] Could not load {config_path}: {exc}. Using defaults.")

    # Expand ~ in paths
    for key in ("media_folder", "history_file", "subtitle_temp_dir"):
        _config[key] = str(Path(_config[key]).expanduser())

    # Ensure subtitle temp directory exists
    os.makedirs(_config["subtitle_temp_dir"], exist_ok=True)


def get(key: str, default=None):
    """Return a setting value by key."""
    if not _config:
        load()
    return _config.get(key, default)


def set_value(key: str, value) -> None:
    """Set a runtime setting value."""
    _config[key] = value


def save(config_path: str = "config.json") -> None:
    """Persist current settings to disk."""
    try:
        with open(config_path, "w", encoding="utf-8") as fh:
            json.dump(_config, fh, indent=4)
    except Exception as exc:
        print(f"[Settings] Could not save settings: {exc}")
