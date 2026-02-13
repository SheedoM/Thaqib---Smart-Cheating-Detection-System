"""
Configuration management for Thaqib.

Loads settings from environment variables and .env file.
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
    yolo_model: str = "yolov8s"
    detection_confidence: float = 0.5

    # Tracking
    tracking_max_distance: int = 100
    tracking_max_age: int = 30

    # Neighbor Modeling
    neighbor_distance_threshold: int = 200
    neighbor_k: int = 4

    # Head Pose
    head_pose_model: Literal["mediapipe", "6drepnet"] = "mediapipe"

    # Risk Detection
    risk_angle_tolerance: float = 15.0  # Degrees
    suspicious_duration_threshold: float = 2.0  # Seconds
    suspicious_match_ratio: float = 0.7

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
