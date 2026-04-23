"""
Face-based Re-Identification Module.
Computes 75-D embeddings from Procrustes-normalized 3D face landmarks.
"""

import logging

import numpy as np

from thaqib.video.face_mesh import FaceMeshResult

logger = logging.getLogger(__name__)


class FaceReIdentifier:
    """
    Manages face embeddings and matches new tracks to known identities.

    Embeddings are 75-D vectors derived from 25 stable, anatomically-spread
    3D landmarks normalized via Procrustes alignment for rotation and scale
    invariance.
    """

    # -----------------------------------------------------------------------
    # Stable landmark indices (MediaPipe 478-point face mesh).
    # Selected for anatomical stability — not affected by mouth/jaw expressions.
    # Covers: nose ridge, eye corners, brow edges, forehead, temples,
    #         cheekbones, jaw references, and chin.
    # -----------------------------------------------------------------------
    _STABLE_POINTS: list[int] = [
        # Nose ridge + tip (most geometrically stable region)
        1, 2, 4, 5, 6, 168, 197,
        # Eye corners (primary Procrustes anchors — also stable features)
        33, 133, 263, 362,
        # Eyebrow outer/inner edges (upper face — not expression-sensitive)
        70, 107, 300, 336,
        # Forehead center + temples
        10, 21, 251,
        # Cheekbone references
        116, 345,
        # Jaw lateral + chin (lower-face structural reference)
        172, 397, 152,
        # Mid-cheek
        50, 280,
    ]

    # Procrustes anchor indices (used for alignment, NOT part of the embedding)
    _LEFT_EYE_OUTER = 33
    _LEFT_EYE_INNER = 133
    _RIGHT_EYE_INNER = 362
    _RIGHT_EYE_OUTER = 263
    _NOSE_TIP = 1

    def __init__(self, match_threshold: float | None = None) -> None:
        """
        Initialize the Re-Identifier.

        Args:
            match_threshold: Minimum cosine similarity [0.0 – 1.0].
                             Defaults to settings.reid_match_threshold.
        """
        from thaqib.config import get_settings
        settings = get_settings()

        self._threshold = match_threshold if match_threshold is not None \
            else getattr(settings, "reid_match_threshold", 0.80)
        self._debug = getattr(settings, "reid_similarity_debug", False)

        # track_id → normalized Procrustes embedding vector
        self._embeddings: dict[int, np.ndarray] = {}
        # Avoid flooding logs with repeated match messages
        self._logged_matches: set[int] = set()

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def remove_embeddings(self, track_ids: list[int]) -> None:
        """Remove embeddings for purged track IDs to prevent memory leaks."""
        for tid in track_ids:
            self._embeddings.pop(tid, None)
            self._logged_matches.discard(tid)

    def compute_embedding(self, face_mesh: FaceMeshResult) -> np.ndarray | None:
        """
        Compute a normalized, Procrustes-aligned embedding from 3D landmarks.

        Returns a 75-D unit vector (25 points × 3 coords), or None if the
        mesh is too small or the Procrustes step fails.
        """
        lm3d = face_mesh.landmarks_3d
        if not lm3d or len(lm3d) < 474:
            return None

        vec = self._procrustes_normalize(lm3d)
        if vec is None:
            return None

        norm = np.linalg.norm(vec)
        if norm < 1e-6:
            return None
        return vec / norm

    def register_embedding(self, track_id: int, face_mesh: FaceMeshResult) -> bool:
        """
        Store or update the embedding for a known track ID.

        Low-quality frames (extreme profile, heavy tilt) are skipped to
        prevent corrupting the stored embedding. EMA alpha is proportional
        to the face's frontality score — frontal faces update faster.

        Returns True if the new embedding matches the stored one (or first time).
        """
        quality = self._mesh_quality_score(face_mesh)

        # Skip very low-quality frames (e.g. >70° profile) entirely
        if quality < 0.30:
            return track_id in self._embeddings

        emb = self.compute_embedding(face_mesh)
        if emb is None:
            return False

        is_match = True
        if track_id in self._embeddings:
            current = self._embeddings[track_id]
            similarity = float(np.dot(emb, current))

            if self._debug:
                logger.debug(
                    f"ReID register — Track {track_id}: "
                    f"similarity={similarity:.3f} quality={quality:.2f}"
                )

            if similarity < self._threshold:
                is_match = False
            else:
                # Quality-weighted EMA:
                #   quality=1.0 → α=0.40 (frontal: update aggressively)
                #   quality=0.30 → α=0.10 (slight profile: update conservatively)
                alpha = 0.10 + 0.30 * quality
                updated = (1.0 - alpha) * current + alpha * emb
                norm = np.linalg.norm(updated)
                if norm > 1e-6:
                    self._embeddings[track_id] = updated / norm
        else:
            self._embeddings[track_id] = emb

        return is_match

    def match(self, face_mesh: FaceMeshResult) -> int | None:
        """Find the best matching known track ID for the given face mesh."""
        result = self.match_with_score(face_mesh)
        return result[0] if result else None

    def match_with_score(self, face_mesh: FaceMeshResult) -> tuple[int, float] | None:
        """
        Find the best matching known track ID and return (track_id, score).

        Iterates ALL stored embeddings (including inactive/lost IDs) so that
        a student who disappeared entirely can still be recovered.
        Returns None if no match exceeds the threshold.
        """
        emb = self.compute_embedding(face_mesh)
        if emb is None:
            return None

        best_id = None
        best_score = -1.0

        for track_id, stored_emb in self._embeddings.items():
            similarity = float(np.dot(emb, stored_emb))
            if similarity > best_score:
                best_score = similarity
                best_id = track_id

        if self._debug and self._embeddings:
            scores = {
                tid: round(float(np.dot(emb, stored)), 3)
                for tid, stored in self._embeddings.items()
            }
            logger.debug(f"ReID scores: {scores} | threshold={self._threshold}")

        if best_score >= self._threshold and best_id is not None:
            if best_id not in self._logged_matches:
                logger.info(
                    f"ReID match found! Restoring track ID {best_id} "
                    f"(Score: {best_score:.3f})"
                )
                self._logged_matches.add(best_id)
            return best_id, best_score

        return None

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _procrustes_normalize(self, lm3d: list) -> np.ndarray | None:
        """
        Pose-normalize 3D landmarks for rotation and scale invariance.

        Algorithm:
          1. Translate: shift centroid to midpoint of the four eye corners.
          2. Scale: divide all coordinates by the inter-ocular distance (IOD).
          3. Rotate: build an orthonormal basis from the eye axis (X) and
             the nose direction (Y, Gram-Schmidt orthogonalized), then apply
             the inverse rotation to bring all points to canonical pose.

        This makes the embedding invariant to:
          - Translation (student moves closer/further, camera pans)
          - Scale (distance from camera changes IOD)
          - Yaw, pitch, and partial roll (head turns up to ~45°)
        """
        # Eye center anchors
        l_eye = (
            np.array(lm3d[self._LEFT_EYE_OUTER], dtype=float) +
            np.array(lm3d[self._LEFT_EYE_INNER], dtype=float)
        ) / 2.0
        r_eye = (
            np.array(lm3d[self._RIGHT_EYE_INNER], dtype=float) +
            np.array(lm3d[self._RIGHT_EYE_OUTER], dtype=float)
        ) / 2.0

        eye_center = (l_eye + r_eye) / 2.0
        iod = np.linalg.norm(r_eye - l_eye)
        if iod < 1e-6:
            return None

        # Extract stable points and translate
        pts = np.array([lm3d[i] for i in self._STABLE_POINTS], dtype=float)
        pts -= eye_center

        # Scale by IOD
        pts /= iod

        # Build canonical rotation basis
        # X-axis: eye-to-eye direction
        eye_vec = r_eye - l_eye
        x_axis = eye_vec / np.linalg.norm(eye_vec)

        # Y-axis: nose direction, orthogonalized against X
        nose_vec = np.array(lm3d[self._NOSE_TIP], dtype=float) - eye_center
        nose_norm = np.linalg.norm(nose_vec)
        if nose_norm < 1e-6:
            return None
        nose_unit = nose_vec / nose_norm
        y_proj = nose_unit - np.dot(nose_unit, x_axis) * x_axis
        y_norm = np.linalg.norm(y_proj)
        if y_norm < 1e-6:
            return None
        y_axis = y_proj / y_norm

        # Z-axis: orthogonal to both (right-hand rule)
        z_axis = np.cross(x_axis, y_axis)

        # Rotation matrix: rows are canonical basis vectors
        R = np.stack([x_axis, y_axis, z_axis])  # (3, 3)

        # Rotate all stable points into canonical pose
        pts_canonical = (R @ pts.T).T  # (N, 3)

        return pts_canonical.flatten()  # 75-D vector

    def _mesh_quality_score(self, face_mesh: FaceMeshResult) -> float:
        """
        Score the quality of a face mesh for embedding reliability [0.0 – 1.0].

        Measures how frontal the face is using the head rotation matrix.
        A perfectly frontal face scores 1.0; a 90° profile scores 0.0.
        Frames without a head matrix (no MediaPipe transform) score 0.5
        so they are not completely discarded but are updated conservatively.
        """
        if face_mesh.head_matrix is None:
            return 0.5

        if len(face_mesh.landmarks_3d) < 474:
            return 0.0

        # MediaPipe head_matrix: R @ [0, 0, -1] gives head forward direction.
        # When fully frontal, forward ≈ [0, 0, -1] → -forward_z ≈ 1.0.
        R = face_mesh.head_matrix[:3, :3]
        head_fwd = R @ np.array([0.0, 0.0, -1.0])
        frontality = float(np.clip(-head_fwd[2], 0.0, 1.0))

        return frontality
