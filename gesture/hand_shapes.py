"""
Pure functions that turn a list of 21 MediaPipe hand landmarks into
simple boolean gesture facts (open palm / fist) and a center point.

Kept separate from GestureEngine so the FSM logic doesn't need to know
anything about landmark indices — it just asks "is this an open palm?".
"""

# MediaPipe hand landmark indices
FINGER_TIPS = [8, 12, 16, 20]   # index, middle, ring, pinky
FINGER_PIPS = [6, 10, 14, 18]   # corresponding lower joints


def is_open_palm(landmarks) -> bool:
    """True if at least 3 of 4 fingers are extended (tip above pip)."""
    if not landmarks or len(landmarks) < 21:
        return False

    extended = 0
    for tip, pip in zip(FINGER_TIPS, FINGER_PIPS):
        if landmarks[tip][1] < landmarks[pip][1]:
            extended += 1

    return extended >= 3


def is_fist(landmarks) -> bool:
    """True if at least 3 of 4 fingers are curled (tip below pip)."""
    if not landmarks or len(landmarks) < 21:
        return False

    curled = 0
    for tip, pip in zip(FINGER_TIPS, FINGER_PIPS):
        if landmarks[tip][1] > landmarks[pip][1]:
            curled += 1

    return curled >= 3


def palm_center(landmarks):
    """Rough palm center using the wrist (0) and middle-finger MCP (9)."""
    wrist = landmarks[0]
    middle_mcp = landmarks[9]
    return ((wrist[0] + middle_mcp[0]) / 2, (wrist[1] + middle_mcp[1]) / 2)
