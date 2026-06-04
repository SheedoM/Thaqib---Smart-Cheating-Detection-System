# Thaqib — Smart Cheating Detection System

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/Version-1.0.0-brightgreen.svg)]()
[![Status](https://img.shields.io/badge/Status-Production%20Ready-success.svg)]()

**Thaqib** (Arabic: ثاقب, meaning "piercing" or "sharp-sighted") is an AI-powered, real-time exam monitoring system. It uses computer vision to detect cheating behaviors — gaze-based paper copying and unauthorized phone usage — and automatically generates evidence video clips.

---

## Key Capabilities

| Feature                           | Description                                                                                                                                                                                                   |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Gaze-Based Cheating Detection** | Tracks each student's head pose and iris direction via MediaPipe, calculates gaze angles toward neighboring students' papers, and flags sustained suspicious looking (>2 seconds).                            |
| **Phone Detection**               | Detects mobile phones anywhere in the frame (independent of student tracking) and generates alert clips with red bounding boxes.                                                                              |
| **Automatic Evidence Recording**  | When cheating is detected, the system saves an MP4 clip containing 2 seconds before the event, the event itself, and 2 seconds after — annotated with RED (cheater) and YELLOW (target paper) bounding boxes. |
| **Continuous Archive**            | The full camera feed is continuously recorded to `archive/` for post-exam review.                                                                                                                             |
| **Interactive Controls**          | Real-time keyboard shortcuts for student selection, display toggles, quality presets, and archive mode switching.                                                                                             |
| **Re-Identification**             | Face-based ReID ensures students retain their identity across temporary occlusions using OSNet appearance embeddings.                                                                                         |
| **Audio Cheating Detection**      | Multi-microphone audio analysis detects localized speech (whispers) vs. global sounds using energy-ratio discrimination, Silero VAD, and Whisper STT with keyword matching. Saves forensic evidence (WAV + JSON). See [Audio README](src/thaqib/audio/README.md) for details. |

---

## Architecture

```
Camera (USB / RTSP / Video File)
    │
    ▼
┌──────────────────────────────────────────────────┐
│                  VideoPipeline                    │
│                                                   │
│  ┌───────────┐   ┌────────────┐   ┌───────────┐ │
│  │  YOLO     │   │  YOLO      │   │  BoT-SORT │ │
│  │  Person   │   │  Tools     │   │  Tracker  │ │
│  │  Detector │   │  Detector  │   │           │ │
│  └─────┬─────┘   └─────┬──────┘   └─────┬─────┘ │
│        │               │               │        │
│        ▼               ▼               ▼        │
│  ┌──────────────────────────────────────────┐   │
│  │         GlobalStudentRegistry            │   │
│  │  (track state, neighbors, papers, gaze)  │   │
│  └─────────────────┬────────────────────────┘   │
│                    │                             │
│       ┌────────────┼───────────────┐            │
│       ▼            ▼               ▼            │
│  ┌─────────┐ ┌───────────┐ ┌─────────────┐    │
│  │FaceMesh │ │ Neighbor  │ │  Cheating   │    │
│  │Extractor│ │ Computer  │ │  Evaluator  │    │
│  │(MP pool)│ │ (k=6 NN)  │ │ (gaze+angle)│    │
│  └─────────┘ └───────────┘ └──────┬──────┘    │
│                                    │           │
│                     ┌──────────────┼──────┐    │
│                     ▼              ▼      ▼    │
│               ┌──────────┐  ┌────────┐  ┌───┐ │
│               │  Alert   │  │ Phone  │  │HUD│ │
│               │ Recorder │  │ Alert  │  │   │ │
│               └──────────┘  └────────┘  └───┘ │
└──────────────────────────────────────────────────┘
    │                │              │
    ▼                ▼              ▼
 alerts/          alerts/        cv2.imshow()
 gaze_alert_*.mp4  phone_alert_*.mp4
```

---

## Quick Start

### Prerequisites

- Python 3.10 or higher
- Node.js 18+ and npm
- Docker & Docker Compose (for camera simulator)
- NVIDIA GPU with CUDA (recommended; CPU works but slower)
- Webcam, IP camera (RTSP), or pre-recorded video file

### Installation

```bash
git clone https://github.com/SheedoM/Thaqib---Smart-Cheating-Detection-System.git
cd Thaqib---Smart-Cheating-Detection-System

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/macOS

# Install Python dependencies
pip install -e .
pip install -e ".[gpu]"  # For GPU support

# Install frontend dependencies
cd frontend
npm install
cd ..

# Copy environment config
cp .env.example .env
```

### Running the Full System

The system has 3 components: **Camera Simulator**, **Backend**, and **Frontend**.

#### 1. Start the Database

```bash
docker-compose up -d db
```

#### 2. Start the Camera Simulator (for testing with pre-recorded videos)

Place video files in `simulator/test_videos/` (e.g., `cam1.mp4`, `cam2.mp4`), then:

```bash
docker-compose -f simulator/docker-compose.simulator.yml up -d
```

Verify the simulator can see the mounted videos before starting an exam:

```bash
curl http://localhost:8000/cameras
```

For the seeded Hall 101 demo, `hall101_cam_front`, `hall101_cam_back`, and `hall101_cam_side` should show `"video_exists": true`. If they show `false`, the dashboard will display the simulator fallback frame instead of real video. The simulator container mounts `simulator/test_videos` at `/app/videos`, so configured video paths should look like `/app/videos/cam1.mp4`.

#### 3. Apply Database Migrations

The backend uses a local SQLite database (`data/thaqib.db`). Apply all schema migrations before seeding:

```bash
python -m alembic upgrade head
```

#### 4. Seed the Database with Demo Data

```bash
# For simulator (HTTP MJPEG streams)
python scripts/seed_demo.py --protocol=http --stream-host=localhost --stream-port=8000

# For real cameras (RTSP streams)
python scripts/seed_demo.py --protocol=rtsp --stream-host=192.168.1.100 --stream-port=554
```

#### 5. Start the Backend

```bash
uvicorn src.thaqib.main:app --reload --host 0.0.0.0 --port 8001
```

The API will be available at `http://localhost:8001`.

#### 6. Start the Frontend

```bash
cd frontend
npm run dev -- --host
```

Open `http://localhost:5173` in your browser. The Vite dev server proxies `/api` HTTP requests and PTT WebSockets to the backend on `127.0.0.1:8001`.

For phone PTT testing, do not use plain LAN HTTP such as `http://192.168.1.12:5173` for microphone transmission. Mobile browsers require a secure context for microphone access, so use an HTTPS Vite dev URL with a trusted local certificate or a trusted tunnel. Receive-only PTT can connect over HTTP, but pressing PTT to transmit will be blocked by the browser.

If you bypass the Vite proxy or call the backend directly from another device, keep `APP_ENV=development` and include your LAN frontend URL in `CORS_ORIGINS`, for example:

```env
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://192.168.1.12:5173
```

### Running the Demo (Standalone Video)

```bash
# From a video file
python scripts/demo_video.py --source "path/to/exam_video.mp4"

# From webcam
python scripts/demo_video.py --source 0
```

### Production Workflow (Real IP Cameras)

1. Connect IP cameras to the local network (Wi-Fi or Ethernet)
2. Obtain each camera's RTSP URL from its admin interface (e.g., `rtsp://admin:password@192.168.1.101:554/stream`)
3. Open the Thaqib dashboard → **Hall Management** → create a hall and add cameras with their RTSP stream URLs
4. The backend automatically connects to configured cameras and starts monitoring

## 📁 Project Structure

## Keyboard Controls

| Key | Function                                            | Scope        |
| --- | --------------------------------------------------- | ------------ |
| `S` | Select all tracked students for monitoring          | Pipeline     |
| `M` | Toggle deselect mode — click a student to remove    | Pipeline     |
| `C` | Clear all selections                                | Pipeline     |
| `T` | Toggle neighbor graph display                       | Display only |
| `R` | Toggle archive mode (RAW / ANNOTATED)               | Recording    |
| `D` | Toggle paper bounding box display                   | Display only |
| `F` | Toggle phone bounding box display                   | Display only |
| `L` | Toggle student→paper link lines                     | Display only |
| `V` | Cycle video quality (LOW 50% / MED 75% / HIGH 90%)  | Recording    |
| `G` | Cycle processing resolution (NATIVE / 1080p / 720p) | Processing   |
| `W` | Toggle live timestamp display                       | Display only |
| `P` | Toggle control panel                                | Display only |
| `Q` | Quit                                                | System       |

> **Note:** Toggling display (`D`, `F`, `L`) does NOT disable detection — it only hides/shows visual elements on screen. The system continues detecting and recording alerts regardless. Timestamp (`W`) toggles the live display only — recordings always include timestamps.

---

## Project Structure

```
Thaqib---Smart-Cheating-Detection-System/
├── src/thaqib/
│   ├── config/
│   │   └── settings.py             # Pydantic settings (loaded from .env)
│   ├── audio/
│   │   ├── pipeline.py             # Audio orchestrator (3-thread architecture)
│   │   ├── source.py               # Audio sources (file / live / multi-channel)
│   │   ├── discriminator.py        # Global/Local energy classifier
│   │   ├── keyword_detector.py     # VAD → Whisper STT → keyword matching
│   │   ├── preprocessor.py         # HPF + noise reduction + adaptive gain
│   │   ├── evidence.py             # WAV + JSON forensic evidence recorder
│   │   ├── session_recorder.py     # Full-session WAV streaming
│   │   ├── models.py               # Data classes (AudioChunk, AudioAlert, etc.)
│   │   └── README.md               # Audio system documentation
│   └── video/
│       ├── pipeline.py             # Main orchestrator (threading, state machines)
│       ├── camera.py               # Threaded camera capture (USB/RTSP/file)
│       ├── detector.py             # YOLOv11 person detection
│       ├── tools_detector.py       # YOLOv8 paper/phone detection
│       ├── tracker.py              # BoT-SORT multi-object tracker
│       ├── registry.py             # GlobalStudentRegistry (per-student state)
│       ├── neighbors.py            # k-NN spatial neighbor computation
│       ├── face_mesh.py            # MediaPipe face landmark extraction (VIDEO mode)
│       ├── face_mesh_worker.py     # Multiprocessing worker for face mesh
│       ├── gaze.py                 # 2D gaze direction from head pose + iris
│       ├── cheating_evaluator.py   # Gaze-angle cheating evaluation logic
│       ├── reid.py                 # OSNet face re-identification
│       ├── timestamps.py           # Timestamp overlay (shared by pipeline + display)
│       └── visualizer.py           # HUD, control panel, bbox rendering
├── scripts/
│   ├── demo_video.py               # Entry point — runs the full video pipeline
│   └── demo_audio.py               # Entry point — runs the audio pipeline with GUI
├── models/
│   ├── yolo11m.pt                  # Person detection model
│   ├── best.pt                     # Paper/phone detection model
│   └── face_landmarker.task        # MediaPipe face landmark model
├── alerts/                          # Auto-generated cheating evidence clips
├── audio alerts/                    # Auto-generated audio evidence (WAV + JSON)
├── sessions/                        # Full-session audio recordings
├── archive/                         # Auto-generated continuous video recordings
├── pyproject.toml                   # Dependencies and build config
└── .env                             # Runtime configuration
```

---

## Configuration (`.env`)

| Variable                        | Default | Description                                   |
| ------------------------------- | ------- | --------------------------------------------- |
| `CAMERA_SOURCE`                 | `0`     | Webcam index or RTSP URL or video file path   |
| `CAMERA_WIDTH`                  | `1280`  | Capture width (pixels)                        |
| `CAMERA_HEIGHT`                 | `720`   | Capture height (pixels)                       |
| `CAMERA_FPS`                    | `30`    | Capture FPS                                   |
| `DETECTION_INTERVAL`            | `1.0`   | Seconds between YOLO detection runs           |
| `DETECTION_CONFIDENCE`          | `0.15`  | YOLO person detection confidence              |
| `DETECTION_IMGSZ`               | `640`   | YOLO inference resolution                     |
| `RISK_ANGLE_TOLERANCE`          | `25.0`  | Gaze angle tolerance (degrees)                |
| `SUSPICIOUS_DURATION_THRESHOLD` | `2.0`   | Seconds of sustained gaze to trigger alert    |
| `NEIGHBOR_K`                    | `6`     | Number of nearest neighbors per student       |
| `VIDEO_QUALITY`                 | `75`    | Video output quality (0–100)                  |
| `ALERT_MAX_HEIGHT`              | `720`   | Max height for alert videos (0 = no limit)    |
| `ARCHIVE_MODE`                  | `raw`   | Archive recording mode (`raw` or `annotated`) |

**Audio settings** are documented in [Audio README](src/thaqib/audio/README.md). Key variables:

| Variable                        | Default | Description                                   |
| ------------------------------- | ------- | --------------------------------------------- |
| `AUDIO_WHISPER_MODEL`           | `tiny`  | Whisper model size                            |
| `AUDIO_LANGUAGE`                | `ar`    | Language code for Whisper                     |
| `AUDIO_STRICT_MODE`             | `true`  | Any speech = cheating (silent exam mode)      |
| `AUDIO_MIC_NAMES`               | `""`    | Mic labels (IPs, names, comma/JSON format)    |
| `AUDIO_SESSION_RECORDING`       | `true`  | Record full exam audio                        |
| `AUDIO_EPISODE_RECORDING`       | `true`  | Track sustained cheating episodes             |

---

## Output Files

### Alert Videos (`alerts/`)

| Type           | Filename Pattern                        | Contents                                       |
| -------------- | --------------------------------------- | ---------------------------------------------- |
| Gaze cheating  | `gaze_alert_trackN_YYYYMMDD_HHMMSS.mp4` | RED box on cheater, YELLOW box on target paper |
| Phone detected | `phone_alert_YYYYMMDD_HHMMSS.mp4`       | RED box on phone, "PHONE ALERT" banner         |

Each alert clip includes:

- **2 seconds** of pre-event footage (raw, no annotation)
- **Event duration** with annotated bounding boxes
- **2 seconds** of post-event footage

### Archive Videos (`archive/`)

Continuous recording of the full camera feed, saved as `archive_YYYYMMDD_HHMMSS.mp4`.

---

## Dependencies

| Package                          | Purpose                         |
| -------------------------------- | ------------------------------- |
| `ultralytics`                    | YOLO object detection           |
| `opencv-python`                  | Video capture, rendering, codec |
| `numpy`                          | Vectorized math                 |
| `mediapipe`                      | Face landmark extraction        |
| `boxmot`                         | BoT-SORT multi-object tracker   |
| `pydantic` / `pydantic-settings` | Configuration validation        |
| `python-dotenv`                  | `.env` file loading             |
| `torch`                          | Silero VAD runtime              |
| `faster-whisper`                 | Speech-to-text (Whisper STT)    |
| `sounddevice`                    | Live microphone capture         |
| `pydub`                          | Audio file loading (MP3, M4A)   |
| `scipy` *(optional)*             | Audio high-pass filter          |
| `noisereduce` *(optional)*       | Spectral noise reduction        |

---

## Team

- **Mohamed Elsaied Shalaan**

## License

Apache License 2.0 — see [LICENSE](LICENSE).
