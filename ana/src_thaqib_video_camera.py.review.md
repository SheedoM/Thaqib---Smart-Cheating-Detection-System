# Review: src/thaqib/video/camera.py

Overall quality: Good

Refactoring effort: Medium

## Findings

1. Reconnection timing is hardcoded
   - Lines `148` and `166` sleep for 2 seconds; line `233` polls every 0.01 seconds.
   - Suggestion: move reconnect delay and read polling interval to settings.

2. Camera source logging may expose credentials
   - Line `96` logs `self.source`.
   - Security impact: RTSP URLs often include usernames/passwords.
   - Suggestion: redact credentials before logging URLs.

3. OpenCV capture lifecycle is thread-sensitive
   - Lines `136-206` manage capture in an update loop.
   - Suggestion: add tests with a fake capture object for EOF, reconnect, and stop behavior.

## What Works

- The class provides `FrameData`, `read()`, and `frames()` abstractions that keep OpenCV out of most callers.
- It handles EOF differently from transient live-camera read failures.
