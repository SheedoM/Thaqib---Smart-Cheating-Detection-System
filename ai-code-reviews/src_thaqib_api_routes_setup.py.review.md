# Review: src/thaqib/api/routes/setup.py

Overall quality: Needs Improvement

Refactoring effort: Medium

## Findings

1. Fixed default admin password
   - Line `64` sets `default_password = "Admin_Password123!"`.
   - Line `88` returns it to the client.
   - Security impact: every fresh installation starts with the same admin credential.
   - Suggestion: generate a random one-time password, store only its hash, mark the user as `must_change_password`, and never reuse the value.

2. Race condition in first-install check
   - Lines `43-46` count rows and then create rows without a transaction-level lock or uniqueness guarantee around setup.
   - Suggestion: enforce unique root setup state or use a serializable transaction so concurrent install requests cannot both pass.

3. Setup endpoint has no authentication or deployment gate
   - Lines `31-37` expose install publicly until any institution/user exists.
   - Suggestion: require an installation token from environment or bind setup to local/admin-only deployment flow.

4. Username/email generation is too weak
   - Lines `61-62` derive username/email directly from display name.
   - Maintainability impact: collisions and non-ASCII/invalid email edge cases are likely.
   - Suggestion: normalize through the same user schema, check collisions, and let the installer provide email explicitly.

## What Works

- The endpoint is rate limited at line `32`.
- It returns a clean install status through `/status`.
