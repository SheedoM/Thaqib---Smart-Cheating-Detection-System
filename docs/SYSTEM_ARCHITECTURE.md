# Thaqib — System Architecture (Source of Truth)

> **Status:** This document reflects the **as-built** system as of June 2026, plus one
> clearly-marked **planned** subsystem (RF Device Detection). Where a feature is
> designed but not yet implemented, it is tagged **[PLANNED]**. Everything else is
> implemented in the codebase.
>
> This file supersedes all earlier architecture notes. When code and this document
> disagree, fix one of them — do not let them drift.

---

## Table of Contents

1. [What Thaqib Is](#1-what-thaqib-is)
2. [User Roles](#2-user-roles)
3. [High-Level Architecture](#3-high-level-architecture)
4. [Technology Stack (Actual)](#4-technology-stack-actual)
5. [Video Detection Pipeline](#5-video-detection-pipeline)
6. [Audio Detection Pipeline](#6-audio-detection-pipeline)
7. [Spatial Neighbor Modeling](#7-spatial-neighbor-modeling)
8. [Alert Processing Framework](#8-alert-processing-framework)
9. [Hall Voice Channel Subsystem](#9-hall-voice-channel-subsystem)
10. [Video Streaming](#10-video-streaming)
11. [Data Model](#11-data-model)
12. [Backend API Surface](#12-backend-api-surface)
13. [Frontend Application](#13-frontend-application)
14. [Security](#14-security)
15. [Anti-Cheating Signal Strategy](#15-anti-cheating-signal-strategy)
16. [RF Device Detection Subsystem — PLANNED](#16-rf-device-detection-subsystem--planned)
17. [Deployment & Running the System](#17-deployment--running-the-system)
18. [Configuration Reference](#18-configuration-reference)
19. [Evidence & Forensics](#19-evidence--forensics)

---

## 1. What Thaqib Is

Thaqib (ثاقب, "sharp-sighted") is an **AI-powered real-time exam monitoring system** that
assists human invigilators in detecting cheating during **in-person** academic
examinations. It is explicitly a **decision-support / human-in-the-loop** tool: the AI
surfaces likely incidents, but **no disciplinary action is ever taken automatically** —
every alert requires human review.

It detects three primary behavior classes:

1. **Gaze cheating** — a student sustaining their gaze toward a neighbor's paper.
2. **Coordinated neighbor events** — two adjacent students exhibiting suspicious gaze
   within a short window (potential collaboration).
3. **Audio anomalies** — whispered exchanges and talking during a silent exam.

A fourth class — **unauthorized objects** (phones, cheat sheets) — is detected by a
dedicated object model.

---

## 2. User Roles

| Role | Responsibilities |
|---|---|
| **admin** | System setup, institutions, halls, devices, users, exam scheduling, global settings. |
| **referee** (control room) | Schedules exams, monitors the control-room dashboard, reviews/handles escalated alerts, talks to invigilators over the hall voice channel. |
| **invigilator** | Physically present in the hall. Starts/stops monitoring, receives alerts on a tablet, walks to flagged seats, communicates with the control room over the hall voice channel (hold-to-talk). |

Roles are enforced server-side via a `RequireRole` dependency and JWT claims.

---

## 3. High-Level Architecture

Thaqib has four logical layers:

```
┌─────────────────────────────────────────────────────────────────┐
│  1. DATA ACQUISITION                                              │
│     IP cameras (RTSP)   USB/IP microphones   [PLANNED: RF nodes]  │
└───────────────┬─────────────────────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────────────────────┐
│  2. DETECTION ENGINE (Python)                                     │
│     Video pipeline (YOLOv11 + BoT-SORT + MediaPipe + OSNet)       │
│     Audio pipeline (energy discriminator + Silero VAD + Whisper)  │
│     → emits DetectionEvents                                       │
└───────────────┬─────────────────────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────────────────────┐
│  3. BACKEND (FastAPI + SQLAlchemy)                                │
│     Event aggregation → GroupEvents → Alerts (tiered)             │
│     REST API · WebSocket alerts · WebSocket voice · MJPEG streams │
│     SQLite (dev) / PostgreSQL (prod)                              │
└───────────────┬─────────────────────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────────────────────┐
│  4. DASHBOARD (React 19 + TypeScript + Tailwind, RTL/Arabic)      │
│     Admin/referee control room · Invigilator hall monitoring      │
└───────────────────────────────────────────────────────────────────┘
```

---

## 4. Technology Stack (Actual)

> ⚠️ Earlier drafts mentioned Redis, RabbitMQ, Socket.IO, WebRTC/GStreamer, Kubernetes,
> and smartwatch haptics. **None of these are in the current system.** The accurate
> stack is below.

**Detection Engine**
- Python 3.10+
- PyTorch
- Ultralytics **YOLOv11** (`models/yolo11m.pt`) — person detection
- Ultralytics **YOLOv8** custom (`models/best.pt`) — papers/phones/objects
- **BoT-SORT** via `boxmot` — multi-object tracking
- **MediaPipe Face Landmarker** (`models/face_landmarker.task`) — 478 3D landmarks
- **OSNet** (`osnet_x0_25_msmt17.pt`) — face/person re-identification
- **Silero VAD** — voice activity detection
- **Faster-Whisper** — speech-to-text (Arabic by default)

**Backend**
- FastAPI
- SQLAlchemy ORM + Alembic migrations
- Pydantic v2 settings
- SQLite (development) / PostgreSQL (production)
- `slowapi` rate limiting
- WebSockets (native FastAPI) for alerts and the hall voice channel
- MJPEG over HTTP for live video

**Frontend**
- React 19 + TypeScript
- Vite
- Tailwind CSS 4
- React Router
- Full RTL / Arabic interface

**No external broker, no Redis, no Kubernetes.** State lives in the relational DB;
real-time delivery is in-process via the WebSocket `ConnectionManager`.

---

## 5. Video Detection Pipeline

Located in `src/thaqib/video/`. Master orchestration in `pipeline.py`.

**Flow:**

```
RTSP frame (≤30 FPS)
   │
   ▼
YOLOv11m person detection         detector.py    (conf 0.15, imgsz 640)
   │
   ▼
BoT-SORT tracking                 tracker.py      (persistent track IDs)
   │
   ▼
OSNet re-identification           reid.py         (cosine ≥ 0.80 on re-entry)
   │
   ▼
MediaPipe face landmarks          face_mesh.py    (parallel worker pool)
   │
   ▼
Gaze vector computation           gaze.py         (nose-bridge → iris, 2D unit vec)
   │
   ▼
Cheating evaluation               cheating_evaluator.py
   │   - For each surrounding paper, compute cos(angle) between gaze and
   │     direction to paper.
   │   - If cos(angle) > cos(RISK_ANGLE_TOLERANCE)  (default 25°)
   │     sustained for SUSPICIOUS_DURATION_THRESHOLD (default 2.0 s)
   │     → flag student as cheating, fire on_alert(state).
   │   - Cooldown logic prevents oscillation on brief gaze breaks.
   ▼
Object detection (parallel)       tools_detector.py (YOLOv8, conf 0.45)
   │   - Detects papers (for neighbor modeling) and phones/objects.
   ▼
Annotated alert clip + DetectionEvent
```

**Key parameters** (from `config/settings.py`, overridable via `.env`):

| Setting | Default | Meaning |
|---|---|---|
| `detection_confidence` | 0.15 | Person-detection threshold |
| `detection_imgsz` | 640 | YOLO inference resolution |
| `tools_confidence` | 0.45 | Object (paper/phone) threshold |
| `tracking_max_distance` | 100 | BoT-SORT association distance |
| `tracking_max_age` | 30 | Frames a lost track survives |
| `neighbor_k` | 6 | Nearest neighbors per student |
| `risk_angle_tolerance` | 25.0° | Max gaze-to-paper angle to count as "looking" |
| `suspicious_duration_threshold` | 2.0 s | Sustained gaze before flagging |
| `reid_match_threshold` | 0.80 | OSNet cosine similarity for re-ID |
| `face_mesh_workers` | 4 | Parallel MediaPipe workers |

The evaluator runs **synchronously on the main thread** to keep `is_cheating` /
`is_alert_recording` state consistent with the recording collector.

---

## 6. Audio Detection Pipeline

Located in `src/thaqib/audio/`. Three-thread design.

```
Main thread:    read 500 ms chunks → classify GLOBAL/LOCAL → route
VAD worker:     Silero VAD on LOCAL chunks → accumulate speech buffer
Whisper worker: Faster-Whisper STT + keyword match → save evidence
```

**Global/Local discriminator** (`discriminator.py`):
- **2-mic mode:** learns a baseline energy ratio over the first
  `audio_calibration_chunks` (30) chunks; a chunk is **LOCAL** when
  `raw_ratio / baseline_ratio ≥ audio_local_ratio_multiplier` (2.0×).
- **N-mic mode:** a chunk is **LOCAL** if fewer than `audio_global_fraction` (60%) of
  mics heard it.
- Periodic recalibration every `audio_recalibration_interval_sec` (300 s).

**Preprocessing** (`preprocessor.py`): high-pass filter (100 Hz), spectral noise
reduction (strength 0.75), adaptive RMS gain.

**Detection modes:**
- **STRICT** (`audio_strict_mode=true`, default): any confirmed speech = violation
  (silent-exam assumption).
- **KEYWORD:** only speech matching `keywords.json` (fuzzy match) is flagged.

**Evidence** (`evidence.py`): WAV clip (2 s pre + event + 2 s post) plus a JSON sidecar
with transcript, matched keywords, confidence, timestamps, and SHA-256 hash. Full-session
recording and sustained-episode recording are also supported.

---

## 7. Spatial Neighbor Modeling

`src/thaqib/video/neighbors.py` + `registry.py`.

- A **k-nearest-neighbor graph** (k = `neighbor_k`, default 6) is maintained continuously
  from person-detection centroids — it reflects the live seating arrangement, not a static
  floor plan.
- Each student's `surrounding_papers` set is populated with paper centroids detected in
  the regions of its k nearest neighbors. This lets the gaze evaluator attribute a gaze to
  a **specific neighbor's paper** and identify the "victim" track.
- When two adjacent students both produce suspicious gaze events within the **5-second
  aggregation window**, the backend creates a **GroupEvent** (coordinated cheating).

---

## 8. Alert Processing Framework

**Event aggregation:** Raw `DetectionEvent`s enter a 5-second sliding window. Events
sharing a session, within spatial adjacency, and of compatible types are merged into a
**GroupEvent** (with traceability back to participating events).

**Severity inputs:** (i) behavior duration, (ii) gaze angle magnitude, (iii) number of
students involved, (iv) recent violation frequency for that student.

**Tiers:**
- **Tier 1 (low):** brief, isolated anomaly. → invigilator dashboard notification.
- **Tier 2 (high):** GroupEvent, prolonged behavior (>10 s), large head turn, or repeated
  violations. → invigilator **and** all active control referees, with a distinct cue.

**Alert lifecycle** (as implemented in the `Alert` model + routes):

```
pending ──► claimed ──► confirmed        (real incident, action taken)
   │                └──► cancelled / false_positive  (no cheating)
   └──────────────────► escalated ──► confirmed / cancelled
```

The `Alert` model stores `claimed_by/at`, `confirmed_by/at`, `cancelled_by/at`,
`escalated`, `resolution_notes`. Routes expose `confirm` and `cancel` actions; the
dashboard calls `/api/alerts/{id}/confirm` and `/api/alerts/{id}/cancel`.

**Application-level invariant:** each `Alert` references **exactly one** of
`detection_event_id` **or** `group_event_id` (never both).

---

## 9. Hall Voice Channel Subsystem

Two-way live voice between the control room (admin/referee) and hall invigilators, over the
local network. Runs entirely in-process (no media server) and is **deliberately stateless**
— no DB writes, no clip recording, no approval state machine.

> **History:** An earlier "PTT" design (`routes/ptt.py` + `ws_manager.py` +
> `models/ptt.py` + `HallVoiceChannel`/`PttClip` tables) was **fully removed** in commit
> `29d7de1` and replaced by this minimal channel. Migration `20260604_remove_ptt` drops the
> `ptt_clips` / `hall_voice_channels` tables and the `users.ptt_id` column. Do not
> reintroduce those references.

**Backend** — `src/thaqib/api/routes/voice.py`:
- **Endpoint:** `WS /api/v1/voice/ws/{hall_id}` — one channel per hall. State is a simple
  in-memory dict: `hall_id → { user_id → {ws, role, name} }`.
- Audio: binary frames (raw PCM) are relayed to everyone else in the hall (`_broadcast_bytes`,
  excluding the sender).
- Control messages: `talk_start` / `talk_stop` (relayed to others) and `ping` → `pong`.
- **Presence:** every connect/disconnect broadcasts a `presence` message listing
  participants (`id`, `role`, `name`).
- **Authentication:** JWT from the access cookie or `?access_token=` query param (the Vite
  dev proxy strips cookies on the WS upgrade, so the token is also appended to the URL).
  `user_id` is the username.
- **Incident push:** `notify_hall(hall_id, message)` lets other parts of the backend push a
  JSON card (e.g. a confirmed incident) to everyone connected to a hall; it's a no-op when
  nobody is connected.
- **No persistence:** nothing about voice is written to the database. Microphone capture on
  the client requires a secure context (HTTPS or `localhost`).

**Frontend** — `frontend/src/hooks/useHallVoice.ts`:
- Opens the hall voice WebSocket, handles presence, relays mic audio while the talk button
  is held, and plays received audio.
- Consumed by the control-room hall view (`DashboardPage.tsx`) and the invigilator's
  monitoring page (`HallMonitoringPage.tsx`).

---

## 10. Video Streaming

- Cameras are ingested as RTSP by the detection engine.
- The browser receives **MJPEG over HTTP** via `/api/stream/*` — no WebRTC, no plugins.
- The dashboard polls `/api/stream/monitoring`, `/api/stream/alerts`, and
  `/api/stream/status` on short intervals (5 s / 3 s / 2 s) to update hall, alert, and
  per-camera stats.
- A **hall readiness check** confirms all registered devices are online before monitoring
  can start.

---

## 11. Data Model

All models use UUID primary keys, `created_at`/`updated_at` timestamps, and most
infrastructure entities support soft delete (`deleted_at`).

### Implemented tables

```
institutions ──1:N── halls ──1:N── devices
     │                  │
     │                  └──M:N── exam_sessions  (via exam_session_halls)
     │
     └──1:N── users ──1:N── refresh_tokens
                  │
                  └──1:N── assignments

exam_sessions ──1:N── assignments ──N:1── halls
exam_sessions ──1:N── detection_events ──N:1── devices
exam_sessions ──1:N── group_events
exam_sessions ──1:N── alerts

detection_events ──N:1(opt)── group_events
alerts ──► detection_event (1) XOR group_event (1)

audit_logs (standalone)
```

> Voice channels are **not** in the data model — the hall voice subsystem (§9) is
> stateless and writes nothing to the DB.

**Core fields by table:**

- **institutions** — `name`, `code`, `contact_email`, `logo_url`, `address`.
- **halls** — `institution_id`, `name`, `building`, `floor`, `capacity`, `layout_map`
  (JSON), `image`, `status` (`ready`/`not_ready`/...).
- **devices** — `hall_id`, `type` (`camera`/`microphone`), `identifier`, `ip_address`,
  `stream_url`, `position` (JSON), `coverage_area` (JSON), `status`, `last_health_check`.
- **users** — `institution_id`, `username` (unique), `password_hash`, `full_name`,
  `email`, `phone`, `image`, `role`, `status`. *(The old `ptt_id` column was dropped by
  migration `20260604_remove_ptt`; the voice subsystem identifies users by `username`.)*
- **refresh_tokens** — `user_id`, `token_hash`, `expires_at`, `revoked_at`,
  `replaced_by_hash`.
- **exam_sessions** — `exam_name`, `exam_type`, `scheduled_start/end`,
  `actual_start/end`, `status` (`scheduled`/`active`/`completed`/`cancelled`),
  `student_count`, `configuration` (JSON), `created_by`. Many-to-many with halls.
- **assignments** — `exam_session_id`, `invigilator_id`, `hall_id`, `role`
  (`primary`/`secondary`), `monitoring_started_at`, `monitoring_ended_at`.
- **detection_events** — `exam_session_id`, `device_id?`, `group_id?`, `event_type`
  (`head_pose`/`gaze_alignment`/`audio_anomaly`/`object_detected`/...), `severity`,
  `student_position` (JSON), `timestamp`, `confidence_score`, `video_clip_path`,
  `audio_clip_path`, `metadata_json`.
- **group_events** — `exam_session_id`, `event_type`, `severity`, `student_positions`
  (JSON).
- **alerts** — `exam_session_id`, `detection_event_id?`, `group_event_id?`, `alert_type`
  (`tier_1`/`tier_2`), `status`, `claimed_by/at`, `resolved_at`, `resolution_notes`,
  `escalated`, `confirmed_by/at`, `cancelled_by/at`.

### Planned tables (RF subsystem — see §16)
`rf_scanners`, `rf_detections`, `rf_whitelist_entries`.

---

## 12. Backend API Surface

Routers are mounted in `src/thaqib/main.py`:

| Prefix | Purpose |
|---|---|
| `/api/v1/voice` | Stateless hall voice channel WebSocket (`/ws/{hall_id}`) |
| `/api/setup` | First-run install wizard |
| `/api/auth` | Login, logout, refresh, `/me`, CSRF |
| `/api/institutions` | Institution CRUD |
| `/api/halls` | Hall CRUD + readiness |
| `/api/devices` | Camera/mic registration + health |
| `/api/users` | User management (RBAC) |
| `/api/sessions` | Exam sessions, assignments, monitoring start/stop, **report** |
| `/api/events` | Detection event ingestion (CSRF-exempt, token-guarded) |
| `/api/alerts` | Alert confirm/cancel/claim/escalate |
| `/api/stream` | MJPEG feeds, monitoring/alerts/status polling |
| `/api/settings` | Runtime settings (writes `.env`-style values) |
| `/uploads` | Static evidence files (clips, snapshots) |

**Middleware:** security headers (CSP, X-Frame-Options, HSTS, nosniff), CSRF enforcement
for cookie-authenticated unsafe methods (login/setup/events exempt), CORS restricted to
configured origins, slowapi rate limiting.

**Session report** (`GET /api/sessions/{id}/report`) aggregates alerts, resolutions, and
response times for post-exam review.

---

## 13. Frontend Application

`frontend/src/` — React 19 + TypeScript + Tailwind 4, RTL Arabic.

**Admin / referee (`DashboardPage.tsx`):**
- Tabs: Home, Halls, Exams, Supervisors, Settings.
- Live hall grid, alert stack, per-camera stats, alert review (confirm/cancel),
  per-hall voice control (hold-to-talk via `useHallVoice`).

**Invigilator:**
- `SchedulePage` — assigned sessions.
- `HallMonitoringPage` — live MJPEG feed, readiness check, start/stop monitoring,
  alert timeline, floating hold-to-talk voice button, voice connection badge.

**Setup wizard** — institution + admin + halls bootstrap.

**API config (`config/api.ts`):** `authFetch` injects CSRF header and credentials;
`wsOrigin()` builds the voice WebSocket URL.

---

## 14. Security

- **Auth:** JWT access token (cookie, 30 min) + refresh token (7 days, hashed, rotatable
  via `refresh_tokens`).
- **CSRF:** double-submit cookie + `X-CSRF-Token` header on unsafe cookie-auth requests.
- **RBAC:** `RequireRole` dependency; invigilators scoped to assigned halls.
- **Rate limiting:** slowapi (e.g., session creation, assignments).
- **Headers:** CSP, HSTS, X-Frame-Options DENY, X-Content-Type-Options nosniff.
- **Production guards:** Pydantic validator rejects default `SECRET_KEY`, missing
  `INTERNAL_EVENT_TOKEN`, wildcard CORS, and `SameSite=None` without `Secure`.
- **Privacy:** evidence captured only during active sessions; landmark-based gaze
  (geometry, not pixels) avoids appearance bias; audio uses energy/transcript features
  with no speaker identification.

---

## 15. Anti-Cheating Signal Strategy

**Design decision: Thaqib does NOT jam signals — it detects them.**

Rationale (the system runs entirely on WiFi):

- The cameras, the invigilator's tablet, and the dashboard all communicate over WiFi.
- A full-spectrum jammer would kill **its own monitoring system** — jamming WiFi takes the
  cameras and tablet offline; jamming 2.4 GHz also kills the invigilator's Bluetooth
  earbuds.
- Therefore jamming and monitoring **cannot coexist** in the same room at the same
  frequencies.

**Adopted approach — passive RF detection (see §16):** rather than block signals, listen
for them. Detect any device that activates during the exam and alert the invigilator, who
responds in person. This keeps WiFi, cameras, and invigilator comms fully functional.

**The cheating vector still breaks** because the invigilator is directed to the exact seat;
the student cannot use a device once an invigilator is standing over them. Wired earbuds
(no RF) are covered by the **camera** and **audio** pipelines instead.

> If an institution insists on physical jamming, it requires (in Egypt) an **NTRA permit**,
> and the only workable engineering compromises are: run the whole system on **5 GHz WiFi**
> while jamming **cellular + 2.4 GHz only**, with the invigilator on a **wired headset**.
> This is documented as an alternative, not the default design.

---

## 16. RF Device Detection Subsystem — PLANNED

**Goal:** detect any wireless device (phone, Bluetooth earbud, smartwatch) that activates
inside a hall during an exam, without jamming.

### Hardware (per hall)
- **3 × ESP32-WROOM-32** nodes (BLE scan + WiFi reporting), front-left, front-right,
  rear-center — enables RSSI triangulation to a seating zone.
- 5 V USB power per node.
- *(Optional)* RTL-SDR + Raspberry Pi Zero 2 W for wider-spectrum (cellular-energy)
  sensing.
- Approx cost: ~$35/hall (BLE), ~$80/hall (with SDR).

### Data flow
```
ESP32 nodes (passive BLE scan)
   │  batch every ~3 s, POST over WiFi
   ▼
POST /api/v1/rf-push/{scanner_id}/detections   (pre-shared key auth)
   │
   ▼
Whitelist check + RSSI→zone estimate
   │
   ├─ whitelisted / weak signal → record only
   └─ unknown & strong → DetectionEvent(event_type="rf_transmission")
                              → Alert (tier_2) → WebSocket → dashboard
```

### Lifecycle
- **Pre-exam baseline (~5 min):** admin starts a baseline scan; everything currently
  broadcasting (tablet, invigilator earbuds, cameras, AP) is added to the hall whitelist.
- **During exam:** any non-whitelisted device, or a whitelisted device whose RSSI
  **jumps** (hidden earbud powering on), fires an alert carrying the advertised device
  name and estimated zone.

### Planned tables
- **rf_scanners** — `hall_id`, `identifier`, `position` (JSON), `ip_address`,
  `api_key_hash`, `status`, `last_seen`.
- **rf_detections** — `scanner_id`, `exam_session_id?`, `detected_at`, `signal_type`,
  `mac_hash` (SHA-256 — never store raw MAC), `device_name?`, `rssi`, `is_whitelisted`,
  `estimated_zone?`, `metadata_json`.
- **rf_whitelist_entries** — `hall_id`, `mac_hash`, `device_name?`, `device_role`,
  `added_by`, `expires_at`.

### Integration
RF hits reuse the **existing** `DetectionEvent → Alert → WebSocket` pipeline — no new alert
machinery. A new `event_type = "rf_transmission"` and a dashboard RF badge are the only
additions on the consuming side.

### Coverage
Catches active BLE/WiFi devices (named earbuds, phones coming off airplane mode). Does
**not** catch fully passive wired earbuds — those remain the responsibility of the camera
earbud-detection model and the audio pipeline.

### Build order
1. Models + Alembic migration.
2. `/api/v1/rf-push` ingest endpoint + whitelist logic + zone estimation.
3. Alert integration (`rf_transmission`).
4. Scanner firmware (`scanner_node/main.py` + `config.json`).
5. Dashboard RF badge + baseline-scan controls.

---

## 17. Deployment & Running the System

**Development (local).** Three processes, fixed port convention:

| Process | Port | Notes |
|---|---|---|
| Camera simulator | `8000` | Serves MJPEG feeds; seeded `Device.stream_url`s point here. |
| Backend API (uvicorn) | `8001` | FastAPI app. |
| Frontend (Vite) | `5173` | Proxies `/api` → `127.0.0.1:8001`. |

```powershell
# Camera simulator (feeds) — port 8000
python -m uvicorn simulator.main:app --host 0.0.0.0 --port 8000

# Backend API — port 8001
python -m uvicorn src.thaqib.main:app --reload --host 0.0.0.0 --port 8001

# Frontend (Vite) — port 5173, proxies /api → 127.0.0.1:8001
cd frontend; npm run dev -- --host
```

- The Vite dev server proxies `/api` (including WebSocket upgrades, `ws: true`) to the
  backend on **8001**. **The proxy target must match the uvicorn API port (8001).** A
  mismatch silently breaks every API call and the voice socket. Note 8000 is the
  *simulator*, not the API.
- CORS origins must include the frontend origin (`http://localhost:5173`).
- Database defaults to SQLite at `./data/thaqib.db`; set `DATABASE_URL` to PostgreSQL for
  production (see the Database subsection below).
- Mobile microphone access (voice transmit) requires a **secure context** — use HTTPS
  (e.g., a Cloudflare quick tunnel) or `localhost`. Receive-only works over plain LAN.

**Seeding a demo:** run the setup wizard first (creates institution, admin, hall named
`قاعة 101`, and an `invigilator` user), then `python seed_demo.py` to create the demo exam
session + assignment.

### Database: SQLite (dev) / PostgreSQL (production)

The system is **DB-agnostic** via SQLAlchemy + Alembic; the database is selected entirely
by `DATABASE_URL` (no code change needed). `db/database.py` configures the engine
conditionally:

- **SQLite** (dev default, `sqlite:///./data/thaqib.db`): `check_same_thread=False` so the
  engine is shared across FastAPI's thread pool. SQLite serializes writes (single writer)
  — fine for development and the test suite.
- **PostgreSQL** (production / pilot): `pool_pre_ping=True`, `pool_size=10`,
  `max_overflow=20`, `pool_recycle=1800`. PostgreSQL provides true concurrent writes
  (MVCC), which is **required** under live multi-hall detection-event load — SQLite would
  hit `database is locked` errors when several halls' detection streams write at once.

**Why production uses PostgreSQL:** the detection engine writes `DetectionEvent`s
continuously during exams, concurrently with alert updates and dashboard reads. This is a
concurrent-writer workload that SQLite cannot serve reliably.

**Provisioning (Docker):** `docker-compose.yml` provides PostgreSQL 15 + PgAdmin:

```powershell
docker compose up -d db                # Postgres on localhost:5433, PgAdmin on :5050
$env:DATABASE_URL = "postgresql+psycopg2://thaqib_admin:development_password@localhost:5433/thaqib_production"
python -m alembic upgrade head         # apply the full migration chain
```

> The full migration chain has been verified end-to-end against PostgreSQL 15 (including
> the `batch_alter_table` operations and the `20260604_remove_ptt` drops). On Postgres all
> `DateTime(timezone=True)` columns become real `timestamptz`.

**Timezone discipline:** because Postgres uses real `timestamptz`, all DB-written datetimes
must be **UTC-aware** (`datetime.now(timezone.utc)`), never naive `datetime.now()`. Runtime
writes (auth, alerts, devices, monitoring start/stop) and the seed scripts follow this.
Naive `datetime.now()` is only used for human-readable **filenames** (recordings, clips),
which is intentional and not DB-bound.

---

## 18. Configuration Reference

All settings live in `src/thaqib/config/settings.py` and are overridable via `.env`.
Highlights (defaults shown):

**Video:** `detection_confidence=0.15`, `detection_imgsz=640`, `tools_confidence=0.45`,
`neighbor_k=6`, `risk_angle_tolerance=25.0`, `suspicious_duration_threshold=2.0`,
`reid_match_threshold=0.80`, `face_mesh_workers=4`, `yolo_model=models/yolo11m.pt`,
`tools_model=models/best.pt`.

**Audio:** `audio_whisper_model=tiny`, `audio_language=ar`, `audio_strict_mode=true`,
`audio_chunk_ms=500`, `audio_vad_threshold=0.5`, `audio_calibration_chunks=30`,
`audio_local_ratio_multiplier=2.0`, `audio_clip_sec_before/after=2.0`,
`audio_episode_min_sec=3.0`, `audio_session_recording=true`.

**Server/security:** `server_port=8000`, `access_token_expire_minutes=30`,
`refresh_token_expire_days=7`, `access_cookie_name=thaqib_access_token`,
`csrf_cookie_name=thaqib_csrf_token`, `cookie_secure=false` (dev),
`cors_origins=[localhost:5173, 127.0.0.1:5173, localhost:3000]`.

**Output:** `video_quality=75`, `alert_max_height=720`, `archive_mode=raw`.

---

## 19. Evidence & Forensics

- **Video alert clips:** annotated MP4 with a RED box on the flagging student and a YELLOW
  box on the target neighbor's paper, with 2 s pre/post buffers. Stored under `alerts/`.
- **Audio alert clips:** WAV + JSON metadata (transcript, keywords, confidence, SHA-256).
  Stored under `audio alerts/`; full sessions under `sessions/`.
- **Voice channel:** live only — no recordings are stored (the subsystem is stateless).
- **Continuous archive:** raw (or annotated) camera recordings under `archive/`.
- **SHA-256 hashing** on audio evidence provides chain-of-custody integrity.

All evidence is generated only during active, scheduled sessions and is intended for human
review — consistent with the human-in-the-loop, no-automatic-sanctions policy.
