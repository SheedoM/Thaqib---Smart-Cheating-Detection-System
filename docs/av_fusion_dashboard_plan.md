# Implementation Plan — AV Fusion in the Product + Mic Selection + Clip Playback Speed

_Last updated: 2026-06-15_

## Context & Goal

A cheating incident should produce **one clip in the dashboard that combines the camera video with the audio of the offending student's nearest microphone**. The fusion logic already exists (`AVAlertComposer`) and works in the **offline desktop harness** (`run.py` + OpenCV windows, file inputs). It is **not wired into the live web product**: `src/thaqib/api/routes/stream.py` runs video-only, never instantiates the audio pipeline or the composer, and has no microphone transport or mic→camera mapping.

Developer "Shalan" (branch `origin/feature/video-detection`) added **mouse-based mic placement** and **alert-clip FPS/duration fixes**, but the mic placement lives only in the desktop OpenCV visualizer and its `MicLayout` is **in-memory, session-only** (persistence was deliberately removed in commit `14a2bc7`).

This plan folds three things into one effort:
- **A. Make AV fusion real in the product** (simulator-served audio, full production hardening).
- **B. Bring mic selection/placement into the web dashboard** (with DB persistence; mic→camera mapping from DB device data + seed defaults).
- **C. Add an alert-clip playback-speed toggle** in the dashboard.

Decisions already taken: audio transport = **simulator-served stream** (mirror the camera simulator); mic layout source = **DB device data + seed defaults**; scope = **full production hardening**.

## Current State (reuse inventory)

**Exists and reusable**
- `src/thaqib/av_alert_composer.py` — `AVAlertComposer.on_video_alert` / `on_audio_alert`, ffmpeg mux (`-c:v copy -c:a aac`), nearest-mic selection via `MicLayout.nearest_mic_for_point`, video-only / audio-only fallbacks.
- `src/thaqib/video/pipeline.py` — `VideoPipeline` accepts `composer`, `camera_id`, `frame_buffer`, `clock`; fires `composer.on_video_alert(...)` at alert time.
- `src/thaqib/audio/pipeline.py` — `AudioPipeline` accepts `source`, `composer`, `audio_buffers`, `mic_ids`, `clock`; has `start()` (threaded daemons) / `stop()`; fills `audio_buffers`; fires `composer.on_audio_alert(...)`.
- `src/thaqib/audio/source.py` — `AudioSource` ABC, `FileAudioSource`, and `LiveAudioSource` (sounddevice). **No URL/stream-based source yet.**
- `src/thaqib/mic_layout.py` (Shalan) — in-memory `MicLayout`, multi-camera-per-mic (`pins: Dict[str, List[MicPin]]`), `add_pin / get_pins_for_camera / nearest_mic_for_point / cameras_for_mic / camera_for_mic`.
- `simulator/main.py` + `simulator/config.yaml` — FastAPI; `cameras:` map → MJPEG `/camera/{id}/feed` on `:8000`; Dockerfile **already installs ffmpeg**; demo `cam1.mp4`/`cam2.mp4` contain audio tracks.
- DB: `DetectionEvent.audio_clip_path` field already exists (unused); WebSocket `incident_card` already carries `audio_clip_path` + `video_clip_path`. Camera `Device.position` JSON is already serialized; alert clips served via `/api/stream/alerts/video/{path}` and `/api/sessions/.../alerts/{id}/clip`.
- Frontend clip players: `CameraModal.tsx:341` (admin), `HallMonitoringPage.tsx:651` (invigilator).

**Missing**
- Audio transport into the server; a URL-based `AudioSource`.
- Mic→camera→position persistence; a DB→`MicLayout` builder.
- Audio/composer wiring in `stream.py`; hall-centric runtime.
- Fused-clip → DB alert attachment.
- Web mic-placement UI; clip speed control.
- `SimClock` is simulation-only; production needs a wall-clock.

## Target Architecture

Per **monitored hall**, on monitoring start, build a `HallAVRuntime` that owns:
- a shared **wall-clock** (replace `SimClock` usage with `time.time`-based clock so audio and video timestamps align in real time);
- `video_buffers[camera_id]`, `audio_buffers[mic_id]`, `video_registries[camera_id]` (deques/registries);
- a per-hall `MicLayout` built from DB device placements;
- one `VideoPipeline` per camera (constructed **with** `composer`, `camera_id=str(device.id)`, `frame_buffer`, `clock`);
- one `AudioPipeline` (multi-mic) reading a `StreamAudioSource` that pulls each mic's audio from the simulator;
- one `AVAlertComposer` whose muxed MP4 output is attached to the DB alert.

IDs are unified as `str(device.id)` for both `camera_id` and `mic_id` everywhere (composer, buffers, layout, pipelines).

---

## Workstreams

### WS1 — Simulator: audio streaming endpoint
- Add a `mics:` section to `simulator/config.yaml` (`mic_id → {audio_path}`); for the demo, point at audio extracted from `cam1.mp4`/`cam2.mp4` (ffmpeg present) or dedicated `.wav` files.
- Add a `MicStreamer` analog to `VideoStreamer` and a route `GET /mic/{mic_id}/feed` that streams **looped, chunked PCM/WAV** (fixed sample rate 16 kHz, mono, e.g. 500 ms chunks) as `StreamingResponse`. Add `/mics` + `/mic/{id}/info` for parity.
- Files: `simulator/main.py`, `simulator/config.yaml`, `simulator/README.md`.

### WS2 — Backend: URL-based audio source
- New `StreamAudioSource(AudioSource)` in `src/thaqib/audio/source.py` that opens each mic's simulator URL and yields synchronized `(n_mics, n_samples)` chunks with clock timestamps, masking dead mics with silence (reuse the dead-mic pattern in `LiveAudioSource`). Must satisfy the ABC (`start/get_chunk/stop/num_mics/sample_rate`).
- A real-time clock: small `WallClock` (or reuse `SimClock` interface with `now()=time.time()`), shared by audio + video.

### WS3 — DB mic-layout persistence + builder
- Store placements in the mic `Device.position` JSON (multi-camera, mirrors Shalan's model):
  ```json
  { "label": "...", "placements": [ { "camera_id": "<deviceId>", "norm_pos": [0.3, 0.5] } ] }
  ```
- `mic_stream_url` on the mic `Device.stream_url` (the simulator `/mic/{id}/feed` URL), analogous to cameras.
- `build_mic_layout(hall) -> MicLayout`: iterate the hall's mic devices, `add_pin(str(mic.id), camera_id, norm_pos)` for each placement.
- Serialize `placements` + `source_configured` in `_hall_to_payload` mics ([stream.py:286](../src/thaqib/api/routes/stream.py)).
- Endpoints (extend `devices.py`, admin-scoped writes): `PUT /api/devices/{micId}/placements` (replace list); optionally `DELETE` one. Reads come via `/api/stream/monitoring`.

### WS4 — Hall-centric monitoring runtime (`stream.py`)
- Introduce `HallAVRuntime` and a `_hall_runtimes` registry alongside the existing `_camera_states`.
- In `start_hall_monitoring`: build buffers/registries/layout/clock/composer; start camera `VideoPipeline`s **with composer + frame_buffer + clock**; start one `AudioPipeline.start()` with `StreamAudioSource`. In `stop_hall_monitoring`: stop the audio pipeline, stop camera threads, drop the runtime.
- Keep the MJPEG live feed working (the async generator from the prior fix) — the composer path is for *alert clips*, independent of the live preview.
- Guard with a settings flag (e.g. `av_fusion_enabled`) so video-only operation remains possible if audio infra is down.

### WS5 — Fused clip → DB alert
- Route composer output into the alert record: set `DetectionEvent.video_clip_path` to the **fused MP4** (so the existing `<video>` plays it with sound) and optionally `audio_clip_path` for a raw-audio artifact. Reconcile with the current `on_alert` → `_persist_stream_alert` + `_poll_for_alert_clip` flow (the composer becomes the clip producer; the disk-polling attach is replaced by a direct callback from the composer with the output path).
- Ensure WebSocket `incident_card` emits the populated `video_clip_path`/`audio_clip_path`.

### WS6 — Frontend: mic placement UI (admin `CameraModal`)
- Add a **mic-placement mode** toggle in the enlarged-feed controls.
- Mic **dropdown** (hall mics from payload) replaces Shalan's right-click cycle; click on the feed `<img>` → `norm_pos = [offsetX/clientWidth, offsetY/clientHeight]` → `PUT /api/devices/{micId}/placements`.
- Render existing placements as absolutely-positioned overlay pins (port `_draw_mic_placement` idea), with delete and optional drag-to-move.
- Files: `frontend/src/components/CameraModal.tsx`, a new `MicPlacementOverlay.tsx`, types in `frontend/src/types/exams.ts`.

### WS7 — Frontend: clip playback-speed toggle (no backend)
- New shared `VideoSpeedControl` component (`0.25× / 0.5× / 1× / 2×`) holding a `videoRef`, setting `videoRef.current.playbackRate`; reset to `1×` on open.
- Wire into both players: `CameraModal.tsx:341` and `HallMonitoringPage.tsx:651`.

### WS8 — Seeding & config defaults
- Update the canonical root `seed_demo.py` so mic devices get a `stream_url` (simulator `/mic/{id}/feed`) and sensible default `placements` for demo halls. Mirror the existing camera `stream_url` seeding.

### WS9 — Performance & hardening
- Whisper/Silero load **per hall** is heavy: default to `whisper tiny`, CPU int8; consider a shared model/executor or load only while a hall is monitored. Use Shalan's perf flags (VAD batching, `FACE_MESH_INTERVAL`, per-camera YOLO).
- Apply the AV-sync fix from Shalan's analysis: make the composer **wait for `video_buffer.newest_ts >= window_end`** before muxing (or set `audio_alert_clip_after`), to avoid 0-second/reversed-window clips (`docs/av_sync_analysis.md`, `docs/alert_duration_analysis.md`).
- Ensure ffmpeg is present on the **backend** host (add a startup check like `run.py` and document/Docker it).

### WS10 — Tests & verification
- Unit: `StreamAudioSource` chunking; `build_mic_layout`; placement endpoints (scoping); composer attach-to-alert.
- Integration: simulated hall → audio+video alert → fused MP4 attached → served via clip endpoint.
- Frontend: `VideoSpeedControl` sets `playbackRate`; placement POST shape.

---

## Sequencing (milestones)

1. **M0 — Quick win:** WS7 playback speed toggle (frontend only). Ship immediately.
2. **M1 — Config layer:** WS3 (DB persistence + builder + serialization) + WS6 (placement UI). Standalone; no audio runtime needed.
3. **M2 — Audio transport:** WS1 (simulator audio) + WS2 (URL source) + WS8 (seed mic stream_urls). Verifiable with a standalone audio-pipeline smoke test.
4. **M3 — Fusion in product:** WS4 (hall runtime) + WS5 (clip→alert) + WS9 (perf/AV-sync). Lights up M1's placements.
5. **M4 — Hardening:** WS9 remainder + WS10 tests + ffmpeg packaging.

## Risks / open questions
- **Per-hall model cost** (Whisper×halls) — may need a shared inference service; validate on target hardware.
- **AV latency** — must implement the composer wait-for-video fix or clips will be empty.
- **Shalan's session-only `MicLayout`** diverges from DB persistence; we keep his in-memory class but populate it from DB at monitoring start (don't reintroduce JSON files).
- **Branch state** — Shalan's work is on `feature/video-detection`, ahead of `develop`; decide merge timing before building on it.
- **Seed script drift** was resolved by making root `seed_demo.py` the only demo seeding entrypoint, with `college` and `university` modes.

## Verification (end-to-end)
1. Run simulator (`:8000`) with `mics:` configured; `curl /mic/<id>/feed` streams audio.
2. Seed (university mode) so mics have `stream_url` + placements; start monitoring a hall from the invigilator app.
3. In admin `CameraModal`, confirm mic pins render; move one and confirm it persists (reload).
4. Trigger a cheating event (phone/gaze or a keyword on the audio track); confirm a **fused MP4** appears as the alert clip and **plays with audio** in both review UIs.
5. Use the **speed toggle** (0.25×–2×) on the clip and confirm playback rate changes.
6. Stop monitoring; confirm audio+video threads tear down and session reaches `completed`.
