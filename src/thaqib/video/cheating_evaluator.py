"""
Cheating evaluation module.

Extracted from pipeline.py (P2 Fix 11) to reduce monolithic complexity.
Evaluates gaze-based and phone-based cheating rules synchronously on the
main thread to ensure state consistency with the alert recording collector.
"""

import math
import time
import logging

import numpy as np

from thaqib.config import get_settings
from thaqib.video.registry import GlobalStudentRegistry
from thaqib.video.gaze import compute_gaze_direction


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

    def __init__(self, registry: GlobalStudentRegistry, cooldown_frames: int = 30):
        self._registry = registry
        self._cooldown_frames = cooldown_frames
        self._on_alert: callable = None

    @property
    def on_alert(self):
        return self._on_alert
    
    @on_alert.setter
    def on_alert(self, callback):
        self._on_alert = callback

    def evaluate(self, track_id: int) -> None:
        """
        Evaluate cheating rules for a single student.
        
        Called synchronously on the main thread for each selected student.
        """
        state = self._registry.get(track_id)
        if not state or not state.face_mesh or not state.surrounding_papers:
            if state:
                state.suspicious_start_time = 0.0
                # Freeze cooldown when face is undetected, BUT cap the freeze
                # at 90 frames (~3s). After that, decrement anyway so the
                # red box doesn't stay forever.
                if state.is_cheating and not state.is_using_phone:
                    state.cheating_cooldown -= 1
                    if state.cheating_cooldown <= -90:
                        state.is_cheating = False
                        state.cheating_cooldown = 0
                        state.cheating_target_paper = None
                        state.cheating_target_neighbor = None
            return

        # Use shared gaze computation (single source of truth with visualizer)
        gaze_dir = compute_gaze_direction(state.face_mesh)
        if gaze_dir is None:
            state.suspicious_start_time = 0.0
            # Same freeze logic for invalid gaze
            if state.is_cheating and not state.is_using_phone:
                state.cheating_cooldown -= 1
                if state.cheating_cooldown <= -90:
                    state.is_cheating = False
                    state.cheating_cooldown = 0
                    state.cheating_target_paper = None
                    state.cheating_target_neighbor = None
            return

        lm2d = state.face_mesh.landmarks_2d
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
        current_time = time.time()
        duration_threshold = settings.suspicious_duration_threshold
        
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
                    # Fire the on_alert callback
                    if self._on_alert is not None:
                        try:
                            self._on_alert(state)
                        except Exception as e:
                            logger.error(f"on_alert callback error: {e}")
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
