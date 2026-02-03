"""
Neighbor modeling and risk angle calculation.

Identifies spatial relationships between students and defines risky gaze directions.
"""

import logging
import math
from dataclasses import dataclass, field

from thaqib.config import get_settings
from thaqib.video.tracker import TrackedObject, TrackingResult

logger = logging.getLogger(__name__)


@dataclass
class PaperZone:
    """Estimated paper zone for a student."""

    center: tuple[int, int]
    top_left: tuple[int, int]
    bottom_right: tuple[int, int]

    @property
    def width(self) -> int:
        return self.bottom_right[0] - self.top_left[0]

    @property
    def height(self) -> int:
        return self.bottom_right[1] - self.top_left[1]


@dataclass
class Neighbor:
    """A neighboring student with spatial relationship data."""

    track_id: int
    center: tuple[int, int]
    distance: float
    relative_angle: float  # Angle from target to neighbor in degrees
    paper_zone: PaperZone
    paper_risk_angle: float  # Angle from target to neighbor's paper


@dataclass
class RiskAngleRange:
    """Angular range representing a risky gaze direction."""

    center_angle: float
    min_angle: float
    max_angle: float
    neighbor_id: int

    def contains(self, angle: float) -> bool:
        """Check if the given angle falls within this risk range."""
        # Handle angle wraparound
        normalized = self._normalize_angle(angle)
        min_n = self._normalize_angle(self.min_angle)
        max_n = self._normalize_angle(self.max_angle)

        if min_n <= max_n:
            return min_n <= normalized <= max_n
        else:
            # Range crosses 180/-180 boundary
            return normalized >= min_n or normalized <= max_n

    @staticmethod
    def _normalize_angle(angle: float) -> float:
        """Normalize angle to [-180, 180] range."""
        while angle > 180:
            angle -= 360
        while angle < -180:
            angle += 360
        return angle


@dataclass
class StudentSpatialContext:
    """Spatial context for a monitored student."""

    track_id: int
    center: tuple[int, int]
    paper_zone: PaperZone
    neighbors: list[Neighbor] = field(default_factory=list)
    risk_angles: list[RiskAngleRange] = field(default_factory=list)

    def get_matching_risk(self, gaze_yaw: float) -> RiskAngleRange | None:
        """
        Check if gaze direction matches any risk angle.

        Args:
            gaze_yaw: Gaze yaw angle in degrees.

        Returns:
            Matching RiskAngleRange if found, None otherwise.
        """
        for risk in self.risk_angles:
            if risk.contains(gaze_yaw):
                return risk
        return None


class NeighborModeler:
    """
    Models spatial relationships between students.

    Calculates distances, identifies neighbors, estimates paper zones,
    and defines risk angles for each monitored student.

    Example:
        >>> modeler = NeighborModeler()
        >>> contexts = modeler.compute(tracking_result)
        >>> for ctx in contexts:
        ...     print(f"Student {ctx.track_id} has {len(ctx.neighbors)} neighbors")
        ...     for risk in ctx.risk_angles:
        ...         print(f"  Risk angle toward student {risk.neighbor_id}: {risk.center_angle:.1f}°")
    """

    def __init__(
        self,
        distance_threshold: int | None = None,
        k_neighbors: int | None = None,
        risk_angle_tolerance: float | None = None,
        paper_offset_ratio: float = 0.3,
    ):
        """
        Initialize neighbor modeler.

        Args:
            distance_threshold: Maximum distance (pixels) to consider as neighbor.
            k_neighbors: Number of nearest neighbors to track.
            risk_angle_tolerance: Angular tolerance (degrees) for risk angles.
            paper_offset_ratio: Ratio of bbox height for paper zone offset.
        """
        settings = get_settings()

        self.distance_threshold = distance_threshold or settings.neighbor_distance_threshold
        self.k_neighbors = k_neighbors or settings.neighbor_k
        self.risk_angle_tolerance = risk_angle_tolerance or settings.risk_angle_tolerance
        self.paper_offset_ratio = paper_offset_ratio

    def compute(
        self,
        tracking_result: TrackingResult,
        selected_only: bool = True,
    ) -> list[StudentSpatialContext]:
        """
        Compute spatial context for all tracked students.

        Args:
            tracking_result: Current tracking result.
            selected_only: If True, only compute for selected (monitored) students.

        Returns:
            List of StudentSpatialContext for each student.
        """
        # Filter tracks
        if selected_only:
            target_tracks = [t for t in tracking_result.tracks if t.is_selected]
        else:
            target_tracks = tracking_result.tracks

        # All tracks are potential neighbors
        all_tracks = tracking_result.tracks

        contexts = []
        for target in target_tracks:
            # Estimate paper zone for target
            paper_zone = self._estimate_paper_zone(target)

            # Find neighbors
            neighbors = self._find_neighbors(target, all_tracks)

            # Calculate risk angles
            risk_angles = self._calculate_risk_angles(target, neighbors)

            contexts.append(
                StudentSpatialContext(
                    track_id=target.track_id,
                    center=target.center,
                    paper_zone=paper_zone,
                    neighbors=neighbors,
                    risk_angles=risk_angles,
                )
            )

        return contexts

    def _estimate_paper_zone(self, track: TrackedObject) -> PaperZone:
        """
        Estimate the paper zone for a student.

        Assumes the paper is positioned below the student's center,
        offset by a ratio of the bounding box height.
        """
        cx, cy = track.center
        w, h = track.width, track.height

        # Paper is below and slightly in front of the student
        paper_offset_y = int(h * self.paper_offset_ratio)
        paper_width = int(w * 0.6)
        paper_height = int(h * 0.3)

        paper_cx = cx
        paper_cy = cy + paper_offset_y

        return PaperZone(
            center=(paper_cx, paper_cy),
            top_left=(paper_cx - paper_width // 2, paper_cy - paper_height // 2),
            bottom_right=(paper_cx + paper_width // 2, paper_cy + paper_height // 2),
        )

    def _find_neighbors(
        self,
        target: TrackedObject,
        all_tracks: list[TrackedObject],
    ) -> list[Neighbor]:
        """Find k-nearest neighbors within distance threshold."""
        neighbors = []

        for track in all_tracks:
            if track.track_id == target.track_id:
                continue

            # Calculate distance
            distance = self._distance(target.center, track.center)

            if distance > self.distance_threshold:
                continue

            # Calculate relative angle
            relative_angle = self._angle_to(target.center, track.center)

            # Estimate paper zone for neighbor
            paper_zone = self._estimate_paper_zone(track)

            # Calculate risk angle (angle to neighbor's paper)
            paper_risk_angle = self._angle_to(target.center, paper_zone.center)

            neighbors.append(
                Neighbor(
                    track_id=track.track_id,
                    center=track.center,
                    distance=distance,
                    relative_angle=relative_angle,
                    paper_zone=paper_zone,
                    paper_risk_angle=paper_risk_angle,
                )
            )

        # Sort by distance and take k-nearest
        neighbors.sort(key=lambda n: n.distance)
        return neighbors[: self.k_neighbors]

    def _calculate_risk_angles(
        self,
        target: TrackedObject,
        neighbors: list[Neighbor],
    ) -> list[RiskAngleRange]:
        """Calculate risk angle ranges for all neighbors."""
        risk_angles = []

        for neighbor in neighbors:
            center_angle = neighbor.paper_risk_angle

            risk_angles.append(
                RiskAngleRange(
                    center_angle=center_angle,
                    min_angle=center_angle - self.risk_angle_tolerance,
                    max_angle=center_angle + self.risk_angle_tolerance,
                    neighbor_id=neighbor.track_id,
                )
            )

        return risk_angles

    @staticmethod
    def _distance(p1: tuple[int, int], p2: tuple[int, int]) -> float:
        """Calculate Euclidean distance between two points."""
        return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)

    @staticmethod
    def _angle_to(from_point: tuple[int, int], to_point: tuple[int, int]) -> float:
        """
        Calculate angle from one point to another.

        Returns angle in degrees where:
        - 0° is right
        - 90° is down (positive y)
        - ±180° is left
        - -90° is up
        """
        dx = to_point[0] - from_point[0]
        dy = to_point[1] - from_point[1]
        return math.degrees(math.atan2(dy, dx))
