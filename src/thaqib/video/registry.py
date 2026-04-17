"""
Global student spatial registry system.

Stores the spatial state of all tracked students for the current frame.
"""

from collections import deque
from dataclasses import dataclass, field
import numpy as np

from thaqib.video.tracker import TrackedObject
from thaqib.video.face_mesh import FaceMeshResult


# Maximum frames kept in the per-student recording buffer (~10s at 30fps).
# Each 720p frame ≈ 2.7MB → 300 frames ≈ 810MB worst-case per student.
_MAX_RECORDING_FRAMES = 300


@dataclass
class StudentSpatialState:
    """Private spatial state of a student for the current frame."""

    track_id: int
    bbox: tuple[int, int, int, int]
    center: tuple[int, int]
    paper_center: tuple[int, int]
    frame_index: int
    timestamp: float

    # Persistence fields
    last_seen_frame: int = 0
    last_seen_time: float = 0.0
    face_embedding: np.ndarray | None = None
    face_mesh: FaceMeshResult | None = None
    is_active: bool = True

    # Dynamically added fields by NeighborComputer
    neighbors: list[int] = field(default_factory=list)
    neighbor_distances: dict[int, float] = field(default_factory=dict)
    neighbor_papers: dict[int, tuple[int, int]] = field(default_factory=dict)
    detected_paper: tuple[int, int] | None = None
    is_heuristic_paper: bool = False  # True = paper_center fallback, False = YOLO detected
    surrounding_papers: list[tuple[int, int]] = field(default_factory=list)
    is_cheating: bool = False
    suspicious_start_time: float = 0.0
    cheating_cooldown: int = 0  # Frames remaining before is_cheating can be cleared
    cheating_target_paper: tuple[int, int] | None = None   # Exact paper coords being copied
    cheating_target_neighbor: int | None = None             # Track ID of the victim student
    
    # Phone cheating state
    is_using_phone: bool = False
    phone_bbox: tuple[int, int, int, int] | None = None    # Phone bounding box if detected

    # Alert recording state
    is_alert_recording: bool = False
    recording_buffer: deque = field(default_factory=lambda: deque(maxlen=_MAX_RECORDING_FRAMES))
    frames_to_record: int = 0

class GlobalStudentRegistry:
    """Registry system that stores the spatial state of all tracked students."""

    def __init__(self):
        self._states: dict[int, StudentSpatialState] = {}

    def update(self, tracks: list[TrackedObject], frame_index: int, timestamp: float) -> list[int]:
        """
        Update registry with new tracking data.
        Does not delete lost students immediately (keeps for 10 seconds).
        Returns a list of expired track IDs that were purged.
        """
        active_ids = {t.track_id for t in tracks}

        # 1. Update or add new tracks
        for track in tracks:
            if track.track_id in self._states:
                state = self._states[track.track_id]
                state.bbox = track.bbox
                state.center = track.center
                state.paper_center = track.paper_center
                state.frame_index = frame_index
                state.timestamp = timestamp
                state.last_seen_frame = frame_index
                state.last_seen_time = timestamp
                state.is_active = True
            else:
                self._states[track.track_id] = StudentSpatialState(
                    track_id=track.track_id,
                    bbox=track.bbox,
                    center=track.center,
                    paper_center=track.paper_center,
                    frame_index=frame_index,
                    timestamp=timestamp,
                    last_seen_frame=frame_index,
                    last_seen_time=timestamp,
                    is_active=True,
                )

        # 2. Handle lost tracks (purge if older than 10 seconds)
        expired_ids = []
        for track_id, state in self._states.items():
            if track_id not in active_ids:
                state.is_active = False
                if timestamp - state.last_seen_time > 10.0:
                    expired_ids.append(track_id)
        
        for tid in expired_ids:
            del self._states[tid]
            
        return expired_ids

    def get(self, track_id: int) -> StudentSpatialState | None:
        """Get spatial state for a specific track ID."""
        return self._states.get(track_id)

    def get_all(self) -> list[StudentSpatialState]:
        """Get all spatial states."""
        return list(self._states.values())

    def purge(self, track_id: int) -> None:
        """Immediately remove a track from the registry."""
        self._states.pop(track_id, None)
