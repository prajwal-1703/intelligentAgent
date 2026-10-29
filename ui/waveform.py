"""
Animated waveform widget that pulses while the agent is listening.
"""

import math
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QTimer, QRectF
from PyQt5.QtGui import QPainter, QColor, QPen, QLinearGradient


class WaveformWidget(QWidget):
    """
    Displays a multi-bar waveform animation.
    Call `set_active(True)` to start animating, `set_active(False)` to idle.
    """

    BAR_COUNT = 7
    BAR_WIDTH = 4
    BAR_SPACING = 3
    MAX_HEIGHT = 28
    MIN_HEIGHT = 4
    FPS = 40  # animation frames per second

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active = False
        self._phase = 0.0
        self._heights = [self.MIN_HEIGHT] * self.BAR_COUNT

        total_width = self.BAR_COUNT * (self.BAR_WIDTH + self.BAR_SPACING) - self.BAR_SPACING
        self.setFixedSize(total_width + 8, self.MAX_HEIGHT + 8)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000 // self.FPS)

    # ── public ─────────────────────────────────────────────────────────────

    def set_active(self, active: bool):
        self._active = active
        if not active:
            self._heights = [self.MIN_HEIGHT] * self.BAR_COUNT
            self.update()

    # ── internal ───────────────────────────────────────────────────────────

    def _tick(self):
        if not self._active:
            return
        self._phase += 0.20
        for i in range(self.BAR_COUNT):
            wave = math.sin(self._phase + i * 0.9)
            noise = math.sin(self._phase * 1.7 + i * 1.3) * 0.4
            raw = (wave + noise + 1) / 2          # 0..1
            target = self.MIN_HEIGHT + raw * (self.MAX_HEIGHT - self.MIN_HEIGHT)
            # Smooth toward target
            self._heights[i] += (target - self._heights[i]) * 0.35
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        x = 4
        mid_y = self.height() / 2

        for i, h in enumerate(self._heights):
            top = mid_y - h / 2
            rect = QRectF(x, top, self.BAR_WIDTH, h)

            grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            if self._active:
                grad.setColorAt(0.0, QColor(120, 180, 255, 230))
                grad.setColorAt(0.5, QColor(80, 140, 255, 255))
                grad.setColorAt(1.0, QColor(120, 180, 255, 230))
            else:
                c = QColor(100, 100, 120, 100)
                grad.setColorAt(0, c)
                grad.setColorAt(1, c)

            painter.setPen(Qt.NoPen)
            painter.setBrush(grad)
            painter.drawRoundedRect(rect, 2, 2)

            x += self.BAR_WIDTH + self.BAR_SPACING
