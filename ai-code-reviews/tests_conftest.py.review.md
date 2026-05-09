# Review: tests/conftest.py

Overall quality: Needs Improvement

Refactoring effort: Medium

## Findings

1. Tests import the app before isolating settings
   - Line `11` imports `app`, which loads settings immediately through database setup.
   - `pytest -q` failed because the active environment had `LOG_FORMAT=json`, conflicting with `Settings.log_format`.
   - Suggestion: set deterministic test env vars before importing app, or provide a test settings fixture/module.

2. Session-scoped schema with per-test transactions can leak state
   - Lines `28-32` create metadata once; lines `36-42` use transaction rollback.
   - This is generally fine for SQLite, but app lifespan side effects can still run during `TestClient`.
   - Suggestion: disable stream manager startup in tests through settings or dependency injection.

3. Password fixture values are duplicated
   - Lines `70`, `85`, `99`, and `111` repeat `"securepassword"`.
   - Suggestion: define `TEST_PASSWORD` constant.

4. No test client auth helper for non-admin roles beyond invigilator
   - Lines `96-117` only provide admin and invigilator token headers.
   - Suggestion: add role-parametrized user/token fixtures.

## What Works

- In-memory SQLite with `StaticPool` is appropriate for fast API tests.
- Dependency override for `get_db` is the standard FastAPI pattern.
