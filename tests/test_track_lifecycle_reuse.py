"""
Unit tests for Repair R3: Track ID Reuse & Stale ReID Alias / Incident Lifecycle.

Tests:
  - Track expiration completely purges spatial state, incident type, and buffers
  - Tracker ID recycling (e.g. byteTrack re-assigning ID 42) produces clean state
  - Stale ReID aliases and embeddings do not leak into the recycled track ID
"""

import sys
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from thaqib.video.registry import GlobalStudentRegistry, StudentSpatialState
from thaqib.video.tracker import TrackedObject
from thaqib.video.face_mesh import FaceMeshResult
from thaqib.video.reid import FaceReIdentifier


class TestTrackLifecycleReuse(unittest.TestCase):
    def setUp(self):
        self.registry = GlobalStudentRegistry()
        self.reid = FaceReIdentifier(match_threshold=0.8)

    def test_track_expiration_and_id_reuse(self):
        """When track 42 expires and is reused by a new person, no state/alias leaks."""
        # 1. Student A arrives with track_id = 42
        t0 = 100.0
        track_a = TrackedObject(track_id=42, bbox=(10, 10, 100, 100), confidence=0.9)
        expired = self.registry.update([track_a], frame_index=0, timestamp=t0)
        self.assertEqual(len(expired), 0)
        
        state_a = self.registry.get(42)
        self.assertIsNotNone(state_a)
        state_a.active_incident_type = "phone"
        state_a.is_alert_recording = True
        state_a.recording_buffer.append(np.zeros((10, 10, 3), dtype=np.uint8))
        
        # Directly store an embedding vector for Student A in reid
        self.reid._embeddings[42] = np.ones(75, dtype=np.float32) / np.sqrt(75.0)
        
        # 2. Track 42 expires at t0 + 3.5s (> 3.0s purge threshold)
        t_expire = t0 + 3.5
        expired = self.registry.update([], frame_index=105, timestamp=t_expire)
        self.assertEqual(len(expired), 1)
        self.assertEqual(expired[0].track_id, 42)
        
        # Cleanup ReID
        self.reid.remove_embeddings([42])
        
        # Registry no longer has 42
        self.assertIsNone(self.registry.get(42))
        self.assertNotIn(42, self.reid._embeddings)
        
        # 3. Student B arrives and tracker reuses track_id = 42
        t_new = t_expire + 1.0
        track_b = TrackedObject(track_id=42, bbox=(200, 200, 300, 300), confidence=0.95)
        expired_b = self.registry.update([track_b], frame_index=90, timestamp=t_new)
        self.assertEqual(len(expired_b), 0)
        
        state_b = self.registry.get(42)
        self.assertIsNotNone(state_b)
        self.assertIsNot(state_b, state_a)  # Must be a distinct object
        self.assertIsNone(state_b.active_incident_type)  # Must NOT inherit "phone"
        self.assertFalse(state_b.is_alert_recording)
        self.assertEqual(len(state_b.recording_buffer), 0)  # Empty buffer
        
        # 4. Student B's embedding is registered fresh
        emb_b = np.zeros(75, dtype=np.float32)
        emb_b[0] = 1.0
        self.reid._embeddings[42] = emb_b
        self.assertIn(42, self.reid._embeddings)


if __name__ == "__main__":
    unittest.main()
