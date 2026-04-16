"""
Video processing pipeline orchestrator.

Coordinates camera, detection, and tracking.
"""

import logging
import math
import time
import threading
import os
from queue import Queue, Empty
from collections import deque
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
        settings = get_settings()
        face_workers = min(settings.face_mesh_workers, os.cpu_count() or 4)
        self._face_executor = ThreadPoolExecutor(max_workers=face_workers)

        self._is_running = False
        
        self._frame_lock = threading.Lock()
        self._track_aliases: dict[int, int] = {}
        self._global_frame_buffer: deque[np.ndarray] = deque(maxlen=60)
        
        # Cheating cooldown: number of frames before is_cheating resets.
        # 30 frames ≈ 1 second at 30fps — prevents false-negative oscillation
        # when a student briefly glances away then back.
        self._cheating_cooldown_frames = 30
        
        # Async Detection State
        self._detection_queue: Queue[tuple[DetectionResult, ToolsDetectionResult]] = Queue(maxsize=1)
        self._current_frame_data: FrameData | None = None
        self._detection_thread: threading.Thread | None = None
        self._last_detection_result: DetectionResult | None = None
        self._last_tools_result: ToolsDetectionResult | None = None
        self._last_tracking_result: TrackingResult | None = None

        self._selected_ids: set[int] = set()

    def _detection_worker(self) -> None:
        """Background thread running YOLO detection."""
        last_detect_time = 0.0
        while self._is_running:
            current_time = time.time()
            if current_time - last_detect_time >= self.detection_interval:
                # Grab a reference to the latest frame
                with self._frame_lock:
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
        settings = get_settings()
        if settings.torch_num_threads is not None:
            import torch
            torch.set_num_threads(settings.torch_num_threads)
        
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
            with self._frame_lock:
                self._current_frame_data = frame_data

            start_time = time.time()

            # Process frame
            pipeline_frame = self._process_frame(frame_data)
            pipeline_frame.processing_time_ms = (time.time() - start_time) * 1000

            yield pipeline_frame

    def _process_frame(self, frame_data: FrameData) -> PipelineFrame:
        """Process a single frame through the pipeline."""
        
        t0 = time.perf_counter()

        # Add to global frame ring buffer for alert recordings
        # Only buffer when students are being monitored to save memory.
        if self._selected_ids:
            self._global_frame_buffer.append(frame_data.frame.copy())

        
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
            self._last_tracking_result = tracking_result
        elif self._last_tracking_result is not None:
            # Reuse last tracking result — BoT-SORT's internal Kalman filter
            # already ran its prediction on the last update call. Calling it
            # again with empty detections every frame would cause it to drop
            # all tracks after track_buffer frames of zero matches.
            tracking_result = TrackingResult(
                frame_index=frame_data.frame_index,
                timestamp=frame_data.timestamp,
                tracks=list(self._last_tracking_result.tracks),
            )
        else:
            tracking_result = TrackingResult(
                frame_index=frame_data.frame_index,
                timestamp=frame_data.timestamp,
                tracks=[],
            )

        # Apply ID Alias Translation Layer
        for track in tracking_result.tracks:
            if track.track_id in self._track_aliases:
                track.track_id = self._track_aliases[track.track_id]

        t2 = time.perf_counter()

        # Apply Detection Stability Filter block removed to eliminate tracking artifacts

        # Apply Re-ID and ID mapping
        for track in tracking_result.tracks:
            track.is_selected = track.track_id in self._selected_ids


        # Update spatial registry and compute neighbors for ALL tracks
        expired_ids = self._registry.update(tracking_result.tracks, frame_data.frame_index, frame_data.timestamp)
        
        # Cleanup ReID memory and aliases
        if expired_ids:
            self._reid.remove_embeddings(expired_ids)
            keys_to_delete = [
                bot_id for bot_id, thaqib_id in self._track_aliases.items()
                if bot_id in expired_ids or thaqib_id in expired_ids
            ]
            for k in keys_to_delete:
                del self._track_aliases[k]

        t3 = time.perf_counter()
        
        self._neighbor_computer.compute_neighbors(self._registry, k=get_settings().neighbor_k)
        
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
                state = StudentState(
                    track_id=track.track_id,
                    center=track.center,
                    paper_center=track.paper_center,
                    bbox=track.bbox,
                    neighbors=spatial.neighbors if spatial else [],
                    neighbor_distances=spatial.neighbor_distances if spatial else {},
                    neighbor_papers=spatial.neighbor_papers if spatial else {},
                    surrounding_papers=spatial.surrounding_papers if spatial else [],
                    face_mesh=spatial.face_mesh if spatial else None,
                    is_cheating=spatial.is_cheating if spatial else False,
                )
                student_states.append(state)

            # 2. Extract face mesh in parallel, then evaluate cheating SYNCHRONOUSLY
            #    on the main thread (eliminates race condition with the collector loop).
            if frame_data.frame_index % 2 == 0:
                # Copy frame ONCE and share across all threads (not per-student)
                # With 13 students on 4K, this saves ~300MB of copies per cycle
                shared_frame = frame_data.frame.copy()

                futures = {}
                for state in student_states:
                    future = self._face_executor.submit(
                        self._process_student_parallel,
                        shared_frame,
                        state
                    )
                    futures[future] = state.track_id

                # Collect completed face mesh results (non-blocking: timeout=0)
                # Any futures not yet complete will be picked up next cycle.
                for future in list(futures.keys()):
                    if not future.done():
                        continue
                    orig_track_id = futures[future]
                    try:
                        _, result = future.result()
                        reg_state = self._registry.get(orig_track_id)
                        if reg_state is not None:
                            reg_state.face_mesh = result  # Explicitly allow None to clear stale meshes
                            
                        # ReID Integration — skip for locked IDs (already confirmed)
                        if result is not None and not self._tracker.is_locked(orig_track_id):
                            best_id = self._reid.match(result)
                            if best_id is not None and best_id != orig_track_id:
                                visible_ids = {t.track_id for t in tracking_result.tracks}
                                active_aliases = set(self._track_aliases.values())
                                
                                if best_id not in visible_ids and best_id not in active_aliases:
                                    logger.info(f"ReID match found! Aliasing tracker ID {orig_track_id} -> {best_id}")
                                    self._track_aliases[orig_track_id] = best_id

                            actual_id = self._track_aliases.get(orig_track_id, orig_track_id)
                            is_match = self._reid.register_embedding(actual_id, result)
                            self._tracker.verify_embedding_match(actual_id, is_match)
                    except Exception as e:
                        logger.debug(f"Face mesh parallel error: {e}")

            # 3. Evaluate cheating on the MAIN THREAD — no race condition
            for state in student_states:
                self._evaluate_cheating(state.track_id)

        # 4. Alert recording collector — runs AFTER cheating evaluation,
        #    so is_cheating and is_alert_recording are guaranteed stable.
        #
        # State machine:
        #   is_cheating=T, recording=F → START: snapshot pre-buffer, begin recording
        #   is_cheating=T, recording=T → DURING: keep appending frames, reset countdown
        #   is_cheating=F, recording=T → POST: countdown 60 frames (2s), then save
        for state in self._registry.get_all():
            if state.is_cheating and not state.is_alert_recording:
                # START recording: snapshot the pre-buffer (last ~2s)
                state.is_alert_recording = True
                state.recording_buffer = deque(self._global_frame_buffer, maxlen=300)
                state.frames_to_record = 60  # 2s post-buffer
            
            if not state.is_alert_recording:
                continue

            # Append current frame to recording buffer
            state.recording_buffer.append(frame_data.frame.copy())

            if state.is_cheating:
                # Still cheating — keep recording, reset post-cheating countdown
                state.frames_to_record = 60  # Will countdown only after cheating stops
            else:
                # Cheating stopped — count down the 2s post-buffer
                state.frames_to_record -= 1
                if state.frames_to_record <= 0:
                    # Take a snapshot of the buffer for the writer thread,
                    # then reset recording state immediately.
                    frames_snapshot = list(state.recording_buffer)
                    state.is_alert_recording = False
                    state.recording_buffer = deque(maxlen=300)
                    self._save_alert_video_async(
                        frames_snapshot, state.track_id, frame_data.timestamp
                    )

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

    def _evaluate_cheating(self, track_id: int) -> None:
        """
        Evaluate cheating rules **synchronously on the main thread**.
        
        This must run on the main thread to avoid race conditions with the
        alert recording collector that also reads/writes is_cheating and
        is_alert_recording.
        """
        state = self._registry.get(track_id)
        if not state or not state.face_mesh or not state.surrounding_papers:
            if state:
                state.suspicious_start_time = 0.0
                # Apply cooldown before clearing cheating flag
                if state.is_cheating:
                    state.cheating_cooldown -= 1
                    if state.cheating_cooldown <= 0:
                        state.is_cheating = False
            return

        # Use shared gaze computation (single source of truth with visualizer)
        from thaqib.video.gaze import compute_gaze_direction
        gaze_dir = compute_gaze_direction(state.face_mesh)
        if gaze_dir is None:
            state.suspicious_start_time = 0.0
            # Apply cooldown before clearing cheating flag
            if state.is_cheating:
                state.cheating_cooldown -= 1
                if state.cheating_cooldown <= 0:
                    state.is_cheating = False
            return

        lm2d = state.face_mesh.landmarks_2d
        def pt2d(idx):
            return np.array(lm2d[idx], dtype=float)

        # Check intersection with surrounding papers
        student_head_pos = pt2d(168)
        is_looking_at_paper = False
        
        settings = get_settings()
        threshold = math.cos(math.radians(settings.risk_angle_tolerance))

        for paper_pt in state.surrounding_papers:
            paper_vec = np.array(paper_pt) - student_head_pos
            dist = np.linalg.norm(paper_vec)
            if dist < 1e-6:
                continue
                
            paper_dir = paper_vec / dist
            dot_product = np.dot(gaze_dir, paper_dir)
            
            if dot_product > threshold:
                is_looking_at_paper = True
                break

        # Apply the suspicious duration rule from settings
        current_time = time.time()
        duration_threshold = settings.suspicious_duration_threshold
        
        if is_looking_at_paper:
            # Reset cooldown whenever student is looking at a paper
            state.cheating_cooldown = self._cheating_cooldown_frames
            
            if state.suspicious_start_time == 0.0:
                state.suspicious_start_time = current_time
            elif current_time - state.suspicious_start_time >= duration_threshold:
                if not state.is_cheating:
                    state.is_cheating = True
                    paper_source = "heuristic" if state.is_heuristic_paper else "YOLO"
                    logger.warning(
                        f"CHEATING DETECTED: Track {track_id} looking at neighbor paper "
                        f"for {duration_threshold}s (paper_source={paper_source})"
                    )
                    # Fire the on_alert callback
                    if self.on_alert is not None:
                        try:
                            self.on_alert(state)
                        except Exception as e:
                            logger.error(f"on_alert callback error: {e}")
        else:
            state.suspicious_start_time = 0.0
            # Use cooldown: don't immediately clear is_cheating.
            # This prevents oscillation from brief gaze breaks.
            if state.is_cheating:
                state.cheating_cooldown -= 1
                if state.cheating_cooldown <= 0:
                    state.is_cheating = False

    def _save_alert_video_async(self, frames: list[np.ndarray], track_id: int, timestamp: float) -> None:
        """Save alert video in a background thread. Receives an independent frames list."""
        def writer_task():
            import cv2
            from pathlib import Path
            from datetime import datetime
            
            if not frames:
                logger.warning(f"Alert video for track {track_id}: empty frame list, skipping.")
                return
            
            alerts_dir = Path("alerts")
            alerts_dir.mkdir(exist_ok=True)
            
            time_str = datetime.fromtimestamp(timestamp).strftime("%Y%m%d_%H%M%S")
            filename = alerts_dir / f"cheating_alert_track{track_id}_{time_str}.mp4"
            
            height, width = frames[0].shape[:2]
            
            # Try H.264 first, fallback to MPEG-4
            writer = None
            for codec in ['avc1', 'mp4v']:
                fourcc = cv2.VideoWriter_fourcc(*codec)
                writer = cv2.VideoWriter(str(filename), fourcc, 30.0, (width, height))
                if writer.isOpened():
                    logger.debug(f"Using codec '{codec}' for {filename}")
                    break
                writer.release()
                writer = None
            
            if writer is None or not writer.isOpened():
                logger.error(f"Failed to create video writer for {filename}")
                return
            
            frames_written = 0
            try:
                for f in frames:
                    writer.write(f)
                    frames_written += 1
                duration = frames_written / 30.0
                logger.info(
                    f"Saved cheating alert video: {filename} "
                    f"({duration:.1f}s, {frames_written} frames)"
                )
            except Exception as e:
                logger.error(f"Error saving alert video: {e}")
            finally:
                writer.release()
                
        threading.Thread(target=writer_task, daemon=True, name=f"AlertWriter-{track_id}").start()

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
