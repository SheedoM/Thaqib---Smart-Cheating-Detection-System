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
try:
    from thaqib.video.osnet_reid import OSNetReID as _OSNetReID
    _OSNET_AVAILABLE = True
except ImportError:
    _OSNET_AVAILABLE = False

import numpy as np

from thaqib.config import get_settings
from thaqib.video.camera import CameraStream, FrameData
from thaqib.video.detector import HumanDetector, DetectionResult
from thaqib.video.tracker import ObjectTracker, TrackingResult, TrackedObject
from thaqib.video.registry import GlobalStudentRegistry, StudentSpatialState
from thaqib.video.neighbors import NeighborComputer
from thaqib.video.face_mesh import FaceMeshExtractor, FaceMeshResult

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
    face_mesh: FaceMeshResult | None = None


@dataclass
class PipelineFrame:
    """Complete processed frame data."""

    frame: np.ndarray
    frame_index: int
    timestamp: float
    detection_result: DetectionResult | None
    tracking_result: TrackingResult
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
        self._tracker = ObjectTracker()
        self._registry = GlobalStudentRegistry()
        self._neighbor_computer = NeighborComputer()
        self._face_extractor = FaceMeshExtractor()
        self._reid = FaceReIdentifier()

        # OSNet appearance ReID (primary identity model; falls back to face reid)
        self._osnet: _OSNetReID | None = None
        if _OSNET_AVAILABLE:
            try:
                self._osnet = _OSNetReID()
                logger.info("OSNet-x0.25 ReID active.")
            except Exception as e:
                logger.warning(f"OSNet ReID unavailable: {e}. Using face-landmark fallback.")
        else:
            logger.info("torchreid not installed — using face-landmark ReID.")

        # OSNet embedding gallery: track_id → 512-dim L2 normalised embedding
        self._osnet_gallery: dict[int, np.ndarray] = {}
        
        # Parallel executor for per-student processing
        optimal_workers = os.cpu_count() or 8
        self._face_executor = ThreadPoolExecutor(max_workers=optimal_workers)

        self._is_running = False
        
        # Async Detection State
        self._detection_queue: Queue[DetectionResult] = Queue(maxsize=1)
        self._current_frame_data: FrameData | None = None
        self._detection_thread: threading.Thread | None = None
        self._last_detection_result: DetectionResult | None = None

        self._selected_ids: set[int] = set()
        
        # Identity maps
        self._id_map: dict[int, int] = {}  # new_track_id -> old_track_id
        self._known_tracks: set[int] = set()

    def _detection_worker(self) -> None:
        """Background thread running YOLO detection."""
        last_detect_time = 0.0
        while self._is_running:
            current_time = time.time()
            if current_time - last_detect_time >= self.detection_interval:
                # Grab a reference to the latest frame
                frame_data = self._current_frame_data
                if frame_data is not None:
                    # Run YOLO inference
                    detection_result = self._detector.detect(
                        frame_data.frame.copy(),
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
                        self._detection_queue.put_nowait(detection_result)
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
            detection_result = self._detection_queue.get_nowait()
            self._last_detection_result = detection_result
            new_detection = True
            logger.debug(f"Detection: {self._last_detection_result.count} persons")
        except Empty:
            detection_result = self._last_detection_result
            
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
            mapped_id = self._id_map.get(track.track_id, track.track_id)
            if self._tracker.is_locked(track.track_id):
                mapped_id = track.track_id

            track.track_id = mapped_id
            track.is_selected = track.track_id in self._selected_ids

            if track.track_id not in self._known_tracks:
                self._known_tracks.add(track.track_id)


        # Update spatial registry and compute neighbors for ALL tracks
        self._registry.update(tracking_result.tracks, frame_data.frame_index, frame_data.timestamp)
        t3 = time.perf_counter()
        
        self._neighbor_computer.compute_neighbors(self._registry, k=4)
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
                    face_mesh=spatial.face_mesh if spatial else None, 
                )
                student_states.append(state)

            # 2. Extract face mesh in background without blocking the main thread
            if frame_data.frame_index % 2 == 0:
                def make_callback(track_id):
                    def callback(future):
                        try:
                            _, result = future.result()
                            if result is not None:
                                reg_state = self._registry.get(track_id)
                                if reg_state is not None:
                                    reg_state.face_mesh = result
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

            # 3. Batch process OSNet Embeddings
            osnet_embeddings = []
            if self._osnet is not None:
                bboxes = [state.bbox for state in student_states]
                # Process all bounding boxes in one forward pass
                osnet_embeddings = self._osnet.extract_batch(frame_data.frame, bboxes)
            else:
                osnet_embeddings = [None] * len(student_states)

            # 5. Process the OSNet Embeddings we got from the batch
            for state, osnet_emb in zip(student_states, osnet_embeddings):
                if osnet_emb is not None:
                    if state.track_id in self._osnet_gallery:
                        prev = self._osnet_gallery[state.track_id]
                        blended = 0.8 * prev + 0.2 * osnet_emb
                        norm = np.linalg.norm(blended)
                        if norm > 1e-6:
                            blended /= norm
                        self._osnet_gallery[state.track_id] = blended
                    else:
                        self._osnet_gallery[state.track_id] = osnet_emb
                        # Attempt matching against gallery for new tracks
                        if self._osnet is not None:
                            match = self._osnet.match_against_gallery(
                                osnet_emb, 
                                {k:v for k,v in self._osnet_gallery.items() if k != state.track_id}, 
                                threshold=0.96  # Increased to prevent false ID merging
                            )
                            if match is not None:
                                matched_id, _ = match
                                self._id_map[state.track_id] = matched_id
                                state.track_id = matched_id
                                
                    # Also update registry
                    if frame_data.frame_index % 10 == 0:
                        reg_state = self._registry.get(state.track_id)
                        if reg_state is not None:
                            reg_state.update_embedding(osnet_emb)

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
