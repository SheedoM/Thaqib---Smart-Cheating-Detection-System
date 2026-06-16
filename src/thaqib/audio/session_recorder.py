"""
Continuous session audio recorder.

Records ALL incoming audio from every microphone to WAV files for the
entire duration of an exam session.  This is separate from evidence clips
(which capture only the cheating moment).  Session recordings allow:

    - Post-exam forensic analysis of the full audio
    - Re-running the discriminator with different thresholds offline
    - Verifying the system's decisions against the raw audio
    - Comparing raw vs. processed audio side-by-side

Each session creates a timestamped folder with TWO sub-folders:

    <output_dir>/
        session_<YYYY-MM-DD_HH-MM-SS>/
            raw/                    <- original mic audio (no processing)
                session_mic0.wav
                session_mic1.wav
            processed/              <- HPF + noise reduction + adaptive gain
                session_mic0.wav    (written only once noise profile is ready)
                session_mic1.wav
            session_manifest.json   <- metadata about the session
"""

import json
import logging
import wave
from datetime import datetime
from pathlib import Path

import numpy as np

from thaqib.audio.models import AudioChunk

logger = logging.getLogger(__name__)


class SessionAudioRecorder:
    """
    Streams live audio from all microphones to WAV files in real-time.

    Saves two parallel copies of each mic's audio:
        raw/       -- original samples straight from the audio source.
        processed/ -- samples after the AudioPreprocessor pipeline
                      (HPF + spectral noise reduction + adaptive gain).
                      Written only when the preprocessor has a ready noise
                      profile (at least 5 GLOBAL/SILENT samples collected).

    Usage:
        recorder = SessionAudioRecorder(output_dir="sessions")
        recorder.open(n_mics=2, sample_rate=16000)

        # Inside the pipeline loop:
        recorder.write_chunk(chunk, processed_mics=processed_audio_list)

        # On session end:
        recorder.close()
        print(recorder.session_dir)
    """

    def __init__(self, output_dir: str = "sessions"):
        self._output_dir = Path(output_dir)
        self._session_dir: Path | None = None
        self._raw_dir: Path | None = None
        self._processed_dir: Path | None = None

        self._raw_writers: list[wave.Wave_write] = []
        self._processed_writers: list[wave.Wave_write] = []

        self._n_mics: int = 0
        self._sample_rate: int = 16000
        self._chunks_written: int = 0
        self._processed_chunks_written: int = 0
        self._session_start: float = 0.0
        self._is_open: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def session_dir(self) -> "Path | None":
        """Path to the current session directory (None if not started)."""
        return self._session_dir

    @property
    def is_open(self) -> bool:
        """True if a recording session is currently active."""
        return self._is_open

    def open(self, n_mics: int, sample_rate: int = 16000) -> Path:
        """
        Start a new recording session.

        Creates a timestamped session directory with raw/ and processed/
        sub-folders, opening one WAV file per microphone in each.

        Args:
            n_mics: Number of microphones to record.
            sample_rate: Sample rate in Hz (must match the pipeline source).

        Returns:
            Path to the created session directory.
        """
        if self._is_open:
            logger.warning("Session recorder already open -- close first")
            return self._session_dir

        import shutil, time

        # Check disk space before opening files
        total, used, free = shutil.disk_usage(
            str(self._output_dir.parent if self._output_dir.exists() else Path.cwd())
        )
        free_mb = free / (1024 * 1024)
        if free_mb < 500:
            logger.critical(
                f"Session recorder: LOW DISK SPACE -- only {free_mb:.0f} MB free. "
                f"Session recording may fail or truncate the exam audio. "
                f"Free at least 500 MB before starting."
            )
        else:
            logger.info(f"Disk space OK: {free_mb:.0f} MB free")

        self._session_start = time.time()
        self._n_mics = n_mics
        self._sample_rate = sample_rate
        self._chunks_written = 0
        self._processed_chunks_written = 0

        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self._session_dir   = self._output_dir / f"session_{ts}"
        self._raw_dir       = self._session_dir / "raw"
        self._processed_dir = self._session_dir / "processed"

        self._raw_dir.mkdir(parents=True, exist_ok=True)
        self._processed_dir.mkdir(parents=True, exist_ok=True)

        # Open WAV writers for raw/
        self._raw_writers = []
        for mic_id in range(n_mics):
            wav_path = self._raw_dir / f"session_mic{mic_id}.wav"
            wf = wave.open(str(wav_path), "wb")
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            self._raw_writers.append(wf)
            logger.info(f"Session recorder [raw]: mic{mic_id} -> {wav_path.name}")

        # Open WAV writers for processed/
        self._processed_writers = []
        for mic_id in range(n_mics):
            wav_path = self._processed_dir / f"session_mic{mic_id}.wav"
            wf = wave.open(str(wav_path), "wb")
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            self._processed_writers.append(wf)
            logger.info(f"Session recorder [processed]: mic{mic_id} -> {wav_path.name}")

        self._is_open = True
        logger.info(
            f"Session recording started: {self._session_dir} "
            f"({n_mics} mics, {sample_rate}Hz) -- raw/ + processed/"
        )
        return self._session_dir

    def write_chunk(
        self,
        chunk: AudioChunk,
        processed_mics: "list[np.ndarray] | None" = None,
    ) -> None:
        """
        Write one audio chunk to raw/ and (optionally) processed/ WAV files.

        Args:
            chunk:          AudioChunk with mic_data shape (n_mics, n_samples).
                            Always written to raw/.
            processed_mics: List of preprocessed audio arrays, one per mic.
                            Written to processed/ when provided.
                            Pass None (default) to skip processed recording
                            (e.g. before the noise profile is ready).
        """
        if not self._is_open:
            return

        n_mics = chunk.mic_data.shape[0]

        # -- Write raw audio --------------------------------------------------
        for mic_id in range(min(n_mics, len(self._raw_writers))):
            self._raw_writers[mic_id].writeframes(
                self._to_int16(chunk.mic_data[mic_id]).tobytes()
            )
        self._chunks_written += 1

        # -- Write processed audio (when available) ---------------------------
        if processed_mics is not None:
            for mic_id in range(min(len(processed_mics), len(self._processed_writers))):
                self._processed_writers[mic_id].writeframes(
                    self._to_int16(processed_mics[mic_id]).tobytes()
                )
            self._processed_chunks_written += 1

    @staticmethod
    def _to_int16(audio: np.ndarray) -> np.ndarray:
        """Convert float32 [-1, 1] to int16 PCM (no-op if already int16)."""
        if audio.dtype in (np.float32, np.float64):
            return np.clip(audio * 32767, -32768, 32767).astype(np.int16)
        return audio.astype(np.int16)

    def close(self) -> dict:
        """
        Finalize all WAV files and write a session manifest JSON.

        Returns:
            Session metadata dictionary (also written to manifest.json).
        """
        if not self._is_open:
            return {}

        import time
        duration_sec = time.time() - self._session_start

        # Close raw writers
        for mic_id, wf in enumerate(self._raw_writers):
            try:
                wf.close()
                logger.info(f"Session recorder [raw]: mic{mic_id} file closed")
            except Exception as e:
                logger.error(f"Error closing raw WAV for mic{mic_id}: {e}")

        # Close processed writers
        for mic_id, wf in enumerate(self._processed_writers):
            try:
                wf.close()
                logger.info(f"Session recorder [processed]: mic{mic_id} file closed")
            except Exception as e:
                logger.error(f"Error closing processed WAV for mic{mic_id}: {e}")

        self._raw_writers.clear()
        self._processed_writers.clear()
        self._is_open = False

        # Collect file sizes for manifest
        raw_files  = sorted(self._raw_dir.glob("session_mic*.wav"))
        proc_files = sorted(self._processed_dir.glob("session_mic*.wav"))

        metadata = {
            "session_start":  datetime.fromtimestamp(self._session_start).isoformat(),
            "session_end":    datetime.now().isoformat(),
            "duration_sec":   round(duration_sec, 2),
            "n_mics":         self._n_mics,
            "sample_rate":    self._sample_rate,
            "chunks_written": self._chunks_written,
            "processed_chunks_written": self._processed_chunks_written,
            "folders": {
                "raw": {
                    "description": "Original mic audio -- no processing applied",
                    "files": {
                        f.name: {"size_bytes": f.stat().st_size}
                        for f in raw_files
                    },
                },
                "processed": {
                    "description": "HPF + noise reduction + adaptive gain applied",
                    "files": {
                        f.name: {"size_bytes": f.stat().st_size}
                        for f in proc_files
                        if f.stat().st_size > 44   # skip empty WAV headers
                    },
                },
            },
        }

        manifest_path = self._session_dir / "session_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info(
            f"Session recording closed: {self._session_dir.name} | "
            f"duration={duration_sec/60:.1f}min | "
            f"raw_chunks={self._chunks_written} | "
            f"processed_chunks={self._processed_chunks_written}"
        )
        return metadata
