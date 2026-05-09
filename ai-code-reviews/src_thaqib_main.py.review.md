# Review: src/thaqib/main.py

Overall quality: Good

Refactoring effort: Low

## Findings

1. CORS origins are hardcoded
   - Lines `47-51` hardcode local frontend origins.
   - Suggestion: move allowed origins to `Settings`, use a comma-separated env var, and fail closed in production.

2. HSTS is sent unconditionally
   - Line `41` sets `Strict-Transport-Security` even during local HTTP development.
   - Suggestion: only send HSTS when `app_env == "production"` and TLS is terminated correctly.

3. Security header policy may break legitimate media needs
   - Line `42` sets `default-src 'self'` and `object-src 'none'`.
   - The backend serves MJPEG/video/PDF endpoints, so this policy should be tested against dashboard/report use cases.
   - Suggestion: define CSP centrally and cover stream/report pages in integration tests.

4. Stream manager starts with the app lifecycle
   - Lines `13-19` start/stop monitoring streams during app lifespan.
   - Performance impact: importing or starting the API can open cameras and heavy models.
   - Suggestion: gate stream startup behind a setting or an explicit admin action for test and API-only deployments.

## What Works

- Lifespan management is the right FastAPI pattern.
- Router inclusion is clear and discoverable at lines `61-70`.
