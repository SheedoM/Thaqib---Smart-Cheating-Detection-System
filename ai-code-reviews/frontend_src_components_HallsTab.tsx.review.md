# Review: frontend/src/components/HallsTab.tsx

Overall quality: Needs Improvement

Refactoring effort: High

## Findings

1. Frontend payload does not match backend schemas
   - Lines `224` and `243` send `image`, which backend hall schemas do not accept.
   - Lines `264` sends `name` for devices, but backend `DeviceCreate` does not define `name`.
   - Line `268` sends `stream_url: null` for microphones, while backend requires a string.
   - Suggestion: create shared API DTO types or align backend schemas with frontend requirements.

2. Raw `any[]` hides device-shape errors
   - Lines `178-179`, `282`, and `288` use `any`.
   - Suggestion: define `EditableDevice` and strongly type update/remove helpers.

3. Mutating copied arrays still mutates nested objects
   - Lines `282-285` shallow-copy the array and mutate `newArr[index][field]`.
   - Suggestion: use immutable object replacement: `arr.map((item, i) => i === index ? {...item, [field]: value} : item)`.

4. Auth header can send `Bearer null`
   - Lines `34-39`, `53-57`, and `197-201` build auth headers without checking token presence.
   - Suggestion: use a shared `authFetch` that redirects to login on missing/expired token.

5. Editing devices is incomplete
   - Lines `249-252` state that editing only adds new devices.
   - Suggestion: implement full create/update/delete reconciliation or disable editing existing devices clearly.

## What Works

- The component re-fetches after mutations and keeps modal open/closed state straightforward.
- It validates institution context before creating halls at lines `203-211`.
