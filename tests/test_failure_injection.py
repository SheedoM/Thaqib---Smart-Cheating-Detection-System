"""
Failure Injection Tests to verify graceful degradation and edge-case handling.
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
import cv2
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from thaqib.av_alert_composer import AVAlertComposer
from thaqib.mic_layout import MicLayout
from thaqib.video.registry import GlobalStudentRegistry
from thaqib.video.tracker import TrackedObject


class TestFailureInjection(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="thaqib_test_fail_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_missing_video_archive_fails_gracefully(self):
        """Requesting video composition when archive file is missing returns None and logs warning."""
        composer = AVAlertComposer(
            audio_archives={},
            video_archives={"cam0": os.path.join(self.temp_dir, "non_existent_archive.mp4")},
            output_dir=self.temp_dir
        )
        res = composer.compose_video_alert("cam0", None, 0.0, 2.0, "gaze")
        self.assertIsNone(res)

    def test_corrupt_video_archive_fails_gracefully(self):
        """Requesting video composition on a corrupt 0-byte file returns None without hanging."""
        corrupt_file = os.path.join(self.temp_dir, "corrupt.mp4")
        with open(corrupt_file, "wb") as f:
            f.write(b"not a valid mp4 header")

        composer = AVAlertComposer(
            audio_archives={},
            video_archives={"cam0": corrupt_file},
            output_dir=self.temp_dir
        )
        res = composer.compose_video_alert("cam0", None, 0.0, 2.0, "gaze")
        self.assertIsNone(res)

    def test_negative_or_inverted_seek_timestamps(self):
        """Negative start_sec or end_sec <= start_sec are sanitized to valid ranges."""
        archive_path = os.path.join(self.temp_dir, "valid.mp4")
        # Create small 1-second video
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(archive_path, fourcc, 30.0, (160, 120))
        for _ in range(30):
            out.write(np.zeros((120, 160, 3), dtype=np.uint8))
        out.release()

        composer = AVAlertComposer(
            audio_archives={},
            video_archives={"cam0": archive_path},
            output_dir=self.temp_dir
        )
        out_clip = os.path.join(self.temp_dir, "out_negative_seek.mp4")
        # Pass negative and inverted timestamps
        success = composer._extract_and_annotate_video(
            video_archive=archive_path,
            output_path=out_clip,
            camera_id="cam0",
            mic_id=None,
            start_sec=-10.0,
            end_sec=-5.0
        )
        # Should sanitize start_sec to 0.0 and end_sec to 0.1, extracting valid frame
        self.assertTrue(success)
        self.assertTrue(os.path.exists(out_clip))

    def test_corrupt_mic_layout_json_recovery(self):
        """Corrupt JSON in mic layout file is caught and handled safely."""
        bad_json = os.path.join(self.temp_dir, "bad_layout.json")
        with open(bad_json, "w", encoding="utf-8") as f:
            f.write("{invalid_json: 123,")

        layout = MicLayout(config_path=bad_json)
        self.assertEqual(len(layout.pins), 0)  # Gracefully initialized empty


if __name__ == "__main__":
    unittest.main()
