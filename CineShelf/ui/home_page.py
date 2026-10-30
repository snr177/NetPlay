"""
CineShelf home / library page.
"""

import os
from typing import List, Optional

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QFrame, QGridLayout, QFileDialog,
    QSizePolicy, QSpacerItem
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont

from services.library_scanner import ScanResult, LibraryScanner
from services.metadata_service import MetadataService
from services.thumbnail_service import ThumbnailService
from ui.video_card import VideoCard
from app import settings


class HomePage(QWidget):
    """
    Library home screen.
    Shows recently played, all videos, and a search bar.
    Emits play_requested(result) when the user selects a video.
    """

    play_requested = Signal(object)   # ScanResult

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_results: List[ScanResult] = []
        self._cards: dict = {}   # path → VideoCard
        self._current_folder: str = settings.get("media_folder", "")

        self._scanner    = LibraryScanner(self)
        self._meta_svc   = MetadataService(self)
        self._thumb_svc  = ThumbnailService(self)

        self._build_ui()
        self._connect_signals()

        # Auto-scan on startup
        QTimer.singleShot(200, self._refresh_library)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- Sidebar ---
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 24, 12, 24)
        sidebar_layout.setSpacing(4)

        logo = QLabel("🎬 CineShelf")
        logo.setObjectName("title_label")
        logo.setFont(QFont("Segoe UI", 15, QFont.Bold))
        sidebar_layout.addWidget(logo)
        sidebar_layout.addSpacing(24)

        self._sidebar_btns: dict = {}
        for name, icon in [("Library", "🗂"), ("Recently Played", "🕐"), ("Settings", "⚙")]:
            btn = QPushButton(f"  {icon}  {name}")
            btn.setObjectName("sidebar_btn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setCheckable(False)
            btn.clicked.connect(lambda checked, n=name: self._on_sidebar_click(n))
            sidebar_layout.addWidget(btn)
            self._sidebar_btns[name] = btn

        sidebar_layout.addStretch()

        # Folder button
        folder_btn = QPushButton("📁  Change Folder")
        folder_btn.setObjectName("sidebar_btn")
        folder_btn.setCursor(Qt.PointingHandCursor)
        folder_btn.clicked.connect(self._change_folder)
        sidebar_layout.addWidget(folder_btn)

        refresh_btn = QPushButton("🔄  Refresh Library")
        refresh_btn.setObjectName("sidebar_btn")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(self._refresh_library)
        sidebar_layout.addWidget(refresh_btn)

        # --- Main content area ---
        content_area = QWidget()
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(24, 16, 24, 16)
        content_layout.setSpacing(16)

        # Top bar: search
        top_row = QHBoxLayout()
        self._search_bar = QLineEdit()
        self._search_bar.setPlaceholderText("🔍  Search videos…")
        self._search_bar.setFixedHeight(36)
        self._search_bar.textChanged.connect(self._on_search)
        top_row.addWidget(self._search_bar)
        content_layout.addLayout(top_row)

        # Status label
        self._status_label = QLabel("Scanning library…")
        self._status_label.setStyleSheet("color: #777777; font-size: 12px;")
        content_layout.addWidget(self._status_label)

        # Scroll area for cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        self._grid_widget = QWidget()
        self._grid_layout = QGridLayout(self._grid_widget)
        self._grid_layout.setSpacing(16)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)
        self._grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        scroll.setWidget(self._grid_widget)
        content_layout.addWidget(scroll)

        root.addWidget(sidebar)
        root.addWidget(content_area)

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _connect_signals(self):
        self._scanner.scan_started.connect(
            lambda: self._status_label.setText("Scanning library…")
        )
        self._scanner.scan_finished.connect(self._on_scan_finished)
        self._scanner.scan_error.connect(
            lambda msg: self._status_label.setText(f"Error: {msg}")
        )
        self._meta_svc.metadata_ready.connect(self._on_metadata_ready)
        self._thumb_svc.thumbnail_ready.connect(self._on_thumbnail_ready)

    # ------------------------------------------------------------------
    # Library management
    # ------------------------------------------------------------------

    def _refresh_library(self) -> None:
        self._all_results.clear()
        self._cards.clear()
        self._clear_grid()
        self._scanner.scan(self._current_folder)

    def _on_scan_finished(self, results: List[ScanResult]) -> None:
        self._all_results = results
        count = len(results)
        self._status_label.setText(
            f"{count} file{'s' if count != 1 else ''} in {self._current_folder}"
        )
        self._populate_grid(results)
        for result in results:
            self._meta_svc.fetch(result)
            self._thumb_svc.request(result.path)

    def _on_metadata_ready(self, result: ScanResult) -> None:
        card = self._cards.get(result.path)
        if card:
            card.update_result(result)

    def _on_thumbnail_ready(self, media_path: str, thumb_path: str) -> None:
        card = self._cards.get(media_path)
        if card and thumb_path:
            card.set_thumbnail(thumb_path)

    # ------------------------------------------------------------------
    # Grid population
    # ------------------------------------------------------------------

    def _clear_grid(self) -> None:
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    def _populate_grid(self, results: List[ScanResult]) -> None:
        self._clear_grid()
        cols = max(1, (self.width() - 200 - 48) // 240)
        for i, result in enumerate(results):
            card = VideoCard(result, self._grid_widget)
            card.clicked.connect(self._on_card_clicked)
            self._grid_layout.addWidget(card, i // cols, i % cols)
            self._cards[result.path] = card

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Re-layout grid on resize
        if self._all_results:
            self._populate_grid(self._filter_results(self._search_bar.text()))

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _on_search(self, text: str) -> None:
        filtered = self._filter_results(text)
        self._populate_grid(filtered)

    def _filter_results(self, query: str) -> List[ScanResult]:
        query = query.strip().lower()
        if not query:
            return self._all_results
        return [r for r in self._all_results if query in r.name.lower()]

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _on_sidebar_click(self, name: str) -> None:
        if name == "Library":
            self._populate_grid(self._all_results)
        elif name == "Recently Played":
            self._show_recent()
        elif name == "Settings":
            self._show_settings()

    def _show_recent(self) -> None:
        from services import playback_history
        recent = playback_history.get_recent(20)
        paths = [r["path"] for r in recent]
        results = [r for r in self._all_results if r.path in paths]
        # Keep history order
        order = {p: i for i, p in enumerate(paths)}
        results.sort(key=lambda r: order.get(r.path, 999))
        self._populate_grid(results)
        self._status_label.setText(f"{len(results)} recently played")

    def _show_settings(self) -> None:
        from ui.dialogs import show_info
        show_info(
            self, "Settings",
            f"Media folder: {self._current_folder}\n\n"
            "Use 'Change Folder' in the sidebar to select a different folder.\n"
            "Settings are saved in config.json."
        )

    # ------------------------------------------------------------------
    # Folder selection
    # ------------------------------------------------------------------

    def _change_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Select Media Folder", self._current_folder
        )
        if folder:
            self._current_folder = folder
            settings.set_value("media_folder", folder)
            settings.save()
            self._refresh_library()

    # ------------------------------------------------------------------
    # Card click → play
    # ------------------------------------------------------------------

    def _on_card_clicked(self, result: ScanResult) -> None:
        self.play_requested.emit(result)

    # ------------------------------------------------------------------
    # Drag and drop
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path):
                result = ScanResult(path)
                self.play_requested.emit(result)
                break
