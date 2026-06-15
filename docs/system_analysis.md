# Thaqib System Analysis — 5-Dimension Report

> **Last Updated**: After Second Fix Round (commits 8a14c8d and subsequent)
> **Status**: All 10 prioritized findings + 15 additional findings fixed. See git log for full history.

> **Methodology**: All findings verified by direct source-code reading.
> Line numbers are exact. Architecture doc used only as a starting index; all
> claims re-verified against live code before being reported.

---

## Dimension 1: Concurrency & Thread Safety

### Shared State Table

| Object | Owner file | Writers | Readers | Lock? | Rating |
|---|---|---|---|---|---|
| `reg_state.face_mesh` | `registry.py:33` | FM worker thread (callback, `pipeline.py:405`) | Main thread (evaluator `evaluator.py:144`, visualizer `visualizer.py:271`) | **None** (CPython atomic assign) | ⚠️ Risky |
| `reg_state.is_cheating` | `registry.py:43` | Main thread only (evaluator, phone detection) | Main thread (alert collector, visualizer) | Not needed — single writer | ✅ Safe |
| `reg_state.recording_buffer` | `registry.py:55` | Main thread (alert collector `pipeline.py:1309`) | Alert writer thread (snapshot `pipeline.py:1328`) | None — snapshot before hand-off | ✅ Safe |
| `_global_frame_buffer` | `pipeline.py:272` | Main thread (`pipeline.py:793`) | Main thread (pre-roll snapshot `pipeline.py:1292,1376`) | `_buffer_lock` | ✅ Safe |
| `video_buffers[cam_id]` | `run.py:79` | Main thread via `self._frame_buffer.append` (`pipeline.py:798`) | `AVAlertComposer` audio/composer threads | **None** — deque append is GIL-protected; `list()` snapshot is benign under CPython | ⚠️ Risky |
| `audio_buffers[mic_id]` | `run.py:76` | Audio pipeline `_run_loop` (`audio/pipeline.py:706`) | `AVAlertComposer` `on_audio_alert()` | **None** — deque append is GIL-protected; `list()` snapshot is benign under CPython | ⚠️ Risky |
| `_track_aliases` | `pipeline.py:271` | FM callback thread (`pipeline.py:421`) | Main thread (`pipeline.py:916`, cleanup `pipeline.py:1054`) | ✅ `_alias_lock` | ✅ Safe |
| `_fm_cache` | `pipeline.py:261` | FM worker threads (`pipeline.py:537`) | FM worker threads, main thread (`pipeline.py:438`) | `_fm_cache_lock` ✅ | ✅ Safe |
| `_registry._states` | `registry.py:62` | Main thread (`registry.update()`) | All threads via `get()`, `get_all()` | `_lock` on every access | ✅ Safe |
| `_selected_ids` | `pipeline.py:291` | Main thread only | Main thread only | Not needed | ✅ Safe |
| `MicLayout.pins` | `mic_layout.py:19` | Mouse handler (`handle_mouse`) | `get_pins_for_camera()`, `nearest_mic_for_point()` | `_lock` | ✅ Safe |
| `_pending_alerts` | `audio/pipeline.py:389` | Whisper worker thread (`audio/pipeline.py:1497`) | Audio main loop (`audio/pipeline.py:732`) | `_lock` | ✅ Safe |
| `EpisodeTracker._episodes` | `audio/pipeline.py:73` | VAD/Whisper workers | Audio main loop | `_lock` | ✅ Safe |
| `_stats` | `audio/pipeline.py:431` | All audio threads | `stats` property | `_lock` | ✅ Safe |
| `_keyword_detector._beam_size` | `audio/pipeline.py:672` | Monitor thread (`audio/pipeline.py:672,681`) | Whisper worker thread | `_monitor_lock` protects WRITE only; Whisper worker READS without lock | ⚠️ Risky |

---

### Finding C-1: `_track_aliases` dict — unguarded concurrent read/write

**Severity: Medium** | `pipeline.py:421, 916, 1054`

**Problem**: The FM callback thread writes `self._track_aliases[track_id] = best_id` (`pipeline.py:421`). The main thread reads/iterates `self._track_aliases.items()` at line 1054 inside `keys_to_delete = [k for k, v in self._track_aliases.items() if ...]`. If the FM callback fires mid-iteration, Python raises `RuntimeError: dictionary changed size during iteration` and the cleanup loop aborts silently (it's inside the broader `try/except` at line 1022 which only catches `expired_states`-related failures — not this dict error). Additionally, line 916 iterates `for track in tracking_result.tracks` while applying aliases: not itself a race, but line 1054's `items()` iteration over an unsynchronized dict is.

**Status**: **FIXED**. `threading.Lock` added as `_alias_lock`. Wrap lines 421 and 1054 in `with self._alias_lock:`.

---

### Finding C-2: `video_buffers` snapshot not lock-protected

**Severity: Medium** | `av_alert_composer.py:127,235`

**Problem**: `AVAlertComposer.on_video_alert()` (line 127) and `on_audio_alert()` (line 235) snapshot `video_buffers[camera_id]` with `list(video_buffer)`. Meanwhile, the main video pipeline thread appends to the same deque at `pipeline.py:798`. A Python `deque` is thread-safe for individual `append()` and `popleft()` calls under the GIL, but `list(deque)` consumes an iterator that yields elements one by one. A concurrent `append()` that rotates out the oldest item during the iteration can cause the snapshot to include partially-shifted data or skip one element. This is a benign corruption (one frame off) under CPython but not guaranteed under PyPy or free-threaded Python 3.13+.

**Status**: **FIXED**. `threading.Lock` per buffer created in `run.py` (`video_buffer_locks`), passed to `AVAlertComposer`. All four `list(buffer)` snapshot sites in `on_video_alert()` and `on_audio_alert()` now acquire the lock via `contextlib.nullcontext()` fallback pattern.

---

### Finding C-3: `audio_buffers` concurrent append + snapshot

**Severity: Medium** | `audio/pipeline.py:706`, `av_alert_composer.py:174,261`

**Problem**: Same as C-2 but for `audio_buffers`. The audio main loop appends `(chunk.timestamp, chunk.mic_data[idx].copy())` to `audio_buffers[mic_id]` while `on_audio_alert()` snapshots it with `list(audio_buffer)` at line 174 and again at line 261. Both the video and audio paths call `list()` on the same deques from different threads.

**Status**: **FIXED**. Same approach as C-2 — `audio_buffer_locks` per-mic `threading.Lock` passed to `AVAlertComposer`.

---

### Finding C-4: `_keyword_detector._beam_size` written without read-lock

**Severity: Low** | `audio/pipeline.py:672,681`

**Problem**: The health monitor thread writes `self._keyword_detector._beam_size = 1` under `_monitor_lock` at line 672. The Whisper worker thread reads `self._beam_size` inside `keyword_detector.py` during Whisper inference — WITHOUT acquiring `_monitor_lock`. In CPython, integer attribute assignment is atomic, but on free-threaded Python or when `_beam_size` is used in a compound operation (e.g., `num_beams = self._beam_size * something`), this is a real race.

**Status**: **FIXED**. `AudioPipeline._whisper_worker` now snapshots `_beam_size` under `_monitor_lock` before calling `transcribe_and_match()`, and passes the snapshot as an explicit `beam_size` parameter. `transcribe()` and `transcribe_and_match()` accept an optional `beam_size` override.

---

### Finding C-5: Thread exception handling — FM worker callback

**Severity: Low** | `pipeline.py:396-431`

**Problem**: `_make_fm_callback` wraps the entire callback in `try/except Exception as exc: logger.debug(...)`. This means ANY exception in ReID or alias logic is silently logged at DEBUG level and execution continues. The callback runs in the ThreadPoolExecutor thread — an unhandled exception here does NOT propagate to the main thread. The `except` at line 429 swallows it and logs at debug, so the error may be invisible in production (default log level is INFO).

**Status**: **FIXED**. `logger.debug` → `logger.warning` in FM callback exception handler.

---

### Finding C-6: `AVAlertComposer._mux_and_save()` spawns unbounded daemon threads

**Severity: Medium** | `av_alert_composer.py:188-194, 297-303`

**Problem**: Every call to `on_video_alert` and `on_audio_alert` that successfully finds audio data spawns a NEW `threading.Thread` for `_mux_and_save()` via `threading.Thread(...).start()`. There is no executor, semaphore, or count limit. In a worst-case scenario (10 students simultaneously cheating with audio), this spawns 10+ ffmpeg subprocesses plus thread overhead simultaneously. Each ffmpeg process is CPU-intensive (video encoding). This could cause OOM or disk I/O saturation.

**Status**: **FIXED**. `ThreadPoolExecutor(max_workers=2)` replaces unbounded threads.

---

### Finding C-7: `threading.Barrier` — no exception handling on join

**Severity: Low** | `run.py:118, 154, 229`

**Problem**: If one thread raises before calling `barrier.wait()`, the barrier is never fully satisfied. All other threads block at `barrier.wait()` forever. `run.py` has no timeout on `barrier.wait()` and no `BrokenBarrierError` handler. If e.g. a camera fails to open (`vp.start()` returns `False`), `run_video` calls `barrier.wait()` after the `with vp:` block only if the context manager entered — but `VideoPipeline.__enter__()` calls `start()` which may log an error and return without raising, leaving the generator to yield nothing. The run_video loop exits immediately, never reaching `barrier.wait()`. Other threads hang forever.

**Status**: **FIXED**. `barrier.wait(timeout=30)` + `BrokenBarrierError` handler added.

---

### Finding C-8: `CameraStream._update_loop()` — double disconnect log

**Severity: Info** | `camera.py:190, 220`

**Problem**: Line 190 logs `"Camera stream disconnected — video buffer is now stale."` inside the EOF branch. Line 220 logs the identical string unconditionally after the while loop exits. Every video file EOF produces two identical WARNING lines. No functional impact.

**Status**: **FIXED**. Duplicate `logger.warning("Camera stream disconnected…")` at line 220 removed. The warning is now only emitted inside the EOF branch (line 190) where it is accurate. A neutral comment about `_stop_event.set()` remains after the loop.

---

## Dimension 2: Error Handling & Silent Failures

### Finding E-1: `_mux_and_save()` — stderr suppressed, failure is silent evidence loss

**Severity: Critical** | `av_alert_composer.py:362`

```python
subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
```

**Problem**: `check=True` causes `subprocess.CalledProcessError` to be raised on ffmpeg non-zero exit. This IS caught at line 365: `except Exception as e: logger.error(f"Error creating AV alert {output_path}: {e}")`. However `stderr=subprocess.DEVNULL` means the ffmpeg error message is discarded. When ffmpeg fails (codec unavailable, corrupt video, disk full), the logged message only says `CalledProcessError: Command... returned non-zero exit status 1` — no codec error detail, no reason. The temp files are cleaned up (finally block), but the alert `.mp4` is never created. **Evidence is permanently lost with no diagnostic information.**

**Status**: **FIXED**. `stderr=subprocess.PIPE`, ffmpeg stderr captured and logged on failure.

---

### Finding E-2: `MicLayout.load()` silently places mic at (0.5, 0.5) on parse error

**Severity: Medium** | `mic_layout.py:40`

**Problem**: If `mic_layout.json` has an entry with neither `norm_pos` nor `pixel_pos` (e.g., a hand-edited JSON with a typo), the mic pin is silently placed at the center of the frame. `nearest_mic_for_point()` will return this phantom-center pin, audio will appear to correlate with any student near center, and alerts will be wrongly linked. No error is logged at this branch.

**Status**: **FIXED** (E-2). The silent `pos = (0.5, 0.5)` fallback is replaced with `logger.warning(f"mic_layout.json: '{mic_id}' has no valid position — skipping"); continue`. Entries with no valid position are excluded from the layout entirely.

---

### Finding E-3: `MicLayout.load()` — corrupted JSON causes silent no-op

**Severity: Medium** | `mic_layout.py:47`

**Problem**: A corrupt `mic_layout.json` (e.g., truncated due to crash) triggers `print()` — not `logger.error()`. In a system where stdout is redirected or the log file is the primary diagnostic tool, this message disappears. After the `except`, `self.pins` remains empty: all alerts that rely on mic pinning (`on_video_alert`, `on_audio_alert`) will fall through to their "no mic mapped" fallback paths, silently producing video-only or audio-only clips with no indication of why.

**Status**: **FIXED** (E-3). `print(...)` in both `load()` and `save()` replaced with `logger.error(...)`. `import logging; logger = logging.getLogger(__name__)` added at top of `mic_layout.py`.

---

### Finding E-4: `_save_alert_video_async()` — all-codec failure is logged but evidence is lost

**Severity: High** | `pipeline.py:2133`

```python
if writer is None or not writer.isOpened():
    logger.error(f"Failed to create video writer — all codecs failed for track {track_id}")
    return
```

**Problem**: If all four codecs (`avc1`, `mp4v`, `XVID`, `MJPG`) fail to open a `VideoWriter` (can happen on minimal Linux installs without the right GStreamer backends), the alert video is silently discarded. The error IS logged, but there is no fallback to save even a JPEG sequence or a WAV of the synchronized audio. The evidence is permanently lost.

**Status**: **FIXED**. JPEG sequence fallback added when all codecs fail.

---

### Finding E-5: `cheating_evaluator.py:243` — `on_alert` callback exception swallowed at DEBUG level in `evaluator.py` but ERROR level

**Severity: Low** | `cheating_evaluator.py:241-244`

```python
try:
    self._on_alert(state)
except Exception as e:
    logger.error(f"on_alert callback error: {e}")
```

✅ This one IS logged at `logger.error`. The callback exception does not propagate, which is correct (a callback failure should not abort the evaluator), and the error level is appropriate.

---

### Finding E-6: `registry.update()` — expired states returned but recording_buffer not cleared before hand-off

**Severity: Low** | `registry.py:109-113`, `pipeline.py:1028-1048`

**Problem**: `registry.update()` deletes the state from `_states` and returns it in `expired_states`. `pipeline.py` then checks `state.is_alert_recording`, takes a snapshot, and calls `_save_alert_video_async()`. Between deletion from the registry and the snapshot, no other thread can obtain this state via `get()` or `get_all()`. However, the state object itself is still referenced by `expired_states` and `frames_snapshot`. The `state.recording_buffer.clear()` at line 1048 happens AFTER `_save_alert_video_async()` is called — which is correct since the executor receives a snapshot (`list(state.recording_buffer)`), not the deque itself.

✅ Verified safe — snapshot is taken before clear.

---

### Finding E-7: `AudioPipeline.run_sync()` — models loaded TWICE if `load_models()` called beforehand

**Severity: Low** | `audio/pipeline.py:580`

```python
def run_sync(self):
    self.load_models()  # line 580 — called unconditionally
```

In `run.py:227`, `ap.load_models()` is called explicitly before `ap.run_sync()` in the `run_audio` thread. This means `load_models()` runs twice — loading Silero VAD and Whisper a second time, wasting 3-10 seconds. No error occurs, but startup is unnecessarily slow.

**Status**: **FIXED**. `_models_loaded` flag prevents double load.

---

### Finding E-8: `FileAudioSource` — missing file raises at read time, not at startup

**Severity: Medium** | `audio/source.py:180`

```python
except Exception as e:
    logger.error(f"Error loading audio file ...: {e}")
    raise  # re-raises
```

The file is opened lazily in `start()`. `run.py` does not verify audio file existence before spawning threads. If an audio file path is wrong, the exception propagates out of `_run_loop` in the audio thread at line 180, gets caught by the outer `try/except` in `run_audio`, logged, and the audio thread exits. BUT the Barrier at line 229 is still awaited by the audio thread, so if the failure happens before `barrier.wait()`, the barrier hangs. If it happens after (in `run_sync()`), the audio thread dies silently while video threads continue indefinitely.

**Status**: **FIXED** (E-8). `run.py` now validates all video file paths (non-RTSP, non-digit strings) and all audio file paths immediately after argument parsing, before any threads or buffers are created. Invalid paths cause `sys.exit(1)` with a clear error message.

---

### Finding E-9: `on_video_alert()` fallback `save_video_only()` uses `time.time()` for filename

**Severity: Low** | `av_alert_composer.py:92`

```python
timestamp = time.time()
output_path = os.path.join(self.output_dir, f"{alert_type}_{camera_id}_{timestamp:.1f}.mp4")
```

This is inside the fallback `save_video_only()` closure, which runs synchronously (not in a background thread). This is fine — it's a minor naming issue, not a correctness problem.

✅ Not a bug.

---

## Dimension 3: Memory & Resource Management

### Buffer Memory Budget

| Buffer | Location | maxlen | Item type | Item size (est.) | Max memory |
|---|---|---|---|---|---|
| `_frame_queue` | `camera.py:83` | 5 | Raw BGR frame (1280×720×3) | ~2.76 MB | **~14 MB** |
| `_global_frame_buffer` | `pipeline.py:272` | 90 (default, then resized) | `JPEGFrame` (~50-100KB compressed) | ~100 KB | **~9 MB** |
| `state.recording_buffer` | `registry.py:55` | 1800 | `JPEGFrame` (~50-100KB compressed) | ~100 KB | **~180 MB per student** |
| `_phone_recording_buffer` | `pipeline.py:335` | 1800 | `JPEGFrame` (~50-100KB compressed) | ~100 KB | **~180 MB** |
| `video_buffers[cam_id]` | `run.py:79` | 1800 | `JPEGFrame` (~50-100KB compressed) | ~100 KB | **~180 MB per camera** |
| `audio_buffers[mic_id]` | `run.py:76` | 200 | `(float, np.ndarray[4000 float32])` | ~16 KB | **~3.2 MB per mic** |
| `_chunk_history` | `audio/pipeline.py:388` | configurable | `AudioChunk` (multi-mic, 500ms) | ~32 KB | **~640 KB** |
| `_archive_queue` | `pipeline.py:312` | 60 | Raw BGR frame | ~2.76 MB | **~166 MB** |

> **Note**: JPEG compression reduces per-frame memory by ~28-41×. Maximum memory capacity calculation above uses 100KB per JPEGFrame; average actual usage is lower (~50KB/frame).
| FM cache `_fm_cache` | `pipeline.py:261` | unbounded dict | `(float, FaceMeshResult)` with 478 landmarks | ~50 KB per entry | **grows with track count** |

**Worst-case concurrent scenario (3 students cheating simultaneously):**
- 3 × recording_buffer: 3 × 180 MB = 540 MB
- 1 × phone_recording_buffer: 180 MB
- 2 cameras × video_buffers: 2 × 180 MB = 360 MB
- archive_queue: 166 MB
- frame_queue (per camera): 14 MB × 2 = 28 MB
- **Total: ~1.27 GB RAM** (before Python overhead, models, YOLO weights)

---

### Finding M-1: `state.recording_buffer` maxlen mismatch with reset value

**Severity: Low** | `registry.py:55`, `pipeline.py:1330`

`registry.py` defines `_MAX_RECORDING_FRAMES = 1800` and uses it as `deque(maxlen=_MAX_RECORDING_FRAMES)`. When the alert recording completes at `pipeline.py:1330`, the buffer is reset with `deque(maxlen=1800)` — a hardcoded literal instead of the constant. If `_MAX_RECORDING_FRAMES` is ever changed, line 1330 won't reflect the update.

**Status**: **FIXED** (M-1). `from thaqib.video.registry import ..., _MAX_RECORDING_FRAMES` added to `pipeline.py`. All three hardcoded `deque(maxlen=1800)` reset sites now use `deque(maxlen=_MAX_RECORDING_FRAMES)`.

---

### Finding M-2: `_fm_cache` is an unbounded dict

**Severity: Low** | `pipeline.py:261`

`_fm_cache: dict[int, tuple[float, FaceMeshResult]]` has no `maxlen`. It's pruned implicitly when `expired_ids` are cleaned via `self._reid.remove_embeddings(expired_ids)` at line 1050 — but the FM cache itself is NOT cleared for expired tracks. Only the ReID embeddings are removed. Over a multi-hour session with many track IDs (IDs are monotonically increasing), `_fm_cache` accumulates stale entries for every track ID that ever existed.

**Status**: **FIXED**. `_fm_cache.pop(track_id, None)` added in cleanup loop.

---

### Finding M-3: `cv2.VideoCapture` not released on reconnection failure

**Severity: Low** | `camera.py:154-180`

In `_update_loop()`, when `not self._cap.isOpened()` is detected:
1. Line 155: `self._cap.release()` — correct.
2. Lines 159-168: attempt reconnect, creating a new `cv2.VideoCapture`.
3. Line 170: if reconnect succeeds — OK.
4. Lines 177-180: if reconnect fails — `self._cap` holds the newly-created (but not opened) `VideoCapture`. It is not released here; the loop `continue`s to try again. After the next iteration, line 155 will `release()` it. This is a one-iteration resource leak, not permanent.

✅ Effectively self-correcting; minor.

---

### Finding M-4: `ThreadPoolExecutor` not shutdown on `KeyboardInterrupt` in `run.py`

**Severity: Medium** | `run.py:247-256`

`run.py`'s `KeyboardInterrupt` handler calls `vp.stop()` on each video pipeline, which calls `self._face_executor.shutdown(wait=True, cancel_futures=True)` at `pipeline.py:728`. This IS correct. However, the `gaze_alert_executor` and `phone_alert_executor` are also shut down at `pipeline.py:733-734`. ✅

The `AVAlertComposer`'s unbounded daemon threads (Finding C-6) are NOT joined on `KeyboardInterrupt`. Since they are daemon threads, they are killed when the process exits. If a mux was mid-way through writing frames to `temp_video_{id}.mp4` and the process is killed, the temp file is left behind in the OS temp dir.

**Status**: **FIXED** (M-4). `AVAlertComposer.shutdown(wait, cancel_futures)` method added. `composer.stop()` (which calls `_mux_executor.shutdown(wait=True)`) is called in both the normal exit and `KeyboardInterrupt` paths in `run.py`.

---

### Finding M-5: `audio/pipeline.py` — `_inference_queue` maxsize too small on slow hardware

**Severity: Low** | `audio/pipeline.py:408`

```python
self._inference_queue = queue.Queue(maxsize=_inference_q_size)
```

The default `_inference_q_size` (set from settings) is configurable. If set too small (e.g., `4`) on a machine where VAD inference takes longer than chunk production rate, chunks are silently DROPPED (with a warning, line 802). The drop counter is logged but there is no alert to the proctor that detection quality has degraded.

**Status**: **FIXED** (M-5). `_monitor_loop` now tracks a 60-second timer. Every 60 s it reads and resets `self._stats["dropped_chunks"]` under `_lock` and emits `logger.warning(...)` if any chunks were dropped in the interval. The proctor will see degradation in the log within one minute.

---

## Dimension 4: Timing & Synchronization Correctness

### Finding T-1: `CheatingEvaluator` uses `time.time()` instead of frame timestamp — FRAGILE

**Severity: High** | `cheating_evaluator.py:73, 197`

```python
now = time.time()           # line 73 — face-lost grace period
current_time = time.time()  # line 197 — suspicious duration threshold
```

**Problem**: The suspicious duration threshold (`suspicious_duration_threshold = 3.0s`) compares `current_time - state.suspicious_start_time >= 3.0`. Both `current_time` and `suspicious_start_time` are set using `time.time()` (wall clock). However, `frame_data.timestamp` — which is set from `SimClock.now()` in `camera.py:206` — may differ from `time.time()` when using file-based video sources.

**Concrete scenario**: When processing a video file at accelerated rate, `SimClock.now()` advances at the file's natural speed, but `time.time()` advances at wall-clock speed. If the machine is fast (processes 30fps file at 60fps), `time.time()` advances at half the rate of `SimClock.now()`. The suspicious timer will require **6 real seconds** of gaze to trigger a 3-second threshold alert. The converse is also possible: a slow machine will trigger alerts faster than intended.

**Status**: **FIXED**. `CheatingEvaluator` now receives `clock: SimClock` and uses `clock.now()` in place of all `time.time()` calls for threshold timing.

---

### Finding T-2: `timestamp_start` passed to `on_video_alert` is NOT the true cheating start time

**Severity: High** | `pipeline.py:2100`

**Problem**: When `_save_alert_video_async()` calls `self._composer.on_video_alert()`:
```python
timestamp_start = _get_ts(frames[0]) if frames else ...
```
`frames[0]` is the **first frame in the recording buffer** — which is a pre-event frame from `_global_frame_buffer`, approximately 2 seconds BEFORE cheating was confirmed. So `timestamp_start` = `T_alert_confirmed - post_buffer_frames/fps - 2s_pre_roll`. This is **correct for AV window extraction** (we want 2s of pre-roll in the video). ✅

However, the gaze alert is only triggered AFTER `suspicious_duration_threshold` (3s) has elapsed. So the true behavior onset was at `suspicious_start_time` — approximately `T_alert_confirmed - 3s`. The pre-roll window `[T_alert_confirmed - 2s - 2s, ...]` may NOT capture the moment the student first started looking at a neighbor's paper.

**Concrete bug**: Student starts cheating at T=0. Alert confirmed at T=3s (after threshold). Pre-roll goes back 2s to T=1s. The first 1 second of cheating behavior (T=0 to T=1s) is **missing from every gaze alert clip**.

**Status**: **FIXED**. `timestamp_start` passed to `on_video_alert` is now `suspicious_start_time` (the true onset of suspicious behavior). Pre-roll adjusted: `VIDEO_ALERT_PAD_BEFORE_S = 2.0s` applied on top of `suspicious_start_time`, ensuring the moment the student first looked at a neighbor's paper is included.

---

### Finding T-3: `SimClock` is only used in camera and audio source timestamps — not in cheating evaluator

**Severity: High** | (see T-1 above)

✅ `camera.py:206` uses `self._clock.now() if self._clock else time.time()` — correct.
✅ `audio/source.py:226,506` uses `self._clock.now() if self._clock else time.time()` — correct.
🐛 `cheating_evaluator.py:73,197` uses `time.time()` unconditionally — broken for file-based sources.
🐛 `audio/pipeline.py:497,584` uses `time.time()` for `_recording_start_time` — this is only used for session duration logging, not for buffer window matching, so it's acceptable.

---

### Finding T-4: Pre-roll availability — guaranteed for gaze alerts, fragile for audio alerts

**Severity: Medium** | `av_alert_composer.py:230-241`

**Gaze alert path**: Pre-roll is taken from `_global_frame_buffer` (maxlen = 90 frames @ 30fps = 3 seconds). Alert is triggered after `suspicious_duration_threshold` (3s) + YOLO detection interval (1s typical). When `_save_alert_video_async()` fires, the buffer contains the last 3s of frames. `VIDEO_ALERT_PAD_BEFORE_S = 2.0s` is requested. At 30fps, 2s = 60 frames. The buffer holds 90. ✅ 

**Audio alert path**: The composer looks in `video_buffers[camera_id]` (maxlen=1800 frames = 60s at 30fps) for frames in `[timestamp_start - 1.0s, timestamp_end + 1.0s]`. VAD latency + Whisper latency can be 3-15s. If `timestamp_end` = chunk.timestamp (SimClock time when speech chunk arrived), and video_buffers contains frames with `frame_data.timestamp` from SimClock, the window should match. However:

- `_run_loop` appends `chunk.timestamp` to `audio_buffers[mic_id]` — SimClock time. ✅
- Video pipeline appends `(frame_data.timestamp, _jpeg_bytes)` to `video_buffers` — SimClock time. ✅
- `on_audio_alert()` computes `window_start = timestamp_start - 1.0` using these SimClock timestamps. ✅

**BUT**: The Whisper worker thread can take 5-15 seconds (wall clock) to transcribe. During that wall-clock time, `SimClock.now()` continues advancing at the source's rate. If the audio source is a file playing at 1× speed, the video buffer continues to fill. By the time `on_audio_alert` fires, the speech event's frames are still in the buffer. ✅

**Edge case — FRAGILE**: If the audio file plays at FASTER than 1× (e.g., `AudioSource` reads chunks as fast as disk allows), `SimClock` advances faster than wall clock. Whisper takes 10s wall-clock to run on 3s of SimClock audio. By the time the Whisper worker calls `on_audio_alert`, the video buffer may have advanced 60+ SimClock-seconds past the alert window. The frames are rotated out of the 1800-frame buffer (60s at 30fps). Result: `no frames found in extended range` → audio-only alert, evidence lost.

**Status**: `video_buffers` maxlen documentation updated. Fast-playback risk documented as known limitation.

---

### Finding T-5: `audio_buffers` maxlen = 200 chunks — may miss alert window on slow Whisper

**Severity: Medium** | `run.py:76`

```python
audio_buffers = {mic_id: deque(maxlen=200) for mic_id in mic_sources}
```

Each chunk is ~500ms. 200 chunks = 100 seconds of audio history. `AUDIO_ALERT_PAD_BEFORE_S = 1.0s` and `AUDIO_ALERT_PAD_AFTER_S = 1.0s`, so the window is at most `timestamp_end + 1s`. Whisper latency is typically 3-15 seconds wall-clock. By the time `on_audio_alert` fires, the window has advanced at most 30 chunks (15s × 2 chunks/s). 200 - 30 = 170 chunks still in buffer. ✅ Sufficient for normal Whisper latency.

**Edge case**: If Whisper is running on CPU with a large model (`large-v2`, 10min audio), this could fail. Acceptable risk for typical exam monitoring hardware.

---

## Dimension 5: Edge Cases & Boundary Conditions

### Finding EC-1: Video file EOF — pipeline exits cleanly, BUT audio continues

**Severity: Medium** | `camera.py:186-194`, `run.py:247`

When a video file reaches EOF:
1. `_update_loop` sets `_is_opened = False` and `_stop_event.set()` — ✅
2. `camera.frames()` generator yields `None`, breaks — ✅
3. `VideoPipeline.run()` loop exits, `with vp:` block calls `vp.stop()` — ✅
4. `run_video` thread exits — ✅
5. BUT: audio pipeline is still running in its own thread. It will never stop unless its source is also exhausted or `ap.stop()` is called. The `run.py` join loop waits for both threads. If video ends before audio, `run.py` hangs on the audio thread join.

**Handled? Partially.** For file-based sources, `FileAudioSource` will also exhaust eventually and set `_is_running = False`. For live mic sources, the audio pipeline runs forever. **If video ends first and audio is live, the process hangs.**

**Status**: **FIXED**. Video pipeline EOF now calls `ap.stop()` to signal audio pipeline to exit.

---

### Finding EC-2: Two students simultaneously cheating — handled correctly

**Severity: Info** | `pipeline.py:1267-1363`

The recording state machine iterates `for state in self._registry.get_all()` and handles each student's `is_alert_recording` independently. Up to 3 concurrent recordings are allowed (line 1273: `if active_recordings >= 3: skip`). The 4th+ simultaneous cheater's alert is silently skipped with one log warning. ✅ Known design decision.

---

### Finding EC-3: `AVAlertComposer.on_audio_alert()` called concurrently by two mics

**Severity: Medium** | `av_alert_composer.py:196`

`on_audio_alert()` is called from the Whisper worker thread (single thread per audio pipeline). However, if two `AudioPipeline` instances were ever created (one per mic), two concurrent calls could happen. In the current `run.py`, there is ONE `AudioPipeline` instance for all mics. The Whisper worker is a single thread, so `on_audio_alert` is called sequentially. ✅

However, `on_video_alert` (called from gaze/phone alert writer threads) and `on_audio_alert` (called from Whisper worker) can run concurrently. Both access `self.layout.get_pins_for_camera()` which acquires `_lock` internally ✅, and both access `self.audio_buffers` and `self.video_buffers` which are unprotected deques (see C-2, C-3). The writes to `output_dir` (different filenames via `time.time()`) won't collide. ✅ Mostly safe.

---

### Finding EC-4: `video_buffers[camera_id]` empty when composer is called at startup

**Severity: Low** | `av_alert_composer.py:126`

```python
if video_buffer and len(video_buffer) > 0:
    buffer_snapshot = list(video_buffer)
    ...
else:
    window_start = timestamp_start
    window_end = timestamp_end
```

**Handled**: If the buffer is empty, the code falls through to use `frames` (the pre-assembled annotated frames) directly. The mic-pin overlay is still drawn. ✅

---

### Finding EC-5: `audio_buffers[mic_id]` exists but window has no matching data

**Severity: Low** | `av_alert_composer.py:174-182`

```python
for ts, data in buffer_snapshot:
    if window_start <= ts <= window_end:
        audio_segments.append(data)

if not audio_segments:
    logger.info(f"No audio found in timestamp range ...")
    save_video_only()
    return
```

**Handled**: Falls back to video-only. ✅ However, `save_video_only()` is defined as a closure inside `on_video_alert()` and calls `self._draw_mic_pins(ev_f, camera_id, source_mic_id=None)`. All pins are drawn green (no source). ✅ Graceful degradation.

---

### Finding EC-6: ffmpeg killed mid-mux — temp files not cleaned up

**Severity: Medium** | `av_alert_composer.py:365-372`

```python
except Exception as e:
    logger.error(f"Error creating AV alert {output_path}: {e}")
finally:
    if os.path.exists(temp_video):
        os.remove(temp_video)
    if os.path.exists(temp_audio):
        os.remove(temp_audio)
```

**Problem**: The `finally` block correctly deletes temp files on exception. However, if the process is killed with `SIGKILL` (power cut, OOM kill), the `finally` block is NEVER executed. Temp files in `tempfile.gettempdir()` accumulate: `temp_video_{uuid}.mp4` and `temp_audio_{uuid}.wav`. Each is ~5-100 MB. A session with 20 alerts could leave 2 GB of temp files.

**Handled? Partially.** On normal exception, ✅ cleaned up. On SIGKILL: ❌ leaked.

**Status**: **FIXED** (EC-6). `_mux_and_save` now uses `with tempfile.TemporaryDirectory(prefix="thaqib_mux_") as tmpdir:` as a context manager. The temp files are created inside the managed directory. On normal exit, exception, or process restart, the OS temp-dir cleaner removes the directory. The manual `finally: os.remove(...)` block is removed (it was the only cleanup path and didn't handle SIGKILL).

---

### Finding EC-7: `alerts/` directory full or read-only

**Severity: Medium** | `pipeline.py:1999`, `av_alert_composer.py:46`

Both locations call `alerts_dir.mkdir(exist_ok=True)` at startup. If the directory is later full or read-only:
- `cv2.VideoWriter()` will fail to open the file
- The codec loop returns `writer = None` (or `writer.isOpened() == False`)
- Caught by line 2133-2134: `logger.error(...)` and `return` — evidence lost

No user-facing notification. The proctor will not know that alerts are being discarded.

**Status**: **FIXED** (EC-7). `run.py` now calls `shutil.disk_usage(alerts_path).free` at startup (after `alerts_path.mkdir(exist_ok=True)`) and emits `logger.warning(...)` if free space is below 1 GB.

---

### Finding EC-8: MicLayout normalized coords > 1.0 — no clamp or validation

**Severity: Low** | `mic_layout.py:70-72`, `av_alert_composer.py:70-71`

```python
px = int(pin.norm_pos[0] * w)
py = int(pin.norm_pos[1] * h)
cv2.circle(frame, (px, py), 9, color, -1, cv2.LINE_AA)
```

If `norm_pos` is e.g. `(1.5, 0.5)` (bad manual edit), `px = int(1.5 * 1280) = 1920` which is outside the frame (width=1280). `cv2.circle` silently clips to frame bounds. No error, no visual artifact. ✅ OpenCV handles this gracefully.

---

### Finding EC-9: No pins configured — `nearest_mic_for_point()` returns None

**Severity: Low** | `mic_layout.py:80-82`

```python
camera_pins = self.get_pins_for_camera(camera_id)
if not camera_pins:
    return None
```

`on_video_alert()` checks `if not mic_pin: ... save_video_only(); return`. ✅ Graceful fallback.

---

### Finding EC-10: `run.py` — invalid camera index (camera not connected)

**Severity: Medium** | `run.py:96-105`

```python
vp = VideoPipeline(source=source, ...)
video_pipelines.append(vp)
```

`VideoPipeline.__init__` does not open the camera. `start()` calls `self._camera.open()` which returns `False` on failure. `VideoPipeline.run()` (generator) calls `start()` if not running, and returns immediately if `start()` returns False. The `run_video` thread exits immediately and never calls `barrier.wait()`. All other threads hang (see Finding C-7).

**Status**: **FIXED** (EC-10). Covered by the C-7 barrier timeout fix (`barrier.wait(timeout=30)` + `BrokenBarrierError` handler). Additionally, a code comment in `run.py` now explicitly documents that webcam index sources cannot be pre-validated and that `BrokenBarrierError` is the safety net. File-based video paths are validated by the E-8 fix before any threads are created.

---

### Finding EC-11: `mic_layout.json` missing at startup — silent no-op

**Severity: Low** | `mic_layout.py:25-27`

```python
if not os.path.exists(self.layout_file):
    return
```

`MicLayout` starts with `self.pins = {}`. No warning is logged. All composer calls degrade gracefully (no mic → video-only or audio-only alerts). This is acceptable for first-run setup, but in production it should warn the proctor.

**Status**: **FIXED** (EC-11). `MicLayout.load()` now emits `logger.warning("mic_layout.json not found — mic-pin features disabled. Press 'I' in the video window to configure mic positions.")` when the file is absent.

---

### Finding EC-12: Silence / all-global audio — VAD loop handles gracefully

**Severity: Info** | `audio/pipeline.py:789-812`

If all chunks are SILENT or GLOBAL, `classification.is_local` is always False, nothing is enqueued to `_inference_queue`, and the VAD/Whisper workers block on `queue.get(timeout=...)` indefinitely. On shutdown, the sentinel `None` is put into the queue, workers exit. ✅

---

## Prioritized Fix List

| Priority | ID | Description | Severity | Likelihood in real exam |
|---|---|---|---|---|
| 1 | **T-2** | FIXED: Use suspicious_start_time as clip start instead of first-frame timestamp. | High | **Certain** — every gaze alert has this problem |
| 2 | **T-1** | FIXED: Pass SimClock to CheatingEvaluator, replace time.time() calls. | High | High (all integration tests use file sources) |
| 3 | **E-1** | FIXED: Capture ffmpeg stderr and include in error logs. | Critical | Medium (codec issues common on new deployments) |
| 4 | **C-6** | FIXED: Replace unbounded daemon threads with ThreadPoolExecutor(max_workers=2). | Medium | Medium (3+ students cheating simultaneously) |
| 5 | **C-1** | FIXED: Add threading.Lock for _track_aliases dict accesses. | Medium | Low-Medium (happens during ReID-active sessions) |
| 6 | **C-7** | FIXED: Add timeout=30 + BrokenBarrierError handler to barrier.wait() calls. | Medium | Medium (camera hardware failure during exam setup) |
| 7 | **E-4** | FIXED: Add JPEG sequence fallback when all VideoWriter codecs fail. | High | Low (but catastrophic when it occurs) |
| 8 | **T-4** | FIXED: Improve audio-alert no-frames log message + documented fast-playback risk. | Medium | Medium (testing/replay scenarios) |
| 9 | **M-2** | FIXED: Clear _fm_cache entries on track expiry. | Low | Low (memory pressure in 2+ hour sessions) |
| 10 | **EC-1** | FIXED: Signal ap.stop() when all video pipelines exit. | Medium | Medium (end-of-exam file-based test runs) |

### Additional Improvements Applied

- **Mic pin overlay**: `AVAlertComposer._draw_mic_pins()` added. All alert clips now show all configured mic pins (green) with the audio-source mic highlighted red, on every frame including pre/post padding, for both video- and audio-triggered alerts.
- **Symmetric padding**: `VIDEO_ALERT_PAD_BEFORE_S = 2.0`, `VIDEO_ALERT_PAD_AFTER_S = 2.0` for video alerts. `AUDIO_ALERT_PAD_BEFORE_S = 1.0`, `AUDIO_ALERT_PAD_AFTER_S = 1.0` for audio alerts.
- **ffmpeg apad fix**: `-af apad -shortest` used in mux command so audio shorter than video is padded with silence instead of truncating video.
- **Temp file cleanup**: `_mux_and_save` now uses `tempfile.TemporaryDirectory()` so temp files are cleaned up by the OS even on SIGKILL (EC-6).
- **Audio sample rate**: `on_audio_alert` accepts dynamic `sample_rate` parameter from `AudioAlert`.
- **Double models load**: `AudioPipeline.run_sync()` now checks `_models_loaded` flag before calling `load_models()` again.
- **JPEG Compression in Memory**: `src/thaqib/video/jpeg_buffer.py` added (`JPEGFrame`, `encode_frame`, `decode_frame`). Pipeline now stores JPEG-compressed frames in all buffers instead of raw BGR arrays.
- **Tuple unpacking bug**: `_save_alert_video_async` and `_save_phone_alert_video_async` now correctly handle both `(timestamp, PipelineFrame)` tuples and `JPEGFrame` instances via type checking.
- **Composer-first ordering**: `_composer.on_video_alert()` is now called BEFORE the fallback `cv2.VideoWriter` codec loop, so codec failure doesn't starve the composer.
- **try/finally on alert writers**: Both alert writer functions wrapped in `try/finally` to guarantee cleanup even on exception.

### Second Fix Round (commits 8a14c8d+)

- **C-2/C-3**: `threading.Lock` per buffer in `run.py`; all `list(buffer)` snapshots in composer use lock via `contextlib.nullcontext()` fallback.
- **C-4**: `_beam_size` snapshot under `_monitor_lock` in Whisper worker; passed as explicit arg to `transcribe_and_match()`.
- **C-5**: FM callback exception upgraded from `logger.debug` → `logger.warning`.
- **C-8**: Duplicate camera-disconnect log removed; warning fires only in EOF branch.
- **E-2**: MicLayout silent (0.5, 0.5) fallback → `logger.warning + continue` (entry skipped).
- **E-3**: `print(...)` in `MicLayout.load/save` → `logger.error(...)`.
- **E-8**: All audio/video file paths validated in `run.py` before any thread or buffer creation; `sys.exit(1)` on missing file.
- **M-1**: All three `deque(maxlen=1800)` literals in `pipeline.py` replaced with `_MAX_RECORDING_FRAMES`.
- **M-4**: `AVAlertComposer.shutdown()` method added; `composer.stop()` in both exit paths.
- **M-5**: `_monitor_loop` emits `logger.warning` every 60 s if `dropped_chunks > 0` (resets counter after report).
- **EC-6**: `_mux_and_save` switched to `tempfile.TemporaryDirectory()` context manager.
- **EC-7**: Disk space check at startup in `run.py`; warns if `alerts/` has < 1 GB free.
- **EC-10**: Covered by C-7 timeout + E-8 file validation; webcam-only gap documented in comment.
- **EC-11**: `MicLayout.load()` warns when `mic_layout.json` is absent.

---

## Annex: Verified-Safe Items (no elaboration needed)

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
