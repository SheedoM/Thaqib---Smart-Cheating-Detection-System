# Review: src/thaqib/db/models/users.py

Overall quality: Good

Refactoring effort: Medium

## Findings

1. Role and status are unconstrained strings
   - Lines `36` and `39` store `role` and `status` as strings.
   - Suggestion: add check constraints or SQLAlchemy enums aligned with Pydantic schemas.

2. Email is not unique
   - Line `34` stores email with `nullable=False` but no unique constraint.
   - Suggestion: decide product behavior; if email is a login/recovery identity, make it unique.

3. User delete semantics conflict with assignment history
   - Line `44` cascades assignments from user deletion.
   - Risk: deleting users can remove historical invigilation records.
   - Suggestion: prefer soft delete/deactivation for users and preserve assignment history.

## What Works

- Username is unique at line `31`.
- Password hash is stored separately from user schemas and not exposed in `UserResponse`.
