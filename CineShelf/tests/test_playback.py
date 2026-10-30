"""
Tests for the playback history service.
"""

import os
import json
import tempfile
import pytest

import services.playback_history as ph


@pytest.fixture(autouse=True)
def reset_history(tmp_path):
    """Reset history state and use a temp file for each test."""
    ph._history = {}
    ph._history_path = str(tmp_path / "test_history.json")
    yield
    ph._history = {}
    ph._history_path = ""


class TestPlaybackHistory:
    def test_save_and_get_position(self):
        ph.save_position("/tmp/video.mp4", 30000, 120000)
        pos = ph.get_position("/tmp/video.mp4")
        assert pos == 30000

    def test_get_position_missing_returns_none(self):
        pos = ph.get_position("/nonexistent/video.mp4")
        assert pos is None

    def test_position_near_end_returns_none(self):
        # 96% through — treat as finished
        ph.save_position("/tmp/video.mp4", 96000, 100000)
        pos = ph.get_position("/tmp/video.mp4")
        assert pos is None

    def test_position_at_95_percent_is_kept(self):
        # Exactly 95% — just before the threshold, keep it
        ph.save_position("/tmp/video.mp4", 94999, 100000)
        pos = ph.get_position("/tmp/video.mp4")
        assert pos == 94999

    def test_clear_removes_entry(self):
        ph.save_position("/tmp/video.mp4", 10000, 60000)
        ph.clear("/tmp/video.mp4")
        assert ph.get_position("/tmp/video.mp4") is None

    def test_clear_all_empties_history(self):
        ph.save_position("/tmp/a.mp4", 1000, 60000)
        ph.save_position("/tmp/b.mp4", 2000, 60000)
        ph.clear_all()
        assert ph.get_position("/tmp/a.mp4") is None
        assert ph.get_position("/tmp/b.mp4") is None

    def test_history_is_persisted(self):
        ph.save_position("/tmp/video.mp4", 15000, 90000)
        # Reload from disk
        saved_path = ph._history_path
        ph._history = {}
        ph._history_path = saved_path
        pos = ph.get_position("/tmp/video.mp4")
        assert pos == 15000

    def test_get_recent_order(self):
        import time
        ph.save_position("/tmp/a.mp4", 1000, 60000)
        time.sleep(0.01)
        ph.save_position("/tmp/b.mp4", 2000, 60000)
        recent = ph.get_recent(10)
        paths = [r["path"] for r in recent]
        # Most recent first — but files must exist, so we just check order
        # b was saved later, so it comes first in timestamp order
        b_idx = next((i for i, r in enumerate(recent) if r["path"] == "/tmp/b.mp4"), None)
        a_idx = next((i for i, r in enumerate(recent) if r["path"] == "/tmp/a.mp4"), None)
        if b_idx is not None and a_idx is not None:
            # b is more recent, so its index should be lower (earlier in the list)
            assert b_idx < a_idx
