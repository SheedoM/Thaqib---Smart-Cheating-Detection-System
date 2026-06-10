"""
Audio processing pipeline orchestrator.

Coordinates all audio subsystems:
    Source -> Discriminator -> VAD -> Whisper -> Keywords -> Alerts

Runs as a standalone system, independent of the video pipeline.
All default parameters are loaded from the shared .env / settings system
(AUDIO_* environment variables), just like the video pipeline.
"""

import collections
import logging
import threading
import time
from dataclasses import dataclass
import queue

import numpy as np

from thaqib.config import get_settings
from thaqib.audio.models import AudioChunk, AudioAlert, CheatEpisode
from thaqib.audio.source import AudioSource
from thaqib.audio.discriminator import GlobalLocalDiscriminator
from thaqib.audio.keyword_detector import KeywordDetector
from thaqib.audio.evidence import AudioEvidenceRecorder
from thaqib.audio.session_recorder import SessionAudioRecorder
from thaqib.audio.preprocessor import AudioPreprocessor

logger = logging.getLogger(__name__)


@dataclass
class _PendingAlert:
    alert: AudioAlert
    audio_sequence: list[np.ndarray]
    target_post_chunks: int
    post_collected: int = 0


@dataclass
class _WhisperTask:
    """Payload pushed from VAD worker to Whisper worker."""
    audio_buffer: np.ndarray      # ready speech buffer for Whisper
    mic_id: int
    chunk: "AudioChunk"           # triggering chunk (timestamp, index, etc.)
    classification: object        # SoundClassification
    history_snapshot: list[dict]  # pre-event audio history
    sample_rate: int


class EpisodeTracker:
    """
    Tracks sustained cheating episodes per microphone.

    Logic:
        1. on_alert(alert)  → open episode (or extend existing one)
           Mark CONFIRMED once cheating sustained >= episode_min_sec
        2. on_chunk(chunk)  → add raw audio to all open episodes
           If now - last_alert_time >= episode_grace_sec AND confirmed
           → close episode and return it for saving
        3. flush()          → force-close on pipeline shutdown

    Settings (from .env):
        AUDIO_EPISODE_MIN_SEC   = minimum sustained duration to confirm cheating
        AUDIO_EPISODE_GRACE_SEC = silence gap before declaring episode over
    """

    def __init__(self, episode_min_sec: float = 3.0, episode_grace_sec: float = 5.0):
        self._min_sec   = episode_min_sec
        self._grace_sec = episode_grace_sec
        self._episodes: dict[int, CheatEpisode] = {}   # keyed by mic_id
        self._lock = threading.Lock()

    def on_alert(self, alert: "AudioAlert") -> None:
        """Register a new cheating alert — opens or extends the episode."""
        with self._lock:
            mic_id = alert.mic_id
            now    = alert.timestamp

            if mic_id not in self._episodes:
                ep = CheatEpisode(
                    mic_id=mic_id,
                    start_time=now,
                    last_alert_time=now,
                    sample_rate=alert.sample_rate,
                )
                # Initialize with the alert's audio clip which contains [1.0s pre-event] + [first incident chunk/buffer]
                ep.audio_chunks = [alert.audio_clip.copy()]
                self._episodes[mic_id] = ep
                logger.info(f"Episode OPENED  mic{mic_id} @ {now:.1f}")
            else:
                ep = self._episodes[mic_id]

            ep.on_alert(alert)

            if not ep.confirmed and (now - ep.start_time) >= self._min_sec:
                ep.confirmed = True
                logger.warning(
                    f"Episode CONFIRMED mic{mic_id}: sustained={now - ep.start_time:.1f}s "
                    f"alerts={ep.alert_count} keywords={ep.all_keywords}"
                )

    def on_chunk(self, chunk: "AudioChunk", processed_mics: "list[np.ndarray] | None" = None) -> "list[CheatEpisode]":
        """Accumulate audio + check if any episodes should close."""
        now = chunk.timestamp
        completed = []
        with self._lock:
            for mic_id, ep in list(self._episodes.items()):
                if mic_id < chunk.mic_data.shape[0]:
                    if processed_mics is not None and mic_id < len(processed_mics):
                        ep.audio_chunks.append(processed_mics[mic_id].copy())
                    else:
                        ep.audio_chunks.append(chunk.mic_data[mic_id].copy())

                idle_sec = now - ep.last_alert_time
                if idle_sec >= self._grace_sec:
                    if ep.confirmed:
                        # Slice out grace period chunks from the end
                        chunk_duration_sec = chunk.duration_ms / 1000.0
                        num_grace_chunks = int(idle_sec / chunk_duration_sec)
                        if num_grace_chunks > 0 and len(ep.audio_chunks) > num_grace_chunks:
                            ep.audio_chunks = ep.audio_chunks[:-num_grace_chunks]
                        completed.append(ep)
                        logger.info(
                            f"Episode CLOSED  mic{mic_id}: "
                            f"duration={ep.duration_sec:.1f}s idle={idle_sec:.1f}s"
                        )
                    else:
                        logger.debug(
                            f"Episode DISCARDED mic{mic_id}: "
                            f"not confirmed ({ep.duration_sec:.1f}s < {self._min_sec}s)"
                        )
                    del self._episodes[mic_id]
        return completed

    def flush(self) -> "list[CheatEpisode]":
        """Force-close all open confirmed episodes (on pipeline shutdown)."""
        with self._lock:
            confirmed = [ep for ep in self._episodes.values() if ep.confirmed]
            self._episodes.clear()
        return confirmed


class AsyncAudioWriter:
    """Thread-safe background queue worker for non-blocking file writes."""

    def __init__(self):
        self._queue = queue.Queue(maxsize=200)
        self._is_running = False
        self._thread = None

    def start(self):
        if self._is_running:
            return
        self._is_running = True
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="AsyncAudioWriter"
        )
        self._thread.start()

    def enqueue_write(self, func, *args, **kwargs):
        if not self._is_running:
            return
        try:
            self._queue.put_nowait((func, args, kwargs))
        except queue.Full:
            logger.error("AsyncAudioWriter queue full! Dropping write task.")

    def stop(self):
        self._is_running = False
        self._queue.put(None)
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None

    def _run_loop(self):
        while self._is_running:
            try:
                task = self._queue.get(timeout=0.5)
                if task is None:
                    self._queue.task_done()
                    break
                func, args, kwargs = task
                try:
                    func(*args, **kwargs)
                except Exception as e:
                    logger.error(f"AsyncAudioWriter error executing {func.__name__}: {e}", exc_info=True)
                finally:
                    self._queue.task_done()
            except queue.Empty:
                continue


class AudioPipeline:
    """
    Main audio cheating detection pipeline.

    Processes audio from any AudioSource (live mics or files),
    classifies sounds as global vs. local, and runs keyword
    detection on local speech.

    Can run in its own thread (for integration with video)
    or synchronously (for standalone use / testing).

    Example (standalone):
        >>> from thaqib.audio.source import FileAudioSource
        >>> source = FileAudioSource(["mic1.mp3", "mic2.m4a"])
        >>> pipeline = AudioPipeline(source)
        >>> pipeline.run_sync()  # Process all audio, print results

    Example (threaded, for video integration):
        >>> alert_queue = Queue()
        >>> pipeline = AudioPipeline(source, alert_queue=alert_queue)
        >>> pipeline.start()  # Runs in background thread
        >>> # ... main thread does video processing ...
        >>> alert = alert_queue.get()  # Receive audio alerts
    """

    def __init__(
        self,
        source: AudioSource,
        alert_queue: queue.Queue | None = None,
        whisper_model: str | None = None,
        language: str | None = None,
        keywords_file: str | None = None,
        silence_threshold: float | None = None,
        global_ratio: float | None = None,
        global_fraction: float | None = None,
        use_cross_correlation: bool | None = None,
        on_alert: callable = None,
        on_chunk: callable = None,
        clip_sec_before: float | None = None,
        clip_sec_after: float | None = None,
        strict_mode: bool | None = None,
        speech_buffer_sec: float | None = None,
        speech_gap_max: int | None = None,
        history_chunks: int | None = None,
        inference_queue_size: int | None = None,
        output_dir: str | None = None,
        calibration_chunks: int | None = None,
        local_ratio_multiplier: float | None = None,
        recalibration_interval_sec: float | None = None,
        session_recording: bool | None = None,
        sessions_dir: str | None = None,
        vad_context_ms: int | None = None,
    ):
        """
        Initialize the audio pipeline.

        All parameters default to None, which means they are read from the
        shared settings system (AUDIO_* environment variables / .env file).
        Any explicitly passed value overrides the setting for this instance.

        Args:
            source: Audio source (FileAudioSource or LiveAudioSource).
            alert_queue: Optional queue for sending alerts to another system.
            whisper_model: Whisper model size. Env: AUDIO_WHISPER_MODEL.
            language: Expected language code. Env: AUDIO_LANGUAGE.
            keywords_file: Path to cheating keywords JSON. Env: AUDIO_KEYWORDS_FILE.
            silence_threshold: Discriminator silence cutoff. Env: AUDIO_SILENCE_THRESHOLD.
            global_ratio: Discriminator heard-by-mic threshold. Env: AUDIO_GLOBAL_RATIO.
            global_fraction: Discriminator global-fraction threshold. Env: AUDIO_GLOBAL_FRACTION.
            use_cross_correlation: Enable cross-correlation validation. Env: AUDIO_CROSS_CORRELATION.
            on_alert: Callback called with each AudioAlert.
            on_chunk: Callback called with (AudioChunk, SoundClassification).
            clip_sec_before: Pre-event audio seconds. Env: AUDIO_CLIP_SEC_BEFORE.
            clip_sec_after: Post-event audio seconds. Env: AUDIO_CLIP_SEC_AFTER.
            strict_mode: If True, ANY speech = cheating. Env: AUDIO_STRICT_MODE.
            speech_buffer_sec: Seconds to accumulate before Whisper. Env: AUDIO_SPEECH_BUFFER_SEC.
            speech_gap_max: Non-speech chunks before buffer reset. Env: AUDIO_SPEECH_GAP_MAX.
            history_chunks: Rolling history buffer size. Env: AUDIO_HISTORY_CHUNKS.
            inference_queue_size: Inference queue capacity. Env: AUDIO_INFERENCE_QUEUE_SIZE.
            output_dir: Directory for evidence files. Env: AUDIO_OUTPUT_DIR.
            calibration_chunks: Non-silent chunks used to learn baseline ratio. Env: AUDIO_CALIBRATION_CHUNKS.
            local_ratio_multiplier: Normalized ratio threshold for LOCAL. Env: AUDIO_LOCAL_RATIO_MULTIPLIER.
            recalibration_interval_sec: Seconds between periodic baseline re-learning. Env: AUDIO_RECALIBRATION_INTERVAL_SEC.
            session_recording: If True, record all audio to WAV files. Env: AUDIO_SESSION_RECORDING.
            sessions_dir: Directory for session recordings. Env: AUDIO_SESSIONS_DIR.
        """
        s = get_settings()

        # Resolve each param: explicit arg takes precedence, else fall back to settings
        _whisper_model       = whisper_model       if whisper_model       is not None else s.audio_whisper_model
        _language            = language            if language            is not None else s.audio_language
        _keywords_file       = keywords_file       if keywords_file       is not None else s.audio_keywords_file
        _silence_threshold   = silence_threshold   if silence_threshold   is not None else s.audio_silence_threshold
        _global_ratio        = global_ratio        if global_ratio        is not None else s.audio_global_ratio
        _global_fraction     = global_fraction     if global_fraction     is not None else s.audio_global_fraction
        _cross_correlation   = use_cross_correlation if use_cross_correlation is not None else s.audio_cross_correlation
        _clip_sec_before     = clip_sec_before     if clip_sec_before     is not None else s.audio_clip_sec_before
        _clip_sec_after      = clip_sec_after      if clip_sec_after      is not None else s.audio_clip_sec_after
        _strict_mode         = strict_mode         if strict_mode         is not None else s.audio_strict_mode
        _speech_buffer_sec   = speech_buffer_sec   if speech_buffer_sec   is not None else s.audio_speech_buffer_sec
        _speech_gap_max      = speech_gap_max      if speech_gap_max      is not None else s.audio_speech_gap_max
        _history_chunks      = history_chunks      if history_chunks      is not None else s.audio_history_chunks
        _inference_q_size    = inference_queue_size if inference_queue_size is not None else s.audio_inference_queue_size
        _output_dir          = output_dir          if output_dir          is not None else s.audio_output_dir
        _calibration_chunks  = calibration_chunks  if calibration_chunks  is not None else s.audio_calibration_chunks
        _local_ratio_mult    = local_ratio_multiplier if local_ratio_multiplier is not None else s.audio_local_ratio_multiplier
        _recalib_interval    = recalibration_interval_sec if recalibration_interval_sec is not None else s.audio_recalibration_interval_sec
        _session_recording   = session_recording   if session_recording   is not None else s.audio_session_recording
        _sessions_dir        = sessions_dir        if sessions_dir        is not None else s.audio_sessions_dir
        _vad_context_ms      = vad_context_ms      if vad_context_ms      is not None else s.audio_vad_context_ms

        logger.info(
            f"AudioPipeline init: model={_whisper_model} lang={_language} "
            f"strict={_strict_mode} vad_buf={_speech_buffer_sec}s "
            f"queue={_inference_q_size} history={_history_chunks} "
            f"calibration={_calibration_chunks}chunks multiplier={_local_ratio_mult}x "
            f"vad_only={getattr(s, 'audio_vad_only', False)}"
        )

        self._settings = s
        self._source = source
        self._alert_queue = alert_queue
        self._use_cross_correlation = _cross_correlation
        self._on_alert = on_alert
        self._on_chunk = on_chunk
        self._clip_sec_before = _clip_sec_before
        self._clip_sec_after = _clip_sec_after

        # ── Audio Preprocessor (HPF + noise reduction + adaptive gain) ──────────
        self._preprocessor = AudioPreprocessor(
            hpf_cutoff=getattr(s, 'audio_hpf_cutoff', 100),
            noise_reduction=getattr(s, 'audio_noise_reduction', True),
            noise_reduction_strength=getattr(s, 'audio_noise_reduction_strength', 0.75),
            adaptive_gain=getattr(s, 'audio_adaptive_gain', True),
            transient_suppression=getattr(s, 'audio_transient_suppression', True),
            transient_threshold=getattr(s, 'audio_transient_threshold', 0.65),
            transient_damping=getattr(s, 'audio_transient_damping', 0.15),
        )

        self._discriminator = GlobalLocalDiscriminator(
            silence_threshold=_silence_threshold,
            global_ratio=_global_ratio,
            global_fraction=_global_fraction,
            calibration_chunks=_calibration_chunks,
            local_ratio_multiplier=_local_ratio_mult,
            recalibration_interval_sec=_recalib_interval,
            on_recalibrate=self._preprocessor.reset_noise_profile,
            chunk_ms=s.audio_chunk_ms,
        )

        self._keyword_detector = KeywordDetector(
            model_size=_whisper_model,
            language=_language,
            keywords_file=_keywords_file,
            strict_mode=_strict_mode,
            speech_buffer_sec=_speech_buffer_sec,
            speech_gap_max=_speech_gap_max,
            beam_size=getattr(s, 'audio_whisper_beam_size', 1),
            device=getattr(s, 'audio_device', 'auto'),
            compute_type=getattr(s, 'audio_compute_type', 'auto'),
            adaptive_vad=getattr(s, 'audio_adaptive_vad', True),
            vad_calibration_chunks=getattr(s, 'audio_vad_calibration_chunks', 50),
            preprocessor=self._preprocessor,
            vad_context_ms=_vad_context_ms,
        )

        self._evidence_recorder = AudioEvidenceRecorder(
            output_dir=_output_dir,
            mic_names=s.mic_registry,           # dict[int, str] — supports IPs, any count
        )
        # Store registry for log messages throughout the pipeline
        self._mic_registry: dict[int, str] = s.mic_registry

        # Session recorder — streams all audio to WAV for post-exam analysis
        self._session_recorder: SessionAudioRecorder | None = (
            SessionAudioRecorder(output_dir=_sessions_dir) if _session_recording else None
        )

        self._chunk_history = collections.deque(maxlen=_history_chunks)
        self._pending_alerts: list[_PendingAlert] = []

        # Episode-based sustained cheat detection
        _episode_recording = getattr(s, 'audio_episode_recording', True)
        self._episode_tracker: EpisodeTracker | None = (
            EpisodeTracker(
                episode_min_sec=getattr(s, 'audio_episode_min_sec', 3.0),
                episode_grace_sec=getattr(s, 'audio_episode_grace_sec', 5.0),
            ) if _episode_recording else None
        )

        self._recording_start_time: float = 0.0
        self._is_running = False
        self._thread: threading.Thread | None = None
        self._worker_thread: threading.Thread | None = None

        # Separate VAD queue + Whisper queue for non-blocking inference
        # _inference_queue: main loop → VAD worker (fast, LOCAL chunks)
        # _whisper_queue:   VAD worker → Whisper worker (slow, ready speech buffers)
        self._inference_queue = queue.Queue(maxsize=_inference_q_size)
        self._whisper_queue: queue.Queue = queue.Queue(maxsize=4)
        self._whisper_worker_thread: threading.Thread | None = None

        # Lock protecting _pending_alerts, _stats, and _alerts
        # from concurrent access by main loop and inference worker.
        self._lock = threading.Lock()
        self._async_writer = AsyncAudioWriter()

        # ── VAD-only detection mode ───────────────────────────────────────────
        # When True, the Whisper worker is bypassed entirely: as soon as Silero
        # VAD confirms human speech on a LOCAL chunk, an alert fires immediately.
        # Per-mic cooldown prevents alert spam for continuous whispers.
        self._vad_only: bool = getattr(s, 'audio_vad_only', False)
        self._vad_alert_cooldown: float = getattr(s, 'audio_vad_alert_cooldown', 3.0)
        # dict[mic_id -> monotonic time when next alert is allowed]
        self._vad_alert_times: dict[int, float] = {}

        self._last_vad_dom_mic = None
        self._vad_hangover_chunks = 6
        self._vad_hangover_counter = 0

        # Statistics for dashboard
        self._stats = {
            "chunks_processed": 0,
            "silent_chunks": 0,
            "global_chunks": 0,
            "local_chunks": 0,
            "speech_detected": 0,
            "alerts_triggered": 0,
            "dropped_chunks": 0,
            "two_pass_rescored": 0,   # GLOBAL→LOCAL rescores via two-pass denoising
            "start_time": 0.0,
        }
        self._alerts: list[AudioAlert] = []

        # Pipeline Health Monitor settings & locks
        self._monitor_thread = None
        self._monitor_lock = threading.Lock()
        self._monitor_stop_event = threading.Event()
        self._original_beam_size = self._keyword_detector._beam_size
        self._health_state = "NORMAL"

    @property
    def stats(self) -> dict:
        """Processing statistics for dashboard display."""
        with self._lock:
            return self._stats.copy()

    @property
    def alerts(self) -> list[AudioAlert]:
        """List of all alerts triggered during this session."""
        with self._lock:
            return list(self._alerts)

    def load_models(self) -> None:
        """
        Eagerly load all AI models (Silero VAD + Whisper) into memory.

        Call this BEFORE start() to eliminate first-chunk inference delay.
        Blocks until both models are fully loaded and ready.
        """
        logger.info("[MODEL LOAD] Loading Silero VAD models...")
        t0 = time.time()
        for i in range(self._source.num_mics):
            self._keyword_detector._ensure_vad_loaded_for_mic(i)
        logger.info(f"[MODEL LOAD] VAD ready in {time.time()-t0:.1f}s")

        if not self._vad_only:
            logger.info(f"[MODEL LOAD] Loading Whisper '{self._keyword_detector._model_size}'...")
            t1 = time.time()
            self._keyword_detector._ensure_whisper_loaded()
            logger.info(f"[MODEL LOAD] Whisper ready in {time.time()-t1:.1f}s")

        logger.info(f"[MODEL LOAD] All models ready. Total: {time.time()-t0:.1f}s")

    def start(self) -> None:
        """Load all models then start the audio pipeline in a background thread."""
        if self._is_running:
            logger.warning("Audio pipeline already running")
            return

        # ── Phase 1: Block until all AI models are in memory ──────────────────
        # This guarantees the first LOCAL chunk is processed immediately
        # with zero cold-start delay, instead of waiting 3-10s mid-stream.
        self.load_models()

        # ── Phase 2: Start audio ingestion and workers ─────────────────────────
        self._is_running = True
        self._recording_start_time = time.time()
        self._stats["start_time"] = self._recording_start_time
        self._source.start()
        self._async_writer.start()

        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="AudioPipeline",
        )
        self._thread.start()

        # Start VAD worker + Whisper worker as separate threads
        self._worker_thread = threading.Thread(
            target=self._inference_worker, daemon=True, name="AudioVADWorker"
        )
        self._worker_thread.start()

        self._whisper_worker_thread = threading.Thread(
            target=self._whisper_worker, daemon=True, name="AudioWhisperWorker"
        )
        self._whisper_worker_thread.start()

        # Start Pipeline Health Monitor Agent
        self._monitor_stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="AudioPipelineMonitor"
        )
        self._monitor_thread.start()

        # ── Phase 3: Open session recorder (streams all audio to WAV) ──────────
        if self._session_recorder:
            self._session_recorder.open(
                n_mics=self._source.num_mics,
                sample_rate=self._source.sample_rate,
            )

        logger.info("Audio pipeline started — models pre-loaded, zero cold-start delay")

    def stop(self) -> None:
        """Stop the audio pipeline and all worker threads."""
        self._is_running = False
        self._source.stop()
        self._async_writer.stop()

        # Shutdown Health Monitor Agent
        self._monitor_stop_event.set()
        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=3.0)
            self._monitor_thread = None

        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None

        # Drain both queues with sentinels
        self._inference_queue.put(None)
        if self._worker_thread is not None:
            self._worker_thread.join(timeout=5.0)
            self._worker_thread = None

        self._whisper_queue.put(None)
        if self._whisper_worker_thread is not None:
            self._whisper_worker_thread.join(timeout=30.0)  # Whisper may be mid-inference
            self._whisper_worker_thread = None

        # Close session recorder and write manifest
        if self._session_recorder and self._session_recorder.is_open:
            self._session_recorder.close()

        logger.info(
            f"Audio pipeline stopped. Stats: "
            f"{self._stats['chunks_processed']} chunks processed, "
            f"{self._stats.get('dropped_chunks', 0)} dropped, "
            f"{self._stats['alerts_triggered']} alerts"
        )

    def run_sync(self) -> list[AudioAlert]:
        """
        Run the pipeline synchronously (blocking).

        Processes all audio from the source until exhausted.
        Returns the list of triggered alerts.
        """
        # ── Phase 1: Block until all AI models are in memory ──────────────────
        self.load_models()

        # ── Phase 2: Start ingestion ─────────────────────────────────────────
        self._is_running = True
        self._recording_start_time = time.time()
        self._stats["start_time"] = self._recording_start_time
        self._source.start()
        self._async_writer.start()

        # ── Phase 3: Open session recorder ──────────────────────────────
        if self._session_recorder:
            self._session_recorder.open(
                n_mics=self._source.num_mics,
                sample_rate=self._source.sample_rate,
            )

        logger.info("Audio pipeline running (synchronous mode)")

        # Start both worker threads in sync mode too
        self._worker_thread = threading.Thread(
            target=self._inference_worker, daemon=True, name="AudioVADWorker"
        )
        self._worker_thread.start()

        self._whisper_worker_thread = threading.Thread(
            target=self._whisper_worker, daemon=True, name="AudioWhisperWorker"
        )
        self._whisper_worker_thread.start()

        # Start Pipeline Health Monitor Agent
        self._monitor_stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="AudioPipelineMonitor"
        )
        self._monitor_thread.start()

        try:
            self._run_loop()
        finally:
            self._source.stop()
            self._async_writer.stop()
            
            # Shutdown Health Monitor Agent
            self._monitor_stop_event.set()
            if self._monitor_thread is not None:
                self._monitor_thread.join(timeout=3.0)
                self._monitor_thread = None

            self._inference_queue.put(None)
            if self._worker_thread is not None:
                self._worker_thread.join(timeout=5.0)
                self._worker_thread = None

            self._whisper_queue.put(None)
            if self._whisper_worker_thread is not None:
                self._whisper_worker_thread.join(timeout=30.0)
                self._whisper_worker_thread = None

            # Close session recorder in run_sync too
            if self._session_recorder and self._session_recorder.is_open:
                self._session_recorder.close()

            logger.info(
                f"Audio pipeline stopped. Stats: "
                f"{self._stats['chunks_processed']} chunks processed, "
                f"{self._stats.get('dropped_chunks', 0)} dropped, "
                f"{self._stats['alerts_triggered']} alerts"
            )

        return list(self._alerts)

    def _monitor_loop(self) -> None:
        """
        Background thread monitoring the audio pipeline queues and dynamically
        swapping Whisper decoding parameters to handle load spikes.
        """
        logger.info("[Health Monitor] Agent started background monitoring loop.")
        while self._is_running and not self._monitor_stop_event.is_set():
            try:
                inf_qsize = self._inference_queue.qsize()
                wh_qsize = self._whisper_queue.qsize()

                # Swapping logic based on whisper queue thresholds with hysteresis
                with self._monitor_lock:
                    if wh_qsize >= 3:
                        if self._health_state != "CRITICAL":
                            logger.warning(
                                f"[Health Monitor] Pipeline WARNING/CRITICAL state! "
                                f"VAD queue={inf_qsize}, Whisper queue={wh_qsize}. "
                                f"Activating load-shedding: swapping beam_size {self._original_beam_size} -> 1."
                            )
                            self._health_state = "CRITICAL"
                            self._keyword_detector._beam_size = 1
                    elif wh_qsize <= 1:
                        if self._health_state != "NORMAL":
                            logger.info(
                                f"[Health Monitor] Pipeline recovered to NORMAL state. "
                                f"VAD queue={inf_qsize}, Whisper queue={wh_qsize}. "
                                f"Restoring original beam_size -> {self._original_beam_size}."
                            )
                            self._health_state = "NORMAL"
                            self._keyword_detector._beam_size = self._original_beam_size

            except Exception as e:
                logger.error(f"[Health Monitor] Error: {e}", exc_info=True)

            # Wait on stop event instead of sleeping to terminate immediately on exit
            if self._monitor_stop_event.wait(timeout=1.0):
                break
        logger.info("[Health Monitor] Agent stopped background monitoring loop.")

    def _run_loop(self) -> None:
        """Main processing loop."""
        try:
            while self._is_running:
                chunk = self._source.get_chunk()

                if chunk is None:
                    # Source exhausted (file ended) or stopped
                    logger.info("Audio source exhausted — stopping pipeline")
                    self._is_running = False
                    break

                # 0. Compute processed audio ONCE per chunk.
                #    Reused by: session recorder (processed/ folder) + Two-Pass discriminator.
                #    Computing it twice caused adaptive-gain state drift that suppressed the 3rd alert.
                #    raw/       <- always written (original samples)
                #    processed/ <- written once the noise profile is ready
                _processed_mics_cache: "list[np.ndarray] | None" = None
                if self._preprocessor.noise_profile_ready:
                    try:
                        _processed_mics_cache = [
                            self._preprocessor.process(
                                chunk.mic_data[i], chunk.sample_rate, mic_id=i
                            )
                            for i in range(chunk.mic_data.shape[0])
                        ]
                    except Exception as _pe:
                        logger.debug(f"Preprocessor error (chunk {chunk.chunk_index}): {_pe}")

                if self._session_recorder and self._session_recorder.is_open:
                    self._async_writer.enqueue_write(
                        self._session_recorder.write_chunk, chunk, processed_mics=_processed_mics_cache
                    )

                # 1. Provide the new chunk to any pending alerts
                completed_alerts = []
                with self._lock:
                    for pending in self._pending_alerts:
                        pending.audio_sequence.append(chunk.mic_data[pending.alert.mic_id].copy())
                        pending.post_collected += 1
                        if pending.post_collected >= pending.target_post_chunks:
                            completed_alerts.append(pending)
                    
                    # 2. Save any completed alerts
                    for completed in completed_alerts:
                        self._pending_alerts.remove(completed)

                for completed in completed_alerts:
                    full_audio = np.concatenate(completed.audio_sequence)
                    completed.alert.audio_clip = full_audio
                    self._async_writer.enqueue_write(
                        self._evidence_recorder.save_alert, completed.alert
                    )

                # 3. Process the chunk (fast classification)
                #    Pass the already-computed processed audio so Two-Pass
                #    does NOT call preprocessor.process() a second time.
                classification = self._process_chunk(chunk, precomputed_processed=_processed_mics_cache)

                # 3b. Feed GLOBAL/SILENT chunks to noise profile learner.
                # IMPORTANT: only truly-GLOBAL chunks train the noise model.
                # Two-pass rescored chunks (originally GLOBAL, reclassified LOCAL)
                # must NOT train the noise profile — they contain the whisper signal.
                is_two_pass_local = (
                    classification
                    and classification.is_local
                    and self._stats.get("two_pass_rescored", 0) > 0
                    # Heuristic: if this chunk was just rescored it appears LOCAL now.
                    # The safe guard is: we only add GLOBAL chunks to the learner.
                )
                if classification and (classification.is_global or classification.is_silent):
                    for mic_id in range(chunk.mic_data.shape[0]):
                        self._preprocessor.add_noise_sample(
                            chunk.mic_data[mic_id], chunk.sample_rate, mic_id=mic_id
                        )

                # 3c. Episode tracker — accumulate audio + detect closed episodes
                if self._episode_tracker is not None:
                    use_processed = getattr(self._settings, 'audio_episode_use_processed', False)
                    tracker_processed_mics = _processed_mics_cache if use_processed else None
                    closed_episodes = self._episode_tracker.on_chunk(chunk, processed_mics=tracker_processed_mics)
                    for ep in closed_episodes:
                        self._async_writer.enqueue_write(
                            self._evidence_recorder.save_episode, ep
                        )

                # 4. Add to history buffer
                self._chunk_history.append(chunk)
                
                # 5. Enqueue for slow inference if local
                if classification and classification.is_local:
                    history_list = list(self._chunk_history)
                    n_mics = chunk.mic_data.shape[0]
                    # Snapshot the last 20 chunks for all mics to ensure history is always available
                    history_snapshot = [
                        {mic_id: c.mic_data[mic_id].copy() for mic_id in range(n_mics)}
                        for c in history_list[-20:]
                    ]
                    try:
                        self._inference_queue.put_nowait(
                            (chunk, classification, history_snapshot, _processed_mics_cache)
                        )
                    except queue.Full:
                        logger.warning(f"Inference queue full — dropping oldest VAD task to enqueue chunk {chunk.chunk_index}")
                        try:
                            self._inference_queue.get_nowait()
                        except queue.Empty:
                            pass
                        try:
                            self._inference_queue.put_nowait(
                                (chunk, classification, history_snapshot, _processed_mics_cache)
                            )
                        except queue.Full:
                            pass
                        with self._lock:
                            self._stats["dropped_chunks"] += 1
        finally:
            # Flush any remaining pending alerts on shutdown
            with self._lock:
                remaining = list(self._pending_alerts)
                self._pending_alerts.clear()
            for pending in remaining:
                full_audio = np.concatenate(pending.audio_sequence)
                pending.alert.audio_clip = full_audio
                self._async_writer.enqueue_write(
                    self._evidence_recorder.save_alert, pending.alert
                )

            # Flush any open confirmed episodes on shutdown
            if self._episode_tracker is not None:
                for ep in self._episode_tracker.flush():
                    self._async_writer.enqueue_write(
                        self._evidence_recorder.save_episode, ep
                    )

    def _process_chunk(
        self,
        chunk: "AudioChunk",
        precomputed_processed: "list[np.ndarray] | None" = None,
    ) -> "SoundClassification":
        """
        Process a single audio chunk (fast synchronous part).

        Args:
            chunk: Raw AudioChunk from the audio source.
            precomputed_processed: Pre-computed per-mic denoised audio arrays
                (from the run loop's single preprocessor call). When provided,
                the Two-Pass step reuses these directly instead of calling
                preprocessor.process() again, preventing adaptive-gain drift.
        """
        with self._lock:
            self._stats["chunks_processed"] += 1

        # ── Pass 1: Classify raw audio ────────────────────────────────────────
        classification = self._discriminator.classify(chunk)

        # ── Pass 2: Two-pass discrimination (noise-aware re-classification) ──
        #
        # Problem: In a noisy exam hall (HVAC, chairs, general room hum), ALL
        # microphones pick up similar background energy. A student whispering
        # near mic-0 creates energy on that mic, but the shared noise floor
        # raises mic-1 too — making the ratio look small → wrongly GLOBAL.
        #
        # Fix: Once the noise profile is learned (from the first ~30 GLOBAL
        # chunks), denoise each microphone independently, then re-classify.
        # After subtraction, the shared room noise disappears from both mics,
        # but the whisper energy (which was only on mic-0) remains.
        # Now the ratio is large again → correctly LOCAL → goes to VAD/Whisper.
        #
        # Only runs when:
        #   - Pass 1 said GLOBAL (not LOCAL or SILENT — those are fine)
        #   - Noise profile is ready (need at least 5 GLOBAL samples first)
        # Cost: one denoising call per mic (~1–3ms, negligible vs Whisper).
        if classification.is_global and self._preprocessor.noise_profile_ready:
            try:
                # For classification, we always compute denoised audio with bypass_agc=True
                # to prevent independent channel AGC from flattening spatial energy ratios.
                denoised_mics = [
                    self._preprocessor.process(chunk.mic_data[i], chunk.sample_rate, mic_id=i, bypass_agc=True)
                    for i in range(chunk.mic_data.shape[0])
                ]
                denoised_chunk = AudioChunk(
                    timestamp=chunk.timestamp,
                    mic_data=np.stack(denoised_mics, axis=0),
                    sample_rate=chunk.sample_rate,
                    duration_ms=chunk.duration_ms,
                    chunk_index=chunk.chunk_index,
                )
                classification2 = self._discriminator.classify(denoised_chunk)

                if classification2.is_local:
                    logger.info(
                        f"[Two-Pass] Chunk {chunk.chunk_index}: GLOBAL->LOCAL after denoising "
                        f"(noise profile chunks={self._preprocessor.noise_chunks_collected}, "
                        f"active_mics={classification2.active_mics})"
                    )
                    classification = classification2
                    with self._lock:
                        self._stats["two_pass_rescored"] += 1

            except Exception as e:
                logger.debug(f"Two-pass re-classification error: {e}")

        # Optional: cross-correlation validation for borderline cases
        if self._use_cross_correlation and classification.is_local:
            classification = self._discriminator.validate_with_cross_correlation(
                chunk, classification
            )

        # Notify dashboard callback
        if self._on_chunk:
            try:
                self._on_chunk(chunk, classification)
            except Exception as e:
                logger.debug(f"on_chunk callback error: {e}")

        # Update stats
        with self._lock:
            if classification.is_silent:
                self._stats["silent_chunks"] += 1
            elif classification.is_global:
                self._stats["global_chunks"] += 1
            elif classification.is_local:
                self._stats["local_chunks"] += 1

        return classification

    def _inference_worker(self) -> None:
        """
        FAST VAD worker thread.

        Consumes LOCAL chunks from _inference_queue, runs Silero VAD
        and accumulates speech buffers.  When a buffer is ready, pushes
        a _WhisperTask to _whisper_queue — without waiting for Whisper.

        crash watchdog: exceptions restart the loop.
        """
        while True:
            try:
                item = self._inference_queue.get(timeout=0.5)
                if item is None:
                    self._inference_queue.task_done()
                    # Signal Whisper worker to drain too
                    self._whisper_queue.put(None)
                    break

                chunk, classification, history_snapshot, processed_mics = item
                self._vad_step(chunk, classification, history_snapshot, processed_mics)
                self._inference_queue.task_done()

            except queue.Empty:
                if not self._is_running:
                    self._whisper_queue.put(None)
                    break
            except Exception as e:
                # Watchdog — log and continue instead of dying
                logger.error(f"VAD worker error: {e}", exc_info=True)
                try:
                    self._inference_queue.task_done()
                except Exception:
                    pass

    def _vad_step(
        self,
        chunk: "AudioChunk",
        classification: object,
        history_snapshot: "list[dict]",
        processed_mics: "list[np.ndarray] | None" = None,
    ) -> None:
        """
        Execution step for the VAD Worker Thread.

        Operational Modes:
            1. VAD-Only Mode (self._vad_only = True):
               Applies per-mic VAD with spatial Voice Content Matching:
               - Denoise each mic independently (removes shared room noise)
               - Run Silero VAD on each denoised mic independently
               - Find the dominant mic (highest VAD confidence)
               - Validate against other mics: if another mic has speech, compute
                 spectral cosine similarity. If similarity >= 0.80, same voice (GLOBAL).
                 If similarity < 0.80, distinct voices (LOCAL -> immediate Alert).
            2. Whisper STT Mode (self._vad_only = False):
               - Selects the dominant mic using the energy-ratio classification.
               - Runs VAD on that mic and accumulates speech in a buffer.
               - When buffer is full, enqueues to Whisper STT queue.
        """
        from thaqib.audio.models import SoundClassification as SC
        n_mics = chunk.mic_data.shape[0]
        if not all(0 <= i < n_mics for i in classification.active_mics):
            logger.error(
                f"active_mics {classification.active_mics} out of range "
                f"for {n_mics} mics — skipping chunk {chunk.chunk_index}"
            )
            return

        # ── VAD-Only fast path: Per-Mic VAD with Spatial Comparison ──────────
        if self._vad_only:
            # Step 1 + 2: Use denoised audio if available, else raw
            #             Run VAD on EVERY mic independently.
            per_mic_vad: list[tuple[int, float]] = []  # (mic_id, vad_confidence)
            for mic_id in range(n_mics):
                # Prefer denoised audio (cleaner speech signal for VAD)
                if processed_mics is not None and mic_id < len(processed_mics):
                    audio = processed_mics[mic_id]
                else:
                    audio = chunk.mic_data[mic_id]
                _, conf = self._keyword_detector.is_speech(audio, chunk.sample_rate, mic_id=mic_id)
                per_mic_vad.append((mic_id, conf))

            # Step 3: Find dominant mic (highest VAD confidence) with hangover
            candidate_dom_mic, candidate_dom_conf = max(per_mic_vad, key=lambda x: x[1])

            if candidate_dom_conf >= self._keyword_detector.get_vad_threshold(candidate_dom_mic):
                if self._last_vad_dom_mic is not None and self._vad_hangover_counter > 0:
                    if candidate_dom_mic != self._last_vad_dom_mic:
                        dom_mic_id = self._last_vad_dom_mic
                        self._vad_hangover_counter -= 1
                        # Get the confidence score for the locked mic
                        dom_conf = dict(per_mic_vad)[dom_mic_id]
                    else:
                        dom_mic_id = candidate_dom_mic
                        dom_conf = candidate_dom_conf
                        self._vad_hangover_counter = self._vad_hangover_chunks
                else:
                    dom_mic_id = candidate_dom_mic
                    dom_conf = candidate_dom_conf
                    self._last_vad_dom_mic = dom_mic_id
                    self._vad_hangover_counter = self._vad_hangover_chunks
            else:
                dom_mic_id = candidate_dom_mic
                dom_conf = candidate_dom_conf
                if self._vad_hangover_counter > 0:
                    self._vad_hangover_counter -= 1
                    if self._vad_hangover_counter == 0:
                        self._last_vad_dom_mic = None

            # No speech anywhere?
            if dom_conf < self._keyword_detector.get_vad_threshold(dom_mic_id):
                return  # silence — nothing to do

            logger.debug(
                f"[Per-Mic-VAD] Chunk {chunk.chunk_index}: "
                + ", ".join(f"mic{mid}={conf:.3f}" for mid, conf in per_mic_vad)
                + f" | dominant=mic{dom_mic_id} (candidate=mic{candidate_dom_mic}, conf={dom_conf:.3f}, hangover={self._vad_hangover_counter})"
            )

            # Step 4: Enhanced bilateral check — Voice Content Matching
            #
            # JUST comparing VAD confidence levels is not enough:
            #   - Two students whispering simultaneously near different mics
            #     would both have high VAD confidence → wrongly GLOBAL.
            #
            # We now require TWO conditions for GLOBAL classification:
            #   (a) Other mic hears speech at >= 70% of dominant mic's confidence
            #       (similar loudness level)
            #   (b) The spectral content of both mics is highly similar >= 0.80
            #       (same voice, same words)
            #
            # If both (a) and (b) → same person's voice heard everywhere → GLOBAL.
            # If (a) but not (b) → two DIFFERENT voices near two mics → LOCAL (cheating).
            # If not (a) → dominant mic clearly has unique speech → LOCAL (cheating).
            dom_audio = (
                processed_mics[dom_mic_id]
                if processed_mics is not None and dom_mic_id < len(processed_mics)
                else chunk.mic_data[dom_mic_id]
            )

            is_local = True
            for other_mic_id, other_conf in per_mic_vad:
                if other_mic_id == dom_mic_id:
                    continue

                # Perform voice cosine similarity check whenever both microphones show a low absolute confidence threshold (e.g. >= 0.15)
                # This ensures global ambient sounds (like the instructor speaking) are correctly matched as global noise
                # regardless of non-linear VAD confidence ratio drops.
                min_conf = getattr(self._settings, 'audio_voice_min_confidence', 0.15)
                sim_threshold = getattr(self._settings, 'audio_voice_similarity_threshold', 0.80)
                if other_conf >= min_conf:
                    other_audio = (
                        processed_mics[other_mic_id]
                        if processed_mics is not None and other_mic_id < len(processed_mics)
                        else chunk.mic_data[other_mic_id]
                    )
                    similarity = self._voice_similarity(dom_audio, other_audio)

                    if similarity >= sim_threshold:
                        # Same voice content (highly correlated spectrum) → GLOBAL (not cheating)
                        logger.debug(
                            f"[Voice-Match] Chunk {chunk.chunk_index} GLOBAL: "
                            f"mic{dom_mic_id} vs mic{other_mic_id} — "
                            f"other_conf={other_conf:.3f}, similarity={similarity:.3f} >= {sim_threshold:.2f}"
                        )
                        is_local = False
                        break
                    else:
                        # Different voice/sound content → LOCAL (cheating)
                        logger.debug(
                            f"[Voice-Match] Chunk {chunk.chunk_index} LOCAL (diff voices): "
                            f"mic{dom_mic_id} vs mic{other_mic_id} — "
                            f"other_conf={other_conf:.3f}, similarity={similarity:.3f} < {sim_threshold:.2f}"
                        )
                # else: vad_ratio < 70% → dominant mic clearly unique → LOCAL (no change)

            if is_local:
                import time as _time
                now = _time.monotonic()
                if now >= self._vad_alert_times.get(dom_mic_id, 0.0):
                    self._vad_alert_times[dom_mic_id] = now + self._vad_alert_cooldown
                    self._fire_vad_only_alert(
                        chunk, classification, history_snapshot, dom_mic_id, dom_conf
                    )
            return

        # ── Normal path: accumulate speech → Whisper ──────────────────────
        # Use dominant mic found in active_mics logic for legacy compatibility
        active_mics = sorted(
            classification.active_mics,
            key=lambda m: classification.energy_profile[m],
            reverse=True,
        )
        for mic_id in active_mics[:1]:
            if processed_mics is not None and mic_id < len(processed_mics):
                mic_audio = processed_mics[mic_id]
                is_preprocessed = True
            else:
                mic_audio = chunk.mic_data[mic_id]
                is_preprocessed = False

            # ── Normal path: accumulate speech → Whisper ──────────────────────
            speech_buffer = self._keyword_detector.vad_and_buffer(
                mic_audio, chunk.sample_rate, mic_id=mic_id, preprocessed=is_preprocessed
            )
            if speech_buffer is not None:
                # Speech buffer is full — push to Whisper worker
                task = _WhisperTask(
                    audio_buffer=speech_buffer,
                    mic_id=mic_id,
                    chunk=chunk,
                    classification=classification,
                    history_snapshot=history_snapshot,
                    sample_rate=chunk.sample_rate,
                )
                try:
                    self._whisper_queue.put_nowait(task)
                except queue.Full:
                    logger.warning(
                        f"Whisper queue full — dropping speech buffer for mic{mic_id}. "
                        f"Whisper is too slow. Consider a faster model."
                    )

    @staticmethod
    def _voice_similarity(audio1: np.ndarray, audio2: np.ndarray) -> float:
        """
        Spectral cosine similarity between two audio signals.

        Measures how similar the FREQUENCY CONTENT (voice fingerprint) of
        two audio clips is, regardless of volume.

        Returns:
            float in [0.0, 1.0]
                1.0 = identical spectral content (same voice, same words)
                0.0 = completely different content (voice vs. noise)

        Examples:
            Teacher speaking → all mics → similarity ~0.90 → GLOBAL
            Student whispering + different ambient on other mic → ~0.15 → LOCAL

        Implementation:
            FFT magnitude spectrum → L2-normalize → cosine dot product.
            Pure numpy, no external dependencies, ~0.1ms per call.
        """
        min_len = min(len(audio1), len(audio2))
        if min_len < 64:
            return 0.0

        # Magnitude spectrum (phase-independent)
        spec1 = np.abs(np.fft.rfft(audio1[:min_len]))
        spec2 = np.abs(np.fft.rfft(audio2[:min_len]))

        norm1 = np.linalg.norm(spec1)
        norm2 = np.linalg.norm(spec2)
        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0

        return float(np.dot(spec1 / norm1, spec2 / norm2))

    def _fire_vad_only_alert(
        self,
        chunk: "AudioChunk",
        classification: object,
        history_snapshot: list[dict],
        mic_id: int,
        vad_confidence: float,
    ) -> None:
        """
        Create and dispatch an AudioAlert from VAD detection alone (no Whisper).

        Called when AUDIO_VAD_ONLY=true and Silero VAD confirms human speech on
        a LOCAL chunk.  No transcription is performed — the alert fires in ~5ms.

        If an alert for this mic is already pending (continuous whisper), the
        existing clip is extended rather than creating a duplicate.
        """
        from thaqib.audio.models import AudioAlert
        mic_audio = chunk.mic_data[mic_id]
        mic_name = self._mic_registry.get(mic_id, f"mic{mic_id}")

        # Check if an alert is already pending for this mic — extend it
        # instead of creating a duplicate (same logic as Whisper path).
        with self._lock:
            existing_pending = None
            for pending in self._pending_alerts:
                if pending.alert.mic_id == mic_id:
                    existing_pending = pending
                    break

            if existing_pending:
                existing_pending.post_collected = 0
                existing_pending.alert.confidence = max(
                    existing_pending.alert.confidence, vad_confidence
                )

        if existing_pending:
            logger.info(
                f"[VAD-Only] Extended alert [{mic_name}]: "
                f"chunk={chunk.chunk_index} vad_conf={vad_confidence:.3f}"
            )
            return

        # Build pre-event audio buffer from history
        chunk_duration_sec = chunk.duration_ms / 1000.0
        pre_chunks_needed  = int(self._clip_sec_before / chunk_duration_sec)

        pre_buffer_frames = history_snapshot[-pre_chunks_needed:] if len(history_snapshot) >= pre_chunks_needed else history_snapshot
        pre_buffer = [frame[mic_id] for frame in pre_buffer_frames if mic_id in frame]
        pre_buffer.append(mic_audio.copy())

        alert = AudioAlert(
            timestamp=chunk.timestamp,
            mic_id=mic_id,
            active_mics=[mic_id],
            transcript="",                          # no Whisper → no transcript
            matched_keywords=["*HUMAN_SPEECH_DETECTED*"],
            audio_clip=np.concatenate(pre_buffer),
            sample_rate=chunk.sample_rate,
            confidence=float(vad_confidence),
            chunk_index=chunk.chunk_index,
            recording_start=self._recording_start_time,
            discriminator_baseline=getattr(classification, 'baseline_ratio', 0.0),
            discriminator_raw_ratio=getattr(classification, 'raw_ratio', 0.0),
            discriminator_normalized_ratio=getattr(classification, 'normalized_ratio', 0.0),
        )

        with self._lock:
            self._alerts.append(alert)
            self._stats["alerts_triggered"] += 1
            self._stats["speech_detected"]   += 1

        # Episode tracker
        if self._episode_tracker is not None:
            self._episode_tracker.on_alert(alert)

        # Defer evidence write if clip_sec_after is configured
        chunk_duration_sec = chunk.duration_ms / 1000.0
        target_post_chunks = int(self._clip_sec_after / chunk_duration_sec) if self._clip_sec_after > 0 else 0

        if target_post_chunks > 0:
            pending_alert = _PendingAlert(
                alert=alert,
                audio_sequence=[alert.audio_clip.copy()],
                target_post_chunks=target_post_chunks,
                post_collected=0,
            )
            with self._lock:
                self._pending_alerts.append(pending_alert)
        else:
            self._async_writer.enqueue_write(
                self._evidence_recorder.save_alert, alert
            )

        # Dispatch to external consumers
        if self._alert_queue is not None:
            self._alert_queue.put(alert)

        if self._on_alert:
            try:
                self._on_alert(alert)
            except Exception as e:
                logger.debug(f"on_alert callback error: {e}")

        logger.warning(
            f"[VAD-Only] HUMAN SPEECH ALERT #{self._stats['alerts_triggered']}: "
            f"mic {mic_id} ({mic_name}), vad_conf={vad_confidence:.3f}, "
            f"chunk={chunk.chunk_index}"
        )

    def _whisper_worker(self) -> None:
        """
        SLOW Whisper worker thread.

        Consumes _WhisperTask items, runs Whisper + keyword matching,
        and creates alerts.  Runs independently of the VAD worker so
        a 5-second Whisper call never blocks new chunk processing.

        crash watchdog: exceptions restart the loop.
        """
        while True:
            try:
                item = self._whisper_queue.get(timeout=1.0)
                if item is None:
                    self._whisper_queue.task_done()
                    break
                self._process_chunk_inference(
                    item.chunk,
                    item.classification,
                    item.history_snapshot,
                    precomputed_buffer=item.audio_buffer,
                    mic_id=item.mic_id,
                )
                self._whisper_queue.task_done()

            except queue.Empty:
                if not self._is_running:
                    break
            except Exception as e:
                # Watchdog — log and continue
                logger.error(f"Whisper worker error: {e}", exc_info=True)
                try:
                    self._whisper_queue.task_done()
                except Exception:
                    pass

    def _process_chunk_inference(
        self,
        chunk: "AudioChunk",
        classification: object,
        history_snapshot: list[dict],
        precomputed_buffer: "np.ndarray | None" = None,
        mic_id: int | None = None,
    ) -> None:
        """
        Whisper + alert creation (runs in Whisper worker thread).

        precomputed_buffer: already-transcribable speech buffer from vad_and_buffer().
        mic_id: the mic to process (must be set when precomputed_buffer is given).
        """
        n_mics = chunk.mic_data.shape[0]
        if not all(0 <= i < n_mics for i in classification.active_mics):
            logger.error(
                f"active_mics {classification.active_mics} out of range "
                f"for {n_mics} mics — skipping chunk {chunk.chunk_index}"
            )
            return

        if mic_id is None:
            active_mics = sorted(
                classification.active_mics,
                key=lambda m: classification.energy_profile[m],
                reverse=True,
            )
            mic_id = active_mics[0] if active_mics else classification.active_mics[0]

        mic_audio = chunk.mic_data[mic_id]

        # Use pre-computed speech buffer if provided (two-thread path)
        if precomputed_buffer is not None:
            result = self._keyword_detector.transcribe_and_match(
                precomputed_buffer, chunk.sample_rate
            )
        else:
            # Legacy single-thread path (fallback)
            result = self._keyword_detector.analyze(
                mic_audio, chunk.sample_rate, mic_id=mic_id
            )

        if result is None:
            return

        with self._lock:
            self._stats["speech_detected"] += 1

        mic_name = self._mic_registry.get(mic_id, f"mic{mic_id}")

        if result.is_cheating:
            existing_pending = None
            with self._lock:
                for pending in self._pending_alerts:
                    if pending.alert.mic_id == mic_id:
                        existing_pending = pending
                        break

                if existing_pending:
                    existing_pending.post_collected = 0
                    for kw in result.matched_keywords:
                        if kw not in existing_pending.alert.matched_keywords:
                            existing_pending.alert.matched_keywords.append(kw)
                    existing_pending.alert.transcript += " " + result.transcript
                    existing_pending.alert.confidence = max(
                        existing_pending.alert.confidence, result.confidence
                    )

            if existing_pending:
                logger.warning(
                    f"EXTENDED ALERT [{mic_name}]: keywords={result.matched_keywords}"
                )
            else:
                alert = AudioAlert(
                    timestamp=chunk.timestamp,
                    mic_id=mic_id,
                    active_mics=classification.active_mics,
                    transcript=result.transcript,
                    matched_keywords=result.matched_keywords,
                    audio_clip=mic_audio.copy(),
                    sample_rate=chunk.sample_rate,
                    confidence=result.confidence,
                    chunk_index=chunk.chunk_index,
                    recording_start=self._recording_start_time,
                    # Log the discriminator's decision metrics in alert
                    discriminator_baseline=getattr(classification, 'baseline_ratio', 0.0),
                    discriminator_raw_ratio=getattr(classification, 'raw_ratio', 0.0),
                    discriminator_normalized_ratio=getattr(classification, 'normalized_ratio', 0.0),
                )

                with self._lock:
                    self._alerts.append(alert)
                    self._stats["alerts_triggered"] += 1

                # Episode tracker — register the new alert
                if self._episode_tracker is not None:
                    self._episode_tracker.on_alert(alert)

                chunk_duration_sec = chunk.duration_ms / 1000.0
                pre_chunks_needed = int(self._clip_sec_before / chunk_duration_sec)

                # Get the history chunks before the speech buffer started
                if precomputed_buffer is not None:
                    speech_chunks = len(precomputed_buffer) // len(mic_audio)
                else:
                    speech_chunks = 1

                hist_len = len(history_snapshot)
                raw_start = -(speech_chunks + pre_chunks_needed)
                raw_end = -speech_chunks if speech_chunks > 0 else None

                # Protect negative slicing indices from overrunning history buffer boundaries
                if raw_end is not None:
                    if speech_chunks >= hist_len:
                        pre_buffer_frames = []
                    else:
                        bounded_start = max(-hist_len, raw_start)
                        pre_buffer_frames = history_snapshot[bounded_start:raw_end]
                else:
                    bounded_start = max(-hist_len, raw_start)
                    pre_buffer_frames = history_snapshot[bounded_start:]

                pre_buffer = [frame[mic_id] for frame in pre_buffer_frames if mic_id in frame]

                if precomputed_buffer is not None:
                    alert.audio_clip = np.concatenate(pre_buffer + [precomputed_buffer])
                else:
                    alert.audio_clip = np.concatenate(pre_buffer + [mic_audio.copy()])

                # Defer evidence write if clip_sec_after is configured
                chunk_duration_sec = chunk.duration_ms / 1000.0
                target_post_chunks = int(self._clip_sec_after / chunk_duration_sec) if self._clip_sec_after > 0 else 0

                if target_post_chunks > 0:
                    pending_alert = _PendingAlert(
                        alert=alert,
                        audio_sequence=[alert.audio_clip.copy()],
                        target_post_chunks=target_post_chunks,
                        post_collected=0,
                    )
                    with self._lock:
                        self._pending_alerts.append(pending_alert)
                else:
                    self._async_writer.enqueue_write(
                        self._evidence_recorder.save_alert, alert
                    )

                if self._alert_queue is not None:
                    self._alert_queue.put(alert)

                if self._on_alert:
                    try:
                        self._on_alert(alert)
                    except Exception as e:
                        logger.debug(f"on_alert callback error: {e}")

                logger.warning(
                    f"AUDIO CHEATING ALERT #{self._stats['alerts_triggered']}: "
                    f"Mic {mic_id}, keywords={result.matched_keywords}, "
                    f"transcript='{result.transcript}'"
                )
        else:
            transcript_text = result.transcript.strip()
            if transcript_text:
                logger.info(
                    f"Speech transcribed but NO cheating keywords matched. "
                    f"Transcript: '{transcript_text}'"
                )
            else:
                logger.info("VAD detected speech, but Whisper found no recognizable words.")
