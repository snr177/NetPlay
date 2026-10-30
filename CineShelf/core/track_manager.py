"""
CineShelf audio track manager.
Reads and switches audio tracks through the VLC backend.
"""

from typing import List, Dict, Optional
from core.vlc_backend import VLCBackend


class TrackManager:
    """Manages audio track discovery and selection."""

    def __init__(self, backend: VLCBackend):
        self._backend = backend

    # ------------------------------------------------------------------
    # Audio tracks
    # ------------------------------------------------------------------

    def get_audio_tracks(self) -> List[Dict]:
        """Return the list of audio track dicts from the current media."""
        return self._backend.get_audio_tracks()

    def get_current_audio_track(self) -> int:
        """Return the current audio track ID."""
        return self._backend.get_audio_track()

    def set_audio_track(self, track_id: int) -> None:
        """Select an audio track by ID."""
        self._backend.set_audio_track(track_id)

    def next_audio_track(self) -> Optional[Dict]:
        """
        Switch to the next audio track.
        Cycle back to the first track after the last.
        Return the newly selected track dict, or None when no tracks exist.
        """
        tracks = self.get_audio_tracks()
        if not tracks:
            return None
        if len(tracks) == 1:
            return tracks[0]

        current_id = self.get_current_audio_track()
        ids = [t["id"] for t in tracks]

        try:
            idx = ids.index(current_id)
            next_idx = (idx + 1) % len(tracks)
        except ValueError:
            next_idx = 0

        next_track = tracks[next_idx]
        self._backend.set_audio_track(next_track["id"])
        return next_track

    def previous_audio_track(self) -> Optional[Dict]:
        """
        Switch to the previous audio track.
        Cycle to the last track before the first.
        Return the newly selected track dict, or None when no tracks exist.
        """
        tracks = self.get_audio_tracks()
        if not tracks:
            return None
        if len(tracks) == 1:
            return tracks[0]

        current_id = self.get_current_audio_track()
        ids = [t["id"] for t in tracks]

        try:
            idx = ids.index(current_id)
            prev_idx = (idx - 1) % len(tracks)
        except ValueError:
            prev_idx = len(tracks) - 1

        prev_track = tracks[prev_idx]
        self._backend.set_audio_track(prev_track["id"])
        return prev_track

    def format_track_label(self, track: Dict) -> str:
        """Return a human-readable label for an audio track."""
        name = track.get("name", "").strip()
        if name:
            return name
        return f"Track {track.get('id', '?')}"
