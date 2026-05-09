# Review: src/thaqib/api/routes/users.py

Overall quality: Good

Refactoring effort: Medium

## Findings

1. Update endpoint can write unsafe fields directly
   - Lines `106-108` apply every provided field with `setattr`.
   - `UserUpdate` currently restricts fields, but this pattern becomes risky as schemas evolve.
   - Suggestion: explicitly assign allowed fields and handle password changes through a dedicated endpoint.

2. No email uniqueness check
   - Lines `34-39` check username only.
   - Database model line `src/thaqib/db/models/users.py:34` does not mark email unique.
   - Suggestion: decide whether email is unique. If yes, enforce it in both DB and route.

3. Deleting users is hard delete
   - Lines `130-131` delete the row even though `User` mixes in soft-delete fields.
   - Suggestion: either use `deleted_at` consistently or remove `SoftDeleteMixin` from models that are hard-deleted.

4. Pagination bounds are not validated
   - Lines `59-60` expose `skip` and `limit` without limits.
   - Suggestion: use FastAPI `Query` constraints.

## What Works

- Admin-only dependency is consistently used on CRUD routes.
- Passwords are hashed before storage at line `47`.
