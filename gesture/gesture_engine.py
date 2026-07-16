"""
GestureEngine — the Finite State Machine described in the spec.

It only looks at hand landmarks and emits signals (presentation mode
entered/exited, swipe left/right, window-switch entered/exited, hand
position). It never touches the keyboard or the overlay directly —
that's AppService's job. This keeps the FSM testable in isolation.

States:
    WAITING_ACTIVATION  -> waiting for open-palm hold to enter Presentation Mode
    PRESENTATION_MODE   -> default mode: overlay visible, swipes send arrow keys,
                           fist enters Window Switch. Pointing the open palm
                           downwards opens the Radial Menu.
    RADIAL_MENU_MODE    -> move hand to highlight a segment, fist to confirm
    WINDOW_SWITCH_MODE  -> active window switching (from Presentation Mode)
    MOUSE_CONTROL_MODE  -> index finger moves cursor, pinch clicks
    (COOLDOWN is handled as a timestamp guard rather than a separate
     state, to avoid an extra state transition on every swipe)
"""

import time
import math
from enum import Enum, auto

from PySide6.QtCore import QObject, Signal

from gesture.hand_shapes import (
    is_open_palm, is_open_palm_down, is_fist, palm_center,
    is_pointing, is_pinch,
)

FIST_CONFIRM_SECONDS = 0.5   # brief hold to confirm fist before window switch
SWIPE_WINDOW_SECONDS = 0.6   # max time allowed to complete a swipe


class GestureState(Enum):
    WAITING_ACTIVATION = auto()
    PRESENTATION_MODE = auto()
    RADIAL_MENU_MODE = auto()
    WINDOW_SWITCH_MODE = auto()
    MOUSE_CONTROL_MODE = auto()


class GestureEngine(QObject):
    # Radial Menu signals
    radial_menu_entered = Signal()
    radial_menu_exited = Signal()
    radial_menu_selection_changed = Signal(int)  # index of highlighted segment

    # Presentation Mode signals
    presentation_mode_entered = Signal()
    presentation_mode_exited = Signal()
    swipe_right = Signal()
    swipe_left = Signal()
    swipe_up = Signal()
    swipe_down = Signal()
    hand_position_changed = Signal(float, float)  # normalized x, y

    # Window Switch Mode signals
    window_switch_entered = Signal()
    window_switch_exited = Signal()

    # Mouse Control Mode signals
    mouse_control_entered = Signal()
    mouse_control_exited = Signal()
    mouse_moved = Signal(float, float)   # normalized x, y of index finger tip
    mouse_clicked = Signal()             # fired once per pinch onset

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._reload_settings()

        self.enabled = False
        self.state = GestureState.WAITING_ACTIVATION

        self._palm_hold_start = None
        self._fist_hold_start = None
        self._cooldown_until = 0.0

        self._track_start_x = None
        self._track_start_y = None
        self._track_start_time = None

        self._radial_hovered_index = -1
        self._was_pinched = False

    def _reload_settings(self):
        self.hold_duration = self.settings.get("activation_hold_seconds", 1.0)
        self.cooldown_duration = self.settings.get("cooldown_seconds", 1.0)
        self.swipe_threshold = self.settings.get("swipe_distance_threshold", 0.15)

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------
    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        if not enabled:
            self._force_back_to_waiting()

    def process_landmarks(self, landmarks):
        """Called for every camera frame with the detected hand (or None)."""
        if not self.enabled:
            return

        now = time.time()
        if now < self._cooldown_until:
            return

        if self.state == GestureState.WAITING_ACTIVATION:
            self._handle_waiting_activation(landmarks, now)
        elif self.state == GestureState.PRESENTATION_MODE:
            self._handle_presentation_mode(landmarks, now)
        elif self.state == GestureState.RADIAL_MENU_MODE:
            self._handle_radial_menu_mode(landmarks, now)
        elif self.state == GestureState.WINDOW_SWITCH_MODE:
            self._handle_window_switch_mode(landmarks, now)
        elif self.state == GestureState.MOUSE_CONTROL_MODE:
            self._handle_mouse_control_mode(landmarks, now)

    # ---------------------------------------------------------
    # WAITING_ACTIVATION  ->  hold open palm  ->  PRESENTATION_MODE
    # ---------------------------------------------------------
    def _handle_waiting_activation(self, landmarks, now):
        if landmarks and is_open_palm(landmarks):
            if self._palm_hold_start is None:
                self._palm_hold_start = now
            elif now - self._palm_hold_start >= self.hold_duration:
                self._enter_presentation_mode()
        else:
            self._palm_hold_start = None

    def _enter_presentation_mode(self):
        self.state = GestureState.PRESENTATION_MODE
        self._palm_hold_start = None
        self._fist_hold_start = None
        self._track_start_x = None
        self._track_start_y = None
        self.presentation_mode_entered.emit()

    # ---------------------------------------------------------
    # PRESENTATION_MODE  (default mode — all existing behaviour preserved)
    # ---------------------------------------------------------
    def _handle_presentation_mode(self, landmarks, now):
        if not landmarks:
            self._track_start_x = None
            self._track_start_y = None
            self._fist_hold_start = None
            return

        # --- Radial Menu Trigger: Open palm pointing DOWN ---
        if is_open_palm_down(landmarks):
            self._enter_radial_menu_mode()
            return

        # --- Fist hold -> Window Switch Mode (unchanged) ---
        if is_fist(landmarks):
            if self._fist_hold_start is None:
                self._fist_hold_start = now
            elif now - self._fist_hold_start >= FIST_CONFIRM_SECONDS:
                self._enter_window_switch_mode()
            return
        else:
            self._fist_hold_start = None

        # --- Open palm: overlay tracking + swipe detection ---
        cx, cy = palm_center(landmarks)
        self.hand_position_changed.emit(cx, cy)
        self._track_swipe(cx, cy, now, in_presentation_mode=True)

    # ---------------------------------------------------------
    # RADIAL_MENU_MODE  (2 segments: Presentasi / Mouse Interaktif)
    # ---------------------------------------------------------
    def _enter_radial_menu_mode(self):
        self.state = GestureState.RADIAL_MENU_MODE
        self._radial_hovered_index = -1
        self.presentation_mode_exited.emit()  # hide overlay while menu is open
        self.radial_menu_entered.emit()

    def _handle_radial_menu_mode(self, landmarks, now):
        # Hand lost → cancel, go back to Presentation Mode
        if not landmarks:
            self._exit_radial_menu_to_presentation()
            return

        # Fist → confirm selection
        if is_fist(landmarks):
            self._execute_radial_menu_selection()
            return

        # Track hand position to determine hovered segment
        cx, cy = palm_center(landmarks)
        dx = cx - 0.5
        dy = cy - 0.5

        # 2 segments, each 180 degrees:
        # Right (index 0): angle -90..90   → Mouse Interaktif
        # Left  (index 1): angle 90..270   → Presentasi
        angle = math.degrees(math.atan2(dy, dx))
        if angle < 0:
            angle += 360

        # Right half: 0-90 and 270-360 → index 0
        # Left half:  90-270           → index 1
        if angle < 90 or angle >= 270:
            index = 0  # Mouse Interaktif (right)
        else:
            index = 1  # Presentasi (left)

        if index != self._radial_hovered_index:
            self._radial_hovered_index = index
            self.radial_menu_selection_changed.emit(index)

    def _execute_radial_menu_selection(self):
        idx = self._radial_hovered_index
        self.radial_menu_exited.emit()

        if idx == 0:
            # Mouse Interaktif
            self._enter_mouse_control_mode()
        else:
            # Presentasi (go back to presentation mode)
            self._enter_presentation_mode()

    def _exit_radial_menu_to_presentation(self):
        """Cancel the menu and go back to Presentation Mode."""
        self.radial_menu_exited.emit()
        self._enter_presentation_mode()

    # ---------------------------------------------------------
    # WINDOW_SWITCH_MODE  (unchanged)
    # ---------------------------------------------------------
    def _enter_window_switch_mode(self):
        self.state = GestureState.WINDOW_SWITCH_MODE
        self._fist_hold_start = None
        self._track_start_x = None
        self._track_start_y = None
        self.window_switch_entered.emit()

    def _handle_window_switch_mode(self, landmarks, now):
        if not landmarks:
            self._track_start_x = None
            self._track_start_y = None
            return

        if is_open_palm(landmarks):
            self._exit_window_switch_mode()
            return

        if is_fist(landmarks):
            cx, cy = palm_center(landmarks)
            self._track_swipe(cx, cy, now, in_presentation_mode=False)

    def _exit_window_switch_mode(self):
        self.window_switch_exited.emit()
        self._enter_cooldown_and_reset()

    # ---------------------------------------------------------
    # MOUSE_CONTROL_MODE  (unchanged)
    # ---------------------------------------------------------
    def _enter_mouse_control_mode(self):
        self.state = GestureState.MOUSE_CONTROL_MODE
        self._track_start_x = None
        self._track_start_y = None
        self._was_pinched = False
        self.mouse_control_entered.emit()

    def _handle_mouse_control_mode(self, landmarks, now):
        if not landmarks:
            self._was_pinched = False
            return

        # True fist (index also curled) → exit
        index_curled = landmarks[8][1] > landmarks[6][1]
        if is_fist(landmarks) and index_curled:
            self._exit_mouse_control_mode()
            return

        # Cursor movement
        if is_pointing(landmarks):
            index_tip = landmarks[8]
            self.mouse_moved.emit(float(index_tip[0]), float(index_tip[1]))

        # Click detection (edge-triggered)
        currently_pinching = is_pinch(landmarks)
        if currently_pinching and not self._was_pinched:
            self.mouse_clicked.emit()
        self._was_pinched = currently_pinching

    def _exit_mouse_control_mode(self):
        self.mouse_control_exited.emit()
        self._enter_cooldown_and_reset()

    # ---------------------------------------------------------
    # Swipe tracking (shared by Presentation and Window Switch)
    # ---------------------------------------------------------
    def _track_swipe(self, cx, cy, now, in_presentation_mode: bool):
        if self._track_start_x is None or self._track_start_y is None:
            self._track_start_x = cx
            self._track_start_y = cy
            self._track_start_time = now
            return

        elapsed = now - self._track_start_time
        if elapsed > SWIPE_WINDOW_SECONDS:
            self._track_start_x = cx
            self._track_start_y = cy
            self._track_start_time = now
            return

        delta_x = cx - self._track_start_x
        delta_y = cy - self._track_start_y

        if abs(delta_x) >= self.swipe_threshold or abs(delta_y) >= self.swipe_threshold:
            if abs(delta_x) >= abs(delta_y):
                if delta_x > 0:
                    self.swipe_right.emit()
                else:
                    self.swipe_left.emit()
            else:
                if delta_y > 0:
                    self.swipe_down.emit()
                else:
                    self.swipe_up.emit()

            self._track_start_x = None
            self._track_start_y = None
            self._track_start_time = None

            if in_presentation_mode:
                self.presentation_mode_exited.emit()
                self._enter_cooldown_and_reset()

    # ---------------------------------------------------------
    # Cooldown / reset helpers
    # ---------------------------------------------------------
    def _enter_cooldown_and_reset(self):
        self._cooldown_until = time.time() + self.cooldown_duration
        self.state = GestureState.WAITING_ACTIVATION
        self._palm_hold_start = None
        self._fist_hold_start = None
        self._track_start_x = None
        self._track_start_y = None
        self._was_pinched = False
        self._radial_hovered_index = -1

    def _force_back_to_waiting(self):
        """Used when gesture control is disabled mid-gesture (hotkey off)."""
        if self.state == GestureState.RADIAL_MENU_MODE:
            self.radial_menu_exited.emit()
        elif self.state == GestureState.PRESENTATION_MODE:
            self.presentation_mode_exited.emit()
        elif self.state == GestureState.WINDOW_SWITCH_MODE:
            self.window_switch_exited.emit()
        elif self.state == GestureState.MOUSE_CONTROL_MODE:
            self.mouse_control_exited.emit()

        self._enter_cooldown_and_reset()

