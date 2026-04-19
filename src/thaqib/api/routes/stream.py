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
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from sqlalchemy.orm import Session, selectinload

from src.thaqib.db.database import SessionLocal
from src.thaqib.db.models.infrastructure import Device, Hall

logger = logging.getLogger(__name__)

router = APIRouter()

ALERTS_DIR = Path("./alerts")
ALERTS_DIR.mkdir(exist_ok=True)
_ROOT_ALERTS_DIR = ALERTS_DIR.resolve()


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


def _draw_annotations(frame: np.ndarray, pipeline_frame: Any) -> np.ndarray:
    annotated = frame.copy()

    for track in pipeline_frame.tracking_result.tracks:
        if not track.is_selected:
            x1, y1, x2, y2 = track.bbox
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (128, 128, 128), 2)
            cv2.putText(
                annotated,
                f"ID:{track.track_id}",
                (x1, y1 - 10),
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

        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            annotated,
            f"ID:{state.track_id} [{status}]",
            (x1, y1 - 10),
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
                arrow_length = 50
                yaw = float(getattr(pose, "yaw", 0.0))
                pitch = float(getattr(pose, "pitch", 0.0))
                yaw_rad = np.radians(yaw)
                end_x = int(cx + arrow_length * np.cos(yaw_rad))
                end_y = int(cy + arrow_length * np.sin(yaw_rad))
                cv2.arrowedLine(annotated, (cx, cy), (end_x, end_y), (255, 0, 255), 2)
                cv2.putText(
                    annotated,
                    f"Y:{yaw:.0f} P:{pitch:.0f}",
                    (x1, y2 + 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 0, 255),
                    1,
                )

        spatial_context = getattr(state, "spatial_context", None)
        if spatial_context is not None:
            for risk in getattr(spatial_context, "risk_angles", []) or []:
                cx, cy = state.center
                angle_rad = np.radians(risk.center_angle)
                end_x = int(cx + 40 * np.cos(angle_rad))
                end_y = int(cy + 40 * np.sin(angle_rad))
                cv2.line(annotated, (cx, cy), (end_x, end_y), (0, 165, 255), 1)

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
            (10, 30 + i * 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )
    return annotated


def _save_alert_snapshot(frame: np.ndarray, camera: CameraRuntime, track_id: int) -> str:
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_camera_id = camera.device_id.replace("-", "")
    filename = f"alert_{safe_camera_id}_{track_id}_{timestamp_str}_{uuid.uuid4().hex[:6]}.jpg"
    filepath = ALERTS_DIR / filename
    cv2.imwrite(str(filepath), frame)
    logger.info("Alert snapshot saved: %s", filepath)
    return filename


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

        filename = _save_alert_snapshot(frame_img, camera, state.track_id)
        alert_data = {
            "id": str(uuid.uuid4()),
            "camera_id": camera.device_id,
            "camera_identifier": camera.identifier,
            "camera_name": camera.camera_name,
            "hall_id": camera.hall_id,
            "hall_name": camera.hall_name,
            "track_id": state.track_id,
            "looking_at": state.looking_at_neighbor_id,
            "event_type": "غش من الجار",
            "severity": "high",
            "timestamp": datetime.now().isoformat(),
            "snapshot_file": filename,
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
            state.looking_at_neighbor_id,
        )

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

            annotated = _draw_annotations(frame_data.frame, frame_data)
            ok, jpeg = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
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
            time.sleep(0.04)
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


@router.post("/reload")
async def reload_monitoring() -> JSONResponse:
    _refresh_camera_states()
    return JSONResponse(
        {
            "status": "reloaded",
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


@router.get("/alerts/snapshot/{filename}")
async def get_alert_snapshot(filename: str) -> FileResponse:
    safe_name = Path(filename).name
    filepath = (ALERTS_DIR / safe_name).resolve()
    if _ROOT_ALERTS_DIR not in filepath.parents or not filepath.exists():
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return FileResponse(str(filepath), media_type="image/jpeg")
