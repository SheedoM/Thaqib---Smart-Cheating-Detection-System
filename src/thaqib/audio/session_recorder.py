"""
Continuous session audio recorder.

Records ALL incoming audio from every microphone to WAV files for the
entire duration of an exam session.  This is separate from evidence clips
(which capture only the cheating moment).  Session recordings allow:

    - Post-exam forensic analysis of the full audio
    - Re-running the discriminator with different thresholds offline
    - Verifying the system's decisions against the raw audio
    - Evidence for appeals / legal review

Files are written incrementally (streamed) — no large in-memory buffer.
Each microphone gets its own WAV file:

    <output_dir>/
        session_<YYYY-MM-DD_HH-MM-SS>/
            session_mic0.wav
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

    Usage:
        recorder = SessionAudioRecorder(output_dir="sessions")
        recorder.open(n_mics=2, sample_rate=16000)

        # Call on every chunk inside the pipeline loop:
        recorder.write_chunk(chunk)

        # On session end:
        recorder.close()
        print(recorder.session_dir)  # path to the session folder
    """

    def __init__(self, output_dir: str = "sessions"):
        self._output_dir = Path(output_dir)
        self._session_dir: Path | None = None
        self._wav_writers: list[wave.Wave_write] = []
        self._n_mics: int = 0
        self._sample_rate: int = 16000
        self._chunks_written: int = 0
        self._session_start: float = 0.0
        self._is_open: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def session_dir(self) -> Path | None:
        """Path to the current session directory (None if not started)."""
        return self._session_dir

    @property
    def is_open(self) -> bool:
        """True if a recording session is currently active."""
        return self._is_open

    def open(self, n_mics: int, sample_rate: int = 16000) -> Path:
        """
        Start a new recording session.

        Creates a timestamped session directory and opens one WAV file
        per microphone.  WAV files are opened in streaming mode (data is
        written chunk by chunk, not buffered in memory).

        Args:
            n_mics: Number of microphones to record.
            sample_rate: Sample rate in Hz (must match the pipeline source).

        Returns:
            Path to the created session directory.
        """
        if self._is_open:
            logger.warning("Session recorder already open — close first")
            return self._session_dir

        # check available disk space before opening files
        import shutil, time
        total, used, free = shutil.disk_usage(str(self._output_dir.parent
                                              if self._output_dir.exists()
                                              else Path.cwd()))
        free_mb = free / (1024 * 1024)
        if free_mb < 500:
            logger.critical(
                f"Session recorder: LOW DISK SPACE — only {free_mb:.0f} MB free. "
                f"Session recording may fail or truncate the exam audio. "
                f"Free at least 500 MB before starting."
            )
        else:
            logger.info(f"Disk space OK: {free_mb:.0f} MB free")

        self._session_start = time.time()
        self._n_mics = n_mics
        self._sample_rate = sample_rate
        self._chunks_written = 0

        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self._session_dir = self._output_dir / f"session_{ts}"
        self._session_dir.mkdir(parents=True, exist_ok=True)

        self._wav_writers = []
        for mic_id in range(n_mics):
            wav_path = self._session_dir / f"session_mic{mic_id}.wav"
            wf = wave.open(str(wav_path), "wb")
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            self._wav_writers.append(wf)
            logger.info(f"Session recorder: mic{mic_id} -> {wav_path.name}")

        self._is_open = True
        logger.info(
            f"Session recording started: {self._session_dir} "
            f"({n_mics} mics, {sample_rate}Hz)"
        )
        return self._session_dir

    def write_chunk(self, chunk: AudioChunk) -> None:
        """
        Write one audio chunk from all microphones to their WAV files.

        Called on every chunk inside the pipeline loop.  This is a fast
        operation (pure I/O, no DSP).

        Args:
            chunk: AudioChunk with mic_data shape (n_mics, n_samples).
        """
        if not self._is_open:
            return

        n_mics = chunk.mic_data.shape[0]
        for mic_id in range(min(n_mics, len(self._wav_writers))):
            audio = chunk.mic_data[mic_id]

            # Convert float32 [-1, 1] to int16 PCM
            if audio.dtype in (np.float32, np.float64):
                audio_int16 = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
            else:
                audio_int16 = audio.astype(np.int16)

            self._wav_writers[mic_id].writeframes(audio_int16.tobytes())

        self._chunks_written += 1

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

        # Close all WAV writers
        for mic_id, wf in enumerate(self._wav_writers):
            try:
                wf.close()
                logger.info(f"Session recorder: mic{mic_id} file closed")
            except Exception as e:
                logger.error(f"Error closing WAV for mic{mic_id}: {e}")

        self._wav_writers.clear()
        self._is_open = False

        # Build file list
        wav_files = sorted(self._session_dir.glob("session_mic*.wav"))
        file_sizes = {f.name: f.stat().st_size for f in wav_files}

        # Write manifest
        metadata = {
            "session_start": datetime.fromtimestamp(self._session_start).isoformat(),
            "session_end": datetime.now().isoformat(),
            "duration_sec": round(duration_sec, 2),
            "n_mics": self._n_mics,
            "sample_rate": self._sample_rate,
            "chunks_written": self._chunks_written,
            "files": {name: {"size_bytes": sz} for name, sz in file_sizes.items()},
        }

        manifest_path = self._session_dir / "session_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info(
            f"Session recording closed: {self._session_dir.name} | "
            f"duration={duration_sec/60:.1f}min | "
            f"chunks={self._chunks_written} | "
            f"files={[f.name for f in wav_files]}"
        )
        return metadata
