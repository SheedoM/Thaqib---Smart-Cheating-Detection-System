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
# Import concurrent.futures to manage bounded thread pools for async alert videos.
from concurrent.futures import ThreadPoolExecutor, Future
import concurrent.futures
from dataclasses import dataclass, field
from typing import Callable, Generator

from thaqib.video.reid import FaceReIdentifier

import numpy as np

from thaqib.config import get_settings
from thaqib.video.camera import CameraStream, FrameData
from thaqib.video.detector import HumanDetector, DetectionResult
from thaqib.video.tracker import ObjectTracker, TrackingResult, TrackedObject
from thaqib.video.registry import GlobalStudentRegistry, StudentSpatialState, _MAX_RECORDING_FRAMES
from thaqib.video.timestamps import draw_timestamp_overlay
from thaqib.video.neighbors import NeighborComputer
from thaqib.video.face_mesh import FaceMeshResult
from thaqib.video.tools_detector import ToolsDetector, ToolsDetectionResult
from thaqib.video.cheating_evaluator import CheatingEvaluator
from thaqib.video.video_logger import get_video_logger
from thaqib.video.jpeg_buffer import JPEGFrame, encode_frame, decode_frame

# Run face mesh every N frames per student to prevent executor backlog.
# At 30 FPS with N=3: ~10 updates/sec per student — sufficient for gaze accuracy.
FACE_MESH_INTERVAL: int = 3


class ConstantVelocityExtrapolator:
    """Extrapolates bounding boxes on intermediate frames using historical velocity."""
    def __init__(self):
        self.history = {}  # track_id -> (last_bbox, last_timestamp)
        self.velocity = {} # track_id -> (vx_cx, vy_cy, v_w, v_h)

    def update(self, track_id: int, bbox: tuple[int, int, int, int], timestamp: float):
        x1, y1, x2, y2 = bbox
        w, h = x2 - x1, y2 - y1
        cx, cy = x1 + w / 2.0, y1 + h / 2.0

        if track_id in self.history:
            prev_bbox, prev_ts = self.history[track_id]
            px1, py1, px2, py2 = prev_bbox
            pw, ph = px2 - px1, py2 - py1
            pcx, pcy = px1 + pw / 2.0, py1 + ph / 2.0

            dt = timestamp - prev_ts
            if dt > 0.0:
                # Calculate velocity (pixels per second)
                self.velocity[track_id] = (
                    (cx - pcx) / dt,
                    (cy - pcy) / dt,
                    (w - pw) / dt,
                    (h - ph) / dt
                )
        else:
            self.velocity[track_id] = (0.0, 0.0, 0.0, 0.0)

        self.history[track_id] = (bbox, timestamp)

    def extrapolate(self, track_id: int, target_timestamp: float) -> tuple[int, int, int, int] | None:
        if track_id not in self.history:
            return None

        bbox, last_ts = self.history[track_id]
        vx_cx, vy_cy, v_w, v_h = self.velocity.get(track_id, (0.0, 0.0, 0.0, 0.0))
        dt = target_timestamp - last_ts

        if dt <= 0.0:
            return bbox

        x1, y1, x2, y2 = bbox
        w, h = x2 - x1, y2 - y1
        cx, cy = x1 + w / 2.0, y1 + h / 2.0

        new_cx = cx + vx_cx * dt
        new_cy = cy + vy_cy * dt
        new_w = w + v_w * dt
        new_h = h + v_h * dt

        nx1 = int(new_cx - new_w / 2.0)
        ny1 = int(new_cy - new_h / 2.0)
        nx2 = int(new_cx + new_w / 2.0)
        ny2 = int(new_cy + new_h / 2.0)

        return (nx1, ny1, nx2, ny2)

    def prune(self, active_ids: set[int]):
        """Prunes historical state for lost tracks."""
        expired = set(self.history.keys()) - active_ids
        for eid in expired:
            self.history.pop(eid, None)
            self.velocity.pop(eid, None)


logger = logging.getLogger(__name__)



@dataclass
class AlertFrame:
    """Normalized buffer entry for alert recordings.

    Replaces ad-hoc (frame, track_id) / (frame, phone_bboxes) tuples
    so the writer thread can rely on typed field access instead of
    fragile positional unpacking.
    """

    frame: np.ndarray
    frame_index: int = 0
    # track_id is None for pre-event (global) frames — not yet confirmed cheating.
    # phone_bboxes is [] for pre-event frames — phone not yet visible.
    track_id: int | None = None
    phone_bboxes: list = field(default_factory=list)
    student_bbox: tuple[int, int, int, int] | None = None
    student_center: tuple[int, int] | None = None


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
    tracking_result: TrackingResult
    tools_result: ToolsDetectionResult | None = None
    registry: GlobalStudentRegistry | None = None
    student_states: list[StudentState] = field(default_factory=list)
    processing_time_ms: float = 0.0
    archive_mode: str = "raw"  # Current archive recording mode ('raw' or 'annotated')
    video_quality: int = 75    # Current video quality (50=LOW / 75=MED / 90=HIGH)
    processing_res: str = "NATIVE"  # Current processing resolution label
    # Annotated frame rendered once per cycle — reused by archive and display.
    # None when no visualizer is attached (e.g. headless/testing mode).
    annotated_frame: np.ndarray | None = None

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
    2. Periodic human detection (YOLO)
    3. Continuous tracking (BoT-SORT)

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
        camera_id: str = "cam0",
        composer = None,
        clock = None,
    ):
        """
        Initialize video pipeline.

        Args:
            source: Camera source (webcam index, RTSP URL, or video file).
            detection_interval: Seconds between full detection runs.
            on_alert: Callback function when suspicious behavior detected.
        """
        settings = get_settings()
        self._settings = settings  # Keep reference for alert writers
        import torch
        if not hasattr(self._settings, "device"):
            object.__setattr__(self._settings, "device", "cuda" if torch.cuda.is_available() else "cpu")
        if (self._settings.detection_imgsz > 640
                and str(self._settings.device).lower() == 'cpu'):
            logger.warning(
                "DETECTION_IMGSZ=%d on CPU may exceed detection interval "
                "(%ds). Consider reducing to 640 for real-time performance.",
                self._settings.detection_imgsz,
                self._settings.detection_interval,
            )

        self.detection_interval = detection_interval or settings.detection_interval

        self._camera_id = camera_id
        self._composer = composer
        self._camera = CameraStream(
            source=source,
            clock=clock
        )
        self._detector = HumanDetector()
        self._tools_detector = ToolsDetector()
        self._tracker = ObjectTracker()
        self._registry = GlobalStudentRegistry()
        self._neighbor_computer = NeighborComputer()
        self._reid = FaceReIdentifier()
        self._cheating_evaluator = CheatingEvaluator(self._registry, clock=clock)
        self._cheating_evaluator.on_alert = on_alert


        # Thread pool for face mesh — created lazily in start().
        # Uses threads instead of processes because Python's multiprocessing.Pool
        # has an internal _handle_results thread that never gets GIL time during
        # the pipeline's tight frame loop, causing ready() to never return True.
        # MediaPipe inference is C++ and releases the GIL, so threads achieve
        # real parallelism without the spawn/shared-memory overhead.
        self._face_executor: ThreadPoolExecutor | None = None
        self._fm_thread_local = None  # threading.local for per-thread FaceLandmarker
        # Shared result cache: track_id → (timestamp, FaceMeshResult)
        # When MediaPipe fails on a frame (occlusion/blur), we return the last
        # good result if it is less than 0.3 s old instead of returning None.
        # A lock protects concurrent writes from multiple worker threads.
        self._fm_cache: dict[int, tuple[float, "FaceMeshResult"]] = {}
        self._fm_cache_lock = threading.Lock()

        self._is_running = False

        # Injected visualizer for single-pass rendering (see set_visualizer()).
        # None by default so headless/test usage is unaffected.
        self._visualizer = None

        # Stores alias mappings for tracks (from tracker ID to ReID main ID)
        self._track_aliases: dict[int, int] = {}
        self._alias_lock = threading.Lock()
        self._global_frame_buffer: deque[tuple[np.ndarray, None]] = deque(maxlen=90)
        
        self._buffer_lock = threading.Lock()
        # _frame_lock: guards _current_frame_data written by run() and read by _detection_worker.
        self._frame_lock = threading.Lock()
        self._phone_alert_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="PhoneAlertWriter"
        )
        self._gaze_alert_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="GazeAlertWriter"
        )
        
        # Async Detection State
        self._detection_queue: Queue[tuple[DetectionResult, ToolsDetectionResult]] = Queue(maxsize=1)
        self._current_frame_data: FrameData | None = None
        self._detection_thread: threading.Thread | None = None
        self._last_detection_result: DetectionResult | None = None
        self._last_tools_result: ToolsDetectionResult | None = None
        self._last_tracking_result: TrackingResult | None = None

        self._selected_ids: set[int] = set()
        self._auto_select_enabled: bool = True
        self._deselected_ids: set[int] = set()
        
        # Initialize last logged track IDs to prevent all active students showing as new.
        self._last_logged_track_ids: set[int] = set()
        
        # Face mesh futures: [(Future, track_id), ...]
        self._pending_fm_futures: list[tuple[Future, int]] = []
        self._fm_rr_idx: int = 0  # Round-robin index for face mesh job submission
        
        # Archive recording: continuous video save to archive/ folder
        self._archive_writer: cv2.VideoWriter | None = None
        self._archive_path: str | None = None
        self._archive_size: tuple[int, int] | None = None  # (width, height) of archive writer
        
        # Archive mode: 'raw' = original camera feed, 'annotated' = with overlays
        self._archive_annotated: bool = (settings.archive_mode == "annotated")
        logger.info(f"Archive mode: {'annotated (with overlays)' if self._archive_annotated else 'raw (original video)'}")
        
        # Background archive writer thread (offloads 1-3ms/frame)
        self._archive_queue: queue.Queue = queue.Queue(maxsize=60)
        self._archive_thread: threading.Thread | None = None
        
        # Track which track IDs we've already warned about recording cap
        # to avoid per-frame log spam.
        self._recording_skip_warned: set[int] = set()

        # Scale factor for face mesh processing only (NOT for recordings).
        # MediaPipe at 4K takes 300-675ms; downscaling to 1080p brings it to ~10ms.
        # Recordings and display remain at full native resolution.
        self._recording_max_h: int = 1080  # Used only for face mesh resize target
        self._fm_scale: float = 1.0
        self._fm_scale_computed: bool = False

        # Maps paper center (x, y) → full YOLO bbox (x1, y1, x2, y2).
        # Updated every frame from tools_result so _render_alert_frame
        # can draw a precise yellow box around the paper.
        self._paper_bboxes: dict[tuple[int, int], tuple[int, int, int, int]] = {}

        # Phone alert recording — independent of student tracking.
        # A phone anywhere in frame triggers its own 2s+event+2s clip.
        self._phone_detected: bool = False
        self._phone_is_recording: bool = False
        self._phone_recording_buffer: deque = deque(maxlen=1800)
        self._phone_frames_to_record: int = 0
        self._phone_current_bboxes: list = []  # phone bboxes in the current frame

        # Runtime video quality — cycles LOW/MED/HIGH via V key.
        # 50 = LOW  (smallest files), 75 = MED (default), 90 = HIGH (best quality)
        self._video_quality: int = settings.video_quality
        self._quality_presets: tuple[int, ...] = (50, 75, 90)

        # Runtime processing resolution — cycles NATIVE/1080p/720p via G key.
        # Downscales camera frames before ALL processing to improve FPS on 4K.
        # 0 = native (no resize).
        self._processing_max_height: int = 0
        self._processing_presets: tuple[tuple[str, int], ...] = (
            ("NATIVE", 0),
            ("1080p", 1080),
            ("720p", 720),
        )
        self._processing_preset_idx: int = 0

        # Diagnostic video logger (non-blocking, background writer thread).
        self._vlog = get_video_logger()
        self._extrapolator = ConstantVelocityExtrapolator()

    def toggle_video_quality(self) -> None:
        """Cycle through LOW/MED/HIGH video quality presets."""
        idx = self._quality_presets.index(self._video_quality)
        self._video_quality = self._quality_presets[(idx + 1) % len(self._quality_presets)]
        logger.info(f"Video quality changed to: {self._video_quality}")

    def toggle_processing_resolution(self) -> str:
        """Cycle through NATIVE/1080p/720p processing resolution presets.

        Returns the new preset label.
        """
        self._processing_preset_idx = (
            self._processing_preset_idx + 1
        ) % len(self._processing_presets)
        label, max_h = self._processing_presets[self._processing_preset_idx]
        self._processing_max_height = max_h
        # Force recalculation of face mesh scale factor for the new frame size.
        # Without this reset, landmarks could be computed at the wrong scale
        # after switching resolution, causing face overlays to appear misaligned.
        self._fm_scale_computed = False
        logger.info(f"Processing resolution changed to: {label} (max_height={max_h})")
        return label

    # Pass only track_id as tracking_result is unused after using the live registry to prevent stale ReID blockages.
    def _make_fm_callback(self, track_id: int) -> "Callable":
        """Return a done-callback for the face mesh future.

        Old pattern (restored): evaluate cheating IMMEDIATELY when the face
        mesh result arrives in the worker thread, instead of deferring to the
        next main-thread frame.  This reduces latency by up to one full frame
        interval and matches the reference implementation.

        Thread-safety note: the callback runs on the ThreadPoolExecutor thread,
        not the main thread.  We write only to reg_state.face_mesh (atomic
        assignment in CPython) and call CheatingEvaluator which guards its own
        state with time.time() comparisons — acceptable benign race.
        """
        def callback(future):
            try:
                result = future.result()

                reg_state = self._registry.get(track_id)
                if reg_state is None:
                    return

                # Write face mesh result (atomic in CPython — no lock needed)
                reg_state.face_mesh = result

                if result is not None:
                    # ReID — skip for permanently locked IDs
                    if not self._tracker.is_locked(track_id):
                        best_id = self._reid.match(result)
                        if best_id is not None and best_id != track_id:
                            # Retrieve active track IDs from the live registry to prevent stale tracks from blocking ReID.
                            # use live registry instead of stale closure — fixes V-L-1
                            visible_ids = {s.track_id for s in self._registry.get_all()
                                           if s.is_active}
                            with self._alias_lock:
                                active_aliases = set(self._track_aliases.values())
                            if best_id not in visible_ids and best_id not in active_aliases:
                                logger.info(
                                    f"ReID match found! Aliasing tracker ID {track_id} -> {best_id}"
                                )
                                with self._alias_lock:
                                    self._track_aliases[track_id] = best_id

                        with self._alias_lock:
                            actual_id = self._track_aliases.get(track_id, track_id)
                        is_match = self._reid.register_embedding(actual_id, result)
                        self._tracker.verify_embedding_match(actual_id, is_match)

                    # Avoid evaluating cheating on worker threads to prevent race conditions on student state fields.

            except Exception as exc:
                logger.warning(f"FM callback error (track {track_id}): {exc}")

        return callback

    def _get_fm_cached(self, track_id: int) -> "FaceMeshResult | None":

        """Return the cached FaceMeshResult for track_id if it is < 0.3 s old."""
        with self._fm_cache_lock:
            entry = self._fm_cache.get(track_id)
        if entry is None:
            return None
        cache_time, cached = entry
        if time.time() - cache_time <= 0.3:
            return cached
        return None

    def _fm_thread_infer(
        self, frame: np.ndarray, bbox: tuple, fm_scale: float, track_id: int
    ) -> "FaceMeshResult | None":
        """Run face mesh inference in a worker thread.

        Each thread lazily initializes its own FaceLandmarker in IMAGE mode
        via threading.local() so there is no lock contention.  MediaPipe's
        C++ inference releases the GIL, giving true parallelism.

        On detection failure the last cached result (< 0.3 s) is returned so
        brief occlusions / bad frames don't cause the overlay to blink off.

        Returns a FaceMeshResult or None if no face is detected.
        """
        import mediapipe as mp
        from mediapipe.tasks.python import vision
        from mediapipe.tasks.python.core import base_options as mp_base_options
        from pathlib import Path

        tl = self._fm_thread_local
        if not hasattr(tl, "landmarker"):
            model_path = Path(__file__).parent.parent.parent.parent / "models" / "face_landmarker.task"
            opts = vision.FaceLandmarkerOptions(
                base_options=mp_base_options.BaseOptions(
                    model_asset_path=str(model_path)
                ),
                running_mode=vision.RunningMode.IMAGE,
                num_faces=1,
                min_face_detection_confidence=0.80,
                min_face_presence_confidence=0.80,
                min_tracking_confidence=0.80,
                output_face_blendshapes=False,
                output_facial_transformation_matrixes=True,
            )
            tl.landmarker = vision.FaceLandmarker.create_from_options(opts)

        # Scale bbox to match the (potentially downscaled) frame
        x1, y1, x2, y2 = [int(v * fm_scale) for v in bbox]

        # Clamp to frame bounds (use full bbox — old working approach)
        fh, fw = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(fw, x2), min(fh, y2)

        if x2 <= x1 or y2 <= y1:
            return self._get_fm_cached(track_id)

        crop = frame[y1:y2, x1:x2]
        if crop.shape[0] < 40 or crop.shape[1] < 40:
            return self._get_fm_cached(track_id)

        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        try:
            det = tl.landmarker.detect(mp_img)
        except Exception as exc:
            logger.debug(f"FaceLandmarker inference error: {exc}")
            return self._get_fm_cached(track_id)

        if not det.face_landmarks:
            # Detection failed — return cached result if fresh (< 0.3 s)
            return self._get_fm_cached(track_id)

        raw = det.face_landmarks[0]
        ch, cw = crop.shape[:2]

        lm = np.array([[l.x, l.y, l.z] for l in raw], dtype=float)
        px_py = (lm[:, :2] * [cw, ch] + [x1, y1]).astype(int)

        inv = 1.0 / fm_scale
        lm2d = [(int(x * inv), int(y * inv)) for x, y in px_py]
        lm3d = [tuple(row) for row in lm]

        hmat = None
        if det.facial_transformation_matrixes:
            hmat = np.array(
                det.facial_transformation_matrixes[0].data
            ).reshape(4, 4)

        bbox_orig = (int(x1 * inv), int(y1 * inv), int(x2 * inv), int(y2 * inv))

        result = FaceMeshResult(
            landmarks_2d=lm2d,
            landmarks_3d=lm3d,
            bbox=bbox_orig,
            head_matrix=hmat,
        )

        # Save successful result to cache for use on future failures
        with self._fm_cache_lock:
            self._fm_cache[track_id] = (time.time(), result)

        return result

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
                    
                    try:
                        # Wrap YOLO detections to prevent exceptions in worker threads from silencing pipeline.
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
                    except Exception as exc:
                        logger.error("Detection worker exception — skipping frame: %s", exc)
                        time.sleep(1.0)
                        continue
                    
                    last_detect_time = time.time()
                    
                    # Update queue (drop old if present)
                    try:
                        while not self._detection_queue.empty():
                            self._detection_queue.get_nowait()
                    except Empty:
                        pass
                    
                    try:
                        self._detection_queue.put_nowait((detection_result, tools_result))
                    except Exception as e:
                        logger.debug("Detection queue put failed (queue full?): %s", e)
            
            time.sleep(0.01)  # Yield CPU

    def preload_models(self) -> None:
        """Pre-load YOLO and tools detector weights before pipeline starts."""
        self._detector.load()
        if self._tools_detector:
            self._tools_detector.load()

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

        # Log all configuration at startup so every run is fully reproducible
        self._vlog.log_startup(
            source=self._camera.source,
            detection_interval=self.detection_interval,
            archive_mode=self.archive_mode,
            face_workers=getattr(settings, "face_mesh_workers", 4),
            video_quality=self._video_quality,
            yolo_model=settings.yolo_model,
            tools_model=settings.tools_model,
            detection_confidence=settings.detection_confidence,
            tools_confidence=settings.tools_confidence,
            detection_imgsz=settings.detection_imgsz,
            neighbor_k=settings.neighbor_k,
            risk_angle_tolerance=settings.risk_angle_tolerance,
            suspicious_duration_threshold=settings.suspicious_duration_threshold,
            reid_match_threshold=settings.reid_match_threshold,
        )

        if not self._camera.open():
            logger.error("Failed to open camera")
            return False

        self._detector.load()
        self._tools_detector.load()

        self._is_running = True
        
        # Capture measured FPS from the device — used to derive post-event buffer
        # frame counts so they are correct for non-30-FPS sources.
        self._camera_fps: float = self._camera.actual_fps
        self._post_buffer_frames: int = max(1, round(self._camera_fps * 2))  # 2-second post-buffer
        self._global_frame_buffer = deque(self._global_frame_buffer, maxlen=self._post_buffer_frames)
        logger.info(f"Camera FPS: {self._camera_fps:.1f} — post-buffer = {self._post_buffer_frames} frames")

        # Create thread pool for face mesh — threads share address space so
        # no shared memory is needed.  Each thread lazily initializes its own
        # FaceLandmarker via threading.local (see _fm_thread_infer).
        settings = get_settings()
        face_workers = min(settings.face_mesh_workers, os.cpu_count() or 4)
        self._fm_thread_local = threading.local()
        self._fm_num_workers = face_workers
        try:
            self._face_executor = ThreadPoolExecutor(
                max_workers=face_workers,
                thread_name_prefix="FaceMesh",
            )
            logger.info(f"Face-mesh thread pool created with {face_workers} workers")
        except Exception as e:
            logger.error(f"Failed to create face-mesh thread pool: {e}. Face mesh disabled.")
            self._face_executor = None

        self._vlog.log_camera_open(
            camera_fps=self._camera_fps,
            post_buffer_frames=self._post_buffer_frames,
            face_workers=face_workers,
        )

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
                cheat_ctx = {
                    'target_paper': state.cheating_target_paper,
                    'target_neighbor': state.cheating_target_neighbor,
                    'paper_bbox': self._paper_bboxes.get(
                        state.cheating_target_paper
                    ) if state.cheating_target_paper else None,
                    'is_heuristic_paper': state.is_heuristic_paper,
                    'is_using_phone': getattr(state, 'is_using_phone', False),
                    'phone_bbox': getattr(state, 'phone_bbox', None),
                    'suspicious_start_time': getattr(state, 'suspicious_start_time', 0.0),
                }
                self._save_alert_video_async(
                    frames_snapshot, state.track_id, time.time(),
                    cheat_ctx=cheat_ctx
                )
            state.recording_buffer.clear()  # Free memory immediately

        # Flush phone recording if active
        if self._phone_is_recording and len(self._phone_recording_buffer) > 0:
            frames_snapshot = list(self._phone_recording_buffer)
            self._phone_is_recording = False
            self._phone_recording_buffer.clear()
            self._save_phone_alert_video_async(frames_snapshot, time.time())
        
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
        
        # Clean up thread pool
        try:
            if self._face_executor is not None:
                # Use wait=True to block until worker threads join and release MediaPipe FaceLandmarker objects.
                self._face_executor.shutdown(wait=True, cancel_futures=True)
        except Exception as e:
            logger.warning("Thread pool shutdown error: %s", e)

        # Shut down phone and gaze alert executors to clean up background worker threads.
        self._phone_alert_executor.shutdown(wait=True)
        self._gaze_alert_executor.shutdown(wait=True)
        
        logger.info("Video pipeline stopped")
        # Flush and close the diagnostic log file
        self._vlog.close()

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

            # ── Downscale to processing resolution if set ──
            max_h = self._processing_max_height
            if max_h > 0:
                h_orig = frame_data.frame.shape[0]
                if h_orig > max_h:
                    scale = max_h / h_orig
                    new_w = int(frame_data.frame.shape[1] * scale)
                    frame_data = FrameData(
                        frame=cv2.resize(frame_data.frame, (new_w, max_h),
                                         interpolation=cv2.INTER_AREA),
                        frame_index=frame_data.frame_index,
                        timestamp=frame_data.timestamp,
                        width=new_w,
                        height=max_h,
                    )

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

        # Add to global frame ring buffer for alert recordings.
        # Frames are JPEG-encoded before storage to reduce memory footprint by ~30×.
        # Decode happens only at alert-composition time (background thread).
        # Acquire buffer lock to protect against concurrent list snapshots from alert writers.
        with self._buffer_lock:
            _jpeg_bytes = encode_frame(frame_data.frame)
            self._global_frame_buffer.append(
                JPEGFrame(data=_jpeg_bytes, timestamp=frame_data.timestamp, frame_index=frame_data.frame_index)
            )

        # Check for new detection async result
        new_detection = False
        try:
            detection_result, tools_result = self._detection_queue.get_nowait()

            # ── Split YOLO detections by class ──────────────────────────────────
            # The detector may return both person (class 0) and phone (class 67)
            # detections in one result. We must split them before the tracker:
            #   • Person detections → ObjectTracker (tracking people)
            #   • Phone detections  → merged into tools_result (phone alerts)
            if detection_result is not None:
                from thaqib.video.detector import HumanDetector
                phone_class = HumanDetector.PHONE_CLASS_ID
                phone_dets  = [d for d in detection_result.detections
                               if d.class_id == phone_class]
                person_dets = [d for d in detection_result.detections
                               if d.class_id != phone_class]

                # Rebuild a persons-only DetectionResult for the tracker
                person_result = DetectionResult(
                    frame_index=detection_result.frame_index,
                    timestamp=detection_result.timestamp,
                    detections=person_dets,
                )

                # Convert phone Detections → ToolDetection and merge into tools_result
                if phone_dets and tools_result is not None:
                    from thaqib.video.tools_detector import ToolDetection
                    yolo_phone_tools = [
                        ToolDetection(
                            bbox=d.bbox,
                            confidence=d.confidence,
                            class_id=d.class_id,
                            label="phone",  # canonical label for pipeline phone filter
                        )
                        for d in phone_dets
                    ]
                    # Merge: keep existing tools_result tools (papers etc.) + add YOLO phones
                    from thaqib.video.tools_detector import ToolsDetectionResult
                    tools_result = ToolsDetectionResult(
                        frame_index=tools_result.frame_index,
                        timestamp=tools_result.timestamp,
                        tools=tools_result.tools + yolo_phone_tools,
                    )
                    logger.debug(
                        f"YOLO phones injected: {len(yolo_phone_tools)} phone(s) "
                        f"(conf={[round(d.confidence,2) for d in phone_dets]})"
                    )

                detection_result = person_result

            self._last_detection_result = detection_result
            self._last_tools_result = tools_result
            new_detection = True
            logger.debug(
                f"Detection: {detection_result.count if detection_result else 0} persons, "
                f"{tools_result.count if tools_result else 0} tools"
            )
            # Log detection result to the diagnostic file
            # phone label strings — keep in sync with VideoVisualizer._PHONE_LABELS
            phone_labels_det = {'phone', 'Using_phone', 'cell phone'}
            paper_count_det = sum(
                1 for t in (tools_result.tools if tools_result else [])
                if t.label not in phone_labels_det
            )
            phone_count_det = sum(
                1 for t in (tools_result.tools if tools_result else [])
                if t.label in phone_labels_det
            )
            self._vlog.log_detection_result(
                frame_idx=frame_data.frame_index,
                persons=detection_result.count if detection_result else 0,
                phones=phone_count_det,
                papers=paper_count_det,
                elapsed_ms=(time.perf_counter() - t0) * 1000,
            )
        except Empty:
            detection_result = self._last_detection_result
            tools_result = self._last_tools_result
            
        t1 = time.perf_counter()

        # Update tracking
        if new_detection and detection_result is not None:
            tracking_result = self._tracker.update(detection_result, frame_data.frame)
            self._last_tracking_result = tracking_result
            # Update extrapolator history with actual tracker coordinates
            for track in tracking_result.tracks:
                self._extrapolator.update(track.track_id, track.bbox, frame_data.timestamp)
        elif self._last_tracking_result is not None:
            # Use sticky last-known bounding boxes instead of velocity extrapolation.
            # Linear velocity extrapolation overshoots wildly when frame rates drop
            # (e.g. during CUDA timeouts) in a mostly static exam environment.
            sticky_tracks = []
            for track in self._last_tracking_result.tracks:
                sticky_tracks.append(TrackedObject(
                    track_id=track.track_id,
                    bbox=track.bbox,
                    confidence=track.confidence,
                    is_selected=track.is_selected,
                    label=track.label,
                    is_predicted=track.is_predicted
                ))
            tracking_result = TrackingResult(
                frame_index=frame_data.frame_index,
                timestamp=frame_data.timestamp,
                tracks=sticky_tracks,
            )
        else:
            tracking_result = TrackingResult(
                frame_index=frame_data.frame_index,
                timestamp=frame_data.timestamp,
                tracks=[],
            )

        # Apply track aliasing
        with self._alias_lock:
            for track in tracking_result.tracks:
                if track.track_id in self._track_aliases:
                    track.track_id = self._track_aliases[track.track_id]

        t2 = time.perf_counter()

        # Detection Stability Filter — keep selected tracks alive through
        # brief YOLO misses by injecting a mock track at the Kalman-predicted
        # position.  Tolerance of 300 frames (~10s at 30fps) is intentionally
        # large: BoT-SORT's track_buffer already handles short gaps, but
        # selected students should never flicker out of the overlay.
        active_track_ids = {t.track_id for t in tracking_result.tracks}
        # Prune stale extrapolator entries to prevent historical velocity maps from growing unbounded during long sessions.
        # prune stale extrapolator entries — fixes V-M-5
        self._extrapolator.prune(active_track_ids)
        tolerance = 90
        for state in self._registry.get_all():
            if state.track_id not in active_track_ids and state.is_active:
                frames_missing = frame_data.frame_index - state.last_seen_frame
                if 0 < frames_missing < tolerance:
                    predicted_bbox = self._tracker.get_predicted_bbox(state.track_id)
                    bbox = predicted_bbox if predicted_bbox is not None else state.bbox

                    # IoU check — discard ghost tracks that overlap a live track
                    is_overlapping = False
                    for active_track in tracking_result.tracks:
                        xA = max(bbox[0], active_track.bbox[0])
                        yA = max(bbox[1], active_track.bbox[1])
                        xB = min(bbox[2], active_track.bbox[2])
                        yB = min(bbox[3], active_track.bbox[3])
                        inter = max(0, xB - xA) * max(0, yB - yA)
                        if inter > 0:
                            aA = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
                            aB = (active_track.bbox[2] - active_track.bbox[0]) * (active_track.bbox[3] - active_track.bbox[1])
                            if inter / float(aA + aB - inter) > 0.4:
                                is_overlapping = True
                                break

                    if is_overlapping:
                        state.is_active = False
                        state.last_seen_time = 0.0
                        self._selected_ids.discard(state.track_id)
                        continue

                    tracking_result.tracks.append(TrackedObject(
                        track_id=state.track_id,
                        bbox=bbox,
                        confidence=0.3,
                        is_selected=state.track_id in self._selected_ids,
                        is_predicted=True,
                    ))

        # Post-tracking duplicate suppression (NMS) to resolve Issue 1
        if len(tracking_result.tracks) > 1:
            sorted_tracks = sorted(
                tracking_result.tracks,
                key=lambda x: (not getattr(x, "is_predicted", False), x.confidence),
                reverse=True
            )
            keep = []
            while sorted_tracks:
                current = sorted_tracks.pop(0)
                keep.append(current)
                cx1, cy1, cx2, cy2 = current.bbox
                c_area = (cx2 - cx1) * (cy2 - cy1)
                
                remaining = []
                for track in sorted_tracks:
                    tx1, ty1, tx2, ty2 = track.bbox
                    ix1 = max(cx1, tx1)
                    iy1 = max(cy1, ty1)
                    ix2 = min(cx2, tx2)
                    iy2 = min(cy2, ty2)
                    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                    if inter > 0:
                        t_area = (tx2 - tx1) * (ty2 - ty1)
                        union = c_area + t_area - inter
                        iou = inter / float(union)
                        if iou >= 0.45:
                            logger.info(
                                f"Suppressed duplicate overlap: Track {track.track_id} "
                                f"suppressed by Track {current.track_id} (IoU={iou:.2f})"
                            )
                            state = self._registry.get(track.track_id)
                            if state:
                                state.is_active = False
                                state.last_seen_time = 0.0
                                self._selected_ids.discard(track.track_id)
                            continue
                    remaining.append(track)
                sorted_tracks = remaining
            tracking_result.tracks = keep

        # Apply Re-ID and ID mapping
        for track in tracking_result.tracks:
            if self._auto_select_enabled:
                if track.track_id not in self._selected_ids and track.track_id not in self._deselected_ids:
                    self._selected_ids.add(track.track_id)
                    self._tracker.add_selection(track.track_id)
                    logger.info(f"Auto-selected student ID {track.track_id} for monitoring.")
            track.is_selected = track.track_id in self._selected_ids



        # Update spatial registry and compute neighbors for ALL tracks
        expired_states = self._registry.update(tracking_result.tracks, frame_data.frame_index, frame_data.timestamp)
        expired_ids = []
        
        # Cleanup ReID memory and aliases
        if expired_states:
            expired_ids = [state.track_id for state in expired_states]
            
            # Save in-progress recordings for expired tracks
            for state in expired_states:
                if state.is_alert_recording and len(state.recording_buffer) > 0:
                    frames_snapshot = list(state.recording_buffer)
                    state.is_alert_recording = False
                    cheat_type = "phone" if state.is_using_phone else "gaze"
                    cheat_ctx = {
                        'target_paper': state.cheating_target_paper,
                        'target_neighbor': state.cheating_target_neighbor,
                        'paper_bbox': self._paper_bboxes.get(
                            state.cheating_target_paper
                        ) if state.cheating_target_paper else None,
                        'is_heuristic_paper': state.is_heuristic_paper,
                        'is_using_phone': state.is_using_phone,
                        'phone_bbox': state.phone_bbox,
                        'suspicious_start_time': state.suspicious_start_time,
                    }
                    self._save_alert_video_async(
                        frames_snapshot, state.track_id, frame_data.timestamp,
                        cheat_type=cheat_type, cheat_ctx=cheat_ctx
                    )
                state.recording_buffer.clear()  # Free memory immediately
            
            self._reid.remove_embeddings(expired_ids)
            # Use the public API to prune tracker state — avoids reaching
            # into private dicts/sets from outside the tracker class.
            self._tracker.remove_tracks(expired_ids)
            
            with self._fm_cache_lock:
                for track_id in expired_ids:
                    self._fm_cache.pop(track_id, None)
                    
            with self._alias_lock:
                keys_to_delete = [
                    bot_id for bot_id, thaqib_id in self._track_aliases.items()
                    if bot_id in expired_ids or thaqib_id in expired_ids
                ]
                for k in keys_to_delete:
                    del self._track_aliases[k]

        t3 = time.perf_counter()

        # Log tracking and registry state whenever we get a new detection batch
        if new_detection:
            # Retrieve last logged track IDs to correctly identify new students.
            prev_ids = self._last_logged_track_ids
            current_ids = {t.track_id for t in tracking_result.tracks}
            # Update last logged track IDs with the current ones.
            self._last_logged_track_ids = current_ids
            self._vlog.log_tracking_update(
                frame_idx=frame_data.frame_index,
                track_ids=sorted(current_ids),
                new_ids=sorted(current_ids - prev_ids),
                expired_ids=sorted(expired_ids) if expired_ids else [],
                registry_size=len(self._registry.get_all()),
            )
        
        self._neighbor_computer.compute_neighbors(self._registry, k=get_settings().neighbor_k)
        
        # Compute paper neighbors specifically (excluding the student's closest paper)
        if tools_result is not None:
            # Labels that are NOT phones — treat as papers on the desk
            # phone label strings — keep in sync with VideoVisualizer._PHONE_LABELS
            phone_labels = {'phone', 'Using_phone', 'cell phone'}
            paper_tools = [t for t in tools_result.tools if t.label not in phone_labels]
            paper_centers = [t.center for t in paper_tools]
            # Keep a center→bbox map so alert frames can draw exact paper boxes
            self._paper_bboxes = {t.center: t.bbox for t in paper_tools}
            self._neighbor_computer.compute_paper_neighbors(self._registry, paper_centers, self._selected_ids)
            
            # Phone detection — NOT linked to any student.
            # A phone anywhere in the frame triggers an independent alert clip.
            # phone label strings — keep in sync with VideoVisualizer._PHONE_LABELS
            phone_tools = [t for t in tools_result.tools if t.label in ('phone', 'Using_phone', 'cell phone')]
            self._phone_detected = len(phone_tools) > 0

            # attribute phone detection to the nearest active student — fixes V-L-3
            if phone_tools:
                for tool in phone_tools:
                    nearest = None
                    min_dist = 300  # pixels — ignore phones far from any student
                    for s in self._registry.get_all():
                        if not s.is_active:
                            continue
                        dx = tool.center[0] - s.center[0]
                        dy = tool.center[1] - s.center[1]
                        dist = (dx * dx + dy * dy) ** 0.5
                        if dist < min_dist:
                            min_dist = dist
                            nearest = s
                    if nearest is not None:
                        nearest.is_using_phone = True
                        if not nearest.is_cheating:
                            nearest.is_cheating = True
                            nearest.cheating_cooldown = self._post_buffer_frames
            self._phone_current_bboxes = [t.bbox for t in phone_tools]
            if self._phone_detected:
                logger.warning(f"PHONE DETECTED: {len(phone_tools)} phone(s) in frame")
                self._vlog.log_phone_detected(
                    frame_idx=frame_data.frame_index,
                    bbox_count=len(phone_tools),
                    bboxes=[t.bbox for t in phone_tools],
                )
        
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

        # 2. Face mesh via thread pool:
        #    - First, COLLECT any completed futures from PREVIOUS cycle
        #    - Then, SUBMIT new jobs for this cycle
        
        # Collect completed futures — housekeeping only.
        # ReID, face_mesh update, and cheating evaluation all happen in
        # the done_callback (_make_fm_callback) immediately when the result
        # arrives, so here we just remove finished futures from the queue.
        still_pending = []
        _fm_done = 0
        _fm_not_ready = 0
        for future, orig_track_id in self._pending_fm_futures:
            if future.done():
                _fm_done += 1
            else:
                _fm_not_ready += 1
                still_pending.append((future, orig_track_id))
        self._pending_fm_futures = still_pending

        # Face mesh diagnostic (DEBUG level)
        if frame_data.frame_index % 30 == 0 and (selected_tracks or self._pending_fm_futures):
            fm_in_registry = sum(1 for s in self._registry.get_all() if s.face_mesh is not None)
            logger.debug(
                f"FM: collected={_fm_done} none=0 "
                f"errors=0 not_ready={_fm_not_ready} "
                f"pending={len(self._pending_fm_futures)} "
                f"registry_with_mesh={fm_in_registry} "
                f"student_states={len(student_states)} "
                f"selected_tracks={len(selected_tracks)}"
            )

        # Refresh face_mesh in student_states from the registry NOW
        for state in student_states:
            reg_state = self._registry.get(state.track_id)
            if reg_state is not None and reg_state.face_mesh is not None:
                state.face_mesh = reg_state.face_mesh

        if frame_data.frame_index % 30 == 0 and student_states:
            with_mesh = sum(1 for s in student_states if s.face_mesh is not None)
            logger.debug(f"FM: student_states with mesh after refresh: {with_mesh}/{len(student_states)}")

        # Submit NEW face-mesh jobs via thread pool.
        # Rules (matching the original working multiprocessing approach):
        #   1. Skip any student that already has a pending job — prevents a race
        #      where an OLDER result arrives late and overwrites a newer one,
        #      causing the face overlay to appear at a stale ("flying") position.
        #   2. Respect available worker slots (pending < num_workers).
        #   3. Cap total pending at 3 × workers as a safety net.
        if selected_tracks and student_states and self._face_executor is not None:
            # Cleanup completed futures to keep list small
            self._pending_fm_futures = [(f, tid) for f, tid in self._pending_fm_futures if not f.done()]

            # Safety net: if too many pending futures, skip all new submissions this frame
            MAX_PENDING_FM = self._fm_num_workers * 4   # e.g. 4 workers × 4 = 16 max queued
            if len(self._pending_fm_futures) >= MAX_PENDING_FM:
                logger.warning(
                    f"Face mesh executor backlogged ({len(self._pending_fm_futures)} pending) "
                    f"— skipping face mesh this frame."
                )
            else:
                # Only submit for students WITHOUT a pending job (key fix vs old round-robin)
                pending_track_ids = {tid for _, tid in self._pending_fm_futures}
                new_students = []
                for state in student_states:
                    if state.track_id in pending_track_ids:
                        continue
                    
                    reg_state = self._registry.get(state.track_id)
                    if reg_state is None:
                        continue
                        
                    if (frame_data.frame_index - reg_state.fm_last_frame) < FACE_MESH_INTERVAL:
                        continue
                        
                    new_students.append((state, reg_state))

                if new_students:
                    # Compute face mesh scale factor for current frame dimensions.
                    # Recalculated whenever _fm_scale_computed is False (e.g. after
                    # a processing-resolution change via the G key).
                    if not self._fm_scale_computed:
                        h = frame_data.frame.shape[0]
                        if h > self._recording_max_h:
                            self._fm_scale = self._recording_max_h / h
                        else:
                            self._fm_scale = 1.0
                        self._fm_scale_computed = True

                    # Downscale frame for face mesh (saves ~4× MediaPipe inference time)
                    fm_scale = self._fm_scale
                    if fm_scale < 1.0:
                        h, w = frame_data.frame.shape[:2]
                        new_w = int(w * fm_scale)
                        new_h = int(h * fm_scale)
                        fm_frame = cv2.resize(frame_data.frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
                    else:
                        fm_frame = frame_data.frame.copy()

                    # Submit to thread pool.
                    # Old pattern: add_done_callback so cheating is evaluated
                    # IMMEDIATELY when face mesh is ready, not deferred to next frame.
                    for state, reg_state in new_students:
                        future = self._face_executor.submit(
                            self._fm_thread_infer, fm_frame, state.bbox, fm_scale, state.track_id
                        )
                        # Remove tracking_result argument to match the updated callback signature.
                        future.add_done_callback(
                            self._make_fm_callback(state.track_id)
                        )
                        self._pending_fm_futures.append((future, state.track_id))
                        reg_state.fm_last_frame = frame_data.frame_index

        # 3. Cheating evaluation — runs every frame for every selected student.
        # The evaluator snapshots reg_state.face_mesh internally and routes to
        # either the face-lost path (_handle_face_lost) or the gaze-check path.
        # A single call here is sufficient and avoids a race where the FM worker
        # delivers a result between two consecutive is-None / is-not-None checks,
        # which previously caused both branches to fire in the same frame.
        if selected_tracks:
            for state in student_states:
                reg_state = self._registry.get(state.track_id)
                if reg_state is not None:
                    self._cheating_evaluator.evaluate(state.track_id, frame_data.timestamp)

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
                        self._vlog.log_recording_cap_hit(
                            track_id=state.track_id,
                            active_recordings=active_recordings,
                        )
                    continue
                
                # START recording: snapshot pre-buffer (last ~2s) from global_frame_buffer.
                # Frames are already JPEG-encoded (JPEGFrame objects) — cheap to copy.
                # Pre-event frames carry tid=None so the writer renders them raw.
                state.is_alert_recording = True
                # Acquire buffer lock to protect against concurrent frame appends.
                with self._buffer_lock:
                    pre_frames = list(self._global_frame_buffer)[-self._post_buffer_frames:]
                state.recording_buffer = deque(pre_frames, maxlen=300)
                state.frames_to_record = self._post_buffer_frames  # 2-second post-buffer
                self._recording_skip_warned.discard(state.track_id)  # Reset warn on successful start
                cheat_type_start = "phone" if state.is_using_phone else "gaze"
                self._vlog.log_alert_recording_start(
                    track_id=state.track_id,
                    prebuffer_frames=len(state.recording_buffer),
                    post_buffer_frames=self._post_buffer_frames,
                    cheat_type=cheat_type_start,
                )
            
            if not state.is_alert_recording:
                continue

            # Append current frame JPEG-encoded to keep per-frame cost ~100 KB (vs 2.76 MB raw).
            state.recording_buffer.append(
                JPEGFrame(
                    data=encode_frame(frame_data.frame),
                    timestamp=frame_data.timestamp,
                    frame_index=frame_data.frame_index,
                    track_id=state.track_id,
                    student_bbox=state.bbox,
                    student_center=state.center,
                )
            )

            if state.is_cheating:
                # Still cheating — keep recording, reset post-cheating countdown
                state.frames_to_record = self._post_buffer_frames  # Will countdown only after cheating stops
            else:
                # Cheating stopped — count down the 2s post-buffer
                state.frames_to_record -= 1
                if state.frames_to_record <= 0:
                    # Take a snapshot of the buffer for the writer thread,
                    # then reset recording state immediately.
                    frames_snapshot = list(state.recording_buffer)
                    state.is_alert_recording = False
                    state.recording_buffer = deque(maxlen=_MAX_RECORDING_FRAMES)
                    
                    # Determine cheat type BEFORE resetting state
                    cheat_type = "phone" if state.is_using_phone else "gaze"
                    
                    # Snapshot cheating context BEFORE reset so the background
                    # writer can render paper/victim annotations correctly.
                    # Without this, cheating_target_paper is already None by
                    # the time the writer thread calls _render_alert_frame.
                    cheat_ctx = {
                        'target_paper': state.cheating_target_paper,
                        'target_neighbor': state.cheating_target_neighbor,
                        'paper_bbox': self._paper_bboxes.get(
                            state.cheating_target_paper
                        ) if state.cheating_target_paper else None,
                        'is_heuristic_paper': state.is_heuristic_paper,
                        'is_using_phone': state.is_using_phone,
                        'phone_bbox': state.phone_bbox,
                        'suspicious_start_time': state.suspicious_start_time,
                    }
                    
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
                        cheat_type=cheat_type, cheat_ctx=cheat_ctx
                    )

        # ── Phone alert recording state machine ──────────────────────────────
        # Completely independent of student tracking.
        # START: phone detected and not yet recording → snapshot 2s pre-buffer
        # DURING: phone still detected → keep recording, reset countdown
        # POST: phone gone → count down 2s (60 frames), then save
        if self._phone_detected and not self._phone_is_recording:
            self._phone_is_recording = True
            # Pre-event frames are already JPEGFrames from global_frame_buffer.
            # Wrap them as phone-context JPEGFrames (phone_bboxes=[]) so the
            # writer knows no phone was visible yet in the pre-roll section.
            # Acquire buffer lock to protect against concurrent frame appends.
            with self._buffer_lock:
                pre = list(self._global_frame_buffer)[-self._post_buffer_frames:]  # last ~2s
            # Re-wrap: copy JPEG bytes, set phone_bboxes=[] (no phone visible yet)
            self._phone_recording_buffer = deque(
                [
                    JPEGFrame(
                        data=item.data,
                        timestamp=item.timestamp,
                        frame_index=item.frame_index,
                        phone_bboxes=[],
                    )
                    for item in pre
                ],
                maxlen=_MAX_RECORDING_FRAMES,
            )
            self._phone_frames_to_record = self._post_buffer_frames
            logger.info("Phone alert recording STARTED")
            self._vlog.log_phone_alert_recording_start(
                prebuffer_frames=len(pre),
                post_buffer_frames=self._post_buffer_frames,
            )

        if self._phone_is_recording:
            # Store JPEG-encoded frame alongside current phone bboxes.
            self._phone_recording_buffer.append(
                JPEGFrame(
                    data=encode_frame(frame_data.frame),
                    timestamp=frame_data.timestamp,
                    frame_index=frame_data.frame_index,
                    phone_bboxes=list(self._phone_current_bboxes),
                )
            )
            if self._phone_detected:
                self._phone_frames_to_record = self._post_buffer_frames  # reset post-countdown
            else:
                self._phone_frames_to_record -= 1
                if self._phone_frames_to_record <= 0:
                    frames_snapshot = list(self._phone_recording_buffer)
                    self._phone_is_recording = False
                    self._phone_recording_buffer = deque(maxlen=_MAX_RECORDING_FRAMES)
                    self._save_phone_alert_video_async(frames_snapshot, frame_data.timestamp)

        t5 = time.perf_counter()

        # Build compact track list for the per-frame diagnostic log
        tracks_for_log = [
            {
                "id": t.track_id,
                "bbox": list(t.bbox),
                "selected": t.is_selected,
                "conf": round(t.confidence, 3),
            }
            for t in tracking_result.tracks
        ]
        self._vlog.log_frame(
            frame_idx=frame_data.frame_index,
            timestamp=frame_data.timestamp,
            proc_ms=(t5 - t0) * 1000,
            detect_ms=(t1 - t0) * 1000,
            track_ms=(t2 - t1) * 1000,
            registry_ms=(t3 - t2) * 1000,
            neighbor_ms=(t4 - t3) * 1000,
            facemesh_ms=(t5 - t4) * 1000,
            tracks=tracks_for_log,
            new_detection=new_detection,
            detection_persons=detection_result.count if detection_result else 0,
            detection_tools=tools_result.count if tools_result else 0,
            selected_count=sum(1 for t in tracking_result.tracks if t.is_selected),
            pending_fm_futures=len(self._pending_fm_futures),
            fm_collected=_fm_done,
            fm_none=0,
            fm_errors=0,
            phone_detected=self._phone_detected,
            phone_is_recording=self._phone_is_recording,
            global_buffer_len=len(self._global_frame_buffer),
            processing_res=self._processing_presets[self._processing_preset_idx][0],
        )

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

        pipeline_frame = PipelineFrame(
            frame=frame_data.frame,
            frame_index=frame_data.frame_index,
            timestamp=frame_data.timestamp,
            detection_result=detection_result,
            tools_result=tools_result,
            tracking_result=tracking_result,
            registry=self._registry,
            student_states=student_states,
            archive_mode=self.archive_mode,
            video_quality=self._video_quality,
            processing_res=self._processing_presets[self._processing_preset_idx][0],
        )

        # Single rendering pass: draw annotations once, store for both
        # archive writing and display. Falls back to raw frame when no
        # visualizer is attached (headless/testing mode).
        if self._visualizer is not None:
            pipeline_frame.annotated_frame = self._visualizer.draw(
                pipeline_frame, registry=self._registry
            )
            # Archive mode determines what gets saved to disk
            if self._archive_annotated:
                self._write_archive_frame(pipeline_frame.annotated_frame)
            else:
                self._write_archive_frame(frame_data.frame)
        else:
            self._write_archive_frame(frame_data.frame)

        return pipeline_frame

    def select_students(self, track_ids: list[int]) -> None:
        """
        Select students to monitor.

        Args:
            track_ids: List of track IDs to monitor.
        """
        self._auto_select_enabled = True
        self._deselected_ids.clear()
        ids_before = sorted(self._selected_ids)
        self._selected_ids = set(track_ids)
        self._tracker.select_tracks(track_ids)
        self._vlog.log_student_selection(
            action="SELECT",
            ids_before=ids_before,
            ids_after=sorted(self._selected_ids),
        )

    def add_student(self, track_id: int) -> None:
        """Add a student to monitoring."""
        self._deselected_ids.discard(track_id)
        ids_before = sorted(self._selected_ids)
        self._selected_ids.add(track_id)
        self._tracker.add_selection(track_id)
        self._vlog.log_student_selection(
            action="ADD",
            ids_before=ids_before,
            ids_after=sorted(self._selected_ids),
        )

    def remove_student(self, track_id: int) -> None:
        """Remove a student from monitoring and realign paper assignments.
        
        Clears the student's paper so they can no longer be a cheating 'victim',
        removes them from other students' neighbor lists, and invalidates the
        neighbor cache so papers realign to adjacent students on the next frame.
        """
        self._deselected_ids.add(track_id)
        ids_before = sorted(self._selected_ids)
        self._selected_ids.discard(track_id)
        self._tracker.remove_selection(track_id)
        self._vlog.log_student_selection(
            action="REMOVE",
            ids_before=ids_before,
            ids_after=sorted(self._selected_ids),
        )
        
        # Clear this student's paper so it's no longer a neighbor paper target
        state = self._registry.get(track_id)
        if state:
            state.detected_paper = None
            state.is_heuristic_paper = False
            state.surrounding_papers = []
        
        # Remove from other students' neighbor/paper lists immediately
        for s in self._registry.get_all():
            if track_id in s.neighbors:
                s.neighbors.remove(track_id)
                s.neighbor_distances.pop(track_id, None)
                s.neighbor_papers.pop(track_id, None)
            # Remove any surrounding paper that belonged to the deselected student
            if state and state.paper_center is not None:
                # remove ALL occurrences — fixes V-L-6
                s.surrounding_papers = [
                    p for p in s.surrounding_papers
                    if p != state.paper_center
                ]
        
        # Invalidate the neighbor stability cache so the next frame
        # fully recomputes neighbors and paper assignments.
        self._neighbor_computer._prev_centers = None
        self._neighbor_computer._prev_track_ids = None

    def clear_selection(self) -> None:
        """Clear all selected students."""
        self._auto_select_enabled = False
        self._deselected_ids.clear()
        self._selected_ids.clear()
        if hasattr(self._tracker, 'clear_selection'):
            self._tracker.clear_selection()

    def set_visualizer(self, visualizer) -> None:
        """Attach a visualizer for single-pass annotation and archive rendering.

        Must be called before pipeline.run() for annotations to appear in
        the archive. Calling with None reverts to archiving raw frames.
        """
        self._visualizer = visualizer

    def toggle_archive_mode(self) -> str:
        """Toggle archive recording between raw and annotated mode.
        
        Returns:
            The new mode as a string ('raw' or 'annotated').
        """
        self._archive_annotated = not self._archive_annotated
        mode = "annotated" if self._archive_annotated else "raw"
        logger.info(f"Archive mode switched to: {mode}")
        return mode

    @property
    def archive_mode(self) -> str:
        """Current archive recording mode."""
        return "annotated" if self._archive_annotated else "raw"


    def _render_alert_frame(
        self, raw_frame: np.ndarray, cheater_track_id: int,
        student_bbox: tuple[int, int, int, int] | None = None,
        student_center: tuple[int, int] | None = None,
        cheat_ctx: dict | None = None,
    ) -> np.ndarray:
        """
        Render an annotated frame for alert video recording.

        Args:
            raw_frame: The raw camera frame.
            cheater_track_id: Track ID of the cheating student.
            student_bbox: Current student bbox in this frame.
            student_center: Current student center in this frame.
            cheat_ctx: Frozen snapshot of cheating state captured before reset.
                       Contains target_paper, target_neighbor, paper_bbox, etc.
                       If None, falls back to live registry (may be stale).

        Draws:
          - RED thick bbox + label on the cheater
          - YELLOW thick bbox + label on the victim paper
          - Gaze arrow from cheater to paper
          - RED bbox on phone (if phone cheating)
          - Status banner at top
        """
        frame = raw_frame.copy()
        cheater = self._registry.get(cheater_track_id)
        
        # Fallback to registry if student_bbox or student_center are not passed
        bbox = student_bbox
        center = student_center
        if bbox is None or center is None:
            if cheater is not None:
                if bbox is None:
                    bbox = cheater.bbox
                if center is None:
                    center = cheater.center
            else:
                return frame

        # Use frozen snapshot if available; fall back to live state.
        ctx = cheat_ctx or {}
        is_using_phone = ctx.get('is_using_phone', getattr(cheater, 'is_using_phone', False) if cheater else False)
        phone_bbox = ctx.get('phone_bbox', getattr(cheater, 'phone_bbox', None) if cheater else None)
        target_paper = ctx.get('target_paper', cheater.cheating_target_paper if cheater else None)
        target_neighbor = ctx.get('target_neighbor', cheater.cheating_target_neighbor if cheater else None)
        paper_bbox_snap = ctx.get('paper_bbox')  # YOLO bbox from snapshot
        is_heuristic = ctx.get('is_heuristic_paper', getattr(cheater, 'is_heuristic_paper', True) if cheater else True)

        # Draw the cheater in RED with full body bbox
        cx1, cy1, cx2, cy2 = bbox
        cv2.rectangle(frame, (cx1, cy1), (cx2, cy2), (0, 0, 255), 3)
        
        # Label depends on cheating type
        if is_using_phone:
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
        if is_using_phone and phone_bbox is not None:
            px1, py1, px2, py2 = phone_bbox
            cv2.rectangle(frame, (px1, py1), (px2, py2), (0, 0, 255), 3)
            cv2.putText(frame, "PHONE", (px1, py1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2, cv2.LINE_AA)
        
        # Draw YELLOW box around the paper being looked at
        if target_paper is not None and not is_using_phone:
            # Try snapshot bbox first, then fall back to live _paper_bboxes
            p_bbox = paper_bbox_snap or self._paper_bboxes.get(target_paper)
            if p_bbox is not None:
                # YOLO-detected paper — draw precise bbox
                px1, py1, px2, py2 = p_bbox
                cv2.rectangle(frame, (px1, py1), (px2, py2), (0, 255, 255), 3)
                paper_label = "PAPER"
                (lw, lh), _ = cv2.getTextSize(paper_label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                cv2.rectangle(frame, (px1, py1 - lh - 8), (px1 + lw, py1), (0, 255, 255), -1)
                cv2.putText(frame, paper_label,
                            (px1, py1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                            (0, 0, 0), 2, cv2.LINE_AA)
                # Gaze line from cheater center to paper center
                paper_cx = (px1 + px2) // 2
                paper_cy = (py1 + py2) // 2
                cv2.line(frame, center, (paper_cx, paper_cy), (0, 0, 255), 2, cv2.LINE_AA)
            elif not is_heuristic:
                # YOLO paper but bbox not in cache — draw circle fallback
                px, py = target_paper
                cv2.circle(frame, (px, py), 22, (0, 255, 255), 3, cv2.LINE_AA)
                cv2.putText(frame, "PAPER", (px - 28, py - 28),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2, cv2.LINE_AA)
                cv2.line(frame, center, (px, py), (0, 0, 255), 2, cv2.LINE_AA)
        
        # Draw status banner at top
        banner_h = 40
        cv2.rectangle(frame, (0, 0), (frame.shape[1], banner_h), (0, 0, 180), -1)
        if is_using_phone:
            status_text = f"PHONE ALERT - Student {cheater_track_id} using phone"
        else:
            status_text = f"CHEATING ALERT - Student {cheater_track_id}"
            if target_neighbor is not None:
                status_text += f" copying from Student {target_neighbor}"
        cv2.putText(frame, status_text, (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        
        return frame

    def _render_phone_alert_frame(
        self, raw_frame: np.ndarray, phone_bboxes: list
    ) -> np.ndarray:
        """
        Render a frame for phone alert recording.

        Draws a red bounding box around each detected phone.
        No student information is shown — phone-only annotation.
        """
        frame = raw_frame.copy()

        for bbox in phone_bboxes:
            if bbox is None:
                continue
            px1, py1, px2, py2 = bbox
            cv2.rectangle(frame, (px1, py1), (px2, py2), (0, 0, 255), 3)
            label = "PHONE"
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            cv2.rectangle(frame, (px1, py1 - lh - 10), (px1 + lw + 4, py1), (0, 0, 255), -1)
            cv2.putText(frame, label, (px1 + 2, py1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

        # Banner at the top
        banner_h = 40
        cv2.rectangle(frame, (0, 0), (frame.shape[1], banner_h), (0, 0, 180), -1)
        cv2.putText(frame, "PHONE ALERT - Mobile device detected",
                    (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

        return frame

    def _save_phone_alert_video_async(
        self, frames: list, timestamp: float
    ) -> None:
        """Save phone alert clip in a background thread.

        Each entry in frames is a (raw_frame, phone_bboxes) tuple.
        Pre-event frames (phone not yet visible) have phone_bboxes = [] and
        are written raw. During/post frames are annotated with red phone boxes.
        """
        def writer_task():
            from pathlib import Path
            from datetime import datetime
            
            writer = None
            try:
                if not frames:
                    return

                # Decode the first valid frame to determine dimensions.
                height, width = None, None
                for item in frames:
                    if isinstance(item, JPEGFrame):
                        raw = item.decode()
                        height, width = raw.shape[:2]
                        break
                    elif isinstance(item, AlertFrame):
                        height, width = item.frame.shape[:2]
                        break
                    elif isinstance(item, tuple):
                        raw = item[1].frame if hasattr(item[1], 'frame') else item[1]
                        if raw is not None:
                            height, width = raw.shape[:2]
                            break
                    elif hasattr(item, 'frame') and item.frame is not None:
                        height, width = item.frame.shape[:2]
                        break

                if height is None:
                    return

                # Downscale to alert_max_height if needed (same as gaze alert)
                max_h = self._settings.alert_max_height
                if max_h > 0 and height > max_h:
                    scale = max_h / height
                    width  = int(width * scale)
                    height = max_h
                out_size = (width, height)

                # Resolve alerts_dir to prevent path traversal vulnerability.
                alerts_dir = Path(self._settings.alerts_dir).resolve()
                alerts_dir.mkdir(exist_ok=True)
                time_str = datetime.fromtimestamp(timestamp).strftime("%Y%m%d_%H%M%S")

                frames_written = 0
                annotated_frames = []
                subject_point = None

                for item in frames:
                    # Decode JPEG bytes if needed (JPEGFrame), else use raw frame.
                    if isinstance(item, JPEGFrame):
                        raw_frame = item.decode()
                        phone_bboxes = item.phone_bboxes
                    elif isinstance(item, tuple):
                        raw_frame = item[1].frame if hasattr(item[1], 'frame') else item[1]
                        phone_bboxes = getattr(item[1], 'phone_bboxes', [])
                    elif hasattr(item, 'frame'):
                        raw_frame = item.frame
                        phone_bboxes = getattr(item, 'phone_bboxes', [])
                    else:
                        continue

                    if raw_frame is None:
                        continue

                    if phone_bboxes:
                        out_frame = self._render_phone_alert_frame(raw_frame, phone_bboxes)
                        if subject_point is None:
                            px1, py1, px2, py2 = phone_bboxes[0]
                            subject_point = ((px1 + px2) // 2, (py1 + py2) // 2)
                    else:
                        out_frame = raw_frame

                    if out_frame.shape[:2] != (height, width):
                        out_frame = cv2.resize(out_frame, out_size, interpolation=cv2.INTER_AREA)

                    # Always burn timestamp into phone alert videos.
                    if out_frame is raw_frame:
                        out_frame = out_frame.copy()
                    draw_timestamp_overlay(out_frame)
                    annotated_frames.append(out_frame)

                # Composer integration path
                if getattr(self, '_composer', None) is not None:
                    if subject_point is None:
                        subject_point = (width // 2, height // 2)
                        
                    def _get_ts(itm):
                        if hasattr(itm, 'timestamp'):
                            return itm.timestamp
                        if isinstance(itm, tuple):
                            return itm[0]
                        return timestamp

                    timestamp_start = _get_ts(frames[0]) if frames else timestamp - (len(annotated_frames) / self._camera_fps)
                    timestamp_end = _get_ts(frames[-1]) if frames else timestamp
                    
                    self._composer.on_video_alert(
                        frames=annotated_frames,
                        alert_type="phone",
                        subject_point=subject_point,
                        camera_id=self._camera_id,
                        timestamp_start=timestamp_start,
                        timestamp_end=timestamp_end
                    )
                    return

                # Standalone Fallback Path
                codec_options = [
                    ('avc1', '.mp4'),
                    ('mp4v', '.mp4'),
                    ('XVID', '.avi'),
                    ('MJPG', '.avi'),
                ]

                filename = None
                for codec, ext in codec_options:
                    filename = alerts_dir / f"phone_alert_{time_str}{ext}"
                    fourcc = cv2.VideoWriter_fourcc(*codec)
                    writer = cv2.VideoWriter(str(filename), fourcc, self._camera_fps, out_size)
                    if writer.isOpened():
                        writer.set(cv2.VIDEOWRITER_PROP_QUALITY, self._video_quality)
                        logger.info(f"Phone alert: using codec '{codec}' → {filename}")
                        break
                    writer.release()
                    writer = None

                if writer is None or not writer.isOpened():
                    logger.error("Phone alert: all codecs failed — video not saved. Attempting JPEG fallback.")
                    jpg_dir = alerts_dir / f"phone_alert_frames_{time_str}"
                    jpg_dir.mkdir(exist_ok=True)
                    for i, out_frame in enumerate(annotated_frames):
                        cv2.imwrite(str(jpg_dir / f"frame_{i:04d}.jpg"), out_frame)
                    logger.warning(f"Saved JPEG sequence fallback to {jpg_dir}")
                    return

                for out_frame in annotated_frames:
                    writer.write(out_frame)
                    frames_written += 1
                    
                duration = frames_written / self._camera_fps
                logger.info(
                    f"Saved phone alert video: {filename} "
                    f"({duration:.1f}s, {frames_written} frames)"
                )
            except Exception as e:
                logger.error(f"Error saving phone alert video: {e}")
            finally:
                if writer is not None:
                    writer.release()

        # Use a bounded thread pool executor for phone alert writing to prevent uncapped memory footprint.
        self._phone_alert_executor.submit(writer_task)

    def _archive_writer_loop(self) -> None:
        """Background thread: drain archive queue and write frames to disk.

        Runs until _is_running is False AND the queue is empty, ensuring
        all buffered frames are flushed on shutdown.
        """
        while self._is_running or not self._archive_queue.empty():
            try:
                frame = self._archive_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if self._archive_writer is not None:
                # Resize if frame dimensions don't match writer (e.g. G key changed resolution).
                if self._archive_size is not None and frame.shape[:2] != (self._archive_size[1], self._archive_size[0]):
                    frame = cv2.resize(frame, self._archive_size, interpolation=cv2.INTER_AREA)
                # Always burn real-time timestamp into archived frames.
                draw_timestamp_overlay(frame)
                self._archive_writer.write(frame)

    def _write_archive_frame(self, frame: np.ndarray) -> None:
        """
        Queue a frame for archive writing (non-blocking).
        Creates the archive writer on first call (one-time cost on main thread).
        Accepts a pre-rendered annotated frame or a raw frame.
        """
        if self._archive_writer is None:
            from pathlib import Path
            from datetime import datetime

            archive_dir = Path(self._settings.archive_dir)
            archive_dir.mkdir(exist_ok=True)

            time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            h, w = frame.shape[:2]

            # Use actual camera FPS so playback speed matches recording speed.
            archive_fps = self._camera_fps

            # Try codecs in order of preference — MP4 first
            for codec, ext in [('avc1', '.mp4'), ('mp4v', '.mp4'), ('XVID', '.avi'), ('MJPG', '.avi')]:
                filepath = archive_dir / f"archive_{time_str}{ext}"
                fourcc = cv2.VideoWriter_fourcc(*codec)
                writer = cv2.VideoWriter(str(filepath), fourcc, archive_fps, (w, h))
                if writer.isOpened():
                    writer.set(cv2.VIDEOWRITER_PROP_QUALITY, self._video_quality)
                    self._archive_writer = writer
                    self._archive_path = str(filepath)
                    self._archive_size = (w, h)
                    logger.info(
                        f"Archive recording started: {filepath} "
                        f"(codec={codec}, quality={self._video_quality}, size={w}x{h})"
                    )
                    self._vlog.log_archive_start(
                        filepath=str(filepath),
                        codec=codec,
                        quality=self._video_quality,
                        size=(w, h),
                        fps=archive_fps,
                    )
                    break
                writer.release()
            else:
                logger.error("Failed to create archive writer — all codecs failed")
                return

        # Non-blocking enqueue — drop frame rather than block main thread
        try:
            self._archive_queue.put_nowait(frame)
        except queue.Full:
            # Log warning when the queue is full to prevent silent frame drops.
            logger.warning("Archive queue full — dropping frame (disk too slow?)")

    def _save_alert_video_async(
        self, frames: list[np.ndarray], track_id: int, timestamp: float,
        cheat_type: str = "gaze", cheat_ctx: dict | None = None,
    ) -> None:
        """Save alert video in a background thread.

        Args:
            frames: Independent frame list (snapshot of recording buffer).
            track_id: The cheating student's track ID.
            timestamp: Event timestamp for filename.
            cheat_type: 'gaze' or 'phone'.
            cheat_ctx: Frozen snapshot of cheating state (paper, victim, etc.).
                       Captured BEFORE state reset so the writer can render
                       paper/victim annotations correctly.
        """
        def writer_task():
            from pathlib import Path
            from datetime import datetime
            
            writer = None
            try:
                if not frames:
                    logger.warning(f"Alert video for track {track_id}: empty frame list, skipping.")
                    return
                
                # Resolve alerts_dir to prevent path traversal vulnerability.
                alerts_dir = Path(self._settings.alerts_dir).resolve()
                alerts_dir.mkdir(exist_ok=True)
                
                time_str = datetime.fromtimestamp(timestamp).strftime("%Y%m%d_%H%M%S")
                
                # Determine frame dimensions by decoding the first valid item.
                height, width = None, None
                for item in frames:
                    if isinstance(item, JPEGFrame):
                        raw_frame = item.decode()
                    elif isinstance(item, AlertFrame):
                        raw_frame = item.frame
                    elif isinstance(item, tuple):
                        raw_frame = item[1].frame if hasattr(item[1], 'frame') else item[1]
                    else:
                        raw_frame = item
                    if raw_frame is not None:
                        height, width = raw_frame.shape[:2]
                        break

                if height is None:
                    logger.warning(f"Alert video for track {track_id}: no valid frames, skipping.")
                    return

                # Downscale alert videos to alert_max_height if needed.
                max_h = self._settings.alert_max_height
                if max_h > 0 and height > max_h:
                    scale = max_h / height
                    width  = int(width  * scale)
                    height = max_h
                out_size = (width, height)
                
                prefix = "phone_alert" if cheat_type == "phone" else "gaze_alert"
                
                frames_written = 0
                annotated_frames = []
                subject_point = None
                
                for item in frames:
                    # Decode JPEG bytes if needed (JPEGFrame), else extract raw array.
                    if isinstance(item, JPEGFrame):
                        raw_frame = item.decode()
                        tid = item.track_id
                        student_bbox = item.student_bbox
                        student_center = item.student_center
                    elif isinstance(item, AlertFrame):
                        raw_frame = item.frame
                        tid = item.track_id
                        student_bbox = item.student_bbox
                        student_center = item.student_center
                    elif isinstance(item, tuple):
                        raw_frame = item[1].frame if hasattr(item[1], 'frame') else item[1]
                        tid = getattr(item[1], 'track_id', None)
                        student_bbox = getattr(item[1], 'bbox', None)
                        student_center = getattr(item[1], 'center', None)
                    else:
                        raw_frame = item
                        tid = None
                        student_bbox = None
                        student_center = None

                    # Pre-event frames have tid=None → write raw.
                    # During/post frames have track_id → annotate.
                    if tid is not None:
                        if student_center is not None:
                            subject_point = student_center
                        out = self._render_alert_frame(
                            raw_frame, tid,
                            student_bbox=student_bbox,
                            student_center=student_center,
                            cheat_ctx=cheat_ctx
                        )
                    else:
                        # Pre-event frame: copy to prevent shared-buffer corruption.
                        out = raw_frame.copy()
                    # Resize if needed
                    if out.shape[:2] != (height, width):
                        out = cv2.resize(out, out_size, interpolation=cv2.INTER_AREA)
                    # Always burn timestamp into gaze alert videos
                    draw_timestamp_overlay(out)
                    annotated_frames.append(out)

                # Composer integration path
                if getattr(self, '_composer', None) is not None:
                    # Resolve subject_point for phone cheat if needed
                    if cheat_type == "phone":
                        phone_bbox = cheat_ctx.get('phone_bbox') if cheat_ctx else None
                        if phone_bbox:
                            subject_point = ((phone_bbox[0] + phone_bbox[2]) // 2, (phone_bbox[1] + phone_bbox[3]) // 2)

                    if subject_point is None:
                        subject_point = (width // 2, height // 2)

                    # Extract relative time using frame_index for perfect archive sync
                    def _get_relative_time(itm):
                        if hasattr(itm, 'frame_index'):
                            return itm.frame_index / float(self._camera_fps)
                        # Fallback for tuples if any
                        if isinstance(itm, tuple) and hasattr(itm[1], 'frame_index'):
                            return itm[1].frame_index / float(self._camera_fps)
                        return None

                    # Use the first and last frames of the buffer directly,
                    # as the buffer naturally contains the pre-roll and post-roll.
                    timestamp_start = _get_relative_time(frames[0]) if frames else 0.0
                    timestamp_end = _get_relative_time(frames[-1]) if frames else 0.0
                    
                    # Fallback to system time if frame_index is somehow missing
                    if timestamp_start is None or timestamp_start == 0.0:
                        def _get_ts(itm):
                            if hasattr(itm, 'timestamp'):
                                return itm.timestamp
                            if isinstance(itm, tuple):
                                return itm[0]
                            return timestamp
                        if cheat_ctx and cheat_ctx.get('suspicious_start_time', 0.0) > 0.0:
                            timestamp_start = cheat_ctx['suspicious_start_time'] - 2.0
                        else:
                            timestamp_start = _get_ts(frames[0]) if frames else timestamp - (len(annotated_frames) / self._camera_fps)
                        timestamp_end = _get_ts(frames[-1]) if frames else timestamp
                    
                    # Find the nearest mic ID to the student
                    mic_id = None
                    if self._composer.layout:
                        mic_pin = self._composer.layout.nearest_mic_for_point(subject_point, self._camera_id, (width, height))
                        if mic_pin:
                            mic_id = mic_pin.mic_id

                    self._composer.compose_video_alert(
                        camera_id=self._camera_id,
                        mic_id=mic_id,
                        start_sec=timestamp_start,
                        end_sec=timestamp_end,
                        alert_type=cheat_type,
                        subject_point=subject_point
                    )
                    return

                # Standalone Fallback Path (if no composer)
                codec_options = [
                    ('avc1', '.mp4'),
                    ('mp4v', '.mp4'),
                    ('XVID', '.avi'),
                    ('MJPG', '.avi'),
                ]
                
                filename = None
                for codec, ext in codec_options:
                    filename = alerts_dir / f"{prefix}_track{track_id}_{time_str}{ext}"
                    fourcc = cv2.VideoWriter_fourcc(*codec)
                    writer = cv2.VideoWriter(str(filename), fourcc, self._camera_fps, out_size)
                    if writer.isOpened():
                        writer.set(cv2.VIDEOWRITER_PROP_QUALITY, self._video_quality)
                        logger.info(f"Using codec '{codec}' for {filename}")
                        break
                    writer.release()
                    writer = None
                
                if writer is None or not writer.isOpened():
                    logger.error(f"Failed to create video writer — all codecs failed for track {track_id}. Attempting JPEG fallback.")
                    jpg_dir = alerts_dir / f"{prefix}_frames_track{track_id}_{time_str}"
                    jpg_dir.mkdir(exist_ok=True)
                    for i, frame in enumerate(annotated_frames):
                        cv2.imwrite(str(jpg_dir / f"frame_{i:04d}.jpg"), frame)
                    logger.warning(f"Saved JPEG sequence fallback to {jpg_dir}")
                    return

                for out in annotated_frames:
                    writer.write(out)
                    frames_written += 1
                duration = frames_written / self._camera_fps
                logger.info(
                    f"Saved {cheat_type} alert video: {filename} "
                    f"({duration:.1f}s, {frames_written} frames, {self._camera_fps:.0f}fps)"
                )
                self._vlog.log_alert_recording_save(
                    track_id=track_id,
                    filename=str(filename),
                    frames=frames_written,
                    duration_sec=duration,
                    codec=codec if writer else "unknown",
                    cheat_type=cheat_type,
                    cheat_ctx=cheat_ctx,
                )
            except Exception as e:
                logger.error(f"Error saving alert video: {e}")
                self._vlog.log_error(context="save_alert_video", error=str(e))
            finally:
                if writer is not None:
                    writer.release()
                
        # Use a bounded thread pool executor for gaze alert writing to prevent uncapped memory footprint.
        self._gaze_alert_executor.submit(writer_task)

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

    @property
    def video_quality(self) -> int:
        """Public accessor for current video quality level."""
        return self._video_quality

    def __enter__(self) -> "VideoPipeline":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.stop()
