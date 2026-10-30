"""
CineShelf player control bar.
Displayed over the video area and hidden during inactivity.
"""

from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QSlider,
    QPushButton, QLabel, QSizePolicy, QWidget
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont


def _ms_to_label(ms: int) -> str:
    """Convert milliseconds to a H:MM:SS or M:SS label."""
    if ms < 0:
        ms = 0
    total_s = ms // 1000
    hours = total_s // 3600
    minutes = (total_s % 3600) // 60
    seconds = total_s % 60
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


class ControlBar(QFrame):
    """
    Overlay control bar for the video player.

    Signals
    -------
    play_pause_clicked
    seek_changed(ms)
    volume_changed(int)
    mute_clicked
    fullscreen_clicked
    back_clicked
    audio_btn_clicked
    subtitle_btn_clicked
    aspect_btn_clicked
    """

    play_pause_clicked    = Signal()
    seek_changed          = Signal(int)    # new position in ms
    volume_changed        = Signal(int)
    mute_clicked          = Signal()
    fullscreen_clicked    = Signal()
    back_clicked          = Signal()
    audio_btn_clicked     = Signal()
    subtitle_btn_clicked  = Signal()
    aspect_btn_clicked    = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("control_bar")
        self._duration_ms: int = 0
        self._is_seeking: bool = False

        self._build_ui()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Seek slider row
        seek_row = QHBoxLayout()
        seek_row.setContentsMargins(16, 8, 16, 0)

        self._time_label = QLabel("0:00")
        self._time_label.setFont(QFont("Segoe UI", 10))
        self._time_label.setStyleSheet("color: #CCCCCC; min-width: 50px;")
        self._time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._seek_bar = QSlider(Qt.Horizontal)
        self._seek_bar.setObjectName("seek_bar")
        self._seek_bar.setRange(0, 1000)
        self._seek_bar.setValue(0)
        self._seek_bar.setCursor(Qt.PointingHandCursor)

        self._duration_label = QLabel("0:00")
        self._duration_label.setFont(QFont("Segoe UI", 10))
        self._duration_label.setStyleSheet("color: #CCCCCC; min-width: 50px;")
        self._duration_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        seek_row.addWidget(self._time_label)
        seek_row.addWidget(self._seek_bar)
        seek_row.addWidget(self._duration_label)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(12, 4, 12, 10)
        btn_row.setSpacing(4)

        # Left: back button
        self._back_btn = self._make_btn("⟵", "Back to library", self.back_clicked)

        # Centre: playback controls
        self._play_btn = self._make_btn("▶", "Play / Pause", self.play_pause_clicked, wide=True)

        # Volume
        self._mute_btn = self._make_btn("🔊", "Mute / Unmute", self.mute_clicked)
        self._vol_slider = QSlider(Qt.Horizontal)
        self._vol_slider.setRange(0, 200)
        self._vol_slider.setValue(80)
        self._vol_slider.setFixedWidth(90)
        self._vol_slider.setCursor(Qt.PointingHandCursor)
        self._vol_slider.setToolTip("Volume")

        # Right-side controls
        self._audio_btn    = self._make_btn("🎵", "Audio track",    self.audio_btn_clicked)
        self._sub_btn      = self._make_btn("💬", "Subtitles",      self.subtitle_btn_clicked)
        self._ratio_btn    = self._make_btn("⊞", "Aspect ratio",   self.aspect_btn_clicked)
        self._fs_btn       = self._make_btn("⛶", "Full screen",    self.fullscreen_clicked)

        btn_row.addWidget(self._back_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self._play_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self._mute_btn)
        btn_row.addWidget(self._vol_slider)
        btn_row.addSpacing(12)
        btn_row.addWidget(self._audio_btn)
        btn_row.addWidget(self._sub_btn)
        btn_row.addWidget(self._ratio_btn)
        btn_row.addWidget(self._fs_btn)

        outer.addLayout(seek_row)
        outer.addLayout(btn_row)

        # Connections
        self._seek_bar.sliderPressed.connect(self._on_seek_press)
        self._seek_bar.sliderReleased.connect(self._on_seek_release)
        self._vol_slider.valueChanged.connect(self.volume_changed.emit)

    def _make_btn(self, icon: str, tip: str, signal: Signal, wide: bool = False) -> QPushButton:
        btn = QPushButton(icon)
        btn.setObjectName("icon_btn")
        btn.setToolTip(tip)
        btn.setCursor(Qt.PointingHandCursor)
        if wide:
            btn.setFixedSize(40, 36)
            btn.setFont(QFont("Segoe UI", 16))
        else:
            btn.setFixedSize(34, 34)
            btn.setFont(QFont("Segoe UI", 14))
        btn.clicked.connect(signal.emit)
        return btn

    # ------------------------------------------------------------------
    # Public update API
    # ------------------------------------------------------------------

    def set_playing(self, playing: bool) -> None:
        self._play_btn.setText("⏸" if playing else "▶")

    def set_time(self, current_ms: int, duration_ms: int) -> None:
        self._duration_ms = duration_ms
        self._time_label.setText(_ms_to_label(current_ms))
        self._duration_label.setText(_ms_to_label(duration_ms))
        if not self._is_seeking and duration_ms > 0:
            pos = int(current_ms / duration_ms * 1000)
            self._seek_bar.blockSignals(True)
            self._seek_bar.setValue(pos)
            self._seek_bar.blockSignals(False)

    def set_volume(self, volume: int) -> None:
        self._vol_slider.blockSignals(True)
        self._vol_slider.setValue(volume)
        self._vol_slider.blockSignals(False)

    def set_muted(self, muted: bool) -> None:
        self._mute_btn.setText("🔇" if muted else "🔊")

    def set_fullscreen_icon(self, is_fullscreen: bool) -> None:
        self._fs_btn.setText("⊡" if is_fullscreen else "⛶")

    # ------------------------------------------------------------------
    # Seek slider
    # ------------------------------------------------------------------

    def _on_seek_press(self) -> None:
        self._is_seeking = True

    def _on_seek_release(self) -> None:
        self._is_seeking = False
        if self._duration_ms > 0:
            pos_ms = int(self._seek_bar.value() / 1000 * self._duration_ms)
            self.seek_changed.emit(pos_ms)
