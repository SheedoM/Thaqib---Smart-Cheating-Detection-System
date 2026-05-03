"""
Configuration management for Thaqib.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    app_env: Literal["development", "production", "testing"] = "production"
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

    # Tracking
    tracking_max_distance: int = 100
    tracking_max_age: int = 30
    neighbor_k: int = 6               # Number of nearest neighbors per student

    # Cheating Evaluation
    risk_angle_tolerance: float = 25.0           # Max gaze-to-paper angle (degrees)
    suspicious_duration_threshold: float = 2.0   # Seconds of sustained gaze to flag
    suspicious_match_ratio: float = 0.7

    # Re-Identification
    reid_match_threshold: float = 0.80   # Cosine similarity threshold for face re-ID
    reid_similarity_debug: bool = False  # Log per-frame similarity scores

    # Performance
    face_mesh_workers: int = 4           # Max parallel face mesh worker processes
    torch_num_threads: int | None = None # PyTorch CPU threads (None = OS default)

    # Video Output
    # video_quality: 0–100. Lower = smaller files.
    #   50  → LOW  (~smallest files)
    #   75  → MED  (default — ~40% size reduction vs uncompressed)
    #   90  → HIGH (best quality)
    # alert_max_height: Alert videos are downscaled to this height (px).
    #   720  → ~720p  (recommended)
    #   1080 → ~1080p (higher quality, larger files)
    #   0    → no downscaling (full native resolution)
    video_quality: int = 75
    alert_max_height: int = 720

    # Archive Recording
    archive_mode: Literal["raw", "annotated"] = "raw"
    # raw       → original camera feed saved as-is
    # annotated → saved with bounding boxes and overlays

    @property
    def camera_source_parsed(self) -> int | str:
        """Parse camera source as int (webcam index) or str (RTSP URL / file path)."""
        try:
            return int(self.camera_source)
        except ValueError:
            return self.camera_source


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance (loaded once at startup)."""
    return Settings()
