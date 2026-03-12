# Thaqib — Software Requirements Specification (SRS)

> **Version:** 1.0
> **Last Updated:** 2026-03-13
> **Status:** Authoritative Reference
>
> This document is the **single source of truth** for the Thaqib system. All other documents (architecture, UML diagrams, UI designs) should be derived from this SRS.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Overall Description](#2-overall-description)
3. [Functional Requirements](#3-functional-requirements)
4. [Non-Functional Requirements](#4-non-functional-requirements)
5. [Data Requirements](#5-data-requirements)
6. [External Interface Requirements](#6-external-interface-requirements)
7. [User Journey](#7-user-journey)
8. [Future Scope](#8-future-scope)
9. [Glossary](#9-glossary)

---

## 1. Introduction

### 1.1 Purpose

This document defines the complete software requirements for **Thaqib** (ثاقب — Arabic for "piercing" / "sharp-sighted"), an AI-powered real-time exam monitoring system. It serves as the authoritative reference for all design, development, and testing activities.

### 1.2 Product Overview

Thaqib assists human invigilators in detecting suspicious behaviors during examinations using AI-driven video and audio analysis. The system operates as a **decision-support tool** — it highlights suspicious situations for human review but **never makes autonomous decisions**. This approach is analogous to VAR (Video Assistant Referee) in football.

The system integrates data from **IP cameras** and **microphones** installed inside examination halls. Computer vision algorithms analyze head movements, gaze direction, and detect unauthorized objects, while audio analysis detects suspicious sounds. All processing is **real-time** — alerts are generated immediately and routed to a control room for human evaluation.

### 1.3 Scope

**In scope (MVP):**
- Real-time video monitoring and suspicious behavior detection
- Real-time audio monitoring and anomaly detection
- Unauthorized object detection (phones, books, notes)
- Web-based control room dashboard with shared alert queue
- Push-to-Talk communication between control room and invigilators
- Exam session management and scheduling
- Hall and device management
- Session reports and history
- Seat-based student tracking
- Single institution deployment
- On-premise deployment
- Bilingual interface (Arabic + English)
- Support for 1–3 concurrent halls

**Out of scope (MVP):**
- Automated cheating decisions (system never confirms cheating)
- Student identity linking (deferred to future)
- Multi-institution / multi-faculty deployment (deferred)
- Cloud deployment
- Smartwatch / haptic alerts
- Mobile invigilator app
- Speech recognition or keyword detection

### 1.4 Definitions & Acronyms

| Term | Definition |
|------|-----------|
| **Alert** | A system-generated notification triggered by AI-detected suspicious behavior |
| **Detection Event** | A single AI detection (e.g., one head pose violation) |
| **Group Event** | Multiple correlated detection events (e.g., two neighbors looking at each other) |
| **Hall** | A physical examination room equipped with cameras and microphones |
| **PTT** | Push-to-Talk — real-time voice communication via WebSocket |
| **Risk Angle** | The angular direction from a student toward a neighbor's exam paper |
| **Session** | A timed monitoring period for a specific exam in one or more halls |
| **Tier 1 Alert** | Low-severity alert (isolated suspicious behavior) |
| **Tier 2 Alert** | High-severity alert (coordinated, prolonged, or repeated behavior) |

---

## 2. Overall Description

### 2.1 User Roles

The system defines three user roles:

#### 2.1.1 System Administrator

| Attribute | Details |
|-----------|---------|
| **Responsibility** | System infrastructure setup and user management |
| **Activities** | Register institution, manage halls, register devices, create user accounts |
| **Does NOT** | Monitor exams, schedule exams, or interact during active sessions |
| **Access** | Full system configuration; no access to monitoring dashboard |
| **Typical user** | IT staff or designated system manager |

#### 2.1.2 Referee

| Attribute | Details |
|-----------|---------|
| **Responsibility** | Exam scheduling AND real-time monitoring from the control room |
| **Pre-exam activities** | Schedule exam sessions, assign halls, assign invigilators |
| **During-exam activities** | Monitor AI alerts via shared queue, review video clips, make decisions on suspicious behavior, contact invigilators via PTT |
| **Access** | Exam management, monitoring dashboard, alert queue, PTT, reports |
| **Typical user** | Control department staff, exam coordinator |

#### 2.1.3 Invigilator

| Attribute | Details |
|-----------|---------|
| **Responsibility** | Physical presence in the examination hall |
| **Pre-exam activities** | View assigned schedule, review hall layout |
| **During-exam activities** | Receive voice instructions from referees via PTT/earpiece, take physical action (approach student, give warning) |
| **Does NOT** | Make detection decisions or review alerts |
| **Access** | Schedule view, PTT (listen & respond) |
| **Typical user** | Teaching assistant, assigned faculty member |

### 2.2 Alert Flow Model — Shared Alert Queue

The control room operates on a **Shared Alert Queue** model:

```
AI Detection → Alert enters shared queue → Any available referee claims it →
  → Reviews video/context → Decision:
      → Suspicious: PTT call to invigilator with instructions
      → Not suspicious: Dismiss as false positive
      → Unclear: Continue monitoring
```

**Key properties:**
- All active alerts are visible to all logged-in referees
- No pre-assignment of referees to specific halls
- A referee **claims** an alert to review it, preventing duplicate work
- The system requires **at least one referee logged in** for a monitoring session to be active
- Staffing is flexible: 2 referees can cover 5 quiet halls, or 5 referees can cover 1 intense hall

### 2.3 Operating Environment

| Component | Specification |
|-----------|--------------|
| **Deployment** | On-premise (local server within institution network) |
| **Server OS** | Windows or Linux |
| **Server Hardware** | Intel Core i5+, 16 GB RAM, SSD, GPU recommended (NVIDIA with CUDA) |
| **Network** | Wired Ethernet LAN (Cat5e or Cat6) |
| **Cameras** | IP cameras with RTSP streaming, 720p/1080p, 25–30 FPS |
| **Microphones** | USB microphones with noise reduction |
| **Client** | Modern web browser (Chrome, Firefox, Edge) |
| **Network Switch** | Gigabit Ethernet, 5–8+ ports |

### 2.4 Design Constraints

1. **Real-time processing** — alert delivery must be < 5 seconds from detection to dashboard
2. **On-premise only** — no dependency on internet connectivity during exams
3. **Privacy-first** — no raw video or audio recordings stored permanently
4. **Decision-support only** — the system never confirms cheating autonomously
5. **Bilingual** — all UI must support Arabic (RTL) and English (LTR)

### 2.5 Assumptions & Dependencies

1. The institution provides a wired Ethernet network connecting cameras to the server
2. A specialist assesses each hall to determine optimal camera/microphone count and placement
3. At least one referee is present in the control room during active monitoring
4. Invigilators have access to an earpiece or audio device for receiving PTT instructions
5. The server has adequate GPU resources for real-time video inference (if processing multiple halls)

---

## 3. Functional Requirements

### FR-01: System Installation & Setup

| ID | Requirement |
|----|------------|
| FR-01.1 | The system shall provide a first-run **Setup Wizard** that collects institution name and creates the initial admin account |
| FR-01.2 | The Setup Wizard shall not be accessible after initial setup is complete |
| FR-01.3 | The system shall initialize the database schema automatically on first run |

### FR-02: User Authentication & Authorization

| ID | Requirement |
|----|------------|
| FR-02.1 | The system shall authenticate users via username and password |
| FR-02.2 | The system shall issue JWT tokens upon successful authentication |
| FR-02.3 | The system shall enforce role-based access control (RBAC) for three roles: Admin, Referee, Invigilator |
| FR-02.4 | The system shall restrict access to features based on user role as defined in §2.1 |
| FR-02.5 | Sessions shall timeout after a configurable period of inactivity |

### FR-03: Hall & Device Management

| ID | Requirement |
|----|------------|
| FR-03.1 | The admin shall be able to create, edit, and delete halls with attributes: name, building, floor, capacity |
| FR-03.2 | The admin shall be able to register devices (cameras and microphones) to a specific hall |
| FR-03.3 | Each device shall have: type (camera/microphone), IP address, stream URL, position label |
| FR-03.4 | The system shall perform an automated **health check** when a device is registered (ping RTSP/audio stream) |
| FR-03.5 | Device status shall be one of: `online`, `offline`, `error`, `maintenance` |
| FR-03.6 | The system shall run **periodic health checks** (configurable interval) on all registered devices |
| FR-03.7 | A hall's status shall automatically be `ready` when ALL its devices are `online`, and `not_ready` otherwise |
| FR-03.8 | The system shall alert the admin when a device goes offline |

### FR-04: Exam Session Management

| ID | Requirement |
|----|------------|
| FR-04.1 | A referee shall be able to create an exam session with: course name, exam type, date, start time, end time |
| FR-04.2 | An exam session shall be assigned to **one or more halls** (multi-hall exam support) |
| FR-04.3 | Only halls with status `ready` shall be selectable for exam sessions |
| FR-04.4 | The system shall prevent scheduling conflicts (overlapping sessions in the same hall) |
| FR-04.5 | A referee shall assign one or more invigilators to an exam session |
| FR-04.6 | Exam session status shall be one of: `scheduled`, `active`, `completed`, `cancelled` |
| FR-04.7 | A referee shall be able to **start** a monitoring session, which activates all AI pipelines for the assigned halls |
| FR-04.8 | A referee shall be able to **end** a monitoring session manually, or it shall end automatically at the scheduled time |
| FR-04.9 | The system shall send a notification to assigned invigilators when an exam session is created |

### FR-05: Real-Time Video Detection Pipeline

| ID | Requirement |
|----|------------|
| FR-05.1 | The system shall capture live video frames from IP cameras via RTSP |
| FR-05.2 | The system shall detect humans in the video frame using object detection (YOLOv8) |
| FR-05.3 | The system shall maintain persistent identity tracking across frames so each detected person keeps a consistent ID |
| FR-05.4 | The system shall estimate **head pose** (yaw, pitch, roll) for each tracked person using facial landmark analysis |
| FR-05.5 | The system shall estimate **gaze direction** by fusing head pose and eye gaze vectors |
| FR-05.6 | The system shall model **neighbor relationships** by identifying the k-nearest tracked persons within a configurable distance threshold |
| FR-05.7 | The system shall compute **risk angles** — the angular direction from each person toward each neighbor's exam paper zone |
| FR-05.8 | The system shall flag a **suspicious gaze event** when a person's gaze direction aligns with a neighbor's risk angle for more than a configurable duration threshold |
| FR-05.9 | The system shall support a **human-in-the-loop selection** step where the operator selects which detected persons are students to monitor (excluding invigilators, late arrivals, etc.) |
| FR-05.10 | The system shall log extracted features (positions, poses, gaze angles) to structured CSV files for each monitored person |
| FR-05.11 | The system shall process video at ≥ 15 FPS on target hardware |

### FR-06: Real-Time Audio Detection Pipeline

| ID | Requirement |
|----|------------|
| FR-06.1 | The system shall capture real-time audio from USB microphones |
| FR-06.2 | The system shall segment audio into fixed-duration time windows for analysis |
| FR-06.3 | The system shall extract low-level audio features (intensity, activity presence) per window |
| FR-06.4 | The system shall distinguish between ambient hall noise and localized audio activity |
| FR-06.5 | Each microphone shall be mapped to a spatial **audio zone** covering a group of nearby students |
| FR-06.6 | The system shall perform **cross-microphone validation** — activity detected on one mic but not neighboring mics is classified as localized; activity on many mics is classified as ambient noise |
| FR-06.7 | The system shall flag a **suspicious audio event** when localized audio activity exceeding baseline thresholds is detected |
| FR-06.8 | The system shall log audio features to structured CSV files per microphone |

### FR-07: Object Detection

| ID | Requirement |
|----|------------|
| FR-07.1 | The system shall detect unauthorized objects in the video frame, including: mobile phones, books, and handwritten notes |
| FR-07.2 | The system shall generate a detection event when an unauthorized object is identified with confidence above a configurable threshold |
| FR-07.3 | The system shall associate detected objects with the nearest tracked student position |

### FR-08: Alert Processing & Shared Queue

| ID | Requirement |
|----|------------|
| FR-08.1 | The system shall create a **detection event** record for each suspicious behavior detected (gaze, audio, object) |
| FR-08.2 | The system shall apply a **5-second aggregation window** to group temporally and spatially related events before generating an alert |
| FR-08.3 | If multiple students are involved in related events (e.g., two neighbors both turning toward each other), the system shall create a **group event** |
| FR-08.4 | The system shall classify alerts into two severity tiers: |

**Tier 1 (Low Severity):**
- Single, brief suspicious behavior (< 5 seconds)
- Isolated head turn or gaze deviation
- Brief audio spike

**Tier 2 (High Severity):**
- Coordinated behavior involving multiple students (group event)
- Prolonged suspicious behavior (> 10 seconds)
- Repeated violations (≥ 3 events from the same person within 60 seconds)
- Multiple concurrent violations (≥ 3 events in the same 5-second window)

| ID | Requirement |
|----|------------|
| FR-08.5 | All alerts shall appear in a **shared queue** visible to all logged-in referees |
| FR-08.6 | A referee shall be able to **claim** an alert, which locks it to that referee and prevents duplicate review |
| FR-08.7 | Alert status shall follow this lifecycle: `pending` → `claimed` → (`resolved` / `false_positive` / `escalated`) |
| FR-08.8 | A referee shall be able to mark an alert as: **resolved** (action taken), **false positive** (not cheating), or **escalated** (needs further attention) |
| FR-08.9 | The system shall apply **suppression rules** to prevent alert fatigue: |

**Suppression Rules:**
- After resolving/dismissing an alert for a student, suppress similar alerts from the same student for 5 minutes
- After resolving a neighbor event, suppress similar neighbor patterns for 10 minutes
- If > 10 false positives occur in 30 minutes, temporarily reduce sensitivity and alert the admin

| ID | Requirement |
|----|------------|
| FR-08.10 | Each alert shall include: timestamp, hall, camera source, event type, severity tier, involved seat positions, and a short auto-expiring video clip (if available) |

### FR-09: Push-to-Talk Communication

| ID | Requirement |
|----|------------|
| FR-09.1 | The system shall provide real-time **Push-to-Talk (PTT)** voice communication between the control room and invigilators via WebSocket |
| FR-09.2 | A referee shall be able to initiate a voice call to a specific invigilator |
| FR-09.3 | An invigilator shall be able to respond to voice calls from the control room |
| FR-09.4 | PTT shall support binary audio streaming with low latency (< 500ms) |
| FR-09.5 | The system shall display connection status for all PTT-connected users |

### FR-10: Live Monitoring Dashboard

| ID | Requirement |
|----|------------|
| FR-10.1 | The control room dashboard shall display a **grid overview** of all active halls with status indicators (online, alerts count, camera health) |
| FR-10.2 | Clicking a hall shall open the **individual hall view** showing live camera feeds in a grid layout |
| FR-10.3 | The dashboard shall display the **shared alert queue** with real-time updates (new alerts appear without page refresh) |
| FR-10.4 | Each alert in the queue shall show: severity tier (color-coded), event type, hall, seat position, timestamp, and claim status |
| FR-10.5 | The dashboard shall show an **event timeline** for each active hall, logging all detection events chronologically |
| FR-10.6 | The dashboard shall provide PTT controls for initiating and receiving voice calls |
| FR-10.7 | The dashboard shall display real-time system health (FPS, camera status, server load) |
| FR-10.8 | The dashboard shall highlight the camera feed associated with an active alert |

### FR-11: Session Reports & History

| ID | Requirement |
|----|------------|
| FR-11.1 | Upon ending a session, the system shall generate a **session summary** including: total alerts, confirmed incidents, false positives, average response time |
| FR-11.2 | The summary shall aggregate data across all halls belonging to the same exam session |
| FR-11.3 | The system shall provide a **History** page with a searchable list of past exam sessions |
| FR-11.4 | Clicking a past session shall display its detailed report with alert timeline, statistics, and outcome breakdown |
| FR-11.5 | The system shall allow exporting session reports |

### FR-12: Invigilator Interface

| ID | Requirement |
|----|------------|
| FR-12.1 | Invigilators shall see a **"My Schedule"** page listing their assigned upcoming and active exam sessions |
| FR-12.2 | Each assignment shall display: course name, hall, date/time, and hall device status (pre-flight check) |
| FR-12.3 | Invigilators shall have a PTT interface to listen to and communicate with the control room |

---

## 4. Non-Functional Requirements

### NFR-01: Performance

| ID | Requirement |
|----|------------|
| NFR-01.1 | Alert delivery from detection to dashboard display shall be < 5 seconds |
| NFR-01.2 | Video pipeline shall process frames at ≥ 15 FPS per camera |
| NFR-01.3 | Dashboard shall render real-time updates without page refresh (WebSocket push) |
| NFR-01.4 | Database queries for active alerts shall complete in < 100ms |
| NFR-01.5 | PTT audio latency shall be < 500ms end-to-end |
| NFR-01.6 | The system shall support 1–3 concurrent active halls (MVP) |

### NFR-02: Security & Privacy

| ID | Requirement |
|----|------------|
| NFR-02.1 | All passwords shall be stored as salted hashes (never plaintext) |
| NFR-02.2 | API communication shall use HTTPS/TLS |
| NFR-02.3 | The system shall **not** store raw video or audio recordings permanently |
| NFR-02.4 | Short video clips captured for alert review shall be **auto-deleted** when the session ends |
| NFR-02.5 | Structured metadata (feature logs, alert records, event summaries) shall be retained for system evaluation and improvement |
| NFR-02.6 | All user actions shall be tracked in an **audit log** |
| NFR-02.7 | The system shall enforce RBAC — users cannot access features outside their role |

### NFR-03: Reliability

| ID | Requirement |
|----|------------|
| NFR-03.1 | The system shall remain operational for the full duration of an exam session (≥ 2 hours) without crashes |
| NFR-03.2 | If a camera goes offline during a session, the system shall continue processing other cameras and display a "Camera Offline" indicator |
| NFR-03.3 | The system shall gracefully handle network interruptions between cameras and the server |
| NFR-03.4 | Session data shall be persisted continuously, not only at session end |

### NFR-04: Scalability

| ID | Requirement |
|----|------------|
| NFR-04.1 | The system architecture shall allow scaling beyond 3 halls in future iterations |
| NFR-04.2 | The video pipeline shall support adding cameras to a hall without code changes (configuration-driven) |
| NFR-04.3 | The database schema shall support multi-institution deployments in the future |

### NFR-05: Usability

| ID | Requirement |
|----|------------|
| NFR-05.1 | The interface shall be available in **Arabic** and **English** |
| NFR-05.2 | Arabic mode shall use proper **RTL** layout |
| NFR-05.3 | Alert severity shall be communicated through **color coding** (e.g., red for Tier 2, yellow for Tier 1) |
| NFR-05.4 | The Setup Wizard shall guide the admin through initial configuration without technical knowledge |
| NFR-05.5 | The control room dashboard shall be optimized for extended use (low eye strain, clear hierarchy) |

### NFR-06: Compatibility

| ID | Requirement |
|----|------------|
| NFR-06.1 | The web dashboard shall work on Chrome, Firefox, and Edge (latest 2 versions) |
| NFR-06.2 | The system shall support IP cameras with RTSP streaming protocol |
| NFR-06.3 | The system shall support standard USB microphones |
| NFR-06.4 | The server shall run on Windows or Linux |

---

## 5. Data Requirements

### 5.1 Data Model Overview

| Entity | Description | Key Relationships |
|--------|-------------|-------------------|
| **Institution** | The academic institution using the system | Has many Halls, Users |
| **Hall** | A physical examination room | Belongs to Institution; has many Devices; many-to-many with ExamSessions |
| **Device** | A camera or microphone registered to a hall | Belongs to Hall |
| **User** | An authenticated system user | Belongs to Institution; has a Role (admin/referee/invigilator) |
| **ExamSession** | A scheduled or active exam monitoring period | Many-to-many with Halls; has many Assignments, DetectionEvents |
| **Assignment** | Links an invigilator to an exam session | Belongs to ExamSession and User |
| **DetectionEvent** | A single AI-detected suspicious behavior | Belongs to ExamSession and Device; optionally grouped into GroupEvent |
| **GroupEvent** | Multiple correlated detection events | Belongs to ExamSession; aggregates DetectionEvents |
| **Alert** | A notification generated for referee review | References either DetectionEvent or GroupEvent (not both); has a status lifecycle |
| **AuditLog** | Record of user actions for accountability | References User |

### 5.2 Key Relationships

```
Institution (1) ──→ (N) Hall
Institution (1) ──→ (N) User

Hall (M) ←──→ (N) ExamSession        [many-to-many: one exam can span multiple halls]
Hall (1) ──→ (N) Device

ExamSession (1) ──→ (N) Assignment ──→ User (invigilator)
ExamSession (1) ──→ (N) DetectionEvent ──→ Device
ExamSession (1) ──→ (N) GroupEvent
ExamSession (1) ──→ (N) Alert

Alert ──→ DetectionEvent (1) XOR GroupEvent (1)
```

### 5.3 Data Retention Policy

| Data Type | Retention | Justification |
|-----------|-----------|--------------|
| Structured feature logs (CSV) | Indefinite | System improvement, model training |
| Alert records & session summaries | Indefinite | Audit trail, institutional records |
| Short video clips (alert context) | Auto-deleted at session end | Privacy compliance |
| Raw video/audio streams | **Never stored** | Privacy — real-time processing only |
| Audit logs | 2 years minimum | Accountability |

---

## 6. External Interface Requirements

### 6.1 User Interfaces

| Interface | Users | Key Features |
|-----------|-------|-------------|
| **Setup Wizard** | Admin | 2-step form: institution details + admin account creation |
| **Login Page** | All | Username/password, bilingual |
| **Admin Dashboard** | Admin | Hall management, device management, user management |
| **Exam Scheduling** | Referee | Create exam, select halls, assign invigilators |
| **Control Room Dashboard** | Referee | Hall grid overview, shared alert queue, individual hall view with camera feeds, event timeline, PTT controls |
| **Alert Review** | Referee | Claim alert, view video clip, mark resolved/false positive/escalated |
| **History & Reports** | Referee, Admin | Past sessions, session detail reports, statistics |
| **Invigilator Schedule** | Invigilator | "My Schedule" view, hall pre-flight status, PTT listen |

### 6.2 Hardware Interfaces

| Hardware | Interface | Protocol |
|----------|-----------|----------|
| IP Camera | Ethernet (RJ45) → Network Switch → Server | RTSP |
| USB Microphone | USB → Server | USB Audio |
| Network Switch | Ethernet (RJ45) | Gigabit Ethernet |
| Invigilator Earpiece | Connected to invigilator's device | Bluetooth / 3.5mm audio |

### 6.3 Software Interfaces

| Interface | Technology | Purpose |
|-----------|-----------|---------|
| REST API | FastAPI (Python) | CRUD operations, authentication, exam management |
| WebSocket | FastAPI WebSocket | Real-time alert push, PTT audio streaming |
| Database | PostgreSQL | Persistent data storage |
| Video Pipeline | YOLOv8, MediaPipe, OpenCV | Detection, tracking, head pose, gaze estimation |
| Audio Pipeline | Python audio libraries | Audio capture, feature extraction, anomaly detection |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4 | Web dashboard |

---

## 7. User Journey

### 7.1 One-Time Setup (Admin)

```
1. Install Thaqib on local server
2. Open browser → Setup Wizard appears
3. Enter institution name + upload logo
4. Create admin account (username, email, password)
5. Admin Dashboard opens
6. Register Halls → enter name, building, floor, capacity
7. For each Hall → register cameras (RTSP URL) and mics (USB)
   → System runs health check → Hall marked "Ready" when all devices online
8. Create user accounts → Referees and Invigilators
```

### 7.2 Before Each Exam (Referee)

```
1. Referee logs in → sees Exam Management page
2. Creates exam session:
   → Course name, exam type, date, start/end time
   → Selects one or more halls (only "Ready" halls shown)
   → Assigns invigilator(s)
3. System sends notification to assigned invigilators
4. Invigilator logs in → sees exam on "My Schedule" → reviews hall info
```

### 7.3 Exam Day (Referee + Invigilator)

```
1. Invigilator goes to the assigned hall physically
2. Referee logs into control room dashboard
3. Referee clicks "Start Monitoring" on the exam session
   → AI pipelines activate for all assigned halls
   → Camera feeds go live on dashboard
4. Referee optionally selects which detected persons are students (human-in-the-loop)

DURING EXAM:
5. AI runs continuously:
   → Video pipeline: detect → track → head pose → gaze → neighbor risk → alert
   → Audio pipeline: capture → segment → extract features → anomaly detect → alert
   → Object detection: scan for phones/books/notes → alert
6. Alerts appear in shared queue on all referees' dashboards
7. A referee claims an alert → reviews video clip and context
8. Decision:
   a. Suspicious → PTT call to invigilator: "Row 3, Seat 7, please check"
   b. Not suspicious → mark as false positive
   c. Unclear → continue monitoring, keep alert open
9. Invigilator takes physical action and confirms
10. Referee marks alert as resolved

END OF EXAM:
11. Referee clicks "End Session" (or session ends automatically at scheduled time)
12. System generates session summary:
    → Total alerts, confirmed incidents, false positives, response times
    → Aggregated across all halls in the exam session
13. Feature logs (CSV) are retained for system improvement
14. Alert video clips are auto-deleted
```

### 7.4 Post-Exam (Admin / Referee)

```
1. Navigate to History & Reports
2. View past sessions, filter by date/hall/course
3. Drill down into session detail → timeline, statistics, outcomes
4. Export report if needed
```

---

## 8. Future Scope

The following features are **not included in the MVP** but are planned for future development. Design decisions should not preclude their implementation.

### 8.1 Multi-Institution Support

The system should eventually support a **hierarchical organizational model**:

```
University
  ├── Faculty of Engineering
  │     ├── Referees, Invigilators, Halls, Exams
  │     └── ...
  └── Faculty of Science
        └── ...
```

Each faculty would operate as an independent institution with its own data scope, while a university-level admin can view across all faculties.

### 8.2 Referee Scoping (Exam-Based Access Control)

In institutions with multiple control departments (e.g., one per academic level), referees should only see exams relevant to them. The recommended approach for future implementation:

**Option A (Recommended): Exam-Based Assignment**
- Referees are assigned to specific exam sessions (like invigilators are)
- Their dashboard and alert queue only shows assigned exams
- Simplest approach, works for any institution type

**Option B: Tag/Scope Property**
- Referees have a flexible scope label (e.g., "Level 1", "Grade 10")
- Exams are tagged with matching scopes
- More automated but requires consistent tagging

**Option C: Hybrid**
- Exam assignment (Option A) as the core mechanism
- Optional "Teams" for batch-assigning referees to multiple exams at once

### 8.3 Student Identity Linking

MVP tracks students by **seat number/position** only. Future versions may link detections to student records by integrating with the institution's student information system.

### 8.4 Smartwatch / Haptic Alerts

In-hall invigilators could receive discreet haptic notifications on a smartwatch instead of (or in addition to) PTT voice. Deprioritized for MVP.

### 8.5 Mobile Invigilator App

A responsive mobile view optimized for invigilators walking between exam halls, with push notifications.

### 8.6 Cloud Deployment

Support for cloud-hosted deployment (AWS, Azure, GCP) as an alternative to on-premise, with appropriate data residency controls.

### 8.7 Speech Recognition / Keyword Detection

Optional analysis of localized audio for exam-related keywords. Treated as a supplementary indicator, never used in isolation.

---

## 9. Glossary

| Term | Definition |
|------|-----------|
| **Aggregation Window** | A short time period (default 5 seconds) during which related detection events are grouped before generating an alert |
| **Audio Zone** | A spatial region within a hall covered by a specific microphone, mapped to a group of nearby students |
| **Claim (Alert)** | A referee takes ownership of an alert for review, preventing other referees from reviewing the same alert simultaneously |
| **Cross-Microphone Validation** | Comparing audio activity across neighboring microphones to distinguish localized sounds from ambient hall noise |
| **Gaze Direction** | The estimated direction a student is looking, computed by fusing head pose and eye gaze vectors |
| **Head Pose** | The orientation of a person's head in 3D space, described by yaw (left/right), pitch (up/down), and roll (tilt) angles |
| **Human-in-the-Loop** | A step where a human operator manually selects which detected persons should be monitored as students |
| **Neighbor Modeling** | The process of identifying spatially adjacent students and computing the angular relationships between them |
| **On-Premise** | Deployed on local hardware within the institution, not relying on cloud infrastructure |
| **RBAC** | Role-Based Access Control — restricting system access based on user roles |
| **Risk Angle** | An angular range pointing from one student toward a neighbor's exam paper zone; gaze alignment with this range may indicate suspicious behavior |
| **Suppression Rules** | Logic that temporarily reduces alert sensitivity after resolved or false-positive alerts to prevent alert fatigue |
