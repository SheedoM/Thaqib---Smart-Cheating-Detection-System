"""
Shared gaze direction computation.

Extracts a 2D gaze direction vector from a FaceMeshResult using
MediaPipe's head rotation matrix and iris landmark deviations.

Used by both pipeline.py (cheating evaluation) and visualizer.py (drawing).
"""

import numpy as np

from thaqib.video.face_mesh import FaceMeshResult


def compute_gaze_direction(face_mesh: FaceMeshResult) -> np.ndarray | None:
    """
    Compute a normalized 2D gaze direction vector from face mesh data.

    Combines the 3D head orientation (from MediaPipe's rotation matrix)
    with 2D iris deviation to produce a screen-space gaze direction.

    Args:
        face_mesh: FaceMeshResult containing landmarks and head matrix.

    Returns:
        A (2,) numpy array (dx, dy) unit vector in screen space,
        or None if the mesh is invalid or insufficient.
    """
    lm2d = face_mesh.landmarks_2d
    head_matrix = face_mesh.head_matrix

    if len(lm2d) < 474 or head_matrix is None:
        return None

    def pt2d(idx: int) -> np.ndarray:
        return np.array(lm2d[idx], dtype=float)

    # 1. Base 3D Head Direction (MediaPipe 3D Space: +X is Left, -X is Right)
    R = head_matrix[:3, :3]
    head_3d = R @ np.array([0.0, 0.0, -1.0])

    # 2. Eye Deviation (Screen Space: +X is Right, -X is Left)
    l_center = (pt2d(33) + pt2d(133)) / 2.0
    r_center = (pt2d(263) + pt2d(362)) / 2.0
    avg_eye_dev = ((pt2d(468) - l_center) + (pt2d(473) - r_center)) / 2.0

    # Normalize by eye width
    eye_width = np.linalg.norm(pt2d(33) - pt2d(133))
    if eye_width > 1e-6:
        avg_eye_dev /= eye_width

    # 3. Combine in 3D Space (Coordinate Alignment)
    # CRITICAL FIX: Invert Eye X-axis to match MediaPipe's 3D Space
    eye_3d = np.array([-avg_eye_dev[0], avg_eye_dev[1], 0.0]) * 3.0
    combined_3d = head_3d + eye_3d

    # 4. Project to 2D Screen Space (Convert +X=Left back to +X=Right for drawing)
    gaze_dir = np.array([-combined_3d[0], combined_3d[1]])
    norm_gaze = np.linalg.norm(gaze_dir)
    if norm_gaze < 1e-6:
        return None

    return gaze_dir / norm_gaze
