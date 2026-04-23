"""
Face mesh extraction using MediaPipe Face Landmarker.
Uses thread-local VIDEO mode for temporal smoothing.
"""

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
import time

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core import base_options as mp_base_options

logger = logging.getLogger(__name__)

_MODEL_PATH = Path(__file__).parent.parent.parent.parent / "models" / "face_landmarker.task"


@dataclass
class FaceMeshResult:
    """
    Extracted face mesh for one student.

    Attributes:
        landmarks_2d: 478 pixel coordinates (x, y) in the original full frame.
        landmarks_3d: 478 metric coordinates (x, y, z); x/y in frame pixels,
                      z is the MediaPipe depth value (negative = closer to camera).
        bbox: The student bounding box used for this result (x1, y1, x2, y2).
        head_matrix: 4x4 facial transformation matrix from MediaPipe (rotation + translation).
                     The Z-column (matrix[:3, 2]) gives the head forward direction vector.
    """

    landmarks_2d: list[tuple[int, int]]
    landmarks_3d: list[tuple[float, float, float]]
    bbox: tuple[int, int, int, int]
    head_matrix: np.ndarray | None = None

    @property
    def count(self) -> int:
        """Number of landmarks."""
        return len(self.landmarks_2d)


class FaceMeshExtractor:
    """
    MediaPipe FaceLandmarker wrapper for full face mesh extraction.

    Loads face_landmarker.task and extracts 2D + 3D landmarks for each
    student crop. Coordinates are remapped back to full-frame pixel space so
    that downstream consumers do not need to know about the crop.

    Uses VIDEO running mode for temporal smoothing — reduces jitter between
    consecutive frames for the same student. Each ThreadPoolExecutor worker
    thread gets its own landmarker instance via threading.local().

    Example:
        >>> extractor = FaceMeshExtractor()
        >>> result = extractor.extract(frame, bbox=(x1, y1, x2, y2), timestamp_ms=0)
        >>> if result:
        ...     print(result.count, "landmarks")
        ...     print(result.landmarks_2d[0])  # (px, py) in full frame
        ...     print(result.landmarks_3d[0])  # (px, py, z_metric)
    """

    def __init__(self, model_path: Path | None = None) -> None:
        """
        Load the FaceLandmarker model.

        Args:
            model_path: Override path to face_landmarker.task.
        """
        self._model_path = model_path or _MODEL_PATH

        if not self._model_path.exists():
            raise FileNotFoundError(
                f"Face landmarker model not found: {self._model_path}\n"
                "Download from: https://storage.googleapis.com/mediapipe-models/"
                "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
            )

        logger.info(f"Loading FaceMeshExtractor model: {self._model_path}")

        # Thread-local storage: each worker thread gets its own FaceLandmarker.
        # VIDEO mode is not thread-safe — concurrent calls on the same instance
        # will crash. Lazy initialization happens on first extract() call per thread.
        self._thread_local = threading.local()

        # Global monotonic timestamp counter (shared, atomic increment via lock).
        # VIDEO mode requires strictly increasing timestamps per landmarker.
        # Since each thread has its own landmarker, we track per-thread counters.
        self._ts_lock = threading.Lock()

        self._mesh_cache: dict[int, tuple[float, FaceMeshResult]] = {}
        
        # Track all created landmarkers for cleanup
        self._landmarkers: list[vision.FaceLandmarker] = []
        self._landmarkers_lock = threading.Lock()
        
        logger.info("FaceMeshExtractor initialized (VIDEO mode, per-thread instances).")

    def _get_landmarker(self) -> vision.FaceLandmarker:
        """Get or create a thread-local FaceLandmarker instance."""
        if not hasattr(self._thread_local, 'landmarker'):
            opts = vision.FaceLandmarkerOptions(
                base_options=mp_base_options.BaseOptions(
                    model_asset_path=str(self._model_path)
                ),
                running_mode=vision.RunningMode.VIDEO,
                num_faces=1,
                min_face_detection_confidence=0.50,   # Lowered from 0.80 — distant faces need slack
                min_face_presence_confidence=0.50,     # Lowered from 0.80
                min_tracking_confidence=0.50,           # Lowered from 0.80
                output_face_blendshapes=False,
                output_facial_transformation_matrixes=True,
            )
            landmarker = vision.FaceLandmarker.create_from_options(opts)
            self._thread_local.landmarker = landmarker
            self._thread_local.timestamp_ms = 0  # Per-thread monotonic counter
            
            # Track for cleanup
            with self._landmarkers_lock:
                self._landmarkers.append(landmarker)
            
            thread_name = threading.current_thread().name
            logger.info(f"Created per-thread FaceLandmarker for thread '{thread_name}'")
        
        return self._thread_local.landmarker

    def _next_timestamp_ms(self) -> int:
        """
        Get the next monotonic timestamp (ms) for the current thread's landmarker.
        
        VIDEO mode requires strictly increasing timestamps. We use a per-thread
        counter that increments by 33ms (~30fps) on each call.
        """
        self._thread_local.timestamp_ms += 33  # ~30fps cadence
        return self._thread_local.timestamp_ms

    # ------------------------------------------------------------------

    def extract(
        self,
        frame: np.ndarray,
        bbox: tuple[int, int, int, int],
        track_id: int | None = None,
    ) -> FaceMeshResult | None:
        """
        Extract 2D + 3D face mesh from a student's bounding box region.

        Landmark coordinates are returned in full-frame pixel space so that
        callers never need to account for the crop offset.

        Args:
            frame: Full BGR video frame (H×W×3, from OpenCV).
            bbox:  Bounding box (x1, y1, x2, y2) of the student in frame.
            track_id: Optional track ID for caching.

        Returns:
            FaceMeshResult if a face was detected, None otherwise.
        """
        x1, y1, x2, y2 = bbox

        # Crop only the HEAD region (upper 40% of person bbox).
        # MediaPipe needs the face, not the full body — this reduces crop
        # area by ~60%, improving both speed and accuracy.
        body_height = y2 - y1
        y2 = y1 + int(body_height * 0.40)

        # Calculate dynamic 15% padding around the head crop
        width = x2 - x1
        height = y2 - y1
        pad_w = int(width * 0.15)
        pad_h = int(height * 0.15)

        # Expand coordinates
        x1 -= pad_w
        y1 -= pad_h
        x2 += pad_w
        y2 += pad_h

        # Clamp to frame bounds
        fh, fw = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(fw, x2), min(fh, y2)

        if x2 <= x1 or y2 <= y1:
            return self._get_cached(track_id, reason="small_crop")

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return self._get_cached(track_id, reason="small_crop")

        crop_h, crop_w = crop.shape[:2]

        if crop_w < 40 or crop_h < 40:
            # Face too small to extrapolate accurate gaze, use cache
            return self._get_cached(track_id, reason="small_crop")

        # BGR → RGB for MediaPipe
        rgb_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_crop)

        try:
            landmarker = self._get_landmarker()
            ts_ms = self._next_timestamp_ms()
            detection = landmarker.detect_for_video(mp_image, ts_ms)
        except Exception as exc:
            logger.debug(f"FaceLandmarker inference error: {exc}")
            return None  # Detection failure — don't return stale cache

        if not detection.face_landmarks:
            return None  # Detection failure — don't mask real gaze changes

        raw = detection.face_landmarks[0]  # First (and only) face

        # Convert landmarks to a (478, 3) numpy array directly
        lm_array = np.array([[lm.x, lm.y, lm.z] for lm in raw], dtype=float)

        # Vectorized math for 2D coords
        # Normalized [0,1] -> crop pixels -> add anchor offset
        px_py = lm_array[:, :2] * np.array([crop_w, crop_h]) + np.array([x1, y1])
        px_py = px_py.astype(int)

        landmarks_2d = [tuple(pt) for pt in px_py]
        landmarks_3d = [tuple(pt) for pt in lm_array]

        # Extract head transformation matrix if available
        if detection.facial_transformation_matrixes:
            head_matrix = np.array(
                detection.facial_transformation_matrixes[0].data
            ).reshape(4, 4)
        else:
            head_matrix = None

        result = FaceMeshResult(
            landmarks_2d=landmarks_2d,
            landmarks_3d=landmarks_3d,
            bbox=(x1, y1, x2, y2),
            head_matrix=head_matrix,
        )

        if track_id is not None:
            self._mesh_cache[track_id] = (time.time(), result)

        return result

    def _get_cached(self, track_id: int | None, reason: str = "unknown") -> FaceMeshResult | None:
        """Return cached mesh only for small_crop scenarios, not detection failures."""
        if track_id is not None and track_id in self._mesh_cache:
            cache_time, cached_mesh = self._mesh_cache[track_id]
            # Only use cache for small crops — detection failures should return None
            # to avoid masking real gaze changes (false negatives on cheating)
            max_age = 0.3 if reason == "small_crop" else 0.0
            if time.time() - cache_time <= max_age:
                return cached_mesh
        return None

    def remove_cache(self, track_ids: list[int]) -> None:
        """Remove cached face meshes for expired track IDs to prevent memory leaks."""
        for tid in track_ids:
            self._mesh_cache.pop(tid, None)

    def close(self) -> None:
        """Release all landmarker resources (all threads)."""
        with self._landmarkers_lock:
            for lm in self._landmarkers:
                try:
                    lm.close()
                except Exception:
                    pass
            self._landmarkers.clear()
        logger.info("FaceMeshExtractor closed (all thread-local instances).")
