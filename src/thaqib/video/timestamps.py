"""
Timestamp overlay utility — shared by visualizer (live display) and pipeline (recordings).

Kept in a separate module to avoid the circular import:
  pipeline.py  →  timestamps.py  (no circular)
  visualizer.py →  timestamps.py  (no circular)
"""

import datetime
import cv2
import numpy as np


def draw_timestamp_overlay(frame: np.ndarray, ts: float | None = None, archive_offset_sec: float | None = None) -> None:
    """Burn a timestamp badge onto the top-right corner of a frame (in-place).

    Args:
        frame: BGR frame to annotate (modified in-place).
        ts:    Unix timestamp. If None, uses current wall-clock time.
        archive_offset_sec: Optional archive offset in seconds to display as a second line.
    """
    dt = (datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).astimezone()
          if ts else datetime.datetime.now().astimezone())
    
    texts = [dt.strftime("%Y-%m-%d  %H:%M:%S")]
    
    if archive_offset_sec is not None:
        m, s = divmod(int(archive_offset_sec), 60)
        h, m = divmod(m, 60)
        texts.append(f"Offset: {h:02d}:{m:02d}:{s:02d}")

    h, w = frame.shape[:2]
    sc = max(0.5, h / 720.0)
    fs = 0.55 * sc
    th = max(1, int(round(sc)))
    pad = int(8 * sc)
    line_spacing = int(10 * sc)

    # Calculate bounding box for all text lines
    max_tw = 0
    total_th = 0
    lines_meta = []
    
    for text in texts:
        (tw, t_h), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, fs, th)
        max_tw = max(max_tw, tw)
        lines_meta.append({'text': text, 'tw': tw, 'th': t_h, 'baseline': baseline})
        total_th += t_h + baseline + line_spacing
        
    total_th -= line_spacing # remove trailing spacing

    x0 = w - max_tw - pad * 2
    y0 = pad
    x1 = w
    y1 = y0 + total_th + pad * 2

    # Semi-transparent dark background
    roi = frame[y0:y1, x0:x1]
    if roi.size > 0:
        overlay = roi.copy()
        cv2.rectangle(overlay, (0, 0), (x1 - x0, y1 - y0), (10, 10, 10), -1)
        cv2.addWeighted(overlay, 0.70, roi, 0.30, 0, roi)

    # Draw texts
    current_y = y0 + pad
    for meta in lines_meta:
        # Right align
        cx = x1 - pad - meta['tw']
        current_y += meta['th']
        cv2.putText(
            frame, meta['text'],
            (cx, current_y),
            cv2.FONT_HERSHEY_SIMPLEX, fs, (220, 220, 220), th, cv2.LINE_AA,
        )
        current_y += meta['baseline'] + line_spacing
