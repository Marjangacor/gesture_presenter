"""
Thin wrapper around pynput. This is the ONLY place in the app that
actually sends keystrokes to Windows — every other module just emits
signals and lets AppService call these methods.
"""

from pynput.keyboard import Controller as _KeyboardController, Key
from pynput.mouse import Controller as _MouseController, Button


class KeyboardController:
    def __init__(self):
        self._keyboard = _KeyboardController()
        self._mouse = _MouseController()

    # ------------------------------------------------------------------
    # Keyboard actions
    # ------------------------------------------------------------------
    def press_right_arrow(self):
        self._keyboard.press(Key.right)
        self._keyboard.release(Key.right)

    def press_left_arrow(self):
        self._keyboard.press(Key.left)
        self._keyboard.release(Key.left)

    def press_up_arrow(self):
        self._keyboard.press(Key.up)
        self._keyboard.release(Key.up)

    def press_down_arrow(self):
        self._keyboard.press(Key.down)
        self._keyboard.release(Key.down)

    def press_enter(self):
        self._keyboard.press(Key.enter)
        self._keyboard.release(Key.enter)

    def press_win_tab(self):
        self._keyboard.press(Key.cmd)
        self._keyboard.press(Key.tab)
        self._keyboard.release(Key.tab)
        self._keyboard.release(Key.cmd)

    # ------------------------------------------------------------------
    # Mouse actions
    # ------------------------------------------------------------------
    def move_mouse_to(self, x: int, y: int):
        """Move the mouse cursor to absolute screen coordinates (x, y)."""
        self._mouse.position = (x, y)

    def mouse_left_click(self):
        """Perform a single left mouse button click."""
        self._mouse.click(Button.left, 1)

    def mouse_left_press(self):
        """Press and hold the left mouse button (for drag operations)."""
        self._mouse.press(Button.left)

    def mouse_left_release(self):
        """Release the left mouse button."""
        self._mouse.release(Button.left)
