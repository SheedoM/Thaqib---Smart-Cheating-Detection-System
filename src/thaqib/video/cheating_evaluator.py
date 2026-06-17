"""
Cheating evaluation module.
Evaluates rules synchronously to ensure state consistency with recording.
"""

import math
import time
import logging
from typing import Callable

import numpy as np

from thaqib.config import get_settings
from thaqib.video.registry import GlobalStudentRegistry
from thaqib.video.gaze import compute_gaze_direction
from thaqib.video.video_logger import get_video_logger


logger = logging.getLogger(__name__)


class CheatingEvaluator:
    """
    Evaluates cheating rules for monitored students.
    
    Supports two cheating modes:
      1. Gaze-based: Student looks at a neighbor's paper for > threshold time
      2. Phone-based: Student is holding/using a phone (immediate flag)
    
    Must run on the main thread — reads/writes is_cheating and
    is_alert_recording fields that are also used by the recording collector.
    """

    def __init__(self, registry: GlobalStudentRegistry, cooldown_frames: int = 30, clock=None):
        self._registry = registry
        self._cooldown_frames = cooldown_frames
        self._on_alert: Callable | None = None
        # Grace period: if face/gaze disappears briefly, don't reset the
        # suspicious timer immediately.  Only reset after GRACE_PERIOD seconds
        # of continuous face loss.  This prevents detection glitches from
        # interrupting a genuine cheating event.
        self._face_lost_times: dict[int, float] = {}  # track_id → time face was lost
        self._GRACE_PERIOD: float = 2.0  # seconds
        self._vlog = get_video_logger()
        # Fix T-1: use SimClock when available so that file-based sources
        # (where SimClock advances at a different rate than wall time) produce
        # correct suspicious-duration thresholds.
        self._clock = clock

        # Intercept registry update to reset is_using_phone at the start of every frame
        original_update = registry.update
        def patched_update(*args, **kwargs):
            for state in registry.get_all():
                state.is_using_phone = False
            expired_states = original_update(*args, **kwargs)
            for state in expired_states:
                self._face_lost_times.pop(state.track_id, None)
            return expired_states
        registry.update = patched_update

    @property
    def on_alert(self):
        return self._on_alert
    
    @on_alert.setter
    def on_alert(self, callback):
        self._on_alert = callback

    def _handle_face_lost(self, state, track_id: int, current_time: float) -> None:
        """Called when face mesh or gaze is unavailable for a student.

        Implements a grace period: the suspicious_start_time is preserved for
        up to GRACE_PERIOD seconds of continuous face loss.  This prevents
        brief detection glitches from resetting a genuine cheating event.
        After the grace period expires, the timer is cleared as usual.
        """
        now = current_time

        # Record the moment the face was first lost (don't overwrite if already set)
        if track_id not in self._face_lost_times:
            self._face_lost_times[track_id] = now

        face_lost_duration = now - self._face_lost_times[track_id]

        if face_lost_duration < self._GRACE_PERIOD:
            # Within grace period — keep suspicious_start_time intact so the
            # cheating timer continues when the face reappears.
            # Still tick down the is_cheating cooldown to avoid eternal red box.
            if state.is_cheating and not state.is_using_phone:
                state.cheating_cooldown -= 1
                if state.cheating_cooldown <= 0:
                    state.is_cheating = False
                    state.cheating_cooldown = 0
                    state.cheating_target_paper = None
                    state.cheating_target_neighbor = None
            self._vlog.log_gaze_check(
                track_id=track_id,
                is_looking=False,
                dot_product=None,
                paper=None,
                matched_neighbor=None,
                suspicious_sec=0.0,
                is_cheating=state.is_cheating,
                cheating_cooldown=state.cheating_cooldown,
                face_available=False,
                in_grace_period=True,
            )
        else:
            # Grace period expired — keep the entry in _face_lost_times so every
            # subsequent face-absent frame immediately enters this post-grace branch
            # and decrements cheating_cooldown each frame until is_cheating clears.
            # Removing the entry (old behaviour) reset the 2-second grace timer on
            # every call, creating a cycle that prevented cooldown from ever reaching 0.
            state.suspicious_start_time = 0.0
            if state.is_cheating and not state.is_using_phone:
                state.cheating_cooldown -= 1
                if state.cheating_cooldown <= 0:
                    state.is_cheating = False
                    state.cheating_cooldown = 0
                    state.cheating_target_paper = None
                    state.cheating_target_neighbor = None
            self._vlog.log_gaze_check(
                track_id=track_id,
                is_looking=False,
                dot_product=None,
                paper=None,
                matched_neighbor=None,
                suspicious_sec=0.0,
                is_cheating=state.is_cheating,
                cheating_cooldown=state.cheating_cooldown,
                face_available=False,
                in_grace_period=False,
            )

    def evaluate(self, track_id: int, current_time: float) -> None:
        """
        Evaluate cheating rules for a single student.
        
        Called synchronously on the main thread for each selected student.
        """
        state = self._registry.get(track_id)
        # Split state, face_mesh, and surrounding_papers checks to avoid incorrectly running the face-lost timer when neighbor papers are not yet assigned.
        if not state:
            return
        # Snapshot face_mesh into a local variable to prevent a TOCTOU race
        # condition: the FM worker thread can write None to state.face_mesh
        # between our guard check here and any subsequent attribute access below.
        face_mesh = state.face_mesh
        if not face_mesh:
            self._handle_face_lost(state, track_id, current_time)
            return
        # face is present — clear any face-lost timer
        self._face_lost_times.pop(track_id, None)
        if not state.surrounding_papers:
            # no neighbor papers yet — skip evaluation without touching timers
            return

        # Use shared gaze computation (single source of truth with visualizer)
        gaze_dir = compute_gaze_direction(face_mesh)
        if gaze_dir is None:
            self._handle_face_lost(state, track_id, current_time)
            return

        # Face is present — clear any grace period timer
        self._face_lost_times.pop(track_id, None)

        lm2d = face_mesh.landmarks_2d
        def pt2d(idx):
            return np.array(lm2d[idx], dtype=float)

        # Check intersection with surrounding papers
        student_head_pos = pt2d(168)
        is_looking_at_paper = False
        matched_paper = None      # The specific paper coords being looked at
        matched_neighbor = None   # The track_id of the student who owns that paper
        
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
                matched_paper = paper_pt
                # Identify which neighbor owns this paper
                for neighbor_id in state.neighbors:
                    n_state = self._registry.get(neighbor_id)
                    if n_state and n_state.detected_paper == paper_pt:
                        matched_neighbor = neighbor_id
                        break
                break

        # Apply the suspicious duration rule from settings
        duration_threshold = settings.suspicious_duration_threshold
        
        # Compute the best dot product for logging (max over all papers).
        # Use the already-snapshotted lm2d (avoids re-accessing state.face_mesh
        # which may be None by now due to the FM worker thread).
        best_dot: float | None = None
        head_pos_log = np.array(lm2d[168], dtype=float)
        for pp in state.surrounding_papers:
            pv = np.array(pp) - head_pos_log
            d = np.linalg.norm(pv)
            if d > 1e-6:
                dp = float(np.dot(gaze_dir, pv / d))
                if best_dot is None or dp > best_dot:
                    best_dot = dp

        if is_looking_at_paper:
            # Store the cheating target for annotated alert video rendering
            state.cheating_target_paper = matched_paper
            state.cheating_target_neighbor = matched_neighbor
            
            # Reset cooldown whenever student is looking at a paper
            state.cheating_cooldown = self._cooldown_frames
            
            if state.suspicious_start_time == 0.0:
                state.suspicious_start_time = current_time
            elif current_time - state.suspicious_start_time >= duration_threshold:
                if not state.is_cheating:
                    state.is_cheating = True
                    paper_source = "heuristic" if state.is_heuristic_paper else "YOLO"
                    victim_info = f", victim=Track {matched_neighbor}" if matched_neighbor else ""
                    logger.warning(
                        f"CHEATING DETECTED: Track {track_id} looking at neighbor paper "
                        f"for {duration_threshold}s (paper_source={paper_source}{victim_info})"
                    )
                    self._vlog.log_cheating_detected(
                        track_id=track_id,
                        victim_id=matched_neighbor,
                        paper=matched_paper,
                        paper_source=paper_source,
                        duration_sec=current_time - state.suspicious_start_time,
                    )
                    # Fire the on_alert callback
                    if self._on_alert is not None:
                        try:
                            self._on_alert(state)
                        except Exception as e:
                            logger.error(f"on_alert callback error: {e}")

            # Log the gaze check result
            self._vlog.log_gaze_check(
                track_id=track_id,
                is_looking=True,
                dot_product=best_dot,
                paper=matched_paper,
                matched_neighbor=matched_neighbor,
                suspicious_sec=current_time - state.suspicious_start_time if state.suspicious_start_time > 0 else 0.0,
                is_cheating=state.is_cheating,
                cheating_cooldown=state.cheating_cooldown,
                face_available=True,
                in_grace_period=False,
            )
        else:
            state.suspicious_start_time = 0.0
            state.cheating_target_paper = None
            state.cheating_target_neighbor = None
            # Use cooldown: don't immediately clear is_cheating.
            # This prevents oscillation from brief gaze breaks.
            if state.is_cheating and not state.is_using_phone:
                state.cheating_cooldown -= 1
                if state.cheating_cooldown <= 0:
                    state.is_cheating = False
                    state.cheating_cooldown = 0
                    state.cheating_target_paper = None
                    state.cheating_target_neighbor = None

            # Log the gaze check result (not looking at any paper)
            self._vlog.log_gaze_check(
                track_id=track_id,
                is_looking=False,
                dot_product=best_dot,
                paper=None,
                matched_neighbor=None,
                suspicious_sec=0.0,
                is_cheating=state.is_cheating,
                cheating_cooldown=state.cheating_cooldown,
                face_available=True,
                in_grace_period=False,
            )
