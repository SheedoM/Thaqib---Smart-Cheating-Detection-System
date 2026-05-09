# Review: src/thaqib/api/routes/institutions.py

Overall quality: Good

Refactoring effort: Low

## Findings

1. Update endpoint can overwrite unique code without collision handling
   - Lines `89-91` apply all update fields directly.
   - Suggestion: if `code` is mutable, check for duplicate code before commit and return a controlled 400 instead of a DB integrity error.

2. Deletion is hard delete despite soft-delete mixin
   - Lines `113-114` delete the institution row.
   - Model `src/thaqib/db/models/infrastructure.py:21` includes `SoftDeleteMixin`.
   - Suggestion: either implement soft delete in route/service logic or remove the mixin from models where hard delete is intended.

3. Pagination lacks validation
   - Lines `48-49` have unbounded `skip`/`limit`.
   - Suggestion: use `Query(0, ge=0)` and `Query(100, ge=1, le=500)`.

## What Works

- The route checks duplicate institution code before create at lines `28-33`.
- Admin role enforcement is consistently applied.
