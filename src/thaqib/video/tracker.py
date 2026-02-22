"""
Object tracking using BoT-SORT via boxmot library.

Maintains persistent identity for detected humans across frames.
Extended with per-track bbox smoothing, lost-track memory, and
ID locking.
"""

import logging
import inspect
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from boxmot.trackers.botsort.bot_sort import BoTSORT

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
    label: str = ""            # Optional student label/name
    is_predicted: bool = False # True when position is a stability-filter injection

    @property
    def center(self) -> tuple[int, int]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    @property
    def width(self) -> int:
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> int:
        return self.bbox[3] - self.bbox[1]


@dataclass
class TrackingResult:
    """Result of tracking on a single frame."""

    frame_index: int
    timestamp: float
    tracks: list[TrackedObject] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.tracks)

    @property
    def selected_count(self) -> int:
        return sum(1 for t in self.tracks if t.is_selected)

    def get_by_id(self, track_id: int) -> TrackedObject | None:
        for track in self.tracks:
            if track.track_id == track_id:
                return track
        return None


class ObjectTracker:
    """
    BoT-SORT based object tracker.

    BoT-SORT contains its own internal Kalman filter and ReID for motion
    prediction and assignment. This class adds:
      - Per-track bbox EMA smoothing (0.7 × prev + 0.3 × current).
      - Lost-track position memory for the detection stability filter.
      - ID locking: track ID is frozen after 10 consecutive positive matches.
    """

    def __init__(
        self,
        max_distance: int | None = None,
        max_age: int | None = None,
    ):
        settings = get_settings()

        self.max_distance = max_distance or settings.tracking_max_distance
        self.max_age = max_age or settings.tracking_max_age

        self._tracker = BoTSORT(
            reid_weights=Path("models/osnet_x0_25_msmt17.pt"),
            device="cpu",
            half=False,
            with_reid=True,
            track_high_thresh=0.25,
            track_low_thresh=0.05,
            new_track_thresh=0.4,
            track_buffer=300,
            match_thresh=0.8
        )

        # Per-track smoothed bbox (EMA)
        self._smoothed_bboxes: dict[int, tuple[int, int, int, int]] = {}

        # Last-known bbox for the detection stability filter
        self._last_known_bbox: dict[int, tuple[int, int, int, int]] = {}

        # Track selection state
        self._selected_ids: set[int] = set()
        self._track_labels: dict[int, str] = {}

        # ID locking (requires 10 consecutive embedding matches)
        self._locked_ids: set[int] = set()
        self._match_counts: dict[int, int] = {}

    # ------------------------------------------------------------------
    # Predicted bbox (for detection stability filter in pipeline)
    # ------------------------------------------------------------------

    def get_predicted_bbox(self, track_id: int) -> tuple[int, int, int, int] | None:
        """
        Return the last-known smoothed bbox for a temporarily missing track.
        """
        return self._last_known_bbox.get(track_id)

    # ------------------------------------------------------------------
    # ID locking
    # ------------------------------------------------------------------

    def verify_embedding_match(self, track_id: int, is_match: bool) -> None:
        """Lock ID after 10 consecutive successful embedding matches."""
        self._match_counts.setdefault(track_id, 0)
        if is_match:
            self._match_counts[track_id] += 1
            if self._match_counts[track_id] >= 10:
                if track_id not in self._locked_ids:
                    logger.info(f"ID LOCK: Track {track_id} permanently locked.")
                self._locked_ids.add(track_id)
        else:
            if track_id not in self._locked_ids:
                self._match_counts[track_id] = 0

    def is_locked(self, track_id: int) -> bool:
        return track_id in self._locked_ids

    # ------------------------------------------------------------------
    # Core update
    # ------------------------------------------------------------------

    def update(self, detection_result: DetectionResult, frame: np.ndarray) -> TrackingResult:
        """Update tracker with new detections and apply bbox smoothing."""

        # Guard: frame must be a valid 3D BGR image (H, W, 3)
        if frame is None or not isinstance(frame, np.ndarray) or len(frame.shape) != 3:
            return TrackingResult(
                frame_index=detection_result.frame_index,
                timestamp=detection_result.timestamp,
                tracks=[],
            )

        if detection_result.count == 0:
            dets = np.empty((0, 6), dtype=float)
        else:
            dets = np.array([
                [d.bbox[0], d.bbox[1], d.bbox[2], d.bbox[3], d.confidence, d.class_id]
                for d in detection_result.detections
            ], dtype=float)

        tracked = self._tracker.update(dets, frame)

        tracks: list[TrackedObject] = []

        if tracked is not None and len(tracked) > 0:
            for t in tracked:
                track_id = int(t[4])
                conf_val = float(t[5]) if len(t) > 5 else 1.0
                raw_bbox = (int(t[0]), int(t[1]), int(t[2]), int(t[3]))

                # EMA bbox smoothing (0.7 × prev + 0.3 × current)
                if track_id in self._smoothed_bboxes:
                    pb = self._smoothed_bboxes[track_id]
                    sx1 = int(0.7 * pb[0] + 0.3 * raw_bbox[0])
                    sy1 = int(0.7 * pb[1] + 0.3 * raw_bbox[1])
                    sx2 = int(0.7 * pb[2] + 0.3 * raw_bbox[2])
                    sy2 = int(0.7 * pb[3] + 0.3 * raw_bbox[3])
                    smoothed = (sx1, sy1, sx2, sy2)
                else:
                    smoothed = raw_bbox

                self._smoothed_bboxes[track_id] = smoothed
                self._last_known_bbox[track_id] = smoothed

                tracks.append(TrackedObject(
                    track_id=track_id,
                    bbox=smoothed,
                    confidence=conf_val,
                    is_selected=track_id in self._selected_ids,
                    label=self._track_labels.get(track_id, ""),
                ))

        return TrackingResult(
            frame_index=detection_result.frame_index,
            timestamp=detection_result.timestamp,
            tracks=tracks,
        )

    # ------------------------------------------------------------------
    # Selection management
    # ------------------------------------------------------------------

    def select_tracks(self, track_ids: list[int]) -> None:
        self._selected_ids = set(track_ids)
        logger.info(f"Selected tracks: {self._selected_ids}")

    def add_selection(self, track_id: int) -> None:
        self._selected_ids.add(track_id)
        logger.info(f"Added track {track_id} to selection")

    def remove_selection(self, track_id: int) -> None:
        self._selected_ids.discard(track_id)
        logger.info(f"Removed track {track_id} from selection")

    def clear_selection(self) -> None:
        self._selected_ids.clear()
        logger.info("Cleared all track selections")

    def set_label(self, track_id: int, label: str) -> None:
        self._track_labels[track_id] = label

    def get_selected_ids(self) -> set[int]:
        return self._selected_ids.copy()

    def reset(self) -> None:
        self._tracker = BoTSORT(
            reid_weights=Path("models/osnet_x0_25_msmt17.pt"),
            device="cpu",
            half=False,
            with_reid=True,
            track_high_thresh=0.25,
            track_low_thresh=0.05,
            new_track_thresh=0.4,
            track_buffer=300,
            match_thresh=0.8
        )
        self._smoothed_bboxes.clear()
        self._last_known_bbox.clear()
        self._selected_ids.clear()
        self._track_labels.clear()
        self._locked_ids.clear()
        self._match_counts.clear()
        logger.info("Tracker reset")
