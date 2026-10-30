"""
CineShelf subtitle service.
Downloads and validates external subtitle files.
"""

import os
import hashlib
import urllib.parse
from pathlib import Path
from typing import Optional

import requests

from app import settings


ALLOWED_EXTENSIONS = {".srt", ".ass", ".ssa", ".vtt", ".sub"}
MAX_BYTES = settings.get("max_subtitle_download_bytes", 5 * 1024 * 1024)
TIMEOUT = settings.get("subtitle_download_timeout", 15)


class SubtitleError(Exception):
    """Raised when a subtitle operation fails."""


def validate_url(url: str) -> None:
    """
    Raise SubtitleError when the URL is not a valid HTTP/HTTPS subtitle URL.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SubtitleError("Only HTTP and HTTPS URLs are supported.")
    if not parsed.netloc:
        raise SubtitleError("The URL does not contain a valid host.")


def validate_extension(filename: str) -> None:
    """Raise SubtitleError when the file extension is not a subtitle format."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise SubtitleError(
            f"Unsupported subtitle format '{ext}'. "
            f"Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )


def download_subtitle(url: str) -> str:
    """
    Download a subtitle file from a URL.
    Return the local path where the file was saved.
    Raise SubtitleError on any failure.
    """
    validate_url(url)

    # Determine filename from URL path
    parsed = urllib.parse.urlparse(url)
    url_path = parsed.path.rstrip("/")
    filename = os.path.basename(url_path) if url_path else "subtitle"
    if not filename:
        filename = "subtitle"

    validate_extension(filename)

    temp_dir = settings.get("subtitle_temp_dir", "/tmp/cineshelf_subtitles")
    os.makedirs(temp_dir, exist_ok=True)

    # Use a hash of the URL as the local file name to avoid conflicts
    url_hash = hashlib.sha1(url.encode()).hexdigest()[:12]
    ext = Path(filename).suffix.lower()
    local_path = os.path.join(temp_dir, f"{url_hash}{ext}")

    # If already cached, return the cached copy
    if os.path.exists(local_path):
        return local_path

    try:
        response = requests.get(
            url,
            timeout=TIMEOUT,
            stream=True,
            headers={"User-Agent": "CineShelf/1.0"},
        )
        response.raise_for_status()

        content_length = int(response.headers.get("Content-Length", 0))
        if content_length and content_length > MAX_BYTES:
            raise SubtitleError(
                f"The subtitle file is too large ({content_length // 1024} KB). "
                f"Maximum allowed size is {MAX_BYTES // 1024} KB."
            )

        downloaded = 0
        with open(local_path, "wb") as fh:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    downloaded += len(chunk)
                    if downloaded > MAX_BYTES:
                        fh.close()
                        os.remove(local_path)
                        raise SubtitleError("The subtitle file exceeded the size limit.")
                    fh.write(chunk)

    except requests.exceptions.Timeout:
        raise SubtitleError("The download timed out. Check your internet connection.")
    except requests.exceptions.ConnectionError as exc:
        raise SubtitleError(f"Connection error: {exc}")
    except requests.exceptions.HTTPError as exc:
        raise SubtitleError(f"HTTP error: {exc}")
    except SubtitleError:
        raise
    except Exception as exc:
        raise SubtitleError(f"Download failed: {exc}") from exc

    return local_path


def validate_local_file(path: str) -> None:
    """
    Raise SubtitleError when the local file is not a valid subtitle file.
    """
    if not os.path.exists(path):
        raise SubtitleError(f"File not found: {path}")
    validate_extension(path)
    size = os.path.getsize(path)
    if size == 0:
        raise SubtitleError("The subtitle file is empty.")
    if size > MAX_BYTES:
        raise SubtitleError(f"The subtitle file is too large ({size // 1024} KB).")
