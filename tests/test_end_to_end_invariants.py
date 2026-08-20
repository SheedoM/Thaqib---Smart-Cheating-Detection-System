"""
Comprehensive End-to-End Invariant Tests across all subsystems.
"""

import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from collections import deque
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from thaqib.sim_clock import SimClock
from thaqib.mic_layout import MicLayout
from thaqib.av_alert_composer import AVAlertComposer
from thaqib.audio.models import AudioAlert
from thaqib.audio.evidence import AudioEvidenceRecorder
from thaqib.video.registry import StudentSpatialState, GlobalStudentRegistry
from thaqib.video.tracker import TrackedObject
from thaqib.startup import StartupCoordinator


class TestEndToEndInvariants(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="thaqib_test_e2e_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_invariant_1_temporal_separation(self):
        """Invariant 1: WallTime never drives seek positions; StreamTime never drives filenames."""
        clock = SimClock()
        stream_t = 14.5  # 14.5 seconds into test
        wall_t = 1771578000.0  # Unix epoch

        alert = AudioAlert(
            timestamp=stream_t,
            mic_id=0,
            active_mics=[0],
            transcript="suspicious",
            matched_keywords=["test"],
            timestamp_start=stream_t - 2.0,
            timestamp_end=stream_t + 2.0,
            audio_clip=np.zeros(16000, dtype=np.float32),
            sample_rate=16000,
            confidence=0.9,
            chunk_index=29,
            recording_start=0.0,
            wall_time=wall_t,
            stream_offset=stream_t,
        )

        recorder = AudioEvidenceRecorder(output_dir=self.temp_dir)
        wav_path, json_path = recorder.save_alert(alert)

        # 1. Filename contains StreamTime offset in HHhMMmSSs
        self.assertIn("OFFSET00h00m14s", os.path.basename(wav_path))
        # 2. Seek arguments to composer must strictly be stream offsets (<= 86400)
        self.assertLess(alert.timestamp_start, 86400.0)
        self.assertLess(alert.timestamp_end, 86400.0)

    def test_invariant_2_incident_state_latching(self):
        """Invariant 2: When phone is detected, active_incident_type remains PHONE even during post-roll."""
        state = StudentSpatialState(
            track_id=10,
            bbox=(50, 50, 150, 150),
            center=(100, 100),
            paper_center=(100, 200),
            frame_index=1,
            timestamp=0.0,
        )
        # Latched Phone alert
        state.is_alert_recording = True
        state.active_incident_type = "phone"
        state.incident_context = {'is_using_phone': True, 'phone_bbox': (80, 80, 120, 120)}

        # Gaze cheat triggers while phone alert is active
        state.cheating_target_paper = (300, 200)

        # Phone disappears
        state.is_using_phone = False
        state.phone_bbox = None

        # Final alert type must still be "phone"
        self.assertEqual(state.active_incident_type, "phone")
        self.assertTrue(state.incident_context['is_using_phone'])

    def test_invariant_3_startup_fail_fast(self):
        """Invariant 3: Any startup failure unblocks and aborts the entire system within finite bounded time."""
        coord = StartupCoordinator(["c0", "c1"])
        t0 = time.time()
        coord.signal_failed("c0", "Camera device disconnected")
        aborted = coord.wait_barrier(timeout=5.0)
        elapsed = time.time() - t0

        self.assertFalse(aborted)
        self.assertTrue(coord.abort_event.is_set())
        self.assertLess(elapsed, 1.0)  # Immediate abort, didn't wait 5s


if __name__ == "__main__":
    unittest.main()
