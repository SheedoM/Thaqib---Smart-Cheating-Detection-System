# Review: frontend/package.json

Overall quality: Good

Refactoring effort: Low

## Findings

1. Test command defaults to watch mode
   - Line `11` defines `"test": "vitest"`.
   - CI usually needs non-watch mode.
   - Suggestion: add `"test:run": "vitest --run"` and use it in CI.

2. No coverage script
   - Lines `6-12` define dev/build/lint/preview/test only.
   - Suggestion: add `"test:coverage": "vitest --run --coverage"` once coverage provider is installed.

3. React 19 ecosystem compatibility should be watched
   - Lines `16-17` use React 19.2.
   - Suggestion: ensure testing libraries and any future UI dependencies support React 19 before expanding.

## What Works

- Build runs TypeScript before Vite bundling at line `8`.
- Dependencies are lean and appropriate for the current app.
