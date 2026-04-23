"""
Multiprocessing worker for face mesh extraction using shared memory.
Uses IMAGE mode for process-safe independent frame inference.
"""

from multiprocessing import shared_memory
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core import base_options as mp_base_options

_MODEL_PATH = Path(__file__).parent.parent.parent.parent / "models" / "face_landmarker.task"
_landmarker = None  # per-process singleton


def init_worker():
    """Initialize a per-process FaceLandmarker singleton.

    Called once per child process by Pool(initializer=...).
    IMAGE mode is used because each inference is independent (no temporal
    smoothing across frames) — this is the trade-off for true parallelism.
    """
    global _landmarker
    opts = vision.FaceLandmarkerOptions(
        base_options=mp_base_options.BaseOptions(
            model_asset_path=str(_MODEL_PATH)
        ),
        running_mode=vision.RunningMode.IMAGE,  # IMAGE mode IS process-safe
        num_faces=1,
        min_face_detection_confidence=0.50,
        min_face_presence_confidence=0.50,
        min_tracking_confidence=0.50,
        output_face_blendshapes=False,
        output_facial_transformation_matrixes=True,
    )
    _landmarker = vision.FaceLandmarker.create_from_options(opts)


def extract_in_worker(args):
    """Run face mesh inference in a child process.

    Args:
        args: tuple of (shm_name, shape, dtype_str, bbox, track_id, fm_scale)
            - shm_name: name of the SharedMemory block containing the frame
            - shape: tuple (H, W, C) of the frame
            - dtype_str: numpy dtype string (e.g. 'uint8')
            - bbox: (x1, y1, x2, y2) in ORIGINAL resolution
            - track_id: student track ID
            - fm_scale: scale factor applied to the frame (e.g. 0.5 for 4K→1080p)

    Returns:
        (track_id, result_dict | None) where result_dict has keys:
            lm2d, lm3d, bbox, hmat
        All values are plain Python types (lists/tuples) for pickle safety.
    """
    shm_name, shape, dtype_str, bbox, track_id, fm_scale = args
    shm = shared_memory.SharedMemory(name=shm_name)
    try:
        frame = np.ndarray(shape, dtype=np.dtype(dtype_str), buffer=shm.buf)

        # Scale bbox to match the (potentially downscaled) frame
        x1, y1, x2, y2 = [int(v * fm_scale) for v in bbox]

        # Crop only the HEAD region (upper 40% of person bbox)
        body_h = y2 - y1
        y2 = y1 + int(body_h * 0.40)

        # Dynamic 15% padding around the head crop
        pad_w = int((x2 - x1) * 0.15)
        pad_h = int((y2 - y1) * 0.15)
        x1 = max(0, x1 - pad_w)
        y1 = max(0, y1 - pad_h)
        x2 = min(shape[1], x2 + pad_w)
        y2 = min(shape[0], y2 + pad_h)

        if x2 <= x1 or y2 <= y1:
            return track_id, None

        crop = frame[y1:y2, x1:x2]
        if crop.shape[0] < 40 or crop.shape[1] < 40:
            return track_id, None

        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        det = _landmarker.detect(mp_img)  # IMAGE mode — no timestamp needed

        if not det.face_landmarks:
            return track_id, None

        raw = det.face_landmarks[0]
        ch, cw = crop.shape[:2]

        # Convert landmarks to numpy for vectorized math
        lm = np.array([[l.x, l.y, l.z] for l in raw], dtype=float)

        # Normalized [0,1] → crop pixels → add anchor offset
        px_py = (lm[:, :2] * [cw, ch] + [x1, y1]).astype(int)

        # Scale back to original resolution
        inv = 1.0 / fm_scale
        lm2d = [(int(x * inv), int(y * inv)) for x, y in px_py]
        lm3d = [tuple(row) for row in lm]

        # Head transformation matrix (4x4)
        hmat = None
        if det.facial_transformation_matrixes:
            hmat = np.array(
                det.facial_transformation_matrixes[0].data
            ).reshape(4, 4).tolist()  # tolist() for pickle safety

        # Return the crop bbox in ORIGINAL resolution
        bbox_orig = (int(x1 * inv), int(y1 * inv), int(x2 * inv), int(y2 * inv))

        return track_id, {
            "lm2d": lm2d,
            "lm3d": lm3d,
            "bbox": bbox_orig,
            "hmat": hmat,
        }
    except Exception:
        return track_id, None
    finally:
        shm.close()
