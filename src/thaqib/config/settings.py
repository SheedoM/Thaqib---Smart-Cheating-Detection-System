"""
Configuration management for Thaqib.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Thaqib"
    app_env: Literal["development", "production", "testing"] = "development"
    debug: bool = True
    log_level: str = "INFO"

    # Camera
    camera_source: str = "0"  # Webcam index or RTSP URL
    camera_width: int = 1280
    camera_height: int = 720
    camera_fps: int = 30

    # Detection
    detection_interval: float = 1.0  # Seconds between full detection runs
    yolo_model: str = "models/yolo11m.pt"
    detection_confidence: float = 0.15
    tools_target_labels: list[str] = ["document"]  # Classes from best.pt paper-detector model
    tools_model: str = "models/best.pt"  # Custom paper-detection model (class: 'document')
    tools_confidence: float = 0.45  # Confidence threshold for paper/tool detection
    detection_imgsz: int = 640  # YOLO inference resolution (640 for speed, 1280 for accuracy)

    # Tracking
    tracking_max_distance: int = 100
    tracking_max_age: int = 30
    neighbor_k: int = 6  # Number of nearest neighbors per student

    # Risk Detection
    risk_angle_tolerance: float = 25.0  # Degrees (accounts for MediaPipe + iris detection noise)
    suspicious_duration_threshold: float = 2.0  # Seconds
    suspicious_match_ratio: float = 0.7

    # Re-Identification
    reid_match_threshold: float = 0.80  # Cosine similarity threshold for face re-ID
    reid_similarity_debug: bool = False  # Log per-frame similarity scores for threshold tuning

    # Performance
    face_mesh_workers: int = 4  # Max parallel face mesh threads
    torch_num_threads: int | None = None  # PyTorch CPU threads (None = use default)

    # Data Storage
    data_dir: Path = Field(default=Path("./data"))
    enable_logging: bool = True
    log_format: Literal["csv", "parquet"] = "csv"

    # Server
    server_host: str = "0.0.0.0"
    server_port: int = 8000

    # Database
    database_url: str = "sqlite:///./data/thaqib.db"

    # WebSocket
    ws_heartbeat_interval: int = 30
    
    # Security
    secret_key: str = "super_secret_temporary_key_for_dev_only"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Archive Recording
    archive_mode: Literal["raw", "annotated"] = "raw"  # raw = original video, annotated = with overlays

    @property
    def camera_source_parsed(self) -> int | str:
        """Parse camera source as int (webcam) or str (RTSP URL)."""
        try:
            return int(self.camera_source)
        except ValueError:
            return self.camera_source


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
