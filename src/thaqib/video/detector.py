"""
Human detection using YOLOv8.

Provides periodic detection of human subjects in video frames.
"""

import logging
from dataclasses import dataclass, field

import numpy as np
from ultralytics import YOLO

from thaqib.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class Detection:
    """Single detection result."""

    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)
    confidence: float
    class_id: int = 0  # 0 = person in COCO

    @property
    def center(self) -> tuple[int, int]:
        """Get center point of bounding box."""
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    @property
    def width(self) -> int:
        """Get bounding box width."""
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> int:
        """Get bounding box height."""
        return self.bbox[3] - self.bbox[1]

    @property
    def area(self) -> int:
        """Get bounding box area."""
        return self.width * self.height


@dataclass
class DetectionResult:
    """Result of detection on a single frame."""

    frame_index: int
    timestamp: float
    detections: list[Detection] = field(default_factory=list)

    @property
    def count(self) -> int:
        """Number of detections."""
        return len(self.detections)


class HumanDetector:
    """
    YOLOv8-based human detector.

    Performs periodic detection of human subjects in video frames.
    Only detects the 'person' class.

    Example:
        >>> detector = HumanDetector()
        >>> result = detector.detect(frame, frame_index=1, timestamp=1234567890.0)
        >>> for detection in result.detections:
        ...     print(f"Person at {detection.center} with confidence {detection.confidence:.2f}")
    """

    PERSON_CLASS_ID = 0  # COCO class ID for person

    def __init__(
        self,
        model_name: str | None = None,
        confidence_threshold: float | None = None,
        device: str | None = None,
    ):
        """
        Initialize the human detector.

        Args:
            model_name: YOLO model name (e.g., 'yolov8n', 'yolov8s'). 
                       If None, uses settings.
            confidence_threshold: Minimum confidence for detections.
                                 If None, uses settings.
            device: Device to run inference on ('cpu', 'cuda', 'mps').
                   If None, auto-selects best available.
        """
        settings = get_settings()

        self.model_name = model_name or settings.yolo_model
        self.confidence_threshold = confidence_threshold or settings.detection_confidence
        self.device = device

        self._model: YOLO | None = None
        self._is_loaded = False

    def load(self) -> None:
        """Load the YOLO model."""
        if self._is_loaded:
            return

        logger.info(f"Loading YOLO model: {self.model_name}")

        self._model = YOLO(f"{self.model_name}.pt")

        # Move to device if specified
        if self.device:
            self._model.to(self.device)

        self._is_loaded = True
        logger.info("YOLO model loaded successfully")

    def detect(
        self,
        frame: np.ndarray,
        frame_index: int,
        timestamp: float,
    ) -> DetectionResult:
        """
        Detect humans in a single frame.

        Args:
            frame: BGR image as numpy array (from OpenCV).
            frame_index: Index of the frame in the video.
            timestamp: Timestamp of the frame.

        Returns:
            DetectionResult containing all detected humans.
        """
        if not self._is_loaded:
            self.load()

        # Run inference
        results = self._model(
            frame,
            conf=self.confidence_threshold,
            classes=[self.PERSON_CLASS_ID],  # Only detect persons
            verbose=False,
            device="cpu" if not self.device else self.device,
        )

        # Parse results
        detections = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for i in range(len(boxes)):
                # Get bounding box (xyxy format)
                bbox = boxes.xyxy[i].cpu().numpy().astype(int)
                confidence = float(boxes.conf[i].cpu().numpy())
                class_id = int(boxes.cls[i].cpu().numpy())

                detections.append(
                    Detection(
                        bbox=(int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])),
                        confidence=confidence,
                        class_id=class_id,
                    )
                )

        return DetectionResult(
            frame_index=frame_index,
            timestamp=timestamp,
            detections=detections,
        )

    def __enter__(self) -> "HumanDetector":
        """Context manager entry."""
        self.load()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        pass  # YOLO handles cleanup automatically

    @property
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._is_loaded
