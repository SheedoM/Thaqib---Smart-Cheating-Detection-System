"""
Video processing pipeline orchestrator.

Coordinates camera, detection, tracking, head pose, and neighbor modeling.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Generator

import cv2
import numpy as np

from thaqib.config import get_settings
from thaqib.video.camera import CameraStream, FrameData
from thaqib.video.detector import HumanDetector, DetectionResult
from thaqib.video.tracker import ObjectTracker, TrackingResult, TrackedObject
from thaqib.video.head_pose import HeadPoseEstimator, HeadPoseResult
from thaqib.video.neighbor import NeighborModeler, StudentSpatialContext

logger = logging.getLogger(__name__)


@dataclass
class StudentState:
    """Current state for a monitored student."""

    track_id: int
    center: tuple[int, int]
    bbox: tuple[int, int, int, int]
    head_pose: HeadPoseResult | None = None
    spatial_context: StudentSpatialContext | None = None
    is_looking_at_neighbor: bool = False
    looking_at_neighbor_id: int | None = None


@dataclass
class PipelineFrame:
    """Complete processed frame data."""

    frame: np.ndarray
    frame_index: int
    timestamp: float
    detection_result: DetectionResult | None
    tracking_result: TrackingResult
    student_states: list[StudentState] = field(default_factory=list)
    processing_time_ms: float = 0.0

    @property
    def tracked_count(self) -> int:
        """Number of tracked objects."""
        return self.tracking_result.count

    @property
    def selected_count(self) -> int:
        """Number of selected (monitored) students."""
        return self.tracking_result.selected_count


class VideoPipeline:
    """
    Main video processing pipeline.

    Orchestrates all video processing components:
    1. Camera capture
    2. Periodic human detection (YOLOv8)
    3. Continuous tracking (ByteTrack)
    4. Head pose estimation (MediaPipe)
    5. Neighbor modeling and risk angle calculation

    Example:
        >>> pipeline = VideoPipeline(source=0)  # Webcam
        >>> pipeline.start()
        >>>
        >>> # Select students to monitor
        >>> pipeline.select_students([1, 2, 3])
        >>>
        >>> # Process frames
        >>> for frame_data in pipeline.run():
        ...     for student in frame_data.student_states:
        ...         if student.is_looking_at_neighbor:
        ...             print(f"Alert: Student {student.track_id} looking at {student.looking_at_neighbor_id}")
        >>>
        >>> pipeline.stop()
    """

    def __init__(
        self,
        source: int | str | None = None,
        detection_interval: float | None = None,
        on_alert: Callable[[StudentState], None] | None = None,
    ):
        """
        Initialize video pipeline.

        Args:
            source: Camera source (webcam index, RTSP URL, or video file).
            detection_interval: Seconds between full detection runs.
            on_alert: Callback function when suspicious behavior detected.
        """
        settings = get_settings()

        self.detection_interval = detection_interval or settings.detection_interval
        self.on_alert = on_alert

        # Initialize components
        self._camera = CameraStream(source=source)
        self._detector = HumanDetector()
        self._tracker = ObjectTracker()
        self._head_pose = HeadPoseEstimator()
        self._neighbor_modeler = NeighborModeler()

        # State
        self._is_running = False
        self._last_detection_time = 0.0
        self._last_detection_result: DetectionResult | None = None

    def start(self) -> bool:
        """
        Start the pipeline.

        Returns:
            True if started successfully.
        """
        logger.info("Starting video pipeline...")

        if not self._camera.open():
            logger.error("Failed to open camera")
            return False

        self._detector.load()
        self._head_pose.initialize()

        self._is_running = True
        self._last_detection_time = 0.0
        logger.info("Video pipeline started")
        return True

    def stop(self) -> None:
        """Stop the pipeline."""
        logger.info("Stopping video pipeline...")
        self._is_running = False
        self._camera.close()
        self._head_pose.close()
        logger.info("Video pipeline stopped")

    def run(self) -> Generator[PipelineFrame, None, None]:
        """
        Run the pipeline and yield processed frames.

        Yields:
            PipelineFrame for each processed frame.
        """
        if not self._is_running:
            if not self.start():
                return

        for frame_data in self._camera.frames():
            if not self._is_running:
                break

            start_time = time.time()

            # Process frame
            pipeline_frame = self._process_frame(frame_data)
            pipeline_frame.processing_time_ms = (time.time() - start_time) * 1000

            yield pipeline_frame

    def _process_frame(self, frame_data: FrameData) -> PipelineFrame:
        """Process a single frame through the pipeline."""
        current_time = time.time()
        detection_result = None

        # Run detection periodically
        if current_time - self._last_detection_time >= self.detection_interval:
            detection_result = self._detector.detect(
                frame_data.frame,
                frame_data.frame_index,
                frame_data.timestamp,
            )
            self._last_detection_time = current_time
            self._last_detection_result = detection_result
            logger.debug(f"Detection: {detection_result.count} persons")

        # Update tracking
        if self._last_detection_result is not None:
            tracking_result = self._tracker.update(self._last_detection_result)
        else:
            # Create empty detection result for tracking
            tracking_result = TrackingResult(
                frame_index=frame_data.frame_index,
                timestamp=frame_data.timestamp,
                tracks=[],
            )

        # Process selected students only
        selected_tracks = [t for t in tracking_result.tracks if t.is_selected]
        student_states = []

        if selected_tracks:
            # Estimate head poses
            head_poses = self._head_pose.estimate_batch(frame_data.frame, selected_tracks)
            pose_map = {hp.track_id: hp for hp in head_poses}

            # Compute spatial contexts
            spatial_contexts = self._neighbor_modeler.compute(tracking_result)
            context_map = {ctx.track_id: ctx for ctx in spatial_contexts}

            # Build student states
            for track in selected_tracks:
                head_pose = pose_map.get(track.track_id)
                spatial_context = context_map.get(track.track_id)

                # Check if looking at neighbor
                is_looking_at_neighbor = False
                looking_at_neighbor_id = None

                if head_pose and head_pose.has_pose and spatial_context:
                    matching_risk = spatial_context.get_matching_risk(head_pose.pose.yaw)
                    if matching_risk:
                        is_looking_at_neighbor = True
                        looking_at_neighbor_id = matching_risk.neighbor_id

                state = StudentState(
                    track_id=track.track_id,
                    center=track.center,
                    bbox=track.bbox,
                    head_pose=head_pose,
                    spatial_context=spatial_context,
                    is_looking_at_neighbor=is_looking_at_neighbor,
                    looking_at_neighbor_id=looking_at_neighbor_id,
                )
                student_states.append(state)

                # Trigger alert callback
                if is_looking_at_neighbor and self.on_alert:
                    self.on_alert(state)

        return PipelineFrame(
            frame=frame_data.frame,
            frame_index=frame_data.frame_index,
            timestamp=frame_data.timestamp,
            detection_result=detection_result,
            tracking_result=tracking_result,
            student_states=student_states,
        )

    def select_students(self, track_ids: list[int]) -> None:
        """
        Select students to monitor.

        Args:
            track_ids: List of track IDs to monitor.
        """
        self._tracker.select_tracks(track_ids)

    def add_student(self, track_id: int) -> None:
        """Add a student to monitoring."""
        self._tracker.add_selection(track_id)

    def remove_student(self, track_id: int) -> None:
        """Remove a student from monitoring."""
        self._tracker.remove_selection(track_id)

    def get_all_tracks(self) -> list[TrackedObject]:
        """Get all currently tracked objects (for selection UI)."""
        if self._last_detection_result:
            result = self._tracker.update(self._last_detection_result)
            return result.tracks
        return []

    @property
    def is_running(self) -> bool:
        """Check if pipeline is running."""
        return self._is_running

    def __enter__(self) -> "VideoPipeline":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.stop()
