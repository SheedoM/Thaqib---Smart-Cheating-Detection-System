"""
Global student spatial registry system.

Stores the spatial state of all tracked students for the current frame.
"""

from dataclasses import dataclass, field
import numpy as np

from thaqib.video.tracker import TrackedObject
from thaqib.video.face_mesh import FaceMeshResult


@dataclass
class StudentSpatialState:
    """Private spatial state of a student for the current frame."""

    track_id: int
    bbox: tuple[int, int, int, int]
    center: tuple[int, int]
    frame_index: int
    timestamp: float

    # Persistence fields
    last_seen_frame: int = 0
    last_seen_time: float = 0.0
    face_embedding: np.ndarray | None = None
    face_mesh: FaceMeshResult | None = None
    is_active: bool = True

    # Appearance embedding (EMA-smoothed)
    appearance_embedding: np.ndarray | None = None
    embedding_count: int = 0

    # Dynamically added fields by NeighborComputer
    neighbors: list[int] = field(default_factory=list)
    neighbor_distances: dict[int, float] = field(default_factory=dict)

    def update_embedding(self, new_embedding: np.ndarray) -> None:
        """
        Blend a new embedding into the appearance model via exponential
        moving average:  E_new = 0.8 * E_old + 0.2 * current
        First observation is stored directly.
        """
        if self.appearance_embedding is None:
            self.appearance_embedding = new_embedding.copy()
        else:
            blended = 0.8 * self.appearance_embedding + 0.2 * new_embedding
            norm = np.linalg.norm(blended)
            if norm > 1e-6:
                blended /= norm
            self.appearance_embedding = blended
        self.embedding_count += 1


class GlobalStudentRegistry:
    """Registry system that stores the spatial state of all tracked students."""

    def __init__(self):
        self._states: dict[int, StudentSpatialState] = {}

    def update(self, tracks: list[TrackedObject], frame_index: int, timestamp: float) -> None:
        """
        Update registry with new tracking data.
        Does not delete lost students immediately (keeps for 10 seconds).
        """
        active_ids = {t.track_id for t in tracks}

        # 1. Update or add new tracks
        for track in tracks:
            if track.track_id in self._states:
                state = self._states[track.track_id]
                state.bbox = track.bbox
                state.center = track.center
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

    def get(self, track_id: int) -> StudentSpatialState | None:
        """Get spatial state for a specific track ID."""
        return self._states.get(track_id)

    def get_all(self) -> list[StudentSpatialState]:
        """Get all spatial states."""
        return list(self._states.values())
