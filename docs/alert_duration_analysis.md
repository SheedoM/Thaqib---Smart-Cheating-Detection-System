# Alert Duration Issue: 0-Second Videos & Reversed Timestamps

## The Problem

You reported that mic-triggered alerts produce videos with a duration of ~0 seconds (only a few frames), despite the system being configured to pad 1 second before and 1 second after the event.

Additionally, the logs show a warning with reversed timestamps:
`WARNING: No video frames found for audio alert window [906.2, 849.7] in camera cam0. Buffer oldest=20.8, newest=849.7.`

## Root Cause Analysis

This issue is caused by a **synchronization and latency mismatch** between the fast Audio Pipeline and the slower Video Pipeline, combined with how the AVAlertComposer handles future timestamps.

### 1. The "Future Window" Problem
When an audio alert fires at time `T` (e.g., `T = 200.0s`), the composer immediately tries to fetch video frames for the window `[199.0, 201.0]`. 
However, because it fetches the frames *instantly*, the video buffer has not yet reached `201.0`. The `newest_ts` in the video buffer is at best `200.0`. 
The composer clamps the window end: `window_end = min(201.0, newest_ts)`. 
This guarantees the "1 second after" is always missing. 

### 2. The Video Latency Lag (The 0-Second / Reversed Timestamp Bug)
The Video Pipeline (which runs YOLO and face mesh) is naturally slower and lags behind the Audio Pipeline. 
If the audio pipeline detects speech at `T = 907.2`, but the video pipeline is lagging behind and has only processed up to `T = 849.7`, the video buffer's `newest_ts` is `849.7`.

The composer calculates the target window:
- `window_start = 907.2 - 1.0 = 906.2`
- `window_end = 907.2 + 1.0 = 908.2`

It then clamps to the buffer bounds:
- `window_start = max(906.2, oldest_ts) -> 906.2`
- `window_end = min(908.2, 849.7) -> 849.7`

This results in the reversed window `[906.2, 849.7]`. Because `start > end`, 0 frames are found, and the alert fails or produces a completely empty video. 
Even when the lag is minor (e.g., video is at `906.3`), the clamped window becomes `[906.2, 906.3]`, resulting in a ~0.1-second video (a few frames).

## Proposed Fixes

To fix this, the system must wait for the video pipeline to catch up to `window_end` before attempting to mux the video.

### Fix Option 1: Asynchronous Composer Waiting (Recommended)
Modify `AVAlertComposer` so that `on_audio_alert` does not fetch frames immediately. Instead, it should place the alert in a queue. A background thread in the composer should monitor `newest_ts` of the video buffer, and only extract frames and run ffmpeg once `newest_ts >= timestamp_end + AUDIO_ALERT_PAD_AFTER_S`.

### Fix Option 2: Enable Audio Pipeline `_clip_sec_after`
The Audio Pipeline has a built-in mechanism for this (`_pending_alerts`). If the configuration setting `audio_alert_clip_after` is set to `1.0`, the audio pipeline will hold the alert and wait until 1.0 second of *future* audio chunks arrive before dispatching it to the composer. This delay naturally gives the video pipeline time to catch up, though it may still fail if the video pipeline lags behind by more than 1 second.
