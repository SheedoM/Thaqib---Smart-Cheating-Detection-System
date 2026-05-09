# Review: frontend/src/hooks/useInvigilatorPtt.ts

Overall quality: Good

Refactoring effort: Medium

## Findings

1. PTT WebSocket has no auth
   - Line `60` opens a WebSocket URL with only `clientId`.
   - Security impact: anyone can impersonate clients and send/receive audio if they know IDs.
   - Suggestion: pass a short-lived token during WebSocket upgrade and validate it server-side.

2. Deprecated audio API
   - Line `111` uses `createScriptProcessor`, which is deprecated.
   - Suggestion: move PCM conversion to an `AudioWorkletProcessor`.

3. Default IDs are hardcoded
   - Lines `15-16` default to `control_room_dashboard` and `invigilator_demo_1`.
   - Suggestion: derive IDs from authenticated user/session context.

4. Audio playback can pile up
   - Lines `192-203` create a new buffer source per chunk without a jitter buffer or scheduling clock.
   - Performance/audio impact: chunks may overlap or stutter under network jitter.
   - Suggestion: add a small playback queue and schedule chunks against `audioContext.currentTime`.

## What Works

- The hook cleans up media tracks and WebSocket state.
- It handles connect timeout and microphone denial in user-visible state.
