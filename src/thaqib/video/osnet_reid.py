"""
OSNet-based appearance Re-Identification module.

Extracts 512-dimensional CNN embeddings from person bounding-box crops
using the lightweight OSNet-x0.25 model from torchreid. This provides
production-grade identity persistence based on clothing/body appearance,
replacing the geometric face-landmark approach.

Pretrained weights are downloaded automatically by torchreid on first use.
"""

import logging
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ImageNet mean/std used during OSNet training
_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)

# OSNet expects exactly this input size
_INPUT_H = 256
_INPUT_W = 128


class OSNetReID:
    """
    Lightweight appearance Re-Identification using OSNet-x0.25.

    Produces an L2-normalised 512-dim embedding for a person crop.
    The model is loaded once and kept in eval() mode on CPU.

    Usage:
        >>> reid = OSNetReID()
        >>> emb = reid.extract(frame, (x1, y1, x2, y2))   # np.ndarray (512,)
        >>> sim = reid.cosine_similarity(emb_a, emb_b)
    """

    def __init__(self) -> None:
        try:
            import torch
            import torchreid
        except ImportError as e:
            raise ImportError(
                "OSNetReID requires torch and torchreid.\n"
                "Install with:\n"
                "  pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu\n"
                "  pip install torchreid"
            ) from e

        self._torch = torch
        self._device = torch.device("cpu")

        logger.info("Loading OSNet-x0.25 model (pretrained on ImageNet)…")
        # Build model without classifier head for feature extraction
        # num_classes must match the pretrained checkpoint; pretrained=True
        # loads weights from Market-1501 automatically on first call.
        self._model = torchreid.models.build_model(
            name="osnet_x0_25",
            num_classes=1000,
            pretrained=True,
        )
        self._model.eval()
        self._model.to(self._device)
        logger.info("OSNet-x0.25 loaded and ready.")

    # ------------------------------------------------------------------

    def extract(
        self,
        frame: np.ndarray,
        bbox: tuple[int, int, int, int],
    ) -> np.ndarray | None:
        """
        Extract a 512-dim L2-normalised appearance embedding from a person crop.

        Args:
            frame: Full BGR video frame (H×W×3, OpenCV).
            bbox:  Person bounding box (x1, y1, x2, y2) in frame pixels.

        Returns:
            np.ndarray of shape (512,), or None if the crop is too small.
        """
        x1, y1, x2, y2 = bbox
        fh, fw = frame.shape[:2]

        # Clamp to frame bounds
        x1 = max(0, x1); y1 = max(0, y1)
        x2 = min(fw, x2); y2 = min(fh, y2)

        if x2 <= x1 or y2 <= y1:
            return None

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0 or crop.shape[0] < 16 or crop.shape[1] < 8:
            return None

        # BGR → RGB, resize to 256×128, float32 normalise
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (_INPUT_W, _INPUT_H))
        tensor = (resized.astype(np.float32) / 255.0 - _IMAGENET_MEAN) / _IMAGENET_STD
        # HWC → CHW → NCHW
        tensor = tensor.transpose(2, 0, 1)[np.newaxis, ...]
        t = self._torch.from_numpy(tensor)

        with self._torch.no_grad():
            feat = self._model(t)  # (1, 512)

        feat_np = feat.squeeze(0).cpu().numpy()  # (512,)

        # L2 normalise
        norm = np.linalg.norm(feat_np)
        if norm < 1e-6:
            return None
        return feat_np / norm

    # ------------------------------------------------------------------

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Return cosine similarity between two L2-normalised vectors."""
        return float(np.dot(a, b))

    # ------------------------------------------------------------------

    def match_against_gallery(
        self,
        query_emb: np.ndarray,
        gallery: dict[int, np.ndarray],
        threshold: float = 0.80,
    ) -> tuple[int, float] | None:
        """
        Find the best match for query_emb in a {track_id: embedding} gallery.

        Args:
            query_emb:  L2-normalised query embedding.
            gallery:    Dict mapping track_id → stored L2-normalised embedding.
            threshold:  Minimum cosine similarity to accept as a match.

        Returns:
            (track_id, score) if a match is found, else None.
        """
        if not gallery:
            return None

        best_id: int | None = None
        best_score = -1.0

        for tid, stored_emb in gallery.items():
            score = self.cosine_similarity(query_emb, stored_emb)
            if score > best_score:
                best_score = score
                best_id = tid

        if best_score >= threshold and best_id is not None:
            logger.info(
                f"OSNet ReID match: track {best_id} (cosine={best_score:.3f})"
            )
            return best_id, best_score

        return None
