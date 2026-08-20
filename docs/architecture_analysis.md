# Thaqib Smart Cheating Detection System — Architecture Analysis

> **Last Updated**: 2026-06-21 — Full Codebase Review
> **Status**: All findings from previous rounds are resolved. This document reflects the current, final state of the codebase.
> **Methodology**: All conclusions below are drawn from direct, line-by-line reading of the source code. Docstrings, README files, and walkthrough documents were **not** used as sources.

---

## Step 1: Project Inventory

### Top-level

| File / Dir | Role |
|---|---|
| `run.py` | Single entry point. Parses CLI (`--video cam0=...`, `--audio mic0=...`), validates file paths, creates shared objects, launches threads via `threading.Barrier`. |
| `src/thaqib/` | Main installable package (`thaqib`) |
| `models/` | YOLO `.pt` weights + `face_landmarker.task` (MediaPipe) + OSNet ReID weights |
| `scripts/` | `demo_video.py`, `demo_audio.py` — standalone demo / testing scripts |
| `alerts/` | Runtime output — alert `.mp4` clips (AV-merged via ffmpeg) |
| `archive/` | Runtime output — continuous session recording (raw or annotated) |
| `sessions/` | Runtime output — continuous session WAV recordings per mic |
| `audio alerts/` | Runtime output — WAV evidence clips + JSON metadata |
| `logs/` | Runtime output — `VideoLogger` JSON-Lines diagnostic logs |

### `src/thaqib/` package tree

```
thaqib/
├── __init__.py                  # Package metadata
├── sim_clock.py                 # SimClock — time.monotonic() wrapper, shared across all pipelines
├── mic_layout.py                # MicLayout, MicPin — persistent normalized mic position DB (JSON)
├── av_alert_composer.py         # AVAlertComposer — archive-based A/V mux + clip saver
├── config/
│   ├── __init__.py              # re-exports get_settings()
│   └── settings.py              # Pydantic BaseSettings (all AUDIO_* / VIDEO_* env vars)
├── audio/
│   ├── models.py                # AudioChunk, AudioAlert, CheatEpisode, SoundClassification
│   ├── source.py                # AudioSource ABC + FileAudioSource, LiveMicSource
│   ├── preprocessor.py          # AudioPreprocessor — HPF, normalise, spectral de-noise, transient suppression
│   ├── discriminator.py         # GlobalLocalDiscriminator — Silero VAD + energy/spectral local-vs-global filter
│   ├── keyword_detector.py      # KeywordDetector — Whisper STT or VAD-only fast path
│   ├── evidence.py              # AudioEvidenceRecorder — saves WAV + JSON evidence clips
│   ├── session_recorder.py      # SessionAudioRecorder — continuous session WAV (all mics)
│   └── pipeline.py              # AudioPipeline (~1556 lines) — full orchestrator
└── video/
    ├── __init__.py
    ├── camera.py                # CameraStream — threaded capture + reconnect
    ├── detector.py              # HumanDetector — YOLOv11 person + phone (joint or dedicated)
    ├── tracker.py               # ObjectTracker — BoT-SORT, EMA smoothing, ID lock
    ├── registry.py              # GlobalStudentRegistry, StudentSpatialState
    ├── neighbors.py             # NeighborComputer — k-NN + greedy paper assignment
    ├── face_mesh.py             # FaceMeshResult dataclass + FaceMeshExtractor (dead code)
    ├── face_mesh_worker.py      # Shared-memory MP worker (dead code — never invoked)
    ├── gaze.py                  # compute_gaze_direction() — single source of truth for gaze math
    ├── reid.py                  # FaceReIdentifier — 75-D Procrustes embeddings + cosine match
    ├── cheating_evaluator.py    # CheatingEvaluator — gaze/cooldown rules + on_alert callback
    ├── tools_detector.py        # ToolsDetector — paper/phone YOLO model (custom `best.pt`)
    ├── video_logger.py          # VideoLogger — non-blocking JSON-Lines diagnostic logger
    ├── jpeg_buffer.py           # JPEGFrame, encode_frame, decode_frame — in-buffer compression
    ├── timestamps.py            # draw_timestamp_overlay() — multi-line SYS + Offset stamp
    ├── visualizer.py            # VideoVisualizer — all OpenCV drawing + interactive mic placement
    └── pipeline.py              # VideoPipeline (~2283 lines) — full orchestrator
```

---

## Step 2: Component Map

### Video subsystem

```
CameraStream
  └─ background reader thread (deque[5] raw frames)
  └─ reconnect logic (RTSP, webcam, or file)
  └─ FrameData { frame, timestamp (SimClock), frame_index }

HumanDetector (YOLO11)
  ├─ person class 0
  └─ phone class 67 (COCO) — via joint inference or dedicated phone model

ToolsDetector (YOLO custom best.pt)
  └─ paper / phone labels (configurable via TOOLS_TARGET_LABELS)

ObjectTracker (BoT-SORT)
  ├─ EMA bbox smoothing (α=0.5)
  ├─ ID locking after N consecutive ReID matches
  └─ remove_tracks() for expired ID pruning + get_predicted_bbox()

ConstantVelocityExtrapolator
  └─ Velocity-based bbox prediction (second-level fallback only)
  └─ Prune called each frame to prevent unbounded memory growth

GlobalStudentRegistry
  └─ StudentSpatialState per track_id
      ├─ bbox, center, paper_center, frame_index, timestamp
      ├─ face_mesh (FaceMeshResult), face_embedding (np.ndarray)
      ├─ neighbors, neighbor_distances, neighbor_papers, surrounding_papers
      ├─ detected_paper, is_heuristic_paper
      ├─ is_cheating, cheating_cooldown, suspicious_start_time
      ├─ cheating_target_paper, cheating_target_neighbor
      ├─ is_using_phone, phone_bbox
      ├─ is_alert_recording, recording_buffer (deque[1800 JPEGFrame])
      ├─ frames_to_record, fm_last_frame
      └─ metadata_history (deque[600])

NeighborComputer
  ├─ compute_neighbors() — vectorised pairwise Euclidean distance, k=NEIGHBOR_K
  └─ compute_paper_neighbors() — greedy 1-to-1 paper → student assignment (argmin)

FaceReIdentifier
  └─ 75-D Procrustes-aligned 3D landmark embeddings
  └─ Quality-weighted EMA update; cosine similarity match
  └─ is_locked(track_id) prevents re-ID for permanently locked IDs

CheatingEvaluator
  └─ evaluate(track_id, current_time) — called every frame on main thread
  └─ Uses SimClock (clock.now()) — NOT time.time() — for correct file-based timing
  └─ Grace period (GRACE_PERIOD=2s) on face loss — prevents timer reset on glitches
  └─ Cooldown (N frames) before clearing is_cheating after gaze breaks
  └─ Patches registry.update() to reset is_using_phone each frame
  └─ on_alert callback fired exactly once when is_cheating first becomes True

VideoVisualizer
  └─ draw() — single call produces annotated frame
  └─ Interactive mic placement mode (toggle with 'I' key)
  └─ Toggle flags: neighbors (T), panel (P), paper (D), phone (F), gaze lines (L), mesh (K), timestamp (W)

VideoLogger (singleton, non-blocking)
  └─ Background QueueListener → RotatingFileHandler (JSON-Lines)
  └─ log_startup, log_camera_open, log_detection_result, log_tracking_update
  └─ log_gaze_check, log_cheating_detected, log_phone_detected
  └─ log_alert_recording_start, log_recording_cap_hit

VideoPipeline (orchestrator, ~2283 lines)
  ├─ Main thread: camera loop → _process_frame()
  ├─ DetectionThread: periodic YOLO (both models), runs at DETECTION_INTERVAL seconds
  ├─ FaceMesh ThreadPoolExecutor (FACE_MESH_WORKERS threads, IMAGE mode, lazy init)
  │    └─ FACE_MESH_INTERVAL = 3 frames between submissions per student
  ├─ GazeAlertWriter ThreadPoolExecutor (max_workers=2)
  ├─ PhoneAlertWriter ThreadPoolExecutor (max_workers=2)
  ├─ ArchiveWriter background thread (queue-based, non-blocking)
  └─ ConstantVelocityExtrapolator (history maintained; bbox used as second-level fallback)
  └─ All buffers store JPEG-compressed frames (JPEGFrame) — ~30× memory reduction
```

### Audio subsystem

```
AudioSource (ABC)
  ├─ FileAudioSource — reads WAV files chunk-by-chunk, advances SimClock
  └─ LiveMicSource — sounddevice callback, real-time ingestion

AudioPreprocessor
  └─ High-pass filter (HPF_CUTOFF Hz)
  └─ Spectral noise reduction (learned room profile, NOISE_REDUCTION_STRENGTH)
  └─ Adaptive gain control (RMS normalisation)
  └─ Transient suppression (pen clicks, paper shuffling — TRANSIENT_THRESHOLD/DAMPING)

GlobalLocalDiscriminator
  └─ Silero VAD per mic — confirms human speech
  └─ Energy ratio + ZCR + spectral contrast: local vs global (TV/PA) classification
  └─ 2-mic shortcut: imbalance ratio vs calibrated baseline (LOCAL_RATIO_MULTIPLIER)
  └─ Cross-correlation validation (optional, AUDIO_CROSS_CORRELATION)
  └─ Periodic baseline recalibration (RECALIBRATION_INTERVAL_SEC)

KeywordDetector
  └─ VAD-only fast path: any speech → alert immediately (VAD_ONLY=True)
  └─ Whisper STT path: transcription + keyword matching (strict or keyword mode)
  └─ Adaptive VAD threshold calibration (ADAPTIVE_VAD=True)
  └─ VAD context window (VAD_CONTEXT_MS) for temporal continuity
  └─ Health-monitor-driven beam_size reduction under load

AudioEvidenceRecorder
  └─ Saves WAV clip + JSON metadata per alert

SessionAudioRecorder
  └─ Continuous session WAV (all mics, timestamped subdirectory)
  └─ Writes raw + processed audio streams

EpisodeTracker
  ├─ on_alert(alert) → opens or extends CheatEpisode per mic
  ├─ Confirms episode after EPISODE_MIN_SEC of sustained alerts
  ├─ on_chunk(chunk) → accumulates audio, closes after EPISODE_GRACE_SEC idle
  └─ flush() → force-close on pipeline shutdown

AsyncAudioWriter
  └─ Background queue thread (maxsize=200) for non-blocking file I/O

AudioPipeline (orchestrator, ~1556 lines)
  ├─ Main loop: source.get_chunk() → session_recorder → episode_tracker → _process_chunk()
  ├─ VAD worker thread: discriminator → VAD-only alert OR Whisper queue
  ├─ Whisper worker thread: KeywordDetector.detect() → _dispatch_audio_alert()
  ├─ Health Monitor thread: monitors queue depths, reduces beam_size under load,
  │    reports dropped_chunks every 60s
  ├─ Dynamic mic_registry built from CLI mic_ids (NOT from AUDIO_MIC_NAMES .env var)
  └─ _on_alert_detected() → composer.compose_audio_alert(wav_path, mic_id, camera_ids, start_sec, end_sec)
```

### Cross-cutting

```
SimClock
  └─ time.monotonic() wrapper — shared by video CameraStream and audio FileAudioSource
  └─ Used for frame timestamps, suspicious_start_time comparisons, archive offsets

MicLayout
  └─ Persistent mic pin DB (mic_layout.json), normalized coords [0.0, 1.0]
  └─ add_pin() / get_pins_for_camera() / nearest_mic_for_point() — all lock-protected
  └─ Interactive placement via mouse callback + 'I' key in video window
  └─ camera_for_mic(mic_id) → returns camera_id for audio→video linking

AVAlertComposer (ARCHIVE-BASED — no memory buffers)
  └─ compose_video_alert(camera_id, mic_id, start_sec, end_sec, alert_type, subject_point)
       └─ Extracts video from video_archive file by seek (CAP_PROP_POS_MSEC)
       └─ _extract_and_annotate_video(): OpenCV VideoWriter with mp4v codec
       └─ Draws mic_pins + subject_point + dual timestamps per frame
       └─ Merges with audio_archive using ffmpeg (-map 0:v:0, -map 1:a:0, -c:v copy, -c:a aac, -shortest)
  └─ compose_audio_alert(alert_wav_path, mic_id, camera_ids, start_sec, end_sec)
       └─ alert_wav_path = pre-cut WAV already saved by AudioEvidenceRecorder
       └─ Extracts video segment from archive, annotates, merges with pre-cut WAV
  └─ update_video_archive(camera_id, archive_path)
       └─ Called by VideoPipeline when a new archive file is created (live camera mode)
       └─ Ensures composer always seeks in the currently-being-written archive file
  └─ _draw_mic_pins(): source mic = RED, others = GREEN
  └─ draw_timestamp_overlay(ts, archive_offset_sec): SYS time + Offset on every frame
  └─ stop() / shutdown() — compatibility stubs (no executor to shut down)
  └─ ffmpeg stderr=subprocess.PIPE; RuntimeError raised with decoded stderr on failure
```

---

## Step 3: Data Flow Diagrams

### 3a. Gaze-triggered alert path

```
Camera HW
  │  raw BGR frame
  ▼
CameraStream._update_loop()
  │  FrameData { frame, timestamp (SimClock.now()), frame_index }
  │  [deque, maxlen=5]
  ▼
VideoPipeline.run()  ← main thread loop
  │
  ├─ Optional: resize to processing resolution (G key cycles NATIVE/1080p/720p)
  │
  ├─ _process_frame()
  │    │
  │    ├─ [1] JPEG-encode → _global_frame_buffer (deque, maxlen=post_buffer_frames)
  │    │       post_buffer_frames = round(camera_fps * 2) — set at start()
  │    │
  │    ├─ [2] _detection_queue.get_nowait()  ← async result from DetectionThread
  │    │       Split: person dets → tracker; phone dets → merged into tools_result
  │    │
  │    ├─ [3] ObjectTracker.update(person_dets, frame)
  │    │       → EMA-smoothed TrackedObjects
  │    │       → Alias translation (with _alias_lock)
  │    │
  │    ├─ [4] Detection Stability Filter (sticky last-known bbox for ≤90 missing frames)
  │    │       IoU ghost-track suppression (≥0.4 IoU kills the predicted track)
  │    │
  │    ├─ [5] NMS dedup (IoU ≥ 0.45 suppresses duplicate active tracks)
  │    │
  │    ├─ [6] Auto-select: new track_ids → _selected_ids
  │    │
  │    ├─ [7] GlobalStudentRegistry.update()
  │    │       Prune expired (>3s lost) → notify ReID, tracker, fm_cache, aliases
  │    │       Save any in-progress recordings for expired tracks
  │    │
  │    ├─ [8] NeighborComputer.compute_neighbors()  [k-NN, every frame]
  │    │       NeighborComputer.compute_paper_neighbors()
  │    │         Assigns YOLO papers 1-to-1 (greedy argmin)
  │    │         Fallback: paper_center heuristic for selected students (is_heuristic_paper=True)
  │    │       Phone detection: nearest active student within 300px → is_using_phone=True
  │    │
  │    ├─ [9] Face-mesh submission (ThreadPoolExecutor, FACE_MESH_INTERVAL=3 frames)
  │    │       Downscale frame to ≤1080p for MediaPipe (fm_scale)
  │    │       _fm_thread_infer() in worker thread:
  │    │         → Per-thread FaceLandmarker (threading.local, IMAGE mode)
  │    │         → FaceMeshResult { landmarks_2d, landmarks_3d, head_matrix, bbox }
  │    │         → Cached in _fm_cache (0.3s staleness tolerance)
  │    │       done_callback (_make_fm_callback):
  │    │         → reg_state.face_mesh = result  (atomic CPython write)
  │    │         → FaceReIdentifier.match() → if new ID: _track_aliases[id] = best_id
  │    │         → FaceReIdentifier.register_embedding() → ObjectTracker.verify_embedding_match()
  │    │
  │    ├─ [10] CheatingEvaluator.evaluate(track_id, frame_data.timestamp)  ← EVERY frame
  │    │         Uses clock.now() / frame_data.timestamp — NOT time.time()
  │    │         Snapshot face_mesh locally (TOCTOU guard)
  │    │         Grace period (2s) on face loss — timer preserved during brief occlusions
  │    │         gaze_dir = compute_gaze_direction(face_mesh)
  │    │         For each paper in surrounding_papers:
  │    │           dot(gaze_dir, paper_dir) > cos(RISK_ANGLE_TOLERANCE)?
  │    │             → suspicious_start_time accumulation
  │    │             → if >= SUSPICIOUS_DURATION_THRESHOLD:
  │    │                 state.is_cheating = True (once only)
  │    │                 → on_alert(state) callback
  │    │         Not looking: suspicious_start_time = 0, cooldown countdown
  │    │
  │    ├─ [11] Alert Recording Collector  ← main thread, after eval
  │    │         is_cheating=T, recording=F  → START
  │    │           pre-frames = last N JPEGFrame from _global_frame_buffer (with _buffer_lock)
  │    │           state.recording_buffer = deque(pre_frames, maxlen=300)
  │    │           state.frames_to_record = post_buffer_frames (2s)
  │    │         is_cheating=T, recording=T  → DURING: append JPEGFrame, reset countdown
  │    │         is_cheating=F, recording=T  → POST: countdown frames_to_record
  │    │           → state.is_alert_recording = False; state.is_cheating = False
  │    │           → _save_alert_video_async(snapshot, track_id, …, cheat_ctx)
  │    │               → GazeAlertWriter thread pool (max_workers=2)
  │    │               → Calculates start_sec/end_sec = frame_index / fps (archive-accurate)
  │    │               → _render_alert_frame() per frame (red bbox, paper box, gaze line)
  │    │               → IF _composer: _composer.compose_video_alert(camera_id, mic_id, …)
  │    │                     → Extracts video from video_archive (seek by start_sec/end_sec)
  │    │                     → _draw_mic_pins + draw_timestamp_overlay (SYS + Offset)
  │    │                     → _merge_with_ffmpeg (audio_archive, -shortest)
  │    │               → ELSE: standalone cv2.VideoWriter fallback (JPEG sequence if all codecs fail)
  │    │
  │    └─ [12] Archive frame write (non-blocking queue → ArchiveWriter thread)
  │
  └─ Yield PipelineFrame → run.py display loop → cv2.imshow()
```

### 3b. Audio-triggered alert path

```
AudioSource.get_chunk()
  │  AudioChunk { mic_data[N_mics, N_samples], timestamp, chunk_index, duration_ms }
  ▼
AudioPipeline._run_loop()
  │
  ├─ Append to audio_buffers[mic_id] (shared deque — used by old buffer path, now legacy)
  │
  ├─ SessionAudioRecorder.write_chunk() (via AsyncAudioWriter)
  │
  ├─ _process_chunk() → AudioPreprocessor.process() per mic → GlobalLocalDiscriminator.classify()
  │
  ├─ If GLOBAL/SILENT: feed to noise profile learner (preprocessor.add_noise_sample)
  │
  └─ EpisodeTracker.on_chunk() → accumulate audio, check for closed episodes

VAD worker thread (_inference_worker)
  │  Receives LOCAL chunk from _inference_queue
  ▼
  GlobalLocalDiscriminator.classify()
    Silero VAD: is_speech? energy ratio: is_local?
  │
  ├─ If VAD_ONLY=True AND is_speech AND is_local:
  │    → Fire alert immediately (per-mic cooldown check)
  │    → AudioAlert { mic_id, timestamp, audio_clip }
  │    → _dispatch_audio_alert(alert)
  └─ If VAD_ONLY=False:
       → _whisper_queue.put(_WhisperTask) if speech buffer full

Whisper worker thread (_whisper_worker)
  │  Receives _WhisperTask
  ▼
  KeywordDetector.detect()
    Whisper transcription → keyword matching (strict or keyword mode)
    beam_size snapshotted under _monitor_lock (Fix C-4)
  │
  ├─ No keywords / no speech: skip
  └─ Match found:
       → AudioAlert { mic_id, timestamp, audio_clip, keywords, sample_rate }
       → EpisodeTracker.on_alert(alert)
       → _dispatch_audio_alert(alert)

_dispatch_audio_alert(alert)
  │
  ├─ _evidence_recorder.save_alert(alert) — WAV + JSON
  ├─ _episode_tracker.on_alert(alert) — episode management
  └─ IF _composer:
       → camera_ids = layout.cameras_for_mic(alert.mic_id)
       → AudioEvidenceRecorder saves WAV file
       → composer.compose_audio_alert(
             alert_wav_path = saved WAV path,
             mic_id         = alert.mic_id,
             camera_ids     = camera_ids,
             start_sec      = alert.timestamp_start,
             end_sec        = alert.timestamp_end,
         )

AVAlertComposer.compose_audio_alert()
  │
  ├─ For each camera_id: extract video from video_archive (seek by start_sec/end_sec)
  ├─ _extract_and_annotate_video() → OpenCV frame loop
  │    → _draw_mic_pins (source=RED, others=GREEN)
  │    → draw_timestamp_overlay(ts=time.time(), archive_offset_sec)
  ├─ _merge_with_ffmpeg(annotated_video, alert_wav, output)
  │    → ffmpeg -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -shortest
  │    → stderr captured and logged on failure (Fix E-1)
  └─ Cleanup temp video file
```

### 3c. Phone-triggered alert path

```
DetectionThread
  │  HumanDetector.detect() — joint person+phone inference
  │  ToolsDetector.detect() — custom tools model
  ▼
_process_frame() step [2]
  Phone class 67 dets → ToolDetection(label="phone")
  Merged into tools_result

Step [8]: phone_tools filter
  For each phone tool: nearest active student within 300px
    → nearest.is_using_phone = True
    → nearest.is_cheating = True (immediate)
    → nearest.cheating_cooldown = post_buffer_frames

CheatingEvaluator skips gaze check when is_using_phone=True

Alert Recording Collector [11]
  → state.is_cheating=T → START recording (max 3 concurrent)
  → JPEGFrame with phone context stored in recording_buffer
  → _save_alert_video_async(…, cheat_type="phone", cheat_ctx={phone_bbox, …})
      → _render_alert_frame() draws PHONE banner + red bbox
      → IF _composer: compose_video_alert(alert_type="phone", subject_point=phone_center)
      → ELSE: standalone VideoWriter fallback (JPEG sequence on codec failure — Fix E-4)

Parallel: Phone global alert (independent of student tracking)
  _phone_is_recording state machine:
    START: snapshot _global_frame_buffer pre-roll
    DURING: append JPEGFrame (phone_bboxes stored)
    POST countdown: _save_phone_alert_video_async()
      → compose_video_alert(alert_type="phone", subject_point=phone_center)
      OR standalone writer
```

---

## Step 4: Shared State Map

| State field | Owner | Written by | Read by | Lock? |
|---|---|---|---|---|
| `reg_state.face_mesh` | `StudentSpatialState` | FM worker thread (callback) | Main thread (evaluator, visualizer) | None (CPython atomic assign) |
| `reg_state.is_cheating` | `StudentSpatialState` | Main thread (evaluator + phone detection) | Alert collector (main thread), visualizer | None (single writer, main thread) |
| `reg_state.recording_buffer` | `StudentSpatialState` | Main thread (collector) | Alert writer thread (snapshot copy) | None (snapshot taken before hand-off) |
| `reg_state.is_using_phone` | `StudentSpatialState` | Main thread (phone detection, CheatingEvaluator.patched_update) | Main thread (evaluator, collector) | None (single writer) |
| `_global_frame_buffer` | `VideoPipeline` | Main thread | Alert writer thread (snapshot copy) | `_buffer_lock` (threading.Lock) |
| `_fm_cache` | `VideoPipeline` | FM worker threads | FM worker threads, main thread | `_fm_cache_lock` (threading.Lock) |
| `_registry._states` | `GlobalStudentRegistry` | Main thread (`update`) | All threads (read-only via `get`, `get_all`) | `_lock` (threading.Lock) |
| `_selected_ids` | `VideoPipeline` | Main thread | Main thread | None |
| `_track_aliases` | `VideoPipeline` | FM callback thread | Main thread | ✅ `_alias_lock` (threading.Lock) |
| `MicLayout.pins` | `MicLayout` | `add_pin()` (mouse handler) | `get_pins_for_camera()`, `nearest_mic_for_point()` | `_lock` (threading.Lock) |
| `EpisodeTracker._episodes` | `EpisodeTracker` | VAD/Whisper workers | Audio main loop | `_lock` (threading.Lock) |
| `AudioPipeline._stats` | `AudioPipeline` | All audio threads | `stats` property, health monitor | `_lock` (threading.Lock) |
| `AudioPipeline._pending_alerts` | `AudioPipeline` | Whisper worker | Audio main loop | `_lock` (threading.Lock) |
| `_keyword_detector._beam_size` | `KeywordDetector` | Health monitor thread (under `_monitor_lock`) | Whisper worker (snapshots under lock — Fix C-4) | `_monitor_lock` (snapshot pattern) |

---

## Step 5: Configuration Map

All settings are Pydantic `BaseSettings` (env vars or `.env` file). Values shown are **actual current defaults from `settings.py`** — not the `.env` file (which overrides them).

### Camera / Video
| Env var | Default (settings.py) | Effect |
|---|---|---|
| `CAMERA_SOURCE` | `"0"` | Webcam index, RTSP URL, or file path |
| `CAMERA_WIDTH` / `CAMERA_HEIGHT` | `1280 / 720` | Requested capture resolution |
| `CAMERA_FPS` | `30` | Target FPS |

### YOLO Detection
| Env var | Default (settings.py) | Effect |
|---|---|---|
| `YOLO_MODEL` | `models/yolo11m.pt` | Person detection model |
| `DETECTION_CONFIDENCE` | `0.15` | Person confidence threshold |
| `DETECTION_INTERVAL` | `1.0` | Seconds between YOLO runs |
| `DETECTION_IMGSZ` | `640` | YOLO inference resolution |
| `YOLO_PHONE_DETECTION` | `True` | Joint person+phone inference |
| `PHONE_CLASS_ID` | `67` | COCO class for phone |
| `PHONE_CONFIDENCE` | `0.30` | Phone detection threshold |
| `PHONE_MODEL` | `""` | Dedicated phone model (empty = share YOLO_MODEL) |
| `TOOLS_MODEL` | `models/best.pt` | Tools (paper/phone) detection model |
| `TOOLS_CONFIDENCE` | `0.45` | Tools detection threshold |
| `TOOLS_TARGET_LABELS` | `["document"]` | Filtered tool labels |

### Tracking
| Env var | Default (settings.py) | Effect |
|---|---|---|
| `TRACKING_MAX_DISTANCE` | `100` | BoT-SORT max distance |
| `TRACKING_MAX_AGE` | `30` | BoT-SORT track buffer frames |
| `REID_WEIGHTS_PATH` | `models/osnet_x0_25_msmt17.pt` | ReID model file |
| `REID_MATCH_THRESHOLD` | `0.80` | Cosine similarity for ReID |
| `REID_SIMILARITY_DEBUG` | `False` | Log per-frame similarity scores |

### Gaze / Cheating
| Env var | Default (settings.py) | Effect |
|---|---|---|
| `RISK_ANGLE_TOLERANCE` | `25.0` | Degrees; gaze cone half-angle |
| `SUSPICIOUS_DURATION_THRESHOLD` | `2.0` | Seconds looking at paper before alert |
| `SUSPICIOUS_MATCH_RATIO` | `0.7` | Frame ratio within window (reserved) |
| `NEIGHBOR_K` | `6` | k-nearest-neighbor count |

### Recording / Output
| Env var | Default (settings.py) | Effect |
|---|---|---|
| `ALERTS_DIR` | `alerts` | Directory for alert clips |
| `ARCHIVE_DIR` | `archive` | Directory for archive recording |
| `ARCHIVE_MODE` | `raw` | `raw` or `annotated` |
| `ALERT_MAX_HEIGHT` | `720` | Max height for alert clips |
| `VIDEO_QUALITY` | `75` | JPEG/codec quality (50=LOW/75=MED/90=HIGH) |
| `FACE_MESH_WORKERS` | `4` | Thread pool size for MediaPipe |
| `VIDEO_LOG_ENABLED` | `True` | Enable structured diagnostic log |
| `VIDEO_LOG_DIR` | `logs` | Log directory |
| `VIDEO_LOG_LEVEL` | `DEBUG` | Log level |
| `VIDEO_LOG_MAX_BYTES` | `100 MB` | Rotation size |

### Audio
| Env var | Default (settings.py) | Effect |
|---|---|---|
| `AUDIO_WHISPER_MODEL` | `tiny` | Whisper model size |
| `AUDIO_LANGUAGE` | `ar` | Language code for Whisper |
| `AUDIO_SAMPLE_RATE` | `16000` | Sample rate (Hz) — required by VAD/Whisper |
| `AUDIO_CHUNK_MS` | `500` | Analysis window size (ms) |
| `AUDIO_SILENCE_THRESHOLD` | `0.01` | RMS below which = silence |
| `AUDIO_VAD_THRESHOLD` | `0.5` | Silero VAD confidence threshold |
| `AUDIO_STRICT_MODE` | `True` | Any speech = alert (silent exam mode) |
| `AUDIO_VAD_ONLY` | `False` | Skip Whisper entirely, fire on VAD |
| `AUDIO_VAD_ALERT_COOLDOWN` | `3.0` | Seconds between VAD-only alerts per mic |
| `AUDIO_SPEECH_BUFFER_SEC` | `2.5` | Accumulated speech before Whisper |
| `AUDIO_EPISODE_MIN_SEC` | `3.0` | Min sustained duration to confirm episode |
| `AUDIO_EPISODE_GRACE_SEC` | `5.0` | Idle gap before closing episode |
| `AUDIO_SESSION_RECORDING` | `True` | Record full session to WAV |
| `AUDIO_SESSIONS_DIR` | `sessions` | Session WAV directory |
| `AUDIO_ADAPTIVE_VAD` | `True` | Auto-adapt VAD threshold to noise floor |
| `AUDIO_NOISE_REDUCTION` | `True` | Spectral noise subtraction |
| `AUDIO_ADAPTIVE_GAIN` | `True` | RMS normalisation per chunk |
| `AUDIO_TRANSIENT_SUPPRESSION` | `True` | Filter pen clicks / paper shuffling |
| `AUDIO_HPF_CUTOFF` | `100` | High-pass filter frequency (Hz) |
| `AUDIO_RECALIBRATION_INTERVAL_SEC` | `300.0` | Seconds between baseline recalibrations |
| `AUDIO_LOCAL_RATIO_MULTIPLIER` | `2.0` | Threshold multiplier for LOCAL classification |
| `AUDIO_MIC_NAMES` | `""` | Ignored — mic labels come from CLI args |

> **Note**: `AUDIO_MIC_NAMES` is defined in settings but **ignored at runtime**. The `AudioPipeline` builds `_mic_registry` directly from the `mic_ids` list passed as CLI arguments (`--audio mic0=front.wav mic1=back.wav`).

---

## Step 6: Verification — Confirmed by Code

1. **Face mesh uses IMAGE mode — inline in `pipeline.py`**, not via `FaceMeshExtractor`.
   - `_fm_thread_infer()` creates `FaceLandmarker` in `IMAGE` mode per thread via `threading.local()`.
   - `FaceMeshExtractor` (VIDEO mode) and `face_mesh_worker.py` (MP process) are **dead code** — never imported or called by the pipeline.

2. **`ConstantVelocityExtrapolator` is live but secondary.**
   - History and velocity are always updated via `extrapolator.update()` after each tracker call.
   - `extrapolator.extrapolate()` is only used inside `_tracker.get_predicted_bbox()` as a second-level fallback if BoT-SORT has no internal prediction.
   - `extrapolator.prune(active_track_ids)` is called every frame to prevent memory growth.

3. **`AVAlertComposer` no longer uses memory buffers.**
   - The old `video_buffers` / `audio_buffers` deque approach is fully replaced.
   - `compose_video_alert()` seeks directly in the video archive file using `cv2.CAP_PROP_POS_MSEC`.
   - `compose_audio_alert()` receives a pre-cut WAV file path from `AudioEvidenceRecorder`.
   - `stop()` and `shutdown()` are compatibility stubs (no executor, no cleanup needed).

4. **`MicLayout` does NOT load/save from JSON.**
   - The current `mic_layout.py` has no `load()` or `save()` methods.
   - Pins are added exclusively at runtime via `add_pin()` (triggered by interactive mouse placement in the video window with 'I' key).
   - `mic_layout.json` file is **not read at startup** in the current code.

5. **Dynamic mic registry from CLI.**
   - `AudioPipeline._mic_registry` is built as `{i: name for i, name in enumerate(mic_ids)}`.
   - `mic_ids` comes from `run.py`'s `--audio mic0=front.wav mic1=back.wav` argument parsing.
   - `AUDIO_MIC_NAMES` in `.env` is ignored for this purpose.

6. **`SimClock` is a `time.monotonic()` wrapper, not a simulation clock.**
   - It does NOT advance faster or slower than wall time.
   - It provides a shared zero-reference so all components measure the same elapsed time from startup.

7. **`CheatingEvaluator` uses `frame_data.timestamp` (passed as `current_time`)** — not `clock.now()` or `time.time()` directly. The timestamp originates from `SimClock.now()` in `CameraStream`, so it is consistent with video archive offsets.

8. **Alert recording cap is 3 concurrent recordings.**
   - `active_recordings = sum(1 for s in self._registry.get_all() if s.is_alert_recording)`
   - 4th+ simultaneous cheater is skipped with a single warning log (suppressed to once per track).

---

## Step 7: Gap Analysis

### Architecture gaps (current state)

| ID | Gap | Severity | Status |
|---|---|---|---|
| G-1 | `FaceMeshExtractor` + `face_mesh_worker.py` are dead code | LOW | Known — never invoked. Safe to remove. |
| G-2 | `_track_aliases` concurrent write/read | MEDIUM | **FIXED** — `_alias_lock` (threading.Lock) |
| G-3 | Double camera-disconnect log | LOW | **FIXED** — duplicate removed from `camera.py` |
| G-4 | `ConstantVelocityExtrapolator` partially superseded | LOW | Known — extrapolated bbox used as second-level fallback only |
| G-5 | Unbounded alert-mux threads | MEDIUM | **FIXED** — AVAlertComposer now uses archive-based approach; no thread pool needed |
| G-6 | `MicLayout` no-op on invalid position | LOW | **FIXED** — entry skipped with `logger.warning` |
| G-7 | ffmpeg not re-checked after startup | LOW | If ffmpeg removed mid-session, `subprocess.run` raises inside alert writer |
| G-8 | `_pending_fm_futures` growth cap | LOW | Capped at `4 × face_workers` via `MAX_PENDING_FM` check |
| G-9 | Archive writer `deque(maxlen=60)` frame drop | LOW | Drop logged; no user-facing indicator |
| G-10 | `VideoLogger` not closed on SIGKILL | LOW | Last few log lines may be lost; not fixable at Python level |
| G-11 | `MicLayout` has no persistence across runs | INFO | Pins are lost on restart; no JSON load in current code |

---

## Summary

The system is a **multi-threaded, multi-pipeline architecture** where:

- **Video pipeline** runs on one main thread per camera, with async sub-threads for YOLO detection, face mesh inference (ThreadPoolExecutor), alert video writing, and archive writing.
- **Audio pipeline** runs on a dedicated thread with VAD worker, Whisper worker, health monitor, and session recorder threads.
- **Alert composition** is fully archive-based: both video and audio alerts extract their media directly from archive files using timestamp offsets (`start_sec / end_sec = frame_index / fps`), eliminating all circular buffer synchronisation issues.
- **SimClock** provides a shared elapsed-time reference from startup for both pipelines, ensuring consistent timestamps across video frames and audio chunks.
- The **critical video path** per frame is: read → downscale (optional) → JPEG-encode → tracking update → neighbor compute → cheating evaluate → alert collect → visualize → archive enqueue. Face mesh is genuinely async and off the critical path.
- **Memory** is kept bounded via JPEG compression (~30× reduction), deque maxlen limits, and alert recording caps (max 3 concurrent, each up to 300 frames post-event).
- **All major concurrency, error handling, and timing bugs** identified in previous analysis rounds are resolved in the current codebase.
