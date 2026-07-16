from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QFormLayout,
    QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit,
    QCheckBox, QPushButton, QGroupBox, QHBoxLayout
)

from config.settings_manager import SettingsManager
from services.app_service import AppService
from vision.camera_utils import list_available_cameras


class MainWindow(QMainWindow):
    def __init__(self, settings: SettingsManager):
        super().__init__()
        self.settings = settings
        self.app_service = AppService(settings)

        self.setWindowTitle("Gesture Presenter")
        self.resize(420, 480)

        self._build_ui()
        self._load_settings_into_ui()
        self._connect_signals()

    # ---------------------------------------------------------
    # UI Construction
    # ---------------------------------------------------------
    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)

        root_layout.addWidget(self._build_camera_group())
        root_layout.addWidget(self._build_detection_group())
        root_layout.addWidget(self._build_hotkey_group())
        root_layout.addWidget(self._build_overlay_group())
        root_layout.addLayout(self._build_control_buttons())

    def _build_camera_group(self) -> QGroupBox:
        group = QGroupBox("Camera")
        layout = QFormLayout(group)

        self.camera_combo = QComboBox()
        available = list_available_cameras()
        if not available:
            available = [0]  # fall back so the combo isn't empty
        for index in available:
            self.camera_combo.addItem(f"Camera {index}", userData=index)

        layout.addRow("Select Camera:", self.camera_combo)
        return group

    def _build_detection_group(self) -> QGroupBox:
        group = QGroupBox("Detection & Timing")
        layout = QFormLayout(group)

        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.1, 1.0)
        self.confidence_spin.setSingleStep(0.05)

        self.hold_duration_spin = QDoubleSpinBox()
        self.hold_duration_spin.setRange(0.5, 10.0)
        self.hold_duration_spin.setSingleStep(0.5)
        self.hold_duration_spin.setSuffix(" s")

        self.cooldown_spin = QDoubleSpinBox()
        self.cooldown_spin.setRange(0.1, 5.0)
        self.cooldown_spin.setSingleStep(0.1)
        self.cooldown_spin.setSuffix(" s")

        self.swipe_distance_spin = QDoubleSpinBox()
        self.swipe_distance_spin.setRange(0.05, 1.0)
        self.swipe_distance_spin.setSingleStep(0.05)

        layout.addRow("Detection Confidence:", self.confidence_spin)
        layout.addRow("Activation Hold Duration:", self.hold_duration_spin)
        layout.addRow("Cooldown:", self.cooldown_spin)
        layout.addRow("Swipe Distance:", self.swipe_distance_spin)
        return group

    def _build_hotkey_group(self) -> QGroupBox:
        group = QGroupBox("Hotkey")
        layout = QFormLayout(group)

        self.hotkey_input = QLineEdit()
        self.hotkey_input.setPlaceholderText("e.g. f8")

        layout.addRow("Toggle Gesture Control:", self.hotkey_input)
        return group

    def _build_overlay_group(self) -> QGroupBox:
        group = QGroupBox("Overlay")
        layout = QFormLayout(group)

        self.overlay_enabled_check = QCheckBox("Enable overlay")

        self.overlay_radius_spin = QSpinBox()
        self.overlay_radius_spin.setRange(5, 100)
        self.overlay_radius_spin.setSuffix(" px")

        self.overlay_opacity_spin = QDoubleSpinBox()
        self.overlay_opacity_spin.setRange(0.1, 1.0)
        self.overlay_opacity_spin.setSingleStep(0.05)

        layout.addRow(self.overlay_enabled_check)
        layout.addRow("Radius:", self.overlay_radius_spin)
        layout.addRow("Opacity:", self.overlay_opacity_spin)
        return group

    def _build_control_buttons(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        self.start_button = QPushButton("Start")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)

        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)
        return layout

    # ---------------------------------------------------------
    # Settings <-> UI binding
    # ---------------------------------------------------------
    def _load_settings_into_ui(self):
        data = self.settings.get_all()

        target_camera_index = data.get("camera_index", 0)
        combo_position = self.camera_combo.findData(target_camera_index)
        self.camera_combo.setCurrentIndex(combo_position if combo_position >= 0 else 0)
        self.confidence_spin.setValue(data.get("detection_confidence", 0.7))
        self.hold_duration_spin.setValue(data.get("activation_hold_seconds", 3.0))
        self.cooldown_spin.setValue(data.get("cooldown_seconds", 1.0))
        self.swipe_distance_spin.setValue(data.get("swipe_distance_threshold", 0.15))

        self.hotkey_input.setText(
            data.get("hotkeys", {}).get("toggle_gesture_control", "f8")
        )

        overlay_data = data.get("overlay", {})
        self.overlay_enabled_check.setChecked(overlay_data.get("enabled", True))
        self.overlay_radius_spin.setValue(overlay_data.get("radius", 20))
        self.overlay_opacity_spin.setValue(overlay_data.get("opacity", 0.5))

    def _connect_signals(self):
        # Every time a value changes, push it back into SettingsManager immediately.
        # This keeps self.settings as the single source of truth at all times.
        self.camera_combo.currentIndexChanged.connect(
            lambda i: self.settings.update(
                "camera_index", self.camera_combo.itemData(i) if i >= 0 else 0
            )
        )
        self.confidence_spin.valueChanged.connect(
            lambda v: self.settings.update("detection_confidence", v)
        )
        self.hold_duration_spin.valueChanged.connect(
            lambda v: self.settings.update("activation_hold_seconds", v)
        )
        self.cooldown_spin.valueChanged.connect(
            lambda v: self.settings.update("cooldown_seconds", v)
        )
        self.swipe_distance_spin.valueChanged.connect(
            lambda v: self.settings.update("swipe_distance_threshold", v)
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

        self.start_button.clicked.connect(self._on_start_clicked)
        self.stop_button.clicked.connect(self._on_stop_clicked)

    # ---------------------------------------------------------
    # Start / Stop handlers (logic filled in later steps)
    # ---------------------------------------------------------
    def _on_start_clicked(self):
        self.settings.save()
        self.app_service.start()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def _on_stop_clicked(self):
        self.app_service.stop()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def closeEvent(self, event):
        # Make sure camera thread / hotkey listener / overlay are cleaned up
        # even if the window is closed without pressing Stop first.
        self.app_service.stop()
        event.accept()
