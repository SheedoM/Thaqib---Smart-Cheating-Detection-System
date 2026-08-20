"""
Unit and integration tests for Repair R1: Cross-Modal Archive Clock-Origin Alignment.

Tests:
  - Test R1-A: Video start = T, Audio start = T, Event = T + 20 -> Video seek = 20, Audio seek = 20
  - Test R1-B: Video start = T, Audio start = T + 2, Event = T + 20 -> Video seek = 20, Audio seek = 18
  - Test R1-C: Audio start = T, Video start = T + 3, Event = T + 20 -> Audio seek = 20, Video seek = 17
  - Test R1-D: Processing delay: Event at T+20 detected at T+22 retains T+20 bounds
  - Test R1-E: Real synthetic media cross-modal extraction with skewed start times
"""

import os
import shutil
import sys
import tempfile
import unittest
import wave
import struct
from pathlib import Path
import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from thaqib.av_alert_composer import AVAlertComposer, ArchiveRef


def create_synthetic_video(file_path: str, duration_sec: float = 5.0, fps: float = 30.0, width: int = 160, height: int = 120):
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(file_path, fourcc, fps, (width, height))
    total_frames = int(duration_sec * fps)
    for i in range(total_frames):
        frame = np.full((height, width, 3), (i % 255), dtype=np.uint8)
        cv2.putText(frame, f"F{i}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        out.write(frame)
    out.release()


def create_synthetic_wav(file_path: str, duration_sec: float = 5.0, sample_rate: int = 16000):
    n_samples = int(duration_sec * sample_rate)
    with wave.open(file_path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        # 440 Hz tone
        raw_data = bytearray()
        for i in range(n_samples):
            val = int(32767.0 * 0.5 * np.sin(2.0 * np.pi * 440.0 * (i / sample_rate)))
            raw_data.extend(struct.pack('<h', val))
        wf.writeframes(raw_data)


class TestCrossModalAlignment(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="thaqib_r1_test_")
        self.video_path = os.path.join(self.temp_dir, "cam0_archive.mp4")
        self.audio_path = os.path.join(self.temp_dir, "mic0_archive.wav")
        create_synthetic_video(self.video_path, duration_sec=6.0, fps=30.0)
        create_synthetic_wav(self.audio_path, duration_sec=6.0, sample_rate=16000)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_r1_a_synchronized_starts(self):
        """Test R1-A: Video start = T, Audio start = T, Event = T + 20 -> Video = 20, Audio = 20"""
        T = 1000.0
        v_ref = ArchiveRef(path=self.video_path, wall_start_time=T)
        a_ref = ArchiveRef(path=self.audio_path, wall_start_time=T)
        composer = AVAlertComposer(
            audio_archives={"mic0": a_ref},
            video_archives={"cam0": v_ref},
            output_dir=self.temp_dir
        )
        
        # Video alert triggered with stream offset 20.0s to 22.0s
        a_start, a_end = composer._cross_modal_offsets(
            source_start=20.0,
            source_end=22.0,
            source_ref=v_ref,
            target_ref=a_ref,
            source_label="video:cam0",
            target_label="audio:mic0"
        )
        self.assertAlmostEqual(a_start, 20.0, places=3)
        self.assertAlmostEqual(a_end, 22.0, places=3)

    def test_r1_b_audio_started_later(self):
        """Test R1-B: Video start = T, Audio start = T + 2, Event = T + 20 -> Video = 20, Audio = 18"""
        T = 1000.0
        v_ref = ArchiveRef(path=self.video_path, wall_start_time=T)
        a_ref = ArchiveRef(path=self.audio_path, wall_start_time=T + 2.0)
        composer = AVAlertComposer(
            audio_archives={"mic0": a_ref},
            video_archives={"cam0": v_ref},
            output_dir=self.temp_dir
        )
        
        # Event occurred at VideoStreamTime = 20.0 -> EventWallTime = 1020.0 -> AudioStreamTime = 1020 - 1002 = 18.0
        a_start, a_end = composer._cross_modal_offsets(
            source_start=20.0,
            source_end=22.0,
            source_ref=v_ref,
            target_ref=a_ref,
            source_label="video:cam0",
            target_label="audio:mic0"
        )
        self.assertAlmostEqual(a_start, 18.0, places=3)
        self.assertAlmostEqual(a_end, 20.0, places=3)

    def test_r1_c_video_started_later(self):
        """Test R1-C: Audio start = T, Video start = T + 3, Event = T + 20 -> Audio = 20, Video = 17"""
        T = 1000.0
        a_ref = ArchiveRef(path=self.audio_path, wall_start_time=T)
        v_ref = ArchiveRef(path=self.video_path, wall_start_time=T + 3.0)
        composer = AVAlertComposer(
            audio_archives={"mic0": a_ref},
            video_archives={"cam0": v_ref},
            output_dir=self.temp_dir
        )
        
        # Audio alert at AudioStreamTime = 20.0 -> EventWallTime = 1020.0 -> VideoStreamTime = 1020 - 1003 = 17.0
        v_start, v_end = composer._cross_modal_offsets(
            source_start=20.0,
            source_end=22.0,
            source_ref=a_ref,
            target_ref=v_ref,
            source_label="audio:mic0",
            target_label="video:cam0"
        )
        self.assertAlmostEqual(v_start, 17.0, places=3)
        self.assertAlmostEqual(v_end, 19.0, places=3)

    def test_r1_d_processing_delay_preserves_event_bounds(self):
        """Test R1-D: Event at T+20 detected at T+22 preserves T+20 bounds based on captured frame/sample times."""
        # When an event happened at stream position 20.0, detection happens at wall time T+22.
        # The stream timestamp recorded was 20.0s (from frame index / fps).
        T_start = 500.0
        v_ref = ArchiveRef(path=self.video_path, wall_start_time=T_start)
        a_ref = ArchiveRef(path=self.audio_path, wall_start_time=T_start)
        
        composer = AVAlertComposer(
            audio_archives={"mic0": a_ref},
            video_archives={"cam0": v_ref},
            output_dir=self.temp_dir
        )
        
        # Video stream bounds are 20.0 to 22.0 (event at 20s, duration 2s)
        a_start, a_end = composer._cross_modal_offsets(
            source_start=20.0,
            source_end=22.0,
            source_ref=v_ref,
            target_ref=a_ref,
            source_label="video:cam0",
            target_label="audio:mic0"
        )
        self.assertEqual(a_start, 20.0)
        self.assertEqual(a_end, 22.0)

    def test_r1_e_real_media_composition_with_skewed_starts(self):
        """Test R1-E: Actual AV alert composition with real video and audio media and different start times."""
        T_video = 100.0
        T_audio = 101.0  # Audio started 1 second after video
        
        v_ref = ArchiveRef(path=self.video_path, wall_start_time=T_video)
        a_ref = ArchiveRef(path=self.audio_path, wall_start_time=T_audio)
        
        composer = AVAlertComposer(
            audio_archives={"mic0": a_ref},
            video_archives={"cam0": v_ref},
            output_dir=self.temp_dir
        )
        
        # Trigger video alert for event at video stream 2.0s - 4.0s
        # Expected audio extraction should be at 2.0 - 1.0 = 1.0s - 3.0s
        alert_path = composer.compose_video_alert(
            camera_id="cam0",
            mic_id="mic0",
            start_sec=2.0,
            end_sec=4.0,
            alert_type="gaze"
        )
        
        self.assertIsNotNone(alert_path)
        self.assertTrue(os.path.exists(alert_path))
        self.assertGreater(os.path.getsize(alert_path), 0)

    def test_r1_f_target_archive_starts_after_event_zero_overlap_no_fabrication(self):
        """
        Prove that when the target archive began recording after the event ended,
        the system returns None and does NOT fabricate false evidence by clamping to 0.0.
        """
        T_video = 100.0  # Video started at 100.0s
        T_audio = 115.0  # Audio started at 115.0s (15s later)
        
        v_ref = ArchiveRef(path=self.video_path, wall_start_time=T_video)
        a_ref = ArchiveRef(path=self.audio_path, wall_start_time=T_audio)
        
        composer = AVAlertComposer(
            audio_archives={"mic0": a_ref},
            video_archives={"cam0": v_ref},
            output_dir=self.temp_dir
        )
        
        # Event in video at stream 2.0s - 4.0s (Wall time = 102.0s - 104.0s)
        # Audio did not start until Wall time = 115.0s (11s after event ended)
        offsets = composer._cross_modal_offsets(
            source_start=2.0,
            source_end=4.0,
            source_ref=v_ref,
            target_ref=a_ref,
            source_label="video:cam0",
            target_label="audio:mic0"
        )
        
        # Must return None — NEVER (0.0, 0.0) or (0.0, 2.0) which would fabricate audio
        self.assertIsNone(offsets)
        
        # compose_video_alert must fallback to video-only alert
        alert_path = composer.compose_video_alert(
            camera_id="cam0",
            mic_id="mic0",
            start_sec=2.0,
            end_sec=4.0,
            alert_type="gaze"
        )
        self.assertIsNotNone(alert_path)
        self.assertTrue(os.path.exists(alert_path))
        # The filename must be video-only (not combined_AV_)
        self.assertNotIn("combined_AV_", os.path.basename(alert_path))

    def test_r1_g_audio_alert_target_video_starts_after_event_skips_camera(self):
        """
        Prove that when audio alert occurs before video camera started recording,
        video composition is skipped rather than attaching future video frames from stream 0.0.
        """
        T_audio = 100.0  # Audio started at 100.0s
        T_video = 120.0  # Video started at 120.0s (20s later)
        
        a_ref = ArchiveRef(path=self.audio_path, wall_start_time=T_audio)
        v_ref = ArchiveRef(path=self.video_path, wall_start_time=T_video)
        
        composer = AVAlertComposer(
            audio_archives={"mic0": a_ref},
            video_archives={"cam0": v_ref},
            output_dir=self.temp_dir
        )
        
        # Audio alert at stream 2.0s - 4.0s (Wall time = 102.0s - 104.0s)
        offsets = composer._cross_modal_offsets(
            source_start=2.0,
            source_end=4.0,
            source_ref=a_ref,
            target_ref=v_ref,
            source_label="audio:mic0",
            target_label="video:cam0"
        )
        self.assertIsNone(offsets)
        
        # compose_audio_alert must skip camera and return empty list
        alerts = composer.compose_audio_alert(
            alert_wav_path=self.audio_path,
            mic_id="mic0",
            camera_ids=["cam0"],
            start_sec=2.0,
            end_sec=4.0
        )
        self.assertEqual(alerts, [])

    def test_r1_h_partial_overlap_seeks_from_target_stream_zero(self):
        """
        When event spans across target archive start (partial overlap),
        target seek begins at 0.0 and ends at the overlapping tail offset.
        """
        T_video = 100.0
        T_audio = 102.0  # Audio starts 2s after video
        
        v_ref = ArchiveRef(path=self.video_path, wall_start_time=T_video)
        a_ref = ArchiveRef(path=self.audio_path, wall_start_time=T_audio)
        
        composer = AVAlertComposer(
            audio_archives={"mic0": a_ref},
            video_archives={"cam0": v_ref},
            output_dir=self.temp_dir
        )
        
        # Event in video at stream 1.0s - 5.0s (Wall time 101.0s - 105.0s)
        # Audio started at 102.0s, so audio covers 102.0s - 105.0s (target stream 0.0s - 3.0s)
        offsets = composer._cross_modal_offsets(
            source_start=1.0,
            source_end=5.0,
            source_ref=v_ref,
            target_ref=a_ref,
            source_label="video:cam0",
            target_label="audio:mic0"
        )
        self.assertIsNotNone(offsets)
        self.assertAlmostEqual(offsets[0], 0.0, places=3)
        self.assertAlmostEqual(offsets[1], 3.0, places=3)


if __name__ == "__main__":
    unittest.main()
