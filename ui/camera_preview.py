"""
Live camera preview overlay window.

Shows a floating, always-on-top webcam feed that the user can drag.
A "Capture & Analyze" button sends the current frame to the AI.
"""

import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap, QColor


class CameraPreviewOverlay(QWidget):
    """
    Floating webcam preview widget.

    Signals
    -------
    capture_requested : emitted when the user clicks "Capture & Analyze".
        The slot should call vision.capture_camera_frame_as_base64() and
        pass the result to the AI.
    closed : emitted when the window is dismissed.
    """

    capture_requested = pyqtSignal()
    closed = pyqtSignal()

    REFRESH_MS = 50   # ~20 fps preview

    def __init__(self, vision_module, parent=None):
        super().__init__(parent)
        self._vision = vision_module
        self._offset = None
        self._frame_count = 0

        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(340, 280)

        self._build_ui()

        # Start camera
        opened = self._vision.open_camera()
        if not opened:
            self._status_label.setText("⚠  No camera detected")

        # Refresh timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_frame)
        self._timer.start(self.REFRESH_MS)

    # ── UI ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        self._container = QWidget()
        self._container.setObjectName("CamContainer")
        self._container.setStyleSheet("""
            QWidget#CamContainer {
                background-color: rgba(20, 22, 34, 230);
                border-radius: 16px;
                border: 1px solid rgba(100, 150, 255, 80);
            }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setXOffset(0)
        shadow.setYOffset(8)
        shadow.setColor(QColor(0, 0, 0, 130))
        self._container.setGraphicsEffect(shadow)

        inner = QVBoxLayout(self._container)
        inner.setContentsMargins(10, 10, 10, 10)
        inner.setSpacing(8)

        # Header row
        header = QHBoxLayout()
        title = QLabel("📷  Live Camera")
        title.setStyleSheet("color: rgba(180,200,255,220); font-family: 'Segoe UI'; font-size: 12px; font-weight: bold; background: transparent; border: none;")
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet("""
            QPushButton { background: rgba(255,80,80,160); color: white; border-radius: 12px; font-size: 11px; }
            QPushButton:hover { background: rgba(255,80,80,255); }
        """)
        close_btn.clicked.connect(self._on_close)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(close_btn)

        # Camera frame label
        self._frame_label = QLabel()
        self._frame_label.setFixedSize(308, 200)
        self._frame_label.setAlignment(Qt.AlignCenter)
        self._frame_label.setStyleSheet(
            "background-color: rgba(0,0,0,180); border-radius: 10px; color: rgba(150,150,180,200);"
        )
        self._frame_label.setText("Initializing camera…")

        # Status + capture button row
        bottom = QHBoxLayout()
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: rgba(150,200,150,200); font-size: 11px; background: transparent; border: none;")

        self._capture_btn = QPushButton("🔍  Capture & Analyze")
        self._capture_btn.setFixedHeight(32)
        self._capture_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(80,130,255,200), stop:1 rgba(130,80,255,200));
                color: white;
                border-radius: 14px;
                font-family: 'Segoe UI';
                font-size: 12px;
                font-weight: bold;
                padding: 0 12px;
            }
            QPushButton:hover { background: rgba(100,160,255,255); }
            QPushButton:pressed { background: rgba(60,100,220,255); }
        """)
        self._capture_btn.clicked.connect(self._on_capture)
        bottom.addWidget(self._status_label)
        bottom.addStretch()
        bottom.addWidget(self._capture_btn)

        inner.addLayout(header)
        inner.addWidget(self._frame_label)
        inner.addLayout(bottom)

        outer.addWidget(self._container)

    # ── frame refresh ───────────────────────────────────────────────────────

    def _refresh_frame(self):
        frame = self._vision.capture_camera_frame_as_qimage()
        if frame is None:
            return

        h, w, ch = frame.shape
        bytes_per_line = ch * w
        qt_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_img).scaled(
            self._frame_label.width(),
            self._frame_label.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self._frame_label.setPixmap(pixmap)
        self._frame_count += 1

    # ── actions ──────────────────────────────────────────────────────────────

    def _on_capture(self):
        self._status_label.setText("📸 Captured!")
        self.capture_requested.emit()

    def _on_close(self):
        self._timer.stop()
        self._vision.release_camera()
        self.closed.emit()
        self.close()

    # ── dragging ─────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._offset = event.pos()

    def mouseMoveEvent(self, event):
        if self._offset is not None and event.buttons() == Qt.LeftButton:
            self.move(self.pos() + event.pos() - self._offset)

    def mouseReleaseEvent(self, event):
        self._offset = None
