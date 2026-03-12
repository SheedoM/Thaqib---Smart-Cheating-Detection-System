# Thaqib — Project Management

> **Methodology:** Agile Scrum
> **Sprint Duration:** 1 week
> **Last Updated:** 2026-03-12

---

## How to Read This Document

| Symbol | Status |
|--------|--------|
| `✅ Done` | Completed and merged/verified |
| `🔄 In Progress` | Actively being worked on |
| `📋 To Do` | Not yet started |

**Epics:** 🎥 Video Detection · 🎙️ Audio Detection · ⚙️ Backend & APIs · 🖥️ Frontend & Dashboard · 🐳 Integration & DevOps

---

## Epic Overview

| Epic | Domain | Status | Description |
|------|--------|--------|-------------|
| **E1** | 🎥 Video Detection Engine | 🔄 In Progress | CV pipeline: human detection, tracking, head pose, gaze estimation, neighbor modeling |
| **E2** | 🎙️ Audio Detection Engine | 🔄 In Progress | Real-time audio capture, whisper detection, zone-based spatial analysis |
| **E3** | ⚙️ Backend & APIs | 🔄 In Progress | FastAPI server, database, authentication, WebSocket, RBAC, event ingestion |
| **E4** | 🖥️ Frontend & Dashboard | 🔄 In Progress | React web dashboard — all pages, components, and UI interactions |
| **E5** | 🐳 Integration & DevOps | 📋 To Do | System launcher, Docker, deployment, setup wizard, health checks |

---

## E1 — 🎥 Video Detection Engine

### User Stories

| ID | Story | Status | Assignee | Deadline |
|----|-------|--------|----------|----------|
| US-101 | Camera stream capture with webcam & RTSP support | 🔄 In Progress | | |
| US-102 | Human detection using YOLOv8 (periodic detection) | 🔄 In Progress | | |
| US-103 | Multi-object tracking with identity continuity (BoT-SORT) | 🔄 In Progress | | |
| US-104 | Facial geometry construction & head pose estimation (yaw/pitch/roll) | 🔄 In Progress | | |
| US-105 | Local eye gaze estimation & final gaze direction fusion | 🔄 In Progress | | |
| US-106 | Neighbor identification & distance-based proximity modeling | 🔄 In Progress | | |
| US-107 | Risk angle computation for neighbor paper zones | 🔄 In Progress | | |
| US-108 | Integrated video pipeline (detection → tracking → pose → gaze → risk) | 🔄 In Progress | | |
| US-109 | Student re-identification across frames | 🔄 In Progress | | |
| US-110 | Real-time visualization overlay (bounding boxes, gaze arrows, alerts) | 🔄 In Progress | | |
| US-111 | Human-in-the-loop candidate selection (select monitored students) | 📋 To Do | | |
| US-112 | Student paper zone localization | 📋 To Do | | |
| US-113 | Feature logging to CSV (per-student temporal data) | 📋 To Do | | |
| US-114 | Suspicious gaze detection rules (duration threshold, match ratio) | 📋 To Do | | |
| US-115 | Multi-camera support and camera switching | 📋 To Do | | |
| US-116 | GPU-accelerated inference for production | 📋 To Do | | |

### Acceptance Criteria

- Camera captures stable frames at configured FPS from webcam or RTSP
- YOLO detects humans with ≥ 50% confidence; bounding boxes are stable
- Tracker maintains consistent IDs for ≥ 10 minutes without ID swaps
- Head pose returns yaw/pitch/roll angles within ±5° accuracy
- Neighbor model identifies the k-nearest students within distance threshold
- Risk angles correctly point toward neighbor paper zones
- Pipeline processes frames at ≥ 15 FPS on target hardware

---

## E2 — 🎙️ Audio Detection Engine

### User Stories

| ID | Story | Status | Assignee | Deadline |
|----|-------|--------|----------|----------|
| US-201 | Real-time audio capture from USB microphones | 🔄 In Progress | | |
| US-202 | Audio temporal segmentation into fixed-duration windows | 🔄 In Progress | | |
| US-203 | Low-level audio feature extraction (intensity, activity detection) | 🔄 In Progress | | |
| US-204 | Silence filtering & baseline ambient noise modeling | 📋 To Do | | |
| US-205 | Whisper / speech detection classifier | 📋 To Do | | |
| US-206 | Microphone-to-student-group spatial mapping (audio zones) | 📋 To Do | | |
| US-207 | Cross-microphone validation (local vs. global noise) | 📋 To Do | | |
| US-208 | Audio event characterization (duration, repetition, patterns) | 📋 To Do | | |
| US-209 | Keyword-based audio indicators (optional) | 📋 To Do | | |
| US-210 | Audio feature logging to CSV (per-microphone temporal data) | 📋 To Do | | |
| US-211 | Multi-microphone support with zone-based attribution | 📋 To Do | | |

### Acceptance Criteria

- Microphone captures audio without dropped frames at target sample rate
- Whisper detection achieves ≥ 80% recall with < 20% false positive rate
- Cross-microphone validation correctly distinguishes local vs. ambient noise
- Audio events are time-aligned with video frames for fusion

---

## E3 — ⚙️ Backend & APIs

### User Stories

| ID | Story | Status | Assignee | Deadline |
|----|-------|--------|----------|----------|
| US-301 | FastAPI application setup with CORS middleware | ✅ Done | | |
| US-302 | Configuration management with pydantic-settings & .env | ✅ Done | | |
| US-303 | Push-to-Talk WebSocket endpoint (2-way audio routing) | ✅ Done | | |
| US-304 | WebSocket connection manager (connect, disconnect, broadcast) | ✅ Done | | |
| US-305 | Database schema — all core models (Institution, Hall, Device, User, ExamSession, Assignment, DetectionEvent, GroupEvent, Alert, AuditLog) | 🔄 In Progress | | |
| US-306 | Alembic migration setup & initial migration | 🔄 In Progress | | |
| US-307 | Authentication API (JWT login, token refresh) | 🔄 In Progress | | |
| US-308 | Role-based access control (admin, referee, invigilator) | 🔄 In Progress | | |
| US-309 | System installation/setup API endpoint | 🔄 In Progress | | |
| US-310 | Institution CRUD API | 🔄 In Progress | | |
| US-311 | Hall CRUD API | 🔄 In Progress | | |
| US-312 | Device registration & health-check API | 📋 To Do | | |
| US-313 | User / staff management API | 📋 To Do | | |
| US-314 | Exam session CRUD & scheduling API | 📋 To Do | | |
| US-315 | Invigilator assignment API | 📋 To Do | | |
| US-316 | Detection event ingestion API (receive alerts from pipelines) | 📋 To Do | | |
| US-317 | Real-time alert broadcast via WebSocket (push to dashboard) | 📋 To Do | | |
| US-318 | Multi-modal correlation engine (video + audio event fusion) | 📋 To Do | | |
| US-319 | Session report generator (PDF export) | 📋 To Do | | |
| US-320 | Security hardening (rate limiting, auth refresh, input validation) | 📋 To Do | | |

### Acceptance Criteria

- All CRUD endpoints return correct status codes and validated responses
- JWT auth works end-to-end with proper role-based route protection
- WebSocket connections are stable for ≥ 2 hours without memory leaks
- Alembic migrations run cleanly on a fresh database
- Detection events are persisted within < 100ms of receipt

---

## E4 — 🖥️ Frontend & Dashboard

### Tech Stack

- **Framework:** React 19 + TypeScript + Vite
- **Styling:** Tailwind CSS v4
- **Icons:** Lucide React

### User Stories

| ID | Story | Status | Assignee | Deadline |
|----|-------|--------|----------|----------|
| US-401 | Vite + React + Tailwind project setup | ✅ Done | | |
| US-402 | Installation / Setup Wizard (institution + admin creation) | 🔄 In Progress | | |
| US-403 | Login page | 📋 To Do | | |
| US-404 | Admin dashboard home (overview, stats, quick actions) | 📋 To Do | | |
| US-405 | Hall management page (list, add, edit, delete halls) | 📋 To Do | | |
| US-406 | Device registration page (cameras & mics per hall, health status) | 📋 To Do | | |
| US-407 | Staff / user management page (CRUD invigilators, role assignment) | 📋 To Do | | |
| US-408 | Exam session scheduling page (create, assign hall & invigilator) | 📋 To Do | | |
| US-409 | Live monitoring dashboard — control room (hall grid overview) | 📋 To Do | | |
| US-410 | Individual hall monitoring page (camera feeds + event timeline) | 📋 To Do | | |
| US-411 | Real-time alert feed & timeline component | 📋 To Do | | |
| US-412 | PTT controls component (push-to-talk UI for WebSocket audio) | 📋 To Do | | |
| US-413 | History & reports page (past sessions, searchable) | 📋 To Do | | |
| US-414 | Session detail / summary report page | 📋 To Do | | |
| US-415 | Settings & management panel (detection thresholds, system config) | 📋 To Do | | |
| US-416 | Invigilator schedule view ("My Schedule" dashboard) | 📋 To Do | | |
| US-417 | Mobile invigilator view (responsive, haptic alerts) | 📋 To Do | | |
| US-418 | React Router setup & navigation (sidebar, role-based routes) | 📋 To Do | | |
| US-419 | API integration layer (Axios/fetch service, auth interceptors) | 📋 To Do | | |
| US-420 | Global state management (auth context, WebSocket context) | 📋 To Do | | |

### Page / Component Checklist

Use this checklist to track individual UI page and component completion:

#### Pages
- [ ] Installation / Setup Wizard
- [ ] Login Page
- [ ] Admin Dashboard Home
- [ ] Hall Management (List + CRUD)
- [ ] Device Registration (per-hall)
- [ ] Staff / User Management
- [ ] Exam Session Scheduling
- [ ] Live Monitoring Dashboard (Control Room — Hall Grid)
- [ ] Individual Hall Monitoring (Camera Feeds + Timeline)
- [ ] History & Reports
- [ ] Session Detail Report
- [ ] Settings & Management Panel
- [ ] Invigilator Schedule View
- [ ] Mobile Invigilator View

#### Shared Components
- [ ] Sidebar Navigation
- [ ] Top Header / Navbar
- [ ] Alert Card Component
- [ ] Camera Feed Tile
- [ ] PTT (Push-to-Talk) Button
- [ ] Hall Status Card
- [ ] Stats / KPI Widget
- [ ] Data Table (sortable, filterable)
- [ ] Modal / Dialog
- [ ] Toast / Notification System
- [ ] Loading Skeleton
- [ ] Form Components (inputs, selects, file upload)

### Acceptance Criteria

- All pages render without errors on latest Chrome/Firefox/Edge
- Forms validate inputs before submission
- WebSocket data appears on dashboard within < 2 seconds of event
- Responsive design works on screens from 768px to 2560px width
- Arabic RTL layout support where applicable

---

## E5 — 🐳 Integration & DevOps

### User Stories

| ID | Story | Status | Assignee | Deadline |
|----|-------|--------|----------|----------|
| US-501 | "Solo Station" launcher (start full stack on one machine) | 📋 To Do | | |
| US-502 | Docker Compose setup (backend + frontend + database) | 📋 To Do | | |
| US-503 | Environment configuration & secrets management | 📋 To Do | | |
| US-504 | Automated device health-check system | 📋 To Do | | |
| US-505 | Centralized logging & error monitoring | 📋 To Do | | |
| US-506 | CI/CD pipeline (lint, test, build) | 📋 To Do | | |
| US-507 | Production deployment guide | 📋 To Do | | |
| US-508 | RTSP camera & USB mic hardware integration testing | 📋 To Do | | |
| US-509 | System endurance testing (2+ hour sessions) | 📋 To Do | | |
| US-510 | Disaster recovery & session data backup | 📋 To Do | | |

### Acceptance Criteria

- Full system starts with a single command
- Docker Compose brings up all services in < 2 minutes
- System runs stable for ≥ 2 hours without memory leaks or crashes
- Health checks detect and report offline devices within 30 seconds

---

## Sprint Planning Template

Use this template at the start of each weekly sprint:

### Sprint N — [Start Date] → [End Date]

**Sprint Goal:** _[One sentence describing the sprint objective]_

| Story ID | Story Title | Assignee | Points | Status |
|----------|------------|----------|--------|--------|
| US-XXX | ... | ... | ... | 📋 To Do |

**Velocity (previous sprint):** _[X] points completed_
**Capacity:** _[X] points planned_

---

## Definition of Done

A user story is considered **Done** when:

1. ✅ Code is written and follows project conventions
2. ✅ Code is reviewed (or self-reviewed for solo work)
3. ✅ Feature is tested (manual or automated)
4. ✅ Branch is merged to `main` (or target branch)
5. ✅ No known regressions introduced
6. ✅ Documentation updated if applicable

---

## Active Branches

| Branch | Purpose | Status |
|--------|---------|--------|
| `main` | Stable release branch | Base |
| `feature/video-detection` | Advanced video pipeline (BoT-SORT, face mesh, re-ID, visualizer) | 🔄 Active |
| `audio-model` | Audio detection model development | 🔄 Active |
| `feat/backend-setup-api` | DB schema, Auth, RBAC, Installation APIs | 🔄 Active |
| `feat/frontend-installation-page` | React installation UI + backend setup | 🔄 Active |

---

## Known Issues

1. **MediaPipe Version**: Must use 0.10.30+ (Tasks API, not legacy solutions)
2. **Model Download**: `face_landmarker.task` auto-downloads to `models/` folder on first run
3. **Audio branch divergence**: `audio-model` branch is heavily diverged from `main` — needs careful merge strategy
