"""
Audio cheating detection subsystem.

Provides real-time multi-microphone audio processing to detect
whispered conversations during exams.
"""

from thaqib.audio.models import AudioChunk, SoundClassification, AudioAlert
from thaqib.audio.pipeline import AudioPipeline
from thaqib.audio.source import StreamAudioSource

__all__ = [
    "AudioChunk",
    "SoundClassification",
    "AudioAlert",
    "AudioPipeline",
    "StreamAudioSource",
]
