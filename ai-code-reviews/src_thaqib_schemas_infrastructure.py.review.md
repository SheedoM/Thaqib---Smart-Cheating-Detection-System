# Review: src/thaqib/schemas/infrastructure.py

Overall quality: Needs Improvement

Refactoring effort: Medium

## Findings

1. `HallUpdate` inherits required fields then overrides only some
   - Line `18` subclasses `HallBase`; lines `19-20` make only `name` and `capacity` optional.
   - Result: updating only `status`, `image`, or `layout_map` may still require inherited fields depending on Pydantic behavior and schema generation.
   - Suggestion: define update schemas independently with every field optional.

2. Device stream URL is required for every device type
   - Line `53` requires `stream_url`, but microphones may not have a stream URL.
   - Suggestion: use discriminated schemas for camera/microphone or make `stream_url` optional with validation when `type == "camera"`.

3. IP regex accepts invalid addresses
   - Line `52` permits octets above 255.
   - Suggestion: use `IPvAnyAddress`.

4. Status fields are raw strings
   - Lines `13` and `56` use plain optional strings.
   - Suggestion: define enums for hall and device status and share them with frontend constants.

## What Works

- Basic length/range constraints exist for names, capacity, identifier, and code.
- `image` is represented in hall schemas at line `12`, matching the frontend payload.
