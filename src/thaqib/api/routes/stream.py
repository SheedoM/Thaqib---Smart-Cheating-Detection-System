"""
Video streaming routes for the monitoring dashboard.

Replaces demo_video.py for web: runs the same VideoPipeline but streams
annotated frames to the browser via MJPEG (multipart HTTP) instead of cv2.imshow().
"""

import asyncio
import logging
import os
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Global pipeline state (singleton for the demo — one pipeline at a time)
# ---------------------------------------------------------------------------

_pipeline_thread: Optional[threading.Thread] = None
_pipeline_running = False
_latest_frame: Optional[bytes] = None
_frame_lock = threading.Lock()
_alerts: list[dict] = []
_alerts_lock = threading.Lock()
_pipeline_stats: dict = {
    "is_running": False,
    "fps": 0,
    "tracked_count": 0,
    "selected_count": 0,
    "frame_index": 0,
    "alert_count": 0,
}

# Alerts folder
ALERTS_DIR = Path("./alerts")
ALERTS_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Pipeline thread (runs the same code as demo_video.py)
# ---------------------------------------------------------------------------

def _draw_annotations(frame: np.ndarray, pipeline_frame) -> np.ndarray:
    """Draw annotations on frame — same as demo_video.py draw_annotations."""
    annotated = frame.copy()

    # Draw all tracks (unselected in gray)
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

    # Draw selected students with full annotations
    for state in pipeline_frame.student_states:
        x1, y1, x2, y2 = state.bbox

        # Color based on status
        if state.is_looking_at_neighbor:
            color = (0, 0, 255)  # Red for suspicious
            status = f"LOOKING AT #{state.looking_at_neighbor_id}"
        else:
            color = (0, 255, 0)  # Green for normal
            status = "OK"

        # Draw bounding box
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

        # Draw ID and status
        cv2.putText(
            annotated,
            f"ID:{state.track_id} [{status}]",
            (x1, y1 - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
        )

        # Draw head pose if available
        if state.head_pose and state.head_pose.has_pose:
            pose = state.head_pose.pose
            cx, cy = state.center

            # Draw yaw direction arrow
            arrow_length = 50
            yaw_rad = np.radians(pose.yaw)
            end_x = int(cx + arrow_length * np.cos(yaw_rad))
            end_y = int(cy + arrow_length * np.sin(yaw_rad))
            cv2.arrowedLine(annotated, (cx, cy), (end_x, end_y), (255, 0, 255), 2)

            # Draw pose text
            cv2.putText(
                annotated,
                f"Y:{pose.yaw:.0f} P:{pose.pitch:.0f}",
                (x1, y2 + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 0, 255),
                1,
            )

        # Draw risk angles if available
        if state.spatial_context:
            for risk in state.spatial_context.risk_angles:
                cx, cy = state.center
                angle_rad = np.radians(risk.center_angle)
                end_x = int(cx + 40 * np.cos(angle_rad))
                end_y = int(cy + 40 * np.sin(angle_rad))
                cv2.line(annotated, (cx, cy), (end_x, end_y), (0, 165, 255), 1)

    # Draw info panel
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


def _save_alert_snapshot(frame: np.ndarray, state) -> str:
    """Save an alert snapshot to the alerts directory and return the filename."""
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"alert_{state.track_id}_{timestamp_str}_{uuid.uuid4().hex[:6]}.jpg"
    filepath = ALERTS_DIR / filename
    cv2.imwrite(str(filepath), frame)
    logger.info(f"Alert snapshot saved: {filepath}")
    return filename


def _run_pipeline(source: str):
    """Run the video pipeline in a background thread."""
    global _pipeline_running, _latest_frame, _pipeline_stats

    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

    from thaqib.video.pipeline import VideoPipeline, StudentState

    # Parse source — try as int (webcam) first
    try:
        parsed_source = int(source)
    except ValueError:
        parsed_source = source

    logger.info(f"Starting pipeline with source: {parsed_source}")

    auto_selected = False

    def on_alert(state: StudentState):
        """Callback when suspicious behavior detected — save snapshot + record alert."""
        nonlocal _latest_frame
        with _frame_lock:
            current_frame = _latest_frame

        if current_frame is not None:
            # Decode the JPEG back to save a proper snapshot
            nparr = np.frombuffer(current_frame, np.uint8)
            frame_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame_img is not None:
                filename = _save_alert_snapshot(frame_img, state)

                alert_data = {
                    "id": str(uuid.uuid4()),
                    "track_id": state.track_id,
                    "looking_at": state.looking_at_neighbor_id,
                    "event_type": "غش من الجار",
                    "severity": "high",
                    "timestamp": datetime.now().isoformat(),
                    "snapshot_file": filename,
                    "location": f"الطالب رقم {state.track_id}",
                }

                with _alerts_lock:
                    _alerts.insert(0, alert_data)
                    # Keep last 50 alerts
                    if len(_alerts) > 50:
                        _alerts.pop()

                _pipeline_stats["alert_count"] = len(_alerts)
                logger.warning(
                    f"ALERT: Student {state.track_id} looking at neighbor {state.looking_at_neighbor_id}"
                )

    pipeline = VideoPipeline(
        source=parsed_source,
        detection_interval=1.0,
        on_alert=on_alert,
    )

    try:
        with pipeline:
            _pipeline_stats["is_running"] = True
            for frame_data in pipeline.run():
                if not _pipeline_running:
                    break

                # Auto-select all students after a few frames
                if not auto_selected and frame_data.frame_index > 5:
                    all_ids = [t.track_id for t in frame_data.tracking_result.tracks]
                    if all_ids:
                        pipeline.select_students(all_ids)
                        auto_selected = True
                        logger.info(f"Auto-selected {len(all_ids)} students for monitoring")

                # Draw annotations (same as demo_video.py)
                annotated = _draw_annotations(frame_data.frame, frame_data)

                # Encode as JPEG
                _, jpeg = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])

                with _frame_lock:
                    _latest_frame = jpeg.tobytes()

                # Update stats
                _pipeline_stats.update({
                    "fps": round(1000 / max(frame_data.processing_time_ms, 1), 1),
                    "tracked_count": frame_data.tracked_count,
                    "selected_count": frame_data.selected_count,
                    "frame_index": frame_data.frame_index,
                })

                # Limit frame rate to ~25fps to not overload
                time.sleep(0.04)

    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)
    finally:
        _pipeline_running = False
        _pipeline_stats["is_running"] = False
        logger.info("Pipeline stopped")


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@router.get("/start")
async def start_pipeline(
    source: str = Query(
        default=r"C:\Users\shady\Downloads\IMG_5123.MOV",
        description="Video source: webcam index (0) or file path"
    )
):
    """Start the video pipeline."""
    global _pipeline_thread, _pipeline_running

    if _pipeline_running:
        return JSONResponse({"status": "already_running", "message": "Pipeline is already running"})

    _pipeline_running = True
    _pipeline_thread = threading.Thread(target=_run_pipeline, args=(source,), daemon=True)
    _pipeline_thread.start()

    return JSONResponse({"status": "started", "message": "Pipeline started", "source": source})


@router.get("/stop")
async def stop_pipeline():
    """Stop the video pipeline."""
    global _pipeline_running
    _pipeline_running = False
    return JSONResponse({"status": "stopped", "message": "Pipeline stopping..."})


@router.get("/status")
async def pipeline_status():
    """Get pipeline status and stats."""
    return JSONResponse(_pipeline_stats)


@router.get("/feed")
async def video_feed():
    """
    MJPEG video stream endpoint.
    
    The browser shows this with: <img src="http://localhost:8000/api/stream/feed" />
    This is the web equivalent of cv2.imshow() — each frame is sent as a JPEG
    in a multipart HTTP response.
    """
    def generate():
        while _pipeline_running:
            with _frame_lock:
                frame = _latest_frame

            if frame is not None:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                )
            else:
                # Send a blank frame placeholder while waiting for pipeline to start
                time.sleep(0.1)

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/alerts")
async def list_alerts():
    """List all recent alerts with their snapshot files."""
    with _alerts_lock:
        return JSONResponse({"alerts": list(_alerts)})


@router.get("/alerts/snapshot/{filename}")
async def get_alert_snapshot(filename: str):
    """Serve an alert snapshot image."""
    filepath = ALERTS_DIR / filename
    if not filepath.exists():
        return JSONResponse({"error": "Snapshot not found"}, status_code=404)
    return FileResponse(str(filepath), media_type="image/jpeg")
