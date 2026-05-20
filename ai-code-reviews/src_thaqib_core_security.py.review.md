# Review: src/thaqib/core/security.py

Overall quality: Good

Refactoring effort: Medium

## Findings

1. Unused import
   - Line `1` imports `os` but never uses it.
   - Suggestion: remove it and enforce Ruff in CI.

2. Token decode contract is too loose
   - Line `41` annotates `decode_token` as returning `dict`, but line `49` returns `None`.
   - Suggestion: annotate `dict | None` and make callers handle a typed result.

3. Refresh tokens are stateless and cannot be revoked
   - Lines `32-39` create refresh tokens without `jti`, storage, rotation tracking, or revocation.
   - Security impact: stolen refresh tokens remain valid until expiry.
   - Suggestion: add `jti`, persist hashed refresh-token IDs, rotate on refresh, and revoke previous tokens.

4. JWT secret validation is not enforced here
   - Lines `29` and `38` sign with whatever `settings.secret_key` contains.
   - Suggestion: rely on settings validation so development defaults cannot reach production.

## What Works

- Bcrypt through `passlib` is appropriate.
- Access and refresh tokens are separated by a `type` claim at lines `28` and `37`.
