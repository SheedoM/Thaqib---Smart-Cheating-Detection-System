# Audio-Video Synchronization & Latency Gap Analysis

This report analyzes how the Thaqib system synchronizes audio and video alerts, specifically focusing on the latency mismatch between the Video Pipeline and the Audio Pipeline, and how this causes the 0-second video bug.

## 1. Alert Dispatch & Video Frame Fetching
When an audio alert is triggered (either by VAD or Whisper keyword detection), the Audio Pipeline dispatches the alert via `_dispatch_audio_alert(alert)`. This immediately triggers the `on_audio_alert` callback in the `AVAlertComposer`.

The composer attempts to fetch the corresponding video frames from the `video_buffer` maintained by the Video Pipeline. It does this synchronously at the exact moment the audio pipeline decides the speech has ended. 

**Relevant Code:** `src/thaqib/av_alert_composer.py`, `_produce_audio_alert_video` method.

## 2. The Latency Gap (YOLO vs. VAD)
A significant latent time gap exists between the two pipelines:
- **Audio Pipeline (VAD/Whisper)**: Audio processing is extremely fast. If it's reading from a file, it operates much faster than real-time (unless artificially slowed down). It detects the end of speech almost instantly.
- **Video Pipeline (YOLO & Face Mesh)**: Video processing is highly computationally expensive. YOLO object detection and MediaPipe face mesh processing cause the Video Pipeline to lag severely behind the Audio Pipeline.

Because the Audio Pipeline dispatches the alert the moment the audio event is detected, the Video Pipeline is usually still processing frames from the *past*. The video buffer simply hasn't received the frames corresponding to the audio event's timestamps yet.

## 3. The Window Clamping Bug (0-Second Video)
In `AVAlertComposer._produce_audio_alert_video` (lines ~260-272), the code attempts to extract a window of video frames surrounding the audio event, adding padding before and after:

```python
        # Expand window for audio alerts
        window_start = timestamp_start - AUDIO_ALERT_PAD_BEFORE_S
        window_end = timestamp_end + AUDIO_ALERT_PAD_AFTER_S
```

However, because the video pipeline is lagging behind, the `video_buffer`'s newest frame (`newest_ts`) is often in the past, entirely missing the `window_end` timestamp. To prevent out-of-bounds errors, the composer clamps the window:

```python
            oldest_ts = buffer_snapshot[0][0]
            newest_ts = buffer_snapshot[-1][0]
            
            # Clamp to buffer bounds
            window_start = max(window_start, oldest_ts)
            window_end = min(window_end, newest_ts)
```

**The Fatal Flaw:**
If the video pipeline lag is severe, `newest_ts` might be smaller than `window_start`.
For example, if the audio event occurred at `T=900.0`, but the video pipeline is currently only at `T=850.0`:
- `window_start` = `899.0` (which is clamped to `max(899.0, oldest_ts) -> 899.0`)
- `window_end` = `901.0` (which is clamped to `min(901.0, 850.0) -> 850.0`)

This results in a reversed window: `[899.0, 850.0]`. Since `start > end`, no frames are extracted, resulting in a 0-second video or the alert being dropped entirely.

## Conclusion
Yes, a severe synchronization gap exists. The system incorrectly assumes that when the Audio Pipeline finishes processing an event, the Video Pipeline has also finished processing the same timestamps. 

**Potential Mitigations:**
1. **Asynchronous Composer Queuing:** The `AVAlertComposer` should not fetch frames immediately. It should queue the alert and wait until `video_buffer.newest_ts >= window_end` before extracting frames.
2. **Audio Pipeline Delay (`clip_sec_after`)**: The Audio Pipeline has a built-in `_pending_alerts` mechanism (lines ~1507-1520 in `src/thaqib/audio/pipeline.py`). If `audio_alert_clip_after` is configured > 0, it defers dispatching the alert until future audio chunks arrive. While this gives the video pipeline *some* time to catch up, it is not a foolproof synchronization method.
