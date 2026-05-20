"""
System-wide runtime settings API.

Settings are persisted to data/system_settings.json so they survive server
restarts without requiring a DB migration or .env edits.
Admins can edit them live via the Settings UI.
"""
from pathlib import Path
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.thaqib.api.dependencies import RequireRole

router = APIRouter()
require_admin = RequireRole(["admin"])

SETTINGS_FILE = Path("data/system_settings.json")
SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)


# ── Schema ────────────────────────────────────────────────────────────────────

class SystemSettings(BaseModel):
    # Video & Archive
    video_quality: int = Field(75, ge=0, le=100,
        description="Quality for saved alert video files (0–100)")
    alert_max_height: int = Field(720, ge=0, le=2160,
        description="Max height (px) for alert video clips. 0 = no downscaling")
    archive_mode: str = Field("raw",
        description="'raw' = clean footage, 'annotated' = with bounding boxes/overlays")

    # Detection
    detection_interval: float = Field(1.0, ge=0.1, le=10.0,
        description="Seconds between full YOLO detection runs")
    detection_confidence: float = Field(0.15, ge=0.01, le=1.0,
        description="Minimum YOLO confidence for person detection")
    detection_imgsz: int = Field(640,
        description="YOLO inference resolution (640 = fast, 1280 = accurate)")
    tools_confidence: float = Field(0.45, ge=0.01, le=1.0,
        description="Confidence threshold for phone/paper detection")
    object_detection_enabled: bool = Field(True,
        description="Enable detection of forbidden objects (phones, papers)")

    # Tracking
    tracking_max_distance: int = Field(100, ge=10, le=500,
        description="Max pixel distance to match a detection to an existing track")
    tracking_max_age: int = Field(30, ge=5, le=300,
        description="Frames before dropping a lost track")
    neighbor_k: int = Field(6, ge=2, le=20,
        description="Number of nearest neighbours each student is compared against")

    # Cheating evaluation
    gaze_sensitivity: int = Field(70, ge=10, le=100,
        description="UI shorthand — maps to risk_angle_tolerance (inverse)")
    risk_angle_tolerance: float = Field(25.0, ge=5.0, le=60.0,
        description="Max angle (°) between gaze and paper direction to flag as cheating")
    suspicious_duration_threshold: float = Field(2.0, ge=0.5, le=30.0,
        description="Seconds a student must look at a neighbour's paper before flagging")
    suspicious_match_ratio: float = Field(0.7, ge=0.1, le=1.0,
        description="Fraction of consecutive frames that must show suspicious gaze")

    # Audio
    audio_sensitivity: int = Field(65, ge=10, le=100,
        description="UI shorthand for audio detection sensitivity")
    alert_cooldown_seconds: int = Field(30, ge=5, le=120,
        description="Seconds between repeated alerts for the same seat")

    # Re-identification
    reid_match_threshold: float = Field(0.80, ge=0.5, le=1.0,
        description="Cosine similarity threshold for re-identifying students (0–1)")

    # Performance
    face_mesh_workers: int = Field(4, ge=1, le=16,
        description="Parallel MediaPipe workers for face mesh extraction")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load() -> SystemSettings:
    """Load settings from JSON file, falling back to defaults."""
    if SETTINGS_FILE.exists():
        try:
            import json
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            return SystemSettings(**data)
        except Exception:
            pass
    return SystemSettings()


def _save(settings: SystemSettings) -> None:
    import json
    SETTINGS_FILE.write_text(
        settings.model_dump_json(indent=2),
        encoding="utf-8"
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=SystemSettings)
def get_settings(_ = Depends(require_admin)) -> Any:
    """Return the current system settings."""
    return _load()


@router.put("/", response_model=SystemSettings)
def update_settings(
    payload: SystemSettings,
    _ = Depends(require_admin),
) -> Any:
    """Persist updated system settings to data/system_settings.json."""
    _save(payload)
    return payload
