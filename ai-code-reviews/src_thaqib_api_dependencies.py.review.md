# Review: src/thaqib/api/dependencies.py

Overall quality: Good

Refactoring effort: Low

## Findings

1. Broad exception handling hides token failure type
   - Line `26` catches every exception, including coding errors.
   - Suggestion: catch `jwt.PyJWTError` and `AttributeError`/validation failures explicitly, then log unexpected exceptions separately.

2. Logging stack traces for routine auth failures may be noisy
   - Line `28` logs every failed token validation with `logging.exception`.
   - Security/performance impact: scanners or expired tokens can flood logs with stack traces.
   - Suggestion: log at `warning` without stack for expected JWT errors; keep stack traces for unexpected exceptions.

3. Role checks use raw strings
   - Lines `43-50` compare raw role strings.
   - Suggestion: introduce a `UserRole` enum used by schemas, models, and dependencies.

4. Inactive user status returns 400
   - Lines `36-38` return `400` for inactive users.
   - Suggestion: use `403` so clients can distinguish validation errors from authorization denial.

## What Works

- The `RequireRole` dependency is a clean, reusable pattern.
- The dependency validates access-token type before loading the user.
