# Limits, GPU Usage, and Performance Bottlenecks Report

## Section 1: Hard Limits — Student Count

### Face Mesh Processing
- **Max Students**: There is **no hard limit** (`MAX_STUDENTS`) on the number of students that get face mesh processing.
- **Worker Limit**: The `ThreadPoolExecutor` for face mesh is bounded by `max_workers = min(settings.face_mesh_workers, os.cpu_count() or 4)` (default 4).
- **Execution**: All tracked and selected students are submitted to the face mesh executor *every single frame*. There is no frame-skipping or sampling logic.
- **Risk**: If there are 20 students, the main thread submits 20 face mesh jobs per frame. At 30 FPS, that is 600 jobs/sec. If 4 workers take ~10ms per job, they can only clear 400 jobs/sec. The `_pending_fm_futures` queue will silently grow infinitely, causing massive memory bloat and delaying cheating alerts by minutes.

### Student Registry
- **Purge Limit**: The `GlobalStudentRegistry` keeps track of *all* unique IDs assigned by BoT-SORT. Lost tracks are kept for 3.0 seconds before being purged. There is no hard limit on the total number of entries in the registry.

## Section 2: GPU vs. CPU Usage Map

### GPU Bound
- **Human Detection**: Ultralytics YOLO (`HumanDetector` in `detector.py`) runs on the device specified by settings (GPU).
- **Tools Detection**: Ultralytics YOLO (`ToolsDetector` in `tools_detector.py`) runs on GPU.

### CPU Bound
- **Face Mesh**: MediaPipe `FaceLandmarker` runs on the CPU (`IMAGE` mode) via the `ThreadPoolExecutor`.
- **Face ReID**: Runs entirely on the CPU using Numpy math (Procrustes normalization + 75-D dot products).
- **Object Tracking (BoT-SORT)**: Runs on the CPU. The ReID component is disabled (`with_reid=False`), and Camera Motion Compensation (CMC) uses OpenCV's `calcOpticalFlowPyrLK` which is CPU-executed.
- **Silero VAD**: Forced to CPU (`self._vad_model = model.cpu()`) because the transfer overhead to GPU exceeds inference time.
- **Whisper STT**: Will run on GPU if available, but falls back to CPU INT8 if CUDA is unavailable or VRAM is exhausted.
- **Audio Preprocessing & Discriminator**: HPF, Noise Reduction, AGC, and Global/Local discrimination run purely on CPU using Numpy.
- **Frame Buffering**: OpenCV `cv2.imencode` (JPEG compression) and `cv2.imdecode` run synchronously on the CPU.
- **Video Muxing**: `ffmpeg` sub-processes for assembling final alert clips run on the CPU.

## Section 3: Bottleneck Analysis

### Audio Pipeline Critical Path
1. **Source Read** -> Synchronous pacing to real-time.
2. **Preprocessing & Discriminator** -> Synchronous numpy array math per chunk.
3. **VAD Inference** -> Background thread (`_inference_worker`). Before the P-1 fix, this was sequentially running `is_speech()` on each mic, causing the inference queue to fill and drop 84% of chunks. With batching, this is resolved, but it remains CPU-intensive.
4. **Whisper STT** -> Separate worker thread. If Whisper falls back to CPU, it will heavily contest with Face Mesh for CPU cycles.

### Video Pipeline Critical Path
1. **Tracker Update**: BoT-SORT updates run *synchronously* on the main thread for every frame. The CMC (Optical Flow) step is a significant CPU blocking operation.
2. **JPEG Encoding**: Every frame is JPEG-encoded (`cv2.imencode`) synchronously on the main thread to populate the `_global_frame_buffer`.
3. **Face Mesh Overload**: Submitting N students to the ThreadPoolExecutor every frame without dropping stale futures creates a massive CPU backlog.
4. **Alert Video Rendering**: The async writers (`_save_alert_video_async`) decode JPEGs, draw heavy OpenCV overlays (bounding boxes, text), and re-encode using `cv2.VideoWriter`. This places massive burst loads on the CPU when multiple students cheat simultaneously.

## Section 4: Multi-Camera Scaling Constraints

### VRAM Bloat (Isolated YOLO Instances)
- Each `VideoPipeline` instantiates its own `HumanDetector` and `ToolsDetector`.
- **Constraint**: Running 5 cameras means 10 separate YOLO models are loaded into GPU VRAM simultaneously. This will easily cause CUDA Out-Of-Memory (OOM) errors on consumer GPUs.

### GPU Contention
- Since Ultralytics YOLO is not thread-safe for shared instances, the current design uses separate threads calling `.predict()` on separate models simultaneously. This causes CUDA stream contention and context-switching overhead, drastically reducing GPU throughput compared to batching frames from all 5 cameras into a single inference call.

### Thread Bloat
- A single camera spawns: 1 camera reader, 1 detection worker, 4 face mesh workers, 1 archive writer, 4 alert writers, plus audio threads (VAD, Whisper, Monitor).
- **Constraint**: 5 cameras will spawn ~60-80 threads. Python's GIL will severely thrash during the non-C++ portions of the pipeline (like the tracker and registry updates).

## Section 5: Optimization Suggestions (Quick Wins P-3 & P-4)

### Priority 3: Face Mesh Frequency Capping
**Problem**: Submitting all students every frame overwhelms the CPU executor.
**Fix**: Introduce frame-skipping for Face Mesh. Only run Face Mesh every 3rd or 5th frame per student, or only run it for students who are currently marked as looking away. Alternatively, bound the `_pending_fm_futures` queue to drop old requests instead of infinitely growing.

### Priority 4: Shared YOLO Inference Manager
**Problem**: 10 YOLO models in VRAM for 5 cameras causes OOM and CUDA thrashing.
**Fix**: Create a global `DetectionManager` singleton. Instead of `_detection_worker` running `.predict()`, it submits frames to the `DetectionManager`. The manager batches frames from all active cameras into a *single* tensor, runs one YOLO `.predict()` call, and distributes the results back to the respective pipelines. This cuts VRAM usage to just 2 models total and maximizes GPU tensor core utilization.
