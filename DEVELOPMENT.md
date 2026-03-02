# Thaqib Development Context

> This file captures the current development state to enable easy continuation in future sessions.

## Project Overview

**Thaqib** is an AI-powered real-time exam monitoring system that detects cheating behaviors using video and audio analysis.

---

## Current Status (2026-02-04)

### Completed ✅

1. **Project Setup**
   - Created Python package structure (`src/thaqib/`)
   - Configured `pyproject.toml` with all dependencies
   - Set up git branching: `main` → `develop` → `feature/video-detection`
   - Pushed to GitHub

2. **Video Detection Module** (`src/thaqib/video/`)
   - `camera.py` - Webcam/RTSP camera handler
   - `detector.py` - YOLOv8 human detection (periodic, 1/sec)
   - `tracker.py` - ByteTrack tracking with human-in-the-loop selection
   - `head_pose.py` - MediaPipe FaceLandmarker head pose estimation
   - `neighbor.py` - Spatial modeling, paper zones, risk angles
   - `pipeline.py` - Orchestrates all video components

3. **Demo Script** (`scripts/demo_video.py`)
   - Test the pipeline with webcam
   - Press `s` to select, `c` to clear, `q` to quit

### In Progress 🔄

- Testing the video pipeline with webcam
- Tuning detection parameters

### Next Tasks 📋

The project is now structured into distinct functional phases. Each phase has specific deliverables required to reach the Minimum Viable Product (MVP).

#### Phase 1: Video Detection & Core Analytics (Current)
- [ ] Test & Verify Pipeline - Run demo with webcam, verify all components work seamlessly together.
- [ ] Add Suspicious Behavior Persistence - Track duration of suspicious gaze (2-3s threshold) to reduce false positives.
- [ ] Add Feature Logging - Implement robust CSV/database output for feature extraction (debugging/analysis).
- [ ] Optimize YOLOv8 and ByteTrack integration for sustained 30FPS processing on local hardware.
- [ ] Finalize Head Pose & Risk Angle confidence scoring logic.

#### Phase 2: Audio Detection & Processing
- [ ] **Research & Setup**: Identify optimal libraries for real-time audio anomaly detection (e.g., Librosa, PyAudio).
- [ ] **VAD Implementation**: Implement Voice Activity Detection (WebRTC VAD or Silero) to filter out background noise.
- [ ] **Anomaly Model**: Develop or integrate a model to classify specific audio anomalies (whispering, sudden spikes, paper rustling).
- [ ] **Spatial Audio Mapping**: Map microphone inputs to specific hall zones (integration with the `neighbor.py` risk areas).
- [ ] **Audio Pipeline**: Create an `audio/pipeline.py` orchestrator, similar to the video module.

#### Phase 3: Web Dashboard & Control Room (Frontend)
- [ ] **Tech Stack Setup**: Initialize React + TypeScript + Vite project for the Admin/Invigilator dashboard.
- [ ] **UI/UX Implementation**: Build the Hall Grid View, Priority Alert Stack, and active monitoring pages based on the System Architecture.
- [ ] **State Management**: Integrate Redux Toolkit or Zustand for handling rapid real-time state changes.
- [x] **Backend API (FastAPI)**: Initialized FastAPI application structure. (REST endpoints for DB pending).
- [x] **Real-time Comms (PTT)**: Implemented 2-way Push-to-Talk WebSockets to allow communication between Invigilators and Control Room.
- [ ] **Real-time Comms (Alerts)**: Implement WebSockets to push detection alerts from the backend pipeline to the frontend exactly when detected.

#### Phase 4: Integration & MVP Delivery
- [ ] Integrate Video and Audio pipelines into a unified core engine.
- [ ] Connect the core engine to the FastAPI backend to broadcast events.
- [ ] End-to-End Test: Run a simulated exam session with 1 camera, 1 mic, and the web dashboard monitoring in real-time.
- [ ] Containerize the application (Docker + Docker Compose) for easy deployment.
- [ ] Finalize "MVP Version 1.0" release tag.

---

## Key Technical Decisions

| Component | Decision | Rationale |
|-----------|----------|-----------|
| Detection | YOLOv8s @ 1/sec | Balance speed/accuracy |
| Tracking | ByteTrack | Best MOT performance |
| Head Pose | MediaPipe FaceLandmarker | CPU-friendly, sufficient accuracy |
| Eye Gaze | **Deferred** | Head pose captures ~85% of gaze direction |
| Neighbors | k=4 nearest | Covers immediate surrounding students |
| Risk Angle | ±15° tolerance | Accounts for estimation error |
| Suspicious | 2-3s duration | Reduces false positives |

---

## User Requirements Summary

- **Deployment**: Single server initially
- **Cameras**: 3 per hall (1 per column of 12 benches)
- **Students/Camera**: 12-24 (testing with 5-10 first)
- **Camera Type**: IP cameras (RTSP), webcam for dev
- **Dashboard**: Web-based, mobile-friendly
- **Data Storage**: Anonymized feature logs only (privacy)

---

## Project Structure

```
thaqib/
├── src/thaqib/
│   ├── config/settings.py    # Pydantic settings from .env
│   └── video/
│       ├── camera.py         # CameraStream
│       ├── detector.py       # HumanDetector (YOLOv8)
│       ├── tracker.py        # ObjectTracker (ByteTrack)
│       ├── head_pose.py      # HeadPoseEstimator (MediaPipe)
│       ├── neighbor.py       # NeighborModeler, risk angles
│       └── pipeline.py       # VideoPipeline orchestrator
├── scripts/
│   └── demo_video.py         # Webcam test script
├── models/
│   └── face_landmarker.task  # Auto-downloaded MediaPipe model
├── pyproject.toml
├── .env.example
└── README.md
```

---

## Commands to Resume

```bash
# Activate environment
cd "f:\University\Graduation project_Smart Cheating System\Thaqib---Smart-Cheating-Detection-System"
.\venv\Scripts\activate

# Run demo
python scripts/demo_video.py --source 0

# Git status
git branch   # Should be on feature/video-detection
git log -3   # Recent commits
```

---

## Known Issues

1. **MediaPipe Version**: Must use 0.10.30+ (Tasks API, not legacy solutions)
2. **Model Download**: `face_landmarker.task` auto-downloads to `models/` folder on first run

---

## Phase Roadmap (Path to MVP)

| Phase | Title | Status | Goal / Deliverable |
|-------|-------|--------|---------------------|
| 0 | Project Setup | ✅ Done | Initial architecture, environment, and GitHub workflow established. |
| 1 | Video Detection | 🔄 Active | Robust visual detection pipeline (YOLO + MediaPipe + Spatial modeling) working locally. |
| 2 | Audio Detection | ⏳ Pending | Processing microphone streams for anomalies (whispers, spikes) mapped to zones. |
| 3 | Frontend & APIs | ⏳ Pending | Responsive React dashboard connected via WebSockets to the FastAPI backend. |
| 4 | Integration & MVP | ⏳ Pending | End-to-end system testing, containerization (Docker), and MVP v1.0 release. |
