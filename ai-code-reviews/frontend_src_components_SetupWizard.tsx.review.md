# Review: frontend/src/components/SetupWizard.tsx

Overall quality: Needs Improvement

Refactoring effort: Medium

## Findings

1. Generated password is displayed in the UI
   - Lines `100-121` show generated credentials, including password at line `117`.
   - Combined with backend fixed password at `src/thaqib/api/routes/setup.py:64`, this is high risk.
   - Suggestion: use a one-time random password, force rotation on first login, and warn that it will only be shown once.

2. Logo upload is not actually uploaded
   - Lines `52-56` send only `logo_file.name` as `logo_url`.
   - Suggestion: either implement multipart upload or remove the file picker until backend storage exists.

3. Object URL is not revoked
   - Line `33` creates an object URL for preview.
   - Suggestion: call `URL.revokeObjectURL` when the selected file changes or component unmounts.

4. Clipboard failures are ignored
   - Lines `42-44` call `navigator.clipboard.writeText` without error handling.
   - Suggestion: make it async and show copy success/failure state.

## What Works

- The setup form is simple and state transitions are easy to follow.
- The component stores generated credentials only after a successful response.
