from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QCursor
from PySide6.QtWidgets import QWidget, QPushButton, QVBoxLayout, QApplication

class FloatingMenuButton(QWidget):
    menu_clicked = Signal()

    def __init__(self):
        super().__init__()
        # Frameless, tool window, always on top
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.Tool |
            Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.btn = QPushButton("Menu")
        self.btn.setFont(QFont("Arial", 12, QFont.Bold))
        self.btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(50, 50, 50, 200);
                color: white;
                border-radius: 15px;
                padding: 10px 30px;
                border: 2px solid rgba(255, 255, 255, 100);
            }
            QPushButton:hover {
                background-color: rgba(80, 80, 80, 230);
                border: 2px solid rgba(255, 255, 80, 200);
            }
            QPushButton:pressed {
                background-color: rgba(120, 120, 120, 255);
            }
        """)
        self.btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn.clicked.connect(self.menu_clicked.emit)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.btn)
        self.setLayout(layout)

        self.resize(120, 45)

    def show_in_bottom_center(self):
        screen = QApplication.primaryScreen().geometry()
        px = (screen.width() - self.width()) // 2
        py = screen.height() - self.height() - 80  # 80px from bottom (moved up)
        self.move(px, py)
        self.show()
