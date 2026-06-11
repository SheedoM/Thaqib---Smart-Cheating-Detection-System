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
        3. Compute the NORMALIZED ratio = raw_ratio / baseline_ratio
        4. If normalized ratio >= local_ratio_multiplier → LOCAL
           This removes the structural imbalance between mic positions

    Algorithm (N-mic mode):
        Same as before — normalize fraction of mics that heard the sound.

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

        # Calibration state — populated during the first N non-silent chunks
        self._calibration_ratios: list[float] = []
        self._baseline_ratio: float | None = None  # None = still calibrating
        self._calibration_done: bool = (calibration_chunks == 0)
        self._last_calibration_time: float = time.monotonic()

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
        self._calibration_done = (self._calibration_chunks == 0)
        self._last_calibration_time = time.monotonic()
        logger.info("Discriminator calibration reset")

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
        2-microphone classification with dynamic baseline calibration.

        During the first `calibration_chunks` non-silent chunks the
        discriminator learns the structural energy imbalance between
        the two mic positions.  After calibration every new chunk is
        judged relative to that baseline — not against a fixed 2.0 ratio.

        Periodic recalibration resets the baseline every
        `recalibration_interval_sec` seconds to adapt to changing
        room acoustics (people moving, doors opening, etc.).
        """
        e0, e1 = float(energy[0]), float(energy[1])
        raw_ratio = max(e0, e1) / (min(e0, e1) + 1e-10)

        # ── Periodic recalibration check ──────────────────────────────
        # After the initial baseline is learned, trigger a fresh
        # recalibration every recalibration_interval_sec seconds.
        if (
            self._calibration_done
            and self._recalibration_interval > 0
            and (time.monotonic() - self._last_calibration_time)
                >= self._recalibration_interval
        ):
            elapsed_min = (time.monotonic() - self._last_calibration_time) / 60
            logger.info(
                f"Periodic recalibration triggered after {elapsed_min:.1f}min "
                f"(old baseline={self._baseline_ratio:.3f}x) — re-learning..."
            )
            self.reset_calibration()

        # ── Calibration phase ─────────────────────────────────────────
        if not self._calibration_done:
            self._calibration_ratios.append(raw_ratio)
            n = len(self._calibration_ratios)
            remaining = self._calibration_chunks - n
            logger.debug(
                f"Calibrating baseline ratio: {n}/{self._calibration_chunks} "
                f"current={raw_ratio:.2f} (need {remaining} more non-silent chunks)"
            )

            if n >= self._calibration_chunks:
                # Compute baseline as the median (robust to outlier whispers
                # that might have slipped in during calibration window).
                # Cap at 3.5x to exclude extreme outliers (real cheating during calibration).
                capped = [r for r in self._calibration_ratios if r <= 3.5]
                source = capped if len(capped) >= n // 2 else self._calibration_ratios
                self._baseline_ratio = float(np.median(source))
                self._calibration_done = True
                # reset timer NOW (not at __init__ time) so the
                # 5-minute recalibration interval starts from here.
                self._last_calibration_time = time.monotonic()
                logger.info(
                    f"Discriminator calibration complete: "
                    f"baseline_ratio={self._baseline_ratio:.3f}x "
                    f"(from {n} chunks, {len(self._calibration_ratios)-len(capped)} outliers excluded).  "
                    f"LOCAL threshold = baseline × {self._local_ratio_multiplier} "
                    f"= {self._baseline_ratio * self._local_ratio_multiplier:.3f}x"
                )

            # During calibration treat everything as GLOBAL to avoid
            # false alerts while the baseline is still being established
            return SoundClassification(is_global=True, energy_profile=energy)

        # ── Post-calibration: normalize against learned baseline ──────
        # normalized_ratio = how many times WORSE the imbalance is
        # compared to the normal structural difference
        normalized_ratio = raw_ratio / self._baseline_ratio

        if normalized_ratio >= self._local_ratio_multiplier:
            active_mic = int(np.argmax(energy))
            logger.info(
                f"LOCAL (2-mic raw={raw_ratio:.2f}x, "
                f"baseline={self._baseline_ratio:.2f}x, "
                f"normalized={normalized_ratio:.2f}x >= "
                f"{self._local_ratio_multiplier:.1f}x): "
                f"dominant mic={active_mic}"
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
            return SoundClassification(
                is_global=True,
                energy_profile=energy,
                raw_ratio=float(raw_ratio),
                normalized_ratio=float(normalized_ratio),
                baseline_ratio=float(self._baseline_ratio),
            )

    def _classify_nmics(self, energy: np.ndarray) -> SoundClassification:
        """N-microphone classification (unchanged from original)."""
        n_mics = len(energy)
        max_energy = float(np.max(energy))

        # Normalize energy relative to loudest mic
        energy_norm = energy / max_energy  # values 0.0–1.0

        # Count mics that "heard" the sound
        heard_count = int(np.sum(energy_norm >= self._global_ratio))
        heard_fraction = heard_count / n_mics

        if heard_fraction >= self._global_fraction:
            # Most mics heard it → GLOBAL sound (proctor, door, etc.)
            return SoundClassification(
                is_global=True,
                energy_profile=energy,
            )
        else:
            # Only a few mics heard it → LOCAL sound (possible whisper)
            active_mics = [
                i for i in range(n_mics)
                if energy_norm[i] >= self._local_ratio
            ]
            logger.info(
                f"LOCAL sound detected on mics {active_mics} "
                f"(heard by {heard_count}/{n_mics}, "
                f"max_energy={max_energy:.4f})"
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

                # Normalized cross-correlation (peak value)
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
