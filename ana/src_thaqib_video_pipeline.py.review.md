# Review: src/thaqib/video/pipeline.py

Overall quality: Needs Improvement

Refactoring effort: High

## Findings

1. Pipeline reaches into tracker private internals
   - Lines `428-431` mutate `_smoothed_bboxes`, `_match_counts`, `_locked_ids`, and `_track_labels`.
   - Maintainability impact: tracker invariants are spread across modules.
   - Suggestion: add a public `ObjectTracker.remove_tracks(expired_ids)` method.

2. Alert writer assumes every buffered frame is a tuple
   - Lines `1056-1064` iterate `for raw_frame, tid in frames`.
   - Earlier comments at lines `1009-1016` still handle both tuples and raw ndarrays, and `stop()` at lines `293-296` snapshots `state.recording_buffer` directly.
   - Risk: if any raw ndarray reaches the writer, unpacking will fail.
   - Suggestion: normalize frame-buffer item type with a dataclass such as `AlertFrame(frame, track_id)`.

3. Process pool is created during pipeline construction
   - Lines `143-146` create a multiprocessing pool before `start()`.
   - Performance/operability impact: simply constructing a pipeline allocates worker processes.
   - Suggestion: lazily create the pool in `start()` and handle creation failure explicitly.

4. Broad exception swallowing hides dropped detection results
   - Lines `238-239`, `314-315`, `320-321`, and `630-631` ignore exceptions.
   - Suggestion: log at least warning/debug with enough context and count recurring failures.

5. Archive and alert output paths are hardcoded
   - Lines `957-969` write to `archive/`; lines `1003-1041` write to `alerts/`.
   - Suggestion: use `settings.data_dir` or dedicated `archive_dir`/`alerts_dir` settings.

6. Magic frame counts assume 30 FPS
   - Lines `687`, `699`, and `993` assume 60 frames is 2 seconds and videos are 30 FPS.
   - Suggestion: compute post-buffer frame counts from measured or configured FPS.

## What Works

- The pipeline already uses a detection thread, shared memory, face worker pool, and bounded archive queue, which shows strong performance awareness.
- Reusing a single annotated frame for display/archive at lines `753-764` is a good optimization.
