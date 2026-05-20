# Review: frontend/src/config/api.ts

Overall quality: Good

Refactoring effort: Low

## Findings

1. Dev WebSocket port appears inconsistent
   - Line `15` defaults to `ws://127.0.0.1:8001`.
   - Backend defaults to port `8000` in `src/thaqib/config/settings.py:69`, while Vite proxy targets `8001` in `frontend/vite.config.ts:12`.
   - Suggestion: document the expected local port topology or use one env var for both HTTP and WS.

2. No validation of configured API origins
   - Lines `2-4` accept any string from env.
   - Suggestion: warn in development if `VITE_API_URL` is missing a protocol or contains a trailing path.

## What Works

- Centralizing API and WebSocket URL construction is the right pattern.
- `encodeURIComponent` at line `21` is good for WebSocket path safety.
