"""
System-wide runtime settings API.

On PUT: writes changed values directly into the .env file AND clears the
get_settings() lru_cache, so any new pipeline that calls get_settings()
will pick up the updated values without a server restart.

Running pipelines are NOT affected (they already loaded settings at start).
New monitoring sessions started after a PUT will use the new values.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.thaqib.api.dependencies import RequireRole

router = APIRouter()
require_admin = RequireRole(["admin"])

ENV_FILE = Path(".env")

# ── Mapping: Settings field → .env key ───────────────────────────────────────
# Only the fields we expose in the UI. Keys match Settings model field names.
ENV_KEY_MAP: dict[str, str] = {
    "video_quality":                  "VIDEO_QUALITY",
    "alert_max_height":               "ALERT_MAX_HEIGHT",
    "archive_mode":                   "ARCHIVE_MODE",
    "detection_interval":             "DETECTION_INTERVAL",
    "detection_confidence":           "DETECTION_CONFIDENCE",
    "detection_imgsz":                "DETECTION_IMGSZ",
    "tools_confidence":               "TOOLS_CONFIDENCE",
    "object_detection_enabled":       "OBJECT_DETECTION_ENABLED",
    "tracking_max_distance":          "TRACKING_MAX_DISTANCE",
    "tracking_max_age":               "TRACKING_MAX_AGE",
    "neighbor_k":                     "NEIGHBOR_K",
    "risk_angle_tolerance":           "RISK_ANGLE_TOLERANCE",
    "suspicious_duration_threshold":  "SUSPICIOUS_DURATION_THRESHOLD",
    "suspicious_match_ratio":         "SUSPICIOUS_MATCH_RATIO",
    "reid_match_threshold":           "REID_MATCH_THRESHOLD",
    "face_mesh_workers":              "FACE_MESH_WORKERS",
}

# UI-only fields that have no .env equivalent (stored in JSON sidecar)
UI_ONLY_FIELDS = {"gaze_sensitivity", "audio_sensitivity", "alert_cooldown_seconds"}
SIDECAR_FILE = Path("data/ui_settings.json")


# ── Schema ────────────────────────────────────────────────────────────────────

class SystemSettings(BaseModel):
    # Video & Archive
    video_quality: int = Field(75, ge=0, le=100)
    alert_max_height: int = Field(720, ge=0, le=2160)
    archive_mode: str = Field("raw")

    # Detection
    detection_interval: float = Field(1.0, ge=0.1, le=10.0)
    detection_confidence: float = Field(0.15, ge=0.01, le=1.0)
    detection_imgsz: int = Field(640)
    tools_confidence: float = Field(0.45, ge=0.01, le=1.0)
    object_detection_enabled: bool = Field(True)

    # Tracking
    tracking_max_distance: int = Field(100, ge=10, le=500)
    tracking_max_age: int = Field(30, ge=5, le=300)
    neighbor_k: int = Field(6, ge=2, le=20)

    # Cheating evaluation (gaze_sensitivity is a UI alias, risk_angle_tolerance is the real .env key)
    gaze_sensitivity: int = Field(70, ge=10, le=100)
    risk_angle_tolerance: float = Field(25.0, ge=5.0, le=60.0)
    suspicious_duration_threshold: float = Field(2.0, ge=0.5, le=30.0)
    suspicious_match_ratio: float = Field(0.7, ge=0.1, le=1.0)

    # Audio (UI sliders — no direct .env equivalent yet)
    audio_sensitivity: int = Field(65, ge=10, le=100)
    alert_cooldown_seconds: int = Field(30, ge=5, le=120)

    # Re-identification
    reid_match_threshold: float = Field(0.80, ge=0.5, le=1.0)

    # Performance
    face_mesh_workers: int = Field(4, ge=1, le=16)


# ── .env helpers ──────────────────────────────────────────────────────────────

def _read_env() -> str:
    """Read the current .env file content, or return empty string."""
    if ENV_FILE.exists():
        return ENV_FILE.read_text(encoding="utf-8")
    return ""


def _write_env(content: str) -> None:
    ENV_FILE.write_text(content, encoding="utf-8")


def _update_env_values(updates: dict[str, str]) -> None:
    """
    Update or append key=value pairs in the .env file.
    - Existing keys are updated in-place (preserving comments and order).
    - New keys are appended at the bottom under a '# [Settings UI]' header.
    """
    content = _read_env()
    lines = content.splitlines(keepends=True)
    remaining = dict(updates)  # keys we still need to write

    new_lines: list[str] = []
    for line in lines:
        # Match KEY=value or KEY = value (ignore comments)
        m = re.match(r'^([A-Z_][A-Z0-9_]*)\s*=', line)
        if m:
            key = m.group(1)
            if key in remaining:
                new_lines.append(f"{key}={remaining.pop(key)}\n")
                continue
        new_lines.append(line)

    # Append any keys that weren't already in the file
    if remaining:
        # Ensure file ends with a newline before appending
        if new_lines and not new_lines[-1].endswith('\n'):
            new_lines.append('\n')
        new_lines.append('\n# [Settings UI — written by /api/settings]\n')
        for key, val in remaining.items():
            new_lines.append(f"{key}={val}\n")

    _write_env("".join(new_lines))


def _invalidate_settings_cache() -> None:
    """Clear the lru_cache on get_settings() so next call re-reads .env."""
    try:
        from src.thaqib.config.settings import get_settings
        get_settings.cache_clear()
    except Exception:
        pass


def _load_sidecar() -> dict:
    """Load UI-only settings from JSON sidecar (not in .env)."""
    SIDECAR_FILE.parent.mkdir(parents=True, exist_ok=True)
    if SIDECAR_FILE.exists():
        try:
            import json
            return json.loads(SIDECAR_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_sidecar(data: dict) -> None:
    import json
    SIDECAR_FILE.parent.mkdir(parents=True, exist_ok=True)
    SIDECAR_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _build_current_settings() -> SystemSettings:
    """Build a SystemSettings by reading .env (via get_settings()) + sidecar."""
    from src.thaqib.config.settings import get_settings
    s = get_settings()
    ui = _load_sidecar()
    return SystemSettings(
        video_quality=s.video_quality,
        alert_max_height=s.alert_max_height,
        archive_mode=s.archive_mode,
        detection_interval=s.detection_interval,
        detection_confidence=s.detection_confidence,
        detection_imgsz=s.detection_imgsz,
        tools_confidence=s.tools_confidence,
        object_detection_enabled=getattr(s, 'object_detection_enabled', True),
        tracking_max_distance=s.tracking_max_distance,
        tracking_max_age=s.tracking_max_age,
        neighbor_k=s.neighbor_k,
        gaze_sensitivity=ui.get("gaze_sensitivity", 70),
        risk_angle_tolerance=s.risk_angle_tolerance,
        suspicious_duration_threshold=s.suspicious_duration_threshold,
        suspicious_match_ratio=s.suspicious_match_ratio,
        audio_sensitivity=ui.get("audio_sensitivity", 65),
        alert_cooldown_seconds=ui.get("alert_cooldown_seconds", 30),
        reid_match_threshold=s.reid_match_threshold,
        face_mesh_workers=s.face_mesh_workers,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=SystemSettings)
def get_system_settings(_ = Depends(require_admin)) -> Any:
    """Return current settings — reads live from .env + sidecar."""
    return _build_current_settings()


@router.put("/", response_model=SystemSettings)
def update_system_settings(
    payload: SystemSettings,
    _ = Depends(require_admin),
) -> Any:
    """
    Persist settings:
    - .env fields  → written directly into .env file
    - UI-only fields → stored in data/ui_settings.json
    - lru_cache cleared so next get_settings() re-reads the updated .env
    """
    # 1. Build .env updates
    data = payload.model_dump()
    env_updates: dict[str, str] = {}
    for field_name, env_key in ENV_KEY_MAP.items():
        if field_name in data:
            val = data[field_name]
            # Convert Python types to .env-friendly strings
            if isinstance(val, bool):
                env_updates[env_key] = str(val).lower()
            elif isinstance(val, float):
                env_updates[env_key] = f"{val:.4g}"
            else:
                env_updates[env_key] = str(val)

    # 2. Write .env
    _update_env_values(env_updates)

    # 3. Invalidate cache — next get_settings() will re-read the updated .env
    _invalidate_settings_cache()

    # 4. Save UI-only fields to sidecar
    sidecar = _load_sidecar()
    for field_name in UI_ONLY_FIELDS:
        if field_name in data:
            sidecar[field_name] = data[field_name]
    _save_sidecar(sidecar)

    # 5. Return the new live state (re-reads .env so values are confirmed)
    return _build_current_settings()
