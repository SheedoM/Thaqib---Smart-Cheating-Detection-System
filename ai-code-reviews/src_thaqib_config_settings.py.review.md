# Review: src/thaqib/config/settings.py

Overall quality: Needs Improvement

Refactoring effort: Medium

## Findings

1. Unsafe production defaults
   - Lines `25-26` default to `app_env="development"` and `debug=True`.
   - Line `78` defaults `secret_key` to a static development value.
   - Security impact: a deployed instance that forgets environment variables will issue JWTs signed with a known key.
   - Suggestion: use `secret_key: str | None = None`, validate it in a model validator, and fail startup when `APP_ENV=production` and the key is missing or weak.

2. Active environment can break tests
   - Line `65` restricts `log_format` to `csv` or `parquet`.
   - `pytest -q` failed because the active environment provided `LOG_FORMAT=json`.
   - Suggestion: isolate tests from `.env` by setting `ENV_FILE` or test env vars before importing `src.thaqib.main`, or add a `testing` settings profile.

3. Environment example and runtime defaults drift
   - Line `37` defaults `yolo_model` to `models/yolo11m.pt`, while `.env.example:43` uses `yolov8s`.
   - Line `38` defaults detection confidence to `0.15`, while `.env.example:46` uses `0.5`.
   - Suggestion: make `.env.example` mirror code defaults or document why demo defaults differ.

4. Magic performance thresholds are spread through settings without validation
   - Lines `31-60` contain many numeric controls but no range constraints.
   - Suggestion: use `Field(gt=0)`, `Field(ge=0, le=1)`, and validators for values such as FPS, confidence, worker count, and thresholds.

## What Works

- Centralized settings through `pydantic-settings` are a solid foundation.
- `camera_source_parsed` at lines `86-92` keeps camera parsing out of callers.
