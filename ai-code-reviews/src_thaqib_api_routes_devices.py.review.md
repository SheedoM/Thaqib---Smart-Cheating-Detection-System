# Review: src/thaqib/api/routes/devices.py

Overall quality: Needs Improvement

Refactoring effort: Medium

## Findings

1. The route mutates ORM datetime fields into strings
   - Lines `57-60`, `80-82`, `98-99`, `126-127`, and `148-149` assign `isoformat()` back to `device.last_health_check`.
   - Maintainability impact: response formatting mutates the SQLAlchemy object and can confuse later ORM/session behavior.
   - Suggestion: let Pydantic serialize datetimes, or return a DTO/dict without modifying the ORM instance.

2. `stream_url` nullability conflicts with frontend behavior
   - Model line `src/thaqib/db/models/infrastructure.py:75` marks `stream_url` non-null.
   - Schema line `src/thaqib/schemas/infrastructure.py:53` requires `stream_url`.
   - Frontend sends `stream_url: null` for microphones at `frontend/src/components/HallsTab.tsx:268`.
   - Suggestion: make stream URL optional for non-camera devices or split camera/microphone schemas.

3. IP address validation is too permissive
   - `src/thaqib/schemas/infrastructure.py:52` accepts `999.999.999.999`.
   - Suggestion: use `pydantic` `IPvAnyAddress` or a stricter validator.

4. Hard delete despite soft-delete mixin
   - Lines `145-146` delete device rows.
   - Suggestion: use `deleted_at` or remove soft-delete from the model.

## What Works

- Duplicate identifier within a hall is checked at lines `32-40`.
- Parent hall existence is checked before create.
