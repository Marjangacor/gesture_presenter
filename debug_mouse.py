"""
debug_mouse.py — Standalone test untuk gesture pointing + pinch + mouse movement.
Jalankan dengan: python debug_mouse.py
Tekan Ctrl+C untuk berhenti.
"""

import time
import sys
import os

sys.path.insert(0, r"d:\rajantelkom\KELAS 12\gesture_presenter")

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision as mp_vision

from gesture.hand_shapes import is_pointing, is_pinch, is_fist
from controller.keyboard_controller import KeyboardController

# Ukuran layar (tanpa Qt)
import ctypes
SCREEN_W = ctypes.windll.user32.GetSystemMetrics(0)
SCREEN_H = ctypes.windll.user32.GetSystemMetrics(1)
print(f"Screen: {SCREEN_W}x{SCREEN_H}")

# Cari model
from vision.model_loader import ensure_model_downloaded
MODEL_PATH = str(ensure_model_downloaded())
print(f"Model: {MODEL_PATH}")

CAMERA_INDEX = 0
CONFIDENCE   = 0.7
ALPHA        = 0.35   # EMA smoothing

cap = cv2.VideoCapture(CAMERA_INDEX)
if not cap.isOpened():
    print("ERROR: Kamera tidak bisa dibuka!")
    sys.exit(1)

options = mp_vision.HandLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=mp_vision.RunningMode.VIDEO,
    num_hands=1,
    min_hand_detection_confidence=CONFIDENCE,
    min_tracking_confidence=CONFIDENCE,
)
landmarker = mp_vision.HandLandmarker.create_from_options(options)
controller  = KeyboardController()

print("\n=== DEBUG AKTIF - Tekan Ctrl+C untuk berhenti ===")
print("POINTING  -> gerakkan kursor")
print("PINCH     -> klik kiri (1x)\n")

state = {
    "ema_x": None,
    "ema_y": None,
    "was_pinching": False,
    "frame": 0,
}
start_time = time.time()

try:
    while True:
        ok, frame = cap.read()
        if not ok:
            continue

        frame    = cv2.flip(frame, 1)
        rgb      = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        ts_ms    = int((time.time() - start_time) * 1000)
        result   = landmarker.detect_for_video(mp_image, ts_ms)

        state["frame"] += 1
        if state["frame"] % 5 != 0:   # log tiap 5 frame
            continue

        if not result.hand_landmarks:
            if state["frame"] % 30 == 0:
                print("[no hand]")
            continue

        lm = [(p.x, p.y) for p in result.hand_landmarks[0]]

        pointing = is_pointing(lm)
        pinching = is_pinch(lm)
        fisting  = is_fist(lm)

        tip   = lm[8]
        thumb = lm[4]
        dist  = ((thumb[0]-tip[0])**2 + (thumb[1]-tip[1])**2) ** 0.5

        labels = []
        if fisting:  labels.append("FIST")
        if pointing: labels.append("POINT")
        if pinching: labels.append("PINCH")
        if not labels: labels.append("---")

        print(f"[{state['frame']:5d}] {'/'.join(labels):15s} "
              f"tip=({tip[0]:.3f},{tip[1]:.3f}) "
              f"thumb-dist={dist:.4f}")

        # Gerakkan kursor
        if pointing:
            raw_x = tip[0] * SCREEN_W
            raw_y = tip[1] * SCREEN_H
            if state["ema_x"] is None:
                state["ema_x"] = raw_x
                state["ema_y"] = raw_y
            else:
                state["ema_x"] = ALPHA * raw_x + (1 - ALPHA) * state["ema_x"]
                state["ema_y"] = ALPHA * raw_y + (1 - ALPHA) * state["ema_y"]
            mx = int(state["ema_x"])
            my = int(state["ema_y"])
            controller.move_mouse_to(mx, my)
            print(f"         → MOUSE MOVED to ({mx}, {my})")

        # Klik (edge-triggered)
        if pinching and not state["was_pinching"]:
            controller.mouse_left_click()
            print("         → LEFT CLICK!")
        state["was_pinching"] = pinching

except KeyboardInterrupt:
    print("\n=== Debug selesai ===")
finally:
    landmarker.close()
    cap.release()
