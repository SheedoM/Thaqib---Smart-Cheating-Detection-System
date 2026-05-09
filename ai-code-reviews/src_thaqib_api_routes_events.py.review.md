# Review: src/thaqib/api/routes/events.py

Overall quality: Needs Improvement

Refactoring effort: Medium

## Findings

1. Event ingestion is unauthenticated
   - Lines `15-20` accept detection events without `get_current_user`, `RequireRole`, or a machine-token dependency.
   - Lines `23-25` note this is intentional for future internal auth.
   - Security impact: anyone who can reach the API can inject false cheating events.
   - Suggestion: require a signed internal pipeline token or mTLS-equivalent deployment boundary before accepting events.

2. Read endpoint is unauthenticated
   - Lines `66-73` expose detection events for any `exam_session_id`.
   - Suggestion: require at least `admin/referee/invigilator` authorization and scope records to the user's institution/assignment.

3. Pagination is unbounded by validation
   - Lines `71-72` default to `skip=0`, `limit=100`, but no `ge/le` bounds.
   - Suggestion: use `Query(0, ge=0)` and `Query(100, ge=1, le=500)`.

4. WebSocket broadcast is coupled to DB write path
   - Line `62` awaits broadcast after committing.
   - Reliability impact: a slow/broken client can make ingestion slower.
   - Suggestion: publish to a queue/background task and let WebSocket delivery fail independently.

## What Works

- The route validates that the exam session exists before inserting the event at lines `27-29`.
