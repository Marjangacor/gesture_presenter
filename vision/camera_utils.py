"""
Quick camera enumeration for the UI dropdown. This briefly opens and
closes each camera index — it's only run once at UI build time, not
during active detection, so the small delay is acceptable.
"""

import cv2


def list_available_cameras(max_index: int = 5) -> list[int]:
    available = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available.append(i)
            cap.release()
    return available
