"""
Camera Streaming Simulator
Serves video files as HTTP MJPEG streams for testing the Thaqib cheating detection system.
"""

from __future__ import annotations

import asyncio
import io
import logging
import threading
import time
from pathlib import Path
from typing import Dict, Optional

import cv2
import numpy as np
import yaml
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load configuration
CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config() -> dict:
    """Load camera configuration from YAML file."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            return yaml.safe_load(f) or {}
    return {"cameras": {}, "server": {"jpeg_quality": 85, "frame_skip": 1}}


CONFIG = load_config()
CAMERA_CONFIGS = CONFIG.get("cameras", {})
SERVER_CONFIG = CONFIG.get("server", {"jpeg_quality": 85, "frame_skip": 1})

app = FastAPI(title="Camera Streaming Simulator", version="1.0.0")

# Global state
active_streams: Dict[str, "VideoStreamer"] = {}
stream_lock = threading.Lock()


class VideoStreamer:
    """Handles video streaming with looping and frame buffering."""

    def __init__(
        self,
        camera_id: str,
        video_path: str,
        fps: int = 30,
        resolution: Optional[tuple] = None,
        jpeg_quality: int = 85,
        frame_skip: int = 1,
    ):
        self.camera_id = camera_id
        self.video_path = video_path
        self.fps = fps
        self.resolution = resolution
        self.jpeg_quality = jpeg_quality
        self.frame_skip = frame_skip
        self.frame_interval = 1.0 / fps

        self.cap: Optional[cv2.VideoCapture] = None
        self.is_running = False
        self.frame_count = 0
        self.current_frame: Optional[np.ndarray] = None
        self.last_frame_time = 0.0

        self._open_video()

    def _open_video(self) -> bool:
        """Open the video file."""
        if self.cap is not None:
            self.cap.release()

        if not Path(self.video_path).exists():
            logger.error(f"Video file not found: {self.video_path}")
            # Create a test pattern frame
            self._create_test_pattern()
            return False

        self.cap = cv2.VideoCapture(self.video_path)
        if not self.cap.isOpened():
            logger.error(f"Failed to open video: {self.video_path}")
            self._create_test_pattern()
            return False

        logger.info(f"Opened video for camera {self.camera_id}: {self.video_path}")
        return True

    def _create_test_pattern(self) -> None:
        """Create a test pattern when video file is not available."""
        width, height = self.resolution or (1280, 720)
        # Create a colored test pattern
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        # Add gradient background
        for y in range(height):
            frame[y, :] = [int(255 * y / height), 100, int(255 * (1 - y / height))]
        # Add text
        cv2.putText(
            frame,
            f"Camera: {self.camera_id}",
            (50, height // 2 - 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            2,
            (255, 255, 255),
            3,
        )
        cv2.putText(
            frame,
            "No video file available",
            (50, height // 2 + 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.5,
            (255, 255, 255),
            2,
        )
        self.current_frame = frame
        self.is_running = True

    def read_frame(self) -> Optional[np.ndarray]:
        """Read the next frame from video or return test pattern."""
        if self.cap is None or not self.cap.isOpened():
            # Return the test pattern frame
            return self.current_frame

        ret, frame = self.cap.read()

        if not ret:
            # Loop video back to start
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
            if not ret:
                logger.warning(f"Failed to read frame from {self.camera_id}")
                return self.current_frame

        # Apply frame skipping
        self.frame_count += 1
        if self.frame_count % self.frame_skip != 0:
            return self.current_frame

        # Resize if needed
        if self.resolution and frame is not None:
            target_width, target_height = self.resolution
            if frame.shape[1] != target_width or frame.shape[0] != target_height:
                frame = cv2.resize(frame, (target_width, target_height))

        self.current_frame = frame
        return frame

    def encode_frame(self, frame: np.ndarray) -> bytes:
        """Encode frame to JPEG bytes."""
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality]
        success, encoded = cv2.imencode(".jpg", frame, encode_params)
        if success:
            return encoded.tobytes()
        return b""

    def release(self) -> None:
        """Release video capture resources."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.is_running = False


def get_or_create_streamer(camera_id: str) -> VideoStreamer:
    """Get existing streamer or create new one for camera."""
    with stream_lock:
        if camera_id not in active_streams:
            config = CAMERA_CONFIGS.get(camera_id, {})
            video_path = config.get("video_path", f"/app/videos/{camera_id}.mp4")
            fps = config.get("fps", 30)
            resolution = config.get("resolution", [1280, 720])

            streamer = VideoStreamer(
                camera_id=camera_id,
                video_path=video_path,
                fps=fps,
                resolution=tuple(resolution) if resolution else None,
                jpeg_quality=SERVER_CONFIG.get("jpeg_quality", 85),
                frame_skip=SERVER_CONFIG.get("frame_skip", 1),
            )
            active_streams[camera_id] = streamer

        return active_streams[camera_id]


async def generate_mjpeg_stream(camera_id: str):
    """Generate MJPEG stream for a camera."""
    streamer = get_or_create_streamer(camera_id)
    boundary = "--frameboundary"

    try:
        while True:
            frame = streamer.read_frame()
            if frame is None:
                await asyncio.sleep(0.1)
                continue

            jpeg_bytes = streamer.encode_frame(frame)
            if not jpeg_bytes:
                await asyncio.sleep(0.1)
                continue

            # Yield MJPEG frame
            yield (
                f"{boundary}\r\n"
                f"Content-Type: image/jpeg\r\n"
                f"Content-Length: {len(jpeg_bytes)}\r\n"
                f"\r\n"
            ).encode() + jpeg_bytes + b"\r\n"

            # Control frame rate
            await asyncio.sleep(streamer.frame_interval)

    except asyncio.CancelledError:
        logger.info(f"Stream cancelled for camera {camera_id}")
        raise
    except Exception as e:
        logger.error(f"Error in stream for {camera_id}: {e}")
        raise


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "service": "Camera Streaming Simulator",
        "version": "1.0.0",
        "cameras": list(CAMERA_CONFIGS.keys()),
        "endpoints": {
            "health": "/health",
            "camera_list": "/cameras",
            "mjpeg_stream": "/camera/{camera_id}/feed",
            "snapshot": "/camera/{camera_id}/snapshot",
            "camera_info": "/camera/{camera_id}/info",
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "active_streams": len(active_streams),
        "cameras_configured": len(CAMERA_CONFIGS),
    }


@app.get("/cameras")
async def list_cameras():
    """List all configured cameras."""
    cameras = []
    for cam_id, config in CAMERA_CONFIGS.items():
        video_path = config.get("video_path", "")
        exists = Path(video_path).exists()
        cameras.append({
            "id": cam_id,
            "video_path": video_path,
            "video_exists": exists,
            "fps": config.get("fps", 30),
            "resolution": config.get("resolution", [1280, 720]),
            "stream_url": f"/camera/{cam_id}/feed",
        })
    return {"cameras": cameras, "count": len(cameras)}


@app.get("/camera/{camera_id}/feed")
async def camera_feed(
    camera_id: str,
    quality: Optional[int] = Query(None, ge=1, le=100, description="JPEG quality (1-100)"),
):
    """Get MJPEG stream for a specific camera."""
    if camera_id not in CAMERA_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found")

    # Update quality if specified
    if quality is not None:
        with stream_lock:
            if camera_id in active_streams:
                active_streams[camera_id].jpeg_quality = quality

    return StreamingResponse(
        generate_mjpeg_stream(camera_id),
        media_type="multipart/x-mixed-replace; boundary=--frameboundary",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/camera/{camera_id}/snapshot")
async def camera_snapshot(camera_id: str):
    """Get a single JPEG snapshot from a camera."""
    if camera_id not in CAMERA_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found")

    streamer = get_or_create_streamer(camera_id)
    frame = streamer.read_frame()

    if frame is None:
        raise HTTPException(status_code=503, detail="Camera not available")

    jpeg_bytes = streamer.encode_frame(frame)

    return StreamingResponse(
        io.BytesIO(jpeg_bytes),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/camera/{camera_id}/info")
async def camera_info(camera_id: str):
    """Get information about a specific camera."""
    if camera_id not in CAMERA_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found")

    config = CAMERA_CONFIGS[camera_id]
    video_path = config.get("video_path", "")

    info = {
        "id": camera_id,
        "video_path": video_path,
        "video_exists": Path(video_path).exists(),
        "fps": config.get("fps", 30),
        "resolution": config.get("resolution", [1280, 720]),
        "stream_url": f"/camera/{camera_id}/feed",
        "snapshot_url": f"/camera/{camera_id}/snapshot",
        "http_stream": f"http://{{host}}:8000/camera/{camera_id}/feed",
    }

    return info


@app.delete("/camera/{camera_id}/stream")
async def stop_stream(camera_id: str):
    """Stop and cleanup a camera stream."""
    with stream_lock:
        if camera_id in active_streams:
            active_streams[camera_id].release()
            del active_streams[camera_id]
            return {"message": f"Stream for {camera_id} stopped"}

    raise HTTPException(status_code=404, detail=f"No active stream for camera '{camera_id}'")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup all streams on shutdown."""
    logger.info("Shutting down, releasing all streams...")
    with stream_lock:
        for streamer in active_streams.values():
            streamer.release()
        active_streams.clear()


if __name__ == "__main__":
    import uvicorn

    host = SERVER_CONFIG.get("host", "0.0.0.0")
    port = SERVER_CONFIG.get("port", 8000)

    uvicorn.run(app, host=host, port=port)
