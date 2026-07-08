"""
Camera connection handler for IP cameras, webcams, and video files.
"""

import logging
import time
import platform
import threading
from collections import deque
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
        clock=None,
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
        self._original_width: int = 0
        self._original_height: int = 0
        
        # Threaded Queue
        self._frame_queue = deque(maxlen=5)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._clock = clock
        self._clock = clock

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
            # Choose platform-appropriate backend for index-based webcam sources.
            # DirectShow (Windows), AVFoundation (macOS), or auto-detect (Linux).
            if platform.system() == "Windows":
                backend = cv2.CAP_DSHOW
            elif platform.system() == "Darwin":
                backend = cv2.CAP_AVFOUNDATION
            else:
                backend = cv2.CAP_ANY
            self._cap = cv2.VideoCapture(self.source, backend)
        else:
            self._cap = cv2.VideoCapture(self.source)

        if not self._cap.isOpened():
            logger.error(f"Failed to open camera source: {self.source}")
            return False

        # Set resolution
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, self.target_fps)

        # Get actual properties and cache for public access
        actual_width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self._cap.get(cv2.CAP_PROP_FPS)
        self._original_width = actual_width
        self._original_height = actual_height

        logger.info(
            f"Camera opened: {actual_width}x{actual_height} @ {actual_fps:.1f} FPS"
        )

        self._is_opened = True
        self._frame_index = 0
        
        # Start reader thread
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._update_loop, daemon=True)
        self._thread.start()

        return True

    def _update_loop(self) -> None:
        """Background thread to read frames without blocking pipeline."""
        fps = self.target_fps if self.target_fps else 30.0
        frame_time_target = 1.0 / fps
        failed_frames = 0

        failed_frames = 0
        stream_start_time = None
        file_frame_idx = 0
        
        # Get actual file FPS for fallback calculation if CAP_PROP_POS_MSEC fails
        file_fps = 30.0
        if self._cap and self._cap.isOpened():
            file_fps = self._cap.get(cv2.CAP_PROP_FPS)
            if file_fps <= 0:
                file_fps = 30.0

        while not self._stop_event.is_set() and self._is_opened:
            if self._cap is None or not self._cap.isOpened():
                logger.warning("Camera lost, reconnecting...")
                if self._cap is not None:
                    self._cap.release()
                time.sleep(2.0)
                
                # Attempt to reconnect
                if isinstance(self.source, int):
                    if platform.system() == "Windows":
                        backend = cv2.CAP_DSHOW
                    elif platform.system() == "Darwin":
                        backend = cv2.CAP_AVFOUNDATION
                    else:
                        backend = cv2.CAP_ANY
                    self._cap = cv2.VideoCapture(self.source, backend)
                else:
                    self._cap = cv2.VideoCapture(self.source)
                    
                if self._cap.isOpened():
                    self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                    self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                    self._cap.set(cv2.CAP_PROP_FPS, self.target_fps)
                    logger.info("Camera reconnected successfully.")
                    failed_frames = 0
                    continue
                else:
                    logger.error("Reconnection failed. Retrying in 2 seconds...")
                    time.sleep(2.0)
                    continue
                
            ret, frame = self._cap.read()
            if not ret:
                failed_frames += 1
                if failed_frames > 15:
                    # For video files, EOF is expected — stop cleanly
                    # instead of reconnecting (which would replay the file).
                    if isinstance(self.source, str) and not self.source.startswith("rtsp"):
                        logger.info("Video file ended (EOF). Stopping reader thread.")
                        logger.warning(f"Camera stream disconnected — video buffer is now stale.")
                        self._is_opened = False
                        # Set stop event immediately on EOF to wake any waiting reader threads and prevent CPU spin.
                        self._stop_event.set()
                        break
                    logger.warning(f"Failed to read {failed_frames} consecutive frames. Reconnecting...")
                    if self._cap is not None:
                        self._cap.release()
                    self._cap = None
                    failed_frames = 0
                continue
                
            is_file = isinstance(self.source, str) and not self.source.startswith("rtsp")
            
            if is_file:
                if stream_start_time is None:
                    stream_start_time = self._clock.now() if self._clock else time.time()
                    
                frame_msec = self._cap.get(cv2.CAP_PROP_POS_MSEC)
                if frame_msec > 0:
                    frame_sec = frame_msec / 1000.0
                else:
                    frame_sec = file_frame_idx / file_fps
                    
                file_frame_idx += 1
                
                now = self._clock.now() if self._clock else time.time()
                elapsed_since_start = now - stream_start_time
                
                sleep_time = frame_sec - elapsed_since_start
                if sleep_time > 0:
                    time.sleep(sleep_time)
                elif sleep_time < -(1.0 / fps):
                    # Drop frame if we are lagging behind by more than 1 frame duration
                    # This ensures 60fps videos play correctly at 30fps without slow motion
                    continue
                    
                ts = stream_start_time + frame_sec
            else:
                ts = self._clock.now() if self._clock else time.time()
                
            self._frame_index += 1
                
            fd = FrameData(
                frame=frame,
                timestamp=ts,
                frame_index=self._frame_index,
                width=frame.shape[1],
                height=frame.shape[0],
            )
            self._frame_queue.append(fd)

        # Stop event already set in the EOF branch above; set it again here
        # in case the loop exited through the while-condition (stop_event or
        # _is_opened cleared from outside), so callers always see it set.
        self._stop_event.set()

    def close(self) -> None:
        """Close the camera connection."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
            
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            self._is_opened = False
            logger.info("Camera closed")

    def read(self) -> FrameData | None:
        """
        Read a single frame from the camera queue.

        Returns:
            FrameData object if successful, None if failed or stream ended.
        """
        if not self._is_opened:
            return None

        # Wait for a frame to arrive in the queue or read final frame
        while True:
            try:
                # Protect popleft operation from concurrent clearing of frame queue.
                return self._frame_queue.popleft()
            except IndexError:
                # queue emptied between check and pop — spin again
                pass
            
            if not self._is_opened or self._stop_event.is_set():
                break
            time.sleep(0.01)
            
        return None

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
    def original_width(self) -> int:
        """Original frame width from the camera/video source."""
        return self._original_width

    @property
    def original_height(self) -> int:
        """Original frame height from the camera/video source."""
        return self._original_height

    @property
    def frame_count(self) -> int:
        """Get number of frames read so far."""
        return self._frame_index

    @property
    def actual_fps(self) -> float:
        """Measured FPS as reported by the capture device after open().

        Falls back to target_fps (or 30.0) when the device has not been
        opened yet or reports an invalid value.
        """
        if self._cap is not None:
            fps = self._cap.get(cv2.CAP_PROP_FPS)
            if fps > 0:
                return fps
        return float(self.target_fps or 30)
