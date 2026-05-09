# Review: src/thaqib/api/routes/stream.py

Overall quality: Needs Improvement

Refactoring effort: High

## Findings

1. Stream control and media endpoints have no auth dependencies
   - Lines `608`, `619`, `630`, `641`, `648`, `666`, `673`, `682`, and `693` define reload, refresh, monitoring, status, feed, alerts, snapshot, video, and PDF endpoints without role checks.
   - Security impact: live camera feeds, alert snapshots, videos, and reports can be accessed or restarted by unauthenticated users.
   - Suggestion: add `Depends(get_current_active_user)` or role dependencies to dashboard endpoints; use signed expiring URLs only when sharing media is required.

2. One module owns too many responsibilities
   - Lines `68-108` define runtime state, lines `269-363` draw annotations, lines `379-532` run pipelines, lines `608-690` expose API endpoints, and lines `693-746` generate PDFs.
   - Maintainability impact: API routing, lifecycle management, rendering, alert persistence, file serving, and reporting are tightly coupled.
   - Suggestion: split into `stream_service`, `alert_store`, `media_store`, `stream_routes`, and `report_routes`.

3. In-memory alert state is not durable
   - Lines `105-108` keep alerts and camera states in process globals.
   - Line `420` truncates alerts to 50.
   - Impact: restart loses alert state; multiple workers will disagree.
   - Suggestion: persist alerts in the database and keep only runtime camera state in memory.

4. Path traversal guard misses root-directory file case
   - Lines `677` and `686` check `_ROOT_ALERTS_DIR not in filepath.parents`.
   - If a valid file were directly under `alerts/`, `filepath.parents` contains root; currently structured files are nested, but the helper is fragile.
   - Suggestion: use `filepath.is_relative_to(_ROOT_ALERTS_DIR)` on Python 3.9+ or compare `commonpath`.

5. Snapshot writes ignore failure
   - Line `373` calls `cv2.imwrite` without checking the boolean return value.
   - Suggestion: if it returns false, log and surface an alert persistence error.

6. Fixed performance numbers are hardcoded
   - Lines `455-459` set `target_fps = 12.0` and `max_stream_w = 1280`.
   - Suggestion: move these to settings and include them in performance tests.

## What Works

- The code downscales MJPEG output and uses JPEG quality controls at lines `476-493`, which is practical for browser performance.
- The path slugging and structured alert directories at lines `38-65` are a good start.
