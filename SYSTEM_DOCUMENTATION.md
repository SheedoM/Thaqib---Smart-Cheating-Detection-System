# Thaqib — System Documentation

> **Scope**: Complete technical reference for the Thaqib Smart Cheating Detection System. Covers architecture, module design, threading model, data flow, detection logic, alert recording, and configuration.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture & Data Flow](#2-architecture--data-flow)
3. [Module Reference](#3-module-reference)
4. [Threading & Concurrency Model](#4-threading--concurrency-model)
5. [Detection Pipeline](#5-detection-pipeline)
6. [Cheating Evaluation Logic](#6-cheating-evaluation-logic)
7. [Alert Recording System](#7-alert-recording-system)
8. [Video Output & Codec Strategy](#8-video-output--codec-strategy)
9. [Interactive Controls](#9-interactive-controls)
10. [Configuration Reference](#10-configuration-reference)
11. [Known Limitations & Edge Cases](#11-known-limitations--edge-cases)

---

## 1. System Overview

Thaqib is a standalone desktop application built with OpenCV and Python. It processes a single camera feed (USB, RTSP, or video file) and detects two types of cheating:

1. **Gaze-based cheating**: A student looks at a neighbor's paper for more than 2 seconds.
2. **Phone usage**: A mobile phone is detected anywhere in the frame.

When cheating is detected, the system automatically saves an annotated evidence video clip (MP4) and continues monitoring.

### What Thaqib IS

- A real-time video processing pipeline
- A standalone OpenCV desktop application
- A cheating detection engine with automatic evidence recording

### What Thaqib is NOT

- Not a web application (no server, no API, no dashboard)
- Not a multi-camera system (processes one camera at a time)
- Not an audio processing system

---

## 2. Architecture & Data Flow

### 2.1 Complete Frame Lifecycle

```
Camera → FrameData → [Detection Worker] → DetectionResult
                                              │
                          ┌───────────────────┘
                          ▼
                     BoT-SORT Tracker → TrackingResult
                          │
                          ▼
                  GlobalStudentRegistry.update()
                          │
              ┌───────────┼──────────────┐
              ▼           ▼              ▼
        NeighborComputer  FaceMesh Pool  Tools (papers/phones)
              │           │              │
              └───────────┼──────────────┘
                          ▼
                  CheatingEvaluator.evaluate()
                          │
              ┌───────────┼───────────────┐
              ▼           ▼               ▼
         Gaze Alert   Phone Alert    VideoVisualizer
         Recording    Recording      (live display)
              │           │
              ▼           ▼
         alerts/*.mp4  alerts/*.mp4
```

### 2.2 Processing Order (per frame)

| Step | Component | Thread | Description |
|------|-----------|--------|-------------|
| 1 | `CameraStream` | Reader thread | Reads frame from capture device |
| 2 | `_detection_worker` | Detection thread | Runs YOLO person + tools detection (every `detection_interval`) |
| 3 | `ObjectTracker.update()` | Main thread | Updates BoT-SORT with new detections |
| 4 | `GlobalStudentRegistry.update()` | Main thread | Creates/updates per-student state objects |
| 5 | `NeighborComputer.compute_*()` | Main thread | Calculates k-NN neighbors and paper assignments |
| 6 | `FaceMeshExtractor.extract()` | Process pool | Extracts face landmarks via MediaPipe (every 2nd frame) |
| 7 | `CheatingEvaluator.evaluate()` | Main thread | Gaze angle vs. paper positions → cheating decision |
| 8 | Alert state machine | Main thread | Manages recording buffers for gaze and phone alerts |
| 9 | `VideoVisualizer.draw()` | Main thread | Renders HUD, bounding boxes, control panel |
| 10 | Archive writer | Writer thread | Writes frame to `archive/` video file |

---

## 3. Module Reference

### 3.1 `pipeline.py` — Main Orchestrator

The central module. Coordinates all subsystems, manages threading, and implements both the gaze and phone alert state machines.

**Key classes:**
- `VideoPipeline` — Main class. Owns all subsystems, runs the frame loop.
- `PipelineFrame` — Immutable data object passed to the visualizer each frame.
- `StudentState` — Per-frame student snapshot (not persisted).

**Key attributes:**
- `_global_frame_buffer` — Ring buffer of last 3 seconds of raw frames (for alert pre-buffering).
- `_phone_detected`, `_phone_is_recording`, `_phone_recording_buffer` — Phone alert state machine.
- `_video_quality` — Runtime-adjustable quality (50/75/90), affects all video writers.
- `_processing_max_height` — Runtime-adjustable input resolution (0=NATIVE, 1080, 720). Downscales camera frames before all processing.

### 3.2 `camera.py` — Camera Capture

Threaded camera reader. Reads frames in a daemon thread and pushes to a `deque(maxlen=5)`.

- Supports webcam index (int), RTSP URL (str), or video file path (str).
- Uses `CAP_DSHOW` backend on Windows for USB cameras.
- Yields `FrameData(frame, frame_index, timestamp)` via a generator.

### 3.3 `detector.py` — Person Detection

YOLOv11 person detector. Runs on CUDA if available, falls back to CPU.

- Model: `models/yolo11m.pt`
- Filters for class 0 (person) only.
- Includes warmup inference on initialization.

### 3.4 `tools_detector.py` — Paper & Phone Detection

Custom YOLO model for detecting papers (class: `document`) and phones (class: `phone`, `Using_phone`, `cell phone`).

- Model: `models/best.pt`
- Runs in the same detection thread as person detection.
- Results are used for both neighbor paper assignment and phone alert triggering.

### 3.5 `tracker.py` — Multi-Object Tracker

BoT-SORT tracker via the `boxmot` library.

- Internal ReID disabled (`with_reid=False`) — custom ReID via `reid.py` is used instead.
- `track_buffer=120` (4 seconds at 30fps before dropping a lost track).
- Implements bbox smoothing and human-in-the-loop selection.

### 3.6 `registry.py` — Student State Registry

`GlobalStudentRegistry` maintains a `StudentSpatialState` for each tracked student.

**Key state fields per student:**
- `track_id`, `bbox`, `center`, `paper_center`
- `face_mesh` — Latest face landmark extraction result
- `neighbors`, `neighbor_papers`, `surrounding_papers`
- `is_cheating`, `is_alert_recording`, `cheating_target_paper`, `cheating_target_neighbor`
- `suspicious_start_time`, `cheating_cooldown`
- `recording_buffer` — Frames captured for the current alert

### 3.7 `neighbors.py` — Spatial Neighbor Computation

Computes k-nearest neighbors for each student using Euclidean distance between centers.

- **Step A**: Compute pairwise distances, sort, select top-k.
- **Step B**: For each detected paper (from YOLO tools model), assign it exclusively to the nearest student (greedy 1-to-1).
- **Step C**: For each student, collect papers belonging to their neighbors → `surrounding_papers`.
- **Skip-if-stable**: If max center movement < 20px since last computation, skip (optimization).

### 3.8 `face_mesh.py` — Face Landmark Extraction

MediaPipe FaceLandmarker in **VIDEO mode** (temporal smoothing enabled).

- Creates one `FaceLandmarker` instance per worker thread (thread-local storage).
- Extracts 2D/3D landmarks, face transformation matrix, and iris positions.
- Returns a `FaceMeshResult` with `landmarks_2d`, `landmarks_3d`, `head_matrix`, `iris_left`, `iris_right`.
- Runs via a multiprocessing `Pool` with shared memory for frame passing.

### 3.9 `gaze.py` — Gaze Direction Computation

Pure function: `compute_gaze_direction(face_mesh_result) → (dx, dy) | None`

- Combines head rotation (from face transformation matrix) with iris deviation.
- Returns a 2D unit vector in screen space.

### 3.10 `cheating_evaluator.py` — Cheating Decision Logic

`CheatingEvaluator.evaluate(track_id)` — determines if a student is cheating.

**Algorithm:**
1. Get gaze direction from face mesh.
2. For each `surrounding_paper` (neighbor's paper):
   - Compute 2D angle between gaze vector and direction toward the paper.
   - If angle < `risk_angle_tolerance` (25°) → student is looking at that paper.
3. If sustained for > `suspicious_duration_threshold` (2s) → `is_cheating = True`.
4. Once cheating stops, a 30-frame cooldown prevents oscillation.
5. If face is undetected, cooldown is **frozen** (not decremented) to prevent escape-by-hiding.

### 3.11 `reid.py` — Face Re-Identification

OSNet-based appearance embeddings for re-identifying students after tracking loss.

- Extracts face crop → generates embedding → cosine similarity matching.
- Alias system maps new tracker IDs to known student identities.

### 3.12 `visualizer.py` — Display & HUD

`VideoVisualizer.draw(pipeline_frame)` — renders all visual overlays.

**Components drawn:**
- Student bounding boxes (color-coded by ID, red when cheating)
- Paper bounding boxes (cyan, optional via `D` key)
- Phone bounding boxes (orange, optional via `F` key)
- Student→paper link lines (yellow, optional via `L` key)
- Gaze direction arrows
- Neighbor connection lines (optional via `T` key)
- HUD: FPS, frame counter, cheating alerts, phone alerts
- Control panel: STATUS + CONTROLS columns
- Instruction bar: keyboard shortcut reference

**Display flags:**
- `show_paper` — paper bounding boxes (`D` key)
- `show_phone` — phone bounding boxes (`F` key)
- `show_gaze_lines` — student→surrounding-paper link lines (`L` key)
- `show_neighbors` — neighbor connection graph (`T` key)
- `show_timestamp` — live timestamp overlay (`W` key, display only)
- `show_control_panel` — STATUS/CONTROLS panel (`P` key)

### 3.13 `timestamps.py` — Timestamp Overlay

Standalone utility module providing `draw_timestamp_overlay(frame, ts)`. Burns a semi-transparent timestamp badge (top-right corner) onto any frame.

- Used by `pipeline.py` to **always** burn timestamps into archive and alert videos.
- Used by `demo_video.py` to **optionally** show timestamps on the live display (toggled via `W` key).
- Kept in a separate module to avoid circular imports between `pipeline.py` and `visualizer.py`.

---

## 4. Threading & Concurrency Model

| Thread/Process | Name | Purpose | Shared State |
|----------------|------|---------|-------------|
| **Main thread** | — | Frame loop, tracking, evaluation, recording state machines | Everything |
| **Camera reader** | `CameraReader` | `cv2.VideoCapture.read()` in a loop | `_frame_queue` (deque) |
| **Detection worker** | `DetectionWorker` | YOLO person + tools inference | `_current_frame_data` (via lock) |
| **Archive writer** | `ArchiveWriter` | Drains frame queue → disk | `_archive_queue` (Queue) |
| **Alert writers** | `AlertWriter-N` | Saves alert clips (one thread per clip) | Independent frame list |
| **Phone alert writer** | `PhoneAlertWriter` | Saves phone clips | Independent frame list |
| **Face mesh pool** | `Pool(4)` | MediaPipe inference (multiprocessing) | Shared memory for frames |

### Key synchronization:
- Detection results pass via `Queue` (thread-safe).
- Camera frames pass via `deque(maxlen=5)` (lock-free, main thread only reads latest).
- Face mesh uses `multiprocessing.shared_memory` to pass frames to worker processes.
- Archive uses a bounded `Queue(maxsize=60)` — drops frames rather than blocking.

---

## 5. Detection Pipeline

### 5.1 Person Detection

```
Frame → HumanDetector.detect(frame) → DetectionResult
                                         │
                                         ├─ detections: list[Detection]
                                         │    ├─ bbox (x1, y1, x2, y2)
                                         │    ├─ confidence
                                         │    └─ class_id (always 0 = person)
                                         └─ count: int
```

Runs every `detection_interval` seconds (default: 1.0s). Between detections, the tracker interpolates positions using Kalman filtering.

### 5.2 Tools Detection (Papers & Phones)

```
Frame → ToolsDetector.detect(frame) → ToolsDetectionResult
                                         │
                                         └─ tools: list[ToolDetection]
                                              ├─ bbox (x1, y1, x2, y2)
                                              ├─ label ("document" / "phone" / etc.)
                                              └─ confidence
```

Runs in the same detection cycle as person detection. Paper detections are assigned to students via `NeighborComputer`. Phone detections trigger the independent phone alert state machine.

---

## 6. Cheating Evaluation Logic

### 6.1 Gaze Cheating State Machine

```
         ┌─────────────────────────────────────────┐
         │ NORMAL MONITORING                        │
         │ (student colored by unique ID color)     │
         └──────────────┬──────────────────────────┘
                        │ Gaze aligned with neighbor paper
                        │ (angle < 25°)
                        ▼
         ┌─────────────────────────────────────────┐
         │ SUSPICIOUS                               │
         │ suspicious_start_time = now              │
         │ Accumulates over frames                  │
         └──────────────┬──────────────────────────┘
                        │ Sustained for > 2 seconds
                        ▼
         ┌─────────────────────────────────────────┐
         │ CHEATING DETECTED                        │
         │ is_cheating = True                       │
         │ Alert recording STARTS                   │
         │ Student bbox turns RED                   │
         └──────────────┬──────────────────────────┘
                        │ Student stops looking at paper
                        ▼
         ┌─────────────────────────────────────────┐
         │ COOLDOWN (30 frames ≈ 1 second)          │
         │ Decrements only when gaze is confirmed   │
         │ NOT toward a paper. Frozen if face lost. │
         └──────────────┬──────────────────────────┘
                        │ Cooldown reaches 0
                        ▼
         ┌─────────────────────────────────────────┐
         │ POST-EVENT (60 frames ≈ 2 seconds)       │
         │ Recording continues                      │
         └──────────────┬──────────────────────────┘
                        │ Post-event countdown ends
                        ▼
         ┌─────────────────────────────────────────┐
         │ RECORDING SAVED → FULL RESET             │
         │ is_cheating = False                      │
         │ All cheating state cleared               │
         │ Student returns to normal                │
         └─────────────────────────────────────────┘
```

### 6.2 Phone Alert State Machine

Completely independent of student tracking:

```
Phone detected in frame → START recording
  │
  ├─ Pre-buffer: last 2 seconds of raw frames (no bboxes)
  ├─ During: phone visible → red bbox + "PHONE ALERT" banner
  └─ Post: phone disappears → 2-second countdown → SAVE
```

- Phone alerts do NOT associate with any student.
- Multiple phones in one frame all get red boxes in the same video.
- Live view shows: red frame border + HUD line "!! PHONE DETECTED (N) !!"

---

## 7. Alert Recording System

### 7.1 Gaze Alert Videos

**Filename**: `alerts/gaze_alert_trackN_YYYYMMDD_HHMMSS.mp4`

**Contents per frame:**
- RED bounding box around the cheating student + label "CHEATER ID:X"
- YELLOW bounding box around the target paper (not the victim student)
- Red banner: "CHEATING ALERT — Student X looking at neighbor's paper"

**Buffer structure:** `(raw_frame, track_id | None)` tuples. Pre-event frames have `track_id=None` → written raw.

### 7.2 Phone Alert Videos

**Filename**: `alerts/phone_alert_YYYYMMDD_HHMMSS.mp4`

**Contents per frame:**
- RED bounding box around each detected phone + label "PHONE"
- Dark red banner: "PHONE ALERT — Mobile device detected"

**Buffer structure:** `(raw_frame, phone_bboxes_list)` tuples. Pre-event frames have `[]` → written raw.

### 7.3 Concurrency Limits

- Maximum 3 simultaneous gaze alert recordings (prevents OOM).
- Phone alerts are independent and not counted against this limit.
- Each recording runs in its own daemon thread.

---

## 8. Video Output & Codec Strategy

### 8.1 Codec Fallback Chain

All video writers (archive + alerts) use the same priority:

| Priority | Codec | Extension | Notes |
|----------|-------|-----------|-------|
| 1 | `avc1` | `.mp4` | H.264 — best quality/size ratio |
| 2 | `mp4v` | `.mp4` | MPEG-4 fallback |
| 3 | `XVID` | `.avi` | Universally available |
| 4 | `MJPG` | `.avi` | Always works, largest files |

> On most Windows systems, `avc1` requires the OpenH264 DLL. If unavailable, the system automatically falls back to `mp4v`.

### 8.2 Quality & Size Control

| Setting | Default | Effect |
|---------|---------|--------|
| `VIDEO_QUALITY` | `75` | OpenCV quality parameter (0–100). 75 saves ~40% vs default. |
| `ALERT_MAX_HEIGHT` | `720` | Alert videos are downscaled to this height. 0 = no limit. |

Quality presets accessible via `V` key at runtime:
- **LOW** (50%) — smallest files
- **MED** (75%) — default balance
- **HIGH** (90%) — best quality

### 8.3 Estimated File Sizes

| Scenario | Before optimization | After optimization |
|----------|--------------------|--------------------|
| 10s alert @ 1080p | ~80–150 MB | ~15–25 MB |
| 10s alert @ 4K | ~300–600 MB | ~15–25 MB (downscaled to 720p) |
| 1 min archive @ 1080p | ~400 MB | ~80 MB |

---

## 9. Interactive Controls

### 9.1 Control Panel (toggle with `P`)

**Left column — STATUS:**
- Tracked students count
- Monitored (selected) students count
- Active cheating alerts
- Archive mode (RAW / ANNOTATED)
- Neighbor graph (ON / OFF)
- Paper display (ON / OFF)
- Phone display (ON / OFF)
- Paper link lines (ON / OFF)
- Video quality (LOW / MED / HIGH)
- Input resolution (NATIVE / 1080p / 720p with actual pixel dimensions)
- Timestamp (ON / OFF — live display only)

**Right column — CONTROLS:**
- All keyboard shortcuts with current state indicators.

### 9.2 Display vs. Detection

| Toggle | Affects display? | Affects detection? | Affects recording? |
|--------|-----------------|-------------------|-------------------|
| `D` (Papers) | ✅ Yes | ❌ No | ❌ No |
| `F` (Phones) | ✅ Yes | ❌ No | ❌ No |
| `L` (Link lines) | ✅ Yes | ❌ No | ❌ No |
| `T` (Neighbors) | ✅ Yes | ❌ No | ❌ No |
| `W` (Timestamp) | ✅ Yes (live only) | ❌ No | ❌ No (always ON in files) |
| `V` (Quality) | ❌ No | ❌ No | ✅ Yes |
| `G` (Resolution) | ✅ Yes | ✅ Yes | ✅ Yes |
| `R` (Archive mode) | ❌ No | ❌ No | ✅ Yes |

---

## 10. Configuration Reference

All settings are loaded from `.env` via Pydantic. Override any setting with an environment variable.

### Camera
| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CAMERA_SOURCE` | str | `"0"` | Webcam index, RTSP URL, or file path |
| `CAMERA_WIDTH` | int | `1280` | Capture width |
| `CAMERA_HEIGHT` | int | `720` | Capture height |
| `CAMERA_FPS` | int | `30` | Capture FPS |

### Detection
| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `YOLO_MODEL` | str | `models/yolo11m.pt` | Person detection model path |
| `TOOLS_MODEL` | str | `models/best.pt` | Paper/phone detection model path |
| `DETECTION_INTERVAL` | float | `1.0` | Seconds between detection runs |
| `DETECTION_CONFIDENCE` | float | `0.15` | Person detection confidence threshold |
| `TOOLS_CONFIDENCE` | float | `0.45` | Paper/phone detection confidence |
| `DETECTION_IMGSZ` | int | `640` | YOLO inference resolution |

### Tracking
| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `TRACKING_MAX_DISTANCE` | int | `100` | Max tracking distance |
| `TRACKING_MAX_AGE` | int | `30` | Max frames before dropping track |
| `NEIGHBOR_K` | int | `6` | Number of nearest neighbors |

### Cheating Evaluation
| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `RISK_ANGLE_TOLERANCE` | float | `25.0` | Max gaze-to-paper angle (degrees) |
| `SUSPICIOUS_DURATION_THRESHOLD` | float | `2.0` | Seconds of sustained gaze to flag |
| `SUSPICIOUS_MATCH_RATIO` | float | `0.7` | Fraction of frames that must match |

### Video Output
| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `VIDEO_QUALITY` | int | `75` | Output quality (0–100) |
| `ALERT_MAX_HEIGHT` | int | `720` | Max alert video height (0 = native) |
| `ARCHIVE_MODE` | str | `raw` | `raw` or `annotated` |

### Re-Identification
| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `REID_MATCH_THRESHOLD` | float | `0.80` | Cosine similarity threshold |
| `REID_SIMILARITY_DEBUG` | bool | `False` | Log per-frame similarity scores |

### Performance
| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `FACE_MESH_WORKERS` | int | `4` | Number of face mesh worker processes |

---

## 11. Known Limitations & Edge Cases

| Scenario | Impact | Mitigation |
|----------|--------|-----------|
| Student enters mid-session | May create phantom paper position | Heuristic paper fallback; resolves when real paper detected |
| Tracking lost (occlusion) | Stale neighbor positions until next detection | `track_buffer=120` preserves track for 4 seconds |
| Two students swap seats | Both lose identity for ~2–5 seconds | ReID alias system reconnects; cooldown prevents false alerts |
| Face not detected (turned away) | Cheating cooldown frozen (by design) | Hard limit prevents permanent freeze |
| >3 simultaneous cheaters | 4th+ recording skipped | Logged once per track; resumes when a slot opens |
| Video file ends during recording | Recording flushed on pipeline stop | `stop()` method saves all pending buffers |
| 4K video input | High memory usage for buffers | Press `G` to switch to 1080p/720p processing. Alert videos also downscaled to `alert_max_height`. |
| `avc1` codec unavailable | Falls back to `mp4v` (larger files) | Install OpenH264 DLL for smallest MP4 output |
