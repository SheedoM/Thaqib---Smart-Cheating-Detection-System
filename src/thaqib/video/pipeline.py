"""
Video processing pipeline orchestrator.

Coordinates camera, detection, and tracking.
"""

import logging
import time
import threading
import queue
import os
import cv2
from queue import Queue, Empty
from collections import deque
from multiprocessing import Pool
from multiprocessing import shared_memory as shm_mod
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
from thaqib.video.cheating_evaluator import CheatingEvaluator


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

        # Initialize components
        self._camera = CameraStream(source=source)
        self._detector = HumanDetector()
        self._tools_detector = ToolsDetector()
        self._tracker = ObjectTracker()
        self._registry = GlobalStudentRegistry()
        self._neighbor_computer = NeighborComputer()
        self._face_extractor = FaceMeshExtractor()
        self._reid = FaceReIdentifier()
        self._cheating_evaluator = CheatingEvaluator(self._registry)
        self._cheating_evaluator.on_alert = on_alert


        # Fix 1: Process pool for face mesh — true CPU parallelism
        settings = get_settings()
        face_workers = min(settings.face_mesh_workers, os.cpu_count() or 4)
        from thaqib.video.face_mesh_worker import init_worker, extract_in_worker
        self._extract_in_worker = extract_in_worker  # Store ref for submit calls
        self._face_pool = Pool(
            processes=face_workers,
            initializer=init_worker,
        )
        self._shm: shm_mod.SharedMemory | None = None  # Reusable shared memory block

        self._is_running = False
        
        self._frame_lock = threading.Lock()
        self._track_aliases: dict[int, int] = {}
        self._global_frame_buffer: deque[np.ndarray] = deque(maxlen=90)
        
        # Async Detection State
        self._detection_queue: Queue[tuple[DetectionResult, ToolsDetectionResult]] = Queue(maxsize=1)
        self._current_frame_data: FrameData | None = None
        self._detection_thread: threading.Thread | None = None
        self._last_detection_result: DetectionResult | None = None
        self._last_tools_result: ToolsDetectionResult | None = None
        self._last_tracking_result: TrackingResult | None = None

        self._selected_ids: set[int] = set()
        
        # Double-buffered face mesh jobs: submit on frame N, collect on frame N+2.
        # Fix 1: uses multiprocessing.AsyncResult instead of concurrent.futures.Future.
        self._pending_mp_jobs: list[tuple] = []  # [(AsyncResult, track_id), ...]
        
        # Archive recording: continuous video save to archive/ folder
        self._archive_writer: cv2.VideoWriter | None = None
        self._archive_path: str | None = None
        
        # Background archive writer thread (Fix 2: offload ~1-3ms/frame)
        self._archive_queue: queue.Queue = queue.Queue(maxsize=60)
        self._archive_thread: threading.Thread | None = None
        
        # Actual FPS tracking for correct video playback speed
        self._fps_tracker: deque[float] = deque(maxlen=60)
        self._actual_fps: float = 30.0
        
        # Track which track IDs we've already warned about recording cap
        # to avoid per-frame log spam.
        self._recording_skip_warned: set[int] = set()
        
        # Maximum height for recording buffers AND face mesh processing.
        # Frames above this height are downscaled to prevent OOM and speed up
        # MediaPipe inference. At 4K (3840x2160), each frame = 23.7MB.
        # Downscaling to 1080p: 5.9MB (75% savings), crops are ~4× smaller.
        self._recording_max_h: int = 1080
        
        # Scale factor for face mesh processing (computed once when first frame arrives)
        self._fm_scale: float = 1.0
        self._fm_scale_computed: bool = False

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
        
        # Start archive writer background thread (Fix 2)
        self._archive_thread = threading.Thread(
            target=self._archive_writer_loop,
            daemon=True,
            name="ArchiveWriter"
        )
        self._archive_thread.start()

        logger.info("Video pipeline started")
        return True

    def stop(self) -> None:
        """Stop the pipeline and flush any in-progress recordings."""
        logger.info("Stopping video pipeline...")
        self._is_running = False
        
        # Flush any in-progress alert recordings before shutdown
        # so the final cheating event in a video is never lost.
        for state in self._registry.get_all():
            if state.is_alert_recording and len(state.recording_buffer) > 0:
                frames_snapshot = list(state.recording_buffer)
                state.is_alert_recording = False
                self._save_alert_video_async(frames_snapshot, state.track_id, time.time())
        
        # Drain and close archive writer thread (Fix 2)
        if self._archive_thread is not None:
            self._archive_thread.join(timeout=3.0)
        if self._archive_writer is not None:
            self._archive_writer.release()
            self._archive_writer = None
            logger.info(f"Archive recording saved: {self._archive_path}")
        
        if self._detection_thread is not None:
            self._detection_thread.join(timeout=1.0)
        self._camera.close()
        self._face_extractor.close()
        
        # Fix 1: Clean up process pool and shared memory
        try:
            self._face_pool.terminate()
            self._face_pool.join()
        except Exception:
            pass
        if self._shm is not None:
            try:
                self._shm.unlink()
            except Exception:
                pass
            self._shm = None
        
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

        # Track actual FPS for correct video playback speed
        self._fps_tracker.append(time.time())
        if len(self._fps_tracker) >= 2:
            elapsed = self._fps_tracker[-1] - self._fps_tracker[0]
            if elapsed > 0:
                self._actual_fps = max(5.0, min(60.0, (len(self._fps_tracker) - 1) / elapsed))

        # Archive recording: write every raw frame to archive video
        self._write_archive_frame(frame_data)

        # Add to global frame ring buffer for alert recordings.
        # Only buffer when students are being monitored to save memory.
        # Downscale to 1080p before buffering to prevent OOM on 4K video.
        if self._selected_ids:
            self._global_frame_buffer.append(self._downscale_for_recording(frame_data.frame))

        
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
        
        # Cleanup ReID memory, face mesh cache, and aliases
        if expired_ids:
            self._reid.remove_embeddings(expired_ids)
            self._face_extractor.remove_cache(expired_ids)
            # Also prune tracker state to prevent memory leaks
            for eid in expired_ids:
                self._tracker._smoothed_bboxes.pop(eid, None)
                self._tracker._match_counts.pop(eid, None)
                self._tracker._locked_ids.discard(eid)
                self._tracker._track_labels.pop(eid, None)
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
            
            # Phone-to-student assignment: check if any phone bbox overlaps a student bbox.
            # If so, mark that student as using a phone (cheating).
            phone_tools = [t for t in tools_result.tools if t.label in ('phone', 'Using_phone', 'cell phone')]
            phone_assigned_students: set[int] = set()
            
            for phone in phone_tools:
                px1, py1, px2, py2 = phone.bbox
                phone_cx = (px1 + px2) // 2
                phone_cy = (py1 + py2) // 2
                
                # Find which student "owns" this phone (phone center inside student bbox)
                best_student = None
                best_dist = float('inf')
                for s in self._registry.get_all():
                    if not getattr(s, 'is_active', True):
                        continue
                    sx1, sy1, sx2, sy2 = s.bbox
                    # Expand bbox by 20% for robustness
                    bw, bh = sx2 - sx1, sy2 - sy1
                    ex1 = sx1 - int(bw * 0.1)
                    ey1 = sy1 - int(bh * 0.1)
                    ex2 = sx2 + int(bw * 0.1)
                    ey2 = sy2 + int(bh * 0.1)
                    
                    if ex1 <= phone_cx <= ex2 and ey1 <= phone_cy <= ey2:
                        dist = abs(phone_cx - s.center[0]) + abs(phone_cy - s.center[1])
                        if dist < best_dist:
                            best_dist = dist
                            best_student = s
                
                if best_student is not None:
                    best_student.is_using_phone = True
                    best_student.phone_bbox = phone.bbox
                    phone_assigned_students.add(best_student.track_id)
                    
                    # Phone = immediate cheating (no 2s delay needed)
                    if not best_student.is_cheating:
                        best_student.is_cheating = True
                        best_student.cheating_cooldown = 90  # ~3s at 30fps (must outlast recording)
                        logger.warning(
                            f"PHONE CHEATING: Track {best_student.track_id} "
                            f"using phone (conf={phone.confidence:.2f})"
                        )
                        # Fire alert callback (same mechanism as gaze cheating)
                        cb = getattr(self._cheating_evaluator, "on_alert", None)
                        if cb is not None:
                            try:
                                cb(best_student)
                            except Exception as e:
                                logger.error(f"on_alert callback error (phone): {e}")
                    else:
                        # Already cheating — keep refreshing cooldown
                        best_student.cheating_cooldown = 90
            
            # Clear phone flag for students no longer holding a phone,
            # BUT keep it sticky during an active alert recording so brief
            # occlusions don't cut the video short or change the cheat type.
            for s in self._registry.get_all():
                if s.track_id not in phone_assigned_students:
                    if not s.is_alert_recording:
                        s.is_using_phone = False
                        s.phone_bbox = None
        
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

        # 2. Double-buffered face mesh (runs even when selection changes
        #    to avoid orphaned jobs):
        #    - First, COLLECT any completed jobs from PREVIOUS cycle
        #    - Then, SUBMIT new jobs for this cycle
        
        # Collect ALL completed async results from previous cycle (Fix 1: multiprocessing)
        still_pending = []
        for async_result, orig_track_id in self._pending_mp_jobs:
            if async_result.ready():
                try:
                    tid, result_dict = async_result.get(timeout=0)
                    
                    # Convert plain dict back to FaceMeshResult (Fix 1)
                    result = None
                    if result_dict is not None:
                        hmat = (np.array(result_dict["hmat"]) 
                                if result_dict["hmat"] is not None else None)
                        result = FaceMeshResult(
                            landmarks_2d=result_dict["lm2d"],
                            landmarks_3d=result_dict["lm3d"],
                            bbox=result_dict["bbox"],
                            head_matrix=hmat,
                        )
                    
                    reg_state = self._registry.get(orig_track_id)
                    if reg_state is not None:
                        reg_state.face_mesh = result  # Allow None to clear stale meshes
                        
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
            else:
                still_pending.append((async_result, orig_track_id))
        self._pending_mp_jobs = still_pending

        # Cap pending jobs to prevent runaway accumulation.
        max_pending = (self._face_pool._processes or 4) * 3
        if len(self._pending_mp_jobs) > max_pending:
            self._pending_mp_jobs = self._pending_mp_jobs[-max_pending:]

        # Submit NEW jobs for this cycle (every frame — downscaled frames are cheap).
        if selected_tracks:
            # Compute face mesh scale factor once (original res → 1080p).
            if not self._fm_scale_computed:
                h = frame_data.frame.shape[0]
                if h > self._recording_max_h:
                    self._fm_scale = self._recording_max_h / h
                else:
                    self._fm_scale = 1.0
                self._fm_scale_computed = True
            
            # Downscale frame for face mesh
            fm_scale = self._fm_scale
            if fm_scale < 1.0:
                h, w = frame_data.frame.shape[:2]
                new_w = int(w * fm_scale)
                new_h = int(h * fm_scale)
                shared_frame = cv2.resize(frame_data.frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
            else:
                shared_frame = frame_data.frame
            
            # Fix 1: Copy frame to shared memory for zero-copy transfer to workers
            nbytes = shared_frame.nbytes
            if self._shm is None or self._shm.size < nbytes:
                if self._shm is not None:
                    try:
                        self._shm.unlink()
                    except Exception:
                        pass
                self._shm = shm_mod.SharedMemory(create=True, size=nbytes)
            buf = np.ndarray(shared_frame.shape, dtype=shared_frame.dtype, buffer=self._shm.buf)
            np.copyto(buf, shared_frame)
            
            # Submit ALL students via process pool.
            # Skip students that already have a pending job.
            pending_track_ids = {tid for _, tid in self._pending_mp_jobs}
            for state in student_states:
                if state.track_id in pending_track_ids:
                    continue
                args = (
                    self._shm.name,
                    shared_frame.shape,
                    str(shared_frame.dtype),
                    state.bbox,
                    state.track_id,
                    fm_scale,
                )
                async_result = self._face_pool.apply_async(
                    self._extract_in_worker, (args,)
                )
                self._pending_mp_jobs.append((async_result, state.track_id))

        # 3. Evaluate cheating on the MAIN THREAD — no race condition
        if selected_tracks:
            for state in student_states:
                self._cheating_evaluator.evaluate(state.track_id)

        # 4. Alert recording collector — runs AFTER cheating evaluation,
        #    so is_cheating and is_alert_recording are guaranteed stable.
        #
        # State machine:
        #   is_cheating=T, recording=F → START: snapshot pre-buffer, begin recording
        #   is_cheating=T, recording=T → DURING: keep appending frames, reset countdown
        #   is_cheating=F, recording=T → POST: countdown 60 frames (2s), then save
        for state in self._registry.get_all():
            if state.is_cheating and not state.is_alert_recording:
                # Cap concurrent recordings to 3 to prevent OOM.
                active_recordings = sum(
                    1 for s in self._registry.get_all() if s.is_alert_recording
                )
                if active_recordings >= 3:
                    # Only warn once per track to avoid per-frame log spam
                    if state.track_id not in self._recording_skip_warned:
                        logger.warning(
                            f"Skipping alert recording for track {state.track_id}: "
                            f"{active_recordings} recordings already active (max 3)"
                        )
                        self._recording_skip_warned.add(state.track_id)
                    continue
                
                # START recording: snapshot raw pre-buffer (last ~3s).
                # Pre-event frames are stored RAW (no annotation) because:
                #   1. Annotating 90 frames blocks the main thread for ~180ms
                #   2. Labels (CHEATER/VICTIM) weren't identified yet pre-event
                # Only during/after frames are annotated with cheating evidence.
                state.is_alert_recording = True
                state.recording_buffer = deque(self._global_frame_buffer, maxlen=300)
                state.frames_to_record = 60  # 2s post-buffer
                self._recording_skip_warned.discard(state.track_id)  # Reset warn on successful start
            
            if not state.is_alert_recording:
                continue

            # Append current raw frame + track ID to recording buffer.
            # Fix 4: defer _render_alert_frame to the writer thread (~2ms saved).
            # Downscale to 1080p first to save memory.
            small_frame = self._downscale_for_recording(frame_data.frame)
            state.recording_buffer.append((small_frame, state.track_id))

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
                    
                    # Determine cheat type BEFORE resetting state
                    cheat_type = "phone" if state.is_using_phone else "gaze"
                    
                    # Fully reset cheating state — the event is captured.
                    # Student returns to normal (no more red box).
                    state.is_cheating = False
                    state.cheating_cooldown = 0
                    state.suspicious_start_time = 0.0
                    state.cheating_target_paper = None
                    state.cheating_target_neighbor = None
                    state.is_using_phone = False
                    state.phone_bbox = None
                    
                    self._save_alert_video_async(
                        frames_snapshot, state.track_id, frame_data.timestamp,
                        cheat_type=cheat_type
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

    # _process_student_parallel removed (Fix 1) — replaced by
    # face_mesh_worker.extract_in_worker running in child processes.

    def _downscale_for_recording(self, frame: np.ndarray) -> np.ndarray:
        """
        Downscale a frame to at most _recording_max_h (1080p) for recording buffers.
        
        At 4K (3840×2160), each frame is 23.7MB. With 90+300 frames per buffer,
        that's ~9GB per buffer. Downscaling to 1080p reduces this to ~2.3GB (75% savings).
        Already-small frames pass through unchanged.
        """
        h, w = frame.shape[:2]
        if h <= self._recording_max_h:
            return frame.copy()
        scale = self._recording_max_h / h
        new_w = int(w * scale)
        return cv2.resize(frame, (new_w, self._recording_max_h), interpolation=cv2.INTER_AREA)

    def _render_alert_frame(self, raw_frame: np.ndarray, cheater_track_id: int) -> np.ndarray:
        """
        Render an annotated frame for alert video recording.
        
        Expects a frame that's already been downscaled by _downscale_for_recording.
        All bbox coordinates are scaled to match the downscaled resolution.
        
        Draws:
          - RED thick bbox + label on the cheater
          - YELLOW thick bbox + label on the victim (student being copied from)
          - GREEN circle on the actual paper location (only if YOLO-detected)
          - RED bbox on phone (if phone cheating)
          - Gaze arrow from cheater to paper
        """
        frame = raw_frame.copy()
        cheater = self._registry.get(cheater_track_id)
        if cheater is None:
            return frame
        
        # Compute scale factor: registry bboxes are in original resolution,
        # but the frame may have been downscaled (e.g., 4K → 1080p).
        frame_h = frame.shape[0]
        # Use the camera's cached original resolution (race-free public property)
        orig_h = self._camera.original_height or frame_h
        scale = frame_h / orig_h if orig_h > 0 else 1.0
        
        def sc(val: int) -> int:
            """Scale a coordinate from original to downscaled resolution."""
            return int(val * scale)
        
        def sc_bbox(bbox: tuple) -> tuple[int, int, int, int]:
            return (sc(bbox[0]), sc(bbox[1]), sc(bbox[2]), sc(bbox[3]))
        
        def sc_pt(pt: tuple) -> tuple[int, int]:
            return (sc(pt[0]), sc(pt[1]))
        
        # Draw the cheater in RED with full body bbox
        cx1, cy1, cx2, cy2 = sc_bbox(cheater.bbox)
        cv2.rectangle(frame, (cx1, cy1), (cx2, cy2), (0, 0, 255), 3)
        
        # Label depends on cheating type
        if cheater.is_using_phone:
            cheat_label = f"PHONE CHEATER ID:{cheater_track_id}"
        else:
            cheat_label = f"CHEATER ID:{cheater_track_id}"
        
        # Draw label with background for readability
        (tw, th), _ = cv2.getTextSize(cheat_label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(frame, (cx1, cy1 - th - 8), (cx1 + tw, cy1), (0, 0, 255), -1)
        cv2.putText(frame, cheat_label,
                    (cx1, cy1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (255, 255, 255), 2, cv2.LINE_AA)
        
        # Draw phone bbox in bright RED if phone cheating
        if cheater.is_using_phone and cheater.phone_bbox is not None:
            px1, py1, px2, py2 = sc_bbox(cheater.phone_bbox)
            cv2.rectangle(frame, (px1, py1), (px2, py2), (0, 0, 255), 3)
            cv2.putText(frame, "PHONE", (px1, py1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2, cv2.LINE_AA)
        
        # Draw the victim in YELLOW (if known — paper-copying cheating)
        victim_id = cheater.cheating_target_neighbor
        if victim_id is not None:
            victim = self._registry.get(victim_id)
            if victim is not None:
                vx1, vy1, vx2, vy2 = sc_bbox(victim.bbox)
                cv2.rectangle(frame, (vx1, vy1), (vx2, vy2), (0, 255, 255), 3)
                victim_label = f"VICTIM ID:{victim_id}"
                (vw, vh), _ = cv2.getTextSize(victim_label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                cv2.rectangle(frame, (vx1, vy1 - vh - 8), (vx1 + vw, vy1), (0, 255, 255), -1)
                cv2.putText(frame, victim_label,
                            (vx1, vy1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                            (0, 0, 0), 2, cv2.LINE_AA)
        
        # Draw the paper location — ONLY when YOLO-detected (not heuristic guesses)
        paper_pt = cheater.cheating_target_paper
        if paper_pt is not None and not cheater.is_heuristic_paper:
            px, py = sc_pt(paper_pt)
            cv2.circle(frame, (px, py), 18, (0, 255, 0), 3, cv2.LINE_AA)
            cv2.circle(frame, (px, py), 6, (0, 255, 0), -1, cv2.LINE_AA)
            cv2.putText(frame, "PAPER", (px - 25, py - 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2, cv2.LINE_AA)
            
            # Draw gaze line from cheater center to paper
            cv2.line(frame, sc_pt(cheater.center), (px, py), (0, 0, 255), 2, cv2.LINE_AA)
        
        # Draw status banner at top
        banner_h = 40
        cv2.rectangle(frame, (0, 0), (frame.shape[1], banner_h), (0, 0, 180), -1)
        if cheater.is_using_phone:
            status_text = f"PHONE ALERT - Student {cheater_track_id} using phone"
        else:
            status_text = f"CHEATING ALERT - Student {cheater_track_id}"
            if victim_id is not None:
                status_text += f" copying from Student {victim_id}"
        cv2.putText(frame, status_text, (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        
        return frame

    def _archive_writer_loop(self) -> None:
        """Background thread: drain archive queue and write frames to disk.
        
        Fix 2: Moves the ~1-3ms cv2.VideoWriter.write() call off the main
        thread. The loop runs until _is_running is False AND the queue is empty,
        ensuring all buffered frames are flushed on shutdown.
        """
        while self._is_running or not self._archive_queue.empty():
            try:
                frame = self._archive_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if self._archive_writer is not None:
                self._archive_writer.write(frame)

    def _write_archive_frame(self, frame_data: FrameData) -> None:
        """
        Queue a frame for archive writing (non-blocking).
        Creates the archive writer on first call (one-time cost on main thread).
        """
        if self._archive_writer is None:
            from pathlib import Path
            from datetime import datetime
            
            archive_dir = Path("archive")
            archive_dir.mkdir(exist_ok=True)
            
            time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            h, w = frame_data.frame.shape[:2]
            
            # Use actual measured FPS for correct playback speed.
            archive_fps = max(10.0, self._actual_fps)
            
            # Try codecs in order of reliability
            for codec, ext in [('XVID', '.avi'), ('mp4v', '.mp4'), ('MJPG', '.avi')]:
                filepath = archive_dir / f"archive_{time_str}{ext}"
                fourcc = cv2.VideoWriter_fourcc(*codec)
                writer = cv2.VideoWriter(str(filepath), fourcc, archive_fps, (w, h))
                if writer.isOpened():
                    self._archive_writer = writer
                    self._archive_path = str(filepath)
                    logger.info(f"Archive recording started: {filepath} (codec={codec})")
                    break
                writer.release()
            else:
                logger.error("Failed to create archive writer — all codecs failed")
                return
        
        # Non-blocking enqueue — drop frame if queue full rather than
        # blocking the main thread (Fix 2)
        try:
            self._archive_queue.put_nowait(frame_data.frame)
        except queue.Full:
            pass  # Drop frame rather than block main thread

    def _save_alert_video_async(
        self, frames: list[np.ndarray], track_id: int, timestamp: float,
        cheat_type: str = "gaze"
    ) -> None:
        """Save alert video in a background thread. Receives an independent frames list."""
        actual_fps = self._actual_fps  # Capture current FPS for the writer thread
        
        def writer_task():
            from pathlib import Path
            from datetime import datetime
            
            if not frames:
                logger.warning(f"Alert video for track {track_id}: empty frame list, skipping.")
                return
            
            alerts_dir = Path("alerts")
            alerts_dir.mkdir(exist_ok=True)
            
            time_str = datetime.fromtimestamp(timestamp).strftime("%Y%m%d_%H%M%S")
            
            height, width = None, None
            # Determine frame dimensions from first valid element.
            # Buffer is mixed: raw ndarray (pre-event) and (frame, tid) tuples.
            for item in frames:
                if isinstance(item, tuple):
                    height, width = item[0].shape[:2]
                    break
                else:
                    height, width = item.shape[:2]
                    break
            
            if height is None:
                logger.warning(f"Alert video for track {track_id}: no valid frames, skipping.")
                return
            
            # Differentiate filenames by cheating type:
            #   phone_alert_track3_20260417_053000.avi
            #   gaze_alert_track3_20260417_053000.avi
            prefix = "phone_alert" if cheat_type == "phone" else "gaze_alert"
            
            # Codec fallback chain — prefer browser-friendly formats first:
            #   1. mp4v + .mp4  (most likely to play in browser <video>)
            #   2. XVID + .avi  (universally available, no external DLLs)
            #   3. MJPG + .avi  (always works, larger files)
            codec_options = [
                ('mp4v', '.mp4'),
                ('XVID', '.avi'),
                ('MJPG', '.avi'),
            ]
            
            writer = None
            filename = None
            for codec, ext in codec_options:
                filename = alerts_dir / f"{prefix}_track{track_id}_{time_str}{ext}"
                fourcc = cv2.VideoWriter_fourcc(*codec)
                writer = cv2.VideoWriter(str(filename), fourcc, actual_fps, (width, height))
                if writer.isOpened():
                    logger.info(f"Using codec '{codec}' for {filename}")
                    break
                writer.release()
                writer = None
            
            if writer is None or not writer.isOpened():
                logger.error(f"Failed to create video writer — all codecs failed for track {track_id}")
                return
            
            frames_written = 0
            try:
                for item in frames:
                    # Fix 4: pre-event frames are raw ndarray, during/post are
                    # (frame, track_id) tuples that need annotation.
                    if isinstance(item, tuple):
                        raw_frame, tid = item
                        annotated = self._render_alert_frame(raw_frame, tid)
                        writer.write(annotated)
                    else:
                        writer.write(item)
                    frames_written += 1
                duration = frames_written / actual_fps
                logger.info(
                    f"Saved {cheat_type} alert video: {filename} "
                    f"({duration:.1f}s, {frames_written} frames, {actual_fps:.0f}fps)"
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
