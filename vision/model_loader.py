"""
The legacy `mp.solutions.hands` API was removed from recent MediaPipe
PyPI releases. We now use the newer MediaPipe Tasks API
(`mp.tasks.vision.HandLandmarker`), which needs a small model bundle
file (~7-10 MB) instead of being bundled in the package.

This downloads it once and caches it under assets/models/, so it only
happens on the very first run.
"""

import urllib.request
from pathlib import Path

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
)

MODEL_DIR = Path(__file__).resolve().parent.parent / "assets" / "models"
MODEL_PATH = MODEL_DIR / "hand_landmarker.task"


def ensure_model_downloaded() -> Path:
    """Downloads the model bundle if it isn't already cached locally."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    if not MODEL_PATH.exists():
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)

    return MODEL_PATH