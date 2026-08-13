"""Authoritative image-quality assessment (server-side).

Mirrors the client-side pre-check but is the source of truth. Thresholds are
heuristic and documented; they gate whether an image is worth sending to a vision
model. Detection confidence (elsewhere) is kept separate from interpretation.
"""
import math

import numpy as np
from PIL import Image

DARK, BRIGHT, BLUR, MIN_RES, EMPTY = 55.0, 220.0, 60.0, 320, 40.0


def _finite(x, default=0.0):
    x = float(x)
    return x if math.isfinite(x) else default


def assess(img: Image.Image) -> dict:
    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    h, w, _ = arr.shape
    gray = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]

    brightness = _finite(gray.mean()) if gray.size else 0.0

    # sharpness: variance of a discrete Laplacian (needs at least a 3x3 interior)
    if h >= 3 and w >= 3:
        lap = (4.0 * gray[1:-1, 1:-1]
               - gray[:-2, 1:-1] - gray[2:, 1:-1]
               - gray[1:-1, :-2] - gray[1:-1, 2:])
        sharpness = _finite(lap.var()) if lap.size else 0.0
    else:
        sharpness = 0.0

    # framing: variance of the central region (near-uniform → empty frame)
    cy0, cy1, cx0, cx1 = int(h * .25), int(h * .75), int(w * .25), int(w * .75)
    region = gray[cy0:cy1, cx0:cx1]
    center_var = _finite(region.var()) if region.size else 0.0

    reasons = []
    if brightness < DARK:
        reasons.append("It's too dark — move into better light.")
    if brightness > BRIGHT:
        reasons.append("It's too bright — reduce glare or harsh light.")
    if sharpness < BLUR:
        reasons.append("The image is blurry — hold steady and try again.")
    if min(w, h) < MIN_RES:
        reasons.append("The image is low-resolution — use a larger, closer photo.")
    if center_var < EMPTY and sharpness >= BLUR:
        reasons.append("No clear palm in frame — fill the outline with your open palm.")

    usable = len(reasons) == 0
    b_score = 1 - min(1, abs(brightness - 140) / 140)
    s_score = min(1, sharpness / 220)
    score = round(_finite(((1 if usable else 0.4) * 0.4 + b_score * 0.3 + s_score * 0.3) * 100), 1)

    return {
        "brightness": round(brightness, 1),
        "sharpness": round(sharpness, 1),
        "resolution": f"{w}x{h}",
        "coverage": round(_finite(min(1.0, center_var / 200.0)), 3),
        "score": score,
        "usable": usable,
        "reasons": reasons,
    }
