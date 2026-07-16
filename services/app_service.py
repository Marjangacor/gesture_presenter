"""
AppService is the only module that knows about every other piece at
once (camera, gesture engine, keyboard controller, overlay, hotkey
listener). Everything else stays decoupled and only talks through
signals — this is what MainWindow's Start/Stop buttons call into.
"""

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from vision.camera_worker import CameraWorker
from gesture.gesture_engine import GestureEngine
from controller.keyboard_controller import KeyboardController
from controller.hotkey_listener import HotkeyListener
from overlay.overlay_window import OverlayWindow
from overlay.radial_menu import RadialMenuWindow


class AppService(QObject):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings

        self.camera_worker = None
        self.gesture_engine = None
        self.keyboard_controller = KeyboardController()
        self.overlay = None
        self.radial_menu = None
        self.hotkey_listener = None

        self._gesture_enabled = False

        # EMA (Exponential Moving Average) state for smooth mouse movement.
        # Reset every time Mouse Control Mode is entered.
        self._mouse_ema_x = None
        self._mouse_ema_y = None
        self._mouse_alpha = 0.35  # lower = smoother but laggier, higher = snappier

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
        
        self.radial_menu = RadialMenuWindow()

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
            
        if self.radial_menu:
            self.radial_menu.hide()
            self.radial_menu = None

        self.gesture_engine = None
        self._gesture_enabled = False

    # ---------------------------------------------------------
    def _toggle_gesture_control(self):
        self._gesture_enabled = not self._gesture_enabled
        self.gesture_engine.set_enabled(self._gesture_enabled)
        if not self._gesture_enabled:
            if self.overlay:
                self.overlay.hide()
            if self.radial_menu:
                self.radial_menu.hide()

    def _connect_gesture_signals(self):
        ge = self.gesture_engine
        
        # Radial Menu signals
        ge.radial_menu_entered.connect(self._on_radial_menu_entered)
        ge.radial_menu_exited.connect(self._on_radial_menu_exited)
        ge.radial_menu_selection_changed.connect(self._on_radial_menu_selection_changed)
        
        # Presentation Mode signals
        ge.presentation_mode_entered.connect(self._on_presentation_entered)
        ge.presentation_mode_exited.connect(self._on_presentation_exited)
        ge.window_switch_entered.connect(self._on_window_switch_entered)
        ge.window_switch_exited.connect(self._on_window_switch_exited)
        ge.swipe_right.connect(self._on_swipe_right)
        ge.swipe_left.connect(self._on_swipe_left)
        ge.swipe_up.connect(self._on_swipe_up)
        ge.swipe_down.connect(self._on_swipe_down)
        ge.hand_position_changed.connect(self._on_hand_position_changed)
        # Mouse Control Mode signals
        ge.mouse_control_entered.connect(self._on_mouse_control_entered)
        ge.mouse_control_exited.connect(self._on_mouse_control_exited)
        ge.mouse_moved.connect(self._on_mouse_moved)
        ge.mouse_clicked.connect(self._on_mouse_clicked)

    # ---------------------------------------------------------
    # Radial Menu handlers (new)
    # ---------------------------------------------------------
    def _on_radial_menu_entered(self):
        if self.radial_menu:
            self.radial_menu.show_in_center()
            
    def _on_radial_menu_exited(self):
        if self.radial_menu:
            self.radial_menu.hide()
            
    def _on_radial_menu_selection_changed(self, index: int):
        if self.radial_menu:
            self.radial_menu.set_hovered_index(index)

    # ---------------------------------------------------------
    # Presentation Mode handlers (unchanged)
    # ---------------------------------------------------------
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

    def _on_swipe_up(self):
        self.keyboard_controller.press_up_arrow()

    def _on_swipe_down(self):
        self.keyboard_controller.press_down_arrow()

    def _on_hand_position_changed(self, x, y):
        if self.overlay:
            self.overlay.move_to_normalized(x, y)

    # ---------------------------------------------------------
    # Mouse Control Mode handlers (new)
    # ---------------------------------------------------------
    def _on_mouse_control_entered(self):
        """Hide the overlay and reset EMA when Mouse Control Mode starts."""
        if self.overlay:
            self.overlay.hide()
        self._mouse_ema_x = None
        self._mouse_ema_y = None

    def _on_mouse_control_exited(self):
        """Clean up EMA state when Mouse Control Mode ends."""
        self._mouse_ema_x = None
        self._mouse_ema_y = None

    def _on_mouse_moved(self, norm_x: float, norm_y: float):
        """Convert normalized finger-tip coords to screen pixels and move mouse.

        Uses EMA smoothing to reduce jitter.  norm_x / norm_y come from
        MediaPipe (0.0 = left/top, 1.0 = right/bottom).
        """
        screen = QApplication.primaryScreen().geometry()
        raw_x = norm_x * screen.width()
        raw_y = norm_y * screen.height()

        if self._mouse_ema_x is None:
            # First sample: seed the filter
            self._mouse_ema_x = raw_x
            self._mouse_ema_y = raw_y
        else:
            a = self._mouse_alpha
            self._mouse_ema_x = a * raw_x + (1.0 - a) * self._mouse_ema_x
            self._mouse_ema_y = a * raw_y + (1.0 - a) * self._mouse_ema_y

        self.keyboard_controller.move_mouse_to(
            int(self._mouse_ema_x), int(self._mouse_ema_y)
        )

    def _on_mouse_clicked(self):
        """Fire a single left click (edge-triggered from GestureEngine)."""
        self.keyboard_controller.mouse_left_click()
