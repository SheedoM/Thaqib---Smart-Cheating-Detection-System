"""
Real-time audio pre-processor for Thaqib's audio pipeline.

Applies three adaptive stages before VAD and Whisper:

    1. High-pass filter  — removes sub-bass rumble (HVAC, AC, vibration)
       Uses a 4th-order Butterworth filter (scipy).  Zero-phase via sosfilt.

    2. Noise reduction   — spectral subtraction using a learned noise profile.
       Uses the `noisereduce` library (graceful fallback if not installed).
       Noise profile is learned automatically from GLOBAL/SILENT chunks.

    3. Adaptive gain     — normalises RMS amplitude to a consistent target
       so Whisper always receives a well-levelled signal regardless of
       microphone sensitivity or distance.

The preprocessor is designed to be stateful and adaptive:
    - It learns the room's noise floor from real-time silent/global frames.
    - All stages have individual enable/disable switches.
    - All operations fail gracefully with a logged warning.
"""

import logging
import numpy as np

logger = logging.getLogger(__name__)


class AudioPreprocessor:
    """
    Stateful audio pre-processor that adapts to the exam room's acoustic
    environment in real time.

    Usage inside the pipeline:
        1. Create once and share between all mics.
        2. Call add_noise_sample() for every GLOBAL / SILENT chunk.
        3. Call process() on each mic's audio before VAD and Whisper.
    """

    def __init__(
        self,
        hpf_cutoff: int = 100,
        noise_reduction: bool = True,
        noise_reduction_strength: float = 0.75,
        adaptive_gain: bool = True,
        target_rms: float = 0.05,
        noise_profile_max_chunks: int = 30,
    ):
        """
        Args:
            hpf_cutoff:               High-pass cutoff in Hz.  0 = disabled.
            noise_reduction:          Enable spectral noise reduction.
            noise_reduction_strength: How aggressively to suppress noise (0–1).
                                      0.75 = remove 75 % of noise energy.
            adaptive_gain:            Normalise RMS to target_rms.
            target_rms:               Target signal RMS after gain stage.
            noise_profile_max_chunks: Max silent chunks to build noise profile.
        """
        self._hpf_cutoff                = hpf_cutoff
        self._noise_reduction           = noise_reduction
        self._nr_strength               = noise_reduction_strength
        self._adaptive_gain             = adaptive_gain
        self._target_rms                = target_rms
        self._noise_profile_max_chunks  = noise_profile_max_chunks

        # Noise profile state (built incrementally from GLOBAL/SILENT chunks)
        self._noise_chunks: list[np.ndarray] = []
        self._noise_profile: np.ndarray | None = None
        self._noise_profile_ready: bool = False

        # Cached Butterworth filter coefficients (per sample-rate)
        self._sos: np.ndarray | None = None
        self._sos_sr: int | None = None

        # Per-run stats for monitoring
        self._chunks_processed: int = 0
        self._nr_applied: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def noise_profile_ready(self) -> bool:
        """True once enough silent frames have been collected."""
        return self._noise_profile_ready

    @property
    def noise_chunks_collected(self) -> int:
        return len(self._noise_chunks)

    def add_noise_sample(self, audio: np.ndarray, sr: int) -> None:
        """
        Feed a known-noise frame (GLOBAL or SILENT classification) to the
        noise profile learner.

        Called by the pipeline main loop — NOT by the VAD thread.
        Thread-safe: numpy operations on separate objects, no shared state.
        """
        if len(self._noise_chunks) >= self._noise_profile_max_chunks:
            return  # profile is complete — no need for more samples

        # Only use frames with meaningful signal (not digital silence)
        rms = float(np.sqrt(np.mean(audio ** 2)))
        if rms < 1e-5:
            return

        self._noise_chunks.append(audio.copy())
        logger.debug(
            f"Noise profile: {len(self._noise_chunks)}/{self._noise_profile_max_chunks} "
            f"chunks collected (rms={rms:.5f})"
        )

        # Minimum 5 samples before enabling noise reduction
        if len(self._noise_chunks) >= 5:
            self._noise_profile = np.concatenate(self._noise_chunks)
            if not self._noise_profile_ready:
                self._noise_profile_ready = True
                logger.info(
                    f"Noise profile ready — spectral noise reduction activated "
                    f"({len(self._noise_chunks)} calibration frames)"
                )

    def process(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """
        Apply the full preprocessing chain to a single audio chunk.

        Stages (in order):
            1. High-pass filter (if hpf_cutoff > 0)
            2. Noise reduction  (if noise_reduction and profile is ready)
            3. Adaptive gain    (if adaptive_gain)

        Returns a new float32 array — does not modify the input in-place.
        """
        audio = audio.astype(np.float32)
        self._chunks_processed += 1

        if self._hpf_cutoff > 0:
            audio = self._highpass(audio, sr)

        if self._noise_reduction and self._noise_profile_ready:
            audio = self._noise_reduce(audio, sr)

        if self._adaptive_gain:
            audio = self._normalize_rms(audio)

        return audio

    # ------------------------------------------------------------------
    # DSP stages
    # ------------------------------------------------------------------

    def _highpass(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """4th-order Butterworth high-pass filter (removes sub-bass / HVAC)."""
        try:
            from scipy.signal import butter, sosfilt

            # Cache coefficients per sample-rate
            if self._sos is None or self._sos_sr != sr:
                self._sos = butter(
                    4, self._hpf_cutoff, btype="high", fs=sr, output="sos"
                )
                self._sos_sr = sr
                logger.debug(f"HPF coefficients computed: cutoff={self._hpf_cutoff}Hz, sr={sr}")

            return sosfilt(self._sos, audio).astype(np.float32)

        except ImportError:
            logger.debug("scipy not available — HPF stage skipped (pip install scipy)")
            return audio
        except Exception as e:
            logger.debug(f"HPF error ({e}) — stage skipped")
            return audio

    def _noise_reduce(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """
        Spectral subtraction using the learned noise profile.

        Uses noisereduce's non-stationary mode which handles time-varying
        backgrounds (chair scraping, coughing, intermittent HVAC).
        """
        try:
            import noisereduce as nr

            reduced = nr.reduce_noise(
                y=audio,
                sr=sr,
                y_noise=self._noise_profile,
                prop_decrease=self._nr_strength,
                stationary=False,       # non-stationary: better for exam room
                n_fft=512,              # balance accuracy vs latency
            )
            self._nr_applied += 1
            return np.clip(reduced, -1.0, 1.0).astype(np.float32)

        except ImportError:
            if self._nr_applied == 0:
                logger.warning(
                    "noisereduce not installed — noise reduction stage skipped. "
                    "Install with: pip install noisereduce"
                )
            return audio
        except Exception as e:
            logger.debug(f"Noise reduction error ({e}) — stage skipped")
            return audio

    def _normalize_rms(self, audio: np.ndarray) -> np.ndarray:
        """
        Adaptive gain: scale the signal so its RMS equals target_rms.

        Safety clamps: gain is bounded to [0.1, 20.0] to prevent
        amplifying digital silence into noise or clipping loud signals.
        """
        rms = float(np.sqrt(np.mean(audio ** 2)))
        if rms > 1e-10:
            gain = self._target_rms / rms
            gain = np.clip(gain, 0.1, 20.0)
            audio = (audio * gain)
        return np.clip(audio, -1.0, 1.0).astype(np.float32)

    def __repr__(self) -> str:
        return (
            f"AudioPreprocessor(hpf={self._hpf_cutoff}Hz, "
            f"nr={self._noise_reduction}[{self._nr_strength:.0%}], "
            f"gain={self._adaptive_gain}→{self._target_rms:.3f}rms, "
            f"noise_ready={self._noise_profile_ready})"
        )
