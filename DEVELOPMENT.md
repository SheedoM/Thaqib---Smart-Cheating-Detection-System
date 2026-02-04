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

1. **Test & Verify Pipeline** - Run demo with webcam, verify all components work
2. **Add Suspicious Behavior Persistence** - Track duration of suspicious gaze (2-3s threshold)
3. **Add Feature Logging** - CSV output for debugging/analysis
4. **Audio Detection Module** - Microphone input, anomaly detection
5. **Backend API** - FastAPI with WebSocket for real-time alerts
6. **Web Dashboard** - React + TypeScript for invigilators

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

## Phase Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 1. Project Setup | ✅ Done | Structure, deps, git |
| 2. Video Detection | 🔄 Testing | Camera → Detect → Track → Pose → Neighbor |
| 3. Audio Detection | ⏳ Pending | Microphones, anomaly detection |
| 4. Backend API | ⏳ Pending | FastAPI, WebSocket |
| 5. Dashboard | ⏳ Pending | React, real-time alerts |
| 6. Integration | ⏳ Pending | End-to-end testing |
