# Feature Specification: Control Room Escalation Workflow

**Feature Branch**: `001-control-room-escalation`

**Created**: 2026-06-09

**Status**: Draft

**Input**: User description: "wait a second, why do we have admin and referee?, aren't both the same thing?

there is a gap here we need to discuss, since the admin would be in a control room and viewing a realistic number of halls simultanesly (what do u think is the number of halls, note that the required fow is that after this plan, the system would typicaly be functional for the invigilator to review alers and take actions fully from theiir dashboard wihle they are in the hall , with the control room (admins) to be a safeguard to alert the inivigilator of an incident if they have not taken an action in it .. etc of actions and roles we need to dicuss the control room shold do, and then also we need to dicuss how the assignment of the admin (control room) should be done?"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Invigilator Handles Hall Alerts Directly (Priority: P1)

As an invigilator assigned to a hall, I need to see incident alerts for my hall and take action from my dashboard so exam incidents are handled on-site without waiting for control room intervention.

**Why this priority**: The invigilator action flow is the primary operational requirement and must work independently for the system to deliver core value.

**Independent Test**: Can be fully tested by generating alerts in one hall, verifying they appear for the assigned invigilator, and confirming the invigilator can acknowledge, classify, and close each alert.

**Acceptance Scenarios**:

1. **Given** an invigilator is assigned to Hall A and a new incident is detected in Hall A, **When** the invigilator opens the dashboard, **Then** the incident appears with sufficient context to decide an action.
2. **Given** an open incident in the invigilator's hall, **When** the invigilator records an action decision, **Then** the incident status changes and is visible in the shared incident timeline.
3. **Given** an invigilator has already acted on an incident, **When** control room staff view the incident, **Then** they see it as handled and no escalation reminder is triggered.

---

### User Story 2 - Control Room Safeguards Unhandled Incidents (Priority: P2)

As a control room admin, I need to monitor multiple halls and intervene only when hall invigilators do not act within a target response window so that unresolved incidents are not missed.

**Why this priority**: This provides resilience and governance, but depends on the primary invigilator workflow already functioning.

**Independent Test**: Can be fully tested by creating incidents where invigilators do not respond and verifying control room escalation notifications are generated and tracked.

**Acceptance Scenarios**:

1. **Given** an incident remains unacknowledged after the configured response window, **When** control room staff are monitoring active halls, **Then** the incident is highlighted as requiring safeguard action.
2. **Given** a control room admin triggers safeguard escalation, **When** the escalation is sent, **Then** the assigned invigilator receives an explicit prompt to take action.
3. **Given** an incident is escalated by control room, **When** the invigilator later resolves it, **Then** the incident history records both safeguard escalation and final hall action.

---

### User Story 3 - Supervisor Assigns Control Room Coverage (Priority: P3)

As an operations supervisor, I need to assign control room admins to hall groups for each exam session so monitoring load is realistic and every hall has backup coverage.

**Why this priority**: Assignment controls scalability and accountability but can be delivered after direct alert handling and safeguard escalation are defined.

**Independent Test**: Can be fully tested by configuring hall-to-admin assignments for a session and verifying only assigned halls appear in each control room view.

**Acceptance Scenarios**:

1. **Given** a supervisor creates an exam session with multiple halls, **When** they assign hall groups to control room admins, **Then** each hall is covered by exactly one primary control room admin.
2. **Given** a control room admin has assigned halls, **When** they open their dashboard, **Then** they only see incidents from halls in their assignment scope.
3. **Given** an assignment is updated during an active session, **When** reassignment is confirmed, **Then** monitoring scope changes immediately and an audit record is created.

---

### Edge Cases

- What happens when an incident is duplicated by repeated detections in a short period for the same student and hall?
- How does the system handle temporary connectivity loss for an invigilator dashboard while incidents continue to be generated?
- What happens if a hall has no assigned invigilator at session start?
- How does the system behave when a control room admin reaches assigned hall capacity and a new hall needs coverage?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST define two distinct operational roles: `Invigilator` (hall-level action owner) and `Control Room Admin` (cross-hall safeguard monitor).
- **FR-002**: System MUST allow invigilators to view, acknowledge, classify, and close incidents for halls they are assigned to.
- **FR-003**: System MUST present incident context required for action decisions, including hall, timestamp, severity, and status history.
- **FR-004**: System MUST start a response timer for each new incident and flag incidents with no invigilator action within the configured window.
- **FR-005**: System MUST notify the assigned control room admin when an incident crosses the no-action threshold.
- **FR-006**: Control room admins MUST be able to send safeguard escalation prompts to invigilators for unhandled incidents.
- **FR-007**: System MUST keep a complete incident timeline that records all actions by both invigilators and control room admins.
- **FR-008**: System MUST support session-based hall assignment for control room admins with configurable capacity limits.
- **FR-009**: System MUST enforce a default assignment capacity of up to 12 halls per control room admin, with supervisor override for low/high-risk sessions.
- **FR-010**: System MUST provide supervisors with an assignment interface showing hall coverage, current load per control room admin, and unassigned halls.
- **FR-011**: System MUST prevent incidents from remaining without an accountable owner by requiring each active hall to have an invigilator and mapped control room coverage.
- **FR-012**: System MUST provide role-specific dashboards so invigilators and control room admins see only incidents relevant to their responsibilities.

### Key Entities *(include if feature involves data)*

- **Incident**: A detected exam-event alert with hall reference, severity, lifecycle status, timestamps, and action timeline.
- **Invigilator Assignment**: Mapping of invigilator to one hall for a session, including active shift window and assignment status.
- **Control Room Coverage Assignment**: Mapping of control room admin to a set of halls for a session, including hall count and capacity threshold.
- **Safeguard Escalation**: A record of control room intervention for an unhandled incident, including trigger reason and recipient invigilator.
- **Exam Session**: Operational window grouping halls, personnel assignments, and active incident monitoring rules.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 95% of incidents are acknowledged by the assigned invigilator within 2 minutes of alert creation during live exam sessions.
- **SC-002**: 100% of incidents without invigilator action after the configured threshold are surfaced to control room admins within 15 seconds of threshold breach.
- **SC-003**: Control room admins can oversee assigned halls with no more than 2 unresolved, overdue incidents per admin under standard load (up to 12 halls each).
- **SC-004**: 100% of active halls in a session have both an assigned invigilator and mapped control room coverage before session start.
- **SC-005**: At least 90% of invigilators complete incident action workflow without external assistance during pilot sessions.

## Assumptions

- A referee role in prior wording is treated as equivalent to the invigilator role for hall-level incident handling.
- Session setup is completed before exam start, including hall roster and user-role assignments.
- Control room admins are intended as backup/safeguard operators, not primary decision-makers for routine incidents.
- Default control room monitoring capacity is 12 halls per admin as a realistic baseline for simultaneous oversight, adjustable by supervisors.
- Alert severity and response threshold policies are configurable per institution and exist before this workflow is activated.
