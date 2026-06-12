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
        raw_ratio: Raw energy ratio between loudest and quietest mic (2-mic mode).
        normalized_ratio: Ratio calculated by normalizing Mic0 by baseline_ratio and comparing to Mic1 symmetrically.
        baseline_ratio: Learned structural imbalance at time of classification.
    """

    is_silent: bool = False
    is_global: bool = False
    is_local: bool = False
    active_mics: list[int] = field(default_factory=list)
    energy_profile: np.ndarray = field(default_factory=lambda: np.array([]))
    # Discriminator forensic fields for evidence JSON
    raw_ratio: float = 1.0
    normalized_ratio: float = 1.0
    baseline_ratio: float = 1.0


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
        recording_start: Pipeline start time (for offset calculation).
        discriminator_baseline: Learned energy baseline at time of alert.
        discriminator_raw_ratio: Raw mic energy ratio at time of alert.
        discriminator_normalized_ratio: Normalized ratio (triggered threshold).
    """

    timestamp: float
    mic_id: int
    active_mics: list[int]
    transcript: str
    matched_keywords: list[str]
    timestamp_start: float
    timestamp_end: float
    audio_clip: np.ndarray
    sample_rate: int
    confidence: float
    chunk_index: int = 0
    recording_start: float = 0.0
    # Discriminator forensic metadata
    discriminator_baseline: float = 0.0
    discriminator_raw_ratio: float = 0.0
    discriminator_normalized_ratio: float = 0.0


@dataclass
class CheatEpisode:
    """A sustained cheating event tracked from first to last detection.

    Unlike AudioAlert (which captures a single keyword-match moment),
    CheatEpisode accumulates ALL audio, transcripts, and keywords across
    the entire period of continuous cheating activity on one mic.

    The episode is "confirmed" once cheating has been sustained for
    audio_episode_min_sec seconds.  It is "closed" when no new cheating
    is detected for audio_episode_grace_sec seconds after the last alert.
    Closing triggers a full-episode WAV + JSON save.

    Attributes:
        mic_id:         Primary microphone where cheating was detected.
        start_time:     Timestamp of the first alert in this episode.
        last_alert_time: Timestamp of the most recent alert.
        confirmed:      True once sustained >= episode_min_sec.
        alert_count:    How many individual alerts make up this episode.
        all_transcripts: Every Whisper transcript during the episode.
        all_keywords:   Deduplicated list of all matched keywords.
        audio_chunks:   Raw audio chunks (from first to last) — built by pipeline.
        sample_rate:    Sample rate of audio_chunks.
    """

    mic_id: int
    start_time: float
    last_alert_time: float
    confirmed: bool = False
    alert_count: int = 0
    all_transcripts: list[str] = field(default_factory=list)
    all_keywords: list[str] = field(default_factory=list)
    audio_chunks: list[np.ndarray] = field(default_factory=list)
    sample_rate: int = 16000

    @property
    def duration_sec(self) -> float:
        """Total episode duration in seconds."""
        return self.last_alert_time - self.start_time

    @property
    def audio_duration_sec(self) -> float:
        """Duration of accumulated audio in seconds."""
        if not self.audio_chunks:
            return 0.0
        return sum(len(c) for c in self.audio_chunks) / self.sample_rate

    def on_alert(self, alert: "AudioAlert") -> None:
        """Integrate a new AudioAlert into this episode."""
        self.last_alert_time = alert.timestamp
        self.alert_count += 1
        if alert.transcript:
            self.all_transcripts.append(alert.transcript)
        for kw in alert.matched_keywords:
            if kw not in self.all_keywords:
                self.all_keywords.append(kw)

    def get_full_audio(self) -> "np.ndarray":
        """Concatenate all accumulated audio chunks."""
        if not self.audio_chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(self.audio_chunks).astype(np.float32)
