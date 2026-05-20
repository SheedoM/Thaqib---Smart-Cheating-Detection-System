# Review: src/thaqib/schemas/users.py

Overall quality: Good

Refactoring effort: Low

## Findings

1. `UserUpdate.role` and `UserUpdate.status` lack validation
   - Lines `28-29` are plain optional strings, unlike `UserBase.role` at line `19`.
   - Suggestion: reuse enums or the same regex constraints for update schemas.

2. Token schema exposes refresh token to browser clients
   - Lines `6-9` include `refresh_token` in the JSON schema.
   - Security impact: frontend stores it in localStorage.
   - Suggestion: move refresh token transport to secure HTTP-only cookie and remove it from normal JSON response where possible.

3. Password validation checks only length
   - Line `22` enforces length but not complexity or breached-password policy.
   - Suggestion: add server-side password policy appropriate for admin/invigilator accounts.

## What Works

- Username and role creation validation are explicit at lines `16` and `19`.
- `EmailStr` is used for create/base email validation.
