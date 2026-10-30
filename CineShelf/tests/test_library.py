"""
Tests for the library scanner and scan result helpers.
"""

import os
import tempfile
import pytest

from services.library_scanner import ScanResult


class TestScanResult:
    def test_filename_extraction(self):
        result = ScanResult("/home/user/Movies/my_video.mp4")
        assert result.filename == "my_video.mp4"
        assert result.name == "my_video"
        assert result.extension == ".mp4"

    def test_extension_is_lowercase(self):
        result = ScanResult("/home/user/Movies/MY_VIDEO.MKV")
        assert result.extension == ".mkv"

    def test_duration_label_seconds(self):
        result = ScanResult("/tmp/test.mp4")
        result.duration_ms = 95000  # 1m 35s
        assert result.duration_label() == "1:35"

    def test_duration_label_hours(self):
        result = ScanResult("/tmp/test.mp4")
        result.duration_ms = 7384000  # 2h 3m 4s
        assert result.duration_label() == "2:03:04"

    def test_duration_label_zero(self):
        result = ScanResult("/tmp/test.mp4")
        result.duration_ms = 0
        assert result.duration_label() == ""

    def test_size_label_mb(self):
        result = ScanResult("/tmp/test.mp4")
        result.size_bytes = 52428800  # 50 MB
        assert "50" in result.size_label()
        assert "MB" in result.size_label()

    def test_size_label_gb(self):
        result = ScanResult("/tmp/test.mp4")
        result.size_bytes = 2 * 1024 * 1024 * 1024  # 2 GB
        assert "GB" in result.size_label()

    def test_size_label_zero(self):
        result = ScanResult("/tmp/test.mp4")
        result.size_bytes = 0
        assert result.size_label() == ""

    def test_container_from_extension(self):
        result = ScanResult("/tmp/video.mkv")
        assert result.container == "mkv"


class TestLibraryScannerUnit:
    """Unit tests that do not require a running Qt event loop."""

    def test_scan_result_defaults(self):
        r = ScanResult("/tmp/video.avi")
        assert r.thumbnail_path == ""
        assert r.resolution == ""
        assert r.video_codec == ""
        assert r.audio_codec == ""
