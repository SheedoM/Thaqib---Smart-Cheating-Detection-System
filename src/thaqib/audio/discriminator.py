"""
Global vs. Local sound discriminator.

Analyzes multi-microphone audio to determine whether a sound
is heard by all microphones (global — not cheating) or only
by a few nearby microphones (local — possible cheating).
"""

import logging
import time

import numpy as np

from thaqib.audio.models import AudioChunk, SoundClassification

logger = logging.getLogger(__name__)


class GlobalLocalDiscriminator:
    """
    Classifies each audio chunk as SILENT, GLOBAL, or LOCAL
    based on energy distribution across microphones.

    Algorithm (2-mic mode):
        1. Compute RMS energy per microphone
        2. Learn baseline energy ratio during a calibration window
           (first N non-silent chunks at session start)
        3. Compute the NORMALIZED ratio symmetrically:
           norm_e0 = e0 / baseline_ratio, norm_e1 = e1
           normalized_ratio = max(norm_e0, norm_e1) / min(norm_e0, norm_e1)
        4. If normalized ratio >= local_ratio_multiplier → LOCAL
           This removes the structural imbalance between mic positions

    Algorithm (N-mic mode):
        1. Compute RMS energy per microphone.
        2. Learn baseline scale factors relative to the average energy:
           baseline_scale = median(mic_energy / mean_energy)
           during a calibration window.
        3. Normalize energies: norm_energy = energy / baseline_scale.
        4. Count how many microphones heard the normalized sound above global ratio threshold.
        5. If heard fraction >= global_fraction → GLOBAL, else LOCAL.

    Why calibration?
        Microphones placed at different distances from students will
        always show unequal energy even in silence.  Without a baseline,
        a ratio threshold of 2.0 fires on natural imbalance (measured
        at ~1.6x in real exam recordings), producing 36% false LOCAL
        rate.  With calibration, only sounds that are 2x LOUDER THAN
        NORMAL on one mic are flagged — cutting false positives to ~5%.

    Example:
        >>> disc = GlobalLocalDiscriminator()
        >>> result = disc.classify(audio_chunk)
        >>> if result.is_local:
        ...     print(f"Suspicious sound on mics: {result.active_mics}")
    """

    def __init__(
        self,
        silence_threshold: float = 0.01,
        global_ratio: float = 0.3,
        global_fraction: float = 0.6,
        local_ratio: float = 0.15,
        local_ratio_multiplier: float = 2.0,
        calibration_chunks: int = 30,
        recalibration_interval_sec: float = 300.0,
        on_recalibrate: "callable | None" = None,
        chunk_ms: int = 250,
    ):
        """
        Args:
            silence_threshold: RMS energy below this = silence (ignored).
            global_ratio: A mic "heard" the sound if its normalized
                          energy is >= this fraction of the loudest mic.
                          (N-mic mode only)
            global_fraction: If this fraction of mics heard it, classify
                             as GLOBAL (e.g., 0.6 = 60% of mics).
                             (N-mic mode only)
            local_ratio: Minimum normalized energy for a mic to count as
                         "active" in a LOCAL classification.
                         (N-mic mode only)
            local_ratio_multiplier: In 2-mic mode, a chunk is LOCAL when
                                    (raw_ratio / baseline_ratio) exceeds
                                    this value.  Default 2.0 means the
                                    energy imbalance must be 2x WORSE
                                    than the calibrated normal baseline.
            calibration_chunks: Number of non-silent chunks to use for
                                 learning the baseline energy ratio.
                                 Set to 0 to disable calibration (uses
                                 fixed 2.0 ratio as before).
            recalibration_interval_sec: After a baseline is learned, trigger
                                        a fresh recalibration every this many
                                        seconds.  0 = never recalibrate again
                                        after the initial calibration.
                                        Default: 300s (every 5 minutes).
        """
        self._silence_threshold = silence_threshold
        self._global_ratio = global_ratio
        self._global_fraction = global_fraction
        self._local_ratio = local_ratio
        self._local_ratio_multiplier = local_ratio_multiplier
        self._calibration_chunks = calibration_chunks
        self._recalibration_interval = recalibration_interval_sec
        self._on_recalibrate = on_recalibrate

        # Calibration state — populated during the first N non-silent chunks
        self._calibration_ratios: list[float] = []
        self._baseline_ratio: float | None = None  # None = still calibrating
        self._calibration_done: bool = (calibration_chunks == 0)
        self._last_calibration_time: float = time.monotonic()

        # N-mic calibration state
        self._calibration_nmics_ratios: list[np.ndarray] = []
        self._baseline_scales: np.ndarray | None = None

        # Hangover window state (anti-flip-flop logic)
        self._last_active_mic: int | None = None
        self._hangover_counter: int = 0
        # Derived from chunk_ms so hangover is always ~1.5 seconds
        # regardless of chunk size setting
        self._hangover_chunks: int = max(1, int(1500 / chunk_ms))

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @property
    def baseline_ratio(self) -> float | None:
        """
        Learned baseline energy ratio (dominant / quiet mic).
        None while still calibrating.
        """
        return self._baseline_ratio

    @property
    def is_calibrated(self) -> bool:
        """True once the baseline has been learned from enough chunks."""
        return self._calibration_done

    def reset_calibration(self) -> None:
        """Reset the baseline so a new session re-learns from scratch."""
        self._calibration_ratios.clear()
        self._baseline_ratio = None
        self._calibration_nmics_ratios.clear()
        self._baseline_scales = None
        self._calibration_done = (self._calibration_chunks == 0)
        self._last_calibration_time = time.monotonic()
        self._last_active_mic = None
        self._hangover_counter = 0
        logger.info("Discriminator calibration reset")
        if getattr(self, '_on_recalibrate', None):
            try:
                self._on_recalibrate()
            except Exception as e:
                logger.error(f"Failed to trigger on_recalibrate callback: {e}")

    # ------------------------------------------------------------------
    # Core classification
    # ------------------------------------------------------------------

    def classify(self, chunk: AudioChunk) -> SoundClassification:
        """
        Classify a multi-mic audio chunk as SILENT, GLOBAL, or LOCAL.

        Args:
            chunk: AudioChunk with mic_data shape (n_mics, n_samples).

        Returns:
            SoundClassification with the classification result and
            energy profile for dashboard display.
        """
        mic_data = chunk.mic_data  # (n_mics, n_samples)
        n_mics = mic_data.shape[0]

        # Step 1: Compute RMS energy per microphone
        energy = np.sqrt(np.mean(mic_data ** 2, axis=1))  # shape: (n_mics,)
        max_energy = np.max(energy)

        # Step 2: Check for silence
        if max_energy < self._silence_threshold:
            return SoundClassification(
                is_silent=True,
                energy_profile=energy,
            )

        # ── Centralized periodic recalibration check ──────────────────
        if (
            self._calibration_done
            and self._recalibration_interval > 0
            and (time.monotonic() - self._last_calibration_time)
                >= self._recalibration_interval
        ):
            elapsed_min = (time.monotonic() - self._last_calibration_time) / 60
            logger.info(
                f"Periodic recalibration triggered after {elapsed_min:.1f}min "
                f"— re-learning baseline scales..."
            )
            self.reset_calibration()

        # Step 3: Classify
        if n_mics == 1:
            return SoundClassification(
                is_local=True,
                active_mics=[0],
                energy_profile=energy,
            )
        elif n_mics == 2:
            return self._classify_2mic(energy)
        else:
            return self._classify_nmics(energy)

    def _classify_2mic(self, energy: np.ndarray) -> SoundClassification:
        """
        2-microphone classification with dynamic baseline calibration
        using symmetric channel normalization.

        During the first `calibration_chunks` non-silent chunks the
        discriminator learns the structural energy imbalance ratio between
        the two mic positions: baseline = median(e0 / e1).
        After calibration every new chunk is normalized by this baseline:
        norm_e0 = e0 / baseline, norm_e1 = e1.
        The normalized ratio = max(norm_e0, norm_e1) / min(norm_e0, norm_e1).
        This eliminates geographical detection bias between adjacent microphones.
        """
        e0, e1 = float(energy[0]), float(energy[1])
        # Guard: if either mic is dead, skip calibration update and return GLOBAL
        if e0 < self._silence_threshold or e1 < self._silence_threshold:
            return SoundClassification(is_global=True, energy_profile=energy)
        # Directional raw ratio for calibration
        calib_ratio = e0 / (e1 + 1e-10)

        # ── Calibration phase ─────────────────────────────────────────
        if not self._calibration_done:
            self._calibration_ratios.append(calib_ratio)
            n = len(self._calibration_ratios)
            remaining = self._calibration_chunks - n
            logger.debug(
                f"Calibrating baseline ratio: {n}/{self._calibration_chunks} "
                f"current={calib_ratio:.2f} (need {remaining} more non-silent chunks)"
            )

            if n >= self._calibration_chunks:
                # Compute baseline as the median of Mic0 / Mic1 energy ratio.
                # Cap between 0.28 and 3.5 to exclude extreme outlier whispers.
                capped = [r for r in self._calibration_ratios if 0.28 <= r <= 3.5]
                source = capped if len(capped) >= n // 2 else self._calibration_ratios
                self._baseline_ratio = float(np.median(source))
                self._calibration_done = True
                self._last_calibration_time = time.monotonic()
                logger.info(
                    f"Discriminator calibration complete: "
                    f"baseline_ratio (Mic0/Mic1)={self._baseline_ratio:.3f}x "
                    f"(from {n} chunks, {len(self._calibration_ratios)-len(capped)} outliers excluded).  "
                    f"Symmetric LOCAL threshold = {self._local_ratio_multiplier:.1f}x"
                )

            # During calibration treat everything as GLOBAL to avoid
            # false alerts while the baseline is still being established
            return SoundClassification(is_global=True, energy_profile=energy)

        # ── Post-calibration: normalize energies against learned baseline ──────
        # Scale Mic 0's energy relative to Mic 1's structural gain
        norm_e0 = e0 / self._baseline_ratio
        norm_e1 = e1

        # Symmetrical normalized ratio
        raw_ratio = max(e0, e1) / (min(e0, e1) + 1e-10)
        normalized_ratio = max(norm_e0, norm_e1) / (min(norm_e0, norm_e1) + 1e-10)

        if normalized_ratio >= self._local_ratio_multiplier:
            candidate_mic = 0 if norm_e0 > norm_e1 else 1
            if self._last_active_mic is not None and self._hangover_counter > 0:
                if candidate_mic != self._last_active_mic:
                    active_mic = self._last_active_mic
                    self._hangover_counter -= 1
                else:
                    active_mic = candidate_mic
                    self._hangover_counter = self._hangover_chunks
            else:
                active_mic = candidate_mic
                self._last_active_mic = active_mic
                self._hangover_counter = self._hangover_chunks

            logger.info(
                f"LOCAL (2-mic raw={raw_ratio:.2f}x, "
                f"baseline={self._baseline_ratio:.2f}x, "
                f"normalized_symmetric={normalized_ratio:.2f}x >= "
                f"{self._local_ratio_multiplier:.1f}x): "
                f"dominant mic={active_mic} (candidate={candidate_mic}, hangover={self._hangover_counter})"
            )
            return SoundClassification(
                is_local=True,
                active_mics=[active_mic],
                energy_profile=energy,
                # forensic fields for evidence JSON
                raw_ratio=float(raw_ratio),
                normalized_ratio=float(normalized_ratio),
                baseline_ratio=float(self._baseline_ratio),
            )
        else:
            if self._hangover_counter > 0:
                self._hangover_counter -= 1
                if self._hangover_counter == 0:
                    self._last_active_mic = None

            return SoundClassification(
                is_global=True,
                energy_profile=energy,
                raw_ratio=float(raw_ratio),
                normalized_ratio=float(normalized_ratio),
                baseline_ratio=float(self._baseline_ratio),
            )

    def _classify_nmics(self, energy: np.ndarray) -> SoundClassification:
        """
        N-microphone classification with dynamic baseline calibration
        using per-microphone average energy ratio normalization.

        During the calibration phase, it learns baseline scale factors relative
        to the average energy: baseline_scale = median(mic_energy / mean_energy).
        After calibration, energies are normalized: norm_energy = energy / baseline_scale.
        The loudest normalized microphone is tested for LOCAL vs GLOBAL classification.
        """
        n_mics = len(energy)

        # ── Calibration phase ─────────────────────────────────────────
        if not self._calibration_done:
            # Guard: if any mic is dead, skip calibration update and return GLOBAL
            if np.any(energy < 1e-6):
                return SoundClassification(is_global=True, energy_profile=energy)
            mean_energy = float(np.mean(energy))
            # Ratio of each mic's energy to the chunk average
            ratios = energy / (mean_energy + 1e-10)
            self._calibration_nmics_ratios.append(ratios)
            n = len(self._calibration_nmics_ratios)
            remaining = self._calibration_chunks - n
            logger.debug(
                f"Calibrating N-mic baseline scale: {n}/{self._calibration_chunks} "
                f"(need {remaining} more non-silent chunks)"
            )

            if n >= self._calibration_chunks:
                # Compute baseline scales as median ratios per microphone
                # Cap baseline scales between 0.2 and 5.0 to suppress outliers
                stacked = np.stack(self._calibration_nmics_ratios, axis=0)
                self._baseline_scales = np.clip(np.median(stacked, axis=0), 0.2, 5.0)
                self._calibration_done = True
                self._last_calibration_time = time.monotonic()
                logger.info(
                    f"Discriminator N-mic calibration complete ({n_mics} mics): "
                    f"baseline_scales={self._baseline_scales.tolist()} "
                    f"from {n} chunks"
                )

            # Treat as GLOBAL during calibration
            return SoundClassification(is_global=True, energy_profile=energy)

        # ── Post-calibration: normalize energies against learned scales ──────
        normalized_energy = energy / (self._baseline_scales + 1e-10)
        max_norm_energy = float(np.max(normalized_energy))

        # Normalize relative to loudest normalized mic (values 0.0 - 1.0)
        energy_norm = normalized_energy / (max_norm_energy + 1e-10)

        # Count mics that "heard" the normalized sound above global ratio threshold
        heard_count = int(np.sum(energy_norm >= self._global_ratio))
        heard_fraction = heard_count / n_mics

        if heard_fraction >= self._global_fraction:
            # Most mics heard it → GLOBAL sound
            if self._hangover_counter > 0:
                self._hangover_counter -= 1
                if self._hangover_counter == 0:
                    self._last_active_mic = None

            return SoundClassification(
                is_global=True,
                energy_profile=energy,
            )
        else:
            # Only a few mics heard it → LOCAL sound (whisper)
            candidate_mic = int(np.argmax(normalized_energy))
            if self._last_active_mic is not None and self._hangover_counter > 0:
                if candidate_mic != self._last_active_mic:
                    active_mic = self._last_active_mic
                    self._hangover_counter -= 1
                else:
                    active_mic = candidate_mic
                    self._hangover_counter = self._hangover_chunks
            else:
                active_mic = candidate_mic
                self._last_active_mic = active_mic
                self._hangover_counter = self._hangover_chunks

            active_mics = [
                i for i in range(n_mics)
                if energy_norm[i] >= self._local_ratio
            ]
            if active_mic not in active_mics:
                active_mics.append(active_mic)
            active_mics.sort()

            logger.info(
                f"LOCAL (N-mic heard by {heard_count}/{n_mics}, "
                f"max_norm={max_norm_energy:.4f}): "
                f"dominant mic={active_mic} (candidate={candidate_mic}, hangover={self._hangover_counter})"
            )
            return SoundClassification(
                is_local=True,
                active_mics=active_mics,
                energy_profile=energy,
            )

    def validate_with_cross_correlation(
        self,
        chunk: AudioChunk,
        classification: SoundClassification,
        correlation_threshold: float = 0.7,
    ) -> SoundClassification:
        """
        Secondary validation using cross-correlation.

        If a sound was classified as LOCAL but the active mic's signal
        is highly correlated with inactive mics, it's actually a global
        sound that was just quieter on some mics (e.g., soft proctor voice).

        Genuinely local sounds (whispers) will have LOW correlation with
        distant mics because the audio content is different.

        Args:
            chunk: The audio chunk to validate.
            classification: Initial classification from classify().
            correlation_threshold: Max correlation to accept as truly local.

        Returns:
            Updated SoundClassification (may flip LOCAL -> GLOBAL).
        """
        if not classification.is_local or not classification.active_mics:
            return classification

        mic_data = chunk.mic_data
        n_mics = mic_data.shape[0]
        active = set(classification.active_mics)
        inactive = [i for i in range(n_mics) if i not in active]

        if not inactive:
            return classification

        # Check if active mic signals correlate with inactive mics
        for a_idx in classification.active_mics:
            sig_a = mic_data[a_idx]
            norm_a = np.linalg.norm(sig_a)
            if norm_a < 1e-10:
                continue

            for i_idx in inactive:
                sig_i = mic_data[i_idx]
                norm_i = np.linalg.norm(sig_i)
                if norm_i < 1e-10:
                    continue

                # Optimization 1: Fast decimation pre-screening (downsample by 4)
                # If downsampled signals are completely uncorrelated, we can early-out
                sig_a_down = sig_a[::4]
                sig_i_down = sig_i[::4]
                norm_a_down = np.linalg.norm(sig_a_down)
                norm_i_down = np.linalg.norm(sig_i_down)
                if norm_a_down > 1e-10 and norm_i_down > 1e-10:
                    corr_down = np.correlate(sig_a_down, sig_i_down, "full")
                    max_corr_down = np.max(np.abs(corr_down)) / (norm_a_down * norm_i_down)
                    if max_corr_down < 0.4:
                        # Genuinely local sound, correlation is too low to ever exceed threshold
                        continue

                # Optimization 2: FFT-based cross-correlation for high-res check
                try:
                    from scipy.signal import correlate as scipy_correlate
                    corr = scipy_correlate(sig_a, sig_i, mode="full", method="fft")
                except ImportError:
                    corr = np.correlate(sig_a, sig_i, "full")

                max_corr = np.max(np.abs(corr)) / (norm_a * norm_i)

                if max_corr > correlation_threshold:
                    # High correlation = same sound content, just quieter
                    # -> reclassify as GLOBAL
                    logger.debug(
                        f"Cross-correlation check: mic {a_idx}<->{i_idx} = "
                        f"{max_corr:.3f} > {correlation_threshold} -> "
                        f"reclassifying as GLOBAL"
                    )
                    return SoundClassification(
                        is_global=True,
                        energy_profile=classification.energy_profile,
                    )

        # Low correlation confirmed -> genuinely LOCAL
        return classification
