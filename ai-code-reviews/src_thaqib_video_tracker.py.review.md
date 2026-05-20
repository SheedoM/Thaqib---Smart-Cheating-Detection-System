# Review: src/thaqib/video/tracker.py

Overall quality: Good

Refactoring effort: Medium

## Findings

1. Re-ID weights default is hidden
   - Line `94` uses `models/osnet_x0_25_msmt17.pt` through `getattr`, but this setting is not declared in `Settings`.
   - Suggestion: add `reid_weights_path` to `Settings` and `.env.example`.

2. Tracker state cleanup API is missing
   - `pipeline.py:428-431` directly mutates tracker internals because this class does not expose cleanup.
   - Suggestion: add public methods for pruning, locking, and querying track state.

3. Role of labels vs selected IDs could be clearer
   - Lines `210-229` manage selection and labels in the tracker.
   - Suggestion: document whether selection is UI state, tracking state, or monitoring state; consider keeping UI selection outside the tracker.

## What Works

- The wrapper around BoT-SORT/ByteTrack-like tracking gives the rest of the system a stable dataclass result.
- Selection methods are small and readable.
