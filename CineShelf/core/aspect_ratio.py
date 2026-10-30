"""
CineShelf aspect ratio manager.
Cycles through and applies aspect ratio modes via the VLC backend.
"""

from typing import List, Optional
from core.vlc_backend import VLCBackend


# Available aspect ratio modes.
# Each entry: (display_name, vlc_ratio_string, crop_string)
ASPECT_RATIO_MODES: List[tuple] = [
    ("Auto",          "",      ""),
    ("Original",      "",      ""),
    ("16:9",          "16:9",  ""),
    ("4:3",           "4:3",   ""),
    ("21:9",          "256:109", ""),
    ("1:1",           "1:1",   ""),
]

DISPLAY_MODE_FIT     = "Fit"
DISPLAY_MODE_FILL    = "Fill"
DISPLAY_MODE_STRETCH = "Stretch"


class AspectRatioManager:
    """Manages video aspect ratio and display mode selection."""

    def __init__(self, backend: VLCBackend):
        self._backend = backend
        self._current_idx: int = 0   # Index into ASPECT_RATIO_MODES
        self._display_mode: str = DISPLAY_MODE_FIT

    # ------------------------------------------------------------------
    # Aspect ratio cycling
    # ------------------------------------------------------------------

    def get_modes(self) -> List[str]:
        """Return the list of aspect ratio display names."""
        return [m[0] for m in ASPECT_RATIO_MODES]

    def get_current_mode(self) -> str:
        """Return the name of the current aspect ratio mode."""
        return ASPECT_RATIO_MODES[self._current_idx][0]

    def cycle_next(self) -> str:
        """Switch to the next aspect ratio. Return the new mode name."""
        self._current_idx = (self._current_idx + 1) % len(ASPECT_RATIO_MODES)
        self._apply()
        return self.get_current_mode()

    def set_mode_by_name(self, name: str) -> bool:
        """Select a named aspect ratio mode. Return True when found."""
        for idx, mode in enumerate(ASPECT_RATIO_MODES):
            if mode[0] == name:
                self._current_idx = idx
                self._apply()
                return True
        return False

    def _apply(self) -> None:
        """Apply the current aspect ratio to the VLC player."""
        name, ratio, crop = ASPECT_RATIO_MODES[self._current_idx]
        self._backend.set_aspect_ratio(ratio)
        self._backend.set_crop_geometry(crop)

    # ------------------------------------------------------------------
    # Display modes
    # ------------------------------------------------------------------

    def get_display_modes(self) -> List[str]:
        return [DISPLAY_MODE_FIT, DISPLAY_MODE_FILL, DISPLAY_MODE_STRETCH]

    def get_display_mode(self) -> str:
        return self._display_mode

    def set_display_mode(self, mode: str) -> None:
        """Apply a display mode (Fit / Fill / Stretch)."""
        self._display_mode = mode
        if mode == DISPLAY_MODE_STRETCH:
            self._backend.set_aspect_ratio("")
            self._backend.set_crop_geometry(None)
        elif mode == DISPLAY_MODE_FILL:
            # Use the current aspect ratio but allow cropping
            self._apply()
        else:  # Fit
            self._apply()

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset to the default Auto aspect ratio."""
        self._current_idx = 0
        self._apply()
