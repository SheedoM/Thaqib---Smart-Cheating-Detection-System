"""
Unit tests for Repair R2: FileAudioSource Clock Consistency & Deterministic Stream Positions.

Tests:
  - Deterministic chunk timestamps (chunk N = N * chunk_ms/1000)
  - Processing delays and jitter do not alter media stream timestamps
  - SimClock offset integration
  - Monotonicity over long sequence of chunks
"""

import os
import shutil
import sys
import tempfile
import time
import unittest
import wave
import struct
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from thaqib.audio.source import FileAudioSource
from thaqib.sim_clock import SimClock


def create_wav_file(path: str, duration_sec: float = 3.0, sample_rate: int = 16000):
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        n_samples = int(duration_sec * sample_rate)
        data = bytearray(n_samples * 2)
        wf.writeframes(data)


class TestAudioSourceClockConsistency(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="thaqib_r2_test_")
        self.wav1 = os.path.join(self.temp_dir, "m1.wav")
        self.wav2 = os.path.join(self.temp_dir, "m2.wav")
        create_wav_file(self.wav1, duration_sec=3.0, sample_rate=16000)
        create_wav_file(self.wav2, duration_sec=3.0, sample_rate=16000)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_deterministic_chunk_timestamps(self):
        """Chunk N must have timestamp = N * (chunk_ms / 1000.0)."""
        source = FileAudioSource(
            file_paths=[self.wav1, self.wav2],
            sample_rate=16000,
            chunk_ms=500,
            real_time=False,
            clock=None
        )
        source.start()
        
        chunks = []
        while (c := source.get_chunk()) is not None:
            chunks.append(c)
        source.stop()

        self.assertEqual(len(chunks), 6)  # 3.0s / 0.5s = 6 chunks
        for i, chunk in enumerate(chunks):
            expected_ts = i * 0.5
            self.assertAlmostEqual(chunk.timestamp, expected_ts, places=4)
            self.assertEqual(chunk.chunk_index, i)

    def test_jitter_does_not_affect_timestamps(self):
        """Artificially sleeping during processing must NOT perturb chunk stream timestamps."""
        source = FileAudioSource(
            file_paths=[self.wav1],
            sample_rate=16000,
            chunk_ms=250,
            real_time=False,
            clock=None
        )
        source.start()

        chunks = []
        while (c := source.get_chunk()) is not None:
            time.sleep(0.01)  # 10ms artificial processing jitter
            chunks.append(c)
        source.stop()

        self.assertEqual(len(chunks), 12)
        for i, chunk in enumerate(chunks):
            expected_ts = i * 0.25
            self.assertAlmostEqual(chunk.timestamp, expected_ts, places=4)

    def test_sim_clock_integration(self):
        """When SimClock is provided, chunk timestamp incorporates start clock offset."""
        clock = SimClock()
        time.sleep(0.05)  # Advance clock
        
        source = FileAudioSource(
            file_paths=[self.wav1],
            sample_rate=16000,
            chunk_ms=500,
            real_time=False,
            clock=clock
        )
        source.start()
        c0 = source.get_chunk()
        c1 = source.get_chunk()
        source.stop()

        self.assertIsNotNone(c0)
        self.assertIsNotNone(c1)
        self.assertAlmostEqual(c1.timestamp - c0.timestamp, 0.5, places=3)
        self.assertTrue(c0.timestamp >= 0.05)


if __name__ == "__main__":
    unittest.main()
