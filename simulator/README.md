# Camera Streaming Simulator

A Docker-based HTTP MJPEG streaming server for simulating IP cameras over WiFi/LAN. Designed for testing the Thaqib cheating detection system without requiring physical cameras.

## Features

- **HTTP MJPEG Streaming** - Stream video files as MJPEG over HTTP
- **Video Looping** - Automatically loops videos to simulate continuous live feed
- **Multi-Camera Support** - Configure multiple cameras with different video sources
- **Test Pattern Fallback** - Shows a test pattern when video file is missing
- **Quality Control** - Adjustable JPEG quality and frame skip for bandwidth control
- **Health Monitoring** - Health check endpoint for Docker/container orchestration
- **FastAPI-based** - Modern async Python web framework

## Quick Start

### 1. Prepare Video Files

Place your test video files in the `test_videos/` directory:

```bash
simulator/
├── test_videos/
│   ├── cam1.mp4      # For hall101_cam_front
│   ├── cam2.mp4      # For hall101_cam_back
│   └── cam3.mp4      # For hall101_cam_side
```

Video files should be named according to the camera mapping in `config.yaml`.

### 2. Start the Simulator

```bash
cd simulator
docker-compose -f docker-compose.simulator.yml up --build
```

The simulator will be available at `http://localhost:8000`.

### 3. Configure Thaqib to Use Simulator

#### Option A: Using seed_demo.py

```bash
cd ..  # Back to project root
.\venv\Scripts\python scripts\seed_demo.py --use-simulator
```

This updates the database to use simulator URLs like `http://localhost:8000/camera/hall101_cam_front/feed`.

#### Option B: Manual Configuration

Set environment variables before running seed_demo.py:

```bash
set SIMULATOR_HOST=192.168.1.10  # For multi-machine testing
set SIMULATOR_HTTP_PORT=8000
.\venv\Scripts\python scripts\seed_demo.py --use-simulator
```

Or use CLI arguments:

```bash
.\venv\Scripts\python scripts\seed_demo.py --use-simulator --simulator-host=192.168.1.10 --simulator-port=8000
```

### 4. Start Thaqib Backend

The backend will now read from the simulator streams instead of local files:

```bash
.\venv\Scripts\python -m src.thaqib.main
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | API info and available cameras |
| `GET /health` | Health check |
| `GET /cameras` | List all configured cameras |
| `GET /camera/{id}/feed` | MJPEG stream endpoint |
| `GET /camera/{id}/snapshot` | Single JPEG snapshot |
| `GET /camera/{id}/info` | Camera configuration info |
| `DELETE /camera/{id}/stream` | Stop and cleanup stream |

## Configuration

Edit `config.yaml` to customize camera mappings:

```yaml
cameras:
  hall101_cam_front:
    video_path: /app/videos/cam1.mp4
    fps: 30
    resolution: [1280, 720]
    
  hall101_cam_back:
    video_path: /app/videos/cam2.mp4
    fps: 30
    resolution: [1280, 720]

server:
  host: 0.0.0.0
  port: 8000
  jpeg_quality: 85
  frame_skip: 1  # 1 = every frame, 2 = every 2nd frame
```

## Multi-Machine Testing

For testing across different machines on the same network:

### Machine 1 (Simulator) - IP: 192.168.1.10

```bash
cd simulator
# Edit docker-compose.simulator.yml to expose on all interfaces
docker-compose -f docker-compose.simulator.yml up
```

### Machine 2 (Thaqib Backend) - IP: 192.168.1.20

```bash
set SIMULATOR_HOST=192.168.1.10
.\venv\Scripts\python scripts\seed_demo.py --use-simulator
.\venv\Scripts\python -m src.thaqib.main
```

## Testing Stream URLs

You can test the streams using OpenCV:

```python
import cv2

# Test HTTP MJPEG stream
cap = cv2.VideoCapture("http://localhost:8000/camera/hall101_cam_front/feed")

while True:
    ret, frame = cap.read()
    if ret:
        cv2.imshow("Simulated Camera", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
```

Or use a browser/VLC to view the stream directly.

## Troubleshooting

### Video file not found
- The simulator will show a test pattern with the camera ID
- Check that video files exist in the mounted `test_videos` directory
- Verify the path mapping in `config.yaml`

### Port already in use
- Change the host port in `docker-compose.simulator.yml`: `"8001:8000"`
- Update `SIMULATOR_HTTP_PORT` environment variable accordingly

### Cannot access from another machine
- Ensure the simulator container binds to `0.0.0.0` (default in config)
- Check firewall settings on the host machine
- Verify the host IP address is correct

## Architecture

```
┌─────────────────┐      WiFi/LAN      ┌─────────────────┐
│   Simulator     │  ◄────────────────►  │  Thaqib Backend │
│   (Docker)      │   HTTP MJPEG stream  │   (Python)      │
│                 │                      │                 │
│ • Serves videos │                      │ • cv2.VideoCapture
│   as streams    │                      │   ("http://...")│
│ • Loops videos  │                      │ • Runs detection│
│ • Test patterns │                      │                 │
└─────────────────┘                      └─────────────────┘
```

## No DB Changes Required

The simulator works with the existing `stream_url` field in the database:

| Environment | stream_url Value |
|-------------|------------------|
| Production | `rtsp://192.168.1.100:554/stream` |
| Local Testing | `C:\Users\...\video.mp4` |
| Simulator | `http://localhost:8000/camera/hall101_cam_front/feed` |
