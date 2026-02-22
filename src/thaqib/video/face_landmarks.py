"""
Face landmarks extraction using MediaPipe Face Landmarker.

Loads the face_landmarker.task model once and provides per-student
landmark extraction from cropped bounding box regions.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core import base_options as mp_base_options

logger = logging.getLogger(__name__)

# Absolute path to the model file
_MODEL_PATH = Path(__file__).parent.parent.parent.parent / "models" / "face_landmarker.task"


@dataclass
class FaceLandmarksResult:
    """Extracted face landmarks for one student."""

    # All 478 MediaPipe face mesh landmarks (x, y, z all in [0,1] relative to crop)
    landmarks: list[tuple[float, float, float]]

    @property
    def count(self) -> int:
        """Number of landmarks returned."""
        return len(self.landmarks)


class FaceLandmarksExtractor:
    """
    MediaPipe Face Landmarker wrapper.

    Loads face_landmarker.task once and provides per-frame
    landmark extraction from individual student bounding box crops.

    Example:
        >>> extractor = FaceLandmarksExtractor()
        >>> result = extractor.extract(frame, bbox=(x1, y1, x2, y2))
        >>> if result:
        ...     print(f"Got {result.count} landmarks")
    """

    def __init__(self, model_path: Path | None = None) -> None:
        """
        Initialize and load the face landmarker model.

        Args:
            model_path: Path to face_landmarker.task. Defaults to models/ directory.
        """
        self._model_path = model_path or _MODEL_PATH

        if not self._model_path.exists():
            raise FileNotFoundError(
                f"Face landmarker model not found: {self._model_path}\n"
                "Download it from: https://storage.googleapis.com/mediapipe-models/"
                "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
            )

        logger.info(f"Loading FaceLandmarker model from: {self._model_path}")

        base_opts = mp_base_options.BaseOptions(
            model_asset_path=str(self._model_path)
        )
        options = vision.FaceLandmarkerOptions(
            base_options=base_opts,
            running_mode=vision.RunningMode.IMAGE,
            num_faces=1,              # One face per student crop
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )
        self._landmarker = vision.FaceLandmarker.create_from_options(options)

        logger.info("FaceLandmarker model loaded successfully")

    def extract(
        self,
        frame: np.ndarray,
        bbox: tuple[int, int, int, int],
    ) -> FaceLandmarksResult | None:
        """
        Extract face landmarks from a student's bounding box region.

        Args:
            frame: Full BGR video frame (from OpenCV).
            bbox: Bounding box (x1, y1, x2, y2) of the student.

        Returns:
            FaceLandmarksResult if a face was detected, None otherwise.
        """
        x1, y1, x2, y2 = bbox

        # Clamp to frame bounds
        h, w = frame.shape[:2]
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(w, x2)
        y2 = min(h, y2)

        # Skip degenerate crops
        if x2 <= x1 or y2 <= y1:
            return None

        # Crop face region and convert BGR → RGB
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return None

        rgb_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)

        # Wrap in MediaPipe Image
        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb_crop,
        )

        # Run inference
        try:
            detection = self._landmarker.detect(mp_image)
        except Exception as exc:
            logger.debug(f"FaceLandmarker inference failed: {exc}")
            return None

        if not detection.face_landmarks:
            return None

        # Take the first (and only) detected face
        raw_landmarks = detection.face_landmarks[0]

        landmarks: list[tuple[float, float, float]] = [
            (lm.x, lm.y, lm.z) for lm in raw_landmarks
        ]

        return FaceLandmarksResult(landmarks=landmarks)

    def close(self) -> None:
        """Release the landmarker resources."""
        self._landmarker.close()
        logger.info("FaceLandmarker closed")
