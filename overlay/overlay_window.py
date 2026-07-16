"""
A transparent, always-on-top, click-through circular overlay — no text,
just a shape, per the spec. Only visible while Presentation Mode is
active; AppService shows/hides it based on GestureEngine signals.
"""

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QBrush
from PySide6.QtWidgets import QWidget, QApplication


class OverlayWindow(QWidget):
    def __init__(self, radius: int = 20, opacity: float = 0.5):
        super().__init__(
            None,
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput,
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self.radius = radius
        self.opacity = opacity
        self.resize(radius * 2, radius * 2)

    def set_radius(self, radius: int):
        self.radius = radius
        self.resize(radius * 2, radius * 2)
        self.update()

    def set_opacity(self, opacity: float):
        self.opacity = opacity
        self.update()

    def move_to_normalized(self, x: float, y: float):
        """x, y are normalized (0..1) hand coordinates from the camera frame."""
        screen = QApplication.primaryScreen().geometry()
        center_x = screen.width() // 2
        center_y = screen.height() // 2

        dx = x - 0.5
        dy = y - 0.5

        sensitivity = 2.0

        if abs(dx) > abs(dy):
            # Horizontal movement dominant: lock Y to center
            px = int(center_x + dx * sensitivity * screen.width()) - self.radius
            py = center_y - self.radius
        else:
            # Vertical movement dominant: lock X to center
            px = center_x - self.radius
            py = int(center_y + dy * sensitivity * screen.height()) - self.radius

        self.move(px, py)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        color = QColor(0, 170, 255)
        color.setAlphaF(self.opacity)

        painter.setBrush(QBrush(color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(0, 0, self.width(), self.height()))
