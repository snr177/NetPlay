"""
CineShelf player page.
Hosts the VLC video surface, overlay control bar, and keyboard handling.
"""

import os
from typing import Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFileDialog,
    QSizePolicy, QFrame
)
from PySide6.QtCore import Qt, Signal, QTimer, QPoint
from PySide6.QtGui import QFont, QColor, QPalette, QKeyEvent, QMouseEvent

from core.playback_controller import PlaybackController
from core.track_manager import TrackManager
from core.aspect_ratio import AspectRatioManager
from core.keyboard_manager import KeyboardManager
from ui.control_bar import ControlBar
from ui.audio_menu import AudioMenu
from ui.subtitle_menu import SubtitleMenu
from ui.dialogs import SubtitleURLDialog, show_error, show_info
from services import subtitle_service
from services.library_scanner import ScanResult


class OSDLabel(QLabel):
    """On-screen display label that fades after a short delay."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setFont(QFont("Segoe UI", 15, QFont.Bold))
        self.setStyleSheet(
            "color: white; background: rgba(0,0,0,0.65);"
            "padding: 8px 20px; border-radius: 8px;"
        )
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self.hide()

    def show_message(self, text: str, duration_ms: int = 1800) -> None:
        self.setText(text)
        self.adjustSize()
        self.show()
        self._timer.start(duration_ms)


class VideoSurface(QWidget):
    """The native widget that VLC renders into."""

    mouse_moved    = Signal()
    left_clicked   = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setAttribute(Qt.WA_PaintOnScreen)
        self.setAttribute(Qt.WA_NativeWindow)
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor("black"))
        self.setPalette(palette)
        self.setAutoFillBackground(True)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def mouseMoveEvent(self, event: QMouseEvent):
        self.mouse_moved.emit()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.left_clicked.emit()
        super().mousePressEvent(event)


class PlayerPage(QWidget):
    """
    Full player page containing:
    - VideoSurface (black VLC render target)
    - ControlBar overlay
    - OSD labels
    - Audio / subtitle menus
    - Keyboard handler
    """

    back_requested  = Signal()
    next_requested  = Signal()
    prev_requested  = Signal()

    def __init__(self, controller: PlaybackController, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        # Sub-systems
        self.track_manager  = TrackManager(controller.backend)
        self.ratio_manager  = AspectRatioManager(controller.backend)
        self.keyboard_mgr   = KeyboardManager(self)
        self.audio_menu_mgr = AudioMenu(self)
        self.sub_menu_mgr   = SubtitleMenu(self)

        self._controls_hide_timer = QTimer(self)
        self._controls_hide_timer.setSingleShot(True)
        self._controls_hide_timer.setInterval(3000)
        self._controls_hide_timer.timeout.connect(self._hide_controls)

        self._current_result: Optional[ScanResult] = None
        self._playlist: List[ScanResult] = []
        self._playlist_idx: int = -1

        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        # Use absolute positioning for overlay
        self._video = VideoSurface(self)
        self._video.setGeometry(0, 0, self.width(), self.height())

        self._controls = ControlBar(self)
        self._controls.setGeometry(0, self.height() - 100, self.width(), 100)

        self._osd = OSDLabel(self)
        self._osd.setGeometry(0, 0, 200, 50)
        self._osd.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        self._video.setGeometry(0, 0, w, h)
        self._controls.setGeometry(0, h - 105, w, 105)
        # Re-centre OSD
        osd_w = max(200, w // 3)
        self._osd.setFixedWidth(osd_w)
        self._osd.move((w - osd_w) // 2, h // 2 - 30)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self):
        # Controller signals → UI
        self.controller.playing.connect(lambda: self._controls.set_playing(True))
        self.controller.paused.connect(lambda: self._controls.set_playing(False))
        self.controller.stopped.connect(lambda: self._controls.set_playing(False))
        self.controller.end_reached.connect(self._on_end_reached)
        self.controller.error_occurred.connect(self._on_playback_error)
        self.controller.time_updated.connect(self._controls.set_time)

        # Control bar signals → controller
        self._controls.play_pause_clicked.connect(self.controller.toggle_play_pause)
        self._controls.seek_changed.connect(self.controller.seek_to_ms)
        self._controls.volume_changed.connect(self.controller.set_volume)
        self._controls.mute_clicked.connect(self.controller.toggle_mute)
        self._controls.back_clicked.connect(self.back_requested)
        self._controls.fullscreen_clicked.connect(self._toggle_fullscreen)
        self._controls.audio_btn_clicked.connect(self._show_audio_menu)
        self._controls.subtitle_btn_clicked.connect(self._show_subtitle_menu)
        self._controls.aspect_btn_clicked.connect(self._cycle_aspect_ratio)

        # Volume / mute sync
        self.controller.volume_changed.connect(self._controls.set_volume)
        self.controller.mute_changed.connect(self._controls.set_muted)

        # Video surface
        self._video.mouse_moved.connect(self._show_controls)
        self._video.left_clicked.connect(self.controller.toggle_play_pause)

        # Audio / subtitle menus
        self.audio_menu_mgr.track_selected.connect(self._set_audio_track)
        self.sub_menu_mgr.track_selected.connect(self._set_subtitle_track)
        self.sub_menu_mgr.import_file.connect(self._import_subtitle_file)
        self.sub_menu_mgr.import_url.connect(self._import_subtitle_url)

        # Keyboard
        self.keyboard_mgr.action_play_pause.connect(self.controller.toggle_play_pause)
        self.keyboard_mgr.action_seek_forward.connect(self.controller.seek_forward)
        self.keyboard_mgr.action_seek_backward.connect(self.controller.seek_backward)
        self.keyboard_mgr.action_fullscreen.connect(self._toggle_fullscreen)
        self.keyboard_mgr.action_exit_fullscreen.connect(self._exit_fullscreen)
        self.keyboard_mgr.action_next_audio.connect(self._next_audio_track)
        self.keyboard_mgr.action_prev_audio.connect(self._prev_audio_track)
        self.keyboard_mgr.action_next_ratio.connect(self._cycle_aspect_ratio)
        self.keyboard_mgr.action_volume_up.connect(self.controller.increase_volume)
        self.keyboard_mgr.action_volume_down.connect(self.controller.decrease_volume)
        self.keyboard_mgr.action_mute.connect(self.controller.toggle_mute)
        self.keyboard_mgr.action_next_video.connect(self.play_next)
        self.keyboard_mgr.action_prev_video.connect(self.play_prev)

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def play_result(self, result: ScanResult, start_ms: int = 0) -> None:
        """Load and play a ScanResult. Optionally seek to start_ms."""
        self._current_result = result
        ok = self.controller.open_file(result.path)
        if not ok:
            show_error(self, "Playback Error", f"Cannot play:\n{result.path}")
            return

        # Embed VLC into the video surface after loading
        QTimer.singleShot(100, self._embed_vlc)

        if start_ms > 0:
            QTimer.singleShot(600, lambda: self.controller.seek_to_ms(start_ms))

        # Initialise volume
        from app import settings
        self.controller.set_volume(settings.get("volume", 80))

    def _embed_vlc(self):
        """Tell VLC to render into our native widget."""
        wid = int(self._video.winId())
        self.controller.backend.set_hwnd(wid)

    def set_playlist(self, results: List[ScanResult], current_idx: int) -> None:
        self._playlist = results
        self._playlist_idx = current_idx

    def play_next(self) -> None:
        if self._playlist and self._playlist_idx < len(self._playlist) - 1:
            self._playlist_idx += 1
            self.play_result(self._playlist[self._playlist_idx])
            self.next_requested.emit()

    def play_prev(self) -> None:
        if self._playlist and self._playlist_idx > 0:
            self._playlist_idx -= 1
            self.play_result(self._playlist[self._playlist_idx])
            self.prev_requested.emit()

    # ------------------------------------------------------------------
    # Controls visibility
    # ------------------------------------------------------------------

    def _show_controls(self) -> None:
        self._controls.show()
        self._controls_hide_timer.start()
        self.setCursor(Qt.ArrowCursor)

    def _hide_controls(self) -> None:
        if self.controller.is_playing():
            self._controls.hide()
            self.setCursor(Qt.BlankCursor)

    def mouseMoveEvent(self, event: QMouseEvent):
        self._show_controls()
        super().mouseMoveEvent(event)

    # ------------------------------------------------------------------
    # Full screen
    # ------------------------------------------------------------------

    def _toggle_fullscreen(self) -> None:
        window = self.window()
        if window.isFullScreen():
            window.showNormal()
            self._controls.set_fullscreen_icon(False)
        else:
            window.showFullScreen()
            self._controls.set_fullscreen_icon(True)

    def _exit_fullscreen(self) -> None:
        window = self.window()
        if window.isFullScreen():
            window.showNormal()
            self._controls.set_fullscreen_icon(False)

    # ------------------------------------------------------------------
    # Audio tracks
    # ------------------------------------------------------------------

    def _show_audio_menu(self) -> None:
        tracks = self.track_manager.get_audio_tracks()
        current = self.track_manager.get_current_audio_track()
        self.audio_menu_mgr.populate(tracks, current)
        btn_pos = self._controls.mapToGlobal(self._controls._audio_btn.pos())
        self.audio_menu_mgr.get_menu().exec(btn_pos)

    def _set_audio_track(self, track_id: int) -> None:
        self.track_manager.set_audio_track(track_id)
        tracks = self.track_manager.get_audio_tracks()
        name = next((t["name"] for t in tracks if t["id"] == track_id), f"Track {track_id}")
        self._osd.show_message(f"🎵 {name}")

    def _next_audio_track(self) -> None:
        track = self.track_manager.next_audio_track()
        if track:
            self._osd.show_message(f"🎵 {track['name']}")

    def _prev_audio_track(self) -> None:
        track = self.track_manager.previous_audio_track()
        if track:
            self._osd.show_message(f"🎵 {track['name']}")

    # ------------------------------------------------------------------
    # Subtitle tracks
    # ------------------------------------------------------------------

    def _show_subtitle_menu(self) -> None:
        tracks = self.controller.backend.get_subtitle_tracks()
        current = self.controller.backend.get_subtitle_track()
        self.sub_menu_mgr.populate(tracks, current)
        btn_pos = self._controls.mapToGlobal(self._controls._sub_btn.pos())
        self.sub_menu_mgr.get_menu().exec(btn_pos)

    def _set_subtitle_track(self, track_id: int) -> None:
        self.controller.backend.set_subtitle_track(track_id)
        if track_id == -1:
            self._osd.show_message("💬 Subtitles off")
        else:
            tracks = self.controller.backend.get_subtitle_tracks()
            name = next((t["name"] for t in tracks if t["id"] == track_id), f"Track {track_id}")
            self._osd.show_message(f"💬 {name}")

    def _import_subtitle_file(self) -> None:
        exts = " ".join(f"*{e}" for e in subtitle_service.ALLOWED_EXTENSIONS)
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Subtitle File", "",
            f"Subtitle files ({exts});;All files (*)",
        )
        if not path:
            return
        try:
            subtitle_service.validate_local_file(path)
        except subtitle_service.SubtitleError as exc:
            show_error(self, "Invalid Subtitle", str(exc))
            return
        ok = self.controller.backend.load_subtitle_file(path)
        if ok:
            self._osd.show_message(f"💬 {os.path.basename(path)}")
        else:
            show_error(self, "Subtitle Error", "Could not load the subtitle file.")

    def _import_subtitle_url(self) -> None:
        dlg = SubtitleURLDialog(self)
        if dlg.exec() != SubtitleURLDialog.Accepted:
            return
        url = dlg.get_url()
        if not url:
            return
        try:
            local_path = subtitle_service.download_subtitle(url)
        except subtitle_service.SubtitleError as exc:
            show_error(self, "Subtitle Download Failed", str(exc))
            return
        ok = self.controller.backend.load_subtitle_file(local_path)
        if ok:
            self._osd.show_message(f"💬 {os.path.basename(local_path)}")
        else:
            show_error(self, "Subtitle Error", "Could not load the downloaded subtitle file.")

    # ------------------------------------------------------------------
    # Aspect ratio
    # ------------------------------------------------------------------

    def _cycle_aspect_ratio(self) -> None:
        mode = self.ratio_manager.cycle_next()
        self._osd.show_message(f"⊞ {mode}")

    # ------------------------------------------------------------------
    # Playback events
    # ------------------------------------------------------------------

    def _on_end_reached(self) -> None:
        from services import playback_history
        if self._current_result:
            playback_history.clear(self._current_result.path)
        self.play_next()

    def _on_playback_error(self) -> None:
        show_error(
            self, "Playback Error",
            "VLC encountered an error during playback.\n"
            "The file may be corrupt or use an unsupported codec."
        )

    # ------------------------------------------------------------------
    # Keyboard events
    # ------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent):
        if not self.keyboard_mgr.handle_key_press(event):
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Save position on close / back
    # ------------------------------------------------------------------

    def save_position(self) -> None:
        from services import playback_history
        if self._current_result:
            pos = self.controller.backend.get_time_ms()
            dur = self.controller.backend.get_duration_ms()
            if pos > 5000:
                playback_history.save_position(self._current_result.path, pos, dur)
