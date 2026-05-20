# Review: src/thaqib/db/models/infrastructure.py

Overall quality: Good

Refactoring effort: Medium

## Findings

1. Soft delete mixin is not honored by routes
   - `Institution`, `Hall`, and `Device` include `SoftDeleteMixin` at lines `21`, `39`, and `65`.
   - Current routes hard-delete rows.
   - Suggestion: implement soft-delete query filters and update delete routes, or remove the mixin.

2. Device stream URL is non-null for all device types
   - Line `75` marks `stream_url` nullable false.
   - This conflicts with microphones and other devices.
   - Suggestion: allow null stream URLs or split device subtype tables/schemas.

3. Missing uniqueness constraints
   - Line `73` stores device identifier but does not enforce uniqueness per hall at the database level.
   - Route-level checks can race.
   - Suggestion: add a composite unique constraint on `(hall_id, identifier)` and likely `(institution_id, name)` for halls.

4. Status values are not constrained
   - Lines `51` and `79` store status as arbitrary strings.
   - Suggestion: use DB enum/check constraints or application enums with validation.

## What Works

- Relationships and cascades are clear.
- `image` exists in the model at line `50`, matching hall schema/frontend intent.
