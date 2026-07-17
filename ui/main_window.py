import sys
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QFormLayout,
    QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit,
    QCheckBox, QPushButton, QGroupBox, QHBoxLayout,
    QTabWidget, QGridLayout, QLabel, QFrame, QSlider,
    QApplication, QAbstractButton
)
from PySide6.QtCore import Qt, QPropertyAnimation, Property, QTimer, Signal
from PySide6.QtGui import QPainter, QColor, QFont

from config.settings_manager import SettingsManager
from services.app_service import AppService
from vision.camera_utils import list_available_cameras


# ---------------------------------------------------------
# Custom Animated Toggle Switch (iOS style)
# ---------------------------------------------------------
class ToggleSwitch(QAbstractButton):
    toggled_switch = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(46, 22)
        self._thumb_position = 3.0
        self._animation = QPropertyAnimation(self, b"thumb_position", self)
        self._animation.setDuration(120)

    @Property(float)
    def thumb_position(self):
        return self._thumb_position

    @thumb_position.setter
    def thumb_position(self, pos):
        self._thumb_position = pos
        self.update()

    def setChecked(self, checked):
        super().setChecked(checked)
        self._thumb_position = 27.0 if checked else 3.0
        self.update()

    def nextCheckState(self):
        super().nextCheckState()
        start = 3.0 if self.isChecked() else 27.0
        end = 27.0 if self.isChecked() else 3.0
        self._animation.setStartValue(start)
        self._animation.setEndValue(end)
        self._animation.start()
        self.toggled_switch.emit(self.isChecked())


    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Track background
        track_color = QColor("#3b82f6") if self.isChecked() else QColor("#374151")
        painter.setBrush(track_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), self.height() / 2, self.height() / 2)
        
        # Thumb
        thumb_color = QColor("#ffffff")
        painter.setBrush(thumb_color)
        r = self.height() - 6
        painter.drawEllipse(self._thumb_position, 3, r, r)


# ---------------------------------------------------------
# Custom Gesture Card Widget
# ---------------------------------------------------------
class GestureCard(QFrame):
    def __init__(self, key, title, subtitle, icon_char, action_choices, parent=None):
        super().__init__(parent)
        self.key = key
        self.title_text = title
        self.subtitle_text = subtitle
        self.icon_char = icon_char
        self.action_choices = action_choices
        
        self.setFrameShape(QFrame.StyledPanel)
        self.setObjectName("GestureCard")
        
        self._build_ui()
        self._is_testing = False
        self._test_timer = QTimer(self)
        self._test_timer.setSingleShot(True)
        self._test_timer.timeout.connect(self._reset_test_state)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        
        # Header Row
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        
        self.icon_label = QLabel(self.icon_char)
        self.icon_label.setObjectName("CardIcon")
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setFixedSize(40, 40)
        
        title_container = QVBoxLayout()
        title_container.setSpacing(2)
        
        self.title_label = QLabel(self.title_text)
        self.title_label.setObjectName("CardTitle")
        
        self.subtitle_label = QLabel(self.subtitle_text)
        self.subtitle_label.setObjectName("CardSubtitle")
        
        title_container.addWidget(self.title_label)
        title_container.addWidget(self.subtitle_label)
        
        self.switch_btn = ToggleSwitch()
        self.switch_btn.setObjectName("CardSwitch")
        
        header_layout.addWidget(self.icon_label)
        header_layout.addLayout(title_container)
        header_layout.addStretch()
        header_layout.addWidget(self.switch_btn)
        
        # Action Dropdown
        action_label = QLabel("ACTION")
        action_label.setObjectName("LabelCaps")
        
        self.action_combo = QComboBox()
        self.action_combo.addItems(self.action_choices)
        self.action_combo.setObjectName("CardCombo")
        
        # Sensitivity Slider
        sens_label = QLabel("SENSITIVITY")
        sens_label.setObjectName("LabelCaps")
        
        slider_layout = QHBoxLayout()
        self.sens_slider = QSlider(Qt.Horizontal)
        self.sens_slider.setRange(0, 100)
        self.sens_slider.setObjectName("CardSlider")
        
        self.sens_val_label = QLabel("70%")
        self.sens_val_label.setObjectName("SliderValueLabel")
        self.sens_val_label.setFixedWidth(35)
        self.sens_val_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        self.sens_slider.valueChanged.connect(lambda v: self.sens_val_label.setText(f"{v}%"))
        
        slider_layout.addWidget(self.sens_slider)
        slider_layout.addWidget(self.sens_val_label)
        
        # Footer Row (Recognition and Test Button)
        footer_layout = QHBoxLayout()
        
        status_layout = QHBoxLayout()
        status_layout.setSpacing(8)
        self.status_dot = QLabel()
        self.status_dot.setObjectName("StatusDotOff")
        self.status_dot.setFixedSize(10, 10)
        
        self.status_text = QLabel("Recognition 0%")
        self.status_text.setObjectName("StatusText")
        
        status_layout.addWidget(self.status_dot)
        status_layout.addWidget(self.status_text)
        status_layout.addStretch()
        
        self.test_btn = QPushButton("▶ Test")
        self.test_btn.setObjectName("CardTestBtn")
        self.test_btn.setFixedSize(65, 26)
        self.test_btn.clicked.connect(self.start_test)
        
        footer_layout.addLayout(status_layout)
        footer_layout.addWidget(self.test_btn)
        
        layout.addLayout(header_layout)
        layout.addWidget(action_label)
        layout.addWidget(self.action_combo)
        layout.addWidget(sens_label)
        layout.addLayout(slider_layout)
        layout.addSpacing(4)
        layout.addLayout(footer_layout)

    def set_recognized(self, recognized: bool, conf: int = 97):
        if not self.switch_btn.isChecked():
            self.status_dot.setObjectName("StatusDotOff")
            self.status_text.setText("Disabled")
            self.status_text.setStyleSheet("color: #64748b;")
            return

        if self._is_testing:
            return

        if recognized:
            self.status_dot.setObjectName("StatusDotOn")
            self.status_text.setText(f"Recognition {conf}%")
            self.status_text.setStyleSheet("color: #22c55e;")
            self.setProperty("detected", "true")
        else:
            self.status_dot.setObjectName("StatusDotOff")
            self.status_text.setText("Recognition 0%")
            self.status_text.setStyleSheet("color: #94a3b8;")
            self.setProperty("detected", "false")

        # Force stylesheet update
        self.style().unpolish(self)
        self.style().polish(self)
        self.status_dot.style().unpolish(self.status_dot)
        self.status_dot.style().polish(self.status_dot)

    def start_test(self):
        self._is_testing = True
        self.status_dot.setObjectName("StatusDotTesting")
        self.status_text.setText("Perform gesture...")
        self.status_text.setStyleSheet("color: #eab308;")
        self.test_btn.setEnabled(False)
        self.status_dot.style().unpolish(self.status_dot)
        self.status_dot.style().polish(self.status_dot)
        self._test_timer.start(5000)

    def trigger_success(self):
        if self._is_testing:
            self._reset_test_state()
        
        self.status_dot.setObjectName("StatusDotOn")
        self.status_text.setText("Triggered! (100%)")
        self.status_text.setStyleSheet("color: #22c55e;")
        self.setProperty("detected", "true")
        self.style().unpolish(self)
        self.style().polish(self)
        self.status_dot.style().unpolish(self.status_dot)
        self.status_dot.style().polish(self.status_dot)
        QTimer.singleShot(1000, self._clear_trigger)

    def _clear_trigger(self):
        if not self._is_testing:
            self.set_recognized(False)

    def _reset_test_state(self):
        self._is_testing = False
        self.test_btn.setEnabled(True)
        self.set_recognized(False)


# ---------------------------------------------------------
# MainWindow Implementation
# ---------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self, settings: SettingsManager):
        super().__init__()
        self.settings = settings
        self.app_service = AppService(settings)

        self.setWindowTitle("Gesture Presenter")
        self.resize(920, 690)

        self._build_ui()
        self._load_settings_into_ui()
        self._connect_signals()
        self._apply_stylesheet()

    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)

        # 1. Header Bar
        header_layout = QHBoxLayout()
        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(4)
        
        self.header_title = QLabel("Gesture Configuration")
        self.header_title.setObjectName("HeaderTitle")
        
        self.header_subtitle = QLabel("Customize how hand gestures map to presentation actions")
        self.header_subtitle.setObjectName("HeaderSubtitle")
        
        title_vbox.addWidget(self.header_title)
        title_vbox.addWidget(self.header_subtitle)
        
        header_layout.addLayout(title_vbox)
        header_layout.addStretch()

        self.reset_btn = QPushButton("Reset to Default")
        self.reset_btn.setObjectName("ResetBtn")
        self.reset_btn.clicked.connect(self._on_reset_clicked)

        self.save_btn = QPushButton("Save Changes")
        self.save_btn.setObjectName("SaveBtn")
        self.save_btn.clicked.connect(self._on_save_clicked)

        header_layout.addWidget(self.reset_btn)
        header_layout.addWidget(self.save_btn)
        
        main_layout.addLayout(header_layout)

        # 2. Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setObjectName("MainTabs")
        main_layout.addWidget(self.tabs)

        # Tab 1: Gestures Tab
        self.gestures_tab = QWidget()
        self.gestures_grid = QGridLayout(self.gestures_tab)
        self.gestures_grid.setContentsMargins(0, 16, 0, 0)
        self.gestures_grid.setSpacing(20)

        swipe_choices = ["Next Slide", "Previous Slide", "None"]
        hold_choices = ["Activate Presentation", "None"]
        fist_choices = ["Window Switcher", "None"]

        self.cards = {
            "swipe_right": GestureCard("swipe_right", "Swipe Right", "Move hand rightward", "🫱", swipe_choices, self),
            "swipe_left": GestureCard("swipe_left", "Swipe Left", "Move hand leftward", "🫲", swipe_choices, self),
            "open_palm": GestureCard("open_palm", "Open Palm", "Spread all fingers (Hold to active)", "🖐", hold_choices, self),
            "closed_fist": GestureCard("closed_fist", "Closed Fist", "Close all fingers (Hold for window switch)", "✊", fist_choices, self)
        }

        self.gestures_grid.addWidget(self.cards["swipe_right"], 0, 0)
        self.gestures_grid.addWidget(self.cards["swipe_left"], 0, 1)
        self.gestures_grid.addWidget(self.cards["open_palm"], 1, 0)
        self.gestures_grid.addWidget(self.cards["closed_fist"], 1, 1)

        self.tabs.addTab(self.gestures_tab, "Gestures")

        # Tab 2: General Settings Tab
        self.general_tab = QWidget()
        general_layout = QVBoxLayout(self.general_tab)
        general_layout.setContentsMargins(10, 20, 10, 10)
        general_layout.setSpacing(16)

        general_layout.addWidget(self._build_camera_group())
        general_layout.addWidget(self._build_cooldown_and_hotkey_group())
        general_layout.addWidget(self._build_overlay_group())
        general_layout.addStretch()

        self.tabs.addTab(self.general_tab, "General Settings")

        # 3. Control Panel (Bottom)
        control_layout = QHBoxLayout()
        
        self.start_button = QPushButton("Start Service")
        self.start_button.setObjectName("StartServiceBtn")
        
        self.stop_button = QPushButton("Stop Service")
        self.stop_button.setObjectName("StopServiceBtn")
        self.stop_button.setEnabled(False)

        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.stop_button)
        
        main_layout.addLayout(control_layout)

    def _build_camera_group(self) -> QGroupBox:
        group = QGroupBox("Camera Settings")
        layout = QFormLayout(group)
        layout.setContentsMargins(16, 20, 16, 16)

        self.camera_combo = QComboBox()
        self.camera_combo.setObjectName("GeneralCombo")
        available = list_available_cameras()
        if not available:
            available = [0]
        for index in available:
            self.camera_combo.addItem(f"Camera {index}", userData=index)

        layout.addRow("Select Webcam Hardware:", self.camera_combo)
        return group

    def _build_cooldown_and_hotkey_group(self) -> QGroupBox:
        group = QGroupBox("Timing & Global Hotkeys")
        layout = QFormLayout(group)
        layout.setContentsMargins(16, 20, 16, 16)

        self.cooldown_spin = QDoubleSpinBox()
        self.cooldown_spin.setRange(0.1, 5.0)
        self.cooldown_spin.setSingleStep(0.1)
        self.cooldown_spin.setSuffix(" seconds")

        self.hotkey_input = QLineEdit()
        self.hotkey_input.setPlaceholderText("e.g. f8")

        layout.addRow("Action Gesture Cooldown:", self.cooldown_spin)
        layout.addRow("Global ON/OFF Shortcut Hotkey:", self.hotkey_input)
        return group

    def _build_overlay_group(self) -> QGroupBox:
        group = QGroupBox("Hand Tracker Visual Overlay")
        layout = QFormLayout(group)
        layout.setContentsMargins(16, 20, 16, 16)

        self.overlay_enabled_check = QCheckBox("Enable visual tracking overlay indicator")

        self.overlay_radius_spin = QSpinBox()
        self.overlay_radius_spin.setRange(5, 100)
        self.overlay_radius_spin.setSuffix(" pixels")

        self.overlay_opacity_spin = QDoubleSpinBox()
        self.overlay_opacity_spin.setRange(0.1, 1.0)
        self.overlay_opacity_spin.setSingleStep(0.05)

        layout.addRow(self.overlay_enabled_check)
        layout.addRow("Overlay Circle Radius:", self.overlay_radius_spin)
        layout.addRow("Overlay Transparency Opacity:", self.overlay_opacity_spin)
        return group

    # ---------------------------------------------------------
    # Settings binding
    # ---------------------------------------------------------
    def _load_settings_into_ui(self):
        data = self.settings.get_all()

        # Load camera setting
        target_camera_index = data.get("camera_index", 0)
        combo_position = self.camera_combo.findData(target_camera_index)
        self.camera_combo.setCurrentIndex(combo_position if combo_position >= 0 else 0)
        
        # Load timing & hotkey
        self.cooldown_spin.setValue(data.get("cooldown_seconds", 1.0))
        self.hotkey_input.setText(data.get("hotkeys", {}).get("toggle_gesture_control", "f8"))

        # Load overlay configuration
        overlay_data = data.get("overlay", {})
        self.overlay_enabled_check.setChecked(overlay_data.get("enabled", True))
        self.overlay_radius_spin.setValue(overlay_data.get("radius", 20))
        self.overlay_opacity_spin.setValue(overlay_data.get("opacity", 0.5))

        # Load gesture cards configurations
        g_settings = data.get("gesture_settings", {})
        for key, card in self.cards.items():
            cfg = g_settings.get(key, {})
            card.switch_btn.setChecked(cfg.get("enabled", True))
            
            action_idx = card.action_combo.findText(cfg.get("action", ""))
            card.action_combo.setCurrentIndex(action_idx if action_idx >= 0 else 0)
            
            card.sens_slider.setValue(cfg.get("sensitivity", 70))
            card.set_recognized(False)

    def _connect_signals(self):
        # General Settings updates
        self.camera_combo.currentIndexChanged.connect(
            lambda i: self.settings.update(
                "camera_index", self.camera_combo.itemData(i) if i >= 0 else 0
            )
        )
        self.cooldown_spin.valueChanged.connect(
            lambda v: self._update_general_setting("cooldown_seconds", v)
        )
        self.hotkey_input.textChanged.connect(
            lambda t: self.settings.update(
                "hotkeys", {**self.settings.get("hotkeys", {}), "toggle_gesture_control": t}
            )
        )
        self.overlay_enabled_check.toggled.connect(
            lambda checked: self.settings.update(
                "overlay", {**self.settings.get("overlay", {}), "enabled": checked}
            )
        )
        self.overlay_radius_spin.valueChanged.connect(
            lambda v: self.settings.update(
                "overlay", {**self.settings.get("overlay", {}), "radius": v}
            )
        )
        self.overlay_opacity_spin.valueChanged.connect(
            lambda v: self.settings.update(
                "overlay", {**self.settings.get("overlay", {}), "opacity": v}
            )
        )

        # Connect gesture cards settings updates
        for key, card in self.cards.items():
            card.switch_btn.toggled_switch.connect(
                lambda checked, k=key: self._update_gesture_setting(k, "enabled", checked)
            )
            card.action_combo.currentIndexChanged.connect(
                lambda idx, k=key: self._update_gesture_setting(k, "action", self.cards[k].action_combo.currentText())
            )
            card.sens_slider.valueChanged.connect(
                lambda val, k=key: self._update_gesture_setting(k, "sensitivity", val)
            )

        # Control Panel Buttons
        self.start_button.clicked.connect(self._on_start_clicked)
        self.stop_button.clicked.connect(self._on_stop_clicked)

        # Forward live feedback from AppService
        self.app_service.gesture_detected.connect(self._on_live_gesture_detected)
        self.app_service.swipe_right.connect(lambda: self.cards["swipe_right"].trigger_success())
        self.app_service.swipe_left.connect(lambda: self.cards["swipe_left"].trigger_success())

    def _update_general_setting(self, key, value):
        self.settings.update(key, value)
        if self.app_service.gesture_engine:
            self.app_service.gesture_engine._reload_settings()

    def _update_gesture_setting(self, gesture_key, option, value):
        g_settings = self.settings.get("gesture_settings", {})
        if gesture_key not in g_settings:
            g_settings[gesture_key] = {}
        g_settings[gesture_key][option] = value
        self.settings.update("gesture_settings", g_settings)
        if self.app_service.gesture_engine:
            self.app_service.gesture_engine._reload_settings()

    # ---------------------------------------------------------
    # Live Recognition signals handler
    # ---------------------------------------------------------
    def _on_live_gesture_detected(self, name: str, detected: bool):
        if name in self.cards:
            self.cards[name].set_recognized(detected)

    # ---------------------------------------------------------
    # Buttons Action Event Handlers
    # ---------------------------------------------------------
    def _on_save_clicked(self):
        self.settings.save()
        self.save_btn.setText("✓ Saved!")
        self.save_btn.setStyleSheet("background-color: #22c55e;")
        QTimer.singleShot(1500, self._restore_save_button_state)

    def _restore_save_button_state(self):
        self.save_btn.setText("Save Changes")
        self.save_btn.setStyleSheet("background-color: #2563eb;")

    def _on_reset_clicked(self):
        self.settings.reset()
        self._load_settings_into_ui()
        if self.app_service.gesture_engine:
            self.app_service.gesture_engine._reload_settings()
        self.reset_btn.setText("✓ Reset Complete!")
        QTimer.singleShot(1500, lambda: self.reset_btn.setText("Reset to Default"))

    def _on_start_clicked(self):
        self.settings.save()
        self.app_service.start()
        # Connect live feedback again to the new engine
        self.app_service.gesture_detected.connect(self._on_live_gesture_detected)
        self.app_service.swipe_right.connect(lambda: self.cards["swipe_right"].trigger_success())
        self.app_service.swipe_left.connect(lambda: self.cards["swipe_left"].trigger_success())
        
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def _on_stop_clicked(self):
        self.app_service.stop()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        for card in self.cards.values():
            card.set_recognized(False)

    def closeEvent(self, event):
        self.app_service.stop()
        event.accept()

    # ---------------------------------------------------------
    # Stylesheet application (QSS)
    # ---------------------------------------------------------
    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0b0f19;
            }

            QTabWidget::pane {
                border: none;
                background-color: #0b0f19;
            }

            QTabBar::tab {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 10px 24px;
                font-size: 10pt;
                font-weight: bold;
            }

            QTabBar::tab:selected {
                background-color: #0b0f19;
                color: #f8fafc;
                border: 1px solid #334155;
                border-bottom: 1px solid #0b0f19;
            }

            QTabBar::tab:hover {
                color: #f8fafc;
                background-color: #1e293b;
            }

            #GestureCard {
                background-color: #111827;
                border: 1px solid #374151;
                border-radius: 12px;
            }

            #GestureCard[detected="true"] {
                border: 1px solid #3b82f6;
                background-color: #161e31;
            }

            #CardIcon {
                background-color: #1f2937;
                border-radius: 20px;
                font-size: 15pt;
            }

            #CardTitle {
                color: #f8fafc;
                font-size: 11pt;
                font-weight: bold;
            }

            #CardSubtitle {
                color: #94a3b8;
                font-size: 9pt;
            }

            #LabelCaps {
                color: #64748b;
                font-size: 8pt;
                font-weight: bold;
                letter-spacing: 1px;
            }

            #CardCombo {
                background-color: #1f2937;
                border: 1px solid #374151;
                border-radius: 6px;
                color: #f8fafc;
                padding: 6px 12px;
                font-size: 10pt;
            }

            #CardCombo::drop-down {
                border: none;
                width: 20px;
            }

            #CardCombo QAbstractItemView {
                background-color: #1f2937;
                color: #f8fafc;
                border: 1px solid #374151;
                selection-background-color: #3b82f6;
            }

            #CardSlider::groove:horizontal {
                height: 6px;
                background: #334155;
                border-radius: 3px;
            }

            #CardSlider::sub-page:horizontal {
                background: #3b82f6;
                border-radius: 3px;
            }

            #CardSlider::handle:horizontal {
                background: #ffffff;
                width: 14px;
                height: 14px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 7px;
            }

            #SliderValueLabel {
                color: #f8fafc;
                font-size: 9pt;
                font-weight: bold;
            }

            #StatusDotOff {
                background-color: #4b5563;
                border-radius: 5px;
            }

            #StatusDotOn {
                background-color: #22c55e;
                border-radius: 5px;
            }

            #StatusDotTesting {
                background-color: #eab308;
                border-radius: 5px;
            }

            #StatusText {
                font-size: 9pt;
                font-weight: 500;
            }

            #CardTestBtn {
                background-color: #1f2937;
                border: 1px solid #374151;
                border-radius: 6px;
                color: #d1d5db;
                font-size: 9pt;
                font-weight: bold;
            }

            #CardTestBtn:hover {
                background-color: #374151;
                color: #ffffff;
            }

            #CardTestBtn:disabled {
                background-color: #111827;
                color: #64748b;
            }

            /* Header Buttons styling */
            #HeaderTitle {
                color: #f8fafc;
                font-size: 18pt;
                font-weight: bold;
            }

            #HeaderSubtitle {
                color: #94a3b8;
                font-size: 10pt;
            }

            #ResetBtn {
                background-color: transparent;
                border: 1px solid #374151;
                border-radius: 6px;
                color: #d1d5db;
                padding: 8px 16px;
                font-size: 9pt;
                font-weight: bold;
            }

            #ResetBtn:hover {
                background-color: #1f2937;
                color: #ffffff;
            }

            #SaveBtn {
                background-color: #2563eb;
                border: none;
                border-radius: 6px;
                color: #ffffff;
                padding: 8px 16px;
                font-size: 9pt;
                font-weight: bold;
            }

            #SaveBtn:hover {
                background-color: #1d4ed8;
            }

            /* General tab widgets */
            QGroupBox {
                border: 1px solid #334155;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 18px;
                color: #f8fafc;
                font-weight: bold;
                font-size: 11pt;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
                color: #3b82f6;
            }

            QLineEdit, QSpinBox, QDoubleSpinBox {
                background-color: #1f2937;
                border: 1px solid #374151;
                border-radius: 6px;
                color: #f8fafc;
                padding: 6px 12px;
                font-size: 10pt;
            }

            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #3b82f6;
            }

            #GeneralCombo {
                background-color: #1f2937;
                border: 1px solid #374151;
                border-radius: 6px;
                color: #f8fafc;
                padding: 6px 12px;
                font-size: 10pt;
            }

            #GeneralCombo::drop-down {
                border: none;
                width: 20px;
            }

            #GeneralCombo QAbstractItemView {
                background-color: #1f2937;
                color: #f8fafc;
                border: 1px solid #374151;
                selection-background-color: #3b82f6;
            }

            QCheckBox {
                color: #f8fafc;
                font-size: 10pt;
            }

            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #374151;
                border-radius: 4px;
                background: #1f2937;
            }

            QCheckBox::indicator:checked {
                background: #3b82f6;
            }

            QFormLayout QLabel {
                color: #94a3b8;
                font-size: 10pt;
                font-weight: 500;
            }

            /* Bottom control panel */
            #StartServiceBtn {
                background-color: #22c55e;
                border: none;
                border-radius: 8px;
                color: #ffffff;
                padding: 12px 24px;
                font-size: 11pt;
                font-weight: bold;
            }

            #StartServiceBtn:hover {
                background-color: #16a34a;
            }

            #StartServiceBtn:disabled {
                background-color: #1f2937;
                color: #64748b;
            }

            #StopServiceBtn {
                background-color: #ef4444;
                border: none;
                border-radius: 8px;
                color: #ffffff;
                padding: 12px 24px;
                font-size: 11pt;
                font-weight: bold;
            }

            #StopServiceBtn:hover {
                background-color: #dc2626;
            }

            #StopServiceBtn:disabled {
                background-color: #1f2937;
                color: #64748b;
            }
        """)
