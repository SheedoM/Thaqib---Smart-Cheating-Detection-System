"""
Data models for the audio cheating detection subsystem.
"""

from dataclasses import dataclass, field
import numpy as np


@dataclass
class AudioChunk:
    """Synchronized audio from all microphones for one analysis window.

    Attributes:
        timestamp: Wall-clock time when this chunk was captured (seconds since epoch).
        mic_data: Raw audio samples, shape (n_mics, n_samples).
        sample_rate: Samples per second (e.g. 16000).
        duration_ms: Window length in milliseconds (e.g. 500).
        chunk_index: Sequential chunk counter (0, 1, 2, ...).
    """

    timestamp: float
    mic_data: np.ndarray
    sample_rate: int
    duration_ms: int
    chunk_index: int = 0


@dataclass
class SoundClassification:
    """Result of global vs. local sound discrimination.

    Attributes:
        is_silent: True if all mics are below the silence threshold.
        is_global: True if the majority of mics heard the sound (not cheating).
        is_local: True if only a few mics heard the sound (possible cheating).
        active_mics: Indices of mics that picked up the sound above threshold.
        energy_profile: RMS energy per mic (for debugging/dashboard display).
    """

    is_silent: bool = False
    is_global: bool = False
    is_local: bool = False
    active_mics: list[int] = field(default_factory=list)
    energy_profile: np.ndarray = field(default_factory=lambda: np.array([]))


@dataclass
class KeywordResult:
    """Result of speech-to-text and keyword matching.

    Attributes:
        transcript: Full transcription text from Whisper.
        matched_keywords: Cheating keywords found in the transcript.
        is_cheating: True if any cheating keywords matched.
        confidence: Whisper's average log probability (higher = more confident).
        language: Detected language code.
    """

    transcript: str = ""
    matched_keywords: list[str] = field(default_factory=list)
    is_cheating: bool = False
    confidence: float = 0.0
    language: str = ""


@dataclass
class AudioAlert:
    """A confirmed audio cheating event.

    Generated when local sound is classified as speech containing
    cheating keywords. Serves as the output of the audio pipeline
    and input to the evidence recorder / video integration.

    Attributes:
        timestamp: When the cheating was detected (seconds since epoch).
        mic_id: Primary microphone that detected the sound.
        active_mics: All mics that picked up the local sound.
        transcript: What was said (from Whisper).
        matched_keywords: Which cheating keywords were found.
        audio_clip: Raw audio data for evidence recording.
        sample_rate: Sample rate of the audio clip.
        confidence: Whisper confidence score.
        chunk_index: Which processing chunk triggered this alert.
    """

    timestamp: float
    mic_id: int
    active_mics: list[int]
    transcript: str
    matched_keywords: list[str]
    audio_clip: np.ndarray
    sample_rate: int
    confidence: float
    chunk_index: int = 0
