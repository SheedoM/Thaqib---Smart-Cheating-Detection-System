# Thaqib — Project Management

> **Methodology:** Agile Scrum
> **Sprint Duration:** 1 week
> **Last Updated:** 2026-03-19

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
| US-101 | As an **invigilator**, I want the system to capture stable video from webcams and RTSP cameras so that exam halls are continuously monitored | 🔄 In Progress | | |
| US-102 | As an **invigilator**, I want the system to detect and track students across frames (YOLOv8 + BoT-SORT) with consistent identity so that each student's behavior is monitored individually without ID swaps | 🔄 In Progress | | |
| US-103 | As an **invigilator**, I want the system to estimate each student's head pose (yaw/pitch/roll) and eye gaze direction so that I can determine where a student is looking | 🔄 In Progress | | |
| US-104 | As an **invigilator**, I want the system to identify neighboring students, compute proximity, and determine risk angles toward neighbor paper zones so that potential cheating interactions are flagged | 🔄 In Progress | | |
| US-105 | As a **developer**, I want an integrated video pipeline (detection → tracking → pose → gaze → neighbor risk) so that all vision stages run end-to-end in a single processing loop | 🔄 In Progress | | |
| US-106 | As an **invigilator**, I want real-time visualization overlays (bounding boxes, gaze arrows, risk highlights) on the video feed so that I can visually assess the exam hall at a glance | 🔄 In Progress | | |
| US-107 | As an **invigilator**, I want to select specific students for monitoring and have the system localize their paper zones so that detection is focused on candidates of concern | 📋 To Do | | |
| US-108 | As a **developer**, I want per-student features and suspicious gaze events (duration thresholds, match ratios) logged to CSV so that detection data is available for analysis and model refinement | 📋 To Do | | |
| US-109 | As an **admin**, I want multi-camera support with camera switching and GPU-accelerated inference so that the system scales to large exam halls in production | 📋 To Do | | |

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
| US-201 | As a **developer**, I want the system to capture real-time audio from USB microphones and segment it into fixed-duration windows so that audio can be processed in discrete, analyzable chunks | 🔄 In Progress | | |
| US-202 | As a **developer**, I want the system to extract low-level audio features (intensity, activity detection) and filter silence against a baseline ambient noise model so that only meaningful audio is passed to classifiers | 🔄 In Progress | | |
| US-203 | As an **invigilator**, I want the system to detect whispers and speech using a trained classifier, with optional keyword-based indicators, so that verbal cheating attempts are identified | 📋 To Do | | |
| US-204 | As an **invigilator**, I want microphones spatially mapped to student groups (audio zones) with cross-microphone validation so that detected audio events are attributed to the correct area and distinguished from ambient noise | 📋 To Do | | |
| US-205 | As a **developer**, I want audio events characterized (duration, repetition, patterns) and logged to CSV per microphone so that temporal audio data is available for analysis and fusion with video events | 📋 To Do | | |

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
| US-301 | As a **developer**, I want a FastAPI application with CORS middleware and pydantic-settings configuration (.env) so that the backend is properly bootstrapped and configurable | ✅ Done | | |
| US-302 | As an **invigilator**, I want a Push-to-Talk WebSocket endpoint with a connection manager (connect, disconnect, broadcast) so that two-way audio communication works in real time between the control room and exam halls | ✅ Done | | |
| US-303 | As a **developer**, I want the full database schema (Institution, Hall, Device, User, ExamSession, Assignment, DetectionEvent, GroupEvent, Alert, AuditLog) with Alembic migrations so that all data is persisted and the schema is version-controlled | ✅ Done | | |
| US-304 | As an **admin**, I want JWT-based authentication with token refresh and role-based access control (admin, referee, invigilator) so that only authorized users can access their permitted resources | ✅ Done | | |
| US-305 | As an **admin**, I want a system installation/setup API endpoint so that the institution and initial admin account can be created during first-time setup | ✅ Done | | |
| US-306 | As an **admin**, I want CRUD APIs for institutions, halls, devices (with health-check), and users/staff so that all organizational resources can be managed through the dashboard | ✅ Done | | |
| US-307 | As an **admin**, I want exam session CRUD, scheduling, and invigilator assignment APIs so that exams can be planned and staffed through the system | ✅ Done | | |
| US-308 | As a **developer**, I want a detection event ingestion API and real-time alert broadcast via WebSocket so that pipeline alerts are persisted and pushed to the dashboard instantly | ✅ Done | | |
| US-309 | As a **developer**, I want a multi-modal correlation engine that fuses video and audio events so that combined evidence produces more accurate cheating alerts | 📋 To Do | | |
| US-310 | As an **admin**, I want a session report generator with PDF export so that post-exam reports can be reviewed and archived | 📋 To Do | | |
| US-311 | As a **developer**, I want security hardening (rate limiting, auth refresh, input validation) so that the API is protected against abuse and common attack vectors | ✅ Done | | |

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
| US-401 | As a **developer**, I want the Vite + React + Tailwind project scaffolded with React Router, an API integration layer (Axios/fetch with auth interceptors), and global state management (auth & WebSocket contexts) so that the frontend has a solid foundation for all features | ✅ Done | | |
| US-402 | As an **admin**, I want an Installation/Setup Wizard page so that I can configure the institution and create the first admin account on initial deployment | 🔄 In Progress | | |
| US-403 | As a **user**, I want a login page with JWT authentication so that I can securely access the system based on my role | ✅ Done | | |
| US-404 | As an **admin**, I want a dashboard home page with overview stats, quick actions, and KPI widgets so that I can see the system status at a glance | 📋 To Do | | |
| US-405 | As an **admin**, I want management pages for halls, devices (cameras & mics per hall with health status), and staff/users (CRUD with role assignment) so that I can configure all organizational resources from the dashboard | 📋 To Do | | |
| US-406 | As an **admin**, I want an exam session scheduling page to create sessions and assign halls & invigilators so that exams are properly planned within the system | 📋 To Do | | |
| US-407 | As an **invigilator**, I want a live monitoring control room with a hall grid overview and per-hall camera feeds with an event timeline so that I can observe all exam halls and drill into individual halls in real time | 📋 To Do | | |
| US-408 | As an **invigilator**, I want a real-time alert feed/timeline and push-to-talk audio controls so that I can receive cheating alerts instantly and communicate with halls | 📋 To Do | | |
| US-409 | As an **admin**, I want a history & reports page with search and a session detail/summary report view so that past exam sessions can be reviewed and audited | 📋 To Do | | |
| US-410 | As an **admin**, I want a settings & management panel for detection thresholds and system configuration so that I can tune the system's sensitivity and behavior | 📋 To Do | | |
| US-411 | As an **invigilator**, I want a personal schedule view ("My Schedule" dashboard) and a responsive mobile view with haptic alerts so that I can check my assignments and receive notifications on the go | 📋 To Do | | |

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
| US-501 | As a **developer**, I want a "Solo Station" launcher and Docker Compose setup (backend + frontend + database) with environment/secrets management so that the full system can be started with a single command on one machine | 📋 To Do | | |
| US-502 | As a **developer**, I want automated device health checks, centralized logging, and error monitoring so that system issues are detected and diagnosed quickly | 📋 To Do | | |
| US-503 | As a **developer**, I want a CI/CD pipeline (lint, test, build) and a production deployment guide so that releases are automated and deployments are reproducible | 📋 To Do | | |
| US-504 | As a **developer**, I want RTSP camera & USB mic hardware integration testing and system endurance testing (2+ hour sessions) so that the system is validated against real hardware under sustained load | 📋 To Do | | |
| US-505 | As an **admin**, I want disaster recovery procedures and session data backup so that exam data is protected against system failures | 📋 To Do | | |

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
| `feat/backend-setup-api` | DB schema, Auth, RBAC, Installation APIs | ✅ Merged |
| `feat/frontend-installation-page` | React installation UI + backend setup | 🔄 Active |

---

## Known Issues

1. **MediaPipe Version**: Must use 0.10.30+ (Tasks API, not legacy solutions)
2. **Model Download**: `face_landmarker.task` auto-downloads to `models/` folder on first run
3. **Audio branch divergence**: `audio-model` branch is heavily diverged from `main` — needs careful merge strategy
