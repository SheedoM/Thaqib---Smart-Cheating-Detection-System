# Review: src/thaqib/api/routes/auth.py

Overall quality: Good

Refactoring effort: Medium

## Findings

1. Refresh token is passed as a query parameter
   - Line `50` declares `refresh_token: str`, so FastAPI treats it as a query parameter.
   - Security impact: refresh tokens can appear in logs, browser history, proxies, and analytics.
   - Suggestion: accept the refresh token in an HTTP-only secure cookie or a JSON body.

2. Refresh rotation is incomplete
   - Lines `71-73` issue a new refresh token but do not revoke the previous one.
   - Suggestion: store hashed refresh-token IDs and invalidate the old token when a new one is minted.

3. Debug endpoint exposes user attributes
   - Lines `91-106` define `/me-debug`.
   - Suggestion: remove it from production or guard it behind `settings.debug`.

4. Login response encourages frontend token storage
   - Lines `40-44` return both tokens in JSON.
   - Suggestion: return access token in JSON only if needed, but prefer secure cookies for refresh tokens.

## What Works

- Rate limiting on login and refresh at lines `16` and `47` is a good baseline.
- The route validates inactive users before token issuance at lines `32-36`.
