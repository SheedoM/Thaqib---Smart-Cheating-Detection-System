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
import threading
import time

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
        transient_suppression: bool = True,
        transient_threshold: float = 0.65,
        transient_damping: float = 0.15,
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
        self._transient_suppression     = transient_suppression
        self._transient_threshold       = transient_threshold
        self._transient_damping         = transient_damping

        # Check if noisereduce is installed
        try:
            import noisereduce as nr
            self._noisereduce_installed = True
        except ImportError:
            self._noisereduce_installed = False
            logger.warning(
                "noisereduce not installed — noise reduction stage fallback activated "
                "(mathematical moving-average energy smoothing envelope). "
                "Install with: pip install noisereduce"
            )

        # Decay envelope state: trailing energy per mic
        self._prev_rms: dict[int, float] = {}
        self._lock = threading.Lock()

        # Per-mic noise profile state (built incrementally from GLOBAL/SILENT chunks).
        # Each mic has its own isolated profile because mics at different positions
        # experience different acoustic environments (HVAC proximity, wall reflections,
        # distance from students). A shared profile causes over-subtraction on quiet
        # mics (removing speech harmonics) and under-subtraction on noisy mics.
        self._noise_chunks: dict[int, list[np.ndarray]] = {}     # mic_id -> chunk list
        self._noise_profiles: dict[int, np.ndarray] = {}         # mic_id -> profile array
        self._noise_profile_ready: dict[int, bool] = {}          # mic_id -> ready flag

        # Cached Butterworth filter coefficients (per sample-rate)
        self._sos: np.ndarray | None = None
        self._sos_sr: int | None = None

        # Per-run stats for monitoring
        self._chunks_processed: int = 0
        self._nr_applied: int = 0
        self._transient_detected_times: dict[int, float] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def noise_profile_ready(self) -> bool:
        """True once at least one mic has a ready noise profile."""
        with self._lock:
            return any(self._noise_profile_ready.values()) if self._noise_profile_ready else False

    def noise_profile_ready_for_mic(self, mic_id: int) -> bool:
        """True once the specific mic's noise profile has been established."""
        with self._lock:
            return self._noise_profile_ready.get(mic_id, False)

    @property
    def noise_chunks_collected(self) -> int:
        """Total noise chunks collected across all mics."""
        with self._lock:
            return sum(len(v) for v in self._noise_chunks.values())

    def noise_chunks_collected_for_mic(self, mic_id: int) -> int:
        """Noise chunks collected for a specific mic."""
        with self._lock:
            return len(self._noise_chunks.get(mic_id, []))

    def add_noise_sample(self, audio: np.ndarray, sr: int, mic_id: int = 0) -> None:
        """
        Feed a known-noise frame (GLOBAL or SILENT classification) to the
        per-mic noise profile learner.

        Each microphone maintains an independent noise profile because mics
        at different positions experience different acoustic environments.
        Using a shared profile causes over-subtraction on quiet mics (removing
        speech harmonics) and under-subtraction on noisy mics.

        Args:
            audio:  Single-mic audio array for one chunk.
            sr:     Sample rate.
            mic_id: Microphone index (0-based). Each mic has its own profile.

        Called by the pipeline main loop — NOT by the VAD thread.
        Thread-safe: protected by self._lock.
        """
        with self._lock:
            # Initialise per-mic state on first encounter
            if mic_id not in self._noise_chunks:
                self._noise_chunks[mic_id] = []
                self._noise_profile_ready[mic_id] = False

            chunks = self._noise_chunks[mic_id]
            if len(chunks) >= self._noise_profile_max_chunks:
                return  # this mic's profile is complete

            # Only use frames with meaningful signal (not digital silence)
            rms = float(np.sqrt(np.mean(audio ** 2)))
            if rms < 1e-5:
                return

            chunks.append(audio.copy())
            logger.debug(
                f"Noise profile mic{mic_id}: {len(chunks)}/{self._noise_profile_max_chunks} "
                f"chunks collected (rms={rms:.5f})"
            )

            # Minimum 5 samples before enabling noise reduction for this mic
            if len(chunks) >= 5:
                self._noise_profiles[mic_id] = np.concatenate(chunks)
                if not self._noise_profile_ready.get(mic_id, False):
                    self._noise_profile_ready[mic_id] = True
                    logger.info(
                        f"Noise profile ready mic{mic_id} — spectral noise reduction activated "
                        f"({len(chunks)} calibration frames)"
                    )

    def reset_noise_profile(self) -> None:
        """Reset all per-mic learned noise profiles to trigger recalibration."""
        with self._lock:
            self._noise_chunks.clear()
            self._noise_profiles.clear()
            self._noise_profile_ready.clear()
            self._prev_rms.clear()
        logger.info("AudioPreprocessor all per-mic noise profiles reset.")

    def process(self, audio: np.ndarray, sr: int, mic_id: int = 0, bypass_agc: bool = False) -> np.ndarray:
        """
        Apply the full preprocessing chain to a single audio chunk.

        Stages (in order):
            1. Transient suppression (if transient_suppression)
            2. High-pass filter (if hpf_cutoff > 0)
            3. Noise reduction  (if noise_reduction and this mic's profile is ready / fallback)
            4. Adaptive gain    (if adaptive_gain and not bypass_agc)

        Returns a new float32 array — does not modify the input in-place.
        """
        audio = audio.astype(np.float32)
        self._chunks_processed += 1

        if self._transient_suppression:
            audio = self._suppress_transients(audio, sr, mic_id=mic_id)

        if self._hpf_cutoff > 0:
            audio = self._highpass(audio, sr)

        if self._noise_reduction:
            mic_ready = False
            with self._lock:
                mic_ready = self._noise_profile_ready.get(mic_id, False)

            if mic_ready:
                if self._noisereduce_installed:
                    audio = self._noise_reduce(audio, sr, mic_id=mic_id)
            else:
                # Apply mathematical decay envelope as a fallback
                audio = self._apply_decay_envelope(audio, mic_id=mic_id)

        if self._adaptive_gain and not bypass_agc:
            audio = self._normalize_rms(audio)

        return audio

    # ------------------------------------------------------------------
    # DSP stages
    # ------------------------------------------------------------------

    def _suppress_transients(self, audio: np.ndarray, sr: int, mic_id: int = 0) -> np.ndarray:
        """
        Detects and attenuates high-frequency transient spikes (e.g. paper shuffling, pen clicks).
        Computes FFT, checks ratio of energy above 6000 Hz, and attenuates those bins if ratio > threshold.
        """
        if len(audio) < 16:
            return audio

        try:
            fft_vals = np.fft.rfft(audio)
            freqs = np.fft.rfftfreq(len(audio), d=1.0/sr)
            
            # Compute energies
            energies = np.abs(fft_vals) ** 2
            total_energy = np.sum(energies)
            
            if total_energy < 1e-10:
                return audio
                
            hf_mask = freqs >= 6000.0
            hf_energy = np.sum(energies[hf_mask])
            
            ratio = hf_energy / total_energy
            
            if ratio > self._transient_threshold:
                # Damp high frequencies
                with self._lock:
                    self._transient_detected_times[mic_id] = time.time()
                fft_vals[hf_mask] *= self._transient_damping
                logger.info(
                    f"[Transient Suppressor] Sharp transient detected (HF ratio={ratio:.3f} > {self._transient_threshold:.3f}). "
                    f"Attenuating high frequencies by factor {self._transient_damping}."
                )
                # Reconstruct signal
                audio = np.fft.irfft(fft_vals, n=len(audio)).astype(np.float32)
                
            return audio
        except Exception as e:
            logger.warning(f"Transient suppressor error ({e}) — stage skipped")
            return audio

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

    def _noise_reduce(self, audio: np.ndarray, sr: int, mic_id: int = 0) -> np.ndarray:
        """
        Spectral subtraction using the per-mic learned noise profile.

        Each mic uses its own isolated noise profile so that mics in
        different acoustic positions (near AC unit, near window, near
        whiteboard) each get noise subtracted accurately without
        contaminating each other's models.

        Uses noisereduce's non-stationary mode which handles time-varying
        backgrounds (chair scraping, coughing, intermittent HVAC).
        """
        try:
            import noisereduce as nr

            with self._lock:
                noise_profile = self._noise_profiles.get(mic_id)

            if noise_profile is None:
                return audio

            reduced = nr.reduce_noise(
                y=audio,
                sr=sr,
                y_noise=noise_profile,
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

    def _apply_decay_envelope(self, audio: np.ndarray, mic_id: int) -> np.ndarray:
        """
        Mathematical moving-average energy smoothing envelope fallback.
        Damps the trailing decay of acoustic energy chunks by 50% per chunk.
        """
        with self._lock:
            current_rms = float(np.sqrt(np.mean(audio ** 2)))
            prev_rms = self._prev_rms.get(mic_id, 0.0)
            expected_rms = prev_rms * 0.5

            # If the energy is decaying, but slower than 50% per chunk, damp it
            if current_rms > 1e-5 and current_rms > expected_rms and current_rms < prev_rms:
                audio = audio * (expected_rms / current_rms)
                current_rms = expected_rms

            self._prev_rms[mic_id] = current_rms
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
            f"transient_suppress={self._transient_suppression}[thr={self._transient_threshold:.2f}, damp={self._transient_damping:.2f}], "
            f"nr={self._noise_reduction}[{self._nr_strength:.0%}], "
            f"gain={self._adaptive_gain}→{self._target_rms:.3f}rms, "
            f"noise_ready={self._noise_profile_ready})"
        )
