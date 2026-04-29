"""
Shared gaze direction computation.
Extracts 2D gaze vector using MediaPipe head matrix and iris deviations.
"""

import numpy as np

from thaqib.video.face_mesh import FaceMeshResult

# Weight applied to iris deviation when blending it with head pose.
# Higher values make iris movement dominate; lower values make head pose dominate.
# 3.0 is empirically calibrated so that ±1 eye-width iris shift ≈ ±45° gaze swing.
_IRIS_WEIGHT = 3.0

# Maximum iris deviation (in normalized eye-width units) before clamping.
# Deviations beyond this are almost certainly noise or partial occlusion of
# the iris landmark, not a real gaze shift. Clamping prevents a single bad
# frame from wildly deflecting the gaze vector.
_IRIS_MAX_DEV = 0.5


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

    # Clamp iris deviation to _IRIS_MAX_DEV to suppress noise / iris occlusion.
    # Beyond half an eye-width, the signal is unreliable on distant or
    # partially-occluded faces.
    iris_mag = np.linalg.norm(avg_eye_dev)
    if iris_mag > _IRIS_MAX_DEV:
        avg_eye_dev = avg_eye_dev * (_IRIS_MAX_DEV / iris_mag)

    # 3. Combine in 3D Space (Invert Eye X-axis to match MediaPipe 3D Space)
    eye_3d = np.array([-avg_eye_dev[0], avg_eye_dev[1], 0.0]) * _IRIS_WEIGHT
    combined_3d = head_3d + eye_3d

    # 4. Project to 2D Screen Space (Convert +X=Left back to +X=Right for drawing)
    gaze_dir = np.array([-combined_3d[0], combined_3d[1]])
    norm_gaze = np.linalg.norm(gaze_dir)
    if norm_gaze < 1e-6:
        return None

    return gaze_dir / norm_gaze
