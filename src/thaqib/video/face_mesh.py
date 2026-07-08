"""
Face mesh data type.

`FaceMeshResult` is the shared container for one student's extracted face mesh,
consumed by the gaze, registry, re-id and pipeline modules. The actual mesh
inference for the live pipeline lives in ``VideoPipeline._fm_thread_infer``
(per-thread MediaPipe FaceLandmarker in IMAGE mode); the older
``FaceMeshExtractor`` VIDEO-mode wrapper that used to live here was unused and
has been removed.
"""

from dataclasses import dataclass

import numpy as np


@dataclass
class FaceMeshResult:
    """
    Extracted face mesh for one student.

    Attributes:
        landmarks_2d: 478 pixel coordinates (x, y) in the original full frame.
        landmarks_3d: 478 metric coordinates (x, y, z); x/y in frame pixels,
                      z is the MediaPipe depth value (negative = closer to camera).
        bbox: The student bounding box used for this result (x1, y1, x2, y2).
        head_matrix: 4x4 facial transformation matrix from MediaPipe (rotation + translation).
                     The Z-column (matrix[:3, 2]) gives the head forward direction vector.
    """

    landmarks_2d: list[tuple[int, int]]
    landmarks_3d: list[tuple[float, float, float]]
    bbox: tuple[int, int, int, int]
    head_matrix: np.ndarray | None = None

    @property
    def count(self) -> int:
        """Number of landmarks."""
        return len(self.landmarks_2d)
