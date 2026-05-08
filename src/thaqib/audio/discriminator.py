"""
Global vs. Local sound discriminator.

Analyzes multi-microphone audio to determine whether a sound
is heard by all microphones (global — not cheating) or only
by a few nearby microphones (local — possible cheating).
"""

import logging

import numpy as np

from thaqib.audio.models import AudioChunk, SoundClassification

logger = logging.getLogger(__name__)


class GlobalLocalDiscriminator:
    """
    Classifies each audio chunk as SILENT, GLOBAL, or LOCAL
    based on energy distribution across microphones.

    Algorithm:
        1. Compute RMS energy per mic
        2. Normalize relative to the loudest mic
        3. Count how many mics "heard" the sound (energy above threshold)
        4. If most mics heard it → GLOBAL (not cheating)
        5. If few mics heard it → LOCAL (possible cheating)

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
    ):
        """
        Args:
            silence_threshold: RMS energy below this = silence (ignored).
            global_ratio: A mic "heard" the sound if its normalized
                          energy is >= this fraction of the loudest mic.
            global_fraction: If this fraction of mics heard it, classify
                             as GLOBAL (e.g., 0.6 = 60% of mics).
            local_ratio: Minimum normalized energy for a mic to count as
                         "active" in a LOCAL classification.
        """
        self._silence_threshold = silence_threshold
        self._global_ratio = global_ratio
        self._global_fraction = global_fraction
        self._local_ratio = local_ratio

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

        # Step 3: Normalize energy relative to loudest mic
        energy_norm = energy / max_energy  # shape: (n_mics,), values 0.0–1.0

        # Step 4: Count mics that "heard" the sound
        heard_count = np.sum(energy_norm >= self._global_ratio)
        heard_fraction = heard_count / n_mics

        # Step 5: Classify
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
                f"(heard by {int(heard_count)}/{n_mics}, "
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
            Updated SoundClassification (may flip LOCAL → GLOBAL).
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
                    # → reclassify as GLOBAL
                    logger.debug(
                        f"Cross-correlation check: mic {a_idx}↔{i_idx} = "
                        f"{max_corr:.3f} > {correlation_threshold} → "
                        f"reclassifying as GLOBAL"
                    )
                    return SoundClassification(
                        is_global=True,
                        energy_profile=classification.energy_profile,
                    )

        # Low correlation confirmed → genuinely LOCAL
        return classification
