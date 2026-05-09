# Review: src/thaqib/schemas/events.py

Overall quality: Needs Improvement

Refactoring effort: Medium

## Findings

1. Severity and event type are raw strings
   - Line `8` declares `severity: str`.
   - Suggestion: use enums/literals for severity and event type to prevent dashboard/report drift.

2. Event metadata is unrestricted
   - Line `14` accepts arbitrary `metadata_json`.
   - Suggestion: define typed metadata for known event categories or validate maximum size.

3. Media paths are accepted from the client/pipeline
   - Lines `12-13` accept `video_clip_path` and `audio_clip_path`.
   - Security impact: untrusted paths can later become file-serving targets if reused unsafely.
   - Suggestion: store media through a media service that returns server-generated relative IDs/paths.

## What Works

- The schema separates create and response types.
- Timestamps are typed as `datetime`.
