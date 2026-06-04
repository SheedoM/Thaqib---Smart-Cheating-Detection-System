# Review: src/thaqib/video/tools_detector.py

Overall quality: Good

Refactoring effort: Medium

## Findings

1. Tool detection silently disables itself on model load failure
   - Lines `81-83` log an error and set `_model = None`.
   - Risk: production could run without tool detection while reporting normal service health.
   - Suggestion: expose detector health to `/status` and make required/optional behavior configurable.

2. Target labels are string-matched at runtime
   - Lines `55`, `106-107`, and `131-140` depend on model class-name strings.
   - Suggestion: validate configured labels against model names at load and fail fast when labels do not exist.

3. Device usage relies on model internals
   - Line `110` uses `self._model.device`.
   - Suggestion: store the resolved device explicitly, as the human detector does.

## What Works

- Separate confidence threshold and target labels keep tool detection configurable.
- The detector returns an empty result when disabled, which protects callers from `None` checks.
