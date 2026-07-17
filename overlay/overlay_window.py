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
        self.base_opacity = opacity
        self.current_opacity = opacity
        
        self.initial_hand_x = None
        self.initial_hand_y = None
        self._ema_px = None
        self._ema_py = None
        self.active_axis = None
        
        self.resize(radius * 2, radius * 2)
        self._center_on_screen()

    def show(self):
        super().show()
        self.initial_hand_x = None
        self.initial_hand_y = None
        self.current_opacity = self.base_opacity
        self.active_axis = None
        self._center_on_screen()

    def hide(self):
        super().hide()
        self.initial_hand_x = None
        self.initial_hand_y = None
        self.active_axis = None

    def _center_on_screen(self):
        screen = QApplication.primaryScreen().geometry()
        px = int(0.5 * screen.width())
        py = int(0.5 * screen.height())
        self._ema_px = px
        self._ema_py = py
        self.move(px - self.radius, py - self.radius)

    def set_radius(self, radius: int):
        self.radius = radius
        self.resize(radius * 2, radius * 2)
        self.update()

    def set_opacity(self, opacity: float):
        self.base_opacity = opacity
        self.current_opacity = opacity
        self.update()

    def move_to_normalized(self, x: float, y: float):
        """x, y are normalized (0..1) hand coordinates from the camera frame."""
        if self.initial_hand_x is None:
            self.initial_hand_x = x
            self.initial_hand_y = y
            self._center_on_screen()
            return
            
        # Calculate deviation from initial hand position
        dx = x - self.initial_hand_x
        dy = y - self.initial_hand_y
        
        # Sensitivity multiplier so small hand movements can reach the edges
        sensitivity = 1.2
        dx *= sensitivity
        dy *= sensitivity
        
        # Deadzone to release axis lock
        deadzone = 0.05
        max_deviation = max(abs(dx), abs(dy))
        
        # Determine sticky axis lock (like a cross-gate arcade joystick)
        if self.active_axis is None:
            if max_deviation > deadzone:
                if abs(dx) > abs(dy):
                    self.active_axis = 'x'
                else:
                    self.active_axis = 'y'
        else:
            # Unlock if returned to center deadzone
            if max_deviation < deadzone:
                self.active_axis = None
                
        # Apply the locked axis
        if self.active_axis == 'x':
            dy = 0.0
            dist = abs(dx)
        elif self.active_axis == 'y':
            dx = 0.0
            dist = abs(dy)
        else:
            # In deadzone, keep perfectly centered
            dx = 0.0
            dy = 0.0
            dist = 0.0

        # Fades out as it moves away from center
        # Fully transparent at distance 0.5 from center (edge of screen)
        fade_factor = max(0.0, 1.0 - (dist / 0.5))
        self.current_opacity = self.base_opacity * fade_factor

        screen = QApplication.primaryScreen().geometry()
        target_px = (0.5 + dx) * screen.width()
        target_py = (0.5 + dy) * screen.height()
        
        # EMA Smoothing to eliminate jitter
        alpha = 0.2  # Smoothing factor (lower is smoother)
        if self._ema_px is None:
            self._ema_px = target_px
            self._ema_py = target_py
        else:
            self._ema_px = alpha * target_px + (1.0 - alpha) * self._ema_px
            self._ema_py = alpha * target_py + (1.0 - alpha) * self._ema_py

        self.move(int(self._ema_px) - self.radius, int(self._ema_py) - self.radius)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        color = QColor(0, 170, 255)
        color.setAlphaF(self.current_opacity)

        painter.setBrush(QBrush(color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(0, 0, self.width(), self.height()))
