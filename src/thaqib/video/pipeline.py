"""
Video processing pipeline orchestrator.

Coordinates camera, detection, and tracking.
"""

import logging
import time
import threading
import os
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Generator

from thaqib.video.reid import FaceReIdentifier

import numpy as np

from thaqib.config import get_settings
from thaqib.video.camera import CameraStream, FrameData
from thaqib.video.detector import HumanDetector, DetectionResult
from thaqib.video.tracker import ObjectTracker, TrackingResult, TrackedObject
from thaqib.video.registry import GlobalStudentRegistry, StudentSpatialState
from thaqib.video.neighbors import NeighborComputer
from thaqib.video.face_mesh import FaceMeshExtractor, FaceMeshResult
from thaqib.video.tools_detector import ToolsDetector, ToolsDetectionResult


logger = logging.getLogger(__name__)


@dataclass
class StudentState:
    """Current state for a monitored student."""

    track_id: int
    center: tuple[int, int]
    paper_center: tuple[int, int]
    bbox: tuple[int, int, int, int]
    neighbors: list[int] = field(default_factory=list)
    neighbor_distances: dict[int, float] = field(default_factory=dict)
    neighbor_papers: dict[int, tuple[int, int]] = field(default_factory=dict)
    surrounding_papers: list[tuple[int, int]] = field(default_factory=list)
    face_mesh: FaceMeshResult | None = None
    is_cheating: bool = False


@dataclass
class PipelineFrame:
    """Complete processed frame data."""

    frame: np.ndarray
    frame_index: int
    timestamp: float
    detection_result: DetectionResult | None
    tracking_result: TrackingResult                     # ⬅️ جبنا ده فوق
    tools_result: ToolsDetectionResult | None = None    # ⬅️ ونزلنا ده تحت
    registry: GlobalStudentRegistry | None = None
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
        ...         # Process student state here
        ...         pass
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
        self._tools_detector = ToolsDetector()
        self._tracker = ObjectTracker()
        self._registry = GlobalStudentRegistry()
        self._neighbor_computer = NeighborComputer()
        self._face_extractor = FaceMeshExtractor()
        self._reid = FaceReIdentifier()


        # Parallel executor for per-student processing
        optimal_workers = os.cpu_count() or 8
        self._face_executor = ThreadPoolExecutor(max_workers=optimal_workers)

        self._is_running = False
        
        # Async Detection State
        self._detection_queue: Queue[tuple[DetectionResult, ToolsDetectionResult]] = Queue(maxsize=1)
        self._current_frame_data: FrameData | None = None
        self._detection_thread: threading.Thread | None = None
        self._last_detection_result: DetectionResult | None = None
        self._last_tools_result: ToolsDetectionResult | None = None

        self._selected_ids: set[int] = set()

    def _detection_worker(self) -> None:
        """Background thread running YOLO detection."""
        last_detect_time = 0.0
        while self._is_running:
            current_time = time.time()
            if current_time - last_detect_time >= self.detection_interval:
                # Grab a reference to the latest frame
                frame_data = self._current_frame_data
                if frame_data is not None:
                    # Run both inferences (Human + Tools)
                    f_copy = frame_data.frame.copy()
                    
                    detection_result = self._detector.detect(
                        f_copy,
                        frame_data.frame_index,
                        frame_data.timestamp,
                    )
                    
                    tools_result = self._tools_detector.detect(
                        f_copy,
                        frame_data.frame_index,
                        frame_data.timestamp,
                    )
                    
                    last_detect_time = time.time()
                    
                    # Update queue (drop old if present)
                    try:
                        while not self._detection_queue.empty():
                            self._detection_queue.get_nowait()
                    except Empty:
                        pass
                    
                    try:
                        self._detection_queue.put_nowait((detection_result, tools_result))
                    except Exception:
                        pass
            
            time.sleep(0.01)  # Yield CPU

    def start(self) -> bool:
        """
        Start the pipeline.

        Returns:
            True if started successfully.
        """
        import torch
        torch.set_num_threads(1)
        
        logger.info("Starting video pipeline...")

        if not self._camera.open():
            logger.error("Failed to open camera")
            return False

        self._detector.load()
        self._tools_detector.load()

        self._is_running = True
        
        # Start async detection thread
        self._detection_thread = threading.Thread(
            target=self._detection_worker,
            daemon=True,
            name="DetectionThread"
        )
        self._detection_thread.start()

        logger.info("Video pipeline started")
        return True

    def stop(self) -> None:
        """Stop the pipeline."""
        logger.info("Stopping video pipeline...")
        self._is_running = False
        if self._detection_thread is not None:
            self._detection_thread.join(timeout=1.0)
        self._camera.close()
        self._face_extractor.close()
        self._face_executor.shutdown(wait=True)
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

            # Update latest frame for the detection thread
            self._current_frame_data = frame_data

            start_time = time.time()

            # Process frame
            pipeline_frame = self._process_frame(frame_data)
            pipeline_frame.processing_time_ms = (time.time() - start_time) * 1000

            yield pipeline_frame

    def _process_frame(self, frame_data: FrameData) -> PipelineFrame:
        """Process a single frame through the pipeline."""
        
        t0 = time.perf_counter()

        
        # Check for new detection async result
        new_detection = False
        try:
            detection_result, tools_result = self._detection_queue.get_nowait()
            self._last_detection_result = detection_result
            self._last_tools_result = tools_result
            new_detection = True
            logger.debug(f"Detection: {self._last_detection_result.count} persons, {self._last_tools_result.count} tools")
        except Empty:
            detection_result = self._last_detection_result
            tools_result = self._last_tools_result
            
        t1 = time.perf_counter()

        # Update tracking
        if new_detection and detection_result is not None:
            tracking_result = self._tracker.update(detection_result, frame_data.frame)
        else:
            # Create empty detection result for tracking
            tracking_result = TrackingResult(
                frame_index=frame_data.frame_index,
                timestamp=frame_data.timestamp,
                tracks=[],
            )

        t2 = time.perf_counter()

        # Apply Detection Stability Filter
        # Use Kalman-predicted bbox for selected tracks missing for < tolerance frames
        active_track_ids = {t.track_id for t in tracking_result.tracks}
        tolerance = 300  # Highly increased to keep tracks stable during heavy async processing
        for state in self._registry.get_all():
            if state.track_id not in active_track_ids and state.is_active:
                frames_missing = frame_data.frame_index - state.last_seen_frame
                if 0 < frames_missing < tolerance:
                    # Prefer Kalman-predicted position, fall back to last known
                    predicted_bbox = self._tracker.get_predicted_bbox(state.track_id)
                    bbox = predicted_bbox if predicted_bbox is not None else state.bbox
                    
                    # IoU Overlap Check against active tracks to detect ghost tracks
                    is_overlapping = False
                    for active_track in tracking_result.tracks:
                        xA = max(bbox[0], active_track.bbox[0])
                        yA = max(bbox[1], active_track.bbox[1])
                        xB = min(bbox[2], active_track.bbox[2])
                        yB = min(bbox[3], active_track.bbox[3])
                        interArea = max(0, xB - xA) * max(0, yB - yA)
                        if interArea > 0:
                            boxAArea = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
                            boxBArea = (active_track.bbox[2] - active_track.bbox[0]) * (active_track.bbox[3] - active_track.bbox[1])
                            iou = interArea / float(boxAArea + boxBArea - interArea)
                            if iou > 0.4:  # Using 0.4 as standard IoU threshold
                                is_overlapping = True
                                break

                    if is_overlapping:
                        # Completely purge the old ghost ID from the entire backend system
                        state.is_active = False
                        state.last_seen_time = 0.0  # Forces registry to delete it immediately
                        self._selected_ids.discard(state.track_id)
                        continue

                    mock_track = TrackedObject(
                        track_id=state.track_id,
                        bbox=bbox,
                        confidence=0.3,
                        is_selected=state.track_id in self._selected_ids,
                        is_predicted=True,
                    )
                    tracking_result.tracks.append(mock_track)

        # Apply Re-ID and ID mapping
        for track in tracking_result.tracks:
            track.is_selected = track.track_id in self._selected_ids


        # Update spatial registry and compute neighbors for ALL tracks
        self._registry.update(tracking_result.tracks, frame_data.frame_index, frame_data.timestamp)
        t3 = time.perf_counter()
        
        self._neighbor_computer.compute_neighbors(self._registry, k=4)
        
        # Compute paper neighbors specifically (excluding the student's closest paper)
        if tools_result is not None:
            paper_centers = [tool.center for tool in tools_result.tools if tool.label == 'book']
            self._neighbor_computer.compute_paper_neighbors(self._registry, paper_centers)
        
        t4 = time.perf_counter()

        # Process selected students only
        selected_tracks = [t for t in tracking_result.tracks if t.is_selected]
        student_states = []

        if selected_tracks:
            # 1. Build initial student states (sequential)
            for track in selected_tracks:
                spatial = self._registry.get(track.track_id)
                paper_center = ((track.bbox[0] + track.bbox[2]) // 2, track.bbox[3])
                state = StudentState(
                    track_id=track.track_id,
                    center=track.center,
                    paper_center=paper_center,
                    bbox=track.bbox,
                    neighbors=spatial.neighbors if spatial else [],
                    neighbor_distances=spatial.neighbor_distances if spatial else {},
                    neighbor_papers=spatial.neighbor_papers if spatial else {},
                    surrounding_papers=spatial.surrounding_papers if spatial else [],
                    face_mesh=spatial.face_mesh if spatial else None,
                    is_cheating=spatial.is_cheating if spatial else False,
                )
                student_states.append(state)

            # 2. Extract face mesh in background without blocking the main thread
            if frame_data.frame_index % 2 == 0:
                def make_callback(track_id):
                    def callback(future):
                        try:
                            _, result = future.result()
                            reg_state = self._registry.get(track_id)
                            if reg_state is not None:
                                reg_state.face_mesh = result  # Explicitly allow None to clear stale meshes
                                # Immediately evaluate cheating off the main thread
                                self._evaluate_cheating_async(track_id)
                        except Exception as e:
                            logger.debug(f"Face mesh parallel error: {e}")
                    return callback

                for state in student_states:
                    # Pass a COPY of the frame so it's safely processed in the background thread
                    future = self._face_executor.submit(
                        self._process_student_parallel,
                        frame_data.frame.copy(),
                        state
                    )
                    future.add_done_callback(make_callback(state.track_id))



        t5 = time.perf_counter()
        
        if frame_data.frame_index % 30 == 0:
            logger.info(
                f"PIPELINE_PERF:\n"
                f"  Detection: {(t1-t0)*1000:.1f} ms\n"
                f"  Tracking: {(t2-t1)*1000:.1f} ms\n"
                f"  Registry: {(t3-t2)*1000:.1f} ms\n"
                f"  Neighbors: {(t4-t3)*1000:.1f} ms\n"
                f"  FaceMesh: {(t5-t4)*1000:.1f} ms\n"
                f"  Total: {(t5-t0)*1000:.1f} ms"
            )

        return PipelineFrame(
            frame=frame_data.frame,
            frame_index=frame_data.frame_index,
            timestamp=frame_data.timestamp,
            detection_result=detection_result,
            tools_result=tools_result,
            tracking_result=tracking_result,
            registry=self._registry,
            student_states=student_states,
        )

    def select_students(self, track_ids: list[int]) -> None:
        """
        Select students to monitor.

        Args:
            track_ids: List of track IDs to monitor.
        """
        self._selected_ids = set(track_ids)
        self._tracker.select_tracks(track_ids)

    def add_student(self, track_id: int) -> None:
        """Add a student to monitoring."""
        self._selected_ids.add(track_id)
        self._tracker.add_selection(track_id)

    def remove_student(self, track_id: int) -> None:
        """Remove a student from monitoring."""
        self._selected_ids.discard(track_id)
        self._tracker.remove_selection(track_id)

    def clear_selection(self) -> None:
        """Clear all selected students."""
        self._selected_ids.clear()
        # Ensure tracker is also cleared if it has a method, else skip
        if hasattr(self._tracker, 'clear_selection'):
            self._tracker.clear_selection()

    def _process_student_parallel(self, frame: np.ndarray, state: StudentState) -> tuple[StudentState, FaceMeshResult | None]:
        """
        Process a single student's face mesh.
        Designed to be run in parallel via ThreadPoolExecutor.
        """
        face_mesh = self._face_extractor.extract(frame, state.bbox, state.track_id)
        return state, face_mesh

    def _evaluate_cheating_async(self, track_id: int) -> None:
        """Evaluate cheating rules asynchronously when face mesh is ready."""
        state = self._registry.get(track_id)
        if not state or not state.face_mesh or not state.surrounding_papers:
            if state: state.suspicious_start_time = 0.0
            return

        lm2d = state.face_mesh.landmarks_2d
        head_matrix = state.face_mesh.head_matrix
        if len(lm2d) < 474 or head_matrix is None:
            state.suspicious_start_time = 0.0
            return

        def pt2d(idx):
            return np.array(lm2d[idx], dtype=float)

        # 1. Calculate 3D Gaze Vector and project to 2D
        R = head_matrix[:3, :3]
        head_3d = R @ np.array([0.0, 0.0, -1.0])
        
        l_center, r_center = (pt2d(33) + pt2d(133)) / 2.0, (pt2d(263) + pt2d(362)) / 2.0
        avg_eye_dev = ((pt2d(468) - l_center) + (pt2d(473) - r_center)) / 2.0
        
        eye_width = np.linalg.norm(pt2d(33) - pt2d(133))
        if eye_width > 1e-6:
            avg_eye_dev /= eye_width

        eye_3d = np.array([-avg_eye_dev[0], avg_eye_dev[1], 0.0]) * 3.0
        combined_3d = head_3d + eye_3d
        
        gaze_dir = np.array([-combined_3d[0], combined_3d[1]])
        norm_gaze = np.linalg.norm(gaze_dir)
        if norm_gaze < 1e-6:
            return
        gaze_dir = gaze_dir / norm_gaze

        # 2. Check intersection with surrounding papers
        student_head_pos = pt2d(168)
        is_looking_at_paper = False

        for paper_pt in state.surrounding_papers:
            paper_vec = np.array(paper_pt) - student_head_pos
            dist = np.linalg.norm(paper_vec)
            if dist < 1e-6:
                continue
                
            paper_dir = paper_vec / dist
            dot_product = np.dot(gaze_dir, paper_dir)
            
            if dot_product > 0.92:
                is_looking_at_paper = True
                break

        # 3. Apply the 2-second rule
        current_time = time.time()
        
        if is_looking_at_paper:
            if state.suspicious_start_time == 0.0:
                state.suspicious_start_time = current_time
            elif current_time - state.suspicious_start_time >= 2.0:
                state.is_cheating = True
        else:
            state.suspicious_start_time = 0.0
            if not state.is_alert_recording:
                state.is_cheating = False

    def get_all_tracks(self) -> list[TrackedObject]:
        """Get all currently tracked objects (for selection UI)."""
        tracks = []
        for state in self._registry.get_all():
            if getattr(state, "is_active", True):
                tracks.append(
                    TrackedObject(
                        track_id=state.track_id,
                        bbox=state.bbox,
                        confidence=1.0,
                        is_selected=state.track_id in self._selected_ids,
                        is_predicted=False,
                    )
                )
        return tracks

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
