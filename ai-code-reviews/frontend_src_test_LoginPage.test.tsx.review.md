# Review: frontend/src/test/LoginPage.test.tsx

Overall quality: Needs Improvement

Refactoring effort: Low

## Findings

1. Success test assertion is stale
   - Line `61` expects `window.alert` to be called.
   - Current `LoginPage` stores tokens and calls `onLoginSuccess` at `LoginPage.tsx:43-49`; it does not alert.
   - Result: `npm test -- --run` fails 1 of 5 tests.
   - Suggestion: render with a mocked `onLoginSuccess`, assert it is called, and assert tokens are written to localStorage.

2. Token response mock is incomplete
   - The success mock returns only `access_token`.
   - Current code also stores `data.refresh_token` at `LoginPage.tsx:44`.
   - Suggestion: include `refresh_token` in the mock to mirror the backend `Token` schema.

3. Test name describes an old behavior
   - The test title says "shows success alert on valid login".
   - Suggestion: rename to "stores tokens and notifies parent on valid login".

## What Works

- The file covers render, failed login, and successful login paths.
- It uses Testing Library interactions rather than implementation details for form input.
