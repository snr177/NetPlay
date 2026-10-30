"""
Tests for the subtitle service.
"""

import os
import tempfile
import pytest

from services import subtitle_service


class TestURLValidation:
    def test_valid_http_url(self):
        # Should not raise
        subtitle_service.validate_url("http://example.com/sub.srt")

    def test_valid_https_url(self):
        subtitle_service.validate_url("https://example.com/sub.ass")

    def test_rejects_ftp(self):
        with pytest.raises(subtitle_service.SubtitleError):
            subtitle_service.validate_url("ftp://example.com/sub.srt")

    def test_rejects_file_protocol(self):
        with pytest.raises(subtitle_service.SubtitleError):
            subtitle_service.validate_url("file:///etc/passwd")

    def test_rejects_empty_url(self):
        with pytest.raises(subtitle_service.SubtitleError):
            subtitle_service.validate_url("")

    def test_rejects_url_without_host(self):
        with pytest.raises(subtitle_service.SubtitleError):
            subtitle_service.validate_url("https:///sub.srt")


class TestExtensionValidation:
    def test_valid_srt(self):
        subtitle_service.validate_extension("movie.srt")

    def test_valid_ass(self):
        subtitle_service.validate_extension("movie.ass")

    def test_valid_ssa(self):
        subtitle_service.validate_extension("movie.ssa")

    def test_valid_vtt(self):
        subtitle_service.validate_extension("movie.vtt")

    def test_valid_sub(self):
        subtitle_service.validate_extension("movie.sub")

    def test_invalid_exe(self):
        with pytest.raises(subtitle_service.SubtitleError):
            subtitle_service.validate_extension("malware.exe")

    def test_invalid_pdf(self):
        with pytest.raises(subtitle_service.SubtitleError):
            subtitle_service.validate_extension("document.pdf")

    def test_case_insensitive(self):
        subtitle_service.validate_extension("MOVIE.SRT")


class TestLocalFileValidation:
    def test_missing_file_raises(self):
        with pytest.raises(subtitle_service.SubtitleError):
            subtitle_service.validate_local_file("/nonexistent/path/sub.srt")

    def test_empty_file_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as fh:
            path = fh.name
        try:
            with pytest.raises(subtitle_service.SubtitleError):
                subtitle_service.validate_local_file(path)
        finally:
            os.remove(path)

    def test_valid_srt_file(self):
        with tempfile.NamedTemporaryFile(suffix=".srt", delete=False, mode="w") as fh:
            fh.write("1\n00:00:01,000 --> 00:00:02,000\nHello world\n\n")
            path = fh.name
        try:
            # Should not raise
            subtitle_service.validate_local_file(path)
        finally:
            os.remove(path)

    def test_wrong_extension_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False, mode="w") as fh:
            fh.write("not a subtitle")
            path = fh.name
        try:
            with pytest.raises(subtitle_service.SubtitleError):
                subtitle_service.validate_local_file(path)
        finally:
            os.remove(path)
