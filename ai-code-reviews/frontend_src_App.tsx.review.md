# Review: frontend/src/App.tsx

Overall quality: Good

Refactoring effort: Medium

## Findings

1. Any token in localStorage grants dashboard view
   - Lines `17-20` skip setup/login if a token exists, without validating expiry or `/api/auth/me`.
   - Suggestion: call `/api/auth/me` on startup and fall back to login if the token is invalid.

2. Setup fallback may expose setup UI during backend outage
   - Lines `30` and `35` set `view` to `setup` on errors.
   - Risk: users may attempt installation when the problem is connectivity, not an uninstalled system.
   - Suggestion: show a connection error state instead of defaulting to setup.

3. Large auth/setup layout lives in the app root
   - Lines `57-135` mix routing state and banner layout.
   - Suggestion: extract `AuthShell` or route-level components.

## What Works

- The `ViewState` union at line `8` keeps app state explicit.
- Logout clears both access and refresh tokens at lines `47-48`.
