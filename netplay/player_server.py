"""Serve the video player, local video metadata, and range-enabled media files."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from urllib.parse import parse_qs, quote, unquote, urlsplit

try:
    import av
except ImportError:
    av = None


ROOT = Path(__file__).resolve().parent
VIDEO_DIR = Path("/home/ubuntu/Downloads")
CACHE_DIR = Path.home() / ".cache" / "cinema-player"
PORT = 8765
VIDEO_EXTENSIONS = {
    ".3g2", ".3gp", ".amv", ".asf", ".avi", ".divx", ".f4v", ".flv",
    ".m2v", ".m2ts", ".m4v", ".mkv", ".mod", ".mov", ".mp4", ".mpe",
    ".mpeg", ".mpg", ".mts", ".mxf", ".ogv", ".qt", ".rm", ".rmvb",
    ".ts", ".vob", ".webm", ".wmv",
}
RANGE_PATTERN = re.compile(r"bytes=(\d*)-(\d*)$")
CHUNK_SIZE = 1024 * 1024
MAX_RANGE_SIZE = 8 * 1024 * 1024
COMPATIBILITY_JOBS: dict[str, dict] = {}
COMPATIBILITY_JOBS_LOCK = Lock()
COMPATIBILITY_EXECUTOR = ThreadPoolExecutor(max_workers=1)


def compatibility_key(path: Path) -> str:
    stat = path.stat()
    fingerprint = f"{path.relative_to(VIDEO_DIR)}\0{stat.st_size}\0{stat.st_mtime_ns}"
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()


def describe_video(
    path: Path,
    media_path: Path | None = None,
    media_url: str | None = None,
) -> dict:
    relative_path = path.relative_to(VIDEO_DIR).as_posix()
    item = {
        "name": path.name,
        "path": relative_path,
        "url": media_url or f"/media/{quote(relative_path, safe='/')}",
        "size": path.stat().st_size,
        "audioTracks": [],
        "compatible": media_url is not None,
    }
    metadata_path = media_path or path
    if av is None:
        item["metadataError"] = "Install PyAV to read audio track metadata."
        return item

    try:
        with av.open(str(metadata_path)) as container:
            for stream in container.streams:
                if stream.type != "audio":
                    continue
                context = stream.codec_context
                metadata = stream.metadata or {}
                layout = getattr(context, "layout", None)
                language = metadata.get("language", "").strip()
                label = metadata.get("title", "").strip()
                if not label:
                    label = (
                        language
                        if language and language.lower() not in {"und", "unknown"}
                        else f"Audio {len(item['audioTracks']) + 1}"
                    )
                item["audioTracks"].append(
                    {
                        "index": stream.index,
                        "label": label,
                        "language": language,
                        "codec": context.name.upper(),
                        "channels": getattr(context, "channels", None),
                        "layout": getattr(layout, "name", "") if layout else "",
                        "sampleRate": getattr(context, "sample_rate", None),
                        "bitRate": getattr(context, "bit_rate", None),
                    }
                )
    except (OSError, av.error.FFmpegError) as error:
        item["metadataError"] = f"Could not inspect audio metadata: {error}"
    return item


def compatibility_cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.mp4"


def compatibility_status(key: str) -> dict:
    with COMPATIBILITY_JOBS_LOCK:
        job = dict(COMPATIBILITY_JOBS.get(key, {"status": "unknown"}))
    job["id"] = key
    if job["status"] == "ready":
        job["url"] = f"/compatible/{key}.mp4"
    return job


def transcode_for_browser(source: Path, key: str) -> None:
    temporary_path = CACHE_DIR / f"{key}.tmp.mp4"
    target_path = compatibility_cache_path(key)
    try:
        with COMPATIBILITY_JOBS_LOCK:
            COMPATIBILITY_JOBS[key].update(status="converting", progress=0)
        if av is None:
            raise RuntimeError("PyAV is required to prepare browser-compatible video.")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        temporary_path.unlink(missing_ok=True)
        with av.open(str(source)) as input_container:
            input_video = next(
                (stream for stream in input_container.streams if stream.type == "video"),
                None,
            )
            input_audio = next(
                (stream for stream in input_container.streams if stream.type == "audio"),
                None,
            )
            if input_video is None:
                raise RuntimeError("The selected file has no video stream.")

            video_context = input_video.codec_context
            scale = min(1.0, 1920 / video_context.width, 1080 / video_context.height)
            output_width = max(2, int(video_context.width * scale) // 2 * 2)
            output_height = max(2, int(video_context.height * scale) // 2 * 2)
            duration = (
                input_container.duration / av.time_base
                if input_container.duration
                else 0
            )
            frame_rate = input_video.average_rate or 24
            output_container = av.open(str(temporary_path), "w", format="mp4")
            output_video = output_container.add_stream("libx264", rate=frame_rate)
            output_video.width = output_width
            output_video.height = output_height
            output_video.pix_fmt = "yuv420p"
            output_video.bit_rate = 5_000_000
            output_video.options = {
                "preset": "ultrafast",
                "tune": "zerolatency",
                "crf": "24",
                "bf": "0",
                "level": "4.2",
            }
            output_audio = None
            if input_audio is not None:
                output_audio = output_container.add_stream(
                    "libmp3lame",
                    rate=input_audio.codec_context.sample_rate,
                )
                output_audio.layout = "stereo"
                output_audio.bit_rate = 128_000

            input_streams = [input_video]
            if input_audio is not None:
                input_streams.append(input_audio)
            last_progress = -1
            try:
                for packet in input_container.demux(*input_streams):
                    if packet.pts is None:
                        continue
                    for frame in packet.decode():
                        if packet.stream.type == "video":
                            timestamp = (
                                float(frame.pts * frame.time_base)
                                if frame.pts is not None
                                else 0
                            )
                            frame = frame.reformat(
                                width=output_width,
                                height=output_height,
                                format="yuv420p",
                            )
                            encoded_packets = output_video.encode(frame)
                        else:
                            timestamp = (
                                float(frame.pts * frame.time_base)
                                if frame.pts is not None
                                else 0
                            )
                            encoded_packets = output_audio.encode(frame)
                        for encoded_packet in encoded_packets:
                            output_container.mux(encoded_packet)
                        if duration:
                            progress = min(99, int(timestamp * 100 / duration))
                            if progress > last_progress:
                                last_progress = progress
                                with COMPATIBILITY_JOBS_LOCK:
                                    COMPATIBILITY_JOBS[key]["progress"] = progress
                for output_stream in (output_video, output_audio):
                    if output_stream is None:
                        continue
                    for encoded_packet in output_stream.encode(None):
                        output_container.mux(encoded_packet)
            finally:
                output_container.close()

        os.replace(temporary_path, target_path)
        with COMPATIBILITY_JOBS_LOCK:
            COMPATIBILITY_JOBS[key].update(status="ready", progress=100)
    except Exception as error:
        temporary_path.unlink(missing_ok=True)
        with COMPATIBILITY_JOBS_LOCK:
            COMPATIBILITY_JOBS[key].update(status="error", error=str(error))
        print(f"[player] Compatibility conversion failed for {source}: {error}", file=sys.stderr)


class PlayerHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:
        request = urlsplit(self.path)
        if request.path == "/api/videos":
            self._send_video_catalog()
        elif request.path == "/api/compatibility":
            self._send_compatibility_status(request.query)
        elif request.path.startswith("/compatible/"):
            self._send_compatible_media(request.path.removeprefix("/compatible/"))
        elif request.path.startswith("/media/"):
            self._send_media(request.path.removeprefix("/media/"))
        elif request.path in {"/", "/player.html"}:
            self.path = "/player.html"
            super().do_GET()
        else:
            self.send_error(404, "Not found.")

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/api/compatibility":
            self.send_error(404, "Not found.")
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if not 0 < content_length <= 4096:
                raise ValueError("Invalid request size.")
            request = json.loads(self.rfile.read(content_length))
            relative_path = request.get("path") if isinstance(request, dict) else None
            if not isinstance(relative_path, str):
                raise ValueError("A video path is required.")
        except (ValueError, json.JSONDecodeError) as error:
            self._send_json({"error": str(error)}, 400)
            return

        source = self._resolve_video_path(relative_path)
        if source is None:
            self._send_json({"error": "Video file not found."}, 404)
            return
        if av is None:
            self._send_json(
                {"error": "PyAV is unavailable; browser compatibility conversion cannot run."},
                503,
            )
            return

        key = compatibility_key(source)
        if compatibility_cache_path(key).is_file():
            with COMPATIBILITY_JOBS_LOCK:
                COMPATIBILITY_JOBS[key] = {"status": "ready", "progress": 100}
        else:
            with COMPATIBILITY_JOBS_LOCK:
                job = COMPATIBILITY_JOBS.get(key)
                if job is None or job.get("status") == "error":
                    COMPATIBILITY_JOBS[key] = {"status": "queued", "progress": 0}
                    COMPATIBILITY_EXECUTOR.submit(transcode_for_browser, source, key)
        job = compatibility_status(key)
        self._send_json(job, 200 if job["status"] == "ready" else 202)

    def do_HEAD(self) -> None:
        request = urlsplit(self.path)
        if request.path.startswith("/compatible/"):
            self._send_compatible_media(request.path.removeprefix("/compatible/"), True)
        elif request.path.startswith("/media/"):
            self._send_media(
                request.path.removeprefix("/media/"),
                head_only=True,
            )
        elif request.path in {"/", "/player.html"}:
            self.path = "/player.html"
            super().do_HEAD()
        else:
            self.send_error(404, "Not found.")

    def _send_video_catalog(self) -> None:
        if not VIDEO_DIR.is_dir():
            self._send_json({"error": f"Video folder not found: {VIDEO_DIR}"}, 404)
            return

        try:
            videos = sorted(
                (
                    path
                    for path in VIDEO_DIR.rglob("*")
                    if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
                ),
                key=lambda path: (path.name.casefold(), str(path).casefold()),
            )
            result = {
                "folder": str(VIDEO_DIR),
                "videos": [],
            }
            for path in videos:
                key = compatibility_key(path)
                cache_path = compatibility_cache_path(key)
                if cache_path.is_file():
                    result["videos"].append(
                        describe_video(
                            path,
                            media_path=cache_path,
                            media_url=f"/compatible/{key}.mp4",
                        )
                    )
                else:
                    result["videos"].append(describe_video(path))
        except OSError as error:
            self._send_json({"error": f"Could not scan video folder: {error}"}, 500)
            return
        self._send_json(result)

    def _send_compatibility_status(self, query: str) -> None:
        key = parse_qs(query).get("id", [""])[0]
        if re.fullmatch(r"[a-f0-9]{64}", key) is None:
            self._send_json({"error": "Invalid conversion ID."}, 400)
            return
        self._send_json(compatibility_status(key))

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _resolve_video_path(self, relative_path: str) -> Path | None:
        decoded_path = unquote(relative_path)
        try:
            path = (VIDEO_DIR / decoded_path).resolve(strict=True)
            path.relative_to(VIDEO_DIR.resolve(strict=True))
        except (OSError, ValueError):
            return None
        if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
            return None
        return path

    def _send_media(self, relative_path: str, head_only: bool = False) -> None:
        path = self._resolve_video_path(relative_path)
        if path is None:
            self.send_error(404, "Video file not found.")
            return
        self._send_media_file(path, head_only)

    def _send_compatible_media(self, filename: str, head_only: bool = False) -> None:
        match = re.fullmatch(r"([a-f0-9]{64})\.mp4", filename)
        if match is None:
            self.send_error(404, "Video file not found.")
            return
        path = compatibility_cache_path(match.group(1))
        if not path.is_file():
            self.send_error(404, "Compatible video is not ready.")
            return
        self._send_media_file(path, head_only)

    def _send_media_file(self, path: Path, head_only: bool = False) -> None:
        try:
            file_size = path.stat().st_size
            range_header = self.headers.get("Range")
            start = 0
            end = file_size - 1
            status = 200

            if range_header:
                match = RANGE_PATTERN.fullmatch(range_header.strip())
                if match is None or file_size == 0:
                    self._send_range_error(file_size)
                    return

                first, last = match.groups()
                if not first:
                    suffix_length = int(last or 0)
                    if suffix_length <= 0:
                        self._send_range_error(file_size)
                        return
                    start = max(0, file_size - suffix_length)
                else:
                    start = int(first)
                    if last:
                        end = int(last)

                if start >= file_size or end < start:
                    self._send_range_error(file_size)
                    return
                end = min(end, file_size - 1)
                end = min(end, start + MAX_RANGE_SIZE - 1)
                status = 206

            length = end - start + 1 if file_size else 0
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "no-store")
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.end_headers()
            if head_only:
                return

            with path.open("rb") as media_file:
                media_file.seek(start)
                remaining = length
                while remaining:
                    chunk = media_file.read(min(CHUNK_SIZE, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except OSError as error:
            self.log_error("Could not stream %s: %s", path, error)
            self.close_connection = True

    def _send_range_error(self, file_size: int) -> None:
        self.send_response(416)
        self.send_header("Content-Range", f"bytes */{file_size}")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format: str, *args) -> None:
        sys.stderr.write(
            f"[player] {self.address_string()} - {format % args}\n"
        )


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), PlayerHandler)
    print(f"Video player: http://localhost:{PORT}/")
    print(f"Video library: {VIDEO_DIR}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping video player server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()