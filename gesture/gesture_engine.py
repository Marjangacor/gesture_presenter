"""
GestureEngine — the Finite State Machine described in the spec.

It only looks at hand landmarks and emits signals (presentation mode
entered/exited, swipe left/right, window-switch entered/exited, hand
position). It never touches the keyboard or the overlay directly —
that's AppService's job. This keeps the FSM testable in isolation.

States:
    WAITING_ACTIVATION  -> waiting for open-palm hold to start Presentation Mode
    PRESENTATION_MODE   -> overlay visible, swipes send arrow keys
    WINDOW_SWITCH_MODE  -> entered via fist while in Presentation Mode
    (COOLDOWN is handled as a timestamp guard rather than a separate
     state, to avoid an extra state transition on every swipe)
"""

import time
from enum import Enum, auto

from PySide6.QtCore import QObject, Signal

from gesture.hand_shapes import is_open_palm, is_fist, palm_center

FIST_CONFIRM_SECONDS = 0.5   # brief hold to confirm fist before Win+Tab
SWIPE_WINDOW_SECONDS = 0.6   # max time allowed to complete a swipe


class GestureState(Enum):
    WAITING_ACTIVATION = auto()
    PRESENTATION_MODE = auto()
    WINDOW_SWITCH_MODE = auto()


class GestureEngine(QObject):
    presentation_mode_entered = Signal()
    presentation_mode_exited = Signal()
    window_switch_entered = Signal()
    window_switch_exited = Signal()
    swipe_right = Signal()
    swipe_left = Signal()
    swipe_up = Signal()
    swipe_down = Signal()
    hand_position_changed = Signal(float, float)  # normalized x, y

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

    def _reload_settings(self):
        self.hold_duration = self.settings.get("activation_hold_seconds", 3.0)
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
        elif self.state == GestureState.WINDOW_SWITCH_MODE:
            self._handle_window_switch_mode(landmarks, now)

    # ---------------------------------------------------------
    # WAITING_ACTIVATION
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
        self._track_start_x = None
        self._track_start_y = None
        self.presentation_mode_entered.emit()

    # ---------------------------------------------------------
    # PRESENTATION_MODE
    # ---------------------------------------------------------
    def _handle_presentation_mode(self, landmarks, now):
        if not landmarks:
            self._track_start_x = None
            self._track_start_y = None
            self._fist_hold_start = None
            return

        if is_fist(landmarks):
            if self._fist_hold_start is None:
                self._fist_hold_start = now
            elif now - self._fist_hold_start >= FIST_CONFIRM_SECONDS:
                self._enter_window_switch_mode()
            return
        else:
            self._fist_hold_start = None

        cx, cy = palm_center(landmarks)
        self.hand_position_changed.emit(cx, cy)
        self._track_swipe(cx, cy, now, in_presentation_mode=True)

    def _enter_window_switch_mode(self):
        self.state = GestureState.WINDOW_SWITCH_MODE
        self._fist_hold_start = None
        self._track_start_x = None
        self._track_start_y = None
        self.window_switch_entered.emit()

    # ---------------------------------------------------------
    # WINDOW_SWITCH_MODE
    # ---------------------------------------------------------
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
    # Swipe tracking (shared by both modes)
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

            # Per spec: a swipe in Presentation Mode is followed by cooldown
            # and a return to Waiting Activation. In Window Switch Mode,
            # swipes can repeat freely until the hand opens again.
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

    def _force_back_to_waiting(self):
        """Used when gesture control is disabled mid-gesture (hotkey off)."""
        if self.state == GestureState.PRESENTATION_MODE:
            self.presentation_mode_exited.emit()
        elif self.state == GestureState.WINDOW_SWITCH_MODE:
            self.window_switch_exited.emit()

        self.state = GestureState.WAITING_ACTIVATION
        self._palm_hold_start = None
        self._fist_hold_start = None
        self._track_start_x = None
        self._track_start_y = None
