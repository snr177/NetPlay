"""
CineShelf dialog boxes.
Subtitle URL input, resume confirmation, and error display.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class SubtitleURLDialog(QDialog):
    """Dialog for entering a subtitle URL."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Load Subtitle from URL")
        self.setModal(True)
        self.setMinimumWidth(480)
        self.url: str = ""
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 20)

        title = QLabel("Subtitle URL")
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        layout.addWidget(title)

        info = QLabel(
            "Enter a direct HTTP or HTTPS link to an SRT, ASS, SSA, VTT, or SUB file."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #999999;")
        layout.addWidget(info)

        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("https://example.com/subtitles/movie.srt")
        self._url_input.setClearButtonEnabled(True)
        layout.addWidget(self._url_input)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        load_btn = QPushButton("Load")
        load_btn.setObjectName("primary_btn")
        load_btn.clicked.connect(self._on_load)
        load_btn.setDefault(True)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(load_btn)
        layout.addLayout(btn_row)

    def _on_load(self):
        self.url = self._url_input.text().strip()
        if self.url:
            self.accept()
        else:
            self._url_input.setFocus()

    def get_url(self) -> str:
        return self.url


class ResumeDialog(QDialog):
    """Ask the user whether to resume or restart playback."""

    RESUME = "resume"
    RESTART = "restart"

    def __init__(self, filename: str, position_label: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resume Playback")
        self.setModal(True)
        self.setMinimumWidth(380)
        self.choice: str = self.RESUME
        self._build_ui(filename, position_label)

    def _build_ui(self, filename: str, position_label: str):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 20)

        title = QLabel("Resume where you left off?")
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        layout.addWidget(title)

        msg = QLabel(
            f"<b>{filename}</b> was paused at <b>{position_label}</b>."
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        restart_btn = QPushButton("Start from beginning")
        restart_btn.clicked.connect(self._on_restart)

        resume_btn = QPushButton(f"Resume from {position_label}")
        resume_btn.setObjectName("primary_btn")
        resume_btn.clicked.connect(self._on_resume)
        resume_btn.setDefault(True)

        btn_row.addWidget(restart_btn)
        btn_row.addWidget(resume_btn)
        layout.addLayout(btn_row)

    def _on_resume(self):
        self.choice = self.RESUME
        self.accept()

    def _on_restart(self):
        self.choice = self.RESTART
        self.accept()


def show_error(parent: QWidget, title: str, message: str) -> None:
    """Display a modal error message box."""
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(message)
    box.setIcon(QMessageBox.Critical)
    box.exec()


def show_info(parent: QWidget, title: str, message: str) -> None:
    """Display a modal information message box."""
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(message)
    box.setIcon(QMessageBox.Information)
    box.exec()
