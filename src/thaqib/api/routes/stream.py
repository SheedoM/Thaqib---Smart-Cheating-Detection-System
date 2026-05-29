"""
Multi-camera monitoring routes for the dashboard.

Reads halls/devices from the database and runs one video pipeline per active
camera device. Each device's `stream_url` can point to a live stream or a
local video file, so the same architecture supports both demo and production.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session, selectinload

from src.thaqib.db.database import SessionLocal
from src.thaqib.db.models.infrastructure import Device, Hall
from src.thaqib.db.models.exams import Assignment
from src.thaqib.db.models.events import Alert, DetectionEvent
from src.thaqib.api.dependencies import RequireRole

logger = logging.getLogger(__name__)

router = APIRouter()
require_stream_user = RequireRole(["admin", "referee"])

ALERTS_DIR = Path("./alerts")
ALERTS_DIR.mkdir(exist_ok=True)
_ROOT_ALERTS_DIR = ALERTS_DIR.resolve()


def _safe_slug(value: str) -> str:
    allowed = []
    for ch in (value or "").strip():
        if ch.isalnum() or ch in ("-", "_"):
            allowed.append(ch)
        elif ch.isspace():
            allowed.append("_")
    out = "".join(allowed).strip("_")
    return out or "unknown"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _alerts_prefix_dir(camera: CameraRuntime, created_at_iso: str) -> Path:
    try:
        d = datetime.fromisoformat(created_at_iso)
    except Exception:
        d = datetime.now()
    date_dir = d.strftime("%Y%m%d")
    hall_dir = _safe_slug(camera.hall_name)
    cam_dir = _safe_slug(camera.identifier)
    return Path(date_dir) / hall_dir / cam_dir


def _ensure_alert_dirs(rel_prefix: Path) -> tuple[Path, Path]:
    snap_dir = (ALERTS_DIR / rel_prefix / "snapshots")
    clip_dir = (ALERTS_DIR / rel_prefix / "clips")
    snap_dir.mkdir(parents=True, exist_ok=True)
    clip_dir.mkdir(parents=True, exist_ok=True)
    return snap_dir, clip_dir


@dataclass
class CameraRuntime:
    device_id: str
    identifier: str
    camera_name: str
    hall_id: str
    hall_name: str
    source: str
    session_id: str | None = None
    thread: threading.Thread | None = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    frame_lock: threading.Lock = field(default_factory=threading.Lock)
    latest_frame: bytes | None = None
    stats: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.stats = {
            "camera_id": self.device_id,
            "camera_identifier": self.identifier,
            "camera_name": self.camera_name,
            "hall_id": self.hall_id,
            "hall_name": self.hall_name,
            "is_running": False,
            "fps": 0.0,
            "tracked_count": 0,
            "selected_count": 0,
            "frame_index": 0,
            "alert_count": 0,
            "last_error": None,
            "last_error_at": None,
            "latency_ms": 0.0,
            "resolution": "N/A",
            "frame_drops": 0,
            "uptime_seconds": 0,
            "started_at": None,
        }


_alerts: list[dict[str, Any]] = []
_alerts_lock = threading.Lock()
_camera_states: dict[str, CameraRuntime] = {}
_manager_lock = threading.Lock()


def _infer_event_type(state: Any) -> str:
    if bool(getattr(state, "is_using_phone", False)):
        return "استخدام الهاتف"
    if getattr(state, "cheating_target_neighbor", None) is not None:
        return "غش من الجار"
    return "سلوك مشبوه"


def _poll_for_alert_clip(
    alert_id: str,
    track_id: int,
    created_at_iso: str,
    rel_prefix_str: str,
    timeout_s: float = 25.0,
) -> None:
    """Attach video_file to an alert once pipeline writer saves it to ./alerts/."""
    try:
        created_at = datetime.fromisoformat(created_at_iso)
    except Exception:
        created_at = _now_utc()

    deadline = time.time() + timeout_s
    patterns = [
        f"*alert_track{track_id}_*.mp4",
        f"*alert_track{track_id}_*.avi",
    ]

    while time.time() < deadline:
        candidates: list[Path] = []
        for pat in patterns:
            candidates.extend(ALERTS_DIR.glob(pat))

        # Prefer newest file created after alert time
        best: Path | None = None
        best_mtime = 0.0
        for p in candidates:
            try:
                st = p.stat()
            except OSError:
                continue
            mtime = st.st_mtime
            if datetime.fromtimestamp(mtime, timezone.utc) < created_at:
                continue
            if mtime > best_mtime:
                best = p
                best_mtime = mtime

        if best is not None:
            # Move clip into structured folder
            rel_prefix = Path(rel_prefix_str)
            _, clip_dir = _ensure_alert_dirs(rel_prefix)
            dest = clip_dir / best.name
            try:
                if best.resolve() != dest.resolve():
                    best.replace(dest)
                best = dest
            except Exception:
                # If move fails, still attach original filename
                pass

            with _alerts_lock:
                for a in _alerts:
                    if a.get("id") == alert_id:
                        try:
                            rel_path = (rel_prefix / "clips" / best.name).as_posix()
                        except Exception:
                            rel_path = best.name
                        a["video_file"] = rel_path
                        db = SessionLocal()
                        try:
                            alert = db.query(Alert).filter(Alert.id == uuid.UUID(alert_id)).first()
                            if alert and alert.detection_event:
                                alert.detection_event.video_clip_path = rel_path
                                db.add(alert.detection_event)
                                db.commit()
                        except Exception as exc:
                            db.rollback()
                            logger.error("Failed to attach alert clip to persisted event: %s", exc)
                        finally:
                            db.close()
                        return
            return

        time.sleep(0.5)


def _parse_source(source: str) -> int | str:
    try:
        return int(source)
    except (TypeError, ValueError):
        return source


def _camera_display_name(device: Device) -> str:
    position = device.position or {}
    if isinstance(position, dict):
        label = position.get("label")
        if isinstance(label, str) and label.strip():
            return label.strip()
    return device.identifier


def _serialize_camera(device: Device, hall: Hall, runtime: CameraRuntime | None) -> dict[str, Any]:
    source = (device.stream_url or "").strip()
    position = device.position if isinstance(device.position, dict) else {}
    return {
        "id": str(device.id),
        "identifier": device.identifier,
        "name": _camera_display_name(device),
        "type": device.type,
        "status": device.status,
        "active": runtime is not None and runtime.stats.get("is_running", False),
        "feed_path": f"/api/stream/feed/{device.id}" if source else None,
        "source_configured": bool(source),
        "position": position,
    }


def _hall_to_payload(hall: Hall, db: Session | None = None) -> dict[str, Any]:
    active_devices = [d for d in hall.devices if d.deleted_at is None]
    camera_devices = [device for device in active_devices if device.type == "camera"]
    mic_devices = [device for device in active_devices if device.type == "microphone"]
    cameras = [
        _serialize_camera(device, hall, _camera_states.get(str(device.id)))
        for device in camera_devices
    ]
    
    monitoring_status = "inactive"
    if db:
        # Check if this hall is currently being monitored
        active_assignment = db.query(Assignment).filter(
            Assignment.hall_id == hall.id,
            Assignment.monitoring_started_at.isnot(None),
            Assignment.monitoring_ended_at.is_(None)
        ).first()
        if active_assignment:
            monitoring_status = "active"

    return {
        "id": str(hall.id),
        "name": hall.name,
        "status": hall.status,
        "monitoring_status": monitoring_status,
        "building": hall.building,
        "floor": hall.floor,
        "capacity": hall.capacity,
        "image": hall.image,
        "cameras": cameras,
        "mics": [
            {
                "id": str(device.id),
                "identifier": device.identifier,
                "name": _camera_display_name(device),
                "status": device.status,
            }
            for device in mic_devices
        ],
    }


def _load_halls_with_devices(db: Session) -> list[Hall]:
    return (
        db.query(Hall)
        .filter(Hall.deleted_at.is_(None))
        .options(selectinload(Hall.devices))
        .order_by(Hall.name.asc())
        .all()
    )


def _load_active_camera_rows(db: Session) -> list[tuple[Hall, Device]]:
    """Load cameras for halls that are currently in an active monitoring session."""
    # Only include halls that have an active assignment (started and not ended)
    active_assignments = (
        db.query(Assignment)
        .filter(
            Assignment.monitoring_started_at.isnot(None),
            Assignment.monitoring_ended_at.is_(None)
        )
        .options(selectinload(Assignment.hall).selectinload(Hall.devices))
        .all()
    )
    
    active_pairs: list[tuple[uuid.UUID, Hall, Device]] = []
    for assignment in active_assignments:
        hall = assignment.hall
        if not hall or hall.deleted_at is not None:
            continue
            
        for device in hall.devices:
            if device.deleted_at is not None:
                continue
            if device.type != "camera":
                continue
            source = (device.stream_url or "").strip()
            if not source:
                continue
            active_pairs.append((assignment.exam_session_id, hall, device))
    return active_pairs


def _draw_annotations(frame: np.ndarray, pipeline_frame: Any, scale: float = 1.0) -> np.ndarray:
    annotated = frame.copy()

    def s(val: Any) -> int:
        return int(float(val) * scale)

    for track in pipeline_frame.tracking_result.tracks:
        if not track.is_selected:
            x1, y1, x2, y2 = track.bbox
            cv2.rectangle(annotated, (s(x1), s(y1)), (s(x2), s(y2)), (128, 128, 128), 2)
            cv2.putText(
                annotated,
                f"ID:{track.track_id}",
                (s(x1), s(y1) - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (128, 128, 128),
                1,
            )

    for state in pipeline_frame.student_states:
        x1, y1, x2, y2 = state.bbox

        is_looking = bool(getattr(state, "is_looking_at_neighbor", False))
        looking_at_id = getattr(state, "looking_at_neighbor_id", None)
        is_cheating = bool(getattr(state, "is_cheating", False))
        is_suspicious = is_looking or is_cheating

        if is_suspicious:
            color = (0, 0, 255)
            status = f"LOOKING AT #{looking_at_id}" if looking_at_id is not None else "SUSPICIOUS"
        else:
            color = (0, 255, 0)
            status = "OK"

        cv2.rectangle(annotated, (s(x1), s(y1)), (s(x2), s(y2)), color, 2)
        cv2.putText(
            annotated,
            f"ID:{state.track_id} [{status}]",
            (s(x1), s(y1) - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
        )

        head_pose = getattr(state, "head_pose", None)
        if head_pose is not None and getattr(head_pose, "has_pose", False):
            pose = getattr(head_pose, "pose", None)
            if pose is not None:
                cx, cy = state.center
                arrow_length = 50 * scale
                yaw = float(getattr(pose, "yaw", 0.0))
                pitch = float(getattr(pose, "pitch", 0.0))
                yaw_rad = np.radians(yaw)
                end_x = int(s(cx) + arrow_length * np.cos(yaw_rad))
                end_y = int(s(cy) + arrow_length * np.sin(yaw_rad))
                cv2.arrowedLine(annotated, (s(cx), s(cy)), (end_x, end_y), (255, 0, 255), 2)
                cv2.putText(
                    annotated,
                    f"Y:{yaw:.0f} P:{pitch:.0f}",
                    (s(x1), s(y2) + 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5 * scale,
                    (255, 0, 255),
                    1,
                )

        spatial_context = getattr(state, "spatial_context", None)
        if spatial_context is not None:
            for risk in getattr(spatial_context, "risk_angles", []) or []:
                cx, cy = state.center
                angle_rad = np.radians(risk.center_angle)
                radius = 40 * scale
                end_x = int(s(cx) + radius * np.cos(angle_rad))
                end_y = int(s(cy) + radius * np.sin(angle_rad))
                cv2.line(annotated, (s(cx), s(cy)), (end_x, end_y), (0, 165, 255), 1)

    info_lines = [
        f"FPS: {1000 / max(pipeline_frame.processing_time_ms, 1):.1f}",
        f"Tracked: {pipeline_frame.tracked_count}",
        f"Selected: {pipeline_frame.selected_count}",
        f"Frame: {pipeline_frame.frame_index}",
    ]
    for i, line in enumerate(info_lines):
        cv2.putText(
            annotated,
            line,
            (10, int(30 * scale + i * 25 * scale)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6 * scale,
            (255, 255, 255),
            2,
        )
    return annotated


def _save_alert_snapshot(frame: np.ndarray, camera: CameraRuntime, track_id: int, created_at_iso: str) -> str:
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_camera_id = camera.device_id.replace("-", "")
    filename = f"alert_{safe_camera_id}_{track_id}_{timestamp_str}_{uuid.uuid4().hex[:6]}.jpg"
    rel_prefix = _alerts_prefix_dir(camera, created_at_iso)
    snap_dir, _ = _ensure_alert_dirs(rel_prefix)
    filepath = snap_dir / filename
    cv2.imwrite(str(filepath), frame)
    logger.info("Alert snapshot saved: %s", filepath)
    rel_path = (rel_prefix / "snapshots" / filename).as_posix()
    return rel_path


def _persist_stream_alert(camera: CameraRuntime, state: Any, alert_data: dict[str, Any]) -> str | None:
    if not camera.session_id:
        return None

    db = SessionLocal()
    try:
        event = DetectionEvent(
            exam_session_id=uuid.UUID(camera.session_id),
            device_id=uuid.UUID(camera.device_id),
            event_type=alert_data.get("event_type") or "gaze_alignment",
            severity=alert_data.get("severity") or "high",
            student_position={
                "track_id": getattr(state, "track_id", None),
                "looking_at": getattr(state, "looking_at_neighbor_id", None),
            },
            timestamp=datetime.fromisoformat(alert_data["timestamp"]),
            confidence_score=None,
            video_clip_path=alert_data.get("video_file"),
            metadata_json={
                "snapshot_file": alert_data.get("snapshot_file"),
                "camera_identifier": camera.identifier,
                "camera_name": camera.camera_name,
                "hall_id": camera.hall_id,
                "hall_name": camera.hall_name,
                "stream_alert_id": alert_data.get("id"),
            },
        )
        alert = Alert(
            exam_session_id=uuid.UUID(camera.session_id),
            detection_event=event,
            alert_type="tier_2",
            status="pending",
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return str(alert.id)
    except Exception as exc:
        db.rollback()
        logger.error("Failed to persist stream alert: %s", exc)
        return None
    finally:
        db.close()


def _run_pipeline(camera: CameraRuntime) -> None:
    from src.thaqib.video.pipeline import VideoPipeline, StudentState

    parsed_source = _parse_source(camera.source)
    logger.info("Starting pipeline for %s (%s)", camera.identifier, parsed_source)
    auto_selected = False

    def on_alert(state: StudentState) -> None:
        with camera.frame_lock:
            current_frame = camera.latest_frame

        if current_frame is None:
            return

        nparr = np.frombuffer(current_frame, np.uint8)
        frame_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame_img is None:
            return

        created_at = _now_utc().isoformat()
        rel_prefix = _alerts_prefix_dir(camera, created_at)
        filename = _save_alert_snapshot(frame_img, camera, state.track_id, created_at)
        alert_data = {
            "id": str(uuid.uuid4()),
            "camera_id": camera.device_id,
            "camera_identifier": camera.identifier,
            "camera_name": camera.camera_name,
            "hall_id": camera.hall_id,
            "hall_name": camera.hall_name,
            "track_id": state.track_id,
            "looking_at": getattr(state, "looking_at_neighbor_id", None),
            "event_type": _infer_event_type(state),
            "severity": "high",
            "timestamp": created_at,
            "snapshot_file": filename,
            "video_file": None,
            "location": f"{camera.hall_name} - {camera.camera_name}",
        }
        persisted_alert_id = _persist_stream_alert(camera, state, alert_data)
        if persisted_alert_id:
            alert_data["id"] = persisted_alert_id

        with _alerts_lock:
            _alerts.insert(0, alert_data)
            del _alerts[50:]
            camera.stats["alert_count"] = sum(1 for item in _alerts if item["camera_id"] == camera.device_id)

        logger.warning(
            "ALERT on %s: student %s looking at neighbor %s",
            camera.identifier,
            state.track_id,
            getattr(state, "looking_at_neighbor_id", None),
        )

        # Attach clip filename once pipeline writer flushes it to disk
        threading.Thread(
            target=_poll_for_alert_clip,
            args=(alert_data["id"], state.track_id, created_at, rel_prefix.as_posix()),
            daemon=True,
            name=f"AlertClipPoll-{state.track_id}",
        ).start()

    # Load runtime settings — get_settings() re-reads .env after any PUT /api/settings
    from src.thaqib.config.settings import get_settings as _get_settings
    _rt = _get_settings()
    _detection_interval = _rt.detection_interval
    _jpeg_quality = _rt.video_quality
    _archive_mode = _rt.archive_mode

    pipeline = VideoPipeline(source=parsed_source, detection_interval=_detection_interval, on_alert=on_alert)
    pipeline._archive_annotated = (_archive_mode == "annotated")
    # Expose pipeline to HTTP control endpoints (toggle_video_quality / toggle_processing_resolution)
    camera._pipeline = pipeline

    try:
        started = pipeline.start()
        if not started:
            camera.stats["is_running"] = False
            camera.stats["last_error"] = f"Failed to open camera source: {camera.source}"
            camera.stats["last_error_at"] = _now_utc().isoformat()
            logger.error("Camera %s failed to open source: %s", camera.identifier, camera.source)
            return

        camera.stats["is_running"] = True
        camera.stats["last_error"] = None
        camera.stats["last_error_at"] = None
        camera.stats["started_at"] = _now_utc().isoformat()
        camera.stats["frame_drops"] = 0

        # Throttle JPEG encoding rate to reduce CPU and avoid UI freezes.
        last_emit = 0.0
        target_fps = 12.0
        min_interval = 1.0 / target_fps
        max_stream_w = 1280

        for frame_data in pipeline.run():
            if camera.stop_event.is_set():
                break

            if not auto_selected and frame_data.frame_index > 5:
                all_ids = [track.track_id for track in frame_data.tracking_result.tracks]
                if all_ids:
                    pipeline.select_students(all_ids)
                    auto_selected = True
                    logger.info(
                        "Auto-selected %s students for %s",
                        len(all_ids),
                        camera.identifier,
                    )

            # Downscale high-res frames (e.g. 4K) to prevent memory crashes and improve MJPEG performance.
            original_frame = frame_data.frame
            h, w = original_frame.shape[:2]
            scale = 1.0
            if w > max_stream_w and w > 0:
                scale = max_stream_w / float(w)
                new_h = max(1, int(h * scale))
                display_frame = cv2.resize(original_frame, (max_stream_w, new_h), interpolation=cv2.INTER_AREA)
            else:
                display_frame = original_frame

            annotated = _draw_annotations(display_frame, frame_data, scale=scale)
            now = time.time()
            if now - last_emit < min_interval:
                camera.stats["frame_drops"] = camera.stats.get("frame_drops", 0) + 1
                continue

            ok, jpeg = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, _jpeg_quality])
            if not ok:
                continue

            with camera.frame_lock:
                camera.latest_frame = jpeg.tobytes()

            # Compute uptime
            started_at = camera.stats.get("started_at")
            uptime = 0
            if started_at:
                try:
                    uptime = int((_now_utc() - datetime.fromisoformat(started_at)).total_seconds())
                except Exception:
                    pass

            camera.stats.update(
                {
                    "is_running": True,
                    "fps": round(1000 / max(frame_data.processing_time_ms, 1), 1),
                    "tracked_count": frame_data.tracked_count,
                    "selected_count": frame_data.selected_count,
                    "frame_index": frame_data.frame_index,
                    "latency_ms": round(frame_data.processing_time_ms, 1),
                    "resolution": f"{w}x{h}",
                    "uptime_seconds": uptime,
                }
            )
            last_emit = now
    except Exception:
        logger.exception("Pipeline error for camera %s", camera.identifier)
        camera.stats["last_error"] = "Pipeline error (see server logs)"
        camera.stats["last_error_at"] = _now_utc().isoformat()
    finally:
        try:
            pipeline.stop()
        except Exception:
            pass
        camera.stats["is_running"] = False
        logger.info("Pipeline stopped for %s", camera.identifier)


def _stop_camera_runtime(camera: CameraRuntime) -> None:
    camera.stop_event.set()
    if camera.thread and camera.thread.is_alive():
        camera.thread.join(timeout=2.0)


def _refresh_camera_states() -> None:
    db = SessionLocal()
    try:
        active_pairs = _load_active_camera_rows(db)
    finally:
        db.close()

    desired_ids = {str(device.id) for _, _, device in active_pairs}

    with _manager_lock:
        stale_ids = [device_id for device_id in _camera_states if device_id not in desired_ids]
        for device_id in stale_ids:
            _stop_camera_runtime(_camera_states[device_id])
            del _camera_states[device_id]

        for session_id, hall, device in active_pairs:
            device_id = str(device.id)
            runtime = _camera_states.get(device_id)
            source = (device.stream_url or "").strip()
            if runtime is not None and runtime.source == source and runtime.thread and runtime.thread.is_alive():
                continue

            if runtime is not None:
                _stop_camera_runtime(runtime)

            runtime = CameraRuntime(
                device_id=device_id,
                identifier=device.identifier,
                camera_name=_camera_display_name(device),
                hall_id=str(hall.id),
                hall_name=hall.name,
                source=source,
                session_id=str(session_id),
            )
            runtime.thread = threading.Thread(
                target=_run_pipeline,
                args=(runtime,),
                daemon=True,
                name=f"Stream-{device.identifier}",
            )
            _camera_states[device_id] = runtime
            runtime.thread.start()


def start_hall_monitoring(hall_id: uuid.UUID, session_id: uuid.UUID, db: Session) -> None:
    """Start monitoring all cameras in a specific hall for a session."""
    # 1. Update database
    assignment = db.query(Assignment).filter(
        Assignment.exam_session_id == session_id,
        Assignment.hall_id == hall_id
    ).first()
    if assignment:
        assignment.monitoring_started_at = _now_utc()
        # Clear ended_at so re-start after stop works correctly (1D fix)
        assignment.monitoring_ended_at = None
        
        # Auto-update session status to 'active' if it was 'scheduled' or 'completed'
        session = assignment.exam_session
        if session.status in ("scheduled", "completed"):
            session.status = "active"
            if not session.actual_start:
                session.actual_start = assignment.monitoring_started_at
                
        db.commit()

    # 2. Start cameras
    hall = db.query(Hall).filter(Hall.id == hall_id).options(selectinload(Hall.devices)).first()
    if not hall:
        return

    with _manager_lock:
        for device in hall.devices:
            if device.deleted_at or device.type != "camera":
                continue
            source = (device.stream_url or "").strip()
            if not source:
                continue
                
            device_id = str(device.id)
            if device_id in _camera_states:
                runtime = _camera_states[device_id]
                if runtime.thread and runtime.thread.is_alive():
                    continue
                _stop_camera_runtime(runtime)

            runtime = CameraRuntime(
                device_id=device_id,
                identifier=device.identifier,
                camera_name=_camera_display_name(device),
                hall_id=str(hall.id),
                hall_name=hall.name,
                source=source,
                session_id=str(session_id),
            )
            runtime.thread = threading.Thread(
                target=_run_pipeline,
                args=(runtime,),
                daemon=True,
                name=f"Stream-{device.identifier}",
            )
            _camera_states[device_id] = runtime
            runtime.thread.start()


def stop_hall_monitoring(hall_id: uuid.UUID, session_id: uuid.UUID, db: Session) -> None:
    """Stop monitoring all cameras in a specific hall."""
    # 1. Update database
    assignment = db.query(Assignment).filter(
        Assignment.exam_session_id == session_id,
        Assignment.hall_id == hall_id
    ).first()
    if assignment:
        assignment.monitoring_ended_at = _now_utc()
        
        # Check if all halls in this session have finished monitoring
        session = assignment.exam_session
        # Get all hall IDs for this session
        session_hall_ids = [h.id for h in session.halls]
        
        # Check if every hall in the session has at least one assignment that has ended monitoring
        # (and no assignments currently monitoring)
        monitoring_halls_count = db.query(Assignment).filter(
            Assignment.exam_session_id == session_id,
            Assignment.monitoring_started_at.isnot(None),
            Assignment.monitoring_ended_at.is_(None)
        ).count()
        
        ended_hall_ids = {
            row.hall_id
            for row in db.query(Assignment).filter(
                Assignment.exam_session_id == session_id,
                Assignment.monitoring_started_at.isnot(None),
                Assignment.monitoring_ended_at.isnot(None),
            ).all()
        }
        all_linked_halls_finished = bool(session_hall_ids) and all(
            hall_id in ended_hall_ids for hall_id in session_hall_ids
        )

        if monitoring_halls_count == 0 and all_linked_halls_finished:
            session.status = "completed"
            if not session.actual_end:
                session.actual_end = assignment.monitoring_ended_at
                
        db.commit()

    # 2. Stop cameras
    hall = db.query(Hall).filter(Hall.id == hall_id).options(selectinload(Hall.devices)).first()
    if not hall:
        return

    with _manager_lock:
        for device in hall.devices:
            device_id = str(device.id)
            if device_id in _camera_states:
                _stop_camera_runtime(_camera_states[device_id])
                del _camera_states[device_id]


async def resume_active_sessions() -> None:
    """Resume monitoring for all assignments that were active before server restart."""
    db = SessionLocal()
    try:
        # Find assignments where monitoring_started_at is set but monitoring_ended_at is NOT
        active_assignments = db.query(Assignment).filter(
            Assignment.monitoring_started_at.isnot(None),
            Assignment.monitoring_ended_at.is_(None)
        ).all()
        
        for assignment in active_assignments:
            logger.info("Resuming monitoring for Hall %s in Session %s", assignment.hall_id, assignment.exam_session_id)
            start_hall_monitoring(assignment.hall_id, assignment.exam_session_id, db)
    finally:
        db.close()


def startup_stream_manager() -> None:
    """Initialize the stream manager. Does not auto-start cameras anymore; 
    resuming is handled by resume_active_sessions during lifespan."""
    logger.info("Initializing monitoring stream manager (idle)")


def shutdown_stream_manager() -> None:
    logger.info("Stopping monitoring stream manager")
    with _manager_lock:
        runtimes = list(_camera_states.values())
        _camera_states.clear()
    for runtime in runtimes:
        _stop_camera_runtime(runtime)


def _force_restart_all_cameras() -> None:
    """Force restart all active camera runtimes (reconnect live, restart video)."""
    with _manager_lock:
        runtimes = list(_camera_states.values())
        _camera_states.clear()
    for runtime in runtimes:
        _stop_camera_runtime(runtime)
    _refresh_camera_states()


@router.post("/reload")
async def reload_monitoring(_=Depends(require_stream_user)) -> JSONResponse:
    _refresh_camera_states()
    return JSONResponse(
        {
            "status": "reloaded",
            "active_cameras": len([state for state in _camera_states.values() if state.stats["is_running"]]),
        }
    )


@router.post("/refresh")
async def refresh_monitoring(_=Depends(require_stream_user)) -> JSONResponse:
    _force_restart_all_cameras()
    return JSONResponse(
        {
            "status": "refreshed",
            "active_cameras": len([state for state in _camera_states.values() if state.stats["is_running"]]),
        }
    )


@router.get("/monitoring")
async def monitoring_layout(_=Depends(require_stream_user)) -> JSONResponse:
    db = SessionLocal()
    try:
        halls = _load_halls_with_devices(db)
        payload = {"halls": [_hall_to_payload(hall, db=db) for hall in halls]}
    finally:
        db.close()
    return JSONResponse(payload)


@router.get("/status")
async def pipeline_status(_=Depends(require_stream_user)) -> JSONResponse:
    try:
        with _manager_lock:
            # Use jsonable_encoder to ensure numpy / datetime / other types are converted
            cameras = {camera_id: jsonable_encoder(runtime.stats) for camera_id, runtime in _camera_states.items()}
        return JSONResponse({"cameras": cameras})
    except Exception:
        logger.exception("Failed to build pipeline status payload")
        raise HTTPException(status_code=500, detail="Failed to build pipeline status")


@router.get("/feed/{device_id}")
async def video_feed(device_id: str, _=Depends(require_stream_user)) -> StreamingResponse:
    runtime = _camera_states.get(device_id)
    if runtime is None:
        raise HTTPException(status_code=404, detail="Camera feed not available")

    def generate() -> Any:
        while not runtime.stop_event.is_set():
            with runtime.frame_lock:
                frame = runtime.latest_frame
            if frame is not None:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            else:
                time.sleep(0.1)

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")


@router.get("/alerts")
async def list_alerts(_=Depends(require_stream_user)) -> JSONResponse:
    with _alerts_lock:
        alerts = list(_alerts)
    return JSONResponse({"alerts": alerts})


@router.get("/alerts/snapshot/{path:path}")
async def get_alert_snapshot(path: str, _=Depends(require_stream_user)) -> FileResponse:
    safe_rel = Path(path)
    filepath = (ALERTS_DIR / safe_rel).resolve()
    if _ROOT_ALERTS_DIR not in filepath.parents or not filepath.exists():
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return FileResponse(str(filepath), media_type="image/jpeg")


@router.get("/alerts/video/{path:path}")
async def get_alert_video(path: str, _=Depends(require_stream_user)) -> FileResponse:
    safe_rel = Path(path)
    filepath = (ALERTS_DIR / safe_rel).resolve()
    if _ROOT_ALERTS_DIR not in filepath.parents or not filepath.exists():
        raise HTTPException(status_code=404, detail="Video not found")

    media_type = "video/mp4" if filepath.suffix.lower() == ".mp4" else "video/x-msvideo"
    return FileResponse(str(filepath), media_type=media_type)


@router.get("/alerts/report/{alert_id}.pdf")
async def get_alert_report_pdf(alert_id: str, _=Depends(require_stream_user)) -> Response:
    with _alerts_lock:
        alert = next((a for a in _alerts if a.get("id") == alert_id), None)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    try:
        from io import BytesIO

        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas as pdf_canvas
    except Exception:
        raise HTTPException(status_code=500, detail="PDF generator not available")

    buf = BytesIO()
    c = pdf_canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    x = 18 * mm
    y = height - 20 * mm

    def line(label: str, value: Any) -> None:
        nonlocal y
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x, y, f"{label}:")
        c.setFont("Helvetica", 11)
        c.drawString(x + 95, y, str(value) if value is not None else "—")
        y -= 8 * mm

    c.setTitle(f"Alert report {alert_id}")
    c.setFont("Helvetica-Bold", 16)
    c.drawString(x, y, "Thaqib Alert Report")
    y -= 12 * mm

    line("Event type", alert.get("event_type"))
    line("Severity", alert.get("severity"))
    line("Time", alert.get("timestamp"))
    line("Hall", alert.get("hall_name"))
    line("Camera", alert.get("camera_name"))
    line("Track ID", alert.get("track_id"))
    line("Snapshot", alert.get("snapshot_file"))
    line("Video", alert.get("video_file"))

    c.showPage()
    c.save()

    pdf_bytes = buf.getvalue()
    headers = {
        "Content-Disposition": f'attachment; filename="alert_{alert_id}.pdf"',
        "Cache-Control": "no-store",
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)



# ── Live camera controls ──────────────────────────────────────────────────────
# _run_pipeline() assigns runtime._pipeline after construction.
# Endpoints map 1:1 to the keyboard shortcuts in the visualizer bottom bar:
# [S] Monitor  [M] Remove-click  [C] Clear  [T] Neighbors  [R] Archive
# [D] Papers   [F] Phone         [L] Lines  [V] Quality    [G] Speed
# [W] Clock    [P] Panel

def _get_pipeline_or_404(device_id: str):
    runtime = _camera_states.get(device_id)
    if runtime is None:
        raise HTTPException(status_code=404, detail="Camera not running")
    pipeline = getattr(runtime, "_pipeline", None)
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not yet ready")
    return runtime, pipeline


# [V] video quality
@router.post("/cameras/{device_id}/quality")
async def toggle_camera_quality(device_id: str, _=Depends(require_stream_user)) -> JSONResponse:
    """[V] Cycle video quality LOW 50 -> MED 75 -> HIGH 90."""
    _, pipeline = _get_pipeline_or_404(device_id)
    pipeline.toggle_video_quality()
    q = pipeline._video_quality
    label = "HIGH" if q >= 90 else ("MED" if q >= 75 else "LOW")
    return JSONResponse({"quality": q, "label": label})


# [G] processing resolution
@router.post("/cameras/{device_id}/resolution")
async def toggle_camera_resolution(device_id: str, _=Depends(require_stream_user)) -> JSONResponse:
    """[G] Cycle processing resolution NATIVE -> 1080p -> 720p."""
    _, pipeline = _get_pipeline_or_404(device_id)
    label = pipeline.toggle_processing_resolution()
    return JSONResponse({"resolution": label})


# [R] archive mode
@router.post("/cameras/{device_id}/archive")
async def toggle_camera_archive(device_id: str, _=Depends(require_stream_user)) -> JSONResponse:
    """[R] Toggle archive overlay between raw and annotated."""
    _, pipeline = _get_pipeline_or_404(device_id)
    mode = pipeline.toggle_archive_mode()
    return JSONResponse({"archive_mode": mode})


# [S] select all students
@router.post("/cameras/{device_id}/select-all")
async def select_all_students(device_id: str, _=Depends(require_stream_user)) -> JSONResponse:
    """[S] Select (start monitoring) all currently tracked students."""
    _, pipeline = _get_pipeline_or_404(device_id)
    tracker = getattr(pipeline, "_tracker", None)
    all_ids = [t.track_id for t in getattr(tracker, "tracks", [])] if tracker else []
    pipeline.select_students(all_ids)
    return JSONResponse({"selected": all_ids, "count": len(all_ids)})


# [C] clear selection
@router.post("/cameras/{device_id}/clear-selection")
async def clear_student_selection(device_id: str, _=Depends(require_stream_user)) -> JSONResponse:
    """[C] Stop monitoring all students."""
    _, pipeline = _get_pipeline_or_404(device_id)
    pipeline.clear_selection()
    return JSONResponse({"selected": [], "count": 0})


# [M] deselect one student
@router.post("/cameras/{device_id}/deselect/{track_id}")
async def deselect_student(device_id: str, track_id: int, _=Depends(require_stream_user)) -> JSONResponse:
    """[M] Remove a specific student from monitoring."""
    _, pipeline = _get_pipeline_or_404(device_id)
    pipeline.remove_selection(track_id)
    return JSONResponse({"deselected": track_id})


# Visualizer display toggles — [T][D][F][L][W][P]
# These operate on runtime._visualizer. Returns state=null if no visualizer is attached
# (plain MJPEG mode without the VideoVisualizer annotation layer).

def _vis_toggle(device_id: str, toggle_method: str, state_attr: str) -> JSONResponse:
    runtime, _ = _get_pipeline_or_404(device_id)
    viz = getattr(runtime, "_visualizer", None)
    if viz is None:
        return JSONResponse({"state": None, "note": "visualizer not attached in MJPEG mode"})
    getattr(viz, toggle_method)()
    return JSONResponse({"state": getattr(viz, state_attr)})


@router.post("/cameras/{device_id}/toggle/neighbors")
async def toggle_neighbors(device_id: str, _=Depends(require_stream_user)) -> JSONResponse:
    """[T] Toggle neighbor graph lines on/off."""
    return _vis_toggle(device_id, "toggle_neighbors", "show_neighbors")


@router.post("/cameras/{device_id}/toggle/papers")
async def toggle_papers(device_id: str, _=Depends(require_stream_user)) -> JSONResponse:
    """[D] Toggle paper bounding-box display on/off."""
    return _vis_toggle(device_id, "toggle_paper", "show_paper")


@router.post("/cameras/{device_id}/toggle/phones")
async def toggle_phones(device_id: str, _=Depends(require_stream_user)) -> JSONResponse:
    """[F] Toggle phone bounding-box display on/off."""
    return _vis_toggle(device_id, "toggle_phone", "show_phone")


@router.post("/cameras/{device_id}/toggle/gaze-lines")
async def toggle_gaze_lines(device_id: str, _=Depends(require_stream_user)) -> JSONResponse:
    """[L] Toggle gaze-to-paper link lines on/off."""
    return _vis_toggle(device_id, "toggle_gaze_lines", "show_gaze_lines")


@router.post("/cameras/{device_id}/toggle/timestamp")
async def toggle_timestamp(device_id: str, _=Depends(require_stream_user)) -> JSONResponse:
    """[W] Toggle live timestamp overlay on/off."""
    return _vis_toggle(device_id, "toggle_timestamp", "show_timestamp")


@router.post("/cameras/{device_id}/toggle/panel")
async def toggle_panel(device_id: str, _=Depends(require_stream_user)) -> JSONResponse:
    """[P] Toggle control panel overlay on/off."""
    return _vis_toggle(device_id, "toggle_control_panel", "show_control_panel")


# GET controls — read current state of all toggles
@router.get("/cameras/{device_id}/controls")
async def get_camera_controls(device_id: str, _=Depends(require_stream_user)) -> JSONResponse:
    """Return current quality, resolution, archive mode, selection count, and visualizer state."""
    runtime = _camera_states.get(device_id)
    if runtime is None:
        raise HTTPException(status_code=404, detail="Camera not running")
    pipeline = getattr(runtime, "_pipeline", None)
    if pipeline is None:
        return JSONResponse({"quality": 75, "quality_label": "MED", "resolution": "NATIVE",
                             "archive_mode": "raw", "selected_count": 0, "visualizer": None})
    q = pipeline._video_quality
    q_label = "HIGH" if q >= 90 else ("MED" if q >= 75 else "LOW")
    res_label, _ = pipeline._processing_presets[pipeline._processing_preset_idx]
    viz = getattr(runtime, "_visualizer", None)
    viz_state = None
    if viz is not None:
        viz_state = {
            "show_neighbors": viz.show_neighbors,
            "show_paper": viz.show_paper,
            "show_phone": viz.show_phone,
            "show_gaze_lines": viz.show_gaze_lines,
            "show_timestamp": viz.show_timestamp,
            "show_control_panel": viz.show_control_panel,
        }
    tracker = getattr(pipeline, "_tracker", None)
    return JSONResponse({
        "quality": q,
        "quality_label": q_label,
        "resolution": res_label,
        "archive_mode": pipeline.archive_mode,
        "selected_count": len(getattr(pipeline, "_selected_ids", set())),
        "tracked_count": len(getattr(tracker, "tracks", [])) if tracker else 0,
        "visualizer": viz_state,
    })
