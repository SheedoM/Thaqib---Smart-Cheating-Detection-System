"""
Face-based Re-Identification Module.

Computes embeddings from stable 3D face landmarks to maintain student tracking
identity even if the ByteTrack tracker temporarily loses them.
"""

import logging
from dataclasses import dataclass

import numpy as np

from thaqib.video.face_mesh import FaceMeshResult

logger = logging.getLogger(__name__)


class FaceReIdentifier:
    """
    Manages face embeddings and matches new tracks to known identities.
    """

    # Stable landmark indices
    _NOSE_TIP = 1
    _LEFT_EYE_OUTER = 33
    _LEFT_EYE_INNER = 133
    _RIGHT_EYE_INNER = 362
    _RIGHT_EYE_OUTER = 263
    _MOUTH_LEFT = 61
    _MOUTH_RIGHT = 291

    _STABLE_POINTS = [
        _NOSE_TIP,
        _LEFT_EYE_OUTER,
        _LEFT_EYE_INNER,
        _RIGHT_EYE_INNER,
        _RIGHT_EYE_OUTER,
        _MOUTH_LEFT,
        _MOUTH_RIGHT,
    ]

    def __init__(self, match_threshold: float = 0.80):
        """
        Initialize the Re-Identifier.

        Args:
            match_threshold: Minimum cosine similarity [0.0 - 1.0].
        """
        self._threshold = match_threshold
        self._embeddings: dict[int, np.ndarray] = {}  # track_id -> normalized embedding vector

    def compute_embedding(self, face_mesh: FaceMeshResult) -> np.ndarray | None:
        """
        Compute a normalized flat embedding vector from stable 3D landmarks.
        """
        lm3d = face_mesh.landmarks_3d
        if not lm3d or len(lm3d) < 474:
            return None

        points = []
        for idx in self._STABLE_POINTS:
            x, y, z = lm3d[idx]
            points.extend([x, y, z])

        # Convert to vector
        vec = np.array(points, dtype=float)

        # Shift to zero-mean (translation invariance)
        vec_3d = vec.reshape(-1, 3)
        mean_3d = np.mean(vec_3d, axis=0)
        vec_3d_centered = vec_3d - mean_3d
        vec_centered = vec_3d_centered.flatten()

        # L2 Normalize (scale invariance)
        norm = np.linalg.norm(vec_centered)
        if norm < 1e-6:
            return None
        
        return vec_centered / norm

    def register_embedding(self, track_id: int, face_mesh: FaceMeshResult) -> bool:
        """
        Store or update the embedding for a known track ID.
        Returns True if the new embedding matches the stored one (or first time).
        """
        emb = self.compute_embedding(face_mesh)
        if emb is None:
            return False

        is_match = True
        if track_id in self._embeddings:
            current = self._embeddings[track_id]
            similarity = float(np.dot(emb, current))
            if similarity < self._threshold:
                is_match = False
            else:
                updated = (current * 0.7) + (emb * 0.3)  # EMA
                updated /= np.linalg.norm(updated)
                self._embeddings[track_id] = updated
        else:
            self._embeddings[track_id] = emb

        return is_match

    def match(self, face_mesh: FaceMeshResult) -> int | None:
        """
        Find the best matching known track ID for the given face mesh.
        Searches ALL stored embeddings, including ones for inactive IDs.
        """
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

        if best_score >= self._threshold and best_id is not None:
            logger.info(
                f"ReID match found! Restoring track ID {best_id} (Score: {best_score:.3f})"
            )
            return best_id, best_score

        return None

