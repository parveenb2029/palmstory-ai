"""Palm detection.

Preferred: MediaPipe Hands (landmark-based, robust across skin tones and
orientations) — used automatically when the `mediapipe` package is installed.
Fallback: a light NumPy heuristic when MediaPipe isn't available.

FAIRNESS NOTE: the heuristic fallback uses a simple skin-tone/coverage proxy,
which is known to be less reliable across the full range of skin tones and
lighting. It is therefore ADVISORY only — it never hard-blocks a reading on its
own. MediaPipe (landmark geometry, not colour) is the accurate path and should be
installed for production. See requirements-cv.txt.
"""
import numpy as np
from PIL import Image


def _mediapipe_available() -> bool:
    try:
        import mediapipe  # noqa: F401
        return True
    except Exception:
        return False


def detect(img: Image.Image) -> dict:
    if _mediapipe_available():
        try:
            return _detect_mediapipe(img)
        except Exception:
            pass  # fall through to heuristic on any runtime error
    return _detect_heuristic(img)


def _detect_mediapipe(img: Image.Image) -> dict:
    import mediapipe as mp

    hands = mp.solutions.hands.Hands(
        static_image_mode=True, max_num_hands=1, min_detection_confidence=0.4
    )
    try:
        res = hands.process(np.asarray(img.convert("RGB")))
    finally:
        hands.close()

    if res.multi_hand_landmarks:
        lm = res.multi_hand_landmarks[0]
        side = None
        if res.multi_handedness:
            side = res.multi_handedness[0].classification[0].label.lower()
        return {
            "detected": True, "source": "mediapipe", "hand_side": side,
            "landmarks": len(lm.landmark), "orientation_ok": True,
            "note": "Hand landmarks detected.",
        }
    return {
        "detected": False, "source": "mediapipe", "hand_side": None,
        "landmarks": 0, "orientation_ok": None,
        "note": "No hand detected — retake with your open palm in frame.",
    }


def _detect_heuristic(img: Image.Image) -> dict:
    import math
    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    h, w, _ = arr.shape
    c = arr[int(h * .2):int(h * .8), int(w * .2):int(w * .8)]
    if c.size == 0:
        c = arr  # tiny image — use the whole thing
    if c.size == 0:
        ratio = 0.0
    else:
        r, g, b = c[..., 0], c[..., 1], c[..., 2]
        mx, mn = c.max(-1), c.min(-1)
        skin = ((r > 60) & (g > 30) & (b > 15) & ((mx - mn) > 12) & (r >= g) & (r >= b))
        ratio = float(skin.mean())
        if not math.isfinite(ratio):
            ratio = 0.0
    detected = ratio > 0.20
    return {
        "detected": detected, "source": "heuristic", "hand_side": None,
        "landmarks": 0, "orientation_ok": None, "skin_ratio": round(ratio, 3),
        "note": ("A palm-like region is likely present (heuristic — install MediaPipe "
                 "for accurate detection)." if detected
                 else "Couldn't confirm a palm (heuristic only) — install MediaPipe for "
                      "accurate detection, or retake with your open palm filling the frame."),
    }
