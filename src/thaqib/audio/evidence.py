"""
Audio evidence recorder.

Saves cheating evidence when an audio alert is triggered:
- WAV file containing the audio clip
- JSON file with metadata (transcript, keywords, confidence, etc.)
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

import numpy as np

from thaqib.audio.models import AudioAlert

logger = logging.getLogger(__name__)


class AudioEvidenceRecorder:
    """
    Saves audio cheating evidence to disk.

    For each AudioAlert, creates two files in the alerts/ directory:
        - audio_alert_YYYYMMDD_HHMMSS_micN.wav  — raw audio clip
        - audio_alert_YYYYMMDD_HHMMSS_micN.json  — metadata

    Example:
        >>> recorder = AudioEvidenceRecorder(output_dir="alerts")
        >>> wav_path, json_path = recorder.save_alert(alert)
        >>> print(f"Evidence saved: {wav_path}")
    """

    def __init__(self, output_dir: str = "alerts"):
        """
        Args:
            output_dir: Directory to save evidence files.
        """
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def save_alert(self, alert: AudioAlert) -> tuple[str, str]:
        """
        Save an audio alert as WAV + JSON evidence files.

        Args:
            alert: The audio cheating alert to save.

        Returns:
            Tuple of (wav_path, json_path) for the saved files.
        """
        timestamp_str = datetime.fromtimestamp(alert.timestamp).strftime(
            "%Y%m%d_%H%M%S"
        )
        base_name = f"audio_alert_{timestamp_str}_mic{alert.mic_id}"

        wav_path = self._output_dir / f"{base_name}.wav"
        json_path = self._output_dir / f"{base_name}.json"

        # Avoid overwriting: append counter if file exists
        counter = 1
        while wav_path.exists() or json_path.exists():
            wav_path = self._output_dir / f"{base_name}_{counter}.wav"
            json_path = self._output_dir / f"{base_name}_{counter}.json"
            counter += 1

        # Save WAV
        self._save_wav(wav_path, alert.audio_clip, alert.sample_rate)

        # Save JSON metadata
        metadata = {
            "timestamp": datetime.fromtimestamp(alert.timestamp).isoformat(),
            "timestamp_unix": alert.timestamp,
            "mic_id": alert.mic_id,
            "active_mics": alert.active_mics,
            "transcript": alert.transcript,
            "matched_keywords": alert.matched_keywords,
            "confidence": alert.confidence,
            "chunk_index": alert.chunk_index,
            "sample_rate": alert.sample_rate,
            "duration_ms": len(alert.audio_clip) / alert.sample_rate * 1000,
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info(
            f"Audio evidence saved: {wav_path.name} + {json_path.name} "
            f"(keywords: {alert.matched_keywords})"
        )

        return str(wav_path), str(json_path)

    @staticmethod
    def _save_wav(path: Path, audio: np.ndarray, sample_rate: int) -> None:
        """Save audio samples as a WAV file using scipy or wave module."""
        try:
            from scipy.io import wavfile

            # scipy expects int16 for WAV
            if audio.dtype == np.float32 or audio.dtype == np.float64:
                audio_int16 = np.clip(audio * 32767, -32768, 32767).astype(
                    np.int16
                )
            else:
                audio_int16 = audio.astype(np.int16)

            wavfile.write(str(path), sample_rate, audio_int16)

        except ImportError:
            # Fallback: use built-in wave module
            import wave
            import struct

            if audio.dtype == np.float32 or audio.dtype == np.float64:
                audio_int16 = np.clip(audio * 32767, -32768, 32767).astype(
                    np.int16
                )
            else:
                audio_int16 = audio.astype(np.int16)

            with wave.open(str(path), "w") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(sample_rate)
                wf.writeframes(audio_int16.tobytes())
