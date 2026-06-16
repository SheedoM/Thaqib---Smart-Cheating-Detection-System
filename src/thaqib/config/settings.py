"""
Configuration management for Thaqib.
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Thaqib"
    app_env: Literal["development", "production", "testing"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    # Camera
    camera_source: str = "0"  # Webcam index, RTSP URL, or video file path
    camera_width: int = 1280
    camera_height: int = 720
    camera_fps: int = 30

    # Detection
    detection_interval: float = 1.0   # Seconds between full YOLO detection runs
    yolo_model: str = "models/yolo11m.pt"
    detection_confidence: float = 0.15
    tools_target_labels: list[str] = ["document"]  # Classes treated as papers
    tools_model: str = "models/best.pt"
    tools_confidence: float = 0.45    # Confidence threshold for paper/phone detection
    detection_imgsz: int = 640        # YOLO inference resolution (640=fast, 1280=accurate)
    # Phone detection via YOLO
    # When True, the main YOLO model (yolo_model) is used to detect phones
    # using the COCO class specified by phone_class_id (default 67 = cell phone).
    # This is more reliable than relying on best.pt label names.
    # Set to False to fall back to the tools model (best.pt) phone detection only.
    yolo_phone_detection: bool = True
    phone_class_id: int = 67          # COCO class ID for 'cell phone'
    phone_confidence: float = 0.30    # Confidence threshold for phone detection (lower than person)
    # Dedicated phone detection model.
    # Leave empty ("") to reuse yolo_model for phone detection (default, zero extra cost).
    # Set a path to load a separate model e.g. "models/phone_yolo11n.pt"
    phone_model: str = ""             # e.g. "models/phone_yolo11n.pt"

    # Tracking
    tracking_max_distance: int = 100
    tracking_max_age: int = 30
    neighbor_k: int = 6               # Number of nearest neighbors per student

    # Cheating Evaluation
    risk_angle_tolerance: float = 25.0           # Max gaze-to-paper angle (degrees)
    suspicious_duration_threshold: float = 2.0   # Seconds of sustained gaze to flag

    # Re-Identification
    reid_match_threshold: float = 0.80   # Cosine similarity threshold for face re-ID
    reid_similarity_debug: bool = False  # Log per-frame similarity scores
    reid_weights_path: str = "models/osnet_x0_25_msmt17.pt"  # OSNet Re-ID weights

    # Performance
    face_mesh_workers: int = 4           # Max parallel face mesh worker processes
    torch_num_threads: int | None = None # PyTorch CPU threads (None = OS default)

    # Data Storage
    data_dir: Path = Field(default=Path("./data"))
    enable_logging: bool = True
    log_format: Literal["csv", "parquet", "json"] = "csv"

    # Server
    server_host: str = "0.0.0.0"
    server_port: int = 8000

    # Database
    database_url: str = "sqlite:///./data/thaqib.db"
    database_echo: bool = False

    # WebSocket
    ws_heartbeat_interval: int = 30
    
    # Security
    secret_key: str = "dev-only-change-me-before-production-please"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    access_cookie_name: str = "thaqib_access_token"
    refresh_cookie_name: str = "thaqib_refresh_token"
    csrf_cookie_name: str = "thaqib_csrf_token"
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]
    internal_event_token: str | None = None
    setup_bootstrap_token: str | None = None
    setup_private_network_only: bool = True
    stream_manager_enabled: bool = True
    av_fusion_enabled: bool = True

    # Video Output
    # video_quality: 0-100. Lower = smaller files.
    #   50  -> LOW  (~smallest files)
    #   75  -> MED  (default -- ~40% size reduction vs uncompressed)
    #   90  -> HIGH (best quality)
    # alert_max_height: Alert videos are downscaled to this height (px).
    #   720  -> ~720p  (recommended)
    #   1080 -> ~1080p (higher quality, larger files)
    #   0    -> no downscaling (full native resolution)
    video_quality: int = 75
    alert_max_height: int = 720

    # Archive Recording
    archive_mode: Literal["raw", "annotated"] = "raw"
    # raw       -> original camera feed saved as-is
    # annotated -> saved with bounding boxes and overlays
    archive_dir: str = "archive"  # Directory for continuous archive recordings
    alerts_dir: str = "alerts"    # Directory for cheating/phone alert clips

    # =========================================================================
    # Diagnostic Video Logging
    # =========================================================================
    # Master switch — set to False to disable file logging entirely.
    video_log_enabled: bool = True

    # Verbosity level written to the log file.
    #   DEBUG   -> every frame: timings, all track states, gaze dot products
    #   INFO    -> events only: detection results, alert start/save, selections
    #   WARNING -> alerts only: phone detected, cheating detected, cap hits
    video_log_level: str = "DEBUG"

    # Directory where video_YYYYMMDD_HHMMSS.log files are written.
    video_log_dir: str = "logs"

    # Maximum log file size in bytes before rotation (default: 100 MB).
    # After rotation up to 5 backup files are kept.
    video_log_max_bytes: int = 100 * 1024 * 1024

    # =========================================================================
    # Audio Detection
    # =========================================================================

    # STT engine: Whisper model size ('tiny', 'base', 'small', 'medium').
    #   tiny   -> fastest (~0.3-0.8s/chunk via faster-whisper), least accurate.
    #   small  -> good accuracy for Arabic, ~2-4s/chunk on CPU.
    audio_whisper_model: str = "tiny"

    # BCP-47 language code passed to Whisper for transcription.
    audio_language: str = "ar"

    # Path to JSON file containing cheating keywords and fuzzy threshold.
    audio_keywords_file: str = "keywords.json"

    # Directory where WAV + JSON evidence files are saved.
    audio_output_dir: str = "audio alerts"

    # Human-readable labels for each microphone, comma-separated.
    # Index 0 = first mic, index 1 = second mic, etc.
    # Used in log messages, WAV filenames, and JSON metadata.
    # Examples:
    #   "front,back"          → front_mic, back_mic
    #   "امامي,خلفي"          → Arabic labels
    #   ""                    → default: mic0, mic1, mic2, ...
    audio_mic_names: str = ""

    # Sample rate in Hz. Silero VAD and Whisper both require 16000 Hz.
    audio_sample_rate: int = 16000

    # Analysis window size in milliseconds. Larger = fewer inference calls
    # but higher latency before a LOCAL chunk is detected.
    audio_chunk_ms: int = 500

    # RMS energy below this value is considered silence (0.0-1.0 normalized).
    audio_silence_threshold: float = 0.01

    # Fraction of the loudest mic's energy a mic must exceed to count as
    # "having heard" a sound in the N-mic global/local discriminator.
    audio_global_ratio: float = 0.3

    # If this fraction of microphones heard the sound, classify as GLOBAL
    # (not cheating). With exactly 2 mics, the 2:1 energy ratio rule is
    # used instead of this threshold.
    audio_global_fraction: float = 0.6

    # Voice activity detection confidence threshold (0.0-1.0).
    # Silero VAD must score above this to classify a 32ms window as speech.
    audio_vad_threshold: float = 0.5

    # Seconds of VAD-confirmed speech to accumulate before calling Whisper.
    # Higher values improve transcription accuracy but add latency.
    audio_speech_buffer_sec: float = 2.5

    # Non-speech chunks tolerated before clearing the speech buffer.
    # Allows brief pauses mid-sentence without losing accumulated audio.
    audio_speech_gap_max: int = 2

    # If True, ANY detected speech triggers a cheating alert (silent exam mode).
    # If False, only speech containing a keyword from keywords_file is flagged
    # (keyword mode, suitable for supervised oral exams).
    audio_strict_mode: bool = True

    # Enable cross-correlation validation for LOCAL chunk classification.
    # Catches soft global sounds misclassified as local; slower (~O(n^2)).
    audio_cross_correlation: bool = False

    # Seconds of audio history to include BEFORE the cheating event in
    # the evidence WAV clip (pre-event buffer).
    audio_clip_sec_before: float = 2.0

    # Seconds of audio to record AFTER the cheating event ends (post-buffer).
    audio_clip_sec_after: float = 2.0

    # Rolling chunk history buffer depth. At 500ms chunks, 20 = 10 seconds
    # of pre-event audio available for evidence clips.
    audio_history_chunks: int = 20

    # Maximum LOCAL chunks that can wait in the inference queue.
    # Max LOCAL chunks queued for inference. Excess are dropped with a warning log.
    audio_inference_queue_size: int = 10

    # Number of non-silent chunks at session start used to learn the
    # structural energy imbalance between microphone positions.
    # (2-mic mode only).  Set to 0 to disable calibration.
    # At 500ms chunks: 30 = 15 seconds of calibration time.
    audio_calibration_chunks: int = 30

    # In 2-mic mode, a chunk is LOCAL when:
    #   (raw_ratio / baseline_ratio) >= audio_local_ratio_multiplier
    # Default 2.0 = the imbalance must be 2x worse than the calibrated normal.
    audio_local_ratio_multiplier: float = 2.0

    # Seconds between automatic baseline recalibrations during a live session.
    # The discriminator re-learns the baseline every N seconds to adapt to
    # changing room acoustics (people moving, HVAC changes, etc.).
    # 0 = recalibrate only once at the start (no periodic updates).
    audio_recalibration_interval_sec: float = 300.0

    # If True, record ALL incoming audio (every mic) to WAV files for the
    # entire exam session.  Files are saved under audio_sessions_dir.
    # Enables post-exam forensic review and offline re-analysis.
    audio_session_recording: bool = True

    # Directory where session WAV files are stored.
    # Each session creates a timestamped sub-folder: session_YYYY-MM-DD_HH-MM-SS/
    audio_sessions_dir: str = "sessions"

    # Whisper decoding beam size.
    # beam_size=1  → greedy (fastest, default, ~same accuracy for short clips)
    # beam_size=5  → beam search (more accurate, ~2x slower per transcription)
    # Only increase this if you observe many transcription errors.
    audio_whisper_beam_size: int = 1

    # Compute device for Whisper inference.
    # "auto"  → detect CUDA automatically; fall back to CPU if unavailable
    # "cuda"  → force GPU (crashes if no CUDA-capable device is present)
    # "cpu"   → force CPU
    audio_device: str = "auto"

    # Compute precision for Whisper.
    # "auto"       → float16 on GPU, int8 on CPU  (recommended)
    # "float16"    → GPU only, fastest + best quality
    # "int8_float16" → GPU, slightly less accurate but lower VRAM
    # "int8"       → CPU only
    # "float32"    → CPU, highest accuracy, slowest
    audio_compute_type: str = "auto"

    # =========================================================================
    # AUDIO PREPROCESSOR
    # =========================================================================

    # High-pass filter cutoff frequency in Hz.
    # Removes sub-bass rumble (HVAC, AC, desk vibrations).
    # 100 Hz is safe for speech — human voice starts at ~85 Hz.
    # Set to 0 to disable.
    audio_hpf_cutoff: int = 100

    # Enable spectral noise reduction using a learned room noise profile.
    # The system learns the noise floor automatically from ambient (non-speech)
    # frames during the first few minutes of the exam.
    # Requires: pip install noisereduce scipy
    audio_noise_reduction: bool = True

    # Noise reduction aggressiveness (0.0 – 1.0).
    # 0.75 = reduce noise energy by 75%.  Higher = cleaner but may clip soft speech.
    audio_noise_reduction_strength: float = 0.75

    # Normalize each chunk's RMS to a consistent level before VAD and Whisper.
    # Compensates for microphones with different sensitivities / distances.
    audio_adaptive_gain: bool = True

    # =========================================================================
    # ADAPTIVE VAD THRESHOLD
    # =========================================================================

    # Automatically adapt the VAD speech/noise threshold to the room's noise
    # floor.  The system measures VAD confidence on non-speech frames and sets
    # the threshold 2σ above the noise floor (range: 0.10 – 0.70).
    # Disable only if you want a fixed threshold (set audio_vad_threshold below).
    audio_adaptive_vad: bool = True

    # Number of non-speech chunks used per calibration cycle.
    # At 500ms chunks: 50 = 25 seconds of noise observation before first update.
    audio_vad_calibration_chunks: int = 50

    # Acoustic context window size in milliseconds to prepend to VAD chunks.
    # Enables temporal continuity for the Silero VAD recurrent neural network.
    # 0 = disabled. Recommended: 150-250 ms.
    audio_vad_context_ms: int = 200

    # =========================================================================
    # SUSTAINED CHEAT EPISODE DETECTION
    # =========================================================================

    # Enable sustained episode recording.
    # When True, the pipeline tracks continuous cheating and saves the FULL
    # episode audio (from first to last alert) as one WAV file.
    audio_episode_recording: bool = True

    # Minimum sustained cheating duration (seconds) to confirm a cheater.
    # Cheating shorter than this is treated as a fluke / noise event.
    # Example: 3.0 = the student must cheat for at least 3 seconds.
    audio_episode_min_sec: float = 3.0

    # Grace period (seconds) after the LAST alert before closing the episode.
    # The system waits this long to make sure the cheating has truly stopped
    # before saving the full audio clip.
    # Example: 5.0 = if no new cheating for 5 seconds → episode is over, save it.
    audio_episode_grace_sec: float = 5.0

    # =========================================================================
    # VAD-ONLY DETECTION MODE
    # =========================================================================

    # When True: skip Whisper entirely.
    # As soon as Silero VAD confirms human speech on a LOCAL chunk → ALERT.
    # This is the fastest possible detection path (~5ms per chunk vs ~4s Whisper).
    # No transcription is produced — evidence JSON will have transcript="".
    # Recommended for SILENT EXAMS where ANY speech is a violation.
    # Combine with AUDIO_STRICT_MODE=true (has no effect if strict_mode=false
    # since keyword mode requires a transcript to match against).
    audio_vad_only: bool = False

    # Cooldown in seconds between alerts for the same microphone in VAD-only mode.
    # Prevents hundreds of alerts for a single continuous whisper.
    # Example: 3.0 = after one alert, wait 3 seconds before firing another on
    # the same mic (the EpisodeTracker will group them into one episode anyway).
    audio_vad_alert_cooldown: float = 3.0

    # =========================================================================
    # VOICE SIMILARITY & TRANSIENT & EPISODE OPTIONS
    # =========================================================================

    # VAD-only Voice Content Matching similarity threshold.
    # If the spectral similarity between dominant and another mic is >= this,
    # it is considered the same sound source (GLOBAL).
    audio_voice_similarity_threshold: float = 0.80

    # VAD-only Voice Content Matching minimum VAD confidence.
    # The other mic must have at least this VAD confidence to trigger similarity check.
    audio_voice_min_confidence: float = 0.15

    # Enable transient suppression to filter pen clicks, paper shuffling.
    audio_transient_suppression: bool = True

    # High-frequency energy ratio threshold to classify a sound as a transient.
    audio_transient_threshold: float = 0.65

    # Attenuation factor for high frequency bins when a transient is detected.
    audio_transient_damping: float = 0.15

    # Use processed (denoised) audio instead of raw audio for cheat episodes.
    audio_episode_use_processed: bool = False

    # =========================================================================

    @property
    def mic_registry(self) -> dict[int, str]:
        """Parse audio_mic_names into a dict[mic_index, label].

        Supports three formats in AUDIO_MIC_NAMES:

        1. Comma-separated list (index = order):
               front,back
               192.168.1.10,192.168.1.11,192.168.1.12

        2. JSON array (index = order):
               ["192.168.1.10","192.168.1.11"]

        3. JSON object (explicit mapping, any index):
               {"0":"192.168.1.10","5":"door_cam","12":"192.168.1.25"}

        Falls back to empty dict → labels become 'mic0', 'mic1', ...
        """
        raw = (self.audio_mic_names or "").strip()
        if not raw:
            return {}

        # Try JSON first
        if raw.startswith("{") or raw.startswith("["):
            try:
                import json as _json
                parsed = _json.loads(raw)
                if isinstance(parsed, list):
                    return {i: str(v) for i, v in enumerate(parsed)}
                if isinstance(parsed, dict):
                    return {int(k): str(v) for k, v in parsed.items()}
            except Exception:
                pass  # fall through to comma-separated

        # Comma-separated list
        names = [n.strip() for n in raw.split(",") if n.strip()]
        return {i: name for i, name in enumerate(names)}

    def mic_label(self, mic_id: int) -> str:
        """Return the human-readable label for a mic (IP, name, or 'mic{id}')."""
        return self.mic_registry.get(mic_id, f"mic{mic_id}")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        """Accept JSON arrays or comma-separated env values for CORS origins."""
        if isinstance(value, str):
            raw = value.strip()
            if raw.startswith("["):
                try:
                    import json
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in raw.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def enforce_production_security(self) -> "Settings":
        """Reject known-unsafe production settings at startup."""
        if self.app_env != "production":
            return self

        if self.debug:
            raise ValueError("debug must be false in production")
        if (
            not self.secret_key
            or self.secret_key == "dev-only-change-me-before-production-please"
            or len(self.secret_key) < 32
        ):
            raise ValueError("SECRET_KEY must be a strong non-default value in production")
        if not self.internal_event_token or len(self.internal_event_token) < 24:
            raise ValueError("INTERNAL_EVENT_TOKEN must be configured in production")
        if not self.cookie_secure:
            raise ValueError("COOKIE_SECURE must be true in production")
        if "*" in self.cors_origins:
            raise ValueError("Wildcard CORS origins are not allowed in production")
        if self.database_url.strip().lower().startswith("sqlite"):
            raise ValueError("SQLite is not allowed in production")
        if not self.setup_bootstrap_token or len(self.setup_bootstrap_token) < 24:
            raise ValueError("SETUP_BOOTSTRAP_TOKEN must be configured in production")
        if self.cookie_samesite == "none" and not self.cookie_secure:
            raise ValueError("SameSite=None cookies must also be Secure")
        return self

    @property
    def camera_source_parsed(self) -> int | str:
        """Parse camera source as int (webcam index) or str (RTSP URL / file path)."""
        try:
            return int(self.camera_source)
        except ValueError:
            return self.camera_source


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance (loaded once at startup from .env)."""
    return Settings()
