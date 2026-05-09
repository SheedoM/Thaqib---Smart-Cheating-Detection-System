# Review: src/thaqib/db/models/exams.py

Overall quality: Good

Refactoring effort: Medium

## Findings

1. Status and assignment role are unconstrained
   - Lines `57` and `96` store raw strings.
   - Suggestion: add check constraints/enums.

2. No uniqueness on assignments
   - Lines `91-96` define assignment links without a unique constraint.
   - Suggestion: add a unique constraint on `(exam_session_id, invigilator_id)`.

3. Soft delete and cascades need policy clarity
   - `ExamSession` includes `SoftDeleteMixin` at line `39`, but relationships cascade delete events and alerts at lines `68-78`.
   - Suggestion: preserve historical detection events even when sessions are archived or soft-deleted.

## What Works

- The many-to-many hall/session table uses cascade foreign keys.
- Relationships are named clearly and map the core domain.
