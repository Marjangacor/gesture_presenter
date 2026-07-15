"""
CameraWorker runs on its own QThread so the UI never freezes while
reading frames / running hand detection. It only emits data (landmarks,
raw frame) — it doesn't know anything about gestures or the FSM.

Uses the MediaPipe Tasks API (HandLandmarker) instead of the removed
legacy `mp.solutions.hands` API.
"""

import time

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision as mp_vision
from PySide6.QtCore import QThread, Signal

from vision.model_loader import ensure_model_downloaded


class CameraWorker(QThread):
    frame_ready = Signal(object)             # raw BGR numpy frame (optional preview)
    hand_landmarks_ready = Signal(object)     # list[(x, y)] normalized, or None
    error_occurred = Signal(str)

    def __init__(self, camera_index: int, detection_confidence: float, parent=None):
        super().__init__(parent)
        self.camera_index = camera_index
        self.detection_confidence = detection_confidence
        self._running = False

    def run(self):
        self._running = True

        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            self.error_occurred.emit(f"Cannot open camera index {self.camera_index}")
            self._running = False
            return

        try:
            model_path = ensure_model_downloaded()
        except Exception as exc:
            self.error_occurred.emit(f"Failed to download hand landmark model: {exc}")
            cap.release()
            self._running = False
            return

        options = mp_vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp_vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=self.detection_confidence,
            min_tracking_confidence=self.detection_confidence,
        )

        landmarker = mp_vision.HandLandmarker.create_from_options(options)
        start_time = time.time()

        try:
            while self._running:
                ok, frame = cap.read()
                if not ok:
                    continue

                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

                timestamp_ms = int((time.time() - start_time) * 1000)
                result = landmarker.detect_for_video(mp_image, timestamp_ms)

                if result.hand_landmarks:
                    points = [(lm.x, lm.y) for lm in result.hand_landmarks[0]]
                    self.hand_landmarks_ready.emit(points)
                else:
                    self.hand_landmarks_ready.emit(None)

                self.frame_ready.emit(frame)
        finally:
            landmarker.close()
            cap.release()

    def stop(self):
        self._running = False
        self.wait()