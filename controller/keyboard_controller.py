"""
Thin wrapper around pynput. This is the ONLY place in the app that
actually sends keystrokes to Windows — every other module just emits
signals and lets AppService call these methods.
"""

from pynput.keyboard import Controller, Key


class KeyboardController:
    def __init__(self):
        self._controller = Controller()

    def press_right_arrow(self):
        self._controller.press(Key.right)
        self._controller.release(Key.right)

    def press_left_arrow(self):
        self._controller.press(Key.left)
        self._controller.release(Key.left)

    def press_enter(self):
        self._controller.press(Key.enter)
        self._controller.release(Key.enter)

    def press_win_tab(self):
        self._controller.press(Key.cmd)
        self._controller.press(Key.tab)
        self._controller.release(Key.tab)
        self._controller.release(Key.cmd)
