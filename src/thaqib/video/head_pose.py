"""
Head pose estimation using MediaPipe FaceLandmarker (Tasks API).

Estimates yaw, pitch, and roll angles from face landmarks.
Supports MediaPipe 0.10.30+ with the new Tasks API.
"""

import logging
import math
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from thaqib.video.tracker import TrackedObject

logger = logging.getLogger(__name__)

# Model download URL
FACE_LANDMARKER_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)


@dataclass
class HeadPose:
    """Head pose angles in degrees."""

    yaw: float  # Horizontal rotation (left/right)
    pitch: float  # Vertical rotation (up/down)
    roll: float  # In-plane rotation (tilt)
    confidence: float = 1.0

    @property
    def is_looking_left(self) -> bool:
        """Check if head is turned left (yaw > 15 degrees)."""
        return self.yaw > 15

    @property
    def is_looking_right(self) -> bool:
        """Check if head is turned right (yaw < -15 degrees)."""
        return self.yaw < -15

    @property
    def is_looking_down(self) -> bool:
        """Check if head is looking down (pitch < -10 degrees)."""
        return self.pitch < -10

    @property
    def is_looking_up(self) -> bool:
        """Check if head is looking up (pitch > 10 degrees)."""
        return self.pitch > 10


@dataclass
class HeadPoseResult:
    """Head pose estimation result for a single tracked object."""

    track_id: int
    pose: HeadPose | None  # None if face not detected
    face_bbox: tuple[int, int, int, int] | None = None  # Face bounding box if detected

    @property
    def has_pose(self) -> bool:
        """Check if pose was successfully estimated."""
        return self.pose is not None


class HeadPoseEstimator:
    """
    MediaPipe-based head pose estimator using FaceLandmarker (Tasks API).

    Uses face mesh landmarks to estimate 3D head orientation (yaw, pitch, roll).
    Compatible with MediaPipe 0.10.30+.

    Example:
        >>> estimator = HeadPoseEstimator()
        >>> # For each tracked student:
        >>> result = estimator.estimate(frame, tracked_object)
        >>> if result.has_pose:
        ...     print(f"Yaw: {result.pose.yaw:.1f}°")
    """

    # Key landmark indices for pose estimation
    # Using nose tip, chin, and eye corners for stability
    LANDMARK_INDICES = {
        "nose_tip": 1,
        "chin": 152,
        "left_eye_outer": 33,
        "right_eye_outer": 263,
        "left_eye_inner": 133,
        "right_eye_inner": 362,
        "left_mouth": 61,
        "right_mouth": 291,
    }

    # 3D model points (generic face model)
    MODEL_POINTS = np.array([
        (0.0, 0.0, 0.0),          # Nose tip
        (0.0, -63.6, -12.5),      # Chin
        (-43.3, 32.7, -26.0),     # Left eye outer
        (43.3, 32.7, -26.0),      # Right eye outer
        (-28.9, 28.9, -24.1),     # Left eye inner
        (28.9, 28.9, -24.1),      # Right eye inner
        (-28.9, -28.9, -24.1),    # Left mouth
        (28.9, -28.9, -24.1),     # Right mouth
    ], dtype=np.float64)

    def __init__(
        self,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        model_path: str | None = None,
    ):
        """
        Initialize head pose estimator.

        Args:
            min_detection_confidence: Minimum confidence for face detection.
            min_tracking_confidence: Minimum confidence for face landmark tracking.
            model_path: Path to face_landmarker.task model file. 
                       If None, downloads automatically.
        """
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.model_path = model_path

        self._landmarker: Any = None
        self._is_initialized = False

    def _ensure_model(self) -> str:
        """Ensure model file exists, downloading if needed."""
        if self.model_path and Path(self.model_path).exists():
            return self.model_path

        # Default model location
        models_dir = Path(__file__).parent.parent.parent.parent / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        model_file = models_dir / "face_landmarker.task"

        if not model_file.exists():
            logger.info(f"Downloading FaceLandmarker model to {model_file}...")
            urllib.request.urlretrieve(FACE_LANDMARKER_MODEL_URL, model_file)
            logger.info("Model downloaded successfully")

        return str(model_file)

    def initialize(self) -> None:
        """Initialize MediaPipe FaceLandmarker."""
        if self._is_initialized:
            return

        logger.info("Initializing MediaPipe FaceLandmarker for head pose estimation")

        try:
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision
        except ImportError as e:
            raise ImportError(
                f"MediaPipe Tasks API not available: {e}. "
                "Install with: pip install mediapipe>=0.10.30"
            )

        # Ensure model exists
        model_path = self._ensure_model()

        # Create FaceLandmarker
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_faces=1,
            min_face_detection_confidence=self.min_detection_confidence,
            min_tracking_confidence=self.min_tracking_confidence,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=True,  # For pose estimation
        )

        self._landmarker = vision.FaceLandmarker.create_from_options(options)
        self._vision = vision  # Keep reference for Image creation
        self._is_initialized = True
        logger.info("Head pose estimator initialized with FaceLandmarker")

    def estimate(
        self,
        frame: np.ndarray,
        tracked_object: TrackedObject,
        padding: float = 0.3,
    ) -> HeadPoseResult:
        """
        Estimate head pose for a tracked object.

        Args:
            frame: Full BGR frame.
            tracked_object: Tracked object with bounding box.
            padding: Padding ratio around bounding box for face detection.

        Returns:
            HeadPoseResult with pose angles if face detected.
        """
        if not self._is_initialized:
            self.initialize()

        import mediapipe as mp

        # Extract and pad bounding box
        x1, y1, x2, y2 = tracked_object.bbox
        h, w = frame.shape[:2]

        # Add padding
        pad_w = int((x2 - x1) * padding)
        pad_h = int((y2 - y1) * padding)

        x1 = max(0, x1 - pad_w)
        y1 = max(0, y1 - pad_h)
        x2 = min(w, x2 + pad_w)
        y2 = min(h, y2 + pad_h)

        # Crop region
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return HeadPoseResult(track_id=tracked_object.track_id, pose=None)

        # Convert to RGB for MediaPipe
        crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)

        # Create MediaPipe Image
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=crop_rgb)

        # Detect face landmarks
        result = self._landmarker.detect(mp_image)

        if not result.face_landmarks:
            return HeadPoseResult(track_id=tracked_object.track_id, pose=None)

        # Get landmarks from first face
        landmarks = result.face_landmarks[0]
        crop_h, crop_w = crop.shape[:2]

        # Extract 2D image points
        image_points = []
        for name, idx in self.LANDMARK_INDICES.items():
            lm = landmarks[idx]
            image_points.append((lm.x * crop_w, lm.y * crop_h))

        image_points = np.array(image_points, dtype=np.float64)

        # Camera matrix (approximate)
        focal_length = crop_w
        center = (crop_w / 2, crop_h / 2)
        camera_matrix = np.array([
            [focal_length, 0, center[0]],
            [0, focal_length, center[1]],
            [0, 0, 1]
        ], dtype=np.float64)

        # Distortion coefficients (assume no distortion)
        dist_coeffs = np.zeros((4, 1))

        # Solve PnP
        success, rotation_vector, translation_vector = cv2.solvePnP(
            self.MODEL_POINTS,
            image_points,
            camera_matrix,
            dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )

        if not success:
            return HeadPoseResult(track_id=tracked_object.track_id, pose=None)

        # Convert rotation vector to euler angles
        rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
        pose_matrix = np.hstack((rotation_matrix, translation_vector))

        _, _, _, _, _, _, euler_angles = cv2.decomposeProjectionMatrix(
            np.vstack((pose_matrix, [0, 0, 0, 1]))[:3]
        )

        pitch = float(euler_angles[0][0])
        yaw = float(euler_angles[1][0])
        roll = float(euler_angles[2][0])

        # Normalize angles to reasonable range
        pitch = self._normalize_angle(pitch)
        yaw = self._normalize_angle(yaw)
        roll = self._normalize_angle(roll)

        pose = HeadPose(yaw=yaw, pitch=pitch, roll=roll)

        return HeadPoseResult(
            track_id=tracked_object.track_id,
            pose=pose,
            face_bbox=(x1, y1, x2, y2),
        )

    def estimate_batch(
        self,
        frame: np.ndarray,
        tracked_objects: list[TrackedObject],
    ) -> list[HeadPoseResult]:
        """
        Estimate head pose for multiple tracked objects.

        Args:
            frame: Full BGR frame.
            tracked_objects: List of tracked objects.

        Returns:
            List of HeadPoseResult for each tracked object.
        """
        return [self.estimate(frame, obj) for obj in tracked_objects]

    @staticmethod
    def _normalize_angle(angle: float) -> float:
        """Normalize angle to [-180, 180] range."""
        while angle > 180:
            angle -= 360
        while angle < -180:
            angle += 360
        return angle

    def close(self) -> None:
        """Close MediaPipe resources."""
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None
            self._is_initialized = False

    def __enter__(self) -> "HeadPoseEstimator":
        """Context manager entry."""
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()
