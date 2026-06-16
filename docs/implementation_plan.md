# Thaqib — Comprehensive Project Review

> Full-stack evaluation from the perspective of the project's context: a **Smart Cheating Detection System** with an admin dashboard, invigilator mobile interface, AI video pipeline, and PTT communication layer.

---

## Executive Summary

The project has a solid foundation: well-structured SQLAlchemy models, cookie-based JWT auth with refresh rotation, a working AI video pipeline with annotation overlays, and polished Arabic RTL interfaces. However, the review uncovered **3 reported bugs** and **14+ additional issues** across security, functionality, UX, and code quality.

---

## 🔴 CRITICAL: Reported Bugs

### Bug 1 — `video_exists: false` for test videos (Simulator)

> [!CAUTION]
> **Root Cause:** The simulator's `config.yaml` uses Linux container paths (`/app/videos/cam1.mp4`), but when running the simulator **outside Docker** on Windows, `Path("/app/videos/cam1.mp4").exists()` always returns `false`.

**Files involved:**
- [config.yaml](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/simulator/config.yaml#L7) — hardcoded `/app/videos/cam1.mp4`
- [main.py](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/simulator/main.py#L207) — `Path(video_path).exists()`

**How to reproduce:** Run `python simulator/main.py` directly on Windows → hit `/cameras` → all show `video_exists: false`.

**Fix:**
1. Accept a `--videos-dir` CLI flag or `VIDEOS_DIR` env var that defaults to `./test_videos` when running locally.
2. In `load_config()`, resolve `video_path` relative to `VIDEOS_DIR` if the absolute path doesn't exist.
3. Alternatively, create a second `config.local.yaml` that uses `./test_videos/cam1.mp4` relative paths.

---

### Bug 2 — PTT Functionality Not Working

> [!CAUTION]
> Multiple interacting failure points make PTT non-functional end-to-end.

**Root causes identified:**

#### 2A. Audio playback never happens — no `AudioContext` sink
- [useInvigilatorPtt.ts](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/frontend/src/hooks/useInvigilatorPtt.ts) — The hook receives binary WebSocket frames, but the **audio playback** path relies on `AudioContext` + `audioWorklet` that must be registered from a separate file (`ptt-playback-processor.js`).
- If that worklet file is missing from `public/`, the browser **silently fails** — no audio output, no error to the user.
- **Verify:** Check if `public/ptt-playback-processor.js` exists. If not, that's the root cause for no audio playback.

#### 2B. Mic permission blocked on non-HTTPS LAN
- The hook correctly detects `isInsecureLanContext()`, but `getUserMedia()` will be **rejected by the browser** on `http://192.168.x.x`.
- On dev (`localhost`) it works; on any LAN IP over HTTP it won't.
- **Fix:** The UI shows a warning badge, but PTT `startTransmission()` should gracefully handle the `NotAllowedError` and set `micState = 'blocked'` instead of leaving the connection in a broken state.

#### 2C. `startSpeak` vs `startTransmission` naming inconsistency
- [DashboardPage.tsx](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/frontend/src/pages/DashboardPage.tsx#L163) calls `ptt.startSpeak()` / `ptt.stopSpeak()`
- [HallMonitoringPage.tsx](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/frontend/src/pages/invigilator/HallMonitoringPage.tsx#L235) calls `ptt.startTransmission()` / `ptt.stopTransmission()`
- These must be two different methods on the same hook. If the hook only exposes one pair, the other page crashes silently.

#### 2D. `client_id` ignored by backend
- [ptt.py L66-67](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/src/thaqib/api/routes/ptt.py#L66-L67): Backend logs "client id supplied by caller was ignored" — the `client_id` URL param is always overridden by the JWT identity. This is **correct for security** but means the frontend must know the user's `ptt_id` to send a targeted `start_speak` message. If the frontend doesn't know the target's `ptt_id`, routing fails silently.

---

### Bug 3 — Test videos path resolution (Backend side)

The backend's [stream.py](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/src/thaqib/api/routes/stream.py) doesn't directly check `video_exists` — it uses `device.stream_url` from the DB (e.g., `http://localhost:8000/camera/hall101_cam_front/feed`). The `video_exists` issue is **entirely in the simulator**, not the backend. However, the backend's `_camera_readiness()` in [exams.py L45](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/src/thaqib/api/routes/exams.py#L45) uses `cv2.VideoCapture(source)` which will also fail if the simulator isn't running.

---

## 🟠 Security Vulnerabilities

### S1. Hardcoded default admin password returned in API response

> [!WARNING]
> **Severity: HIGH** — [setup.py L64, L86-88](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/src/thaqib/api/routes/setup.py#L64-L88)

```python
default_password = "Admin_Password123!"
# ...
return {
    "generated_credentials": {
        "username": generated_username,
        "password": default_password  # ← plaintext in HTTP response
    }
}
```

**Fix:** Either (a) require the password in the setup payload, or (b) don't return it in the response — show it once in the UI only.

### S2. CSRF token not validated on mutating endpoints

The frontend sends `X-CSRF-Token` header via [api.ts L23-25](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/frontend/src/config/api.ts#L23-L25), but the **backend never validates it**. No middleware or dependency checks `X-CSRF-Token` against the cookie. The double-submit cookie pattern is half-implemented.

### S3. Setup endpoint re-entrancy — incomplete guard

[setup.py L46](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/src/thaqib/api/routes/setup.py#L46): `if inst_count > 0 or user_count > 0` — this means if an institution exists but no user (e.g., partial failure), setup is blocked forever. Should use a transaction + idempotency check.

### S4. Demo seed credentials should stay documented

[seed_demo.py](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/seed_demo.py) creates development-only demo users with documented passwords. Keep this script out of production deployments and continue documenting the credentials in the seed output.

---

## 🟡 Functionality Gaps

### F1. No admin dashboard layout wrapper — no logout mechanism

> [!IMPORTANT]
> The admin role has **no `AdminLayout` component** with sidebar, header, or logout button.

[App.tsx L99-103](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/frontend/src/App.tsx#L99-L103): Admin routes render `<DashboardPage />` directly — no layout wrapping. The `handleLogout` function exists but is **never passed** to DashboardPage. Admin users have **no way to log out** from the UI.

### F2. Referee role not supported in frontend routing

[App.tsx L104](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/frontend/src/App.tsx#L104): Only `admin` and `invigilator` roles are routed. A `referee` user sees the "unauthorized" screen despite being a valid role in the backend.

### F3. Hall selector in dashboard is non-functional

[DashboardPage.tsx L503-508](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/frontend/src/pages/DashboardPage.tsx#L503-L508): The "القاعة" (Hall) dropdown is a static `<div>` with no click handler or state management — purely decorative.

### F4. Alerts Tab type mismatch

The [DashboardPage](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/frontend/src/pages/DashboardPage.tsx#L30-L46) `Alert` interface expects `{type, message, timestamp}` for rendering, but the backend returns `{event_type, severity, timestamp}` — field names don't match.

In [HallMonitoringPage.tsx L343](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/frontend/src/pages/invigilator/HallMonitoringPage.tsx#L343): `alert.type` and `alert.message` are rendered but the backend's hall status response returns `{event_type, severity, timestamp, confidence_score}` — missing `type` and `message` fields entirely.

### F5. Session status lifecycle has gaps

- `start_monitoring` in [stream.py L706](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/src/thaqib/api/routes/stream.py#L706) auto-transitions from `scheduled` → `active`, but there's no `paused` state.
- `stop_monitoring` [L778](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/src/thaqib/api/routes/stream.py#L778) auto-transitions to `completed` when all halls stop, but if an admin stops one hall out of four, the session is still marked `completed`.

### F6. No error recovery for pipeline crashes

[stream.py L629](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/src/thaqib/api/routes/stream.py#L629): If the pipeline throws an exception, `is_running` is set to `False` but there's **no automatic retry**. The camera stays in a dead state until manual refresh.

### F7. Reports page — no frontend route for viewing them

The backend has a [session report endpoint](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/src/thaqib/api/routes/exams.py#L530) (`GET /sessions/{id}/report`) but there's **no Reports page** in the frontend. `NAV_ITEMS` includes only `home`, `halls`, `exams`, `supervisors`, `settings`.

### F8. Seed entrypoint drift resolved

[seed_demo.py (root)](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/seed_demo.py) is now the only demo seed entrypoint. It supports `college` and `university` modes and seeds simulator-compatible camera and microphone stream URLs for the demo hall.

---

## 🟢 UX / Flow Issues

### U1. No "force password change" after first setup

After running the setup wizard, the admin account uses `Admin_Password123!` — but the UI never prompts the user to change it.

### U2. Schedule page doesn't filter by date

[SchedulePage.tsx L85](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/frontend/src/pages/invigilator/SchedulePage.tsx#L85): Section header says "اليوم" (Today) but all assignments are shown regardless of date. Past, future, and today's sessions are all mixed together.

### U3. No loading skeleton / shimmer effects

All pages show a centered spinner. For a production system, skeleton screens would feel more polished and reduce perceived latency.

### U4. Bell notification badge in InvigilatorLayout is hardcoded

[InvigilatorLayout.tsx L57](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/frontend/src/layouts/InvigilatorLayout.tsx#L57): The red dot badge is always visible — not connected to actual notification count.

### U5. "عرض الكل" (View All) alerts button is non-functional

[HallMonitoringPage.tsx L331](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/frontend/src/pages/invigilator/HallMonitoringPage.tsx#L331): Shows a "View All" label but it's a `<span>` — not a link or button.

### U6. Settings page is a placeholder

[App.tsx L109](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/frontend/src/App.tsx#L109): Invigilator settings page renders `"قريباً..."` (Coming soon).

---

## 🔵 Code Quality & Consistency Issues

### C1. Duplicate cleanup effect in DashboardPage

[DashboardPage.tsx L189-196 and L283-287](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/frontend/src/pages/DashboardPage.tsx#L189-L196): Two separate `useEffect` hooks both clean up the same interval refs. The first runs on unmount but the second also runs on unmount. The first is redundant.

### C2. Import inside hot loop

[ptt.py L88](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/src/thaqib/api/routes/ptt.py#L88): `import json` is inside the WebSocket message loop. Should be at module level.

### C3. Lazy import of pipeline in thread

[stream.py L474](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/src/thaqib/api/routes/stream.py#L474): `from thaqib.video.pipeline import VideoPipeline` — This uses a different import path (`thaqib.video.pipeline`) than the rest of the codebase (`src.thaqib.*`). Likely relies on PYTHONPATH being set correctly or will fail with `ModuleNotFoundError`.

### C4. Mixed `datetime.now()` usage — naive vs aware

- [stream.py L700](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/src/thaqib/api/routes/stream.py#L700): `datetime.now()` (naive)
- [auth.py L29](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/src/thaqib/api/routes/auth.py#L29): `datetime.now(timezone.utc)` (aware)
- [exams.py L594](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/src/thaqib/api/routes/exams.py#L594): `datetime.now()` (naive)

Mixing naive and timezone-aware datetimes will cause `TypeError` when comparing or subtracting them.

### C5. `init_db.py` and setup wizard redundancy

Both [init_db.py](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/src/thaqib/db/init_db.py) (CLI) and [setup.py](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/src/thaqib/api/routes/setup.py) (API) create the initial institution + admin, but they use different fields. `init_db.py` asks for `code` and `contact_email` which the API setup doesn't. They can conflict if both are used.

### C6. `user.role` not included in `HallMonitoringStatus` alerts

The frontend [types/exams.ts L30-34](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/frontend/src/types/exams.ts#L30-L34) expects `alerts[].type` and `alerts[].message`, but the backend's hall status endpoint [exams.py L316-325](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/src/thaqib/api/routes/exams.py#L316-L325) returns `event_type`, `severity`, `timestamp`, `confidence_score` — no `type` or `message` field at all.

---

## 🏗️ Architecture Concerns

### A1. Single-threaded WebSocket manager

[ws_manager.py](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/src/thaqib/api/ws_manager.py): The `ConnectionManager` stores only **one WebSocket per user_id**. If an admin opens two tabs, the second connection replaces the first silently. No multi-device support.

### A2. Video pipeline threads vs async mismatch

The video pipeline runs in daemon `threading.Thread`s, but FastAPI is async. The `_camera_states` dict is protected by a `threading.Lock`, which is correct, but the `_alerts` list is accessed from both sync threads and async route handlers — potential race condition since `asyncio` coroutines can be preempted between `_alerts_lock` acquire and release.

### A3. No database migrations tool

The project uses `Base.metadata.create_all()` directly. No Alembic migration files found. Schema changes require dropping and recreating the database.

### A4. Simulator and backend share no Docker network

[docker-compose.yml](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/docker-compose.yml) and [docker-compose.simulator.yml](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/simulator/docker-compose.simulator.yml) use separate networks. The backend container can't reach the simulator container by service name — they must communicate via host-published ports.

---

## Proposed Fix Priority

| Priority | Issue | Impact |
|----------|-------|--------|
| 🔴 P0 | Bug 1: Simulator video_exists path | Blocks demo entirely |
| 🔴 P0 | Bug 2: PTT not working (multi-factor) | Core feature broken |
| 🔴 P0 | S1: Plaintext password in API response | Security vulnerability |
| 🟠 P1 | F1: Admin has no logout | Usability blocker |
| 🟠 P1 | F2: Referee role not routed | Feature gap |
| 🟠 P1 | C4: Naive vs aware datetime | Runtime crashes |
| 🟠 P1 | F4/C6: Alert type mismatch FE↔BE | UI shows undefined |
| 🟡 P2 | S2: CSRF not validated | Security gap |
| 🟡 P2 | F6: No pipeline crash recovery | Reliability |
| 🟡 P2 | U2: Schedule not filtered by date | UX confusion |
| 🟡 P2 | C3: Wrong import path for pipeline | Deploy failure |
| 🟢 P3 | A3: No Alembic migrations | Maintainability |
| 🟢 P3 | U3/U4/U5: UX polish items | Quality of life |
| 🟢 P3 | F7/F8: Missing pages, duplicate scripts | Completeness |

---

## Open Questions

> [!IMPORTANT]
> 1. **Are you running the simulator inside Docker or directly on Windows?** This determines the exact fix for Bug 1.
> 2. **Does `public/ptt-playback-processor.js` exist in your frontend build?** This is likely the root cause for Bug 2's audio silence.
> 3. **Which issues do you want me to fix first?** I recommend starting with P0 (video_exists + PTT + security), then P1.
> 4. **Is the `referee` role intended to use the admin dashboard or the invigilator interface?** This affects how we route it.
