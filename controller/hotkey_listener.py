"""
Listens globally for a single configurable key (default F8) so gesture
control can be toggled even when the app window isn't focused.
Runs its own pynput listener thread under the hood; emits a Qt signal
so the rest of the app doesn't need to know about pynput at all.
"""

from pynput import keyboard
from PySide6.QtCore import QObject, Signal


class HotkeyListener(QObject):
    hotkey_pressed = Signal()

    def __init__(self, key_name: str = "f8", parent=None):
        super().__init__(parent)
        self.key_name = key_name.lower()
        self._listener = None

    def _on_press(self, key):
        try:
            name = key.name.lower()          # special keys: f1-f12, esc, etc.
        except AttributeError:
            name = str(key).strip("'").lower()  # character keys

        if name == self.key_name:
            self.hotkey_pressed.emit()

    def start(self):
        self._listener = keyboard.Listener(on_press=self._on_press)
        self._listener.start()

    def stop(self):
        if self._listener:
            self._listener.stop()
            self._listener = None

    def update_key(self, key_name: str):
        self.key_name = key_name.lower()
