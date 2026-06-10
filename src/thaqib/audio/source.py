"""
Audio source abstraction layer.

Provides a unified interface for reading audio from:
- Live microphones (real-time production mode)
- Audio files (testing/development mode)

Both modes produce identical AudioChunk objects so the rest of
the pipeline doesn't care where the audio comes from.
"""

import logging
import time
import threading
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np

from thaqib.audio.models import AudioChunk

logger = logging.getLogger(__name__)


class AudioSource(ABC):
    """Abstract base class for audio sources."""

    @abstractmethod
    def start(self) -> None:
        """Start producing audio."""

    @abstractmethod
    def get_chunk(self) -> AudioChunk | None:
        """
        Get the next synchronized audio chunk from all microphones.

        Blocks until a complete chunk is available, or returns None
        if the source is exhausted (end of file) or stopped.

        Returns:
            AudioChunk with shape (n_mics, n_samples), or None if done.
        """

    @abstractmethod
    def stop(self) -> None:
        """Stop producing audio and release resources."""

    @property
    @abstractmethod
    def num_mics(self) -> int:
        """Number of microphones / channels."""

    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """Sample rate in Hz."""


class FileAudioSource(AudioSource):
    """
    Reads audio from pre-recorded files (one file per microphone).

    Supports MP3, M4A, WAV, and any format that ffmpeg/libsndfile can decode.
    Simulates real-time playback by sleeping between chunks, or can run
    at full speed for batch processing.

    Example:
        >>> source = FileAudioSource(
        ...     file_paths=["mic1.mp3", "mic2.m4a"],
        ...     chunk_ms=500,
        ...     real_time=True,  # Simulate real-time playback speed
        ... )
        >>> source.start()
        >>> while (chunk := source.get_chunk()) is not None:
        ...     process(chunk)
        >>> source.stop()
    """

    def __init__(
        self,
        file_paths: list[str],
        sample_rate: int = 16000,
        chunk_ms: int = 500,
        real_time: bool = False,
    ):
        """
        Args:
            file_paths: One audio file per microphone.
            sample_rate: Target sample rate (files are resampled if needed).
            chunk_ms: Analysis window size in milliseconds.
            real_time: If True, sleep between chunks to simulate real-time.
        """
        self._file_paths = [Path(p) for p in file_paths]
        self._sample_rate = sample_rate
        self._chunk_ms = chunk_ms
        self._real_time = real_time

        self._audio_data: list[np.ndarray] = []  # Per-mic audio arrays
        self._position: int = 0  # Current read position (in samples)
        self._chunk_samples = int(sample_rate * chunk_ms / 1000)
        self._chunk_index: int = 0
        self._is_running = False

    def start(self) -> None:
        """Load and resample all audio files."""
        self._audio_data = []
        for path in self._file_paths:
            if not path.exists():
                raise FileNotFoundError(f"Audio file not found: {path}")

            logger.info(f"Loading audio file: {path}")
            audio = self._load_audio_file(path, self._sample_rate)
            self._audio_data.append(audio)
            logger.info(
                f"  Loaded: {len(audio)} samples, {len(audio)/self._sample_rate:.1f}s "
                f"at {self._sample_rate}Hz"
            )

        # Trim all files to the shortest duration for synchronization
        min_len = min(len(a) for a in self._audio_data)
        self._audio_data = [a[:min_len] for a in self._audio_data]
        logger.info(
            f"Audio source ready: {len(self._audio_data)} mics, "
            f"{min_len/self._sample_rate:.1f}s duration, "
            f"{self._chunk_ms}ms chunks"
        )

        self._position = 0
        self._chunk_index = 0
        self._is_running = True
        self._start_time = time.time()

    @staticmethod
    def _load_audio_file(path, sample_rate: int = 16000) -> "np.ndarray":
        """
        Load an audio file using pydub (primary) or librosa (fallback).
        """
        import os
        import numpy as np

        # Add the ffmpeg-downloader bin path to the environment PATH so pydub can find it
        ffmpeg_bin = os.path.expanduser(r"~\AppData\Local\ffmpegio\ffmpeg-downloader\ffmpeg\bin")
        if os.path.exists(ffmpeg_bin) and ffmpeg_bin not in os.environ.get("PATH", ""):
            os.environ["PATH"] += os.pathsep + ffmpeg_bin

        pydub_error_msg = None

        # ── Try pydub first (best MP3/M4A support) ──────────────────────
        try:
            from pydub import AudioSegment

            seg = AudioSegment.from_file(str(path))
            # Convert to mono, resample
            seg = seg.set_channels(1).set_frame_rate(sample_rate)
            samples = np.array(seg.get_array_of_samples(), dtype=np.float32)
            # Normalize to [-1, 1]
            max_val = float(2 ** (seg.sample_width * 8 - 1))
            samples = samples / max_val
            return samples

        except Exception as e:
            pydub_error_msg = str(e)
            logger.debug(f"pydub failed ({e}), trying librosa...")

        # ── Fallback: librosa ────────────────────────────────────────────
        try:
            import librosa
            audio, _ = librosa.load(str(path), sr=sample_rate, mono=True)
            return audio

        except Exception as librosa_err:
            raise RuntimeError(
                f"Could not load audio file: {path}\n"
                f"pydub error:   {pydub_error_msg}\n"
                f"librosa error: {librosa_err}\n\n"
                "Make sure ffmpeg is installed and accessible."
            ) from librosa_err

    def get_chunk(self) -> AudioChunk | None:
        """Read the next chunk from all files."""
        if not self._is_running:
            return None

        end = self._position + self._chunk_samples
        max_len = len(self._audio_data[0])

        if self._position >= max_len:
            logger.info("Audio files exhausted — no more chunks")
            return None

        # Extract chunk from each mic
        mic_chunks = []
        for mic_audio in self._audio_data:
            if end <= max_len:
                chunk = mic_audio[self._position:end]
            else:
                # Pad last chunk with silence if needed
                chunk = np.zeros(self._chunk_samples, dtype=np.float32)
                remaining = mic_audio[self._position:]
                chunk[:len(remaining)] = remaining
            mic_chunks.append(chunk)

        # Stack into (n_mics, n_samples)
        mic_data = np.stack(mic_chunks, axis=0)

        audio_chunk = AudioChunk(
            timestamp=time.time(),
            mic_data=mic_data,
            sample_rate=self._sample_rate,
            duration_ms=self._chunk_ms,
            chunk_index=self._chunk_index,
        )

        self._position = end
        self._chunk_index += 1

        # Simulate real-time playback speed without cumulative drift
        if self._real_time:
            expected_time = self._start_time + (self._chunk_index * self._chunk_ms / 1000.0)
            now = time.time()
            if expected_time > now:
                time.sleep(expected_time - now)

        return audio_chunk

    def stop(self) -> None:
        """Release loaded audio data."""
        self._is_running = False
        self._audio_data = []
        logger.info("File audio source stopped")

    @property
    def num_mics(self) -> int:
        return len(self._file_paths)

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def total_duration_s(self) -> float:
        """Total duration of loaded audio in seconds."""
        if not self._audio_data:
            return 0.0
        return len(self._audio_data[0]) / self._sample_rate

    @property
    def progress(self) -> float:
        """Current playback progress (0.0 to 1.0)."""
        if not self._audio_data:
            return 0.0
        return min(1.0, self._position / len(self._audio_data[0]))


class LiveAudioSource(AudioSource):
    """
    Captures audio from live microphones in real-time.

    Supports multiple connection methods:
    - Multiple USB microphones (each a separate OS audio device)
    - Multi-channel audio interface (one device, N input channels)

    Example:
        >>> source = LiveAudioSource(
        ...     device_ids=[1, 3],       # Two USB mics
        ...     chunk_ms=500,
        ... )
        >>> source.start()
        >>> chunk = source.get_chunk()  # Blocks until 500ms of audio ready
    """

    def __init__(
        self,
        device_ids: list[int] | None = None,
        multi_channel_device: int | None = None,
        channels: int = 1,
        sample_rate: int = 16000,
        chunk_ms: int = 500,
    ):
        """
        Args:
            device_ids: List of OS audio device indices (one per mic).
                        Use this for multiple separate USB mics.
            multi_channel_device: Single device index for a multi-channel
                                  audio interface. Use this for devices like
                                  Behringer UMC1820 with multiple inputs.
            channels: Number of input channels (only used with multi_channel_device).
            sample_rate: Capture sample rate in Hz.
            chunk_ms: Analysis window size in milliseconds.
        """
        try:
            import sounddevice  # noqa: F401
        except ImportError:
            raise ImportError(
                "sounddevice is required for live audio capture. "
                "Install with: pip install sounddevice"
            )

        if device_ids and multi_channel_device is not None:
            raise ValueError("Specify either device_ids OR multi_channel_device, not both")
        if not device_ids and multi_channel_device is None:
            raise ValueError("Must specify device_ids or multi_channel_device")

        self._device_ids = device_ids
        self._multi_channel_device = multi_channel_device
        self._channels = channels if multi_channel_device is not None else 1
        self._sample_rate = sample_rate
        self._chunk_ms = chunk_ms
        self._chunk_samples = int(sample_rate * chunk_ms / 1000)
        self._chunk_index = 0
        self._is_running = False

        # Per-mic chunk queue: audio callback fills, get_chunk() drains.
        # Max 8 queued chunks per mic (~4 seconds at 500ms chunks).
        # Oldest chunk is dropped with a warning if the queue fills.
        self._chunk_queues: list["queue.Queue"] = []
        self._streams = []

    def start(self) -> None:
        """Start audio capture from all microphones."""
        import queue as _queue
        import sounddevice as sd

        self._is_running = True
        n_mics = len(self._device_ids) if self._device_ids else self._channels
        # One Queue per mic; 8 slots = ~4 seconds of buffer at 500ms chunks
        self._chunk_queues = [_queue.Queue(maxsize=8) for _ in range(n_mics)]
        self._streams = []

        def _push_samples(mic_idx: int, samples: np.ndarray, local_accum: list[np.ndarray]) -> None:
            """Accumulate samples; push complete chunks to the queue."""
            local_accum.append(samples.copy())
            
            # Count total samples
            total_samples = sum(len(arr) for arr in local_accum)
            while total_samples >= self._chunk_samples:
                # Concatenate all accumulated arrays
                all_samples = np.concatenate(local_accum)
                
                # Extract one full chunk
                chunk_arr = all_samples[:self._chunk_samples]
                
                # Keep the remainder
                remainder = all_samples[self._chunk_samples:]
                local_accum.clear()
                if len(remainder) > 0:
                    local_accum.append(remainder)
                
                total_samples = len(remainder)
                
                q = self._chunk_queues[mic_idx]
                if q.full():
                    # Drop the oldest chunk to make room (log once per drop)
                    try:
                        q.get_nowait()
                        logger.warning(
                            f"Mic {mic_idx}: chunk queue full — oldest chunk dropped. "
                            f"Pipeline is too slow to keep up with audio."
                        )
                    except _queue.Empty:
                        pass
                q.put_nowait(chunk_arr)

        if self._device_ids:
            # Mode: Multiple separate USB mics
            for i, dev_id in enumerate(self._device_ids):
                accum: list[np.ndarray] = []  # per-mic accumulator (closure)

                def make_callback(mic_idx: int, buf: list):
                    def callback(indata, frames, time_info, status):
                        if status:
                            logger.warning(f"Mic {mic_idx} capture status: {status}")
                        _push_samples(mic_idx, indata[:, 0], buf)
                    return callback

                stream = sd.InputStream(
                    device=dev_id,
                    channels=1,
                    samplerate=self._sample_rate,
                    blocksize=self._chunk_samples // 4,
                    callback=make_callback(i, accum),
                )
                stream.start()
                self._streams.append(stream)
                logger.info(f"Mic {i} (device {dev_id}): capture started")

        elif self._multi_channel_device is not None:
            # Mode: Multi-channel audio interface
            # Each channel gets its own accumulator
            accums: list[list[np.ndarray]] = [[] for _ in range(self._channels)]

            def multi_callback(indata, frames, time_info, status):
                if status:
                    logger.warning(f"Multi-channel capture status: {status}")
                for ch in range(min(indata.shape[1], self._channels)):
                    _push_samples(ch, indata[:, ch], accums[ch])

            stream = sd.InputStream(
                device=self._multi_channel_device,
                channels=self._channels,
                samplerate=self._sample_rate,
                blocksize=self._chunk_samples // 4,
                callback=multi_callback,
            )
            stream.start()
            self._streams.append(stream)
            logger.info(
                f"Multi-channel device {self._multi_channel_device}: "
                f"{self._channels} channels, capture started"
            )

        logger.info(f"Live audio source ready: {self.num_mics} mics, {self._sample_rate}Hz")

    def get_chunk(self) -> AudioChunk | None:
        """
        Block until a synchronized chunk is available from ALL mics.

        Uses Queue.get() with timeout to poll chunk queues.
        If a microphone fails to produce audio within a small window,
        it is dynamically masked and padded with zero-filled silence
        to prevent blocking the entire pipeline.
        """
        import queue as _queue

        if not self._is_running:
            return None

        # Track consecutive timeouts per mic for dead-mic detection
        if not hasattr(self, '_timeout_counts'):
            self._timeout_counts = [0] * len(self._chunk_queues)
            self._active_mics_mask = [True] * len(self._chunk_queues)

        mic_chunks = []
        for i, q in enumerate(self._chunk_queues):
            # If microphone is marked dead/inactive, immediately yield zero silence chunk
            if not self._active_mics_mask[i]:
                silence_chunk = np.zeros(self._chunk_samples, dtype=np.float32)
                mic_chunks.append(silence_chunk)
                continue

            while True:
                if not self._is_running:
                    return None
                try:
                    # Poll queue with a fast timeout (e.g. 50ms) to detect failure quickly
                    chunk = q.get(timeout=0.05)
                    self._timeout_counts[i] = 0  # reset on success
                    mic_chunks.append(chunk)
                    break
                except _queue.Empty:
                    self._timeout_counts[i] += 1
                    
                    # 100 consecutive 50ms timeouts = 5 seconds of silence/missing chunks
                    if self._timeout_counts[i] >= 100:
                        logger.critical(
                            f"HARDWARE FAILURE: Mic {i} has disconnected or failed! "
                            f"Pruning/masking from active wait loop and using zero silence padding."
                        )
                        self._active_mics_mask[i] = False
                        silence_chunk = np.zeros(self._chunk_samples, dtype=np.float32)
                        mic_chunks.append(silence_chunk)
                        break
                    
                    # Small yield to prevent CPU spinning in while loop
                    time.sleep(0.001)
                    continue

        mic_data = np.stack(mic_chunks, axis=0)  # (n_mics, chunk_samples)

        audio_chunk = AudioChunk(
            timestamp=time.time(),
            mic_data=mic_data,
            sample_rate=self._sample_rate,
            duration_ms=self._chunk_ms,
            chunk_index=self._chunk_index,
        )
        self._chunk_index += 1
        return audio_chunk


    def stop(self) -> None:
        """Stop all capture streams."""
        self._is_running = False
        for stream in self._streams:
            try:
                stream.stop()
                stream.close()
            except Exception as e:
                logger.warning(f"Error closing audio stream: {e}")
        self._streams.clear()
        logger.info("Live audio source stopped")

    @property
    def num_mics(self) -> int:
        if self._device_ids:
            return len(self._device_ids)
        return self._channels

    @property
    def sample_rate(self) -> int:
        return self._sample_rate
