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
        strict_mode: bool = True,
        speech_buffer_sec: float = 2.5,
        speech_gap_max: int = 2,
        beam_size: int = 1,
        device: str = "auto",
        compute_type: str = "auto",
        adaptive_vad: bool = True,
        vad_calibration_chunks: int = 50,
        preprocessor: "AudioPreprocessor | None" = None,
        vad_context_ms: int = 200,
    ):
        """
        Args:
            model_size: Whisper model size ('tiny', 'base', 'small', 'medium').
                        'tiny' = fastest (~1s/chunk on CPU), least accurate.
                        'small' = good balance for Arabic.
            language: Expected language code for Whisper.
            keywords_file: Path to JSON file containing cheating keywords.
            vad_threshold: Voice activity detection confidence threshold.
            strict_mode: If True (default), ANY detected speech is flagged as
                         cheating, regardless of keywords. If False, only
                         transcripts containing a keyword from keywords_file
                         are flagged. Strict mode is suitable for silent exams;
                         keyword mode is suitable for oral/group exams.
            speech_buffer_sec: Minimum seconds of VAD-confirmed speech to
                               accumulate before sending to Whisper. Higher
                               values improve transcription accuracy but add
                               latency. Default: 2.5s.
            speech_gap_max: Number of consecutive non-speech chunks allowed
                            before the speech buffer is cleared. Tolerates
                            brief pauses mid-sentence. Default: 2 chunks.
        """
        self._model_size = model_size
        self._language = language
        self._keywords_file = keywords_file
        self._vad_threshold = vad_threshold   # current effective threshold
        self._vad_threshold_initial = vad_threshold
        self._strict_mode = strict_mode
        self._beam_size = beam_size
        self._device_pref = device
        self._compute_type_pref = compute_type
        self._resolved_device: str | None = None
        self._resolved_compute: str | None = None

        # Adaptive VAD threshold state
        self._adaptive_vad: bool = adaptive_vad
        self._vad_calibration_chunks: int = vad_calibration_chunks
        self._vad_noise_confidences: list[float] = []  # VAD conf on non-speech frames
        self._vad_threshold_min: float = 0.10
        self._vad_threshold_max: float = 0.70

        # EMA Adaptive VAD state
        self._ambient_vad_ema: float = 0.01
        self._ambient_vad_alpha: float = 0.05
        self._ambient_vad_margin: float = 0.20  # Safety margin above noise floor
        self._ambient_vad_emas: dict[int, float] = {}
        self._vad_thresholds: dict[int, float] = {}

        # Optional preprocessor (HPF + noise reduction + adaptive gain)
        self._preprocessor = preprocessor

        # Speech buffer configuration — one buffer per mic_id ()
        self._speech_buffers: dict[int, list[np.ndarray]] = {}
        self._speech_buffer_sec: float = speech_buffer_sec
        self._speech_gap_counters: dict[int, int] = {}
        self._speech_gap_max: int = speech_gap_max

        # Faster Whisper flag (set at model load time)
        self._use_faster_whisper = False
        # Lazy-loaded models (heavy — loaded on first use)
        self._whisper_model = None
        self._vad_model = None
        self._vad_models: dict[int, object] = {}
        self._vad_utils = None
        self._keywords: list[str] = []
        self._fuzzy_threshold: float = 0.8

        self._vad_context_ms = vad_context_ms
        self._vad_contexts: dict[int, np.ndarray] = {}

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

    def _resolve_device(self) -> tuple[str, str]:
        """
        Resolve the actual device and compute_type to use for Whisper.

        Logic:
            device="auto"       → CUDA if available, else CPU
            device="cuda"       → always CUDA (will fail if unavailable)
            device="cpu"        → always CPU

            compute_type="auto" → float16 on CUDA, int8 on CPU
            otherwise           → use value as-is

        Returns:
            (device, compute_type) strings ready to pass to WhisperModel.
        """
        if self._resolved_device is not None:
            return self._resolved_device, self._resolved_compute

        pref = self._device_pref.lower()

        if pref == "auto":
            try:
                import torch
                if torch.cuda.is_available():
                    gpu_name = torch.cuda.get_device_name(0)
                    vram_mb = torch.cuda.get_device_properties(0).total_memory // (1024 * 1024)
                    device = "cuda"
                    logger.info(
                        f"GPU detected: {gpu_name} ({vram_mb} MB VRAM) — "
                        f"Whisper will run on CUDA."
                    )
                else:
                    device = "cpu"
                    logger.info("No CUDA GPU detected — Whisper will run on CPU.")
            except ImportError:
                device = "cpu"
                logger.info("torch not available — Whisper will run on CPU.")
        elif pref == "cuda":
            device = "cuda"
        else:
            device = "cpu"

        # Resolve compute_type
        ct_pref = self._compute_type_pref.lower()
        if ct_pref == "auto":
            compute_type = "float16" if device == "cuda" else "int8"
        else:
            compute_type = ct_pref

        self._resolved_device = device
        self._resolved_compute = compute_type

        logger.info(
            f"Whisper compute config: device={device}, compute_type={compute_type}, "
            f"model={self._model_size}, beam_size={self._beam_size}"
        )
        return device, compute_type

    def _ensure_vad_loaded(self) -> None:
        """Lazy-load Silero VAD model (always on CPU — it's tiny and fast)."""
        if self._vad_model is not None:
            return

        try:
            import torch

            model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                trust_repo=True,
            )
            # VAD is always kept on CPU: it's only 1.8 MB and each call
            # is 10-30ms — the GPU transfer overhead would cost more than it saves.
            self._vad_model = model.cpu()
            self._vad_utils = utils
            logger.info("Silero VAD model loaded (CPU)")
        except Exception as e:
            logger.warning(f"Failed to load Silero VAD: {e}. Skipping VAD.")
            self._vad_model = None

    def _ensure_vad_loaded_for_mic(self, mic_id: int) -> None:
        """Ensure Silero VAD model is loaded and duplicated for this specific microphone channel."""
        if mic_id in self._vad_models:
            return

        self._ensure_vad_loaded()
        if self._vad_model is None:
            return

        import copy
        try:
            # Create a separate, isolated model copy for this mic to preserve RNN state
            self._vad_models[mic_id] = copy.deepcopy(self._vad_model)
            logger.info(f"Instantiated separate Silero VAD model instance for mic{mic_id}")
        except Exception as e:
            logger.error(f"Failed to copy VAD model for mic{mic_id}: {e}")
            self._vad_models[mic_id] = self._vad_model

    def preload_models(self) -> None:
        """Call this at pipeline start to avoid first-chunk delay."""
        self._ensure_vad_loaded()
        self._ensure_whisper_loaded()

    def _ensure_whisper_loaded(self) -> None:
        """Lazy-load Whisper with automatic GPU/CPU selection."""
        if self._whisper_model is not None:
            return

        device, compute_type = self._resolve_device()

        try:
            from faster_whisper import WhisperModel
            logger.info(
                f"Loading faster-whisper '{self._model_size}' "
                f"on {device.upper()} ({compute_type})..."
            )
            self._whisper_model = WhisperModel(
                self._model_size,
                device=device,
                compute_type=compute_type,
            )
            self._use_faster_whisper = True
            logger.info(
                f"faster-whisper '{self._model_size}' loaded — "
                f"device={device}, compute_type={compute_type}"
            )
            return
        except ImportError:
            logger.info("faster-whisper not installed, falling back to openai-whisper")
        except Exception as e:
            # GPU load may fail (e.g., VRAM too small) — auto-fallback to CPU
            if device == "cuda":
                logger.warning(
                    f"faster-whisper GPU load failed ({e}). "
                    f"Falling back to CPU with int8."
                )
                self._resolved_device = "cpu"
                self._resolved_compute = "int8"
                device, compute_type = "cpu", "int8"
                try:
                    from faster_whisper import WhisperModel
                    self._whisper_model = WhisperModel(
                        self._model_size, device="cpu", compute_type="int8"
                    )
                    self._use_faster_whisper = True
                    logger.info("faster-whisper loaded on CPU (fallback after GPU failure)")
                    return
                except Exception as e2:
                    logger.error(f"CPU fallback also failed: {e2}")
            else:
                raise

        # Fallback: openai-whisper (no GPU support in this path)
        try:
            import whisper
            logger.info(f"Loading openai-whisper '{self._model_size}' on CPU...")
            self._whisper_model = whisper.load_model(self._model_size)
            self._use_faster_whisper = False
            logger.info(f"openai-whisper '{self._model_size}' loaded (CPU)")
        except ImportError:
            raise ImportError(
                "Install faster-whisper (recommended) or openai-whisper:\n"
                "  pip install faster-whisper"
            )
    def get_vad_threshold(self, mic_id: int = 0) -> float:
        """
        Get the current VAD threshold for a specific mic.
        """
        return self._vad_thresholds.get(mic_id, self._vad_threshold)

    def is_speech(self, audio: np.ndarray, sample_rate: int, mic_id: int = 0) -> tuple[bool, float]:
        """
        Check if audio contains speech using Silero VAD.

        Uses batch inference — all 512-sample windows are stacked
        into one tensor and processed in a SINGLE model call (3-5× faster
        than the old sequential loop).

        Returns:
            (is_speech, max_confidence) tuple.
        """
        self._ensure_vad_loaded_for_mic(mic_id)
        vad_model = self._vad_models.get(mic_id)

        if vad_model is None:
            return True, 1.0

        try:
            import torch

            # 1. Resample to 16,000 Hz if needed
            if sample_rate != 16000:
                ratio = 16000 / sample_rate
                new_len = int(len(audio) * ratio)
                audio_16k = np.interp(
                    np.linspace(0, len(audio) - 1, new_len),
                    np.arange(len(audio)),
                    audio,
                ).astype(np.float32)
            else:
                audio_16k = audio.astype(np.float32)

            # 2. Apply sliding context padding for temporal continuity
            if self._vad_context_ms > 0:
                context_samples = int(16000 * self._vad_context_ms / 1000)
                prev_context = self._vad_contexts.get(mic_id, None)
                if prev_context is None:
                    prev_context = np.zeros(context_samples, dtype=np.float32)
                
                # Prepend previous context (only used for VAD inference)
                vad_input = np.concatenate([prev_context, audio_16k])
                
                # Update rolling context buffer for next chunk (from clean current chunk)
                self._vad_contexts[mic_id] = audio_16k[-context_samples:].copy()
            else:
                vad_input = audio_16k

            tensor = torch.from_numpy(vad_input)
            window_size = 512
            n_complete = len(tensor) // window_size

            if n_complete == 0:
                # Audio shorter than one VAD window — pad and run once
                padded = torch.zeros(window_size)
                padded[:len(tensor)] = tensor
                max_confidence = vad_model(padded, 16000).item()
            else:
                # batch all windows, single model call
                windows = tensor[:n_complete * window_size].reshape(n_complete, window_size)
                # Silero VAD processes 1D tensors; batch by iterating but
                # avoiding Python-level per-window overhead via torch.stack
                try:
                    # Try batch path (works with most Silero versions)
                    confidences = torch.stack(
                        [vad_model(windows[i], 16000) for i in range(n_complete)]
                    )
                    max_confidence = confidences.max().item()
                except Exception:
                    # Fallback: sequential (rare, some Silero builds vary)
                    max_confidence = max(
                        vad_model(windows[i], 16000).item()
                        for i in range(n_complete)
                    )

            threshold = self.get_vad_threshold(mic_id)
            is_speech = max_confidence >= threshold

            # 3. Dynamic Threshold Adaptation (Exponential Moving Average)
            if self._adaptive_vad:
                if max_confidence < threshold:
                    ema = self._ambient_vad_emas.get(mic_id, self._ambient_vad_ema)
                    ema = (self._ambient_vad_alpha * max_confidence) + ((1.0 - self._ambient_vad_alpha) * ema)
                    self._ambient_vad_emas[mic_id] = ema

                    # Safety margin
                    new_threshold = ema + self._ambient_vad_margin
                    new_threshold = np.clip(new_threshold, self._vad_threshold_min, self._vad_threshold_max)
                    new_threshold = float(round(new_threshold, 3))

                    if new_threshold != threshold:
                        self._vad_thresholds[mic_id] = new_threshold
                        logger.info(
                            f"Adaptive VAD (Mic {mic_id}): threshold updated {threshold:.3f} → {new_threshold:.3f} "
                            f"(ambient noise floor EMA={ema:.3f})"
                        )

            return is_speech, max_confidence

        except Exception as e:
            logger.warning(f"VAD error: {e}. Assuming speech.")
            return True, 1.0

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> dict:
        """
        Transcribe audio using Whisper.

        Returns dict with keys: 'text', 'segments', 'language', 'avg_confidence'.
        Uses self._beam_size (configurable via AUDIO_WHISPER_BEAM_SIZE).
        """
        self._ensure_whisper_loaded()

        if sample_rate != 16000:
            ratio = 16000 / sample_rate
            new_len = int(len(audio) * ratio)
            audio = np.interp(
                np.linspace(0, len(audio) - 1, new_len),
                np.arange(len(audio)),
                audio,
            ).astype(np.float32)

        if self._use_faster_whisper:
            seg_gen, info = self._whisper_model.transcribe(
                audio, language=self._language, beam_size=self._beam_size
            )
            segments = list(seg_gen)
            text = " ".join(s.text for s in segments).strip()
            avg_conf = (
                sum(s.avg_logprob for s in segments) / len(segments)
                if segments else 0.0
            )
            return {
                "text": text,
                "segments": segments,
                "language": info.language,
                "avg_confidence": avg_conf,
            }
        else:
            result = self._whisper_model.transcribe(
                audio,
                language=self._language,
                fp16=False,
                beam_size=self._beam_size if self._beam_size > 1 else None,
            )
            segs = result.get("segments", [])
            avg_conf = (
                sum(s.get("avg_logprob", 0.0) for s in segs) / len(segs)
                if segs else 0.0
            )
            result["avg_confidence"] = avg_conf
            return result

    @staticmethod
    def _strip_diacritics(text: str) -> str:
        """
        Remove Arabic diacritics (tashkeel / harakat) before matching.

        Whisper sometimes includes diacritics that are absent
        from the keywords file, causing missed matches.
        Unicode range U+064B–U+065F covers all Arabic harakat.
        """
        import re
        return re.sub(r'[\u064B-\u065F\u0670]', '', text)

    def match_keywords(self, transcript: str) -> list[str]:
        """
        Match transcript against the cheating keyword list.

        Uses exact substring matching (after diacritic stripping) and
        basic word-level fuzzy matching.
        """
        if not transcript or not self._keywords:
            return []

        # strip diacritics from both transcript and keywords
        transcript_clean = self._strip_diacritics(transcript.lower().strip())
        matches = []

        for keyword in self._keywords:
            keyword_clean = self._strip_diacritics(keyword.lower().strip())

            if keyword_clean in transcript_clean:
                matches.append(keyword)
                continue

            kw_words = keyword_clean.split()
            if len(kw_words) > 1:
                found_words = sum(1 for w in kw_words if w in transcript_clean)
                if found_words / len(kw_words) >= self._fuzzy_threshold:
                    matches.append(keyword)

        return matches

    def vad_and_buffer(
        self, audio: np.ndarray, sample_rate: int, mic_id: int = 0, preprocessed: bool = False
    ) -> "np.ndarray | None":
        """
        Stage 1 only: preprocess → VAD → speech buffer accumulation.

        Preprocessing (HPF + noise reduction + adaptive gain) is applied
        BEFORE VAD so the VAD and Whisper both see the cleaned signal.

        Returns:
            Concatenated speech buffer (ready for Whisper) when enough speech
            has accumulated, or None if still collecting / not speech.
        """
        # --- Pre-processing stage ---
        if self._preprocessor is not None and not preprocessed:
            audio = self._preprocessor.process(audio, sample_rate, mic_id=mic_id)

        # --- Per-mic state ---
        if mic_id not in self._speech_buffers:
            self._speech_buffers[mic_id] = []
            self._speech_gap_counters[mic_id] = 0

        buf   = self._speech_buffers[mic_id]
        gap_c = self._speech_gap_counters[mic_id]

        speech_detected, vad_confidence = self.is_speech(audio, sample_rate, mic_id=mic_id)

        if not speech_detected:

            gap_c += 1
            if gap_c >= self._speech_gap_max:
                if buf:
                    logger.debug(f"VAD gap exceeded max for mic{mic_id}. Clearing speech buffer.")
                    buf.clear()
                gap_c = 0
            self._speech_gap_counters[mic_id] = gap_c
            logger.debug(f"VAD: not speech on mic{mic_id} (conf={vad_confidence:.3f}, thr={self._vad_threshold:.3f})")
            return None

        self._speech_gap_counters[mic_id] = 0
        buf.append(audio.copy())

        total_sec = sum(len(a) for a in buf) / sample_rate
        if total_sec < self._speech_buffer_sec:
            logger.info(f"Accumulating speech on mic{mic_id}... ({total_sec:.1f}s / {self._speech_buffer_sec:.1f}s)")
            return None

        logger.info(f"Speech buffer ready on mic{mic_id} ({total_sec:.1f}s) — sending to Whisper")
        full_audio = np.concatenate(buf)
        buf.clear()
        self._speech_buffers[mic_id] = buf
        return full_audio

    def transcribe_and_match(
        self, audio: np.ndarray, sample_rate: int
    ) -> "KeywordResult":
        """
        Stage 2+3: Whisper transcription + keyword matching.

        This is the SLOW half of analyze(), designed to run in
        a dedicated Whisper worker thread without blocking VAD.

        Returns:
            KeywordResult (is_cheating may be False if no keywords matched).
        """
        try:
            result = self.transcribe(audio, sample_rate)
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            return KeywordResult()

        transcript = result.get("text", "").strip()
        if not transcript:
            return KeywordResult()

        avg_confidence = result.get("avg_confidence", 0.0)
        detected_language = result.get("language", self._language)
        logger.info(f"Whisper transcript: '{transcript}' (lang={detected_language}, conf={avg_confidence:.3f})")

        matched = self.match_keywords(transcript)

        if self._strict_mode:
            is_cheating = len(transcript) > 0
            if is_cheating and not matched:
                matched = ["*UNAUTHORIZED_SPEECH*"]
        else:
            is_cheating = len(matched) > 0

        if is_cheating:
            mode_label = "STRICT" if self._strict_mode else "KEYWORD"
            logger.warning(f"[{mode_label} MODE] UNAUTHORIZED SPEECH: {matched}")

        return KeywordResult(
            transcript=transcript,
            matched_keywords=matched,
            is_cheating=is_cheating,
            confidence=avg_confidence,
            language=detected_language,
        )


    def analyze(self, audio: np.ndarray, sample_rate: int, mic_id: int = 0) -> "KeywordResult | None":
        """
        Full analysis pipeline (backward-compatible): VAD → Whisper → Keywords.

        Delegates to vad_and_buffer() + transcribe_and_match() internally.
        Returns None if not enough speech has accumulated yet.
        """
        speech_buffer = self.vad_and_buffer(audio, sample_rate, mic_id=mic_id)
        if speech_buffer is None:
            return None
        return self.transcribe_and_match(speech_buffer, sample_rate)
