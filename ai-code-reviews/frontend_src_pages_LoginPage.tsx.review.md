# Review: frontend/src/pages/LoginPage.tsx

Overall quality: Needs Improvement

Refactoring effort: Medium

## Findings

1. Tokens are stored in localStorage
   - Lines `43-44` store access and refresh tokens in `localStorage`.
   - Security impact: XSS can steal long-lived refresh tokens.
   - Suggestion: store refresh tokens in secure HTTP-only cookies and keep access tokens in memory where possible.

2. Successful login logs token payload
   - Line `46` logs the full login response.
   - Security impact: tokens can end up in browser logs or shared screenshots.
   - Suggestion: remove the log or log only non-sensitive success metadata in development.

3. "Remember me" and "forgot password" are present but nonfunctional
   - Lines `95-102` render controls that do not change behavior.
   - Suggestion: either implement the flows or remove/disable them until supported.

4. Test expectation is stale
   - Frontend test failed at `frontend/src/test/LoginPage.test.tsx:61`, expecting an alert after successful login.
   - Current code calls `onLoginSuccess` at lines `47-49` instead.
   - Suggestion: update the test to assert callback invocation and token storage, not `window.alert`.

## What Works

- Login uses `application/x-www-form-urlencoded`, matching FastAPI OAuth2 form expectations.
- Error message state is clear and user-facing.
