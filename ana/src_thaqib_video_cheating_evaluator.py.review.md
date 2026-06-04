# Review: src/thaqib/video/cheating_evaluator.py

Overall quality: Good

Refactoring effort: Medium

## Findings

1. Alert callback errors are swallowed
   - Lines `141-142` log callback errors but do not expose failure state.
   - Suggestion: increment a metric or attach callback failure status to pipeline stats.

2. Threshold evaluation lacks unit tests
   - Lines `91-128` combine cosine threshold, suspicious duration, and target selection.
   - Suggestion: add deterministic unit tests for boundary angles, duration threshold, phone state, and cooldown behavior.

3. State mutations are implicit
   - The `evaluate()` method changes registry state and may trigger callbacks.
   - Suggestion: return an evaluation result object and let the pipeline apply side effects.

## What Works

- Risk threshold values come from settings rather than being embedded directly.
- The callback design keeps UI/alert persistence out of evaluator logic.
