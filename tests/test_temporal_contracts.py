"""
Unit tests for Repair A: Temporal Contracts & StreamTime / WallTime Separation.
"""

import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from thaqib.sim_clock import SimClock
from thaqib.audio.models import AudioAlert
from thaqib.audio.evidence import AudioEvidenceRecorder


class TestTemporalContracts(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="thaqib_test_temporal_")
        self.evidence_recorder = AudioEvidenceRecorder(
            output_dir=self.temp_dir,
            mic_names={0: "mic_front", 1: "mic_back"}
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sim_clock_monotonicity(self):
        """SimClock should start near 0.0 and progress monotonically."""
        clock = SimClock()
        t0 = clock.now()
        self.assertGreaterEqual(t0, 0.0)
        time.sleep(0.05)
        t1 = clock.now()
        self.assertGreater(t1, t0)
        clock.reset()
        t2 = clock.now()
        self.assertLess(t2, t1)

    def test_audio_alert_relative_stream_time(self):
        """Evidence recorder should format relative stream time without negative offsets."""
        dummy_audio = np.zeros(16000, dtype=np.float32)  # 1 second of audio
        
        # Scenario: Relative stream time from SimClock (e.g., event at 5.5s)
        alert = AudioAlert(
            timestamp=5.5,
            mic_id=0,
            active_mics=[0],
            transcript="test speech",
            matched_keywords=["test"],
            timestamp_start=3.5,
            timestamp_end=7.5,
            audio_clip=dummy_audio,
            sample_rate=16000,
            confidence=0.95,
            chunk_index=11,
            recording_start=0.0,
            wall_time=time.time(),
            stream_offset=5.5,
        )

        wav_path, json_path = self.evidence_recorder.save_alert(alert)
        self.assertTrue(os.path.exists(wav_path))
        self.assertTrue(os.path.exists(json_path))

        # Check filename does NOT contain negative offset (e.g., OFFSET-492105h)
        base_name = os.path.basename(wav_path)
        self.assertIn("OFFSET00h00m05s", base_name)
        self.assertNotIn("OFFSET-", base_name)

        # Check JSON contents
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["recording_offset"], "00:00:05")
        self.assertAlmostEqual(data["stream_offset_sec"], 5.5, places=2)
        self.assertIn("T", data["timestamp"])  # Valid ISO timestamp
        self.assertGreater(data["timestamp_unix"], 1e9)  # Real Unix timestamp

    def test_audio_alert_epoch_wall_time(self):
        """Evidence recorder should format absolute epoch timestamps correctly."""
        dummy_audio = np.zeros(16000, dtype=np.float32)
        wall_start = 1771578000.0  # Simulated start time
        event_time = wall_start + 12.3  # Event at 12.3s

        alert = AudioAlert(
            timestamp=event_time,
            mic_id=1,
            active_mics=[1],
            transcript="another test",
            matched_keywords=["another"],
            timestamp_start=10.3,
            timestamp_end=14.3,
            audio_clip=dummy_audio,
            sample_rate=16000,
            confidence=0.88,
            chunk_index=24,
            recording_start=wall_start,
            wall_time=event_time,
            stream_offset=12.3,
        )

        wav_path, json_path = self.evidence_recorder.save_alert(alert)
        self.assertTrue(os.path.exists(wav_path))
        self.assertTrue(os.path.exists(json_path))

        base_name = os.path.basename(wav_path)
        self.assertIn("OFFSET00h00m12s", base_name)
        self.assertNotIn("OFFSET-", base_name)

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["recording_offset"], "00:00:12")
        self.assertAlmostEqual(data["stream_offset_sec"], 12.3, places=2)

    def test_long_running_session_offset(self):
        """Offsets for long sessions (e.g. 3 hours) should format accurately without drift."""
        dummy_audio = np.zeros(16000, dtype=np.float32)
        three_hours_sec = 3 * 3600 + 14 * 60 + 25.5  # 03:14:25.5

        alert = AudioAlert(
            timestamp=three_hours_sec,
            mic_id=0,
            active_mics=[0],
            transcript="long session",
            matched_keywords=["session"],
            timestamp_start=three_hours_sec - 2.0,
            timestamp_end=three_hours_sec + 2.0,
            audio_clip=dummy_audio,
            sample_rate=16000,
            confidence=0.99,
            chunk_index=23320,
            recording_start=0.0,
            wall_time=time.time(),
            stream_offset=three_hours_sec,
        )

        wav_path, json_path = self.evidence_recorder.save_alert(alert)
        base_name = os.path.basename(wav_path)
        self.assertIn("OFFSET03h14m25s", base_name)

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["recording_offset"], "03:14:25")
        self.assertAlmostEqual(data["stream_offset_sec"], three_hours_sec, places=2)


if __name__ == "__main__":
    unittest.main()
