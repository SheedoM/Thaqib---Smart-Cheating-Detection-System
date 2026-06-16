# Thaqib Smart Cheating Detection System — Architecture Analysis

> **Last Updated**: After Audit Fix Round (commits 633e1cf, 4d699c5, 73d2d2bd and subsequent)
> **Status**: All 10 prioritized findings fixed. Additional improvements applied.
> See git log for full change history.

> **Methodology**: All conclusions below are drawn from direct, line-by-line reading of the source code.
> Docstrings, README files, and `walkthrough.md` were **not** used as sources.
> Three reading passes were performed; findings are presented in increasing depth.

---

## Step 1: Project Inventory

### Top-level

| File / Dir | Role |
|---|---|
| `run.py` | Single entry point. Parses CLI, creates shared buffers, wires all pipelines, launches threads. |
| `src/thaqib/` | Main package |
| `models/` | YOLO `.pt` weights + `face_landmarker.task` |
| `scripts/` | Regression / integration tests |
| `alerts/` | Runtime output — alert `.mp4` clips |
| `archive/` | Runtime output — continuous session recording |
| `logs/` | Runtime output — `VideoLogger` JSON-Lines diagnostic logs |

### `src/thaqib/` package tree

```
thaqib/
├── __init__.py                  # Package metadata only
├── sim_clock.py                 # SimClock: time.monotonic wrapper
├── mic_layout.py                # MicLayout, MicPin — normalized mic position DB
├── av_alert_composer.py         # AVAlertComposer — A/V mux + clip saver
├── config/
│   ├── __init__.py              # re-exports get_settings()
│   └── settings.py              # Pydantic settings (all env vars)
├── audio/
│   ├── models.py                # AudioChunk, AudioAlert, CheatEpisode, SoundClassification
│   ├── source.py                # AudioSource ABC + FileAudioSource, LiveMicSource
│   ├── preprocessor.py          # AudioPreprocessor — bandpass, normalize, de-noise
│   ├── discriminator.py         # GlobalLocalDiscriminator — Silero VAD fork + env filter
│   ├── keyword_detector.py      # KeywordDetector — Whisper / VAD-only
│   ├── evidence.py              # AudioEvidenceRecorder — saves WAV evidence clips
│   ├── session_recorder.py      # SessionAudioRecorder — continuous session WAV
│   └── pipeline.py              # AudioPipeline (1527 lines) — orchestrator
└── video/
    ├── __init__.py
    ├── camera.py                # CameraStream — threaded capture + reconnect
    ├── detector.py              # HumanDetector — YOLOv8/YOLO11 person+phone
    ├── tracker.py               # ObjectTracker — BoT-SORT, EMA smoothing, ID lock
    ├── registry.py              # GlobalStudentRegistry, StudentSpatialState
    ├── neighbors.py             # NeighborComputer — k-NN + paper assignment
    ├── face_mesh.py             # FaceMeshExtractor — MediaPipe (unused in pipeline)
    ├── face_mesh_worker.py      # Shared-memory MP worker (unused in pipeline)
    ├── gaze.py                  # compute_gaze_direction() — shared math
    ├── reid.py                  # FaceReIdentifier — 75-D Procrustes embeddings
    ├── cheating_evaluator.py    # CheatingEvaluator — gaze rules + on_alert
    ├── tools_detector.py        # ToolsDetector — paper/phone YOLO model
    ├── video_logger.py          # VideoLogger — non-blocking JSON-Lines logger
    ├── jpeg_buffer.py           # JPEGFrame, encode_frame, decode_frame
    ├── timestamps.py            # draw_timestamp_overlay() — shared utility
    ├── visualizer.py            # VideoVisualizer — all OpenCV drawing
    └── pipeline.py              # VideoPipeline (2198 lines) — orchestrator
```

---

## Step 2: Component Map

### Video subsystem

```
CameraStream
  └─ background reader thread (deque[5])
  └─ reconnect logic (RTSP or webcam)

HumanDetector (YOLO)
  ├─ person class 0
  └─ phone class 67 (joint or dedicated model)

ToolsDetector (YOLO)
  └─ paper / phone labels (configurable)

ObjectTracker (BoT-SORT)
  ├─ EMA bbox smoothing (α=0.5)
  ├─ ID locking after 10 consecutive ReID matches
  └─ remove_tracks() for expired ID pruning

GlobalStudentRegistry
  └─ StudentSpatialState per track_id
      ├─ bbox, center, paper_center
      ├─ face_mesh, face_embedding
      ├─ neighbors, neighbor_papers, surrounding_papers
      ├─ is_cheating, cheating_cooldown, suspicious_start_time
      ├─ cheating_target_paper, cheating_target_neighbor
      ├─ is_using_phone, phone_bbox
      ├─ is_alert_recording, recording_buffer (deque[1800 JPEGFrame])
      └─ frames_to_record

NeighborComputer
  ├─ compute_neighbors() — vectorised pairwise Euclidean distance, k=4
  └─ compute_paper_neighbors() — greedy 1-to-1 paper → student assignment

FaceReIdentifier
  └─ 75-D Procrustes-aligned 3D landmark embeddings
  └─ Quality-weighted EMA update; cosine similarity match

CheatingEvaluator
  └─ gaze evaluation per student (calls compute_gaze_direction)
  └─ Grace period (2s) before resetting suspicious timer
  └─ Cooldown (N frames) before clearing is_cheating
  └─ receives SimClock, uses clock.now()

VideoVisualizer
  └─ draw() — single call produces annotated frame
  └─ mic placement interactive mode
  └─ All toggle flags (neighbors, paper, phone, gaze, mesh, …)

VideoLogger (singleton)
  └─ Non-blocking queue → RotatingFileHandler (JSON-Lines)
  └─ Background QueueListener thread

VideoPipeline (orchestrator)
  ├─ Main thread: camera loop → _process_frame()
  ├─ DetectionThread: periodic YOLO (both models)
  ├─ FaceMesh ThreadPoolExecutor (N workers, IMAGE mode)
  ├─ GazeAlertWriter ThreadPoolExecutor (max 2)
  ├─ PhoneAlertWriter ThreadPoolExecutor (max 2)
  ├─ ArchiveWriter background thread
  └─ ConstantVelocityExtrapolator (kept but superseded by sticky-bbox)
  └─ buffer stores JPEG-compressed frames (JPEGFrame)
```

### Audio subsystem

```
AudioSource (ABC)
  ├─ FileAudioSource — reads WAV files, advances SimClock
  └─ LiveMicSource — sounddevice callback

AudioPreprocessor
  └─ Bandpass filter, normalise, de-noise

GlobalLocalDiscriminator
  └─ Silero VAD — distinguishes local human speech from TV/PA

KeywordDetector
  └─ Whisper (or VAD-only mode) — keyword extraction

AudioEvidenceRecorder
  └─ Saves WAV clip evidence

SessionAudioRecorder
  └─ Continuous session WAV

EpisodeTracker
  ├─ Opens / extends / confirms CheatEpisode per mic
  └─ Closes after grace period (default 5 s)

AsyncAudioWriter
  └─ Background queue thread for non-blocking file I/O

AudioPipeline (orchestrator)
  ├─ Main loop: source.read() → preprocess → VAD worker queue
  ├─ VAD worker thread: discriminator → keyword detector → AlertQueue
  ├─ Whisper worker thread: transcription + keyword matching
  └─ on_audio_alert callback → AVAlertComposer
```

### Cross-cutting

```
SimClock — monotonic clock wrapper (shared by video + audio sources)
MicLayout — persistent mic pin DB (JSON file), normalized coords
AVAlertComposer — receives alerts from BOTH pipelines, muxes A/V via ffmpeg
  └─ _draw_mic_pins() for visual overlay
  └─ ThreadPoolExecutor(max_workers=2) instead of raw threads
  └─ _mux_and_save uses -af apad -shortest
```

---

## Step 3: Data Flow Diagrams

### 3a. Gaze-triggered alert path

```
Camera HW
  │  frame (BGR ndarray)
  ▼
CameraStream._update_loop()
  │  FrameData { frame, timestamp, index }
  │  [deque, maxlen=5]
  ▼
VideoPipeline.run()  ← main thread loop
  │
  ├─ _process_frame()
  │    │
  │    ├─ [1] JPEG-encode → _global_frame_buffer (deque, maxlen=post_buffer) stores JPEGFrame
  │    │       also → video_buffers[cam_id] (shared with AVAlertComposer) stores JPEGFrame
  │    │
  │    ├─ [2] _detection_queue.get_nowait()  ← async result from DetectionThread
  │    │       Split person vs phone detections
  │    │
  │    ├─ [3] ObjectTracker.update(person_dets, frame)
  │    │       → EMA-smoothed TrackedObjects
  │    │       → ID Alias translation (ReID re-mapping)
  │    │
  │    ├─ [4] Detection Stability Filter
  │    │       Injects predicted-bbox mock tracks for selected students
  │    │       missing from YOLO for ≤90 frames
  │    │
  │    ├─ [5] NMS dedup (IoU ≥ 0.45 suppresses ghost tracks)
  │    │
  │    ├─ [6] Auto-select: new track_ids → _selected_ids
  │    │
  │    ├─ [7] GlobalStudentRegistry.update()
  │    │       Prune expired > 3s → notify ReID, tracker, aliases
  │    │
  │    ├─ [8] NeighborComputer.compute_neighbors()  [skip-if-stable, Δ<20px]
  │    │       NeighborComputer.compute_paper_neighbors()
  │    │         Assigns YOLO papers 1-to-1 (greedy argmin)
  │    │         Fallback: paper_center for selected students (aspect ratio ≤ 2.5)
  │    │
  │    ├─ [9] Face-mesh submission (ThreadPoolExecutor)
  │    │       fm_frame = resize to ≤1080p for MediaPipe
  │    │       _fm_thread_infer(fm_frame, bbox, fm_scale, track_id)
  │    │         → IMAGE mode FaceLandmarker (per-thread)
  │    │         → FaceMeshResult { landmarks_2d, landmarks_3d, head_matrix }
  │    │         → saved to reg_state.face_mesh (atomic CPython write)
  │    │       done_callback:
  │    │         → FaceReIdentifier.match() + register_embedding()
  │    │         → ObjectTracker.verify_embedding_match() [ID lock]
  │    │
  │    ├─ [10] CheatingEvaluator.evaluate(track_id)  ← EVERY frame, main thread
  │    │         Snapshot reg_state.face_mesh → compute_gaze_direction()
  │    │         gaze_dir = head_3d_forward + iris_deviation × 3.0 (clamped)
  │    │         For each paper in surrounding_papers:
  │    │           dot(gaze_dir, paper_direction) > cos(risk_angle_tolerance)?
  │    │             → suspicious_start_time accumulation
  │    │             → if ≥ suspicious_duration_threshold:
  │    │                 state.is_cheating = True
  │    │                 → on_alert(state)  ← callback set by pipeline
  │    │
  │    ├─ [11] Alert Recording Collector  ← main thread, after eval
  │    │         is_cheating=T, recording=F  → START
  │    │           pre-frames = last N JPEGFrame from _global_frame_buffer
  │    │           state.recording_buffer = deque(pre_frames, maxlen=300)
  │    │         is_cheating=T, recording=T  → DURING: append JPEGFrame
  │    │         is_cheating=F, recording=T  → POST: countdown frames_to_record
  │    │           → _save_alert_video_async(snapshot, track_id, …)
  │    │               → GazeAlertWriter thread pool
  │    │               → _render_alert_frame() per frame (red bbox, paper box, gaze line)
  │    │               → IF _composer: _composer.on_video_alert(frames, …)
  │    │                     → AVAlertComposer: nearest_mic lookup
  │    │                     → audio_buffer extraction for time window (timestamp_start = suspicious_start_time, pre-roll = suspicious_duration_threshold + 2.0s)
  │    │                     → _draw_mic_pins (red=source, green=others)
  │    │                     → _mux_and_save() background thread → ffmpeg (apad)
  │    │               → ELSE: standalone cv2.VideoWriter fallback
  │    │
  │    └─ [12] Archive frame write (non-blocking queue → ArchiveWriter thread)
  │
  └─ Yield PipelineFrame → run.py display loop → cv2.imshow()
```

### 3b. Audio-triggered alert path

```
AudioSource.read()
  │  AudioChunk { mic_data[N_mics, N_samples], timestamp, … }
  ▼
AudioPipeline._process_chunk()  ← main audio loop
  │
  ├─ AudioPreprocessor.process() — bandpass, norm, de-noise per mic
  │
  ├─ audio_buffers[mic_id].append((timestamp, chunk)) — shared with AVAlertComposer
  │
  ├─ SessionAudioRecorder.add_chunk()
  │
  ├─ VAD worker queue.put(chunk)
  │
  └─ EpisodeTracker.on_chunk()
       → returns completed CheatEpisodes → AudioEvidenceRecorder.save()

VAD worker thread
  │  Receives chunk from queue
  ▼
  GlobalLocalDiscriminator.classify()
    Silero VAD: is_speech?
    Spectrum / ZCR / spectral contrast: local vs global (TV/PA) source?
  │
  ├─ If NOT suspicious: skip
  └─ If suspicious human speech:
       →  Whisper worker queue.put(_WhisperTask)

Whisper worker thread
  │  Receives _WhisperTask
  ▼
  KeywordDetector.detect()
    Whisper transcription → keyword matching
    OR VAD-only mode: no transcription needed
  │
  ├─ No keywords found: skip
  └─ Keywords found:
       → AudioAlert { mic_id, timestamp, audio_clip, keywords, … }
       → EpisodeTracker.on_alert(alert)
       → AudioPipeline._on_alert_detected(alert)
             → composer.on_audio_alert(
                   audio_clip  = alert.audio_clip,
                   mic_id      = alert.mic_id,
                   timestamp_start = alert.timestamp_start,
                   timestamp_end   = alert.timestamp_end,
                   keywords    = alert.keywords,
                   sample_rate = alert.sample_rate,
               )

AVAlertComposer.on_audio_alert()
  │
  ├─ layout.camera_for_mic(mic_id)  → camera_id
  ├─ video_buffers[camera_id]       → frame time window lookup
  │    window = [ts_start - 1.0s, ts_end + 1.0s] (symmetric padding)
  │    decode JPEG frames in window
  ├─ audio_buffers[mic_id]         → audio segment extraction
  ├─ Annotate frames: student bboxes + timestamp overlay + _draw_mic_pins()
  │    source mic = RED, others = GREEN
  └─ _mux_and_save() background thread (apad)
       temp_video.mp4 + temp_audio.wav → ffmpeg → output alert.mp4
```

### 3c. Phone-triggered alert path

```
DetectionThread
  │  HumanDetector.detect() — joint person+phone inference
  │  ToolsDetector.detect() — separate tools model
  ▼
VideoPipeline._process_frame() step [2]
  Split detections: phone class 67 → ToolDetection(label="phone")
  Merge into tools_result

Step [8]: phone_tools filter
  For each phone tool: find nearest active student within 300px
    → nearest.is_using_phone = True
    → nearest.is_cheating = True (immediate)
    → nearest.cheating_cooldown = post_buffer_frames

CheatingEvaluator (gaze path disabled for phone — is_using_phone overrides)
  ↓ no gaze check needed; is_cheating already True

Alert Recording Collector [11]
  → state.is_cheating=T → START recording
  → JPEGFrame with phone_bboxes stored
  → _save_alert_video_async(…, cheat_type="phone", cheat_ctx={phone_bbox, …})
      → _render_alert_frame() draws red PHONE bbox + banner
      → IF _composer: on_video_alert(alert_type="phone", subject_point=phone_center)
            → nearest_mic lookup → audio extraction → ffmpeg mux
      → ELSE: standalone VideoWriter fallback

Parallel: Phone global alert (independent of student)
  _phone_is_recording state machine:
    START: snapshot _global_frame_buffer pre-roll
    DURING: append JPEGFrame(phone_bboxes=[…])
    POST countdown: _save_phone_alert_video_async()
      → on_video_alert(alert_type="phone", subject_point=phone_center)
      OR standalone writer
```

---

## Step 4: Shared State Map

| State field | Owner | Written by | Read by | Lock? |
|---|---|---|---|---|
| `reg_state.face_mesh` | `StudentSpatialState` | FM worker thread (callback) | Main thread (evaluator, visualizer), FM worker | None (CPython atomic assign) |
| `reg_state.is_cheating` | `StudentSpatialState` | `CheatingEvaluator` (main thread) | Alert collector (main thread), visualizer | None (single writer, main thread) |
| `reg_state.recording_buffer` | `StudentSpatialState` | Main thread (collector) | Alert writer thread (snapshot copy) | None (snapshot taken before hand-off) |
| `_global_frame_buffer` | `VideoPipeline` | Main thread | Alert writer thread (snapshot copy) | `_buffer_lock` (RLock) |
| `video_buffers[cam_id]` | `run.py` | Main thread (via `frame_buffer` arg) | `AVAlertComposer` (audio/video threads) | None (deque thread-safe for append/popleft) |
| `audio_buffers[mic_id]` | `run.py` | Audio pipeline main loop | `AVAlertComposer` | None (deque append is atomic) |
| `_pending_fm_futures` | `VideoPipeline` | Main thread | Main thread | None (single writer) |
| `_fm_cache` | `VideoPipeline` | FM worker threads | FM worker threads, main thread | `_fm_cache_lock` (threading.Lock) |
| `_registry._states` | `GlobalStudentRegistry` | Main thread (`update`) | All threads (read-only via `get`, `get_all`) | `_lock` (threading.Lock) |
| `_selected_ids` | `VideoPipeline` | Main thread | Main thread | None |
| `_track_aliases` | `VideoPipeline` | FM callback thread | Main thread | ✅ `_alias_lock` (threading.Lock) |
| `JPEGFrame buffers` | `VideoPipeline` / `registry.py` | Main thread | Alert writer thread | None (deque append is atomic) |
| `MicLayout.pins` | `MicLayout` | `add_pin()` (mouse handler) | `get_pins_for_camera()`, `nearest_mic_for_point()` | `_lock` (threading.Lock) |
| `_episodes` | `EpisodeTracker` | VAD/Whisper workers | Audio main loop | `_lock` (threading.Lock) |

---

## Step 5: Configuration Map

All settings are Pydantic `BaseSettings` (env vars or `.env` file).

### Camera / Video
| Env var | Default | Effect |
|---|---|---|
| `CAMERA_SOURCE` | `0` | Webcam index, RTSP URL, or file path |
| `CAMERA_WIDTH` / `CAMERA_HEIGHT` | `1280/720` | Requested capture resolution |
| `CAMERA_FPS` | `30` | Target FPS |

### YOLO Detection
| Env var | Default | Effect |
|---|---|---|
| `YOLO_MODEL` | `yolo11n.pt` | Person detection model |
| `DETECTION_CONFIDENCE` | `0.5` | Person confidence threshold |
| `DETECTION_INTERVAL` | `1.0` | Seconds between YOLO runs |
| `DETECTION_IMGSZ` | `1280` | YOLO input resolution |
| `YOLO_PHONE_DETECTION` | `True` | Joint person+phone inference |
| `PHONE_CLASS_ID` | `67` | COCO class for phone |
| `PHONE_CONFIDENCE` | `0.4` | Phone detection threshold |
| `PHONE_MODEL` | `""` | Dedicated phone model (empty = shared) |
| `TOOLS_MODEL` | `best.pt` | Tools (paper) detection model |
| `TOOLS_CONFIDENCE` | `0.3` | Tools detection threshold |
| `TOOLS_TARGET_LABELS` | `["paper"]` | Filtered labels |

### Tracking
| Env var | Default | Effect |
|---|---|---|
| `TRACKING_MAX_DISTANCE` | `200` | BoT-SORT max distance |
| `TRACKING_MAX_AGE` | `30` | BoT-SORT track buffer frames |
| `REID_WEIGHTS_PATH` | `osnet_x0_25_…` | ReID model file |

### Gaze / Cheating
| Env var | Default | Effect |
|---|---|---|
| `RISK_ANGLE_TOLERANCE` | `40` | Degrees; gaze cone half-angle |
| `SUSPICIOUS_DURATION_THRESHOLD` | `3.0` | Seconds looking at paper before alert |
| `NEIGHBOR_K` | `4` | k-nearest-neighbor count |
| `REID_MATCH_THRESHOLD` | `0.80` | Cosine similarity for ReID |

### Recording / Output
| Env var | Default | Effect |
|---|---|---|
| `ALERTS_DIR` | `alerts` | Directory for alert clips |
| `ARCHIVE_DIR` | `archive` | Directory for archive recording |
| `ARCHIVE_MODE` | `raw` | `raw` or `annotated` |
| `ALERT_MAX_HEIGHT` | `720` | Max height for alert clips |
| `VIDEO_QUALITY` | `75` | JPEG/codec quality (50/75/90) |
| `FACE_MESH_WORKERS` | `4` | Thread pool size for MediaPipe |

### Audio
| Env var | Default | Effect |
|---|---|---|
| `AUDIO_SAMPLE_RATE` | `16000` | Sample rate (Hz) |
| `AUDIO_VAD_MODE` | `vad_only` | `vad_only` or `whisper` |
| `AUDIO_EPISODE_MIN_SEC` | `3.0` | Min sustained duration to confirm |
| `AUDIO_EPISODE_GRACE_SEC` | `5.0` | Silence gap before closing episode |

### Logging
| Env var | Default | Effect |
|---|---|---|
| `VIDEO_LOG_ENABLED` | `True` | Enable structured diagnostic log |
| `VIDEO_LOG_DIR` | `logs` | Log directory |
| `VIDEO_LOG_LEVEL` | `DEBUG` | Log level |
| `VIDEO_LOG_MAX_BYTES` | `100MB` | Rotation size |

---

## Step 6: Verification (Gaps & Cross-checks)

### What I confirmed by code (not assumption):

1. **Face mesh uses IMAGE mode in the pipeline**, not VIDEO mode.
   - `FaceMeshExtractor` (VIDEO mode) and `face_mesh_worker.py` (MP process, IMAGE mode) exist but are **NOT imported or used** by `pipeline.py`.
   - `pipeline.py` contains its own inline `_fm_thread_infer()` method that directly creates `FaceLandmarker` in `IMAGE` mode per thread via `threading.local()`.
   - The `FaceMeshExtractor` class is therefore **dead code** in the current running system.

2. **`ConstantVelocityExtrapolator` is live but superseded.**
   - It is instantiated and updated (history + velocity stored).
   - However, the intermediate-frame code replaced extrapolated bbox with "sticky" last-known bbox (`TrackedObject(is_predicted=True)`). The extrapolator's `extrapolate()` method is called but only in `_tracker.get_predicted_bbox()` path, which is the second fallback if BoT-SORT's internal `lost_stracks` doesn't have a prediction.

3. **Double-duplicate logging of camera disconnect.**
   - `CameraStream._update_loop()` logs `"Camera stream disconnected — video buffer is now stale."` on **both** the EOF branch (line 190) and again unconditionally at line 220 (after the loop ends). Every disconnect produces two identical log lines.

4. **`_fm_cache` in `VideoPipeline` vs `_mesh_cache` in `FaceMeshExtractor`.**
   - These are completely separate caches. The pipeline's `_fm_cache` is used and maintained correctly. The `FaceMeshExtractor._mesh_cache` is never populated in production since the extractor is never called.

5. **`video_buffers` populated correctly.**
   - In `run.py`, `frame_buffer=video_buffers[cam_id]` is passed to `VideoPipeline`.
   - Inside `_process_frame`, JPEG bytes are appended as `(frame_data.timestamp, _jpeg_bytes)` via `self._frame_buffer.append(...)`.
   - `AVAlertComposer.on_audio_alert` reads this buffer and calls `jpeg_decode(frame)` when it sees `bytes`.

6. **`audio_buffers` populated correctly.**
   - `AudioPipeline` receives `audio_buffers` dict reference.
   - After preprocessing, each mic's processed chunk is appended as `(chunk.timestamp, processed_chunk)`.
   - `AVAlertComposer` reads these tuples in timestamp order.

7. **SimClock is used for video only.**
   - `CameraStream.__init__` accepts `clock=clock`.
   - Audio `FileAudioSource` also advances `SimClock`.
   - Real-time synchronisation between audio and video relies on both sources advancing the same `SimClock` and writing matching timestamps to their shared buffers.

8. **`_track_aliases` has a benign race.**
   - Written by FM callback thread (`self._track_aliases[track_id] = best_id`) and read/iterated by main thread.
   - In CPython, dict assignment is atomic under the GIL, but iteration is not. The main thread's cleanup loop (`keys_to_delete = [k for k, v in self._track_aliases.items() if ...]`) can theoretically raise `RuntimeError: dictionary changed size during iteration` if a callback fires simultaneously.
   - **Risk: LOW** in practice (FM callbacks are infrequent), but not zero.

---

## Step 7: Gap Analysis

### Architecture gaps

| ID | Gap | Severity | Notes |
|---|---|---|---|
| G-1 | `FaceMeshExtractor` + `face_mesh_worker.py` are dead code | LOW | They work but are never invoked. Can be removed or re-integrated. |
| G-2 | `_track_aliases` dict modified from 2 threads without a lock | MEDIUM | FIXED |
| G-3 | Double "camera disconnected" log line in `CameraStream` | LOW | Line 220 fires after every normal EOF. Remove or conditionalize. |
| G-4 | `ConstantVelocityExtrapolator` partially bypassed | LOW | History is maintained but extrapolated bbox is only used as second-level fallback in `get_predicted_bbox()`. Comment is misleading. |
| G-5 | `AVAlertComposer._mux_and_save` uses unbounded daemon threads | MEDIUM | FIXED |
| G-6 | `MicLayout.load()` silently falls back to `(0.5, 0.5)` for unknown format | LOW | FIXED |
| G-7 | `ffmpeg` is required at runtime but only checked once at startup | LOW | If ffmpeg is killed or uninstalled mid-session, `subprocess.run` will raise inside daemon threads with no user-facing notification. |
| G-8 | No cap on `_pending_fm_futures` growth per student across cycles | LOW | The cap is `max_pending=100` total, but a single student can accumulate many futures if the executor is backlogged. The per-student "skip if pending" check prevents duplication within one cycle but not across many cycles for the same student. |
| G-9 | Archive writer `deque(maxlen=60)` can silently drop frames | LOW | If disk is slow and the queue fills, frames are dropped. The warning log exists but no user-facing indicator. |
| G-10 | `VideoLogger` singleton is never closed on `KeyboardInterrupt` in `run.py` | LOW | `run.py` calls `vp.stop()` (which calls `_vlog.close()`) but only on `KeyboardInterrupt`. On normal thread exit the logger closes correctly via `vp.stop()`. Risk: last few log lines may be lost on SIGKILL. |
| G-11 | `jpeg_buffer.py` integration | INFO | New production file, JPEG compression applies to all video buffers. |


---

## Summary

The system is a **multi-threaded, multi-pipeline architecture** where:

- **Video pipeline** runs on one thread per camera, with async sub-threads for YOLO detection, face mesh inference, alert video writing, and archive writing.
- **Audio pipeline** runs on a dedicated thread with VAD and Whisper workers.
- **Shared buffers** (`audio_buffers`, `video_buffers`) bridge the two pipelines through the `AVAlertComposer`.
- **Alert composition** is fully asynchronous: muxing happens in background daemon threads, never blocking the real-time camera loop.
- The **critical path** per frame is: read → JPEG-encode → tracking update → neighbor compute → cheating evaluate → alert collect → visualize → archive enqueue. Face mesh is genuinely async and off the critical path.
- **Memory** is kept bounded via JPEG compression (~28-41× reduction), deque maxlen limits, and alert recording caps (max 3 concurrent).
