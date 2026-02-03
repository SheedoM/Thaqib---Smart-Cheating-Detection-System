"""
Object tracking using ByteTrack via supervision library.

Maintains persistent identity for detected humans across frames.
"""

import logging
from dataclasses import dataclass, field

import numpy as np
import supervision as sv

from thaqib.config import get_settings
from thaqib.video.detector import Detection, DetectionResult

logger = logging.getLogger(__name__)


@dataclass
class TrackedObject:
    """A tracked object with persistent identity."""

    track_id: int
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)
    confidence: float
    is_selected: bool = False  # Human-in-the-loop selection
    label: str = ""  # Optional student label/name

    @property
    def center(self) -> tuple[int, int]:
        """Get center point of bounding box."""
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    @property
    def width(self) -> int:
        """Get bounding box width."""
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> int:
        """Get bounding box height."""
        return self.bbox[3] - self.bbox[1]


@dataclass
class TrackingResult:
    """Result of tracking on a single frame."""

    frame_index: int
    timestamp: float
    tracks: list[TrackedObject] = field(default_factory=list)

    @property
    def count(self) -> int:
        """Number of active tracks."""
        return len(self.tracks)

    @property
    def selected_count(self) -> int:
        """Number of selected (monitored) tracks."""
        return sum(1 for t in self.tracks if t.is_selected)

    def get_by_id(self, track_id: int) -> TrackedObject | None:
        """Get track by ID."""
        for track in self.tracks:
            if track.track_id == track_id:
                return track
        return None


class ObjectTracker:
    """
    ByteTrack-based object tracker using supervision library.

    Maintains persistent identities for detected humans across frames.
    Supports human-in-the-loop selection to mark which tracks should be monitored.

    Example:
        >>> tracker = ObjectTracker()
        >>> # On each frame with detections:
        >>> tracking_result = tracker.update(detection_result)
        >>> for track in tracking_result.tracks:
        ...     print(f"Track {track.track_id} at {track.center}")
        >>>
        >>> # Human selects students to monitor:
        >>> tracker.select_tracks([1, 3, 5])
    """

    def __init__(
        self,
        max_distance: int | None = None,
        max_age: int | None = None,
    ):
        """
        Initialize the tracker.

        Args:
            max_distance: Maximum distance (pixels) to associate detections.
                         If None, uses settings.
            max_age: Maximum frames to keep track alive without detection.
                    If None, uses settings.
        """
        settings = get_settings()

        self.max_distance = max_distance or settings.tracking_max_distance
        self.max_age = max_age or settings.tracking_max_age

        # Initialize ByteTrack
        self._tracker = sv.ByteTrack(
            track_activation_threshold=0.25,
            lost_track_buffer=self.max_age,
            minimum_matching_threshold=0.8,
            frame_rate=30,
        )

        # Track selection state
        self._selected_ids: set[int] = set()
        self._track_labels: dict[int, str] = {}

    def update(self, detection_result: DetectionResult) -> TrackingResult:
        """
        Update tracker with new detections.

        Args:
            detection_result: Detection result from HumanDetector.

        Returns:
            TrackingResult with updated tracks.
        """
        # Convert detections to supervision format
        if detection_result.count == 0:
            # No detections - return empty result but keep tracks alive
            detections = sv.Detections.empty()
        else:
            xyxy = np.array([d.bbox for d in detection_result.detections])
            confidence = np.array([d.confidence for d in detection_result.detections])
            class_id = np.array([d.class_id for d in detection_result.detections])

            detections = sv.Detections(
                xyxy=xyxy,
                confidence=confidence,
                class_id=class_id,
            )

        # Update tracker
        tracked_detections = self._tracker.update_with_detections(detections)

        # Convert to TrackedObject list
        tracks = []
        if tracked_detections.tracker_id is not None:
            for i in range(len(tracked_detections)):
                track_id = int(tracked_detections.tracker_id[i])
                bbox = tracked_detections.xyxy[i].astype(int)
                confidence = float(tracked_detections.confidence[i])

                tracks.append(
                    TrackedObject(
                        track_id=track_id,
                        bbox=(int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])),
                        confidence=confidence,
                        is_selected=track_id in self._selected_ids,
                        label=self._track_labels.get(track_id, ""),
                    )
                )

        return TrackingResult(
            frame_index=detection_result.frame_index,
            timestamp=detection_result.timestamp,
            tracks=tracks,
        )

    def select_tracks(self, track_ids: list[int]) -> None:
        """
        Mark tracks as selected for monitoring (human-in-the-loop).

        Args:
            track_ids: List of track IDs to select.
        """
        self._selected_ids = set(track_ids)
        logger.info(f"Selected tracks: {self._selected_ids}")

    def add_selection(self, track_id: int) -> None:
        """Add a single track to selection."""
        self._selected_ids.add(track_id)
        logger.info(f"Added track {track_id} to selection")

    def remove_selection(self, track_id: int) -> None:
        """Remove a single track from selection."""
        self._selected_ids.discard(track_id)
        logger.info(f"Removed track {track_id} from selection")

    def clear_selection(self) -> None:
        """Clear all selections."""
        self._selected_ids.clear()
        logger.info("Cleared all track selections")

    def set_label(self, track_id: int, label: str) -> None:
        """Set label for a track (e.g., student name/ID)."""
        self._track_labels[track_id] = label

    def get_selected_ids(self) -> set[int]:
        """Get set of selected track IDs."""
        return self._selected_ids.copy()

    def reset(self) -> None:
        """Reset tracker state."""
        self._tracker = sv.ByteTrack(
            track_activation_threshold=0.25,
            lost_track_buffer=self.max_age,
            minimum_matching_threshold=0.8,
            frame_rate=30,
        )
        self._selected_ids.clear()
        self._track_labels.clear()
        logger.info("Tracker reset")
