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

Development defaults to **SQLite** (no setup needed — a file at `data/thaqib.db`), so you
can skip this step for local work. Start the PostgreSQL container only when targeting the
**production database** (see [Database: development vs. production](#database-development-vs-production)):

```bash
docker compose up -d db
```

#### 2. Start the Camera Simulator (required for camera feeds)

Camera feeds will **not** open unless the simulator is running on port **8000** — the
seeded `Device.stream_url` values point at `http://localhost:8000/camera/<id>/feed`
(API runs on 8001, simulator on 8000; the backend resolves feeds server-side). Place
video files in `simulator/test_videos/` (e.g., `cam1.mp4`, `cam2.mp4`), then start it
either natively or via Docker:

```bash
# Native (no Docker) — uses the project venv
./venv/Scripts/python.exe -m uvicorn simulator.main:app --host 0.0.0.0 --port 8000

# OR Docker
docker-compose -f simulator/docker-compose.simulator.yml up -d
```

Verify the simulator can see the mounted videos before starting an exam:

```bash
curl http://localhost:8000/cameras
```

For the seeded Hall 101 demo, `hall101_cam_front`, `hall101_cam_back`, and `hall101_cam_side` should show `"video_exists": true`. If they show `false`, the dashboard will display the simulator fallback frame instead of real video. The simulator container mounts `simulator/test_videos` at `/app/videos`, so configured video paths should look like `/app/videos/cam1.mp4`.

#### 3. Apply Database Migrations

In development the backend uses a local SQLite database (`data/thaqib.db`). Apply all schema migrations before seeding:

```bash
python -m alembic upgrade head
```

> For the production database, set `DATABASE_URL` first so migrations run against PostgreSQL — see [Database: development vs. production](#database-development-vs-production).

#### 4. Seed the Database with Demo Data

```bash
# Single-tenant college demo
python seed_demo.py college

# Multi-tenant university demo with three colleges
python seed_demo.py university

# If the simulator runs on another machine
python seed_demo.py college --simulator-base-url http://192.168.1.10:8000
```

`seed_demo.py` is the only demo seed entrypoint. It wipes existing demo data and
rebuilds users, halls, cameras, microphones, exams, and assignments. For real
camera deployments, create or edit devices in the dashboard with their RTSP URLs
after seeding the tenant structure.

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

Open `http://localhost:5173` in your browser. The Vite dev server proxies `/api` HTTP requests and the hall voice WebSocket to the backend on `127.0.0.1:8001`.

#### 7. (Phone testing) Serve over HTTPS with a Cloudflare tunnel

The hall voice channel lets the control room and invigilators talk. Microphone capture only works in a **secure context** (HTTPS or `localhost`), so a phone on plain LAN HTTP such as `http://192.168.1.12:5173` cannot transmit. Expose the app over HTTPS with a Cloudflare quick tunnel:

```bash
cloudflared tunnel --url http://localhost:5173
```

Open the printed `https://<random>.trycloudflare.com` URL on **both** the laptop and the phone, then log in. The voice channel connects over `wss://` through the tunnel and the phone will grant the microphone. (`vite.config.ts` already sets `allowedHosts: true`; everything is same-origin through the tunnel, so no CORS change is needed.)

**Startup order:** database/migrations → seed → simulator (:8000) → backend (:8001) → frontend (5173) → *(phone testing only)* cloudflared tunnel.

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

## Database: development vs. production

The system is database-agnostic via SQLAlchemy + Alembic; the engine is selected entirely
by the `DATABASE_URL` environment variable — **no code change required**.

| Environment | `DATABASE_URL` | Why |
| ----------- | -------------- | --- |
| **Development** (default) | `sqlite:///./data/thaqib.db` | Zero setup. SQLite serializes writes (single writer) — fine for local dev and tests. |
| **Production / pilot** | `postgresql+psycopg2://USER:PASS@HOST:5432/DB` | PostgreSQL provides true concurrent writes (MVCC), required under live multi-hall detection-event load — SQLite would hit `database is locked` errors. |

`db/database.py` tunes the engine automatically: SQLite gets `check_same_thread=False`;
PostgreSQL gets connection pooling (`pool_pre_ping`, `pool_size`, `max_overflow`,
`pool_recycle`).

**Switch to PostgreSQL for production:**

```bash
# 1. Start Postgres (docker-compose.yml provides Postgres 15 + PgAdmin)
docker compose up -d db

# 2. Point the app at it (psycopg2 driver; container maps host port 5433)
export DATABASE_URL="postgresql+psycopg2://thaqib_admin:development_password@localhost:5433/thaqib_production"
#   PowerShell: $env:DATABASE_URL = "postgresql+psycopg2://thaqib_admin:development_password@localhost:5433/thaqib_production"

# 3. Apply migrations against Postgres
python -m alembic upgrade head
```

> **Before a real deployment:** change `development_password` (in `docker-compose.yml` and
> the connection string) to a strong secret, and set `APP_ENV=production` (the settings
> validator then enforces a non-default `SECRET_KEY`, a configured `INTERNAL_EVENT_TOKEN`,
> and non-wildcard CORS).
>
> **Timezone note:** on PostgreSQL all timestamp columns are real `timestamptz`, so all
> DB-written datetimes are UTC-aware. Keep using `datetime.now(timezone.utc)` (never naive
> `datetime.now()`) for any new code that writes timestamps.

---

## Configuration (`.env`)

| Variable                        | Default | Description                                   |
| ------------------------------- | ------- | --------------------------------------------- |
| `DATABASE_URL`                  | `sqlite:///./data/thaqib.db` | DB connection string (SQLite dev / PostgreSQL prod) |
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
- **Shady Mohamed Faragallah**
- **Mohamed Elsaied Shalaan**

## License

Apache License 2.0 — see [LICENSE](LICENSE).
