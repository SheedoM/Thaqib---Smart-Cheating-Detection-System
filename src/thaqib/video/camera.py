"""
Camera connection handler for IP cameras and webcams.

Provides a unified interface for capturing frames from various video sources.
"""

import logging
import time
from dataclasses import dataclass
from typing import Generator

import cv2
import numpy as np

from thaqib.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class FrameData:
    """Container for frame data with metadata."""

    frame: np.ndarray
    timestamp: float
    frame_index: int
    width: int
    height: int


class CameraStream:
    """
    Unified camera stream handler for webcams and IP cameras.

    Supports:
    - Local webcams (by index: 0, 1, 2, ...)
    - IP cameras via RTSP URL
    - Video files for testing

    Example:
        >>> camera = CameraStream(source=0)  # Webcam
        >>> camera = CameraStream(source="rtsp://192.168.1.100:554/stream")  # IP camera
        >>> camera = CameraStream(source="test_video.mp4")  # Video file

        >>> with camera:
        ...     for frame_data in camera.frames():
        ...         process(frame_data.frame)
    """

    def __init__(
        self,
        source: int | str | None = None,
        width: int | None = None,
        height: int | None = None,
        fps: int | None = None,
    ):
        """
        Initialize camera stream.

        Args:
            source: Camera source (webcam index, RTSP URL, or video file path).
                   If None, uses settings from environment.
            width: Desired frame width. If None, uses settings.
            height: Desired frame height. If None, uses settings.
            fps: Desired FPS. If None, uses settings.
        """
        settings = get_settings()

        self.source = source if source is not None else settings.camera_source_parsed
        self.width = width or settings.camera_width
        self.height = height or settings.camera_height
        self.target_fps = fps or settings.camera_fps

        self._cap: cv2.VideoCapture | None = None
        self._frame_index = 0
        self._is_opened = False

    def open(self) -> bool:
        """
        Open the camera connection.

        Returns:
            True if connection successful, False otherwise.
        """
        if self._is_opened:
            return True

        logger.info(f"Opening camera source: {self.source}")

        # Create video capture
        if isinstance(self.source, int):
            self._cap = cv2.VideoCapture(self.source, cv2.CAP_DSHOW)  # DirectShow on Windows
        else:
            self._cap = cv2.VideoCapture(self.source)

        if not self._cap.isOpened():
            logger.error(f"Failed to open camera source: {self.source}")
            return False

        # Set resolution
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, self.target_fps)

        # Get actual properties
        actual_width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self._cap.get(cv2.CAP_PROP_FPS)

        logger.info(
            f"Camera opened: {actual_width}x{actual_height} @ {actual_fps:.1f} FPS"
        )

        self._is_opened = True
        self._frame_index = 0
        return True

    def close(self) -> None:
        """Close the camera connection."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            self._is_opened = False
            logger.info("Camera closed")

    def read(self) -> FrameData | None:
        """
        Read a single frame from the camera.

        Returns:
            FrameData object if successful, None if failed.
        """
        if not self._is_opened or self._cap is None:
            return None

        ret, frame = self._cap.read()
        if not ret:
            logger.warning("Failed to read frame from camera")
            return None

        self._frame_index += 1

        return FrameData(
            frame=frame,
            timestamp=time.time(),
            frame_index=self._frame_index,
            width=frame.shape[1],
            height=frame.shape[0],
        )

    def frames(self) -> Generator[FrameData, None, None]:
        """
        Generator that yields frames continuously.

        Yields:
            FrameData objects for each frame.
        """
        while self._is_opened:
            frame_data = self.read()
            if frame_data is None:
                break
            yield frame_data

    def __enter__(self) -> "CameraStream":
        """Context manager entry."""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()

    @property
    def is_opened(self) -> bool:
        """Check if camera is opened."""
        return self._is_opened

    @property
    def frame_count(self) -> int:
        """Get number of frames read so far."""
        return self._frame_index
