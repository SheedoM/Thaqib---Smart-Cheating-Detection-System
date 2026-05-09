"""
Configuration management for Thaqib.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
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
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]
    internal_event_token: str | None = None
    stream_manager_enabled: bool = True

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

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        """Accept JSON arrays or comma-separated env values for CORS origins."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
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
        if "*" in self.cors_origins:
            raise ValueError("Wildcard CORS origins are not allowed in production")
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
    """Get cached settings instance (loaded once at startup)."""
    return Settings()
