"""
video_logger.py — Non-blocking structured diagnostic logger for the video pipeline.

Design goals
------------
* Real-time safe: log records are placed into an in-memory queue; a single
  background thread drains that queue to disk.  The pipeline main thread
  never waits on disk I/O.
* Structured: every record is a self-contained JSON object (JSON-Lines format),
  making it easy to grep, jq, or load into pandas for post-run analysis.
* Rotating: when a log file exceeds VIDEO_LOG_MAX_BYTES a new file is opened
  automatically (up to 5 back-up files kept).
* Zero extra dependencies: uses only Python stdlib.

Usage
-----
    from thaqib.video.video_logger import get_video_logger
    vlog = get_video_logger()          # returns the singleton
    vlog.log_frame(frame_idx, ...)     # non-blocking — returns immediately
    vlog.close()                       # call once on shutdown
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from thaqib.config import get_settings


# ---------------------------------------------------------------------------
# JSON formatter — converts a LogRecord into a one-line JSON string.
# ---------------------------------------------------------------------------

class _JsonFormatter(logging.Formatter):
    """Emit each log record as a JSON object on a single line."""

    def _sanitize(self, obj):
        if isinstance(obj, dict):
            return {
                k: self._sanitize(v)
                for k, v in obj.items()
            }
        if isinstance(obj, (str, int, float, bool)) or obj is None:
            return obj
        # convert tuples, lists, and other safe types to string
        return str(obj)

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        payload: dict[str, Any] = {
            "ts":  record.created,
            "lvl": record.levelname,
            "mod": record.name.split(".")[-1],  # last component only
            "msg": record.getMessage(),
        }
        # Merge any extra fields attached via the 'extra' dict
        for key, value in record.__dict__.items():
            if key.startswith("_vl_"):
                payload[key[4:]] = value  # strip the "_vl_" namespace prefix
        # Errors
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        try:
            sanitized = self._sanitize(payload)
            return json.dumps(sanitized, ensure_ascii=False)
        except Exception:
            return json.dumps({"ts": record.created, "lvl": "ERROR",
                               "mod": "video_logger", "msg": "json serialise failed"})


# ---------------------------------------------------------------------------
# Non-blocking queue handler — puts log records into an in-memory queue
# and lets a background thread do the actual file write.
# ---------------------------------------------------------------------------

class _QueueHandler(logging.handlers.QueueHandler):
    """Subclass so we can add a custom enqueue that never blocks."""

    def enqueue(self, record: logging.LogRecord) -> None:  # type: ignore[override]
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            pass  # drop the record rather than block the pipeline


# ---------------------------------------------------------------------------
# VideoLogger — the main public class
# ---------------------------------------------------------------------------

class VideoLogger:
    """
    Structured, non-blocking diagnostic logger for the video pipeline.

    All public methods return immediately; the actual file write happens on a
    background thread so the 30-FPS pipeline loop is never blocked.
    """

    # Sentinel used to stop the writer thread cleanly.
    _STOP = object()

    def __init__(
        self,
        log_dir: str = "logs",
        level: str = "DEBUG",
        max_bytes: int = 100 * 1024 * 1024,  # 100 MB
        backup_count: int = 5,
    ) -> None:
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)

        self._level = getattr(logging, level.upper(), logging.DEBUG)
        self._max_bytes = max_bytes
        self._backup_count = backup_count

        # Session-scoped log file: logs/video_YYYYMMDD_HHMMSS.log
        time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._log_path = self._log_dir / f"video_{time_str}.log"

        # Internal queue (unbounded — we drop in _QueueHandler if needed)
        self._queue: queue.Queue = queue.Queue(maxsize=2000)

        # Set up the underlying Python logger (private name so it doesn't
        # interfere with the module-level loggers already in the codebase).
        self._logger = logging.getLogger(f"thaqib.video._diag.{time_str}")
        self._logger.setLevel(self._level)
        self._logger.propagate = False  # don't bubble up to root handler

        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            str(self._log_path),
            maxBytes=self._max_bytes,
            backupCount=self._backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(_JsonFormatter())
        file_handler.setLevel(self._level)

        # Wire through the non-blocking queue
        self._queue_handler = _QueueHandler(self._queue)
        self._queue_handler.setLevel(self._level)
        self._logger.addHandler(self._queue_handler)

        # Background writer thread drains the queue → file handler
        self._listener = logging.handlers.QueueListener(
            self._queue,
            file_handler,
            respect_handler_level=True,
        )
        self._listener.start()

        # Stats
        self._frame_count: int = 0
        self._start_time: float = time.time()
        self._closed: bool = False

        self._log(logging.INFO, "VIDEO_LOGGER_INIT", {
            "log_file": str(self._log_path),
            "level": level,
            "max_bytes": max_bytes,
        })

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _log(self, level: int, event: str, fields: dict[str, Any]) -> None:
        """Emit a structured record; always non-blocking."""
        if self._closed or level < self._level:
            return
        extra = {f"_vl_{k}": v for k, v in fields.items()}
        extra["_vl_event"] = event
        try:
            self._logger.log(level, event, extra=extra)
        except Exception:
            pass  # never crash the pipeline for a log failure

    # ------------------------------------------------------------------
    # Public convenience methods — one per logical event type
    # ------------------------------------------------------------------

    def log_startup(
        self,
        *,
        source: Any,
        detection_interval: float,
        archive_mode: str,
        face_workers: int,
        video_quality: int,
        yolo_model: str,
        tools_model: str,
        detection_confidence: float,
        tools_confidence: float,
        detection_imgsz: int,
        neighbor_k: int,
        risk_angle_tolerance: float,
        suspicious_duration_threshold: float,
        reid_match_threshold: float,
    ) -> None:
        """Log all pipeline configuration at startup."""
        self._log(logging.INFO, "PIPELINE_START", {
            "source": str(source),
            "detection_interval": detection_interval,
            "archive_mode": archive_mode,
            "face_workers": face_workers,
            "video_quality": video_quality,
            "yolo_model": yolo_model,
            "tools_model": tools_model,
            "detection_confidence": detection_confidence,
            "tools_confidence": tools_confidence,
            "detection_imgsz": detection_imgsz,
            "neighbor_k": neighbor_k,
            "risk_angle_tolerance": risk_angle_tolerance,
            "suspicious_duration_threshold": suspicious_duration_threshold,
            "reid_match_threshold": reid_match_threshold,
        })

    def log_camera_open(
        self,
        *,
        camera_fps: float,
        post_buffer_frames: int,
        face_workers: int,
    ) -> None:
        """Log camera and thread-pool info after camera is opened."""
        self._log(logging.INFO, "CAMERA_OPEN", {
            "camera_fps": camera_fps,
            "post_buffer_frames": post_buffer_frames,
            "face_workers": face_workers,
        })

    def log_frame(
        self,
        *,
        frame_idx: int,
        timestamp: float,
        proc_ms: float,
        detect_ms: float,
        track_ms: float,
        registry_ms: float,
        neighbor_ms: float,
        facemesh_ms: float,
        tracks: list[dict],
        new_detection: bool,
        detection_persons: int,
        detection_tools: int,
        selected_count: int,
        pending_fm_futures: int,
        fm_collected: int,
        fm_none: int,
        fm_errors: int,
        phone_detected: bool,
        phone_is_recording: bool,
        global_buffer_len: int,
        processing_res: str,
    ) -> None:
        """Log full per-frame state snapshot. Emitted at DEBUG level."""
        self._frame_count += 1
        self._log(logging.DEBUG, "FRAME", {
            "frame_idx": frame_idx,
            "timestamp": timestamp,
            "proc_ms": round(proc_ms, 2),
            "timing": {
                "detect_ms":   round(detect_ms, 2),
                "track_ms":    round(track_ms, 2),
                "registry_ms": round(registry_ms, 2),
                "neighbor_ms": round(neighbor_ms, 2),
                "facemesh_ms": round(facemesh_ms, 2),
            },
            "tracks": tracks,
            "new_detection": new_detection,
            "detection_persons": detection_persons,
            "detection_tools": detection_tools,
            "selected_count": selected_count,
            "fm": {
                "pending": pending_fm_futures,
                "collected": fm_collected,
                "none_result": fm_none,
                "errors": fm_errors,
            },
            "phone_detected": phone_detected,
            "phone_is_recording": phone_is_recording,
            "global_buffer_len": global_buffer_len,
            "processing_res": processing_res,
        })

    def log_detection_result(
        self,
        *,
        frame_idx: int,
        persons: int,
        phones: int,
        papers: int,
        elapsed_ms: float,
    ) -> None:
        """Log a new detection batch (INFO level — only when new result available)."""
        self._log(logging.INFO, "DETECTION_RESULT", {
            "frame_idx": frame_idx,
            "persons": persons,
            "phones": phones,
            "papers": papers,
            "elapsed_ms": round(elapsed_ms, 2),
        })

    def log_tracking_update(
        self,
        *,
        frame_idx: int,
        track_ids: list[int],
        new_ids: list[int],
        expired_ids: list[int],
        registry_size: int,
    ) -> None:
        """Log registry state after tracking + registry update."""
        self._log(logging.INFO, "TRACKING_UPDATE", {
            "frame_idx": frame_idx,
            "track_ids": track_ids,
            "new_ids": new_ids,
            "expired_ids": expired_ids,
            "registry_size": registry_size,
        })

    def log_gaze_check(
        self,
        *,
        track_id: int,
        is_looking: bool,
        dot_product: float | None,
        paper: tuple | None,
        matched_neighbor: int | None,
        suspicious_sec: float,
        is_cheating: bool,
        cheating_cooldown: int,
        face_available: bool,
        in_grace_period: bool,
    ) -> None:
        """Log the result of a single gaze evaluation (DEBUG level)."""
        self._log(logging.DEBUG, "GAZE_CHECK", {
            "track_id": track_id,
            "face_available": face_available,
            "in_grace_period": in_grace_period,
            "is_looking": is_looking,
            "dot_product": round(dot_product, 4) if dot_product is not None else None,
            "paper": list(paper) if paper else None,
            "matched_neighbor": matched_neighbor,
            "suspicious_sec": round(suspicious_sec, 3),
            "is_cheating": is_cheating,
            "cheating_cooldown": cheating_cooldown,
        })

    def log_cheating_detected(
        self,
        *,
        track_id: int,
        victim_id: int | None,
        paper: tuple | None,
        paper_source: str,
        duration_sec: float,
    ) -> None:
        """Log a new cheating detection event (WARNING level)."""
        self._log(logging.WARNING, "CHEATING_DETECTED", {
            "track_id": track_id,
            "victim_id": victim_id,
            "paper": list(paper) if paper else None,
            "paper_source": paper_source,
            "duration_sec": round(duration_sec, 3),
        })

    def log_phone_detected(
        self,
        *,
        frame_idx: int,
        bbox_count: int,
        bboxes: list,
    ) -> None:
        """Log a phone detection (WARNING level)."""
        self._log(logging.WARNING, "PHONE_DETECTED", {
            "frame_idx": frame_idx,
            "phone_count": bbox_count,
            "bboxes": [list(b) for b in bboxes],
        })

    def log_alert_recording_start(
        self,
        *,
        track_id: int,
        prebuffer_frames: int,
        post_buffer_frames: int,
        cheat_type: str,
    ) -> None:
        """Log when an alert recording begins."""
        self._log(logging.INFO, "ALERT_START", {
            "track_id": track_id,
            "prebuffer_frames": prebuffer_frames,
            "post_buffer_frames": post_buffer_frames,
            "cheat_type": cheat_type,
        })

    def log_alert_recording_save(
        self,
        *,
        track_id: int,
        filename: str,
        frames: int,
        duration_sec: float,
        codec: str,
        cheat_type: str,
        cheat_ctx: dict | None,
    ) -> None:
        """Log when an alert clip is saved to disk."""
        self._log(logging.INFO, "ALERT_SAVE", {
            "track_id": track_id,
            "filename": filename,
            "frames": frames,
            "duration_sec": round(duration_sec, 3),
            "codec": codec,
            "cheat_type": cheat_type,
            "cheat_ctx": cheat_ctx,
        })

    def log_phone_alert_recording_start(
        self,
        *,
        prebuffer_frames: int,
        post_buffer_frames: int,
    ) -> None:
        """Log when a phone-only alert recording begins."""
        self._log(logging.INFO, "PHONE_ALERT_START", {
            "prebuffer_frames": prebuffer_frames,
            "post_buffer_frames": post_buffer_frames,
        })

    def log_phone_alert_save(
        self,
        *,
        filename: str,
        frames: int,
        duration_sec: float,
        codec: str,
    ) -> None:
        """Log when a phone-only alert clip is saved."""
        self._log(logging.INFO, "PHONE_ALERT_SAVE", {
            "filename": filename,
            "frames": frames,
            "duration_sec": round(duration_sec, 3),
            "codec": codec,
        })

    def log_reid_alias(
        self,
        *,
        orig_id: int,
        matched_id: int,
    ) -> None:
        """Log a ReID alias assignment."""
        self._log(logging.INFO, "REID_ALIAS", {
            "orig_id": orig_id,
            "matched_id": matched_id,
        })

    def log_student_selection(
        self,
        *,
        action: str,  # "SELECT" | "ADD" | "REMOVE" | "CLEAR"
        ids_before: list[int],
        ids_after: list[int],
    ) -> None:
        """Log a student selection change."""
        self._log(logging.INFO, "STUDENT_SELECTION", {
            "action": action,
            "ids_before": sorted(ids_before),
            "ids_after": sorted(ids_after),
        })

    def log_archive_start(
        self,
        *,
        filepath: str,
        codec: str,
        quality: int,
        size: tuple[int, int],
        fps: float,
    ) -> None:
        """Log when the continuous archive recording file is opened."""
        self._log(logging.INFO, "ARCHIVE_START", {
            "filepath": filepath,
            "codec": codec,
            "quality": quality,
            "width": size[0],
            "height": size[1],
            "fps": round(fps, 2),
        })

    def log_recording_cap_hit(
        self,
        *,
        track_id: int,
        active_recordings: int,
    ) -> None:
        """Log when a new alert recording is skipped due to the 3-recording cap."""
        self._log(logging.WARNING, "RECORDING_CAP_HIT", {
            "track_id": track_id,
            "active_recordings": active_recordings,
        })

    def log_pipeline_stop(
        self,
        *,
        total_frames: int,
        elapsed_sec: float,
    ) -> None:
        """Log pipeline shutdown summary."""
        fps = total_frames / elapsed_sec if elapsed_sec > 0 else 0.0
        self._log(logging.INFO, "PIPELINE_STOP", {
            "total_frames": total_frames,
            "elapsed_sec": round(elapsed_sec, 2),
            "avg_fps": round(fps, 2),
        })

    def log_keypress(self, *, key: str, action: str) -> None:
        """Log an interactive key press from the display loop."""
        self._log(logging.INFO, "KEYPRESS", {"key": key, "action": action})

    def log_display_fps(self, *, frame_idx: int, display_fps: float) -> None:
        """Log the measured display-loop FPS (sampled every 30 frames)."""
        self._log(logging.DEBUG, "DISPLAY_FPS", {
            "frame_idx": frame_idx,
            "display_fps": round(display_fps, 2),
        })

    def log_error(self, *, context: str, error: str) -> None:
        """Log an unexpected error that was caught and handled."""
        self._log(logging.ERROR, "ERROR", {
            "context": context,
            "error": error,
        })

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def log_path(self) -> str:
        """Absolute path to the current log file."""
        return str(self._log_path)

    def close(self) -> None:
        """Flush the queue and stop the background writer thread."""
        if self._closed:
            return
        elapsed = time.time() - self._start_time
        self.log_pipeline_stop(
            total_frames=self._frame_count,
            elapsed_sec=elapsed,
        )
        # Give the queue a moment to drain before stopping the listener
        try:
            self._listener.stop()
        except Exception:
            pass
        self._closed = True


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_instance: VideoLogger | None = None
_lock = threading.Lock()


def get_video_logger() -> VideoLogger:
    """
    Return the process-wide VideoLogger singleton.

    Creates it on the first call using settings from the environment.
    Subsequent calls return the same instance immediately (no lock contention).
    """
    global _instance
    if _instance is not None:
        return _instance
    with _lock:
        if _instance is not None:
            return _instance
        settings = get_settings()
        enabled = getattr(settings, "video_log_enabled", True)
        if not enabled:
            # Return a no-op logger (level=CRITICAL effectively mutes everything)
            _instance = VideoLogger(
                log_dir=getattr(settings, "video_log_dir", "logs"),
                level="CRITICAL",
            )
            return _instance
        _instance = VideoLogger(
            log_dir=getattr(settings, "video_log_dir", "logs"),
            level=getattr(settings, "video_log_level", "DEBUG"),
            max_bytes=getattr(settings, "video_log_max_bytes", 100 * 1024 * 1024),
        )
    return _instance


def reset_video_logger() -> None:
    """Close the current singleton and clear it (useful for testing)."""
    global _instance
    with _lock:
        if _instance is not None:
            _instance.close()
            _instance = None
