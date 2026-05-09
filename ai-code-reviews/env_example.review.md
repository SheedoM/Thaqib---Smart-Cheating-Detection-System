# Review: .env.example

Overall quality: Good

Refactoring effort: Low

## Findings

1. Example defaults drift from code defaults
   - `.env.example:43` uses `YOLO_MODEL=yolov8s`, while `settings.py:37` defaults to `models/yolo11m.pt`.
   - `.env.example:46` uses `DETECTION_CONFIDENCE=0.5`, while `settings.py:38` defaults to `0.15`.
   - Suggestion: align defaults or clearly label demo vs production values.

2. Missing security settings
   - Lines `97-112` include server/database/websocket settings, but not `SECRET_KEY`, token expiries, or allowed CORS origins.
   - Suggestion: add commented production-required security variables with guidance.

3. Example database URL includes placeholder password
   - Line `107` is commented, so it is not a secret leak, but it should be clearly marked as placeholder only.
   - Suggestion: add comments explaining secret management and never committing real `.env`.

## What Works

- The example is well organized by domain.
- Camera source examples are practical for webcam, RTSP, and HTTP simulator modes.
