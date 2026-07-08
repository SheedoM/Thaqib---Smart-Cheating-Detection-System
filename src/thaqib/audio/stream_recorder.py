"""
Session audio recorder for the web/dashboard monitoring flow.

Each active hall microphone is recorded continuously from its (simulator or
real) PCM feed into a raw little-endian PCM16 mono file, tagged with the
wall-clock time of the first sample (``t0``). Because both this recorder and
the video pipeline run on the same wall clock, an alert's timestamp maps
directly to a byte/second offset into the recording — that is what lets the
AV composer mux the *correct* audio slice onto an alert clip.

Raw PCM (not WAV) is used deliberately: there is no header to finalise, so
ffmpeg can slice a still-growing file mid-recording via
``-f s16le -ar <rate> -ac 1 -ss <start> -to <end>``.
"""

from __future__ import annotations

import logging
import threading
import time
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)


class MicStreamRecorder:
    """Continuously records one microphone's PCM16-mono feed to a raw file."""

    def __init__(self, mic_id: str, stream_url: str, out_dir: Path, default_sample_rate: int = 16000):
        self.mic_id = mic_id
        self.stream_url = stream_url
        self.sample_rate = default_sample_rate
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)

        time_str = time.strftime("%Y%m%d_%H%M%S")
        safe_mic = "".join(c for c in mic_id if c.isalnum() or c in ("-", "_")) or "mic"
        self.pcm_path = self.out_dir / f"{safe_mic}_{time_str}.pcm"

        # Wall-clock epoch of the first recorded sample. Set once, when the
        # read loop actually begins pulling audio.
        self.t0: float | None = None

        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._fh = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, daemon=True, name=f"MicRec-{self.mic_id}"
        )
        self._thread.start()

    def _run(self) -> None:
        try:
            self._fh = open(self.pcm_path, "wb")
        except OSError as exc:
            logger.error("MicRec %s: cannot open %s: %s", self.mic_id, self.pcm_path, exc)
            return

        while not self._stop.is_set():
            try:
                req = urllib.request.urlopen(self.stream_url, timeout=5)
                # Header advertises the true sample rate; fall back to default.
                hdr = req.headers.get("X-Audio-Sample-Rate")
                if hdr:
                    try:
                        self.sample_rate = int(hdr)
                    except ValueError:
                        pass
                if self.t0 is None:
                    # First byte defines the recording's time origin.
                    self.t0 = time.time()
                logger.info(
                    "MicRec %s: recording %s @ %d Hz -> %s",
                    self.mic_id, self.stream_url, self.sample_rate, self.pcm_path.name,
                )
                while not self._stop.is_set():
                    chunk = req.read(8192)
                    if not chunk:
                        break  # stream ended → reconnect
                    self._fh.write(chunk)
            except Exception as exc:
                if self._stop.is_set():
                    break
                logger.warning("MicRec %s: stream error (%s); retrying in 1s", self.mic_id, exc)
                time.sleep(1.0)

        try:
            if self._fh is not None:
                self._fh.flush()
                self._fh.close()
        except Exception:
            pass
        logger.info("MicRec %s: stopped", self.mic_id)

    def offset_for(self, epoch: float) -> float | None:
        """Seconds into the recording that correspond to wall-clock ``epoch``.

        Returns None if recording has not started (t0 unknown).
        """
        if self.t0 is None:
            return None
        return max(0.0, epoch - self.t0)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
