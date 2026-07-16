import json
from pathlib import Path

DEFAULT_SETTINGS_PATH = Path(__file__).parent / "default_settings.json"
USER_SETTINGS_PATH = Path(__file__).parent / "user_settings.json"


class SettingsManager:
    """
    Loads and saves application settings as JSON.
    Falls back to default_settings.json if no user settings exist yet.
    """

    def __init__(self):
        self._settings = self._load()

    def _load(self) -> dict:
        if USER_SETTINGS_PATH.exists():
            path = USER_SETTINGS_PATH
        else:
            path = DEFAULT_SETTINGS_PATH

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get(self, key: str, default=None):
        return self._settings.get(key, default)

    def get_all(self) -> dict:
        return self._settings

    def update(self, key: str, value) -> None:
        self._settings[key] = value

    def save(self) -> None:
        with open(USER_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(self._settings, f, indent=4)
