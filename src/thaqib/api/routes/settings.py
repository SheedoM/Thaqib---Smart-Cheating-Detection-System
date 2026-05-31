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
# Only fields that have a direct .env counterpart and actually affect the backend.
ENV_KEY_MAP: dict[str, str] = {
    # Video & Archive
    "video_quality":                  "VIDEO_QUALITY",
    "alert_max_height":               "ALERT_MAX_HEIGHT",
    "archive_mode":                   "ARCHIVE_MODE",
    # Detection
    "detection_interval":             "DETECTION_INTERVAL",
    "detection_confidence":           "DETECTION_CONFIDENCE",
    "detection_imgsz":                "DETECTION_IMGSZ",
    "tools_confidence":               "TOOLS_CONFIDENCE",
    # Tracking
    "tracking_max_distance":          "TRACKING_MAX_DISTANCE",
    "tracking_max_age":               "TRACKING_MAX_AGE",
    "neighbor_k":                     "NEIGHBOR_K",
    # Gaze / cheating evaluation
    "risk_angle_tolerance":           "RISK_ANGLE_TOLERANCE",
    "suspicious_duration_threshold":  "SUSPICIOUS_DURATION_THRESHOLD",
    # Re-ID & performance
    "reid_match_threshold":           "REID_MATCH_THRESHOLD",
    "face_mesh_workers":              "FACE_MESH_WORKERS",
    # Audio
    "audio_whisper_model":            "AUDIO_WHISPER_MODEL",
    "audio_strict_mode":              "AUDIO_STRICT_MODE",
    "audio_vad_threshold":            "AUDIO_VAD_THRESHOLD",
    "audio_silence_threshold":        "AUDIO_SILENCE_THRESHOLD",
    "audio_speech_buffer_sec":        "AUDIO_SPEECH_BUFFER_SEC",
    "audio_noise_reduction":          "AUDIO_NOISE_REDUCTION",
    "audio_noise_reduction_strength": "AUDIO_NOISE_REDUCTION_STRENGTH",
    "audio_adaptive_gain":            "AUDIO_ADAPTIVE_GAIN",
    "audio_adaptive_vad":             "AUDIO_ADAPTIVE_VAD",
    "audio_session_recording":        "AUDIO_SESSION_RECORDING",
    "audio_episode_recording":        "AUDIO_EPISODE_RECORDING",
    "audio_episode_min_sec":          "AUDIO_EPISODE_MIN_SEC",
    "audio_episode_grace_sec":        "AUDIO_EPISODE_GRACE_SEC",
}


# ── Schema ────────────────────────────────────────────────────────────────────

class SystemSettings(BaseModel):
    # ── Video & Archive ────────────────────────────────────────────────────────
    video_quality: int = Field(75, ge=0, le=100)
    alert_max_height: int = Field(720, ge=0, le=2160)
    archive_mode: str = Field("raw")

    # ── Detection ──────────────────────────────────────────────────────────────
    detection_interval: float = Field(1.0, ge=0.1, le=10.0)
    detection_confidence: float = Field(0.15, ge=0.01, le=1.0)
    detection_imgsz: int = Field(640)
    tools_confidence: float = Field(0.45, ge=0.01, le=1.0)

    # ── Tracking ───────────────────────────────────────────────────────────────
    tracking_max_distance: int = Field(100, ge=10, le=500)
    tracking_max_age: int = Field(30, ge=5, le=300)
    neighbor_k: int = Field(6, ge=2, le=20)
    risk_angle_tolerance: float = Field(25.0, ge=5.0, le=60.0)
    suspicious_duration_threshold: float = Field(2.0, ge=0.5, le=30.0)
    reid_match_threshold: float = Field(0.80, ge=0.5, le=1.0)
    face_mesh_workers: int = Field(4, ge=1, le=16)

    # ── Audio ──────────────────────────────────────────────────────────────────
    audio_whisper_model: str = Field("tiny")
    audio_strict_mode: bool = Field(True)
    audio_vad_threshold: float = Field(0.5, ge=0.1, le=1.0)
    audio_silence_threshold: float = Field(0.01, ge=0.0, le=1.0)
    audio_speech_buffer_sec: float = Field(2.5, ge=0.5, le=10.0)
    audio_noise_reduction: bool = Field(True)
    audio_noise_reduction_strength: float = Field(0.75, ge=0.0, le=1.0)
    audio_adaptive_gain: bool = Field(True)
    audio_adaptive_vad: bool = Field(True)
    audio_session_recording: bool = Field(True)
    audio_episode_recording: bool = Field(True)
    audio_episode_min_sec: float = Field(3.0, ge=1.0, le=30.0)
    audio_episode_grace_sec: float = Field(5.0, ge=1.0, le=30.0)


# ── .env helpers ──────────────────────────────────────────────────────────────

def _read_env() -> str:
    if ENV_FILE.exists():
        return ENV_FILE.read_text(encoding="utf-8")
    return ""


def _write_env(content: str) -> None:
    ENV_FILE.write_text(content, encoding="utf-8")


def _update_env_values(updates: dict[str, str]) -> None:
    """Update or append key=value pairs in the .env file in-place."""
    content = _read_env()
    lines = content.splitlines(keepends=True)
    remaining = dict(updates)

    new_lines: list[str] = []
    for line in lines:
        m = re.match(r'^([A-Z_][A-Z0-9_]*)\s*=', line)
        if m:
            key = m.group(1)
            if key in remaining:
                new_lines.append(f"{key}={remaining.pop(key)}\n")
                continue
        new_lines.append(line)

    if remaining:
        if new_lines and not new_lines[-1].endswith('\n'):
            new_lines.append('\n')
        new_lines.append('\n# [Settings UI — written by /api/settings]\n')
        for key, val in remaining.items():
            new_lines.append(f"{key}={val}\n")

    _write_env("".join(new_lines))


def _invalidate_settings_cache() -> None:
    try:
        from src.thaqib.config.settings import get_settings
        get_settings.cache_clear()
    except Exception:
        pass


def _build_current_settings() -> SystemSettings:
    """Read current settings from live get_settings() (backed by .env)."""
    from src.thaqib.config.settings import get_settings
    s = get_settings()
    return SystemSettings(
        video_quality=s.video_quality,
        alert_max_height=s.alert_max_height,
        archive_mode=s.archive_mode,
        detection_interval=s.detection_interval,
        detection_confidence=s.detection_confidence,
        detection_imgsz=s.detection_imgsz,
        tools_confidence=s.tools_confidence,
        tracking_max_distance=s.tracking_max_distance,
        tracking_max_age=s.tracking_max_age,
        neighbor_k=s.neighbor_k,
        risk_angle_tolerance=s.risk_angle_tolerance,
        suspicious_duration_threshold=s.suspicious_duration_threshold,
        reid_match_threshold=s.reid_match_threshold,
        face_mesh_workers=s.face_mesh_workers,
        audio_whisper_model=s.audio_whisper_model,
        audio_strict_mode=s.audio_strict_mode,
        audio_vad_threshold=s.audio_vad_threshold,
        audio_silence_threshold=s.audio_silence_threshold,
        audio_speech_buffer_sec=s.audio_speech_buffer_sec,
        audio_noise_reduction=s.audio_noise_reduction,
        audio_noise_reduction_strength=s.audio_noise_reduction_strength,
        audio_adaptive_gain=s.audio_adaptive_gain,
        audio_adaptive_vad=s.audio_adaptive_vad,
        audio_session_recording=s.audio_session_recording,
        audio_episode_recording=s.audio_episode_recording,
        audio_episode_min_sec=s.audio_episode_min_sec,
        audio_episode_grace_sec=s.audio_episode_grace_sec,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=SystemSettings)
def get_system_settings(_ = Depends(require_admin)) -> Any:
    return _build_current_settings()


@router.put("/", response_model=SystemSettings)
def update_system_settings(payload: SystemSettings, _ = Depends(require_admin)) -> Any:
    """Write to .env and clear lru_cache. Next get_settings() call re-reads .env."""
    data = payload.model_dump()
    env_updates: dict[str, str] = {}
    for field_name, env_key in ENV_KEY_MAP.items():
        if field_name in data:
            val = data[field_name]
            if isinstance(val, bool):
                env_updates[env_key] = str(val).lower()
            elif isinstance(val, float):
                env_updates[env_key] = f"{val:.4g}"
            else:
                env_updates[env_key] = str(val)

    _update_env_values(env_updates)
    _invalidate_settings_cache()
    return _build_current_settings()
