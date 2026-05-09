# Review: src/thaqib/api/routes/exams.py

Overall quality: Good

Refactoring effort: Medium

## Findings

1. Exam update can assign relationship fields incorrectly
   - Lines `96-98` blindly `setattr` update data.
   - If `hall_ids` or future relationship fields are added to `ExamSessionUpdate`, this will not correctly sync relationships.
   - Suggestion: explicitly handle scalar fields separately from relationship updates.

2. Assignment duplication is not checked
   - Lines `149-157` create an assignment without checking whether the same invigilator is already assigned to the session.
   - Suggestion: add a unique DB constraint on `(exam_session_id, invigilator_id)` and return a controlled 400.

3. Role model is inconsistent with comment
   - Line `134` says admin/referee, but line `131` uses `require_admin`.
   - Suggestion: align implementation and comment, or use `RequireRole(["admin", "referee"])`.

4. No date consistency validation
   - Lines `38-39` persist scheduled start/end without enforcing end after start.
   - Suggestion: add schema validation for scheduled and actual time ranges.

## What Works

- Hall existence is checked before creating an exam session at lines `29-33`.
- Assignment validates user existence and role at lines `141-147`.
