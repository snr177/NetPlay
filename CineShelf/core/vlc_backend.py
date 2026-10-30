"""
CineShelf VLC backend.
All libVLC interaction lives here.
"""

import os
import sys
from typing import Optional, List, Dict

try:
    import vlc
except ImportError:
    print("[VLC] python-vlc not found. Install it with: pip install python-vlc")
    vlc = None  # type: ignore


class VLCBackend:
    """Wraps the libVLC instance, media player, and event manager."""

    def __init__(self):
        self._instance: Optional["vlc.Instance"] = None
        self._player: Optional["vlc.MediaPlayer"] = None
        self._media: Optional["vlc.Media"] = None
        self._event_manager = None
        self._callbacks: Dict[str, list] = {}

        self._init_vlc()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_vlc(self) -> None:
        """Create the libVLC instance and media player."""
        if vlc is None:
            raise RuntimeError("python-vlc is not installed.")
        try:
            self._instance = vlc.Instance("--no-xlib")
            self._player = self._instance.media_player_new()
            self._event_manager = self._player.event_manager()
            self._attach_events()
        except Exception as exc:
            raise RuntimeError(f"Failed to initialise libVLC: {exc}") from exc

    def _attach_events(self) -> None:
        """Attach libVLC player events."""
        em = self._event_manager
        em.event_attach(vlc.EventType.MediaPlayerEndReached,    self._on_end_reached)
        em.event_attach(vlc.EventType.MediaPlayerEncounteredError, self._on_error)
        em.event_attach(vlc.EventType.MediaPlayerTimeChanged,   self._on_time_changed)
        em.event_attach(vlc.EventType.MediaPlayerPlaying,       self._on_playing)
        em.event_attach(vlc.EventType.MediaPlayerPaused,        self._on_paused)
        em.event_attach(vlc.EventType.MediaPlayerStopped,       self._on_stopped)

    # ------------------------------------------------------------------
    # Media loading
    # ------------------------------------------------------------------

    def load_media(self, path: str) -> bool:
        """Load a local media file. Return True on success."""
        if self._instance is None:
            return False
        try:
            self._media = self._instance.media_new(path)
            self._player.set_media(self._media)
            # Parse media to populate track information
            self._media.parse_with_options(vlc.MediaParseFlag.local, 5000)
            return True
        except Exception as exc:
            print(f"[VLC] load_media error: {exc}")
            return False

    def set_hwnd(self, hwnd: int) -> None:
        """Embed the video output into a native window handle."""
        if self._player is None:
            return
        if sys.platform.startswith("linux"):
            self._player.set_xwindow(hwnd)
        elif sys.platform == "win32":
            self._player.set_hwnd(hwnd)
        elif sys.platform == "darwin":
            self._player.set_nsobject(hwnd)

    # ------------------------------------------------------------------
    # Playback control
    # ------------------------------------------------------------------

    def play(self) -> None:
        if self._player:
            self._player.play()

    def pause(self) -> None:
        if self._player:
            self._player.pause()

    def stop(self) -> None:
        if self._player:
            self._player.stop()

    def toggle_play_pause(self) -> None:
        if self._player is None:
            return
        state = self._player.get_state()
        if state == vlc.State.Playing:
            self._player.pause()
        else:
            self._player.play()

    def is_playing(self) -> bool:
        if self._player is None:
            return False
        return self._player.get_state() == vlc.State.Playing

    def is_paused(self) -> bool:
        if self._player is None:
            return False
        return self._player.get_state() == vlc.State.Paused

    # ------------------------------------------------------------------
    # Time and position
    # ------------------------------------------------------------------

    def get_time_ms(self) -> int:
        """Return the current playback position in milliseconds."""
        if self._player is None:
            return 0
        t = self._player.get_time()
        return max(0, t)

    def set_time_ms(self, ms: int) -> None:
        """Seek to a position in milliseconds."""
        if self._player is None:
            return
        duration = self.get_duration_ms()
        ms = max(0, min(ms, duration))
        self._player.set_time(ms)

    def get_duration_ms(self) -> int:
        """Return the total duration in milliseconds."""
        if self._player is None:
            return 0
        d = self._player.get_length()
        return max(0, d)

    def seek_forward(self, seconds: int = 5) -> None:
        self.set_time_ms(self.get_time_ms() + seconds * 1000)

    def seek_backward(self, seconds: int = 5) -> None:
        self.set_time_ms(self.get_time_ms() - seconds * 1000)

    def get_position(self) -> float:
        """Return playback position as a float between 0.0 and 1.0."""
        if self._player is None:
            return 0.0
        return max(0.0, self._player.get_position())

    def set_position(self, pos: float) -> None:
        """Seek to a fractional position between 0.0 and 1.0."""
        if self._player is None:
            return
        self._player.set_position(max(0.0, min(1.0, pos)))

    # ------------------------------------------------------------------
    # Volume
    # ------------------------------------------------------------------

    def get_volume(self) -> int:
        if self._player is None:
            return 0
        return self._player.audio_get_volume()

    def set_volume(self, volume: int) -> None:
        if self._player is None:
            return
        self._player.audio_set_volume(max(0, min(200, volume)))

    def is_muted(self) -> bool:
        if self._player is None:
            return False
        return bool(self._player.audio_get_mute())

    def toggle_mute(self) -> None:
        if self._player:
            self._player.audio_toggle_mute()

    def set_mute(self, muted: bool) -> None:
        if self._player:
            self._player.audio_set_mute(muted)

    # ------------------------------------------------------------------
    # Audio tracks
    # ------------------------------------------------------------------

    def get_audio_tracks(self) -> List[Dict]:
        """Return a list of available audio tracks as dicts."""
        if self._player is None:
            return []
        tracks = []
        try:
            track_desc = self._player.audio_get_track_description()
            if track_desc is None:
                return []
            for td in track_desc:
                track_id = td.id
                track_name = td.name
                if isinstance(track_name, bytes):
                    track_name = track_name.decode("utf-8", errors="replace")
                if track_id == -1:
                    continue  # Skip the "Disable" entry
                tracks.append({"id": track_id, "name": track_name})
        except Exception as exc:
            print(f"[VLC] get_audio_tracks error: {exc}")
        return tracks

    def get_audio_track(self) -> int:
        """Return the current audio track ID."""
        if self._player is None:
            return -1
        return self._player.audio_get_track()

    def set_audio_track(self, track_id: int) -> None:
        """Select an audio track by ID."""
        if self._player:
            self._player.audio_set_track(track_id)

    # ------------------------------------------------------------------
    # Subtitle tracks
    # ------------------------------------------------------------------

    def get_subtitle_tracks(self) -> List[Dict]:
        """Return a list of available subtitle tracks as dicts."""
        if self._player is None:
            return []
        tracks = []
        try:
            track_desc = self._player.video_get_spu_description()
            if track_desc is None:
                return []
            for td in track_desc:
                track_id = td.id
                track_name = td.name
                if isinstance(track_name, bytes):
                    track_name = track_name.decode("utf-8", errors="replace")
                tracks.append({"id": track_id, "name": track_name})
        except Exception as exc:
            print(f"[VLC] get_subtitle_tracks error: {exc}")
        return tracks

    def get_subtitle_track(self) -> int:
        """Return the current subtitle track ID."""
        if self._player is None:
            return -1
        return self._player.video_get_spu()

    def set_subtitle_track(self, track_id: int) -> None:
        """Select a subtitle track by ID."""
        if self._player:
            self._player.video_set_spu(track_id)

    def load_subtitle_file(self, path: str) -> bool:
        """Attach an external subtitle file. Return True on success."""
        if self._player is None:
            return False
        try:
            result = self._player.add_slave(
                vlc.MediaSlaveType.Subtitle, f"file://{path}", True
            )
            return result == 0
        except Exception as exc:
            print(f"[VLC] load_subtitle_file error: {exc}")
            return False

    # ------------------------------------------------------------------
    # Aspect ratio
    # ------------------------------------------------------------------

    def set_aspect_ratio(self, ratio: str) -> None:
        """
        Set the video aspect ratio.
        Pass an empty string or 'Auto' to let VLC use the original ratio.
        Pass '16:9', '4:3', '21:9', '1:1' etc. for fixed ratios.
        """
        if self._player is None:
            return
        if ratio in ("Auto", ""):
            self._player.video_set_aspect_ratio(None)
            self._player.video_set_scale(0)
        else:
            self._player.video_set_aspect_ratio(ratio)

    def set_crop_geometry(self, crop: str) -> None:
        """Set the VLC crop geometry string."""
        if self._player is None:
            return
        self._player.video_set_crop_geometry(crop if crop else None)

    # ------------------------------------------------------------------
    # Full screen (native VLC full screen, optional)
    # ------------------------------------------------------------------

    def set_fullscreen(self, enabled: bool) -> None:
        if self._player:
            self._player.set_fullscreen(enabled)

    # ------------------------------------------------------------------
    # State query
    # ------------------------------------------------------------------

    def get_state(self) -> Optional["vlc.State"]:
        if self._player is None:
            return None
        return self._player.get_state()

    # ------------------------------------------------------------------
    # VLC event callbacks (called from VLC thread — use signals to marshal)
    # ------------------------------------------------------------------

    def on(self, event: str, callback) -> None:
        """Register a Python callback for a named event."""
        self._callbacks.setdefault(event, []).append(callback)

    def _emit(self, event: str, *args) -> None:
        for cb in self._callbacks.get(event, []):
            try:
                cb(*args)
            except Exception as exc:
                print(f"[VLC] callback error for '{event}': {exc}")

    def _on_end_reached(self, event) -> None:
        self._emit("end_reached")

    def _on_error(self, event) -> None:
        self._emit("error")

    def _on_time_changed(self, event) -> None:
        self._emit("time_changed", event.u.new_time)

    def _on_playing(self, event) -> None:
        self._emit("playing")

    def _on_paused(self, event) -> None:
        self._emit("paused")

    def _on_stopped(self, event) -> None:
        self._emit("stopped")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def release(self) -> None:
        """Release VLC resources."""
        try:
            if self._player:
                self._player.stop()
                self._player.release()
            if self._instance:
                self._instance.release()
        except Exception as exc:
            print(f"[VLC] release error: {exc}")
        finally:
            self._player = None
            self._instance = None
            self._media = None
