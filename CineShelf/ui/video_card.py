"""
CineShelf video card widget.
Displays a single media file in the library grid.
"""

from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QSizePolicy
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QFont, QPainter, QColor, QFontMetrics

from services.library_scanner import ScanResult


_THUMB_W = 200
_THUMB_H = 112


class VideoCard(QFrame):
    """
    A clickable poster card showing video thumbnail, title, and metadata.
    Emits clicked(result) when the user selects the card.
    """

    clicked = Signal(object)   # ScanResult

    def __init__(self, result: ScanResult, parent=None):
        super().__init__(parent)
        self.result = result
        self.setObjectName("video_card")
        self.setFixedSize(220, 180)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Thumbnail
        self._thumb_label = QLabel()
        self._thumb_label.setFixedSize(_THUMB_W, _THUMB_H)
        self._thumb_label.setAlignment(Qt.AlignCenter)
        self._thumb_label.setScaledContents(False)
        self._set_placeholder_thumb()

        thumb_container = QFrame()
        thumb_container.setFixedSize(_THUMB_W, _THUMB_H)
        thumb_container.setStyleSheet("background: #0A0A0A; border-radius: 6px 6px 0 0;")
        tl = QVBoxLayout(thumb_container)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.addWidget(self._thumb_label)

        # Info panel
        info_frame = QFrame()
        info_frame.setStyleSheet(
            "background: #151515; border-radius: 0 0 6px 6px; padding: 4px 8px;"
        )
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(8, 6, 8, 6)
        info_layout.setSpacing(2)

        # Title
        title = QLabel(self._truncate(self.result.name, 24))
        title.setFont(QFont("Segoe UI", 10, QFont.Medium))
        title.setStyleSheet("color: #E8E8E8;")
        title.setToolTip(self.result.name)

        # Meta
        meta_parts = []
        if self.result.duration_label():
            meta_parts.append(self.result.duration_label())
        if self.result.resolution:
            meta_parts.append(self.result.resolution)
        if self.result.extension:
            meta_parts.append(self.result.extension.upper().lstrip("."))
        meta_text = "  ·  ".join(meta_parts) if meta_parts else self.result.extension.lstrip(".")

        meta = QLabel(meta_text)
        meta.setFont(QFont("Segoe UI", 8))
        meta.setStyleSheet("color: #777777;")

        info_layout.addWidget(title)
        info_layout.addWidget(meta)

        layout.addWidget(thumb_container)
        layout.addWidget(info_frame)

    def _set_placeholder_thumb(self):
        """Draw a dark placeholder with a play icon."""
        pixmap = QPixmap(_THUMB_W, _THUMB_H)
        pixmap.fill(QColor("#111111"))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#2A2A2A"))
        # Draw a simple play triangle
        from PySide6.QtGui import QPolygon
        from PySide6.QtCore import QPoint
        cx, cy = _THUMB_W // 2, _THUMB_H // 2
        size = 22
        tri = QPolygon([
            QPoint(cx - size // 2, cy - size // 2 - 4),
            QPoint(cx - size // 2, cy + size // 2 + 4),
            QPoint(cx + size, cy),
        ])
        painter.drawPolygon(tri)
        painter.end()
        self._thumb_label.setPixmap(pixmap)

    # ------------------------------------------------------------------
    # Thumbnail update
    # ------------------------------------------------------------------

    def set_thumbnail(self, thumb_path: str) -> None:
        """Set the thumbnail from a file path."""
        if not thumb_path:
            return
        pixmap = QPixmap(thumb_path)
        if pixmap.isNull():
            return
        scaled = pixmap.scaled(
            _THUMB_W, _THUMB_H,
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation,
        )
        # Centre-crop
        if scaled.width() > _THUMB_W or scaled.height() > _THUMB_H:
            x = (scaled.width() - _THUMB_W) // 2
            y = (scaled.height() - _THUMB_H) // 2
            scaled = scaled.copy(x, y, _THUMB_W, _THUMB_H)
        self._thumb_label.setPixmap(scaled)

    # ------------------------------------------------------------------
    # Metadata update (called when metadata is loaded asynchronously)
    # ------------------------------------------------------------------

    def update_result(self, result: ScanResult) -> None:
        self.result = result
        # Rebuild UI would be heavy; just refresh the card minimally
        self.update()

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.result)
        super().mousePressEvent(event)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _truncate(text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 1] + "…"
