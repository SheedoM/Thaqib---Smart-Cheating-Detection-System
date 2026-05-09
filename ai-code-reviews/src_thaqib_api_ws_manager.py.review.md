# Review: src/thaqib/api/ws_manager.py

Overall quality: Needs Improvement

Refactoring effort: Medium

## Findings

1. Active connections are stored without concurrency protection
   - Lines `15`, `19`, `23-24`, and `50-61` mutate/read `active_connections`.
   - Risk: concurrent connects/disconnects/broadcasts can change the dictionary during iteration.
   - Suggestion: protect the mapping with an `asyncio.Lock` or snapshot items before broadcasting.

2. No authentication or ownership checks
   - Lines `17-20` accept any `user_id`/PTT id the caller provides.
   - Security impact: a client can impersonate another user by choosing their ID.
   - Suggestion: authenticate WebSocket upgrade and derive user identity from the token, not the path.

3. Single connection per user silently replaces the previous one
   - Line `19` overwrites any existing connection for the same ID.
   - Suggestion: either support multiple connections per user or explicitly close the old connection when replacing it.

4. Broadcast sends sequentially to all clients
   - Lines `50-57` and `66-73` await each socket send one by one.
   - Performance impact: one slow client delays everyone.
   - Suggestion: send concurrently with bounded tasks, or maintain per-client queues.

## What Works

- Failed sends are cleaned up after broadcast.
- Personal JSON and binary send methods are clearly separated.
