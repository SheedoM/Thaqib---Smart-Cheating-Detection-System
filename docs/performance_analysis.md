# Performance Analysis: Thaqib System

## Executive Summary
The primary bottleneck in the system is the **Audio VAD (Voice Activity Detection) inference loop**. Even with proper real-time chunk pacing, the VAD processes 512-sample audio windows sequentially using a Python list comprehension, resulting in 15 separate PyTorch model calls per 500ms audio chunk. This Python-level overhead prevents the audio pipeline from running faster than real-time, causing the inference queue to overflow and drop 84% of incoming chunks. Secondary bottlenecks include synchronous YOLO model loading occurring after the thread barrier (adding ~7s to startup) and duplicate YOLO instances consuming extra VRAM in multi-camera setups.

## Findings Table
| ID | Component | Finding | Impact | Effort to fix |
|---|---|---|---|---|
| P-1 | Audio Pipeline | Python list comprehension used for VAD tensor batching. | High | Low |
| P-2 | Startup / `run.py` | YOLO models load *after* the thread barrier, delaying video start. | High | Low |
| P-3 | Video Pipeline | Multiple cameras load duplicate YOLO instances into VRAM. | Medium | Medium |
| P-4 | Alert Composer | `cv2.VideoWriter` re-encodes frames sequentially on CPU. | Medium | High |

## Detailed Findings

### P-1: Audio Inference Python Loop Overhead
- **Current Behavior:** In `keyword_detector.py`'s `is_speech()` method, the audio tensor is sliced into 512-sample windows and evaluated via: `[vad_model(windows[i], 16000) for i in range(n_complete)]`.
- **Why it's slow:** This forces PyTorch to execute 15 separate inference passes per 500ms audio chunk, incurring massive Python interpreter and PyTorch dispatch overhead.
- **Suggestion:** Use PyTorch's native batching by passing the 2D tensor directly to the model (e.g., `vad_model(windows, 16000)`) if supported by the Silero version, or increase window size. Expected improvement: 3x-5x faster VAD, eliminating dropped chunks entirely.

### P-2: Sequential YOLO Loading Blocks Startup
- **Current Behavior:** In `run.py`, the video and audio threads wait at `barrier.wait()`. Immediately after, the video thread enters `with vp:`, which triggers `self._detector.load()`.
- **Why it's slow:** YOLO loading takes ~7 seconds. Because it happens *after* synchronization, the entire video pipeline stalls for 7 seconds while audio is already flowing, causing initial sync issues and a delayed first frame.
- **Suggestion:** Call `vp._detector.load()` explicitly in `run_video()` *before* hitting `barrier.wait()`. Expected improvement: The 7-second YOLO load will run in parallel with the 1.1s Whisper load, and both pipelines will start outputting frames instantly when the barrier releases.

### P-3: Duplicate YOLO Models in VRAM
- **Current Behavior:** Each `CameraStream` spawns a `VideoPipeline`, which creates a `HumanDetector` that instantiates a new `YOLO(model_name)`.
- **Why it's slow:** For $N$ cameras, the system loads $N$ copies of the YOLO weights into GPU memory, wasting 1-2 GB of VRAM per extra camera and increasing total startup time.
- **Suggestion:** Load a single global `YOLO` model and pass it into the pipelines by reference. Since `YOLO.predict()` in ultralytics operates asynchronously on the GPU, multiple cameras can query it without duplicating VRAM.

### P-4: CPU Video Encoding for Alerts
- **Current Behavior:** `AVAlertComposer._mux_and_save()` uses `cv2.VideoWriter` with the `mp4v` codec to encode raw frames before muxing with ffmpeg.
- **Why it's slow:** This forces a full software re-encode of hundreds of frames per alert, blocking one of the 3 worker threads for several seconds.
- **Suggestion:** If hardware encoding is available, change the FourCC to `avc1` or `h264` and configure OpenCV to use NVENC/QSV. Expected improvement: 5x faster alert generation.

## Quick Wins (implement in < 1 hour)
1. **Fix P-2 (Startup Latency):** Move the `load()` call in `run.py` to before the `barrier.wait()`.
2. **Fix P-1 (VAD Batching):** If native 2D batching fails in Silero VAD, increase `window_size` to 1024 or 2048 to halve the Python loop iterations, at a minor cost to temporal resolution.

## Medium Effort (1 day)
1. **Optimize VAD Loop:** Refactor the Silero VAD inference to utilize a proper batched forward pass or TorchScript compilation to completely remove Python overhead.
2. **Shared YOLO Instance:** Refactor `HumanDetector` to accept an existing `YOLO` instance rather than instantiating its own, managing concurrent access if needed.

## Architecture Changes (multi-day)
1. **Stream-Copy Alerts:** Instead of saving uncompressed JPEGs in memory and re-encoding them with `cv2.VideoWriter`, save the raw H.264 packets directly from the IP camera stream (using PyAV or ffmpeg) and split the file via keyframes. This would drop CPU usage for alerts to near zero.

## What NOT to change
- **`ffmpeg` in Alert Composer:** The `ffmpeg -c:v copy` command is just muxing an already-encoded MP4 with a WAV file. It takes milliseconds. Do not try to optimize this subprocess call.
- **FaceMesh Sync:** MediaPipe FaceMesh is CPU-heavy, but it runs asynchronously in a capped thread pool (`_face_executor`). It is correctly decoupled and does not block the 30 FPS video tracking loop.
- **Memory Growth:** The tracking extrapolator and re-id embeddings are properly pruned on student exit. The system is structurally safe from unbounded memory leaks.
