# Review: frontend/src/components/CameraModal.tsx

Overall quality: Good

Refactoring effort: Medium

## Findings

1. Report and media downloads lack auth
   - Lines `205`, `271`, `279`, and `286` build unauthenticated stream/report URLs.
   - This matches current backend behavior but should change with secured media endpoints.
   - Suggestion: use authenticated fetch for report generation and signed URLs or authorized file endpoints for media.

2. Demo-only keyboard guidance is visible in production UI
   - Lines `167-179` show OpenCV demo controls that do not apply to the dashboard.
   - Suggestion: remove this block or replace it with actual dashboard controls.

3. Pointer and mouse handlers can double-fire
   - Lines `312-329` register both pointer and mouse events.
   - Some browsers synthesize mouse events after pointer events.
   - Suggestion: use pointer events only, or guard repeated starts/stops with state.

4. Silent report download failure
   - Lines `203-219` ignore download errors.
   - Suggestion: expose a toast/error state when report generation fails.

## What Works

- The component separates camera and alert views well.
- The AVI fallback at lines `201` and `269-295` handles browser playback limitations pragmatically.
