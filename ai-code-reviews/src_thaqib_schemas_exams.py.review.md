# Review: src/thaqib/schemas/exams.py

Overall quality: Good

Refactoring effort: Medium

## Findings

1. Exam status and assignment role are raw strings
   - `AssignmentBase.role` is a plain string at line `9`.
   - `ExamSessionBase.status` is a plain string at line `26`.
   - Suggestion: use `Literal` or enums for `primary/secondary` and `scheduled/active/completed/cancelled`.

2. Date range validation is missing
   - `scheduled_start` and `scheduled_end` are declared at lines `24-25`.
   - Suggestion: validate `scheduled_end > scheduled_start`; similarly validate actual start/end in updates.

3. `configuration` is unrestricted JSON
   - Line `28` accepts arbitrary dicts.
   - Suggestion: define a nested configuration schema for known exam/pipeline controls.

## What Works

- Separate create/update/response schemas exist.
- Hall assignment is represented through `hall_ids`, which is a clean request shape for many-to-many setup.
