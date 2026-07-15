"""
AppService is the only module that knows about every other piece at
once (camera, gesture engine, keyboard controller, overlay, hotkey
listener). Everything else stays decoupled and only talks through
signals — this is what MainWindow's Start/Stop buttons call into.
"""

from PySide6.QtCore import QObject

from vision.camera_worker import CameraWorker
from gesture.gesture_engine import GestureEngine
from controller.keyboard_controller import KeyboardController
from controller.hotkey_listener import HotkeyListener
from overlay.overlay_window import OverlayWindow


class AppService(QObject):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings

        self.camera_worker = None
        self.gesture_engine = None
        self.keyboard_controller = KeyboardController()
        self.overlay = None
        self.hotkey_listener = None

        self._gesture_enabled = False

    # ---------------------------------------------------------
    def start(self):
        camera_index = self.settings.get("camera_index", 0)
        confidence = self.settings.get("detection_confidence", 0.7)

        self.gesture_engine = GestureEngine(self.settings)
        self._connect_gesture_signals()

        self.camera_worker = CameraWorker(camera_index, confidence)
        self.camera_worker.hand_landmarks_ready.connect(
            self.gesture_engine.process_landmarks
        )
        self.camera_worker.start()

        overlay_settings = self.settings.get("overlay", {})
        self.overlay = OverlayWindow(
            radius=overlay_settings.get("radius", 20),
            opacity=overlay_settings.get("opacity", 0.5),
        )

        hotkey = self.settings.get("hotkeys", {}).get("toggle_gesture_control", "f8")
        self.hotkey_listener = HotkeyListener(hotkey)
        self.hotkey_listener.hotkey_pressed.connect(self._toggle_gesture_control)
        self.hotkey_listener.start()

        self._gesture_enabled = False
        self.gesture_engine.set_enabled(False)  # start in Standby Mode

    def stop(self):
        if self.hotkey_listener:
            self.hotkey_listener.stop()
            self.hotkey_listener = None

        if self.camera_worker:
            self.camera_worker.stop()
            self.camera_worker = None

        if self.overlay:
            self.overlay.hide()
            self.overlay = None

        self.gesture_engine = None
        self._gesture_enabled = False

    # ---------------------------------------------------------
    def _toggle_gesture_control(self):
        self._gesture_enabled = not self._gesture_enabled
        self.gesture_engine.set_enabled(self._gesture_enabled)
        if not self._gesture_enabled and self.overlay:
            self.overlay.hide()

    def _connect_gesture_signals(self):
        ge = self.gesture_engine
        ge.presentation_mode_entered.connect(self._on_presentation_entered)
        ge.presentation_mode_exited.connect(self._on_presentation_exited)
        ge.window_switch_entered.connect(self._on_window_switch_entered)
        ge.window_switch_exited.connect(self._on_window_switch_exited)
        ge.swipe_right.connect(self._on_swipe_right)
        ge.swipe_left.connect(self._on_swipe_left)
        ge.hand_position_changed.connect(self._on_hand_position_changed)

    def _on_presentation_entered(self):
        if self.overlay:
            self.overlay.show()

    def _on_presentation_exited(self):
        if self.overlay:
            self.overlay.hide()

    def _on_window_switch_entered(self):
        self.keyboard_controller.press_win_tab()

    def _on_window_switch_exited(self):
        self.keyboard_controller.press_enter()
        if self.overlay:
            self.overlay.hide()

    def _on_swipe_right(self):
        self.keyboard_controller.press_right_arrow()

    def _on_swipe_left(self):
        self.keyboard_controller.press_left_arrow()

    def _on_hand_position_changed(self, x, y):
        if self.overlay:
            self.overlay.move_to_normalized(x, y)
