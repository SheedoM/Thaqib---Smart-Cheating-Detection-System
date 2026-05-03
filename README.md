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

- Python 3.10+
- NVIDIA GPU with CUDA (recommended; CPU works but slower)
- Webcam, IP camera (RTSP), or pre-recorded video file

### Installation

```bash
git clone https://github.com/SheedoM/Thaqib---Smart-Cheating-Detection-System.git
cd Thaqib---Smart-Cheating-Detection-System

python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/macOS

pip install -e .
pip install -e ".[gpu]"        # For CUDA GPU acceleration
```

### Running

```bash
# From a video file
python scripts/demo_video.py --source "path/to/exam_video.mp4"

# From webcam
python scripts/demo_video.py --source 0
```

---

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
│   └── demo_video.py               # Entry point — runs the full pipeline
├── models/
│   ├── yolo11m.pt                  # Person detection model
│   ├── best.pt                     # Paper/phone detection model
│   └── face_landmarker.task        # MediaPipe face landmark model
├── alerts/                          # Auto-generated cheating evidence clips
├── archive/                         # Auto-generated continuous recordings
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

---

## Team

- **Mohamed Elsaied Shalaan**

## License

Apache License 2.0 — see [LICENSE](LICENSE).
