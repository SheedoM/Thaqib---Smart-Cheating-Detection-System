"""
Human detection using YOLO.
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
    YOLOv8/YOLO11-based human (and optionally phone) detector.

    Performs periodic detection of human subjects in video frames.
    Only detects the 'person' class by default.

    When yolo_phone_detection is enabled (settings default), also detects
    'cell phone' (COCO class 67) in the same inference pass at zero extra cost.
    Phone detections are identified by class_id == PHONE_CLASS_ID downstream.

    Example:
        >>> detector = HumanDetector()
        >>> result = detector.detect(frame, frame_index=1, timestamp=1234567890.0)
        >>> persons = [d for d in result.detections if d.class_id == HumanDetector.PERSON_CLASS_ID]
        >>> phones  = [d for d in result.detections if d.class_id == HumanDetector.PHONE_CLASS_ID]
    """

    PERSON_CLASS_ID = 0   # COCO class ID for person
    PHONE_CLASS_ID  = 67  # COCO class ID for cell phone

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
            confidence_threshold: Minimum confidence for person detections.
                                 If None, uses settings.
            device: Device to run inference on ('cpu', 'cuda', 'mps').
                   If None, auto-selects best available.
        """
        settings = get_settings()

        self.model_name = model_name or settings.yolo_model
        self.confidence_threshold = (
            settings.detection_confidence if confidence_threshold is None
            else confidence_threshold
        )
        self.imgsz = getattr(settings, 'detection_imgsz', 640)
        self.device = device

        # Phone detection via YOLO — same model, class 67
        self._yolo_phone_detection: bool = settings.yolo_phone_detection
        self._phone_class_id: int = settings.phone_class_id
        self._phone_confidence: float = settings.phone_confidence
        # Dedicated phone model path (empty = reuse main model)
        self._phone_model_path: str = settings.phone_model.strip()

        self._model: YOLO | None = None
        self._phone_model: YOLO | None = None  # Only set when phone_model_path is given
        self._is_loaded = False

    def load(self) -> None:
        """Load the YOLO model."""
        if self._is_loaded:
            return

        logger.info(f"Loading YOLO model: {self.model_name}")

        import torch
        self._device = "cuda" if torch.cuda.is_available() else "cpu"

        self._model = YOLO(f"{self.model_name}")
        self._model.to(self._device)

        # Warmup main model
        dummy = np.zeros((640, 640, 3), dtype=np.uint8)
        self._model(dummy, verbose=False, device=self._device, imgsz=self.imgsz)

        # Load dedicated phone model if configured
        if self._yolo_phone_detection and self._phone_model_path:
            logger.info(f"Loading dedicated phone model: {self._phone_model_path}")
            try:
                self._phone_model = YOLO(self._phone_model_path)
                self._phone_model.to(self._device)
                self._phone_model(dummy, verbose=False, device=self._device)
                logger.info(f"Phone model loaded: {self._phone_model_path}")
            except Exception as e:
                logger.error(
                    f"Failed to load phone model '{self._phone_model_path}': {e}. "
                    f"Falling back to main model for phone detection."
                )
                self._phone_model = None
        else:
            self._phone_model = None

        self._is_loaded = True
        phone_info = "OFF"
        if self._yolo_phone_detection:
            if self._phone_model_path and self._phone_model is not None:
                phone_info = f"ON — dedicated model: {self._phone_model_path} (conf={self._phone_confidence})"
            elif self._phone_model_path and self._phone_model is None:
                phone_info = f"ON — fallback to main model (dedicated model failed to load)"
            else:
                phone_info = f"ON — shared model, class {self._phone_class_id} (conf={self._phone_confidence})"
        logger.info(
            f"YOLO model loaded: {self.model_name} | device={self._device} | "
            f"imgsz={self.imgsz} | person_conf={self.confidence_threshold} | "
            f"phone={phone_info}"
        )

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

        detections = []

        # ── Person detection (always uses main model) ──────────────────────────
        results = self._model(
            frame,
            conf=self.confidence_threshold,
            classes=[self.PERSON_CLASS_ID],
            device=self._device,
            verbose=False,
            imgsz=self.imgsz,
        )
        for result in results:
            boxes = result.boxes
            if boxes is None or len(boxes) == 0:
                continue
            xyxy_arr = boxes.xyxy.cpu().numpy().astype(int)
            conf_arr = boxes.conf.cpu().numpy()
            for i in range(len(boxes)):
                detections.append(Detection(
                    bbox=(xyxy_arr[i][0], xyxy_arr[i][1], xyxy_arr[i][2], xyxy_arr[i][3]),
                    confidence=float(conf_arr[i]),
                    class_id=self.PERSON_CLASS_ID,
                ))

        # ── Phone detection ────────────────────────────────────────────────────
        if self._yolo_phone_detection:
            # Use dedicated phone model if available, else use main model
            phone_model = self._phone_model if self._phone_model is not None else self._model
            phone_classes = None if self._phone_model is not None else [self._phone_class_id]

            phone_results = phone_model(
                frame,
                conf=self._phone_confidence,
                classes=phone_classes,
                device=self._device,
                verbose=False,
                imgsz=self.imgsz,
            )
            for result in phone_results:
                boxes = result.boxes
                if boxes is None or len(boxes) == 0:
                    continue
                xyxy_arr = boxes.xyxy.cpu().numpy().astype(int)
                conf_arr = boxes.conf.cpu().numpy()
                cls_arr  = boxes.cls.cpu().numpy().astype(int)
                for i in range(len(boxes)):
                    cls_id = int(cls_arr[i])
                    # For shared model: only keep phone class
                    # For dedicated model: keep all detections (model outputs only phones)
                    if self._phone_model is None and cls_id != self._phone_class_id:
                        continue
                    detections.append(Detection(
                        bbox=(xyxy_arr[i][0], xyxy_arr[i][1], xyxy_arr[i][2], xyxy_arr[i][3]),
                        confidence=float(conf_arr[i]),
                        class_id=self._phone_class_id,  # always tag as phone class
                    ))

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
