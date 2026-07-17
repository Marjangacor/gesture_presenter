import math
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QBrush, QPen, QFont, QConicalGradient
from PySide6.QtWidgets import QWidget, QApplication


class RadialMenuWindow(QWidget):
    """
    A GTA 5-style radial menu overlay for selecting gesture modes.
    2 segments: Right = Mouse Interaktif, Left = Presentasi.
    """
    def __init__(self, radius: int = 150):
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
        self.resize(radius * 2 + 20, radius * 2 + 20)

        # 2 Segments: Right (0) = Mouse Interaktif, Left (1) = Presentasi
        self.items = [
            "Mouse\nInteraktif",
            "Presentasi",
        ]
        self.hovered_index = -1
        self.active_index = 1
        self.hover_progress = 0.0  # 0.0..1.0 fill for hold-to-select
        self.center_x = self.width() / 2
        self.center_y = self.height() / 2

    def set_hovered_index(self, index: int):
        if self.hovered_index != index:
            self.hovered_index = index
            self.update()

    def set_active_index(self, index: int):
        self.active_index = index
        self.update()  # Always repaint when active index is set

    def set_hover_progress(self, progress: float):
        self.hover_progress = progress
        self.update()

    def show_in_center(self):
        screen = QApplication.primaryScreen().geometry()
        px = (screen.width() - self.width()) // 2
        py = (screen.height() - self.height()) // 2
        self.move(px, py)
        self.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        center = QPointF(self.center_x, self.center_y)
        rect = QRectF(10, 10, self.radius * 2, self.radius * 2)

        # --- Draw 2 half-circle segments ---
        # Segment 0 (Right half): Mouse Interaktif
        #   QPainter angles: span from -90 to +90 degrees (bottom-right to top-right)
        #   In QPainter coords (1/16th degree, CCW from 3-o'clock):
        #     start = -90 degrees = bottom, span = 180 degrees CCW = right half
        self._draw_segment(painter, rect, center,
                           start_16=-90 * 16, span_16=180 * 16,
                           label=self.items[0], index=0,
                           text_offset_x=self.radius * 0.45, text_offset_y=0)

        # Segment 1 (Left half): Presentasi
        #   start = 90 degrees = top, span = 180 degrees CCW = left half
        self._draw_segment(painter, rect, center,
                           start_16=90 * 16, span_16=180 * 16,
                           label=self.items[1], index=1,
                           text_offset_x=-self.radius * 0.45, text_offset_y=0)

        # --- Inner circle (donut hole) ---
        painter.setBrush(QBrush(QColor(0, 0, 0, 200)))
        painter.setPen(Qt.NoPen)
        inner_r = self.radius * 0.3
        painter.drawEllipse(center, inner_r, inner_r)

        # --- Hold-to-select progress arc ---
        if self.hovered_index >= 0 and self.hover_progress > 0.0:
            self._draw_progress_arc(painter, center)

        # --- Center label ---
        painter.setPen(QColor(255, 255, 255, 200))
        font = QFont("Arial", 8)
        painter.setFont(font)
        label_rect = QRectF(center.x() - 40, center.y() - 10, 80, 20)
        if self.hover_progress > 0:
            secs_left = round(2.0 * (1.0 - self.hover_progress), 1)
            center_text = f"{secs_left:.1f}s"
        else:
            center_text = "Tahan 2 detik"
        painter.drawText(label_rect, Qt.AlignCenter, center_text)

    def _draw_progress_arc(self, painter, center):
        """Draw a glowing arc around the inner circle that fills up as the user holds."""
        arc_r = self.radius * 0.32
        arc_rect = QRectF(
            center.x() - arc_r, center.y() - arc_r,
            arc_r * 2, arc_r * 2
        )
        span_angle = int(360 * self.hover_progress) * 16
        # Start from top (90 degrees = 12-o'clock position)
        start_angle = 90 * 16

        pen = QPen(QColor(255, 255, 80, 230), 5)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(arc_rect, start_angle, span_angle)

    def _draw_segment(self, painter, rect, center,
                      start_16, span_16, label, index,
                      text_offset_x, text_offset_y):
        if index == self.hovered_index:
            brush = QBrush(QColor(255, 255, 255, 180))
            text_color = QColor(0, 0, 0, 255)
        elif index == self.active_index:
            brush = QBrush(QColor(0, 200, 100, 180)) # Green for active feature
            text_color = QColor(255, 255, 255, 255)
        else:
            brush = QBrush(QColor(0, 0, 0, 150))
            text_color = QColor(255, 255, 255, 255)

        painter.setBrush(brush)
        painter.setPen(QPen(QColor(255, 255, 255, 100), 2))
        painter.drawPie(rect, start_16, span_16)

        # Label
        painter.setPen(text_color)
        font = QFont("Arial", 11, QFont.Bold)
        painter.setFont(font)
        tx = self.center_x + text_offset_x
        ty = self.center_y + text_offset_y
        text_rect = QRectF(tx - 50, ty - 20, 100, 40)
        painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, label)
