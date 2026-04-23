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
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from sqlalchemy.orm import Session, selectinload

from src.thaqib.db.database import SessionLocal
from src.thaqib.db.models.infrastructure import Device, Hall

logger = logging.getLogger(__name__)

router = APIRouter()

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
        created_at = datetime.now()

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
            if datetime.fromtimestamp(mtime) < created_at:
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


def _hall_to_payload(hall: Hall) -> dict[str, Any]:
    camera_devices = [device for device in hall.devices if device.type == "camera"]
    mic_devices = [device for device in hall.devices if device.type == "microphone"]
    cameras = [
        _serialize_camera(device, hall, _camera_states.get(str(device.id)))
        for device in camera_devices
    ]
    return {
        "id": str(hall.id),
        "name": hall.name,
        "status": hall.status,
        "building": hall.building,
        "floor": hall.floor,
        "capacity": hall.capacity,
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
        .options(selectinload(Hall.devices))
        .order_by(Hall.name.asc())
        .all()
    )


def _load_active_camera_rows(db: Session) -> list[tuple[Hall, Device]]:
    halls = _load_halls_with_devices(db)
    active_pairs: list[tuple[Hall, Device]] = []
    for hall in halls:
        if hall.status != "ready":
            continue
        for device in hall.devices:
            if device.type != "camera":
                continue
            source = (device.stream_url or "").strip()
            if not source:
                continue
            active_pairs.append((hall, device))
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


def _run_pipeline(camera: CameraRuntime) -> None:
    from thaqib.video.pipeline import VideoPipeline, StudentState

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

        created_at = datetime.now().isoformat()
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

    pipeline = VideoPipeline(source=parsed_source, detection_interval=1.0, on_alert=on_alert)

    try:
        started = pipeline.start()
        if not started:
            camera.stats["is_running"] = False
            camera.stats["last_error"] = f"Failed to open camera source: {camera.source}"
            camera.stats["last_error_at"] = datetime.now().isoformat()
            logger.error("Camera %s failed to open source: %s", camera.identifier, camera.source)
            return

        camera.stats["is_running"] = True
        camera.stats["last_error"] = None
        camera.stats["last_error_at"] = None

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
                continue

            ok, jpeg = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 60])
            if not ok:
                continue

            with camera.frame_lock:
                camera.latest_frame = jpeg.tobytes()

            camera.stats.update(
                {
                    "is_running": True,
                    "fps": round(1000 / max(frame_data.processing_time_ms, 1), 1),
                    "tracked_count": frame_data.tracked_count,
                    "selected_count": frame_data.selected_count,
                    "frame_index": frame_data.frame_index,
                }
            )
            last_emit = now
    except Exception:
        logger.exception("Pipeline error for camera %s", camera.identifier)
        camera.stats["last_error"] = "Pipeline error (see server logs)"
        camera.stats["last_error_at"] = datetime.now().isoformat()
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

    desired_ids = {str(device.id) for _, device in active_pairs}

    with _manager_lock:
        stale_ids = [device_id for device_id in _camera_states if device_id not in desired_ids]
        for device_id in stale_ids:
            _stop_camera_runtime(_camera_states[device_id])
            del _camera_states[device_id]

        for hall, device in active_pairs:
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
            )
            runtime.thread = threading.Thread(
                target=_run_pipeline,
                args=(runtime,),
                daemon=True,
                name=f"Stream-{device.identifier}",
            )
            _camera_states[device_id] = runtime
            runtime.thread.start()


def startup_stream_manager() -> None:
    logger.info("Starting monitoring stream manager")
    _refresh_camera_states()


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
async def reload_monitoring() -> JSONResponse:
    _refresh_camera_states()
    return JSONResponse(
        {
            "status": "reloaded",
            "active_cameras": len([state for state in _camera_states.values() if state.stats["is_running"]]),
        }
    )


@router.post("/refresh")
async def refresh_monitoring() -> JSONResponse:
    _force_restart_all_cameras()
    return JSONResponse(
        {
            "status": "refreshed",
            "active_cameras": len([state for state in _camera_states.values() if state.stats["is_running"]]),
        }
    )


@router.get("/monitoring")
async def monitoring_layout() -> JSONResponse:
    db = SessionLocal()
    try:
        halls = _load_halls_with_devices(db)
        payload = {"halls": [_hall_to_payload(hall) for hall in halls]}
    finally:
        db.close()
    return JSONResponse(payload)


@router.get("/status")
async def pipeline_status() -> JSONResponse:
    with _manager_lock:
        cameras = {camera_id: dict(runtime.stats) for camera_id, runtime in _camera_states.items()}
    return JSONResponse({"cameras": cameras})


@router.get("/feed/{device_id}")
async def video_feed(device_id: str) -> StreamingResponse:
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
async def list_alerts() -> JSONResponse:
    with _alerts_lock:
        alerts = list(_alerts)
    return JSONResponse({"alerts": alerts})


@router.get("/alerts/snapshot/{path:path}")
async def get_alert_snapshot(path: str) -> FileResponse:
    safe_rel = Path(path)
    filepath = (ALERTS_DIR / safe_rel).resolve()
    if _ROOT_ALERTS_DIR not in filepath.parents or not filepath.exists():
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return FileResponse(str(filepath), media_type="image/jpeg")


@router.get("/alerts/video/{path:path}")
async def get_alert_video(path: str) -> FileResponse:
    safe_rel = Path(path)
    filepath = (ALERTS_DIR / safe_rel).resolve()
    if _ROOT_ALERTS_DIR not in filepath.parents or not filepath.exists():
        raise HTTPException(status_code=404, detail="Video not found")

    media_type = "video/mp4" if filepath.suffix.lower() == ".mp4" else "video/x-msvideo"
    return FileResponse(str(filepath), media_type=media_type)


@router.get("/alerts/report/{alert_id}.pdf")
async def get_alert_report_pdf(alert_id: str) -> Response:
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
