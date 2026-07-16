"""
Pure functions that turn a list of 21 MediaPipe hand landmarks into
simple boolean gesture facts (open palm / fist) and a center point.

Kept separate from GestureEngine so the FSM logic doesn't need to know
anything about landmark indices — it just asks "is this an open palm?".

Landmark layout (MediaPipe Hand):
    0  = wrist
    1-4  = thumb  (MCP, IP, tip = 4)
    5-8  = index  (MCP, PIP, DIP, tip = 8)
    9-12 = middle (MCP, PIP, DIP, tip = 12)
    13-16= ring   (MCP, PIP, DIP, tip = 16)
    17-20= pinky  (MCP, PIP, DIP, tip = 20)

Coordinate system: x in [0,1] left→right, y in [0,1] top→bottom.
We use distance from the wrist (0) to determine if a finger is extended.
If dist(tip, wrist) > dist(pip, wrist), the finger is extended.
"""

# MediaPipe hand landmark indices
FINGER_TIPS = [8, 12, 16, 20]   # index, middle, ring, pinky
FINGER_PIPS = [6, 10, 14, 18]   # corresponding PIP joints


def _dist_sq(p1, p2):
    return (p1[0] - p2[0])**2 + (p1[1] - p2[1])**2


def is_open_palm(landmarks) -> bool:
    """True if at least 3 of 4 fingers are extended."""
    if not landmarks or len(landmarks) < 21:
        return False

    # Check orientation: wrist (0) must be below middle finger MCP (9) on screen
    if landmarks[0][1] < landmarks[9][1]:
        return False

    wrist = landmarks[0]
    extended = 0
    for tip, pip in zip(FINGER_TIPS, FINGER_PIPS):
        if _dist_sq(landmarks[tip], wrist) > _dist_sq(landmarks[pip], wrist):
            extended += 1

    return extended >= 3


def is_open_palm_down(landmarks) -> bool:
    """True if hand is pointing downwards and at least 3 of 4 fingers are extended."""
    if not landmarks or len(landmarks) < 21:
        return False

    # Check orientation: wrist (0) must be above middle finger MCP (9) on screen
    if landmarks[0][1] >= landmarks[9][1]:
        return False

    wrist = landmarks[0]
    extended = 0
    for tip, pip in zip(FINGER_TIPS, FINGER_PIPS):
        if _dist_sq(landmarks[tip], wrist) > _dist_sq(landmarks[pip], wrist):
            extended += 1

    return extended >= 3


def is_fist(landmarks) -> bool:
    """True if at least 3 of 4 fingers are curled."""
    if not landmarks or len(landmarks) < 21:
        return False

    wrist = landmarks[0]
    curled = 0
    for tip, pip in zip(FINGER_TIPS, FINGER_PIPS):
        if _dist_sq(landmarks[tip], wrist) < _dist_sq(landmarks[pip], wrist):
            curled += 1

    return curled >= 3


def palm_center(landmarks):
    """Rough palm center using the wrist (0) and middle-finger MCP (9)."""
    wrist = landmarks[0]
    middle_mcp = landmarks[9]
    return ((wrist[0] + middle_mcp[0]) / 2, (wrist[1] + middle_mcp[1]) / 2)


def is_pointing(landmarks) -> bool:
    """True when the index finger is clearly extended and the other 3 fingers
    are mostly curled. Uses distance from wrist, making it rotation invariant.
    """
    if not landmarks or len(landmarks) < 21:
        return False

    wrist = landmarks[0]

    # Index tip must be further from wrist than both its PIP and MCP
    idx_tip_d = _dist_sq(landmarks[8], wrist)
    if idx_tip_d <= _dist_sq(landmarks[6], wrist):
        return False
    if idx_tip_d <= _dist_sq(landmarks[5], wrist):
        return False

    # At least 2 of middle / ring / pinky must be curled
    curled = 0
    for tip, pip in zip([12, 16, 20], [10, 14, 18]):
        if _dist_sq(landmarks[tip], wrist) < _dist_sq(landmarks[pip], wrist):
            curled += 1

    return curled >= 2


def is_pinch(landmarks, threshold: float = 0.08) -> bool:
    """True if thumb tip (4) and index tip (8) are close together."""
    if not landmarks or len(landmarks) < 21:
        return False

    thumb_tip = landmarks[4]
    index_tip = landmarks[8]

    # Using actual distance calculation without squaring for the threshold comparison
    dist = _dist_sq(thumb_tip, index_tip) ** 0.5
    return dist < threshold
