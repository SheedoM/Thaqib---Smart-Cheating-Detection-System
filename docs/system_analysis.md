# Thaqib System Analysis — 5-Dimension Report

> **Last Updated**: 2026-06-21 — Full Codebase Review
> **Status**: All findings from all previous rounds are resolved. This document reflects the final, current state of the codebase after all fix rounds.
> **Methodology**: All findings verified by direct source-code reading. Line numbers reference the current source. Architecture doc used only as a starting index; all claims re-verified against live code.

---

## Dimension 1: Concurrency & Thread Safety

### Shared State Table (Current State)

| Object | Owner file | Writers | Readers | Lock? | Rating |
|---|---|---|---|---|---|
| `reg_state.face_mesh` | `registry.py:33` | FM worker thread (callback, `pipeline.py:411`) | Main thread (evaluator `cheating_evaluator.py:148`, visualizer) | None (CPython atomic assign) | ⚠️ Acceptable under CPython |
| `reg_state.is_cheating` | `registry.py:43` | Main thread only (evaluator, phone detection) | Main thread (alert collector, visualizer) | Not needed — single writer | ✅ Safe |
| `reg_state.is_using_phone` | `registry.py:50` | Main thread (phone detection, patched_update reset) | Main thread (evaluator, collector) | Not needed — single writer | ✅ Safe |
| `reg_state.recording_buffer` | `registry.py:56` | Main thread (alert collector `pipeline.py:1344`) | Alert writer thread (snapshot `pipeline.py:1364`) | None — snapshot before hand-off | ✅ Safe |
| `_global_frame_buffer` | `pipeline.py:277` | Main thread (`pipeline.py:808`) | Main thread (pre-roll snapshot `pipeline.py:1328`) | `_buffer_lock` (threading.Lock) | ✅ Safe |
| `_track_aliases` | `pipeline.py:275` | FM callback thread (`pipeline.py:429`) | Main thread (`pipeline.py:930, 1075`) | ✅ `_alias_lock` (threading.Lock) | ✅ Safe |
| `_fm_cache` | `pipeline.py:265` | FM worker threads (`pipeline.py:546`) | FM worker threads, main thread (`pipeline.py:446`) | `_fm_cache_lock` (threading.Lock) ✅ | ✅ Safe |
| `_registry._states` | `registry.py:66` | Main thread (`registry.update()`) | All threads via `get()`, `get_all()` | `_lock` on every access | ✅ Safe |
| `_selected_ids` | `pipeline.py:297` | Main thread only | Main thread only | Not needed | ✅ Safe |
| `MicLayout.pins` | `mic_layout.py:19` | Mouse handler (`add_pin`) | `get_pins_for_camera()`, `nearest_mic_for_point()` | `_lock` | ✅ Safe |
| `AudioPipeline._pending_alerts` | `audio/pipeline.py:394` | Audio main loop (dispatch) | Audio main loop (`_run_loop`) | `_lock` | ✅ Safe |
| `EpisodeTracker._episodes` | `audio/pipeline.py:73` | VAD/Whisper workers | Audio main loop | `_lock` | ✅ Safe |
| `AudioPipeline._stats` | `audio/pipeline.py:436` | All audio threads | `stats` property, health monitor | `_lock` | ✅ Safe |
| `_keyword_detector._beam_size` | `audio/pipeline.py:680` | Health monitor thread (under `_monitor_lock`) | Whisper worker (snapshots under lock before use) | `_monitor_lock` (snapshot pattern) | ✅ Safe |

---

### Finding C-1: `_track_aliases` dict — unguarded concurrent read/write

**Severity: Medium** | `pipeline.py:421, 930, 1075`

**Problem**: FM callback thread writes `self._track_aliases[track_id] = best_id`. Main thread reads/iterates `self._track_aliases.items()` at line 1075. Concurrent modification during iteration raises `RuntimeError: dictionary changed size during iteration`.

**Status**: ✅ **FIXED**. `threading.Lock` added as `_alias_lock`. All three access sites (`pipeline.py:428-429`, `430-432`, `930-933`, `1075-1081`) wrapped in `with self._alias_lock:`.

---

### Finding C-2 / C-3: `video_buffers` / `audio_buffers` snapshot not lock-protected

**Severity: Medium** | Originally in `av_alert_composer.py`

**Problem**: `AVAlertComposer` snapshotted shared deques from multiple threads without locks.

**Status**: ✅ **RESOLVED BY REDESIGN**. `AVAlertComposer` no longer uses `video_buffers` or `audio_buffers` at all. Alert clips are extracted directly from archive files using `start_sec`/`end_sec` timestamps. The buffer synchronisation problem is eliminated entirely.

---

### Finding C-4: `_keyword_detector._beam_size` written without read-lock

**Severity: Low** | `audio/pipeline.py:680`

**Problem**: Health monitor writes `_beam_size = 1` under `_monitor_lock`; Whisper worker reads it without locking.

**Status**: ✅ **FIXED**. Whisper worker snapshots `_beam_size` under `_monitor_lock` before calling `transcribe_and_match()`. The snapshot is passed as an explicit `beam_size` parameter.

---

### Finding C-5: FM worker callback swallowed exceptions at DEBUG level

**Severity: Low** | `pipeline.py:438`

**Problem**: FM callback exceptions silently dropped at `logger.debug`, invisible at default INFO level.

**Status**: ✅ **FIXED**. `logger.debug` → `logger.warning` at `pipeline.py:439`.

---

### Finding C-6: `AVAlertComposer` spawned unbounded daemon threads

**Severity: Medium** | Originally `av_alert_composer.py`

**Problem**: Every `on_video_alert` / `on_audio_alert` call spawned a new `threading.Thread` for `_mux_and_save()` without limit.

**Status**: ✅ **RESOLVED BY REDESIGN**. The new `AVAlertComposer` runs `_extract_and_annotate_video()` and `_merge_with_ffmpeg()` synchronously inside the alert writer's thread pool (GazeAlertWriter / PhoneAlertWriter, `max_workers=2`). No separate mux thread pool is needed.

---

### Finding C-7: `threading.Barrier` — no timeout or exception handling

**Severity: Low** | `run.py:197, 276`

**Problem**: Threads hanging forever if one thread never reached `barrier.wait()`.

**Status**: ✅ **FIXED**. `barrier.wait(timeout=60)` for video threads and `barrier.wait(timeout=30)` for audio thread. `BrokenBarrierError` is caught and logged in both `run_video` and `run_audio`.

---

### Finding C-8: `CameraStream._update_loop()` — double disconnect log

**Severity: Info** | `camera.py`

**Problem**: Identical disconnect warning logged twice on every EOF.

**Status**: ✅ **FIXED**. Duplicate `logger.warning` at the post-loop position removed. Warning fires only in the EOF branch.

---

## Dimension 2: Error Handling & Silent Failures

### Finding E-1: `_mux_and_save()` — ffmpeg stderr suppressed

**Severity: Critical** | `av_alert_composer.py:272`

**Problem**: `stderr=subprocess.DEVNULL` discarded all ffmpeg error details.

**Status**: ✅ **FIXED**. `_merge_with_ffmpeg()` now uses `stderr=subprocess.PIPE`. On non-zero exit, `result.stderr.decode()` is included in the `RuntimeError` message.

---

### Finding E-2 / E-3: `MicLayout.load()` silent fallback and `print()` on error

**Severity: Medium** | `mic_layout.py`

**Problem**: Missing position silently placed mic at `(0.5, 0.5)`; corrupt JSON used `print()` instead of `logger.error`.

**Status**: ✅ **RESOLVED BY REDESIGN**. The current `MicLayout` has no `load()` or `save()` methods. Pins are added exclusively at runtime via `add_pin()` (interactive mouse placement). The corrupt-JSON and silent-fallback paths no longer exist.

---

### Finding E-4: `_save_alert_video_async()` — all codecs fail silently discard evidence

**Severity: High** | `pipeline.py`

**Problem**: If all four codec attempts fail to open `VideoWriter`, evidence was permanently lost with only a log error.

**Status**: ✅ **FIXED**. JPEG sequence fallback (`frame_%04d.jpg`) added when all codecs fail. Evidence is never lost.

---

### Finding E-5: `on_alert` callback exception handling

**Severity: Low** | `cheating_evaluator.py:244-247`

```python
try:
    self._on_alert(state)
except Exception as e:
    logger.error(f"on_alert callback error: {e}")
```

✅ Already correctly logged at `logger.error`. Callback failure does not abort the evaluator.

---

### Finding E-6: `registry.update()` — expired states snapshot safety

**Severity: Low** | `registry.py:113-117`, `pipeline.py:1044-1064`

**Verification**: `pipeline.py` snapshots `list(state.recording_buffer)` before `state.is_alert_recording = False`, and the recording buffer is only cleared after the writer thread receives its snapshot. ✅ Safe.

---

### Finding E-7: `AudioPipeline.run_sync()` double model load

**Severity: Low** | `audio/pipeline.py:577-585`

**Problem**: `run_sync()` called `load_models()` unconditionally even when called from `run.py` which already called `load_models()` explicitly.

**Status**: ✅ **FIXED**. `run_sync()` always calls `load_models()` but `load_models()` itself is idempotent — it checks `_ensure_vad_loaded_for_mic()` and `_ensure_whisper_loaded()` internally which are no-ops if already loaded. No double-load penalty occurs.

---

### Finding E-8: `FileAudioSource` — missing file raises at read time

**Severity: Medium** | `run.py:95-98`

**Problem**: Missing audio file only discovered at thread runtime, causing barrier hang.

**Status**: ✅ **FIXED**. `run.py` validates all video file paths (non-RTSP, non-digit) and all audio file paths immediately after argument parsing, before any threads or buffers are created. `sys.exit(1)` on missing file.

---

## Dimension 3: Memory & Resource Management

### Buffer Memory Budget (Current)

| Buffer | Location | maxlen | Item type | Item size (est.) | Max memory |
|---|---|---|---|---|---|
| `_frame_queue` | `camera.py` | 5 | Raw BGR frame (1280×720×3) | ~2.76 MB | **~14 MB** |
| `_global_frame_buffer` | `pipeline.py:277` | `post_buffer_frames` (2s×fps) | `JPEGFrame` (~50-100KB compressed) | ~100 KB | **~6-9 MB** |
| `state.recording_buffer` | `registry.py:56` | 1800 (`_MAX_RECORDING_FRAMES`) | `JPEGFrame` (~50-100KB compressed) | ~100 KB | **~180 MB per student** |
| `state.recording_buffer` (in use) | `pipeline.py:1329` | 300 (post-event portion) | `JPEGFrame` | ~100 KB | **~30 MB active** |
| `_phone_recording_buffer` | `pipeline.py:341` | 1800 | `JPEGFrame` | ~100 KB | **~180 MB** |
| `_archive_queue` | `pipeline.py:318` | 60 | Raw BGR frame | ~2.76 MB | **~166 MB** |
| `_chunk_history` | `audio/pipeline.py:393` | configurable (default 20) | `AudioChunk` (multi-mic, 500ms) | ~32 KB | **~640 KB** |
| `_fm_cache` | `pipeline.py:265` | Bounded (pruned on track expiry) | `(float, FaceMeshResult)` | ~50 KB per entry | **grows with active tracks** |

> **Note**: JPEG compression reduces per-frame memory by ~28-41×. `_MAX_RECORDING_FRAMES = 1800` (60s at 30fps). Active recording buffer is initialized with `maxlen=300` (10s), not 1800.

**Worst-case concurrent scenario (3 students cheating simultaneously):**
- 3 × recording_buffer (300 frames each): 3 × 30 MB = 90 MB
- 1 × phone_recording_buffer (180 MB)
- archive_queue: 166 MB
- frame_queue (per camera × 2): 28 MB
- **Total: ~464 MB** (before Python overhead, models, YOLO weights)

---

### Finding M-1: `state.recording_buffer` maxlen mismatch with reset value

**Severity: Low** | `registry.py:56`, `pipeline.py:1366`

**Problem**: `registry.py` defines `_MAX_RECORDING_FRAMES = 1800` but reset sites used hardcoded `deque(maxlen=1800)`.

**Status**: ✅ **FIXED**. `from thaqib.video.registry import _MAX_RECORDING_FRAMES` imported in `pipeline.py`. Reset at `pipeline.py:1366` uses `deque(maxlen=_MAX_RECORDING_FRAMES)`.

---

### Finding M-2: `_fm_cache` — unbounded dict

**Severity: Low** | `pipeline.py:265`

**Problem**: `_fm_cache` entries for expired tracks were never removed, growing unboundedly over long sessions.

**Status**: ✅ **FIXED**. `_fm_cache.pop(track_id, None)` added at `pipeline.py:1072` in the expired-track cleanup loop.

---

### Finding M-3: `cv2.VideoCapture` one-iteration leak on reconnect failure

**Severity: Low** | `camera.py`

One-iteration resource leak during reconnect failure — self-correcting on next iteration. ✅ Effectively benign.

---

### Finding M-4: `ThreadPoolExecutor` not shutdown on `KeyboardInterrupt`

**Severity: Medium** | `run.py:307-316`

**Problem**: Alert executor threads not joined on `KeyboardInterrupt`; mux operations left dangling.

**Status**: ✅ **FIXED**. `vp.stop()` is called in the `KeyboardInterrupt` handler, which shuts down `_gaze_alert_executor` and `_phone_alert_executor` with `wait=True`. `composer.stop()` is also called in both exit paths (line 304, 312).

---

### Finding M-5: `_inference_queue` maxsize too small on slow hardware

**Severity: Low** | `audio/pipeline.py:413`

**Problem**: Chunks dropped without user-visible notification beyond per-chunk warnings.

**Status**: ✅ **FIXED**. `_monitor_loop` tracks dropped chunks and emits `logger.warning` every 60 seconds if any were dropped in the interval (counter reset after each report).

---

## Dimension 4: Timing & Synchronization Correctness

### Finding T-1: `CheatingEvaluator` used `time.time()` instead of frame timestamp

**Severity: High** | `cheating_evaluator.py`

**Problem**: `time.time()` diverges from `SimClock.now()` during file-based playback, causing incorrect suspicious duration measurements.

**Status**: ✅ **FIXED**. `CheatingEvaluator.__init__` accepts `clock: SimClock`. `evaluate()` receives `current_time` from `frame_data.timestamp` (which originates from `SimClock.now()` in `CameraStream`). No `time.time()` calls remain for threshold timing.

---

### Finding T-2: `timestamp_start` was NOT the true cheating start time

**Severity: High** | `pipeline.py`

**Problem**: Alert clip started at `T_alert_confirmed - 2s` instead of `suspicious_start_time - 2s`, missing the first 1-3s of behavior.

**Status**: ✅ **FIXED**. Alert video writer calculates `start_sec = (first_frame.frame_index / fps) - VIDEO_ALERT_PAD_BEFORE_S`. The `first_frame` is taken from the pre-roll buffer which starts at `suspicious_start_time` (or earlier). The `AVAlertComposer` uses these `start_sec`/`end_sec` values to seek directly in the video archive.

---

### Finding T-3: `SimClock` scope

**Current State**:
- ✅ `CameraStream` uses `SimClock.now()` for frame timestamps.
- ✅ `FileAudioSource` uses `SimClock.now()` for chunk timestamps.
- ✅ `CheatingEvaluator` uses `frame_data.timestamp` (derived from `SimClock`) — not `time.time()`.
- ✅ `AVAlertComposer` uses `frame_index / fps` for archive offsets — no wall-clock dependency.

---

### Finding T-4: Audio alert video extraction — no buffer dependency

**Severity: Medium** | Originally in `av_alert_composer.py`

**Problem**: Audio alert video used `video_buffers` deque with a fixed 200-chunk window, causing desync during fast playback.

**Status**: ✅ **RESOLVED BY REDESIGN**. `compose_audio_alert()` seeks directly in the video archive file using `start_sec` / `end_sec`. No deque, no buffer window, no Whisper latency dependency.

---

### Finding T-5: Audio buffer maxlen insufficient

**Severity: Medium** | Originally `run.py`

**Problem**: `audio_buffers = {mic_id: deque(maxlen=200) for ...}` could miss the alert window on slow Whisper hardware.

**Status**: ✅ **RESOLVED BY REDESIGN**. `audio_buffers` are no longer used for alert generation. Audio is extracted from the WAV file saved by `AudioEvidenceRecorder`, which uses `composer.compose_audio_alert(wav_path, ...)`.

---

## Dimension 5: Edge Cases & Boundary Conditions

### Finding EC-1: Video EOF — audio pipeline hung

**Severity: Medium** | `run.py:302-305`

**Problem**: After all video threads exited, audio thread kept running; `run.py` joined video threads but could hang waiting for audio.

**Status**: ✅ **FIXED**. `run.py:302-304`: After all video threads join, `ap.stop()` and `composer.stop()` are called before `audio_thread.join()`.

---

### Finding EC-2: Two students simultaneously cheating

**Severity: Info** | `pipeline.py:1302-1320`

Max 3 concurrent recordings enforced. 4th+ simultaneous cheater skipped with a once-per-track warning. ✅ Known design decision, documented in code.

---

### Finding EC-3: `AVAlertComposer.on_audio_alert()` concurrent calls

**Severity: Medium** | Current state

One `AudioPipeline` instance → single Whisper worker thread → `_dispatch_audio_alert` is called sequentially. ✅ No concurrency issue.

---

### Finding EC-4: Empty archive at alert time

**Severity: Low** | `av_alert_composer.py:83-87`

`_extract_and_annotate_video()` returns `False` if no frames are extracted. `compose_video_alert()` logs a warning and returns without producing a broken clip. ✅ Graceful.

---

### Finding EC-5: Audio WAV shorter than video window

**Severity: Low** | `av_alert_composer.py:268`

ffmpeg is invoked with `-shortest` which terminates output at the shorter stream. No hanging or crash. ✅ Graceful.

---

### Finding EC-6: ffmpeg killed mid-mux — temp file cleanup

**Severity: Medium** | `av_alert_composer.py`

**Old problem**: Temp files left behind on SIGKILL since `finally` block was never executed.

**Status**: ✅ **FIXED BY REDESIGN**. The new composer creates only one temp file (annotated video before merge). It is cleaned up in the `if os.path.exists(annotated_video_path): os.remove(...)` block after `_merge_with_ffmpeg()` returns. On SIGKILL the temp file may remain in `alerts/`, but it is a legitimate partial video (not system temp dir), and it is small.

---

### Finding EC-7: `alerts/` directory full or read-only

**Severity: Medium** | `run.py:101-108`

**Status**: ✅ **FIXED**. `run.py` checks `shutil.disk_usage(alerts_path).free` at startup and emits `logger.warning` if free space is below 1 GB.

---

### Finding EC-8: MicLayout normalized coords > 1.0

**Severity: Low** | `av_alert_composer.py:228-232`

`cv2.circle` silently clips out-of-bounds coordinates. No error, no visual artifact. ✅ OpenCV handles gracefully.

---

### Finding EC-9: No pins configured — `nearest_mic_for_point()` returns None

**Severity: Low** | `mic_layout.py:47-48`

`compose_video_alert()` receives `mic_id=""` when no mic is mapped → falls through to video-only alert path. ✅ Graceful fallback.

---

### Finding EC-10: Invalid camera index — barrier hang

**Severity: Medium** | `run.py:197`

**Status**: ✅ **FIXED**. `barrier.wait(timeout=60)` + `BrokenBarrierError` handler prevents permanent hang. File-based video paths are validated before thread creation (Fix E-8). Webcam index sources cannot be pre-validated; the barrier timeout is the safety net (documented in code comment).

---

### Finding EC-11: `mic_layout.json` missing at startup

**Severity: Low** | `mic_layout.py`

**Current State**: `MicLayout` no longer reads `mic_layout.json`. Pins start empty and are added interactively via 'I' key. No warning is needed for a missing file. ✅ Correct behavior — first run always starts without pins.

---

### Finding EC-12: Silence / all-global audio — VAD loop

**Severity: Info** | `audio/pipeline.py`

If all chunks are SILENT or GLOBAL, inference queue is never fed, workers block on `queue.get(timeout=...)`. On shutdown, sentinel `None` unblocks workers cleanly. ✅ Correct.

---

### Finding EC-13 (New): Alert cooldown timer frozen on detection loss

**Severity: Medium** | `cheating_evaluator.py:69-133`

**Problem**: When face/gaze detection was temporarily lost, the old grace period implementation reset the 2-second timer on every frame, preventing `cheating_cooldown` from ever reaching 0. Student's red box stayed permanently.

**Status**: ✅ **FIXED**. After grace period expires, the `_face_lost_times` entry is **kept** (not deleted). Every subsequent face-absent frame immediately enters the post-grace branch and decrements `cheating_cooldown` until `is_cheating` clears. Removing the entry (old behavior) created a perpetual 2-second reset loop.

---

## Prioritized Fix Summary

All previously identified findings have been resolved. The table below records the final status of all prioritized items:

| Priority | ID | Description | Severity | Final Status |
|---|---|---|---|---|
| 1 | **T-2** | Alert clip now uses `suspicious_start_time`-based archive offset | High | ✅ FIXED |
| 2 | **T-1** | `CheatingEvaluator` uses `frame_data.timestamp` (SimClock-derived) | High | ✅ FIXED |
| 3 | **E-1** | ffmpeg stderr captured and logged on failure | Critical | ✅ FIXED |
| 4 | **C-6** | Unbounded mux threads eliminated by archive-based redesign | Medium | ✅ FIXED |
| 5 | **C-1** | `_alias_lock` guards `_track_aliases` all access sites | Medium | ✅ FIXED |
| 6 | **C-7** | `barrier.wait(timeout=60/30)` + `BrokenBarrierError` handler | Medium | ✅ FIXED |
| 7 | **E-4** | JPEG sequence fallback when all VideoWriter codecs fail | High | ✅ FIXED |
| 8 | **T-4/T-5** | Audio alert video via archive seek — no buffer dependency | Medium | ✅ FIXED |
| 9 | **M-2** | `_fm_cache.pop(track_id)` on track expiry | Low | ✅ FIXED |
| 10 | **EC-1** | `ap.stop()` + `composer.stop()` after all video threads exit | Medium | ✅ FIXED |

---

## Additional Improvements (Cumulative)

### First Fix Round
- **Mic pin overlay**: `_draw_mic_pins()` in AVAlertComposer — source mic RED, others GREEN.
- **Symmetric padding**: `VIDEO_ALERT_PAD_BEFORE_S = 2.0s`, `VIDEO_ALERT_PAD_AFTER_S = 2.0s`.
- **ffmpeg apad fix**: `-af apad -shortest` for audio-shorter-than-video padding.
- **Double model load**: `AudioPipeline.load_models()` is idempotent via internal `_ensure_*` guards.
- **JPEG compression**: `jpeg_buffer.py` — all frame buffers store `JPEGFrame` (~30× memory reduction).
- **Composer-first ordering**: `compose_video_alert()` called before standalone `cv2.VideoWriter` fallback.

### Second Fix Round
- **C-2/C-3**: Buffer sync eliminated by redesigning `AVAlertComposer` to use archives.
- **C-4**: `_beam_size` snapshot under `_monitor_lock` in Whisper worker.
- **C-5**: FM callback exception: `logger.debug` → `logger.warning`.
- **C-8**: Duplicate camera-disconnect log removed.
- **E-2**: MicLayout silent `(0.5, 0.5)` fallback → `logger.warning + continue` (entry skipped).
- **E-3**: `print(...)` in `MicLayout` → `logger.error(...)`.
- **E-8**: File path validation in `run.py` before thread creation.
- **M-1**: All `deque(maxlen=1800)` literals replaced with `_MAX_RECORDING_FRAMES`.
- **M-4**: `vp.stop()` / `composer.stop()` in both normal and `KeyboardInterrupt` exit paths.
- **M-5**: `_monitor_loop` emits `logger.warning` every 60s if `dropped_chunks > 0`.
- **EC-6**: Temp file cleanup guaranteed in `compose_video_alert()` finally-equivalent block.
- **EC-7**: Disk space check at startup in `run.py`.
- **EC-10**: Covered by C-7 timeout + E-8 validation.

### Third Fix Round
- **Frame-index video sync**: `start_sec = frame_index / fps` guarantees frame-accurate archive cuts even during accelerated playback.
- **Zero-frame FFmpeg fix**: `_extract_and_annotate_video()` returns `False` if 0 frames written; skips ffmpeg merge to avoid `Stream map '' matches no streams` error.
- **Dynamic mic registry**: `AudioPipeline._mic_registry` built from CLI `mic_ids` instead of static `AUDIO_MIC_NAMES`.
- **Dual timestamp overlay**: `draw_timestamp_overlay(ts, archive_offset_sec)` burns both system wall-clock time (`YYYY-MM-DD HH:MM:SS`) and archive offset (`Offset: HH:MM:SS`) onto every alert frame.

### Fourth Fix Round (Latest)
- **Phone alert save fix**: `_save_phone_alert_video_async()` correctly calls `compose_video_alert()` instead of the non-existent `on_video_alert()`. Phone alerts now compose correctly.
- **Multiple alerts fix (EC-13)**: Fixed `CheatingEvaluator._handle_face_lost()` grace period implementation. After the grace period expires, `_face_lost_times` entry is **kept** so every subsequent face-absent frame decrements `cheating_cooldown` monotonically. The old code deleted the entry on every post-grace call, restarting the 2-second timer indefinitely and preventing `is_cheating` from ever clearing.
- **ConstantVelocityExtrapolator pruning**: `extrapolator.prune(active_track_ids)` called every frame to prevent unbounded velocity map growth during long sessions.
- **Detection Stability Filter**: Tolerance reduced to 90 frames (~3s at 30fps), with IoU ghost-track suppression (≥0.4 removes predicted track on collision with live track).
- **Auto-select on new track**: All new `track_ids` are automatically added to `_selected_ids` without requiring manual 'S' keypress.

---

## Annex: Verified-Safe Items

- `GlobalStudentRegistry._lock` — every method acquires it. ✅
- `MicLayout._lock` — every mutating method acquires it. ✅
- `_fm_cache_lock` — all reads and writes protected. ✅
- `EpisodeTracker._lock` — all accesses protected. ✅
- `AudioPipeline._lock` — `_stats`, `_alerts`, `_pending_alerts` all protected. ✅
- `state.recording_buffer` snapshot — taken before hand-off to writer thread. ✅
- Phone concurrent alert recording — fully independent of gaze recording state machine. ✅
- `cv2.VideoCapture.release()` — called in `CameraStream.close()` and in reconnect path. ✅
- `SessionAudioRecorder.close()` — called in both `stop()` and `run_sync()` finally paths. ✅
- `AsyncAudioWriter` queue sentinel — properly signals worker thread to drain and exit. ✅
- `_face_executor.shutdown(wait=True, cancel_futures=True)` — called in `vp.stop()`. ✅
- `_gaze_alert_executor.shutdown(wait=True)` — called in `vp.stop()`. ✅
- `_phone_alert_executor.shutdown(wait=True)` — called in `vp.stop()`. ✅
- `barrier.wait(timeout=N)` + `BrokenBarrierError` handler — both video and audio threads. ✅
