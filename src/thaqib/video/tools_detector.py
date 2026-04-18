"""
Detector for cheating tools like papers, phones, etc.
"""

import logging
from dataclasses import dataclass
import numpy as np
from ultralytics import YOLO

from thaqib.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ToolDetection:
    """A single detected tool."""

    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)
    confidence: float
    class_id: int
    label: str

    @property
    def center(self) -> tuple[int, int]:
        """Get the center of the bounding box."""
        return (
            (self.bbox[0] + self.bbox[2]) // 2,
            (self.bbox[1] + self.bbox[3]) // 2,
        )


@dataclass
class ToolsDetectionResult:
    """Detection results for a single frame."""

    frame_index: int
    timestamp: float
    tools: list[ToolDetection]

    @property
    def count(self) -> int:
        """Number of detected tools."""
        return len(self.tools)


class ToolsDetector:
    """Detects cheating tools (papers, phones) in video frames."""

    def __init__(self):
        """Initialize the detector."""
        self._settings = get_settings()
        self._model: YOLO | None = None
        # Target classes from settings (configurable via .env)
        self.target_labels = list(self._settings.tools_target_labels)

    def load(self) -> None:
        """Load the YOLO model for tools."""
        if self._model is not None:
            return
            
        model_path = self._settings.tools_model
        logger.info(f"Loading tools model: {model_path}")
        self._model = YOLO(model_path)
        
        # Determine device
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model.to(device)
        
        # Log available classes
        logger.info(f"Tools model classes: {self._model.names}")
        logger.info(f"Target labels: {self.target_labels}")
        
        # Warmup
        dummy_img = np.zeros((720, 1280, 3), dtype=np.uint8)
        self._model(dummy_img, verbose=False)

    def detect(self, frame: np.ndarray, frame_index: int, timestamp: float) -> ToolsDetectionResult:
        """
        Run detection on a single frame.

        Args:
            frame: Video frame (BGR).
            frame_index: Sequential number of the frame.
            timestamp: Frame timestamp.

        Returns:
            Detection results.
        """
        if self._model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        # Run inference with requested settings
        # Note: We let YOLO handle finding our target classes then filter in Python
        # if the model doesn't explicitly guarantee matching indices for these string labels
        results = self._model(
            frame,
            verbose=False,
            device=self._model.device,
            imgsz=640,
            conf=0.25,
            iou=0.45,
            agnostic_nms=True,
        )
        
        tools = []
        if results and len(results) > 0:
            result = results[0]
            boxes = result.boxes.cpu()

            if frame_index % 300 == 0:
                detected_labels = [result.names[int(b.cls[0])] for b in boxes]
                logger.debug(f"Tools detected: {detected_labels}")
            
            for i in range(len(boxes)):
                box = boxes[i]
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                
                # Model's class name mapping
                label = result.names[cls_id]
                
                # Filter strictly by the required target labels
                if label in self.target_labels:
                    xyxy = box.xyxy[0].numpy().astype(int)
                    tools.append(
                        ToolDetection(
                            bbox=(xyxy[0], xyxy[1], xyxy[2], xyxy[3]),
                            confidence=conf,
                            class_id=cls_id,
                            label=label,
                        )
                    )

        return ToolsDetectionResult(
            frame_index=frame_index,
            timestamp=timestamp,
            tools=tools,
        )
