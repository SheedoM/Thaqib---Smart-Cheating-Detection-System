"""
Audio evidence recorder.

Saves cheating evidence when an audio alert is triggered:
- WAV file containing the audio clip
- JSON file with metadata (transcript, keywords, confidence, etc.)
"""

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path

import numpy as np

from thaqib.audio.models import AudioAlert, CheatEpisode

logger = logging.getLogger(__name__)


class AudioEvidenceRecorder:
    """
    Saves audio cheating evidence to disk.

    For each AudioAlert, creates two files in the alerts/ directory:
        - audio_alert_SYS{HH-MM-SS}_OFFSET{HHhMMmSSs}_micN.wav  — raw audio clip
        - audio_alert_SYS{HH-MM-SS}_OFFSET{HHhMMmSSs}_micN.json  — metadata

    SYS = wall-clock time when the cheating was captured (not saved).
    OFFSET = seconds elapsed since the recording/exam started.

    Example:
        >>> recorder = AudioEvidenceRecorder(output_dir="alerts")
        >>> wav_path, json_path = recorder.save_alert(alert)
        >>> print(f"Evidence saved: {wav_path}")
    """

    def __init__(
        self,
        output_dir: str = "alerts",
        mic_names: "list[str] | dict[int, str] | None" = None,
    ):
        """
        Args:
            output_dir: Directory to save evidence files.
            mic_names:  Mic label registry.  Accepts:
                        - list[str]       index 0 = first label
                        - dict[int, str]  {mic_id: label} explicit mapping
                        - None            fall back to 'mic0', 'mic1', ...

                        Labels can be ANYTHING: IP addresses, names, seat
                        numbers, UUIDs, etc.  Any number of mics is supported.

                        Examples:
                            ['front', 'back']
                            {0: '192.168.1.10', 1: '192.168.1.11'}
                            {0: 'row_A_01', 99: 'door_cam'}
        """
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Normalise to dict[int, str] regardless of input type
        if isinstance(mic_names, dict):
            self._mic_registry: dict[int, str] = {
                int(k): str(v) for k, v in mic_names.items()
            }
        elif isinstance(mic_names, list):
            self._mic_registry = {i: name for i, name in enumerate(mic_names)}
        else:
            self._mic_registry = {}

    # ------------------------------------------------------------------
    # Mic label helpers
    # ------------------------------------------------------------------

    def _mic_label(self, mic_id: int) -> str:
        """Return the display label for mic_id.

        Preserves original format (IP, name, etc.) — used in JSON and logs.
        Falls back to 'mic{id}' for unregistered mics.
        """
        return self._mic_registry.get(mic_id, f"mic{mic_id}")

    @staticmethod
    def _sanitize(label: str) -> str:
        """Convert any label to a safe filename component.

        Replaces characters that are illegal or problematic in filenames
        (on Windows/Linux/macOS) with underscores.

        Examples:
            '192.168.1.10'   -> '192_168_1_10'
            '[2001:db8::1]'  -> '2001_db8__1'
            'front cam #2'   -> 'front_cam_2'
            'row_A_seat_01'  -> 'row_A_seat_01'   (unchanged)
        """
        import re
        safe = re.sub(r'[^\w\-]', '_', label)
        safe = re.sub(r'_+', '_', safe)      # collapse consecutive underscores
        return safe.strip('_') or 'mic_unknown'

    def _mic_filename_part(self, mic_id: int) -> str:
        """Sanitized mic label safe for use in filenames."""
        return self._sanitize(self._mic_label(mic_id))


    def save_alert(self, alert: AudioAlert) -> tuple[str, str]:
        """
        Save an audio alert as WAV + JSON evidence files.

        Args:
            alert: The audio cheating alert to save.

        Returns:
            Tuple of (wav_path, json_path) for the saved files.
        """
        # sys_time_str reflects when the suspicious audio was CAPTURED,
        # not when the file was saved (which may be seconds later due to
        # async inference). This is intentional.
        sys_time_str = datetime.fromtimestamp(alert.timestamp).strftime("%H-%M-%S")

        # Offset from recording start
        offset_sec = alert.timestamp - alert.recording_start
        offset_h   = int(offset_sec // 3600)
        offset_m   = int((offset_sec % 3600) // 60)
        offset_s   = int(offset_sec % 60)
        offset_str = f"{offset_h:02d}h{offset_m:02d}m{offset_s:02d}s"

        mic_label = self._mic_label(alert.mic_id)              # display (raw IP / name)
        mic_safe  = self._mic_filename_part(alert.mic_id)      # filename-safe
        base_name = f"audio_alert_SYS{sys_time_str}_OFFSET{offset_str}_{mic_safe}"

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

        # Compute SHA-256 of the saved WAV for forensic integrity.
        # Any post-save modification of the file will produce a different hash.
        wav_sha256 = self._sha256(wav_path)

        # Save JSON metadata
        metadata = {
            "timestamp": datetime.fromtimestamp(alert.timestamp).isoformat(),
            "timestamp_unix": alert.timestamp,
            "system_time":      datetime.fromtimestamp(alert.timestamp).strftime("%H:%M:%S"),
            "recording_offset": f"{offset_h:02d}:{offset_m:02d}:{offset_s:02d}",
            "recording_start":  datetime.fromtimestamp(alert.recording_start).isoformat(),
            "mic_id":   alert.mic_id,
            "mic_name": self._mic_label(alert.mic_id),
            "active_mics": [
                {"id": m, "name": self._mic_label(m)} for m in alert.active_mics
            ],
            "transcript": alert.transcript,
            "matched_keywords": alert.matched_keywords,
            "confidence": alert.confidence,
            "chunk_index": alert.chunk_index,
            "sample_rate": alert.sample_rate,
            "duration_ms": len(alert.audio_clip) / alert.sample_rate * 1000,
            "wav_file": wav_path.name,
            "wav_sha256": wav_sha256,
            # Discriminator forensic data for audit trail
            "discriminator_decision": {
                "baseline_ratio": round(alert.discriminator_baseline, 4),
                "raw_ratio": round(alert.discriminator_raw_ratio, 4),
                "normalized_ratio": round(alert.discriminator_normalized_ratio, 4),
                "interpretation": (
                    f"Energy imbalance was {alert.discriminator_normalized_ratio:.2f}x "
                    f"the learned baseline of {alert.discriminator_baseline:.2f}x"
                ) if alert.discriminator_baseline > 0 else "N-mic mode (no ratio)",
            },
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info(
            f"Alert saved [{mic_label}]: {wav_path.name} | "
            f"keywords={alert.matched_keywords}"
        )

        return str(wav_path), str(json_path)

    @staticmethod
    def _sha256(path: Path) -> str:
        """Compute SHA-256 hex digest of a file for forensic integrity."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(65536), b""):
                h.update(block)
        return h.hexdigest()

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

    def save_episode(self, episode) -> "Path | None":
        """
        Save a confirmed CheatEpisode: full-duration WAV + JSON.

        Called when sustained cheating ends (grace period exceeded).
        Two files are created:
            episode_{mic_safe}_{YYYY-MM-DD_HH-MM-SS}.wav   — full audio (RAW)
            episode_{mic_safe}_{YYYY-MM-DD_HH-MM-SS}.json  — metadata

        The mic label in JSON/logs is the original display label (IP, name, etc.).
        The filename uses a sanitized version safe for all filesystems.

        Returns:
            Path to the JSON file, or None on failure.
        """
        mic_display = self._mic_label(episode.mic_id)           # original: '192.168.1.10'
        mic_safe    = self._sanitize(mic_display)               # filename: '192_168_1_10'

        if not episode.audio_chunks:
            logger.warning(
                f"Episode [{mic_display}] has no audio — skipping save"
            )
            return None

        self._output_dir.mkdir(parents=True, exist_ok=True)

        ts_str    = datetime.fromtimestamp(episode.start_time).strftime("%Y-%m-%d_%H-%M-%S")
        base      = f"episode_{mic_safe}_{ts_str}"
        wav_path  = self._output_dir / f"{base}.wav"
        json_path = self._output_dir / f"{base}.json"

        full_audio = episode.get_full_audio()
        self._save_wav(wav_path, full_audio, episode.sample_rate)   # fixed: was _write_wav

        wav_sha256 = self._sha256(wav_path)

        d = episode.duration_sec
        dur_fmt = f"{int(d//3600):02d}:{int((d%3600)//60):02d}:{int(d%60):02d}"

        metadata = {
            "type":               "cheat_episode",
            "mic_id":             episode.mic_id,
            "mic_name":           mic_display,       # raw label (IP / name) — not sanitized
            "start_time":         datetime.fromtimestamp(episode.start_time).isoformat(),
            "end_time":           datetime.fromtimestamp(episode.last_alert_time).isoformat(),
            "duration_sec":       round(d, 2),
            "duration_fmt":       dur_fmt,
            "audio_duration_sec": round(episode.audio_duration_sec, 2),
            "confirmed":          episode.confirmed,
            "alert_count":        episode.alert_count,
            "all_keywords":       episode.all_keywords,
            "all_transcripts":    episode.all_transcripts,
            "sample_rate":        episode.sample_rate,
            "wav_file":           wav_path.name,
            "wav_sha256":         wav_sha256,
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.warning(
            f"EPISODE SAVED [{mic_display}]: "
            f"duration={d:.1f}s | alerts={episode.alert_count} | "
            f"keywords={episode.all_keywords} | file={wav_path.name}"
        )
        return json_path
