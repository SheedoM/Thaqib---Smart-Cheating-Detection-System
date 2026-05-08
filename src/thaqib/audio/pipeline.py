"""
Audio processing pipeline orchestrator.

Coordinates all audio subsystems:
    Source → Discriminator → VAD → Whisper → Keywords → Alerts

Runs as a standalone system, independent of the video pipeline.
"""

import collections
import logging
import threading
import time
from dataclasses import dataclass
from queue import Queue

import numpy as np

from thaqib.audio.models import AudioChunk, AudioAlert
from thaqib.audio.source import AudioSource
from thaqib.audio.discriminator import GlobalLocalDiscriminator
from thaqib.audio.keyword_detector import KeywordDetector
from thaqib.audio.evidence import AudioEvidenceRecorder

logger = logging.getLogger(__name__)


@dataclass
class _PendingAlert:
    alert: AudioAlert
    audio_sequence: list[np.ndarray]
    target_post_chunks: int
    post_collected: int = 0


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
        alert_queue: Queue | None = None,
        whisper_model: str = "tiny",
        language: str = "ar",
        keywords_file: str = "keywords.json",
        silence_threshold: float = 0.01,
        global_ratio: float = 0.3,
        global_fraction: float = 0.6,
        use_cross_correlation: bool = False,
        on_alert: callable = None,
        on_chunk: callable = None,
        clip_sec_before: float = 2.0,
        clip_sec_after: float = 2.0,
    ):
        """
        Args:
            source: Audio source (FileAudioSource or LiveAudioSource).
            alert_queue: Optional queue for sending alerts to another system.
            whisper_model: Whisper model size for STT.
            language: Expected language code.
            keywords_file: Path to cheating keywords JSON file.
            silence_threshold: Discriminator silence cutoff.
            global_ratio: Discriminator "heard by mic" threshold.
            global_fraction: Discriminator "global" fraction threshold.
            use_cross_correlation: Enable cross-correlation validation.
            on_alert: Callback function called with each AudioAlert.
            on_chunk: Callback called with (AudioChunk, SoundClassification)
                      for every processed chunk (for dashboard updates).
        """
        self._source = source
        self._alert_queue = alert_queue
        self._use_cross_correlation = use_cross_correlation
        self._on_alert = on_alert
        self._on_chunk = on_chunk
        self._clip_sec_before = clip_sec_before
        self._clip_sec_after = clip_sec_after

        self._discriminator = GlobalLocalDiscriminator(
            silence_threshold=silence_threshold,
            global_ratio=global_ratio,
            global_fraction=global_fraction,
        )

        self._keyword_detector = KeywordDetector(
            model_size=whisper_model,
            language=language,
            keywords_file=keywords_file,
        )

        self._evidence_recorder = AudioEvidenceRecorder(output_dir="audio alerts")

        self._chunk_history = collections.deque(maxlen=20)
        self._pending_alerts: list[_PendingAlert] = []

        self._is_running = False
        self._thread: threading.Thread | None = None

        # Statistics for dashboard
        self._stats = {
            "chunks_processed": 0,
            "silent_chunks": 0,
            "global_chunks": 0,
            "local_chunks": 0,
            "speech_detected": 0,
            "alerts_triggered": 0,
            "start_time": 0.0,
        }
        self._alerts: list[AudioAlert] = []

    @property
    def stats(self) -> dict:
        """Processing statistics for dashboard display."""
        return self._stats.copy()

    @property
    def alerts(self) -> list[AudioAlert]:
        """List of all alerts triggered during this session."""
        return list(self._alerts)

    def start(self) -> None:
        """Start the audio pipeline in a background thread."""
        if self._is_running:
            logger.warning("Audio pipeline already running")
            return

        self._is_running = True
        self._stats["start_time"] = time.time()
        self._source.start()

        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="AudioPipeline",
        )
        self._thread.start()
        logger.info("Audio pipeline started (background thread)")

    def stop(self) -> None:
        """Stop the audio pipeline."""
        self._is_running = False
        self._source.stop()

        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None

        logger.info(
            f"Audio pipeline stopped. Stats: "
            f"{self._stats['chunks_processed']} chunks, "
            f"{self._stats['alerts_triggered']} alerts"
        )

    def run_sync(self) -> list[AudioAlert]:
        """
        Run the pipeline synchronously (blocking).

        Processes all audio from the source until exhausted.
        Returns the list of triggered alerts.
        """
        self._is_running = True
        self._stats["start_time"] = time.time()
        self._source.start()

        logger.info("Audio pipeline running (synchronous mode)")

        try:
            self._run_loop()
        finally:
            self._source.stop()

        return list(self._alerts)

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

                # 1. Provide the new chunk to any pending alerts
                completed_alerts = []
                for pending in self._pending_alerts:
                    pending.audio_sequence.append(chunk.mic_data[pending.alert.mic_id].copy())
                    pending.post_collected += 1
                    if pending.post_collected >= pending.target_post_chunks:
                        completed_alerts.append(pending)
                
                # 2. Save any completed alerts
                for completed in completed_alerts:
                    self._pending_alerts.remove(completed)
                    full_audio = np.concatenate(completed.audio_sequence)
                    completed.alert.audio_clip = full_audio
                    try:
                        self._evidence_recorder.save_alert(completed.alert)
                    except Exception as e:
                        logger.error(f"Failed to save evidence: {e}")

                # 3. Process the chunk to find NEW alerts
                self._process_chunk(chunk)

                # 4. Add to history buffer
                self._chunk_history.append(chunk)
        finally:
            # Flush any remaining pending alerts on shutdown
            for pending in self._pending_alerts:
                full_audio = np.concatenate(pending.audio_sequence)
                pending.alert.audio_clip = full_audio
                try:
                    self._evidence_recorder.save_alert(pending.alert)
                except Exception as e:
                    logger.error(f"Failed to save evidence on shutdown: {e}")
            self._pending_alerts.clear()

    def _process_chunk(self, chunk: AudioChunk) -> None:
        """Process a single audio chunk through the full pipeline."""
        self._stats["chunks_processed"] += 1

        # Step 1: Global vs Local classification
        classification = self._discriminator.classify(chunk)

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
        if classification.is_silent:
            self._stats["silent_chunks"] += 1
            return
        elif classification.is_global:
            self._stats["global_chunks"] += 1
            return
        elif classification.is_local:
            self._stats["local_chunks"] += 1

        # Step 2: Analyze speech on each active mic
        for mic_id in classification.active_mics:
            mic_audio = chunk.mic_data[mic_id]

            result = self._keyword_detector.analyze(
                mic_audio, chunk.sample_rate
            )

            if result is None:
                # Not speech — skip
                continue

            self._stats["speech_detected"] += 1

            if result.is_cheating:
                # Step 3: Create or Extend alert
                existing_pending = None
                for pending in self._pending_alerts:
                    if pending.alert.mic_id == mic_id:
                        existing_pending = pending
                        break
                
                if existing_pending:
                    # EXTEND ONGOING ALERT
                    existing_pending.post_collected = 0
                    
                    # Append new keywords
                    for kw in result.matched_keywords:
                        if kw not in existing_pending.alert.matched_keywords:
                            existing_pending.alert.matched_keywords.append(kw)
                            
                    # Append transcript
                    existing_pending.alert.transcript += " " + result.transcript
                    
                    # Update confidence (max)
                    existing_pending.alert.confidence = max(
                        existing_pending.alert.confidence, result.confidence
                    )
                    
                    logger.warning(
                        f"EXTENDED ALERT for Mic {mic_id}: "
                        f"keywords={result.matched_keywords}"
                    )
                else:
                    # CREATE NEW ALERT
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
                    )

                    self._alerts.append(alert)
                    self._stats["alerts_triggered"] += 1

                    # Calculate chunks needed for 2s before and 2s after
                    chunk_duration_sec = chunk.duration_ms / 1000.0
                    pre_chunks_needed = int(self._clip_sec_before / chunk_duration_sec)
                    post_chunks_needed = int(self._clip_sec_after / chunk_duration_sec)

                    # Extract past chunks from history
                    history_list = list(self._chunk_history)
                    pre_history = history_list[-pre_chunks_needed:] if pre_chunks_needed > 0 else []
                    pre_buffer = [c.mic_data[mic_id].copy() for c in pre_history]
                    
                    # Include current chunk
                    pre_buffer.append(mic_audio.copy())

                    # Create pending alert
                    pending = _PendingAlert(
                        alert=alert,
                        audio_sequence=pre_buffer,
                        target_post_chunks=post_chunks_needed,
                        post_collected=0
                    )
                    self._pending_alerts.append(pending)

                    # Send to external queue (for video integration)
                    if self._alert_queue is not None:
                        self._alert_queue.put(alert)

                    # Call alert callback (for dashboard)
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

                # Only process the primary (loudest) active mic per chunk
                # to avoid duplicate alerts for the same whisper
                break
            else:
                transcript_text = result.transcript.strip()
                if transcript_text:
                    logger.info(
                        f"Speech transcribed but NO cheating keywords matched. "
                        f"Transcript: '{transcript_text}'"
                    )
                else:
                    logger.info("VAD detected speech, but Whisper found no recognizable words (likely noise/cough).")
