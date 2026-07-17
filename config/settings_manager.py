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
        with open(DEFAULT_SETTINGS_PATH, "r", encoding="utf-8") as f:
            defaults = json.load(f)

        if USER_SETTINGS_PATH.exists():
            try:
                with open(USER_SETTINGS_PATH, "r", encoding="utf-8") as f:
                    user_settings = json.load(f)
                    return self._deep_merge(defaults, user_settings)
            except Exception:
                return defaults
        return defaults

    def _deep_merge(self, d1: dict, d2: dict) -> dict:
        result = d1.copy()
        for k, v in d2.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = self._deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    def get(self, key: str, default=None):
        return self._settings.get(key, default)

    def get_all(self) -> dict:
        return self._settings

    def update(self, key: str, value) -> None:
        self._settings[key] = value

    def save(self) -> None:
        with open(USER_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(self._settings, f, indent=4)

    def reset(self) -> None:
        with open(DEFAULT_SETTINGS_PATH, "r", encoding="utf-8") as f:
            self._settings = json.load(f)
        self.save()
