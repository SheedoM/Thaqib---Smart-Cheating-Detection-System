"""
Unit tests for Repair C: AV Alert Composer & Video Archive Seeking.
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


def create_synthetic_video(file_path: str, duration_sec: float = 5.0, fps: float = 30.0, width: int = 320, height: int = 240):
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(file_path, fourcc, fps, (width, height))
    total_frames = int(duration_sec * fps)
    for i in range(total_frames):
        frame = np.full((height, width, 3), (i % 255), dtype=np.uint8)
        cv2.putText(frame, f"F{i}", (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        out.write(frame)
    out.release()


class TestAVAlertComposer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="thaqib_test_composer_")
        self.archive_path = os.path.join(self.temp_dir, "cam0_archive.mp4")
        create_synthetic_video(self.archive_path, duration_sec=4.0, fps=30.0)

        self.composer = AVAlertComposer(
            audio_archives={"mic0": os.path.join(self.temp_dir, "mic0.wav")},
            video_archives={"cam0": self.archive_path},
            output_dir=self.temp_dir,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_extract_and_annotate_exact_frame_count(self):
        """Extraction between 1.0s and 3.0s on a 30fps video should produce ~60 frames."""
        output_clip = os.path.join(self.temp_dir, "extracted_clip.mp4")
        success = self.composer._extract_and_annotate_video(
            video_archive=self.archive_path,
            output_path=output_clip,
            camera_id="cam0",
            mic_id="mic0",
            start_sec=1.0,
            end_sec=3.0,
            subject_point=(100, 100)
        )
        self.assertTrue(success)
        self.assertTrue(os.path.exists(output_clip))

        cap = cv2.VideoCapture(output_clip)
        frames_read = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            frames_read += 1
        cap.release()

        self.assertGreaterEqual(frames_read, 58)
        self.assertLessEqual(frames_read, 62)

    def test_extract_beyond_eof_terminates_cleanly(self):
        """Requesting video beyond file duration should terminate cleanly and not hang."""
        output_clip = os.path.join(self.temp_dir, "eof_clip.mp4")
        success = self.composer._extract_and_annotate_video(
            video_archive=self.archive_path,
            output_path=output_clip,
            camera_id="cam0",
            mic_id="mic0",
            start_sec=10.0,
            end_sec=12.0
        )
        # Should return False because 0 frames could be read
        self.assertFalse(success)

    def test_compose_video_alert_video_only(self):
        """When mic is unmapped, compose_video_alert should generate video-only clip."""
        out_path = self.composer.compose_video_alert(
            camera_id="cam0",
            mic_id=None,
            start_sec=0.5,
            end_sec=2.0,
            alert_type="gaze",
            subject_point=(160, 120)
        )
        self.assertIsNotNone(out_path)
        self.assertTrue(os.path.exists(out_path))

    def test_compose_audio_alert_unmapped_mic_returns_empty(self):
        """When audio alert triggers on an unmapped mic, it safely returns empty list."""
        dummy_wav = os.path.join(self.temp_dir, "dummy_alert.wav")
        with open(dummy_wav, "wb") as f:
            f.write(b"RIFF....WAVE")

        res = self.composer.compose_audio_alert(
            alert_wav_path=dummy_wav,
            mic_id="mic99_unmapped",
            camera_ids=[],
            start_sec=1.0,
            end_sec=3.0
        )
        self.assertEqual(res, [])


if __name__ == "__main__":
    unittest.main()
