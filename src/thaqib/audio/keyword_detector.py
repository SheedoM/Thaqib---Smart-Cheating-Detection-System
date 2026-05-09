"""
Keyword detection pipeline: VAD → Whisper STT → Keyword matching.

Processes audio confirmed as LOCAL speech and determines whether
it contains cheating-related keywords.
"""

import json
import logging
from pathlib import Path

import numpy as np

from thaqib.audio.models import KeywordResult

logger = logging.getLogger(__name__)


class KeywordDetector:
    """
    Two-stage speech analysis for cheating keyword detection.

    Stage 1 — Voice Activity Detection (Silero VAD):
        Confirms the local sound is human speech, not mechanical noise.

    Stage 2 — Speech-to-Text + Keyword Matching (OpenAI Whisper):
        Transcribes the speech and checks against a configurable
        keyword list loaded from an external JSON file.

    Example:
        >>> detector = KeywordDetector(model_size="tiny", language="ar")
        >>> result = detector.analyze(audio_samples, sample_rate=16000)
        >>> if result and result.is_cheating:
        ...     print(f"Cheating keywords: {result.matched_keywords}")
    """

    def __init__(
        self,
        model_size: str = "tiny",
        language: str = "ar",
        keywords_file: str = "keywords.json",
        vad_threshold: float = 0.5,
    ):
        """
        Args:
            model_size: Whisper model size ('tiny', 'base', 'small', 'medium').
                        'tiny' = fastest (~1s/chunk on CPU), least accurate.
                        'small' = good balance for Arabic.
            language: Expected language code for Whisper.
            keywords_file: Path to JSON file containing cheating keywords.
            vad_threshold: Voice activity detection confidence threshold.
        """
        self._model_size = model_size
        self._language = language
        self._keywords_file = keywords_file
        self._vad_threshold = vad_threshold

        # Lazy-loaded models (heavy — loaded on first use)
        self._whisper_model = None
        self._vad_model = None
        self._vad_utils = None
        self._keywords: list[str] = []
        self._fuzzy_threshold: float = 0.8

        self._load_keywords()

    def _load_keywords(self) -> None:
        """Load cheating keywords from external JSON file."""
        path = Path(self._keywords_file)
        if not path.exists():
            logger.warning(
                f"Keywords file not found: {path}. "
                f"Using empty keyword list."
            )
            self._keywords = []
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._keywords = data.get("keywords", [])
            self._fuzzy_threshold = data.get("fuzzy_threshold", 0.8)

            if data.get("language"):
                self._language = data["language"]

            logger.info(
                f"Loaded {len(self._keywords)} keywords from {path} "
                f"(language={self._language})"
            )
        except Exception as e:
            logger.error(f"Failed to load keywords from {path}: {e}")
            self._keywords = []

    def _ensure_vad_loaded(self) -> None:
        """Lazy-load Silero VAD model."""
        if self._vad_model is not None:
            return

        try:
            import torch

            model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                trust_repo=True,
            )
            self._vad_model = model
            self._vad_utils = utils
            logger.info("Silero VAD model loaded")
        except Exception as e:
            logger.warning(f"Failed to load Silero VAD: {e}. Skipping VAD.")
            self._vad_model = None

    def _ensure_whisper_loaded(self) -> None:
        """Lazy-load Whisper model."""
        if self._whisper_model is not None:
            return

        try:
            import whisper

            logger.info(f"Loading Whisper model '{self._model_size}'...")
            self._whisper_model = whisper.load_model(self._model_size)
            logger.info(f"Whisper model '{self._model_size}' loaded")
        except ImportError:
            raise ImportError(
                "openai-whisper is required for speech recognition. "
                "Install with: pip install openai-whisper"
            )

    def is_speech(self, audio: np.ndarray, sample_rate: int) -> tuple[bool, float]:
        """
        Check if audio contains speech using Silero VAD.

        Args:
            audio: Audio samples (1D float32 array).
            sample_rate: Sample rate of the audio.

        Returns:
            (is_speech, confidence) tuple.
        """
        self._ensure_vad_loaded()

        if self._vad_model is None:
            # VAD unavailable — assume speech to avoid missing cheating
            return True, 1.0

        try:
            import torch

            # Silero VAD expects 16kHz mono
            if sample_rate != 16000:
                # Simple resampling via linear interpolation
                ratio = 16000 / sample_rate
                new_len = int(len(audio) * ratio)
                audio = np.interp(
                    np.linspace(0, len(audio) - 1, new_len),
                    np.arange(len(audio)),
                    audio,
                ).astype(np.float32)

            tensor = torch.from_numpy(audio)
            
            # Silero VAD expects exactly 512 samples per call at 16000Hz
            window_size = 512
            max_confidence = 0.0
            
            # Process in 512-sample chunks
            for i in range(0, len(tensor) - window_size + 1, window_size):
                chunk = tensor[i:i+window_size]
                # VAD requires batch dimension or 1D tensor, we pass 1D tensor chunk
                confidence = self._vad_model(chunk, 16000).item()
                if confidence > max_confidence:
                    max_confidence = confidence
                    
            is_speech = max_confidence >= self._vad_threshold
            return is_speech, max_confidence

        except Exception as e:
            logger.warning(f"VAD error: {e}. Assuming speech.")
            return True, 1.0

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> dict:
        """
        Transcribe audio using Whisper.

        Args:
            audio: Audio samples (1D float32 array).
            sample_rate: Sample rate of the audio.

        Returns:
            Whisper result dict with 'text', 'segments', 'language'.
        """
        self._ensure_whisper_loaded()

        # Whisper expects float32, 16kHz
        if sample_rate != 16000:
            ratio = 16000 / sample_rate
            new_len = int(len(audio) * ratio)
            audio = np.interp(
                np.linspace(0, len(audio) - 1, new_len),
                np.arange(len(audio)),
                audio,
            ).astype(np.float32)

        result = self._whisper_model.transcribe(
            audio,
            language=self._language,
            fp16=False,  # CPU-safe
        )
        return result

    def match_keywords(self, transcript: str) -> list[str]:
        """
        Match transcript against the cheating keyword list.

        Uses both exact substring matching and basic fuzzy matching.

        Args:
            transcript: Text to search for keywords.

        Returns:
            List of matched keywords.
        """
        if not transcript or not self._keywords:
            return []

        transcript_lower = transcript.lower().strip()
        matches = []

        for keyword in self._keywords:
            keyword_lower = keyword.lower().strip()

            # Exact substring match
            if keyword_lower in transcript_lower:
                matches.append(keyword)
                continue

            # Basic fuzzy match: check if most words of the keyword appear
            kw_words = keyword_lower.split()
            if len(kw_words) > 1:
                found_words = sum(
                    1 for w in kw_words if w in transcript_lower
                )
                if found_words / len(kw_words) >= self._fuzzy_threshold:
                    matches.append(keyword)

        return matches

    def analyze(self, audio: np.ndarray, sample_rate: int) -> KeywordResult | None:
        """
        Full analysis pipeline: VAD → Whisper → Keyword matching.

        Args:
            audio: Audio samples from a single microphone (1D float32).
            sample_rate: Sample rate of the audio.

        Returns:
            KeywordResult if speech was detected, None if not speech.
        """
        # Stage 1: Voice Activity Detection
        speech_detected, vad_confidence = self.is_speech(audio, sample_rate)

        if not speech_detected:
            logger.debug(f"VAD: not speech (confidence={vad_confidence:.3f})")
            return None

        logger.info(f"VAD: speech detected (confidence={vad_confidence:.3f})")

        # Stage 2: Transcribe with Whisper
        try:
            result = self.transcribe(audio, sample_rate)
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            return KeywordResult()

        transcript = result.get("text", "").strip()
        if not transcript:
            return KeywordResult()

        # Compute average confidence from segments
        segments = result.get("segments", [])
        avg_confidence = 0.0
        if segments:
            avg_confidence = sum(
                s.get("avg_logprob", 0) for s in segments
            ) / len(segments)

        detected_language = result.get("language", self._language)

        logger.info(f"Whisper transcript: '{transcript}' (lang={detected_language})")

        # Stage 3: Keyword matching
        matched = self.match_keywords(transcript)

        if matched:
            logger.warning(f"CHEATING KEYWORDS DETECTED: {matched}")

        return KeywordResult(
            transcript=transcript,
            matched_keywords=matched,
            is_cheating=len(matched) > 0,
            confidence=avg_confidence,
            language=detected_language,
        )
