"""
Timestamp overlay utility — shared by visualizer (live display) and pipeline (recordings).

Kept in a separate module to avoid the circular import:
  pipeline.py  →  timestamps.py  (no circular)
  visualizer.py →  timestamps.py  (no circular)
"""

import datetime
import cv2
import numpy as np


def draw_timestamp_overlay(frame: np.ndarray, ts: float | None = None) -> None:
    """Burn a timestamp badge onto the top-right corner of a frame (in-place).

    Args:
        frame: BGR frame to annotate (modified in-place).
        ts:    Unix timestamp. If None, uses current wall-clock time.
    """
    dt = datetime.datetime.fromtimestamp(ts) if ts else datetime.datetime.now()
    text = dt.strftime("%Y-%m-%d  %H:%M:%S")

    h, w = frame.shape[:2]
    sc = max(0.5, h / 720.0)
    fs = 0.55 * sc
    th = max(1, int(round(sc)))
    pad = int(8 * sc)

    (tw, t_h), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, fs, th)
    x0 = w - tw - pad * 2
    y0 = pad
    x1 = w
    y1 = t_h + baseline + pad * 2

    # Semi-transparent dark background
    roi = frame[y0:y1, x0:x1]
    if roi.size > 0:
        overlay = roi.copy()
        cv2.rectangle(overlay, (0, 0), (x1 - x0, y1 - y0), (10, 10, 10), -1)
        cv2.addWeighted(overlay, 0.70, roi, 0.30, 0, roi)

    # White text
    cv2.putText(
        frame, text,
        (x0 + pad, y0 + t_h + pad),
        cv2.FONT_HERSHEY_SIMPLEX, fs, (220, 220, 220), th, cv2.LINE_AA,
    )
