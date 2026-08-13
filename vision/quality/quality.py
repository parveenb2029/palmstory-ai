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

    # sharpness: variance of a discrete Laplacian, measured on a FIXED small size
    # so the metric is resolution-independent and matches the client's check.
    # (Full-res palm skin has gentle gradients → artificially low variance; a clear
    # palm would otherwise be mis-flagged as blurry.)
    sg_img = img.convert("L")
    longest = max(sg_img.size)
    if longest > 256:
        r = 256 / longest
        sg_img = sg_img.resize((max(1, int(sg_img.size[0] * r)), max(1, int(sg_img.size[1] * r))))
    sg = np.asarray(sg_img, dtype=np.float32)
    sh, sw = sg.shape
    if sh >= 3 and sw >= 3:
        lap = (4.0 * sg[1:-1, 1:-1] - sg[:-2, 1:-1] - sg[2:, 1:-1] - sg[1:-1, :-2] - sg[1:-1, 2:])
        sharpness = _finite(lap.var()) if lap.size else 0.0
    else:
        sharpness = 0.0

    # framing: variance of the central region (near-uniform → empty frame)
    cy0, cy1, cx0, cx1 = int(h * .25), int(h * .75), int(w * .25), int(w * .75)
    region = gray[cy0:cy1, cx0:cx1]
    center_var = _finite(region.var()) if region.size else 0.0

    reasons = []
    blocking = False
    # darkness
    if brightness < 22:
        reasons.append("It's too dark to see your palm — move into much brighter light.")
        blocking = True
    elif brightness < DARK:
        reasons.append("It's a little dark — a bit more light would help.")
    # brightness / glare
    if brightness > 248:
        reasons.append("It's washed out by glare — reduce direct or harsh light.")
        blocking = True
    elif brightness > BRIGHT:
        reasons.append("It's a touch bright — soften the glare if you can.")
    # blur is always overridable (a webcam simply can't focus on a close palm)
    if sharpness < BLUR:
        reasons.append("Looks a little soft — hold steady, or snap it on your phone and upload.")
    # resolution
    if min(w, h) < MIN_RES:
        reasons.append("The photo is too small — use a larger, closer image.")
        blocking = True
    # empty frame (nothing palm-like in the middle)
    if center_var < EMPTY and sharpness >= BLUR:
        reasons.append("I can't see a palm in the frame — fill the outline with your open palm.")
        blocking = True

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
        "blocking": blocking,       # severe issues that can't be overridden
        "reasons": reasons,
    }
