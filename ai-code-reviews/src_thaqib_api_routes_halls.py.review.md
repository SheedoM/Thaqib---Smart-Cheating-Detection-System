# Review: src/thaqib/api/routes/halls.py

Overall quality: Good

Refactoring effort: Medium

## Findings

1. Frontend sends fields not represented by the schema
   - `frontend/src/components/HallsTab.tsx:224` and `HallsTab.tsx:243` send `image`, but the backend hall schema does not define it.
   - Suggestion: either add an image/logo field to `HallCreate/HallUpdate` and model storage, or remove the frontend payload.

2. Status values are raw strings
   - Lines `49-50` write `status` from request data.
   - `src/thaqib/schemas/infrastructure.py:13` defaults to `not_ready`, while frontend sends `active` at `HallsTab.tsx:225`, and stream manager expects `ready` at `stream.py:257`.
   - Suggestion: define a `HallStatus` enum and align frontend options, schemas, and stream activation rules.

3. Hard delete despite soft-delete mixin
   - Lines `129-130` hard-delete halls.
   - Suggestion: implement soft-delete or explicitly document destructive delete behavior.

## What Works

- Create checks parent institution existence and duplicate hall name within institution.
- Admin role checks are applied consistently.
