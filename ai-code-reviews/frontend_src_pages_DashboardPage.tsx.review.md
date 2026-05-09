# Review: frontend/src/pages/DashboardPage.tsx

Overall quality: Needs Improvement

Refactoring effort: High

## Findings

1. Large component owns too much behavior
   - Lines `120-503` manage page state, polling, navigation, notifications, modal state, PTT, and rendering.
   - Lines `513-842` add more subcomponents in the same file.
   - Suggestion: split into hooks (`useMonitoringPolls`, `useAlerts`, `useDashboardPtt`) and components (`DashboardHeader`, `CasesTab`, `CamerasTab`).

2. Dashboard polling lacks auth headers
   - Lines `187`, `200`, and `235` fetch stream endpoints without tokens.
   - This currently works because backend stream routes are unauthenticated, but it bakes in the security gap.
   - Suggestion: use a shared authenticated API client and make backend require auth.

3. Fixed polling intervals are magic numbers
   - Lines `245-247` poll monitoring, alerts, and stats at 5s/3s/2s.
   - Suggestion: move intervals to constants and consider WebSocket/SSE for alerts and stats.

4. User identity is hardcoded
   - Lines `310-311` show a fixed user name and role.
   - Suggestion: load current user from `/api/auth/me` and render real profile data.

5. Refresh streams is unauthenticated and silently ignores errors
   - Lines `279-285` POST refresh with no auth header and no feedback.
   - Suggestion: surface success/failure state and require admin/referee authorization.

## What Works

- Poll cleanup is handled at lines `165-172` and `249-253`.
- The UI has clear states for no halls, loading, offline cameras, alerts, and active feeds.
