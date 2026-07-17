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

FIST_CONFIRM_SECONDS = 0.4   # hold duration before window switch fires (quick enough to feel instant, slow enough to avoid accidents)
SWIPE_WINDOW_SECONDS = 0.6   # max time allowed to complete a swipe
SWIPE_DOWN_WINDOW_SECONDS = 1.2  # wider window for swipe-down → menu trigger
SWIPE_DOWN_THRESHOLD = 0.12  # how far down the hand must travel to open menu
RADIAL_HOLD_SECONDS = 2.0   # how long to hover on a segment to select it


class GestureState(Enum):
    WAITING_ACTIVATION = auto()
    PRESENTATION_MODE = auto()
    RADIAL_MENU_MODE = auto()
    WINDOW_SWITCH_MODE = auto()
    MOUSE_CONTROL_MODE = auto()


class GestureEngine(QObject):
    # Radial Menu signals
    radial_menu_entered = Signal(int)
    radial_menu_exited = Signal()
    radial_menu_selection_changed = Signal(int)  # index of highlighted segment
    radial_menu_hover_progress = Signal(float)   # 0.0..1.0 fill progress for hold indicator

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
    mouse_clicked = Signal()             # kept for compatibility but unused
    mouse_pressed = Signal()             # fired on pinch START (hold left button)
    mouse_released = Signal()            # fired on pinch END   (release left button)

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
        self._hover_hold_start = None  # tracks how long user hovers on current segment

        # Persistent selected mode: 1 = Presentasi (default), 0 = Mouse Interaktif.
        # This survives brief state glitches (e.g. frame dropout → re-entry to
        # PRESENTATION_MODE) so that window-switch is never fired while mouse
        # mode is the intentionally selected feature.
        self._active_mode = 1

        # Dedicated swipe-down tracker for menu trigger (wider window, lower threshold)
        self._swipe_down_start_y = None
        self._swipe_down_start_time = None

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
        self._active_mode = 1  # presentation features enabled
        self._palm_hold_start = None
        self._fist_hold_start = None
        self._track_start_x = None
        self._track_start_y = None
        self._swipe_down_start_y = None
        self._swipe_down_start_time = None
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

        # --- Fist hold → Window Switch (only when Presentation mode is actively selected) ---
        if is_fist(landmarks) and self._active_mode == 1:
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
        self._track_swipe(cx, cy, now)
        self._track_swipe_down_for_menu(cy, now)

    # ---------------------------------------------------------
    # RADIAL_MENU_MODE  (2 segments: Presentasi / Mouse Interaktif)
    # ---------------------------------------------------------
    def _enter_radial_menu_mode(self):
        # Determine active mode before switching
        if self.state == GestureState.MOUSE_CONTROL_MODE:
            self._radial_active_index = 0
            self.mouse_control_exited.emit()
        else:
            self._radial_active_index = 1
            self.presentation_mode_exited.emit()

        # Reset all tracking — no cooldown needed, menu is open
        self._track_start_x = None
        self._track_start_y = None
        self._track_start_time = None
        self._swipe_down_start_y = None
        self._swipe_down_start_time = None
        self._fist_hold_start = None
        self._hover_hold_start = None

        self.state = GestureState.RADIAL_MENU_MODE
        self._radial_hovered_index = -1
        self.radial_menu_entered.emit(self._radial_active_index)

    def _handle_radial_menu_mode(self, landmarks, now):
        # Hand lost → cancel, go back to previous mode
        if not landmarks:
            self.radial_menu_hover_progress.emit(0.0)
            self._exit_radial_menu_to_presentation()
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

        # If segment changed, reset hover timer and progress
        if index != self._radial_hovered_index:
            self._radial_hovered_index = index
            self._hover_hold_start = now
            self.radial_menu_hover_progress.emit(0.0)
            self.radial_menu_selection_changed.emit(index)
            return

        # Compute hold progress and emit for visual feedback
        if self._hover_hold_start is None:
            self._hover_hold_start = now

        elapsed = now - self._hover_hold_start
        progress = min(1.0, elapsed / RADIAL_HOLD_SECONDS)
        self.radial_menu_hover_progress.emit(progress)

        # Confirm selection after holding long enough
        if elapsed >= RADIAL_HOLD_SECONDS:
            self._execute_radial_menu_selection()

    def _execute_radial_menu_selection(self):
        idx = self._radial_hovered_index
        if idx == -1:
            idx = getattr(self, '_radial_active_index', 1)

        self._hover_hold_start = None
        self.radial_menu_hover_progress.emit(0.0)
        self.radial_menu_exited.emit()

        if idx == 0:
            self._enter_mouse_control_mode()
        else:
            self._enter_presentation_mode()

    def _exit_radial_menu_to_presentation(self):
        """Cancel the menu and go back to the previous mode."""
        self.radial_menu_exited.emit()
        if hasattr(self, '_radial_active_index') and self._radial_active_index == 0:
            self._enter_mouse_control_mode()
        else:
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
            self._track_swipe(cx, cy, now)

    def _exit_window_switch_mode(self):
        self.window_switch_exited.emit()
        self._enter_cooldown_and_reset()

    # ---------------------------------------------------------
    # MOUSE_CONTROL_MODE  (unchanged)
    # ---------------------------------------------------------
    def _enter_mouse_control_mode(self):
        self.state = GestureState.MOUSE_CONTROL_MODE
        self._active_mode = 0  # mouse features enabled, presentation features blocked
        self._track_start_x = None
        self._track_start_y = None
        self._track_start_time = None
        self._swipe_down_start_y = None
        self._swipe_down_start_time = None
        self._fist_hold_start = None  # defensive: never carry over fist timer
        self._was_pinched = False
        self.mouse_control_entered.emit()

    def _handle_mouse_control_mode(self, landmarks, now):
        if not landmarks:
            # Hand not visible: pause cursor, keep mode alive.
            # Mark swipe-down tracker for reset so when the hand reappears,
            # the start position seeds from the new position (prevents accidental
            # menu trigger if hand comes back at a lower point than it left).
            self._was_pinched = False
            self._swipe_down_start_y = None
            self._swipe_down_start_time = None
            return

        # Note: We intentionally do NOT exit mouse control mode via a fist gesture anymore.
        # Pinching often looks like a fist to the camera (index tip goes below the knuckle).
        # Exiting this mode is now strictly handled by the on-screen "Menu" button.

        # Open palm detection (swipe down) is intentionally removed from Mouse Control Mode
        # to prevent accidental menu triggers. The menu will now be triggered via an on-screen button.

        # Cursor movement: track palm center whenever it's visible,
        # this provides a stable point for moving the cursor even during a pinch,
        # unlike the index finger which moves around when pinching.
        if landmarks:
            cx, cy = palm_center(landmarks)
            self.mouse_moved.emit(float(cx), float(cy))

        # Pinch hold/release detection (edge-triggered on state change)
        currently_pinching = is_pinch(landmarks) if landmarks else False
        if currently_pinching and not self._was_pinched:
            self.mouse_pressed.emit()      # pinch started → hold left button
        elif not currently_pinching and self._was_pinched:
            self.mouse_released.emit()     # pinch ended   → release left button
        self._was_pinched = currently_pinching

    def _exit_mouse_control_mode(self):
        self.mouse_control_exited.emit()
        self._enter_cooldown_and_reset()

    def open_radial_menu(self):
        """Allows external UI elements to manually open the radial menu."""
        if self.state != GestureState.RADIAL_MENU_MODE:
            self._enter_radial_menu_mode()

    # ---------------------------------------------------------
    # Dedicated swipe-down tracker for menu trigger
    # ---------------------------------------------------------
    def _track_swipe_down_for_menu(self, cy, now):
        """Independent, dedicated tracker for swipe-down → radial menu.
        Uses a longer time window and lower threshold than the regular
        swipe detector so the gesture is reliably caught even if the hand
        moves slowly or the regular swipe tracker resets itself.
        """
        if self._swipe_down_start_y is None:
            self._swipe_down_start_y = cy
            self._swipe_down_start_time = now
            return

        elapsed = now - self._swipe_down_start_time
        if elapsed > SWIPE_DOWN_WINDOW_SECONDS:
            # Window expired — reset and start fresh from current position
            self._swipe_down_start_y = cy
            self._swipe_down_start_time = now
            return

        delta_y = cy - self._swipe_down_start_y
        if delta_y >= SWIPE_DOWN_THRESHOLD:
            # Confirmed swipe-down — open the menu
            self._swipe_down_start_y = None
            self._swipe_down_start_time = None
            if self.state in (GestureState.PRESENTATION_MODE, GestureState.MOUSE_CONTROL_MODE):
                self._enter_radial_menu_mode()

    # ---------------------------------------------------------
    # Swipe tracking (shared by Presentation and Window Switch)
    # ---------------------------------------------------------
    def _track_swipe(self, cx, cy, now):
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
            self._track_start_x = None
            self._track_start_y = None
            self._track_start_time = None

            is_swipe_down = (abs(delta_y) > abs(delta_x) and delta_y > 0)

            # Swipe down is handled by _track_swipe_down_for_menu; skip here.
            if is_swipe_down and self.state in (GestureState.PRESENTATION_MODE, GestureState.MOUSE_CONTROL_MODE):
                return

            # In Mouse Control Mode, slide-change swipes (left/right/up) are blocked.
            # Only swipe down (to open menu) is allowed, and that's handled above.
            if self.state == GestureState.MOUSE_CONTROL_MODE:
                return

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

            if self.state == GestureState.PRESENTATION_MODE:
                self.presentation_mode_exited.emit()
                self._enter_cooldown_and_reset()

    # ---------------------------------------------------------
    # Cooldown / reset helpers
    # ---------------------------------------------------------
    def _enter_cooldown_and_reset(self):
        # Safety: release left button if it was held during a pinch
        if self._was_pinched:
            self.mouse_released.emit()
        self._cooldown_until = time.time() + self.cooldown_duration
        self.state = GestureState.WAITING_ACTIVATION
        self._palm_hold_start = None
        self._fist_hold_start = None
        self._track_start_x = None
        self._track_start_y = None
        self._track_start_time = None
        self._swipe_down_start_y = None
        self._swipe_down_start_time = None
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

        self._active_mode = 1  # reset to presentation on full disable
        self._enter_cooldown_and_reset()

