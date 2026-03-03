# Thaqib — Development Timeline & Roadmap

> **Last Updated:** 2026-03-03
>
> Each phase produces a **full-product MVP** — a working, demonstrable system across all domains. The team works in parallel on their respective domains within each phase, converging at the phase deliverable.

---

## How to Read This Document

| Symbol | Meaning                          |
| ------ | -------------------------------- |
| `[ ]`  | Not started                      |
| `[/]`  | In progress                      |
| `[x]`  | Completed                        |
| 🏁     | Phase MVP — a demo-ready product |

**Domains:** 🎥 Video Detection · 🎙️ Audio Detection · 🎨 UI/UX · 🖥️ Front-end · ⚙️ Back-end · 🐳 DevOps

---

## Phase Overview

| Phase | MVP Name               | Status    | What You Can Demo                                                      |
| ----- | ---------------------- | --------- | ---------------------------------------------------------------------- |
| 0     | Project Foundation     | ✅ Done   | Repo, architecture, dev environment                                    |
| 1     | Solo Developer Station | 🔄 Active | One person at a desk → detections on screen + audio events in terminal |
| 2     | Team Exam Simulation   | ⏳        | 3–5 people in a room → neighbor alerts on a live dashboard             |
| 3     | Full Integrated System | ⏳        | Multi-camera + multi-mic → dashboard with alerts, PTT, session reports |
| 4     | Premises-Ready Release | ⏳        | Containerized install wizard → deploy to a real exam hall              |

---

## Phase 0 — Project Foundation ✅

> **Responsible:** All Team Members
> **Goal:** Project structure, architectural plans, and developer tools ready for the team to start.

- [x] Workspace setup: complete environment, repository, and system architecture plans.

---

## Phase 1 — MVP: Solo Developer Station 🔄

> **Goal:** A single developer can test the whole flow at home. Sitting at a desk with a webcam and mic, the system identifies the person, detects where they are looking, and highlights suspicious sounds. A basic dashboard shows these events live on the same computer.

- [ ] 🎥 **Video Detection**: Complete solo gaze detection pipeline (tracking, head pose, and looking-away rules).
- [ ] 🎙️ **Audio Detection**: Setup real-time audio capture, silence filtering, and basic whisper detection.
- [ ] 🎨 **UI/UX**: Finalize the core design system and wireframes for the "Main Monitoring" page.
- [ ] 🖥️ **Front-end**: Build the **Monitoring Dashboard (V1)** showing a real-time event feed of alerts.
- [ ] ⚙️ **Back-end**: Set up the event ingestion API and live broadcast logic for pushing alerts to the front-end.
- [ ] 🐳 **DevOps**: Create the "Solo Station" launcher to start the full stack on a single machine.

---

## Phase 1 — Testing Summary

| Target        | Simulation Requirement                        | Success Goal                                     |
| ------------- | --------------------------------------------- | ------------------------------------------------ |
| **People**    | Developer sitting alone at a desk             | AI detects and tracks the person immediately     |
| **Vision**    | Look at a phone/neighbor (simulated) > 3s     | A "Suspicious Gaze" alert shows on the dashboard |
| **Sound**     | Whisper or make noise near the mic            | An "Audio Anomaly" alert appears                 |
| **Accuracy**  | Normal behavior (writing, thinking) for 5 min | Very few or zero false alerts                    |
| **Speed**     | Monitor the system "heartbeat" (FPS)          | System stays responsive without lag              |
| **Integrity** | Start the whole system together               | No technical crashes for a 10-minute session     |

---

## Phase 2 — MVP: Team Exam Simulation ⏳

> **Goal:** The team simulates a mini-exam. Multiple cameras track 3–5 people, identifying who is sitting next to whom. Looking at a neighbor's desk triggers a specific "neighbor alert." The audio system knows which mic (which zone) detected a sound. The dashboard now has full camera feeds, a historical timeline, and database storage.

- [ ] 🎥 **Video Detection**: Multi-person tracking and spatial "risk angle" modeling for neighbor detection.
- [ ] 🎙️ **Audio Detection**: Implement "Audio Zones" to isolate whispers using multiple microphone inputs.
- [ ] 🎨 **UI/UX**: Design the **Hall Overview** (multi-hall grid) and the **Alert Management** flows.
- [ ] 🖥️ **Front-end**: Develop the **Hall Grid Page** and the **Detailed Hall View (V1)** with video grid thumbnails.
- [ ] ⚙️ **Back-end**: Implement the permanent database (PostgreSQL) and APIs for Hall/Device management.
- [ ] 🐳 **DevOps**: Package the team environment for multi-camera and multi-mic simulation testing.

---

## Phase 2 — Testing Summary

| Target             | Simulation Requirement                  | Success Goal                                      |
| ------------------ | --------------------------------------- | ------------------------------------------------- |
| **Crowd Control**  | 3–5 people moving around naturally      | System never mixes up their IDs                   |
| **Neighbor Alert** | Person A looks at Person B's desk       | Correct alert with both names appears in < 5s     |
| **Sound Location** | Whisper near Mic #1                     | Alert is specifically linked to "Zone 1" students |
| **Room Ambience**  | Loud general noise (clap or door slam)  | System ignores it as "Environment Noise"          |
| **Supervisor UI**  | Login, view hall, and use Voice Chat    | All buttons and voice features work smoothly      |
| **Data Storage**   | Start an exam, trigger alerts, end exam | All data is saved in the database correctly       |

---

## Phase 3 — MVP: Full Integrated System ⏳

> **Goal:** The "Gold Standard" of the system. All pieces are connected and talk to each other perfectly. Video and audio data are merged to detect complex cheating. Supervisors receive high-priority alerts when multiple bad signs happen at once. At the end of an exam, a full "Summary Report" is generated automatically.

- [ ] 🎥 **Video Detection**: High-speed production pipeline with resilient multi-camera handling.
- [ ] 🎙️ **Audio Detection**: Professional multi-mic integration with perfect time-sync to video events.
- [ ] 🎨 **UI/UX**: Design the **Session Report** templates and the **System Settings** interface.
- [ ] 🖥️ **Front-end**: Build the **History & Reports Page** and the **Admin Management Panel**.
- [ ] ⚙️ **Back-end**: Develop the "Multi-modal Correlation" engine and the automated Report Generator (PDF).
- [ ] 🐳 **DevOps**: Centralized log monitoring and health-check system for the entire stack.

---

## Phase 3 — Testing Summary

| Target          | Simulation Requirement                        | Success Goal                                     |
| --------------- | --------------------------------------------- | ------------------------------------------------ |
| **Full Flow**   | Actual behavior → Pipeline → Server → Web UI  | Alert surfaces on dashboard within 3 seconds     |
| **Correlation** | Look at neighbor AND whisper at the same time | System upgrades this to a "Tier 2 / Critical"    |
| **Resilience**  | Unplug a camera while the session is running  | System remains stable; UI shows "Camera Offline" |
| **End of Exam** | Click "End Session"                           | System generates a report with maps and stats    |
| **Endurance**   | Run the system for 2+ hours                   | No slowdowns, no crashes, no overheating         |

---

## Phase 4 — MVP: Premises-Ready Release ⏳

> **Goal:** The final project deliverable. A "One-Click Install" package ready to be handed to a university. It includes a "Setup Wizard" for non-technical users to configure their halls and cameras. This is the version that will be tested on real IP cameras in a real exam hall for the graduation project final demo.

- [ ] 🎥 **Video Detection**: Production hardware support (RTSP cameras) and GPU-accelerated processing.
- [ ] 🎙️ **Audio Detection**: Final room-calibration tools and professional microphone hardware support.
- [ ] 🎨 **UI/UX**: Conduct a final usability audit and polish all mobile-responsive views.
- [ ] 🖥️ **Front-end**: Implement the **Mobile Invigilator App (V1)** with real-time haptic alerts.
- [ ] ⚙️ **Back-end**: Security hardening (rate limiting, auth refresh) and disaster recovery backups.
- [ ] 🐳 **DevOps**: Build the **Thaqib Setup Wizard** for automated building and hall registration.

---

## Phase 4 — Testing Summary

| Target             | Simulation Requirement                       | Success Goal                                     |
| ------------------ | -------------------------------------------- | ------------------------------------------------ |
| **Retail Setup**   | Run the "Setup Wizard" on a clean computer   | System is configured and ready in < 5 mins       |
| **Real Hardware**  | Connect to university IP cameras             | Video is clear and AI detects students correctly |
| **Real Scale**     | 3 Cameras + 3 Mics + 10+ Students            | System stays stable for the entire 2-hour exam   |
| **Staff Mobility** | Login via phone while walking between aisles | Real-time alerts vibrate phone correctly         |
| **Recovery**       | Restart the server mid-exam (Crash test)     | All session data is recovered upon restart       |
| **Final Demo**     | Graduation project committee walkthrough     | Smooth, professional end-to-end presentation     |

---

## Detailed Dashboard Page Roadmap

This section defines which pages the **Front-end** and **UI/UX** specialists will deliver at each phase.

| Phase | Page / Feature              | Description                                                                  |
| ----- | --------------------------- | ---------------------------------------------------------------------------- |
| **1** | **Live Alerts Feed**        | Centralized list showing real-time video/audio events with severity colors.  |
| **2** | **Hall Grid Overview**      | A dashboard showing status cards for all halls (e.g., Hall A12: 🟢 Online).  |
| **2** | **Detailed Hall View (V1)** | Live thumbnails/feeds from multiple cameras + Real-time event timeline.      |
| **3** | **History & Reports**       | Searchable database of past exam sessions with drill-down to specific dates. |
| **3** | **Settings & Management**   | UI for adding/editing halls, devices (IP/Port), and supervisor accounts.     |
| **3** | **Session Summary Report**  | Automatically generated page/PDF showing total alerts, charts, and maps.     |
| **4** | **Mobile Invigilator View** | Responsive version with notification centers for supervisors on the walk.    |
| **4** | **Setup Wizard**            | Interactive multi-step guide for initial system installation and dry-run.    |

---

## Commands to Resume

```bash
# Activate environment
cd "f:\University\Graduation project_Smart Cheating System\Thaqib---Smart-Cheating-Detection-System"
.\venv\Scripts\activate

# Run demo
python scripts/demo_video.py --source 0

# Git status
git branch   # Should be on develop
git log -3   # Recent commits
```

---

## Known Issues

1. **MediaPipe Version**: Must use 0.10.30+ (Tasks API, not legacy solutions)
2. **Model Download**: `face_landmarker.task` auto-downloads to `models/` folder on first run
