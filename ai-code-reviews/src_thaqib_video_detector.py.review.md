# Review: src/thaqib/video/detector.py

Overall quality: Good

Refactoring effort: Low

## Findings

1. Model path validation is implicit
   - Lines `95` and `113` load whatever `settings.yolo_model` contains.
   - Suggestion: validate path/model names at settings load and return an actionable error if weights are missing.

2. Confidence fallback treats zero as missing
   - Line `96` uses `confidence_threshold or settings.detection_confidence`.
   - If a caller intentionally passes `0.0`, it will be replaced by the setting.
   - Suggestion: use `settings.detection_confidence if confidence_threshold is None else confidence_threshold`.

3. Inference device and image size should be observable
   - Lines `145-147` pass inference settings, but only load logs mention device.
   - Suggestion: include model name, image size, confidence, and device in startup diagnostics.

## What Works

- The detector is isolated behind a clear `HumanDetector` class.
- The dataclasses make downstream code easier to reason about.
