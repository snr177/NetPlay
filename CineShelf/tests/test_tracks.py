"""
Tests for the TrackManager and AspectRatioManager (without VLC).
"""

import pytest
from unittest.mock import MagicMock, patch

from core.track_manager import TrackManager
from core.aspect_ratio import AspectRatioManager, ASPECT_RATIO_MODES


class TestTrackManager:
    """Tests for TrackManager using a mocked VLC backend."""

    def _make_manager(self, tracks, current_id):
        backend = MagicMock()
        backend.get_audio_tracks.return_value = tracks
        backend.get_audio_track.return_value = current_id
        return TrackManager(backend), backend

    def test_get_audio_tracks_returns_list(self):
        tracks = [{"id": 1, "name": "English"}, {"id": 2, "name": "Hindi"}]
        mgr, _ = self._make_manager(tracks, 1)
        result = mgr.get_audio_tracks()
        assert len(result) == 2

    def test_next_audio_track_advances(self):
        tracks = [
            {"id": 1, "name": "English"},
            {"id": 2, "name": "Hindi"},
            {"id": 3, "name": "Telugu"},
        ]
        mgr, backend = self._make_manager(tracks, 1)
        result = mgr.next_audio_track()
        backend.set_audio_track.assert_called_once_with(2)
        assert result["id"] == 2

    def test_next_audio_track_wraps_around(self):
        tracks = [{"id": 1, "name": "English"}, {"id": 2, "name": "Hindi"}]
        mgr, backend = self._make_manager(tracks, 2)
        result = mgr.next_audio_track()
        backend.set_audio_track.assert_called_once_with(1)
        assert result["id"] == 1

    def test_single_track_no_change(self):
        tracks = [{"id": 1, "name": "English"}]
        mgr, backend = self._make_manager(tracks, 1)
        result = mgr.next_audio_track()
        backend.set_audio_track.assert_not_called()
        assert result["id"] == 1

    def test_empty_tracks_returns_none(self):
        mgr, _ = self._make_manager([], -1)
        result = mgr.next_audio_track()
        assert result is None

    def test_previous_audio_track(self):
        tracks = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}, {"id": 3, "name": "C"}]
        mgr, backend = self._make_manager(tracks, 3)
        result = mgr.previous_audio_track()
        backend.set_audio_track.assert_called_once_with(2)
        assert result["id"] == 2

    def test_previous_audio_track_wraps(self):
        tracks = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]
        mgr, backend = self._make_manager(tracks, 1)
        result = mgr.previous_audio_track()
        backend.set_audio_track.assert_called_once_with(2)
        assert result["id"] == 2

    def test_format_track_label_uses_name(self):
        mgr, _ = self._make_manager([], -1)
        label = mgr.format_track_label({"id": 3, "name": "Telugu - AC3 5.1"})
        assert "Telugu" in label

    def test_format_track_label_fallback(self):
        mgr, _ = self._make_manager([], -1)
        label = mgr.format_track_label({"id": 5, "name": ""})
        assert "5" in label


class TestAspectRatioManager:
    def _make_manager(self):
        backend = MagicMock()
        return AspectRatioManager(backend), backend

    def test_initial_mode_is_auto(self):
        mgr, _ = self._make_manager()
        assert mgr.get_current_mode() == "Auto"

    def test_cycle_advances_mode(self):
        mgr, _ = self._make_manager()
        mode1 = mgr.cycle_next()
        assert mode1 != "Auto"

    def test_cycle_returns_to_start(self):
        mgr, _ = self._make_manager()
        total = len(ASPECT_RATIO_MODES)
        for _ in range(total):
            mgr.cycle_next()
        assert mgr.get_current_mode() == "Auto"

    def test_set_mode_by_name(self):
        mgr, backend = self._make_manager()
        found = mgr.set_mode_by_name("16:9")
        assert found is True
        assert mgr.get_current_mode() == "16:9"
        backend.set_aspect_ratio.assert_called()

    def test_set_invalid_mode_returns_false(self):
        mgr, _ = self._make_manager()
        found = mgr.set_mode_by_name("InvalidRatio")
        assert found is False

    def test_get_modes_returns_all(self):
        mgr, _ = self._make_manager()
        modes = mgr.get_modes()
        assert "Auto" in modes
        assert "16:9" in modes
        assert "4:3" in modes

    def test_reset_returns_to_auto(self):
        mgr, _ = self._make_manager()
        mgr.cycle_next()
        mgr.cycle_next()
        mgr.reset()
        assert mgr.get_current_mode() == "Auto"
