# Thaqib System Architecture Documentation

## Table of Contents
1. [User Flows](#user-flows)
2. [Entity Relationship Diagram (ERD)](#entity-relationship-diagram)
3. [Activity Diagrams](#activity-diagrams)
4. [Alert Processing Flow](#alert-processing-flow)
5. [Implementation Notes](#implementation-notes)

---

## 1. User Flows

### 1.1 Admin/Control Referee Complete Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    ADMIN USER JOURNEY                            │
└─────────────────────────────────────────────────────────────────┘

PHASE 1: Authentication & Context Selection
═══════════════════════════════════════════
┌──────────────┐
│ Login Screen │
└──────┬───────┘
       │
       ▼
┌────────────────────────┐
│ Select Institution/    │  ◄── Multi-tenancy support
│ Faculty Context        │      Each admin can manage
└──────┬─────────────────┘      multiple institutions
       │
       ▼
┌────────────────────────┐
│ Admin Dashboard Home   │
└────────────────────────┘


PHASE 2: Infrastructure Setup
══════════════════════════════

A. HALL MANAGEMENT
──────────────────
┌──────────────────┐
│ Navigate to      │
│ "Halls" Section  │
└────┬─────────────┘
     │
     ▼
┌──────────────────┐
│ Click "Add Hall" │
└────┬─────────────┘
     │
     ▼
┌───────────────────────────────┐
│ Enter Hall Details:           │
│ • Name/Number (e.g., "A12")   │
│ • Building                    │
│ • Floor                       │
│ • Max Capacity (students)     │
│ • Upload Floor Plan (optional)│
└────┬──────────────────────────┘
     │
     ▼
┌──────────────────┐
│ Save Hall        │
│ Status: "Not     │
│ Ready" (no       │
│ devices yet)     │
└──────────────────┘


B. DEVICE REGISTRATION
──────────────────────
┌──────────────────────┐
│ Select Hall          │
│ Click "Add Devices"  │
└────┬─────────────────┘
     │
     ├──────────────────────────┐
     │                          │
     ▼                          ▼
┌─────────────────┐    ┌─────────────────┐
│ Add IP Camera   │    │ Add Microphone  │
└────┬────────────┘    └────┬────────────┘
     │                      │
     │ Enter:               │ Enter:
     │ • Device Type        │ • Device Type
     │ • IP Address         │ • IP Address
     │ • RTSP URL           │ • Audio Stream URL
     │ • Position Label     │ • Coverage Zone
     │   (e.g., "Front-     │   (e.g., "Zone 1")
     │   Left")             │
     │                      │
     └──────┬───────────────┘
            │
            ▼
     ┌─────────────────────────┐
     │ AUTOMATED HEALTH CHECK  │
     │ ═══════════════════════ │
     │ System pings RTSP/      │
     │ Audio stream URL        │
     └──────┬──────────────────┘
            │
            ├─────────────┬─────────────┐
            ▼             ▼             ▼
     ┌──────────┐  ┌──────────┐  ┌──────────┐
     │ Success  │  │ Timeout  │  │ Auth     │
     │ 🟢 Online│  │ 🔴 Offline│ │ Error    │
     └──────────┘  └──────────┘  └──────────┘
            │
            ▼
     ┌──────────────────────────┐
     │ Update Hall Status       │
     │ ══════════════════════   │
     │ If ALL devices online:   │
     │   Status → "✅ Ready"   │
     │ If ANY device offline:   │
     │   Status → "⚠️ Not Ready"│
     └──────────────────────────┘


C. USER MANAGEMENT
──────────────────
┌──────────────────┐
│ Navigate to      │
│ "Staff" Tab      │
└────┬─────────────┘
     │
     ▼
┌─────────────────────┐
│ Click "Add          │
│ Invigilator"        │
└────┬────────────────┘
     │
     ▼
┌──────────────────────────┐
│ Enter Details:           │
│ • Username               │
│ • Full Name              │
│ • Email                  │
│ • Phone (for PTT)        │
│ • Role: Invigilator      │
└────┬─────────────────────┘
     │
     ▼
┌──────────────────────────┐
│ System Generates:        │
│ • Temporary Password     │
│ • Login Credentials      │
│ • PTT ID                 │
└────┬─────────────────────┘
     │
     ▼
┌──────────────────────────┐
│ Send Credentials via     │
│ Email/SMS                │
└──────────────────────────┘


PHASE 3: Exam Scheduling
═════════════════════════

┌──────────────────────┐
│ Click "Create New    │
│ Exam Session"        │
└────┬─────────────────┘
     │
     ▼
┌──────────────────────────────────┐
│ STEP 1: Basic Details            │
│ • Course Name                    │
│ • Exam Type (Midterm/Final/etc)  │
│ • Date                           │
│ • Start Time                     │
│ • End Time                       │
└────┬─────────────────────────────┘
     │
     ▼
┌──────────────────────────────────┐
│ STEP 2: Select Hall              │
│ • Show only "Ready" halls        │
│ • Filter by capacity             │
│ • Check availability (no         │
│   conflicting sessions)          │
└────┬─────────────────────────────┘
     │
     ▼
┌──────────────────────────────────┐
│ STEP 3: Assign Invigilator       │
│ • Show available invigilators    │
│ • Check their schedule           │
│ • Assign role (Primary/Backup)   │
└────┬─────────────────────────────┘
     │
     ▼
┌──────────────────────────────────┐
│ STEP 4: Configure Thresholds     │
│ (Optional - use defaults)        │
│ • Detection sensitivity          │
│ • Alert tier thresholds          │
│ • Neighbor distance threshold    │
└────┬─────────────────────────────┘
     │
     ▼
┌──────────────────────────────────┐
│ Review & Confirm                 │
└────┬─────────────────────────────┘
     │
     ▼
┌──────────────────────────────────┐
│ SYSTEM ACTIONS:                  │
│ 1. Create ExamSession record     │
│ 2. Create Assignment record      │
│ 3. Reserve hall (block other     │
│    bookings)                     │
│ 4. Start countdown timer         │
│ 5. Send notification to          │
│    invigilator                   │
└──────────────────────────────────┘


PHASE 4: Active Monitoring (Control Room)
═══════════════════════════════════════

┌──────────────────────────────────┐
│ Control Room Dashboard           │
│ ════════════════════════════════ │
│                                  │
│  HALL GRID VIEW                  │
│  ┌────┬────┬────┬────┐          │
│  │A12 │B07 │C03 │D15 │          │
│  │🟢  │🟢  │⚠️  │🔴  │          │
│  │3🔔 │0   │1🔔 │OFF │          │
│  └────┴────┴────┴────┘          │
│                                  │
│  PRIORITY ALERT STACK            │
│  ┌──────────────────────────┐   │
│  │ 🔴 HIGH | Hall A12       │   │
│  │   Neighbor Event         │   │
│  │   Row 3, Seats 7-8       │   │
│  │   [REVIEW] [CALL]        │   │
│  ├──────────────────────────┤   │
│  │ 🟡 MEDIUM | Hall C03     │   │
│  │   Head Pose              │   │
│  │   Row 2, Seat 5          │   │
│  │   [REVIEW]               │   │
│  └──────────────────────────┘   │
└──────────────────────────────────┘
     │
     │ Click on Hall or Alert
     ▼
┌──────────────────────────────────┐
│ Individual Hall Monitoring Page  │
│ ════════════════════════════════ │
│                                  │
│  LIVE CAMERA FEEDS (Grid)        │
│  ┌─────┬─────┬─────┐            │
│  │ Cam │ Cam │ Cam │            │
│  │  1  │  2  │  3  │            │
│  ├─────┼─────┼─────┤            │
│  │ Cam │ Cam │ Cam │            │
│  │  4  │  5  │  6  │            │
│  └─────┴─────┴─────┘            │
│                                  │
│  EVENT TIMELINE (Right Panel)    │
│  ═══════════════════════════════ │
│  07:22:15 - Row 3, Seat 7-8      │
│    Neighbor Event (ACTIVE)       │
│    [VIDEO CLIP] [CALL]           │
│  ─────────────────────────────── │
│  07:19:43 - Row 5, Seat 12       │
│    Audio Spike (PENDING)         │
│    [REVIEW] [DISMISS]            │
│                                  │
│  PTT CONTROLS                    │
│  [🎤 Talk to Invigilator]        │
└──────────────────────────────────┘


PHASE 5: History & Auditing
════════════════════════════

┌──────────────────────────────────┐
│ History Dashboard                │
│ ════════════════════════════════ │
│                                  │
│  Filters:                        │
│  [Hall: All ▼] [Date: Last 30▼] │
│                                  │
│  EXAM SESSIONS TABLE             │
│  ┌───────────────────────────┐  │
│  │Date   Hall  Course  Alerts│  │
│  ├───────────────────────────┤  │
│  │Feb 10 A12   Physics   7   │  │
│  │Feb 08 B07   Chem      2   │  │
│  │Feb 05 C03   Math      12  │  │
│  └───────────────────────────┘  │
│                                  │
│  Click session → Detailed Report │
└──────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────┐
│ Session Detail Report            │
│ ════════════════════════════════ │
│ Session: Physics Midterm         │
│ Hall: A12 | Date: Feb 10, 2026   │
│ Duration: 2h 15m                 │
│ Invigilator: John Smith          │
│                                  │
│ STATISTICS                       │
│ • Total Alerts: 7                │
│ • Confirmed Incidents: 3         │
│ • False Positives: 4             │
│ • Avg Response Time: 18s         │
│                                  │
│ INCIDENT TIMELINE                │
│ ┌────────────────────────────┐  │
│ │07:15 - Head Pose (FALSE)   │  │
│ │07:22 - Neighbor (CONFIRMED)│  │
│ │07:35 - Audio Spike (FALSE) │  │
│ └────────────────────────────┘  │
│                                  │
│ [Download Video] [Export PDF]    │
└──────────────────────────────────┘
```

### 1.2 Invigilator Complete Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                  INVIGILATOR USER JOURNEY                        │
└─────────────────────────────────────────────────────────────────┘

PHASE 1: Pre-Exam (Scheduled State)
════════════════════════════════════

┌──────────────────┐
│ Login to System  │
└────┬─────────────┘
     │
     ▼
┌──────────────────────────────────┐
│ "My Schedule" Dashboard          │
│ ════════════════════════════════ │
│                                  │
│  TODAY'S ASSIGNMENTS             │
│  ┌────────────────────────────┐ │
│  │ 📅 Physics Midterm         │ │
│  │ Hall: A12                  │ │
│  │ Time: 10:00 AM - 12:00 PM  │ │
│  │ ⏱️ Starts in: 1h 23m       │ │
│  │                            │ │
│  │ PRE-FLIGHT CHECK:          │ │
│  │ ✅ 6/6 Cameras Online      │ │
│  │ ✅ 4/4 Mics Online         │ │
│  │ ✅ Hall Status: Ready      │ │
│  │                            │ │
│  │ [VIEW DETAILS]             │ │
│  └────────────────────────────┘ │
│                                  │
│  UPCOMING                        │
│  ┌────────────────────────────┐ │
│  │ 📅 Chemistry Quiz          │ │
│  │ Hall: A12                  │ │
│  │ Feb 15, 2026 - 2:00 PM     │ │
│  └────────────────────────────┘ │
└──────────────────────────────────┘
     │
     │ Click "VIEW DETAILS"
     ▼
┌──────────────────────────────────┐
│ Exam Session Details             │
│ ════════════════════════════════ │
│                                  │
│ Course: Physics Midterm          │
│ Expected Students: 48            │
│ Duration: 2 hours                │
│                                  │
│ HALL LAYOUT                      │
│ [Floor plan with seat positions] │
│                                  │
│ CAMERA COVERAGE                  │
│ • Front: Cameras 1-2             │
│ • Middle: Cameras 3-4            │
│ • Back: Cameras 5-6              │
│                                  │
│ AUDIO ZONES                      │
│ • Zone 1-4 (Mics 1-4)            │
│                                  │
│ [⬅️ BACK TO SCHEDULE]            │
└──────────────────────────────────┘


PHASE 2: Active Exam (Monitoring State)
════════════════════════════════════════

┌──────────────────────────────────┐
│ At exam start time OR earlier:  │
│ Invigilator clicks               │
│ [▶️ START MONITORING SESSION]    │
└────┬─────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────────────────┐
│ INDIVIDUAL MONITORING PAGE                               │
│ ════════════════════════════════════════════════════════ │
│                                                          │
│  HEADER BAR                                              │
│  ┌────────────────────────────────────────────────────┐ │
│  │ Hall A12 - Physics Midterm | ⏱️ 00:23:15 elapsed   │ │
│  │ Status: 🟢 ACTIVE | Students: 48                   │ │
│  │ [CONTACT CONTROL] [END SESSION]                    │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  LEFT/CENTER: LIVE FEED GRID (70% width)                 │
│  ┌──────────────────────────────────────────────────┐   │
│  │ ┌─────────┬─────────┬─────────┐                  │   │
│  │ │ Camera 1│Camera 2 │Camera 3 │                  │   │
│  │ │         │         │         │                  │   │
│  │ ├─────────┼─────────┼─────────┤                  │   │
│  │ │ Camera 4│Camera 5 │Camera 6 │                  │   │
│  │ │         │         │         │                  │   │
│  │ └─────────┴─────────┴─────────┘                  │   │
│  │                                                   │   │
│  │ Auto-Focus Feature:                              │   │
│  │ When alert triggered → camera zooms/highlights   │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  RIGHT PANEL: EVENT TIMELINE (30% width)                 │
│  ┌────────────────────────────────────────┐             │
│  │ ACTIVE ALERTS (2)                      │             │
│  │ ┌────────────────────────────────────┐ │             │
│  │ │ 🔴 NEIGHBOR EVENT                  │ │             │
│  │ │ Row 3, Seats 7-8                   │ │             │
│  │ │ Ongoing: 23 seconds                │ │             │
│  │ │ [REVIEW VIDEO] [ESCALATE]          │ │             │
│  │ └────────────────────────────────────┘ │             │
│  │ ┌────────────────────────────────────┐ │             │
│  │ │ 🟡 HEAD POSE                       │ │             │
│  │ │ Row 5, Seat 12                     │ │             │
│  │ │ 2 min ago                          │ │             │
│  │ │ [REVIEW] [DISMISS] [FALSE POS]     │ │             │
│  │ └────────────────────────────────────┘ │             │
│  │                                        │             │
│  │ ═══ RESOLVED (5) ═══                  │             │
│  │ 07:19 Row 2, Seat 4 [✅ Resolved]     │             │
│  │ 07:15 Row 7, Seat 20 [❌ False Pos]   │             │
│  └────────────────────────────────────────┘             │
│                                                          │
│  BOTTOM BAR: COMMUNICATIONS                              │
│  ┌────────────────────────────────────────────────────┐ │
│  │ [🎤 PUSH TO TALK - Hold to speak to Control]       │ │
│  └────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘


ALERT RECEPTION METHODS (Multi-Channel)
════════════════════════════════════════

Method 1: DASHBOARD (Primary Visual)
──────────────────────────────────────
• New alert appears in timeline
• Auto-scrolls to top if not visible
• Camera feed auto-highlights suspect area
• Visual: Red/Yellow border around alert
• Timestamp and location prominently displayed

Method 2: SMARTWATCH HAPTIC (Silent, Immediate)
────────────────────────────────────────────────
Tier 1 Alert:
  • 1 short buzz (200ms)
  
Tier 2 Alert:
  • 3 long pulses (500ms each)
  • More urgent pattern

Method 3: AUDIO CUE (Configurable)
───────────────────────────────────
• Subtle tone in earbud
• Different tones for Tier 1 vs Tier 2
• Volume adjustable in settings
• Can be disabled if distracting

Method 4: PTT FROM CONTROL (For escalations)
─────────────────────────────────────────────
• Incoming voice call notification
• Control referee provides context
• Invigilator can respond immediately


ALERT RESPONSE WORKFLOW
════════════════════════

┌──────────────────┐
│ Alert Received   │
└────┬─────────────┘
     │
     ▼
┌────────────────────────────────┐
│ Invigilator Actions:           │
│                                │
│ 1️⃣ [REVIEW VIDEO]              │
│    • View 10-sec clip           │
│    • See highlighted behavior   │
│    • Check context              │
│                                │
│ 2️⃣ Physical Assessment          │
│    • Walk toward area           │
│    • Observe students           │
│    • Make presence known        │
│                                │
│ 3️⃣ Decision:                    │
│    ├─ [RESOLVE]                 │
│    │  "I handled it"            │
│    │                            │
│    ├─ [FALSE POSITIVE]          │
│    │  "Not actually cheating"   │
│    │                            │
│    ├─ [DISMISS]                 │
│    │  "Acknowledged, monitoring"│
│    │                            │
│    └─ [ESCALATE]                │
│       "Need Control support"    │
│       → Opens PTT channel       │
│       → Adds notes              │
└────────────────────────────────┘


PHASE 3: Post-Exam
══════════════════

┌──────────────────────────────────┐
│ SESSION END                      │
│ ════════════════════════════════ │
│                                  │
│ Automatic at scheduled end time  │
│ OR Manual: Click [END SESSION]   │
└────┬─────────────────────────────┘
     │
     ▼
┌──────────────────────────────────┐
│ Session Summary Screen           │
│ ════════════════════════════════ │
│                                  │
│ Duration: 2h 15m                 │
│ Alerts Received: 7               │
│ • Resolved: 3                    │
│ • False Positives: 4             │
│                                  │
│ FLAGGED INCIDENTS (Require       │
│ Review):                         │
│ ┌────────────────────────────┐  │
│ │ 07:22 - Neighbor Event     │  │
│ │ Row 3, Seats 7-8           │  │
│ │ Status: ESCALATED          │  │
│ │ [ADD NOTES]                │  │
│ └────────────────────────────┘  │
│                                  │
│ FINAL NOTES (Optional):          │
│ ┌────────────────────────────┐  │
│ │ [Text area for comments]   │  │
│ └────────────────────────────┘  │
│                                  │
│ [SUBMIT REPORT]                  │
└────┬─────────────────────────────┘
     │
     ▼
┌──────────────────────────────────┐
│ SYSTEM ACTIONS:                  │
│ 1. Finalize recording            │
│ 2. Update session status         │
│ 3. Generate report               │
│ 4. Archive to storage tier       │
│ 5. Send summary to admin         │
└──────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────┐
│ Return to "My Schedule"          │
│ Session moved to history         │
└──────────────────────────────────┘
```

---

## 2. Entity Relationship Diagram (ERD)

### 2.1 Complete Database Schema

```sql
-- ═══════════════════════════════════════════════════════════════
-- CORE INFRASTRUCTURE ENTITIES
-- ═══════════════════════════════════════════════════════════════

-- Institutions (Multi-tenancy support)
CREATE TABLE institutions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    address TEXT,
    contact_email VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Halls (Static Infrastructure)
CREATE TABLE halls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_id UUID REFERENCES institutions(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    building VARCHAR(100),
    floor VARCHAR(20),
    capacity INT NOT NULL CHECK (capacity > 0),
    layout_map JSONB,  -- Seat positions, dimensions
    status VARCHAR(20) DEFAULT 'not_ready' 
        CHECK (status IN ('ready', 'not_ready', 'maintenance', 'inactive')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(institution_id, name)
);

-- Devices (Cameras & Microphones)
CREATE TABLE devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hall_id UUID REFERENCES halls(id) ON DELETE CASCADE,
    type VARCHAR(20) NOT NULL CHECK (type IN ('camera', 'microphone')),
    identifier VARCHAR(100) NOT NULL,  -- MAC address or device ID
    ip_address INET,
    stream_url VARCHAR(500) NOT NULL,
    position JSONB NOT NULL,  -- {x, y, z, label: "Front-Left"}
    coverage_area JSONB,  -- For cameras: FOV, viewing angle
    status VARCHAR(20) DEFAULT 'offline' 
        CHECK (status IN ('online', 'offline', 'error', 'maintenance')),
    last_health_check TIMESTAMP,
    metadata JSONB,  -- Additional device-specific info
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for quick device lookups by hall
CREATE INDEX idx_devices_hall ON devices(hall_id);
CREATE INDEX idx_devices_status ON devices(status);


-- ═══════════════════════════════════════════════════════════════
-- USER MANAGEMENT
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_id UUID REFERENCES institutions(id) ON DELETE CASCADE,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    role VARCHAR(20) NOT NULL 
        CHECK (role IN ('admin', 'referee', 'invigilator')),
    ptt_id VARCHAR(100),  -- Push-to-talk identifier
    status VARCHAR(20) DEFAULT 'active' 
        CHECK (status IN ('active', 'inactive', 'on_duty', 'unavailable')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_institution ON users(institution_id);


-- ═══════════════════════════════════════════════════════════════
-- EXAM SESSION MANAGEMENT
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE exam_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hall_id UUID REFERENCES halls(id) ON DELETE RESTRICT,
    exam_name VARCHAR(255) NOT NULL,
    exam_type VARCHAR(50),  -- Midterm, Final, Quiz, etc.
    scheduled_start TIMESTAMP NOT NULL,
    scheduled_end TIMESTAMP NOT NULL,
    actual_start TIMESTAMP,
    actual_end TIMESTAMP,
    status VARCHAR(20) DEFAULT 'scheduled' 
        CHECK (status IN ('scheduled', 'active', 'completed', 'cancelled')),
    student_count INT,
    configuration JSONB,  -- Detection thresholds, settings
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CHECK (scheduled_end > scheduled_start),
    CHECK (actual_end IS NULL OR actual_end >= actual_start)
);

CREATE INDEX idx_sessions_hall ON exam_sessions(hall_id);
CREATE INDEX idx_sessions_status ON exam_sessions(status);
CREATE INDEX idx_sessions_schedule ON exam_sessions(scheduled_start, scheduled_end);


-- Assignments (Invigilator → Exam Session)
CREATE TABLE assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exam_session_id UUID REFERENCES exam_sessions(id) ON DELETE CASCADE,
    invigilator_id UUID REFERENCES users(id) ON DELETE RESTRICT,
    role VARCHAR(20) DEFAULT 'primary' 
        CHECK (role IN ('primary', 'backup')),
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notified_at TIMESTAMP,
    
    UNIQUE(exam_session_id, invigilator_id)
);

CREATE INDEX idx_assignments_session ON assignments(exam_session_id);
CREATE INDEX idx_assignments_invigilator ON assignments(invigilator_id);


-- ═══════════════════════════════════════════════════════════════
-- DETECTION & ALERT ENTITIES
-- ═══════════════════════════════════════════════════════════════

-- Individual Detection Events
CREATE TABLE detection_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exam_session_id UUID REFERENCES exam_sessions(id) ON DELETE CASCADE,
    device_id UUID REFERENCES devices(id),
    event_type VARCHAR(50) NOT NULL 
        CHECK (event_type IN ('head_pose', 'audio_spike', 'movement', 
                              'object_detection', 'prolonged_absence')),
    severity VARCHAR(20) NOT NULL 
        CHECK (severity IN ('low', 'medium', 'high')),
    student_position JSONB NOT NULL,  -- {row, seat, x, y}
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confidence_score DECIMAL(3, 2) CHECK (confidence_score BETWEEN 0 AND 1),
    metadata JSONB,  -- Event-specific data (angles, decibels, etc.)
    group_id UUID,  -- FK to group_events (nullable)
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_detection_session ON detection_events(exam_session_id);
CREATE INDEX idx_detection_timestamp ON detection_events(timestamp);
CREATE INDEX idx_detection_group ON detection_events(group_id);


-- Grouped Events (Coordinated Cheating)
CREATE TABLE group_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exam_session_id UUID REFERENCES exam_sessions(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL 
        CHECK (event_type IN ('neighbor_cheating', 'collaboration', 
                              'coordinated_movement')),
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('medium', 'high')),
    student_positions JSONB NOT NULL,  -- Array of positions
    participating_event_ids UUID[],  -- Array of detection_event IDs
    first_detected TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add FK constraint after table creation
ALTER TABLE detection_events 
    ADD CONSTRAINT fk_detection_group 
    FOREIGN KEY (group_id) REFERENCES group_events(id) ON DELETE SET NULL;

CREATE INDEX idx_group_session ON group_events(exam_session_id);


-- Alerts (For Invigilators/Referees)
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exam_session_id UUID REFERENCES exam_sessions(id) ON DELETE CASCADE,
    
    -- Polymorphic relationship: Either detection_event OR group_event
    detection_event_id UUID REFERENCES detection_events(id),
    group_event_id UUID REFERENCES group_events(id),
    
    alert_type VARCHAR(10) NOT NULL CHECK (alert_type IN ('tier_1', 'tier_2')),
    status VARCHAR(20) DEFAULT 'pending' 
        CHECK (status IN ('pending', 'acknowledged', 'resolved', 
                         'false_positive', 'escalated')),
    assigned_to UUID REFERENCES users(id),  -- Invigilator or Referee
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TIMESTAMP,
    resolved_at TIMESTAMP,
    resolution_notes TEXT,
    escalated BOOLEAN DEFAULT FALSE,
    
    -- Must reference either detection_event OR group_event, not both
    CHECK (
        (detection_event_id IS NOT NULL AND group_event_id IS NULL) OR
        (detection_event_id IS NULL AND group_event_id IS NOT NULL)
    )
);

CREATE INDEX idx_alerts_session ON alerts(exam_session_id);
CREATE INDEX idx_alerts_status ON alerts(status);
CREATE INDEX idx_alerts_assigned ON alerts(assigned_to);
CREATE INDEX idx_alerts_created ON alerts(created_at);


-- ═══════════════════════════════════════════════════════════════
-- AUDIT & HISTORY
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id UUID,
    details JSONB,
    ip_address INET,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_user ON audit_logs(user_id);
CREATE INDEX idx_audit_timestamp ON audit_logs(created_at);


-- Recording Metadata (Video/Audio Storage References)
CREATE TABLE recordings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exam_session_id UUID REFERENCES exam_sessions(id) ON DELETE CASCADE,
    device_id UUID REFERENCES devices(id),
    storage_path VARCHAR(500) NOT NULL,  -- S3/Azure path
    file_format VARCHAR(20),
    duration_seconds INT,
    file_size_bytes BIGINT,
    storage_tier VARCHAR(20) DEFAULT 'hot' 
        CHECK (storage_tier IN ('hot', 'warm', 'cold', 'archived')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMP
);

CREATE INDEX idx_recordings_session ON recordings(exam_session_id);
```

### 2.2 Relationship Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                    ENTITY RELATIONSHIPS                          │
└─────────────────────────────────────────────────────────────────┘

CORE INFRASTRUCTURE HIERARCHY:
═══════════════════════════════

Institution (1)
    │
    ├──> Halls (N)
    │       │
    │       └──> Devices (N)  [Camera, Microphone]
    │
    └──> Users (N)  [Admin, Referee, Invigilator]


EXAM SESSION FLOW:
══════════════════

Hall (1) ──┐
           ├──> ExamSession (N)
           │        │
User (1) ──┘        ├──> Assignment (N) ──> User (Invigilator)
                    │
                    └──> DetectionEvent (N)
                            │
                            ├──> GroupEvent (N)
                            │
                            └──> Alert (N) ──> User (assigned_to)


DETECTION HIERARCHY:
════════════════════

ExamSession (1)
    │
    ├──> DetectionEvent (N)
    │       │
    │       └──> [Optional] GroupEvent (1)
    │
    └──> Alert (N)
            │
            └──> DetectionEvent (1) OR GroupEvent (1)


KEY CONSTRAINTS:
════════════════

1. Hall Status = "Ready" IF ALL devices = "Online"
2. ExamSession can only be created for "Ready" halls
3. No overlapping ExamSessions for same hall
4. Alert must reference EITHER DetectionEvent OR GroupEvent (not both)
5. GroupEvent aggregates multiple DetectionEvents
6. Assignment links Invigilator to ExamSession (with role)
```

---

## 3. Activity Diagrams

### 3.1 Exam Session Creation

```
┌─────────────────────────────────────────────────────────────────┐
│              ACTIVITY: CREATE EXAM SESSION                       │
└─────────────────────────────────────────────────────────────────┘

ACTORS:
  👤 Admin
  🖥️ System
  📬 Invigilator


SWIMLANES:
══════════

┌──────────────┬────────────────────────┬─────────────────┐
│     ADMIN    │        SYSTEM          │  INVIGILATOR    │
├──────────────┼────────────────────────┼─────────────────┤
│              │                        │                 │
│ (START)      │                        │                 │
│    │         │                        │                 │
│    ▼         │                        │                 │
│ Click        │                        │                 │
│ "Create      │                        │                 │
│ Session"     │                        │                 │
│    │         │                        │                 │
│    │────────>│                        │                 │
│              │ Display                │                 │
│              │ Creation Form          │                 │
│              │    │                   │                 │
│    │<────────│    │                   │                 │
│    │         │    │                   │                 │
│    ▼         │    │                   │                 │
│ Enter:       │    │                   │                 │
│ • Course     │    │                   │                 │
│ • Date/Time  │    │                   │                 │
│ • Duration   │    │                   │                 │
│    │         │    │                   │                 │
│    ▼         │    │                   │                 │
│ Select       │    │                   │                 │
│ Ready Hall   │    │                   │                 │
│    │         │    │                   │                 │
│    │────────>│    │                   │                 │
│              │ Validate:              │                 │
│              │ • Hall Ready?          │                 │
│              │ • No conflicts?        │                 │
│              │ • Time valid?          │                 │
│              │    │                   │                 │
│              │   ◇── Hall Available?  │                 │
│              │   │                    │                 │
│              │  YES                   │                 │
│              │   │                    │                 │
│    │<────────│   ▼                    │                 │
│    │         │ Show Available         │                 │
│    │         │ Halls                  │                 │
│    │         │                        │                 │
│    ▼         │                        │                 │
│ Assign       │                        │                 │
│ Invigilator  │                        │                 │
│    │         │                        │                 │
│    │────────>│                        │                 │
│              │ Check:                 │                 │
│              │ • Invigilator          │                 │
│              │   available?           │                 │
│              │ • No schedule          │                 │
│              │   conflict?            │                 │
│              │    │                   │                 │
│              │    ▼                   │                 │
│              │ ┌─────────────────┐   │                 │
│              │ │ Create Session  │   │                 │
│              │ │ • ExamSession   │   │                 │
│              │ │ • Assignment    │   │                 │
│              │ │ • Reserve Hall  │   │                 │
│              │ └────────┬────────┘   │                 │
│              │          │            │                 │
│              │          ▼            │                 │
│              │ ┌─────────────────┐   │                 │
│              │ │ Start Countdown │   │                 │
│              │ │ Timer           │   │                 │
│              │ └────────┬────────┘   │                 │
│              │          │            │                 │
│              │          │───────────────────────>│     │
│              │                        │    Receive     │
│              │                        │    Notification│
│              │                        │        │       │
│              │                        │        ▼       │
│              │                        │    Email/SMS   │
│              │                        │    • Exam      │
│              │                        │      Details   │
│              │                        │    • Login     │
│              │                        │      Link      │
│              │                        │                │
│    │<────────│ Success                │                │
│    │         │ Confirmation           │                │
│    │         │                        │                │
│    ▼         │                        │                │
│ View Session │                        │                │
│ on Dashboard │                        │                │
│              │                        │                │
│ (END)        │                        │                │
└──────────────┴────────────────────────┴─────────────────┘


DECISION POINTS:
════════════════

1. Hall Available?
   YES → Continue
   NO  → Show error: "Hall not available at this time"

2. Invigilator Available?
   YES → Create session
   NO  → Show error: "Invigilator has schedule conflict"


SYSTEM ACTIONS (Database Operations):
══════════════════════════════════════

INSERT INTO exam_sessions (
    hall_id,
    exam_name,
    scheduled_start,
    scheduled_end,
    status,
    created_by
) VALUES (...);

INSERT INTO assignments (
    exam_session_id,
    invigilator_id,
    role
) VALUES (...);

-- Send notification via queue
INSERT INTO notifications (
    user_id,
    type,
    message,
    sent_at
) VALUES (...);
```

### 3.2 Alert Processing Flow

```
┌─────────────────────────────────────────────────────────────────┐
│           ACTIVITY: ALERT DETECTION & PROCESSING                 │
└─────────────────────────────────────────────────────────────────┘

ACTORS:
  🤖 Detection AI
  🖥️ System (Backend)
  👤 Invigilator
  🎯 Control Referee


SWIMLANES:
══════════

┌────────────┬────────────┬──────────────┬────────────────┐
│ DETECTION  │  SYSTEM    │ INVIGILATOR  │ CONTROL REFEREE│
│     AI     │            │              │                │
├────────────┼────────────┼──────────────┼────────────────┤
│            │            │              │                │
│ (START)    │            │              │                │
│  Analyze   │            │              │                │
│  Video/    │            │              │                │
│  Audio     │            │              │                │
│    │       │            │              │                │
│    ▼       │            │              │                │
│ ┌────────┐ │            │              │                │
│ │Behavior│ │            │              │                │
│ │Detected│ │            │              │                │
│ └───┬────┘ │            │              │                │
│     │      │            │              │                │
│     │─────────────>│    │              │                │
│            │ Create     │              │                │
│            │ Detection  │              │                │
│            │ Event      │              │                │
│            │    │       │              │                │
│            │    ▼       │              │                │
│            │ ┌─────────────────┐       │                │
│            │ │ WAIT 5 SECONDS  │       │                │
│            │ │ (Aggregation    │       │                │
│            │ │  Window)        │       │                │
│            │ └────────┬────────┘       │                │
│            │          │                │                │
│    │───────────────>│ │                │                │
│ More       │          │                │                │
│ Events     │          │                │                │
│ (if any)   │          │                │                │
│            │          ▼                │                │
│            │ ┌─────────────────┐       │                │
│            │ │ Group Related   │       │                │
│            │ │ Events          │       │                │
│            │ │ • Same area     │       │                │
│            │ │ • Time window   │       │                │
│            │ │ • Type match    │       │                │
│            │ └────────┬────────┘       │                │
│            │          │                │                │
│            │          ▼                │                │
│            │    ◇── Multiple           │                │
│            │    │   Students?          │                │
│            │   YES                     │                │
│            │    │                      │                │
│            │    ▼                      │                │
│            │ Create                    │                │
│            │ GroupEvent                │                │
│            │    │                      │                │
│            │    └───┐                  │                │
│            │        │                  │                │
│            │        ▼                  │                │
│            │   ◇── Calculate           │                │
│            │   │   Severity            │                │
│            │   │                       │                │
│            │  LOW                      │                │
│            │   │                       │                │
│            │   ▼                       │                │
│            │ Tier 1                    │                │
│            │ Alert                     │                │
│            │   │                       │                │
│            │   │──────────────────>│   │                │
│            │           Notify          │                │
│            │           • Dashboard     │                │
│            │           • Haptic (1x)   │                │
│            │           • Timeline      │                │
│            │                  │        │                │
│            │                  ▼        │                │
│            │              Review       │                │
│            │              Alert        │                │
│            │                  │        │                │
│            │                  ▼        │                │
│            │             ◇── Decision  │                │
│            │             │             │                │
│            │         RESOLVE           │                │
│            │             │             │                │
│            │   │<────────│             │                │
│            │   │                       │                │
│            │   ▼                       │                │
│            │ Update                    │                │
│            │ Alert                     │                │
│            │ Status                    │                │
│            │                           │                │
│            │  MEDIUM/HIGH              │                │
│            │   │                       │                │
│            │   ▼                       │                │
│            │ Tier 2                    │                │
│            │ Alert                     │                │
│            │   │                       │                │
│            │   ├──────────────────>│   │                │
│            │   │       Notify          │                │
│            │   │       • Dashboard     │                │
│            │   │       • Haptic (3x)   │                │
│            │   │       • Audio Cue     │                │
│            │   │              │        │                │
│            │   │              ▼        │                │
│            │   │          Review       │                │
│            │   │          Alert        │                │
│            │   │              │        │                │
│            │   │              │        │                │
│            │   └─────────────────────────────>│         │
│            │                  │       Notify  │         │
│            │                  │       • Queue │         │
│            │                  │       • Chime │         │
│            │                  │       • Video │         │
│            │                  │          │    │         │
│            │                  │          ▼    │         │
│            │                  │      Review   │         │
│            │                  │      Context  │         │
│            │                  │          │    │         │
│            │                  ▼          ▼    │         │
│            │             ◇── Escalate?  ◇──Confirm?    │
│            │             │              │    │         │
│            │            YES             YES  │         │
│            │             │              │    │         │
│            │   │<────────│──────────────│────│         │
│            │   │         │              │              │
│            │   │         └──────────────┘              │
│            │   │         PTT Call                      │
│            │   │         Initiated                     │
│            │   │                                       │
│            │   ▼                                       │
│            │ Update                                    │
│            │ Alert:                                    │
│            │ "Escalated"                               │
│            │                                           │
│ (END)      │                                           │
└────────────┴────────────┴──────────────┴────────────────┘


AGGREGATION LOGIC:
══════════════════

Group events IF:
1. Same exam_session_id
2. Within 5-second window
3. Students adjacent (distance < threshold)
4. Related event types (e.g., both head_pose)

Example:
  Event 1: Student A turns head at 10:23:15
  Event 2: Student B turns head at 10:23:17
  Distance: 1.2 meters (neighbors)
  → CREATE GroupEvent (neighbor_cheating)


SEVERITY CALCULATION:
═════════════════════

LOW (Tier 1):
• Single head turn < 30°
• Brief audio spike < 2 seconds
• Isolated movement

MEDIUM (Tier 2):
• Prolonged behavior (> 5 seconds)
• Head turn > 45°
• Repeated violations (> 3 in 60s)

HIGH (Tier 2):
• Coordinated cheating (GroupEvent)
• Multiple concurrent violations
• Prolonged suspicious behavior (> 10s)
```

### 3.3 Device Health Check

```
┌─────────────────────────────────────────────────────────────────┐
│         ACTIVITY: DEVICE REGISTRATION & HEALTH CHECK             │
└─────────────────────────────────────────────────────────────────┘

ACTORS:
  👤 Admin
  🖥️ System
  📷 Device (Camera/Microphone)


SWIMLANES:
══════════

┌──────────────┬────────────────────────┬─────────────────┐
│     ADMIN    │        SYSTEM          │     DEVICE      │
├──────────────┼────────────────────────┼─────────────────┤
│              │                        │                 │
│ (START)      │                        │                 │
│ Select Hall  │                        │                 │
│    │         │                        │                 │
│    ▼         │                        │                 │
│ Click "Add   │                        │                 │
│ Device"      │                        │                 │
│    │         │                        │                 │
│    │────────>│                        │                 │
│              │ Show Device            │                 │
│              │ Registration           │                 │
│              │ Form                   │                 │
│              │    │                   │                 │
│    │<────────│    │                   │                 │
│    │         │    │                   │                 │
│    ▼         │    │                   │                 │
│ Enter:       │    │                   │                 │
│ • Type       │    │                   │                 │
│ • IP         │    │                   │                 │
│ • RTSP URL   │    │                   │                 │
│ • Position   │    │                   │                 │
│    │         │    │                   │                 │
│    │────────>│    │                   │                 │
│              │ Validate:              │                 │
│              │ • IP format            │                 │
│              │ • URL format           │                 │
│              │ • Not duplicate        │                 │
│              │    │                   │                 │
│              │    ▼                   │                 │
│              │ ┌──────────────────┐  │                 │
│              │ │ INSERT INTO      │  │                 │
│              │ │ devices          │  │                 │
│              │ │ status='offline' │  │                 │
│              │ └────────┬─────────┘  │                 │
│              │          │            │                 │
│              │          ▼            │                 │
│              │ ┌──────────────────┐  │                 │
│              │ │ Ping RTSP Stream │  │                 │
│              │ │ Timeout: 10s     │  │                 │
│              │ └────────┬─────────┘  │                 │
│              │          │            │                 │
│              │          │──────────────────────>│      │
│              │                        │    RTSP        │
│              │                        │    Request     │
│              │                        │       │        │
│              │                        │       ▼        │
│              │                        │    ◇──Stream   │
│              │                        │    │  Active?  │
│              │                        │   YES          │
│              │                        │    │           │
│              │          │<───────────────────┘         │
│              │          │            │    Stream       │
│              │          │            │    Response     │
│              │          │            │    (200 OK)     │
│              │          ▼            │                 │
│              │     ◇──Connection     │                 │
│              │     │   Successful?   │                 │
│              │    YES                │                 │
│              │     │                 │                 │
│              │     ▼                 │                 │
│              │ ┌──────────────────┐  │                 │
│              │ │ UPDATE devices   │  │                 │
│              │ │ SET status=      │  │                 │
│              │ │   'online'       │  │                 │
│              │ │ last_health_     │  │                 │
│              │ │   check=NOW()    │  │                 │
│              │ └────────┬─────────┘  │                 │
│              │          │            │                 │
│              │          ▼            │                 │
│              │ ┌──────────────────┐  │                 │
│              │ │ Check Hall       │  │                 │
│              │ │ Readiness:       │  │                 │
│              │ │ Are ALL devices  │  │                 │
│              │ │ online?          │  │                 │
│              │ └────────┬─────────┘  │                 │
│              │          │            │                 │
│              │          ▼            │                 │
│              │     ◇──All Online?    │                 │
│              │     │                 │                 │
│              │    YES                │                 │
│              │     │                 │                 │
│              │     ▼                 │                 │
│              │ ┌──────────────────┐  │                 │
│              │ │ UPDATE halls     │  │                 │
│              │ │ SET status=      │  │                 │
│              │ │   'ready'        │  │                 │
│              │ └────────┬─────────┘  │                 │
│              │          │            │                 │
│    │<────────│──────────┘            │                 │
│    │         │ Success                │                 │
│    │         │ Notification           │                 │
│    │         │                        │                 │
│    ▼         │                        │                 │
│ View Device  │                        │                 │
│ Status:      │                        │                 │
│ 🟢 Online    │                        │                 │
│              │                        │                 │
│              │                        │                 │
│              │     │                  │                 │
│              │    NO (Connection      │                 │
│              │         Failed)        │                 │
│              │     │                  │                 │
│              │     ▼                  │                 │
│              │ ┌──────────────────┐   │                 │
│              │ │ Log Error        │   │                 │
│              │ │ Keep status=     │   │                 │
│              │ │   'offline'      │   │                 │
│              │ └────────┬─────────┘   │                 │
│              │          │             │                 │
│    │<────────│──────────┘             │                 │
│    │         │ Error                  │                 │
│    │         │ Notification           │                 │
│    │         │                        │                 │
│    ▼         │                        │                 │
│ View Device  │                        │                 │
│ Status:      │                        │                 │
│ 🔴 Offline   │                        │                 │
│              │                        │                 │
│ Retry or     │                        │                 │
│ Contact IT   │                        │                 │
│              │                        │                 │
│ (END)        │                        │                 │
└──────────────┴────────────────────────┴─────────────────┘


PERIODIC HEALTH CHECKS:
═══════════════════════

After initial registration, system runs automated health checks:

CRON Job (every 5 minutes):
┌─────────────────────────────┐
│ FOR EACH device WHERE       │
│   status IN ('online',      │
│              'error')       │
│ DO:                         │
│   1. Ping RTSP stream       │
│   2. IF success:            │
│      • status = 'online'    │
│      • last_health_check =  │
│        NOW()                │
│   3. IF failure:            │
│      • status = 'error'     │
│      • Send alert to admin  │
│   4. Update hall status     │
└─────────────────────────────┘


HALL READINESS CALCULATION:
═══════════════════════════

UPDATE halls
SET status = 
  CASE
    WHEN (
      SELECT COUNT(*)
      FROM devices
      WHERE hall_id = halls.id
        AND status = 'online'
    ) = (
      SELECT COUNT(*)
      FROM devices
      WHERE hall_id = halls.id
    ) AND (
      SELECT COUNT(*)
      FROM devices
      WHERE hall_id = halls.id
    ) > 0
    THEN 'ready'
    ELSE 'not_ready'
  END;
```

---

## 4. Alert Processing Flow

### 4.1 Detailed Alert State Machine

```
┌─────────────────────────────────────────────────────────────────┐
│                    ALERT LIFECYCLE                               │
└─────────────────────────────────────────────────────────────────┘

STATE: CREATED
══════════════
Initial state when detection event occurs

Transitions:
  → PENDING (automatically after aggregation window)


STATE: PENDING
══════════════
Alert created and sent to invigilator/referee

Allowed Actions:
  • Acknowledge
  • Review video
  • Dismiss
  • Escalate

Transitions:
  → ACKNOWLEDGED (invigilator views alert)
  → ESCALATED (invigilator requests help)
  → FALSE_POSITIVE (invigilator dismisses)


STATE: ACKNOWLEDGED
═══════════════════
Invigilator has seen the alert and is investigating

Allowed Actions:
  • Resolve (mark handled)
  • Escalate (need help)
  • Mark false positive

Transitions:
  → RESOLVED (incident handled)
  → ESCALATED (needs control room)
  → FALSE_POSITIVE (not actually cheating)


STATE: ESCALATED
════════════════
Control referee is reviewing

Allowed Actions:
  • Confirm (send instructions)
  • Resolve (provide guidance)
  • Downgrade to false positive

Transitions:
  → RESOLVED (after referee confirms & invigilator acts)
  → FALSE_POSITIVE (referee determines not cheating)


STATE: RESOLVED
═══════════════
Alert has been handled, incident closed

No further transitions (terminal state)

Metadata stored:
  • Resolution time
  • Resolution notes
  • Actions taken


STATE: FALSE_POSITIVE
════════════════════
Alert determined to be incorrect detection

No further transitions (terminal state)

Used for:
  • Training data
  • System improvement
  • Alert accuracy metrics


STATE DIAGRAM:
══════════════

                    ┌─────────┐
                    │ CREATED │
                    └────┬────┘
                         │
                         ▼
                    ┌─────────┐
                ┌──>│ PENDING │
                │   └────┬────┘
                │        │
                │        ├───────────────┬──────────────┐
                │        │               │              │
                │        ▼               ▼              ▼
                │   ┌────────────┐  ┌───────────┐  ┌─────────────┐
                │   │ACKNOWLEDGED│  │ ESCALATED │  │FALSE_       │
                │   └─────┬──────┘  └─────┬─────┘  │POSITIVE     │
                │         │               │        └─────────────┘
                │         │               │              ^
                │         │               │              │
                │         ├───────────────┼──────────────┘
                │         │               │
                │         ▼               ▼
                │      ┌──────────────────────┐
                └──────┤     RESOLVED         │
                       └──────────────────────┘


SUPPRESSION RULES:
══════════════════

After an alert is RESOLVED or marked FALSE_POSITIVE:

1. Same student, same type:
   • Suppress for 5 minutes
   • Prevent alert fatigue

2. Neighbor events:
   • After resolution, suppress similar
     neighbor patterns for 10 minutes

3. Whole hall suppression:
   • If > 10 false positives in 30 minutes
   • Reduce sensitivity temporarily
   • Alert admin for review
```

### 4.2 Tier Classification Logic

```python
# Pseudo-code for alert tier determination

def calculate_alert_tier(detection_event, group_event=None):
    """
    Determine if alert should be Tier 1 or Tier 2
    
    Tier 1: Direct to Invigilator
    Tier 2: Both Invigilator + Control Referee
    """
    
    # TIER 2 (HIGH PRIORITY) CONDITIONS
    # ==================================
    
    # Condition 1: Group Event (Coordinated Cheating)
    if group_event is not None:
        return "tier_2"
    
    # Condition 2: High Severity Single Event
    if detection_event.severity == "high":
        return "tier_2"
    
    # Condition 3: Prolonged Behavior
    if detection_event.metadata.get("duration") > 10:  # 10 seconds
        return "tier_2"
    
    # Condition 4: Repeated Violations
    recent_events = get_recent_events(
        student_position=detection_event.student_position,
        time_window=60  # Last 60 seconds
    )
    
    if len(recent_events) >= 3:
        return "tier_2"
    
    # Condition 5: Multiple Concurrent Violations
    concurrent = get_concurrent_events(
        exam_session_id=detection_event.exam_session_id,
        time_window=5  # Same 5-second window
    )
    
    if len(concurrent) >= 3:
        return "tier_2"
    
    # DEFAULT: TIER 1
    # ===============
    return "tier_1"


def create_alert(detection_event, group_event=None):
    """Create alert and route to appropriate recipients"""
    
    tier = calculate_alert_tier(detection_event, group_event)
    
    # Get assigned invigilator
    exam_session = get_exam_session(detection_event.exam_session_id)
    invigilator = get_primary_invigilator(exam_session.id)
    
    # Create alert record
    alert = Alert.create(
        exam_session_id=exam_session.id,
        detection_event_id=detection_event.id if not group_event else None,
        group_event_id=group_event.id if group_event else None,
        alert_type=tier,
        assigned_to=invigilator.id,
        status="pending"
    )
    
    # TIER 1: Notify invigilator only
    if tier == "tier_1":
        send_notification(
            user=invigilator,
            alert=alert,
            channels=["dashboard", "haptic"],
            urgency="normal"
        )
    
    # TIER 2: Notify both invigilator and control
    elif tier == "tier_2":
        # Notify invigilator
        send_notification(
            user=invigilator,
            alert=alert,
            channels=["dashboard", "haptic", "audio"],
            urgency="high"
        )
        
        # Notify all active control referees
        referees = get_active_referees()
        for referee in referees:
            send_notification(
                user=referee,
                alert=alert,
                channels=["dashboard", "audio"],
                urgency="high"
            )
    
    return alert
```

---

## 5. Implementation Notes

### 5.1 Technology Stack Recommendations

```
BACKEND:
════════
• API: FastAPI (Python)
• Database: PostgreSQL 14+
• Cache: Redis
• Message Queue: RabbitMQ or AWS SQS
• WebSocket: Socket.IO or FastAPI WebSocket

FRONTEND:
═════════
• Framework: React 18+
• State: Redux Toolkit or Zustand
• UI: Material-UI or Ant Design
• Real-time: Socket.IO client
• Charts: Recharts or Chart.js

VIDEO PROCESSING:
═════════════════
• Streaming: RTSP → WebRTC conversion
• Detection: YOLOv8 for object detection
• Head Pose: MediaPipe or Dlib
• Edge Computing: NVIDIA Jetson for on-premise

AUDIO PROCESSING:
═════════════════
• Stream: WebRTC or GStreamer
• Detection: Librosa + Custom ML model
• VAD: WebRTC VAD or Silero VAD

STORAGE:
════════
• Hot: Local SSD (0-7 days)
• Warm: S3/Azure Blob (7-90 days)
• Cold: Glacier/Archive (90+ days)

DEPLOYMENT:
═══════════
• Containers: Docker + Kubernetes
• Load Balancer: NGINX or AWS ALB
• Monitoring: Prometheus + Grafana
• Logging: ELK Stack
```

### 5.2 Performance Considerations

```
REAL-TIME REQUIREMENTS:
═══════════════════════

Alert Delivery:
• Target: < 2 seconds from detection to notification
• Acceptable: < 5 seconds
• Critical path optimization needed

Video Streaming:
• Latency: < 500ms preferred
• Frame rate: 15-30 FPS
• Resolution: 720p minimum, 1080p ideal

Database Queries:
• Alert fetch: < 100ms
• Session load: < 200ms
• History queries: < 1s (with pagination)

SCALABILITY:
════════════

Concurrent Sessions:
• Target: 100 simultaneous exam sessions
• Per session: 6 cameras + 4 mics = 10 streams
• Total: 1000 concurrent streams

Detection Throughput:
• 30 FPS × 6 cameras = 180 frames/sec per hall
• 100 halls = 18,000 frames/sec
• Use GPU batching: Process 32-64 frames/batch

WebSocket Connections:
• Invigilators: 100 connections
• Control referees: 10 connections
• Use connection pooling and load balancing
```

### 5.3 Security Measures

```
AUTHENTICATION:
═══════════════
• JWT tokens with refresh mechanism
• 2FA for admin/referee accounts
• Session timeout: 4 hours
• Password policy: Min 12 chars, complexity

AUTHORIZATION:
══════════════
• Role-Based Access Control (RBAC)
• Resource-level permissions
• Hall-specific access for invigilators

DATA PROTECTION:
════════════════
• TLS 1.3 for all connections
• End-to-end encryption for video streams
• Encrypted at rest (database, storage)
• PII anonymization in logs

COMPLIANCE:
═══════════
• GDPR: Right to erasure, data portability
• Data retention: Configurable per region
• Audit logs: 2-year retention
• Video: 90-day default retention
```

### 5.4 Testing Strategy

```
UNIT TESTS:
═══════════
• Detection algorithms (accuracy > 90%)
• Alert tier classification
• Aggregation logic
• State machine transitions

INTEGRATION TESTS:
══════════════════
• API endpoints
• Database operations
• WebSocket communication
• Video stream processing

E2E TESTS:
══════════
• Complete user flows (admin, invigilator)
• Alert processing end-to-end
• Device health check workflow
• Session creation and monitoring

PERFORMANCE TESTS:
══════════════════
• Load testing: 100 concurrent sessions
• Stress testing: Peak detection rates
• Latency testing: Alert delivery time
• Video streaming under load
```

---

## Summary

This architecture provides:

✅ **Clear Separation of Concerns**: Admin manages infrastructure, Invigilators monitor exams
✅ **Scalable Design**: Supports 100+ concurrent sessions
✅ **Real-time Performance**: < 2s alert delivery, < 500ms video latency
✅ **Intelligent Alerting**: Tiered system reduces overwhelm
✅ **Comprehensive Audit**: Full tracking from detection to resolution
✅ **Flexible Infrastructure**: Halls + Devices model allows easy expansion

Ready for implementation! 🚀
