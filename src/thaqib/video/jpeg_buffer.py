"""
jpeg_buffer.py — Memory-efficient frame storage for rolling buffers.

Replaces raw numpy ndarray frames (2-25 MB each) with JPEG-compressed bytes
(~80-150 KB each at quality 85) in the long-lived deque buffers.  Decode
happens only at alert-composition time (background thread), so the real-time
pipeline is unaffected except for a brief encode step (~2-5 ms per frame).

Memory savings:
  - 720p  (1280×720 ×3): 2.76 MB raw  →  ~100 KB JPEG  (~28× reduction)
  - 1080p (1920×1080×3): 6.22 MB raw  →  ~200 KB JPEG  (~31× reduction)
  - 4K    (3840×2160×3): 24.9 MB raw  →  ~600 KB JPEG  (~41× reduction)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# JPEG quality used when encoding frames into buffers.
# 85 gives excellent visual quality with ~28-41× size reduction vs raw.
# Annotations (text, boxes) drawn AFTER decode are unaffected by the
# compression artefacts because they are added to the decoded array.
JPEG_QUALITY: int = 85

_ENCODE_PARAMS = [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]


def encode_frame(frame: np.ndarray) -> bytes:
    """Encode a BGR numpy frame to JPEG bytes.

    Args:
        frame: BGR uint8 ndarray of any resolution.

    Returns:
        JPEG-encoded bytes, or the raw frame bytes as a fallback on error.
    """
    ok, buf = cv2.imencode(".jpg", frame, _ENCODE_PARAMS)
    if not ok:
        # Fallback: store raw bytes (still correct, just large).
        logger.warning("JPEG encode failed; falling back to raw frame bytes.")
        return frame.tobytes()
    return buf.tobytes()


def decode_frame(data: bytes, original_shape: tuple[int, int, int] | None = None) -> np.ndarray:
    """Decode JPEG bytes back to a BGR numpy ndarray.

    Args:
        data: JPEG bytes (or raw frame bytes from the encode_frame fallback).
        original_shape: (H, W, C) of the original frame.  Only needed if the
                        fallback raw-bytes path was taken; ignored for normal JPEG.

    Returns:
        BGR uint8 ndarray.
    """
    arr = np.frombuffer(data, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        # Data was stored as raw bytes (encode fallback path).
        if original_shape is not None:
            return np.frombuffer(data, dtype=np.uint8).reshape(original_shape)
        logger.error("decode_frame: imdecode returned None and no shape given.")
        return np.zeros((1, 1, 3), dtype=np.uint8)
    return frame


# ---------------------------------------------------------------------------
# JPEGFrame — drop-in replacement for AlertFrame that stores JPEG bytes.
# ---------------------------------------------------------------------------

@dataclass
class JPEGFrame:
    """A single frame stored as JPEG bytes for memory-efficient buffering.

    Mirrors the fields used by AlertFrame so the writer tasks can handle
    both types via isinstance checks without needing separate code paths.
    """

    # JPEG-encoded frame bytes (see encode_frame / decode_frame above).
    data: bytes

    # Metadata — mirrors AlertFrame fields so writers can use either type.
    timestamp: float = 0.0
    frame_index: int = 0
    track_id: int | None = None
    phone_bboxes: list = field(default_factory=list)
    student_bbox: tuple[int, int, int, int] | None = None
    student_center: tuple[int, int] | None = None

    def decode(self) -> np.ndarray:
        """Decode the stored JPEG bytes to a BGR ndarray."""
        return decode_frame(self.data)

    @property
    def frame(self) -> np.ndarray:
        """Compatibility shim: decode on access (for code expecting .frame).

        Note: Each call decodes fresh — cache the result if you need it
        multiple times in the same scope.
        """
        return self.decode()
