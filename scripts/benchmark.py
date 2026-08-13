"""Micro-benchmark for the reading pipeline (mock providers).

    DEV_MOCK_AI=true python scripts/benchmark.py [N]

Times the full observation → interpretation → reading → storyboard → comic chain.
"""
import io
import os
import sys
import time

import numpy as np
from PIL import Image

os.environ.setdefault("DEV_MOCK_AI", "true")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.services.pipeline import generate_reading  # noqa: E402
from vision.preprocessing.preprocess import to_jpeg_bytes  # noqa: E402


def _img():
    rng = np.random.default_rng(0)
    arr = rng.integers(90, 190, size=(480, 640, 3), dtype=np.uint8)
    return Image.fromarray(arr, "RGB")


def main(n=50):
    jpeg = to_jpeg_bytes(_img())
    quality = {"brightness": 140, "sharpness": 200, "resolution": "640x480",
               "coverage": 0.5, "score": 90, "usable": True, "reasons": []}
    detection = {"detected": True, "source": "heuristic", "note": ""}
    # warm up
    generate_reading(jpeg, "right", quality, detection, [640, 480])
    t0 = time.perf_counter()
    for _ in range(n):
        generate_reading(jpeg, "right", quality, detection, [640, 480])
    dt = time.perf_counter() - t0
    print(f"pipeline: {n} runs in {dt:.3f}s → {dt/n*1000:.1f} ms/reading, {n/dt:.0f} readings/s")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 50)
