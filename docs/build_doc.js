/* Thaqib graduation documentation generator.
   Grounded in the actual source code under src/thaqib/.
   Produces: Thaqib_Graduation_Documentation.docx
*/
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat, TableOfContents, HeadingLevel,
  BorderStyle, WidthType, ShadingType, VerticalAlign, PageNumber, PageBreak,
  SectionType, NumberFormat, Tab, TabStopType, TabStopPosition, ImageRun,
} = require("docx");

// generated diagram manifest { key: {path, w, h} }
const FIGS = JSON.parse(fs.readFileSync(path.join(__dirname, "figures", "manifest.json"), "utf-8"));

// ---------- constants ----------
const FONT = "Times New Roman";
const ARABIC_FONT = "Arial";
const A4 = { width: 11906, height: 16838 };
const MARGIN = { top: 1440, right: 1440, bottom: 1440, left: 1440 };
const CONTENT_W = A4.width - MARGIN.left - MARGIN.right; // 9026
const BLUE = "1F4E79";
const LIGHT = "D9E2F3";
const GREY = "F2F2F2";

// ---------- helpers ----------
const T = (text, opts = {}) => new TextRun({ text, font: FONT, ...opts });

function P(text, opts = {}) {
  const { align, spacingAfter = 120, spacingBefore = 0, bold, italic, size = 24, color, indent } = opts;
  return new Paragraph({
    alignment: align,
    spacing: { after: spacingAfter, before: spacingBefore, line: 276 },
    indent,
    children: Array.isArray(text) ? text : [T(text, { bold, italics: italic, size, color })],
  });
}

function H1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 240, after: 160 },
    children: [T(text)],
  });
}
function H2(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 200, after: 120 }, children: [T(text)] });
}
function H3(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_3, spacing: { before: 160, after: 100 }, children: [T(text)] });
}
function chapterTitle(num, title) {
  // Heading 1 used for TOC; styled big
  return [
    new Paragraph({ spacing: { before: 240, after: 0 }, alignment: AlignmentType.CENTER,
      children: [T(`CHAPTER ${num}`, { bold: true, size: 28, color: BLUE })] }),
    new Paragraph({
      heading: HeadingLevel.HEADING_1,
      alignment: AlignmentType.CENTER,
      spacing: { before: 60, after: 200 },
      children: [T(title)],
    }),
  ];
}

function bullet(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "bullets", level },
    spacing: { after: 60, line: 276 },
    children: Array.isArray(text) ? text : [T(text, { size: 24 })],
  });
}
function numItem(text, ref = "nums") {
  return new Paragraph({
    numbering: { reference: ref, level: 0 },
    spacing: { after: 60, line: 276 },
    children: Array.isArray(text) ? text : [T(text, { size: 24 })],
  });
}

// monospace bordered diagram block (used for real architecture/data-flow from code)
function diagram(lines, caption) {
  const b = { style: BorderStyle.SINGLE, size: 4, color: BLUE };
  const rows = lines.map((ln) =>
    new Paragraph({
      spacing: { after: 0, line: 240 },
      children: [new TextRun({ text: ln === "" ? " " : ln, font: "Consolas", size: 16 })],
    })
  );
  const cell = new TableCell({
    borders: { top: b, bottom: b, left: b, right: b },
    shading: { fill: GREY, type: ShadingType.CLEAR },
    margins: { top: 120, bottom: 120, left: 160, right: 160 },
    width: { size: CONTENT_W, type: WidthType.DXA },
    children: rows,
  });
  const tbl = new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: [CONTENT_W],
    rows: [new TableRow({ children: [cell] })],
  });
  return [tbl, figCaption(caption)];
}

function figCaption(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 80, after: 200 },
    children: [T(text, { italics: true, size: 20, color: "555555" })],
  });
}

// embed a generated diagram PNG (from diagrams.js), scaled to fit content width
function figure(key, caption, maxW = 580) {
  const f = FIGS[key];
  if (!f) throw new Error("missing figure: " + key);
  const dispW = Math.min(maxW, f.w);
  const dispH = Math.round((dispW * f.h) / f.w);
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 120, after: 40 },
      children: [
        new ImageRun({
          type: "png",
          data: fs.readFileSync(path.join(__dirname, f.path)),
          transformation: { width: dispW, height: dispH },
          altText: { title: caption, description: caption, name: key },
        }),
      ],
    }),
    figCaption(caption),
  ];
}

// captioned placeholder for diagrams/screenshots the team must insert
function figurePlaceholder(caption, hint) {
  const b = { style: BorderStyle.DASHED, size: 6, color: "999999" };
  const cell = new TableCell({
    borders: { top: b, bottom: b, left: b, right: b },
    shading: { fill: "FAFAFA", type: ShadingType.CLEAR },
    margins: { top: 360, bottom: 360, left: 160, right: 160 },
    width: { size: CONTENT_W, type: WidthType.DXA },
    verticalAlign: VerticalAlign.CENTER,
    children: [
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
        children: [T("[ INSERT FIGURE HERE ]", { bold: true, color: "999999", size: 22 })] }),
      new Paragraph({ alignment: AlignmentType.CENTER,
        children: [T(hint, { italics: true, color: "999999", size: 18 })] }),
    ],
  });
  const tbl = new Table({ width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: [CONTENT_W],
    rows: [new TableRow({ children: [cell] })] });
  return [tbl, figCaption(caption)];
}

// generic table builder
function makeTable(headers, rows, widths) {
  const b = { style: BorderStyle.SINGLE, size: 2, color: "BFBFBF" };
  const borders = { top: b, bottom: b, left: b, right: b };
  const headerRow = new TableRow({
    tableHeader: true,
    children: headers.map((h, i) =>
      new TableCell({
        borders, width: { size: widths[i], type: WidthType.DXA },
        shading: { fill: BLUE, type: ShadingType.CLEAR },
        margins: { top: 60, bottom: 60, left: 110, right: 110 },
        verticalAlign: VerticalAlign.CENTER,
        children: [new Paragraph({ children: [T(h, { bold: true, color: "FFFFFF", size: 21 })] })],
      })
    ),
  });
  const bodyRows = rows.map((r, ri) =>
    new TableRow({
      children: r.map((c, i) =>
        new TableCell({
          borders, width: { size: widths[i], type: WidthType.DXA },
          shading: { fill: ri % 2 ? "FFFFFF" : GREY, type: ShadingType.CLEAR },
          margins: { top: 50, bottom: 50, left: 110, right: 110 },
          verticalAlign: VerticalAlign.CENTER,
          children: [new Paragraph({ children: Array.isArray(c) ? c : [T(String(c), { size: 21 })] })],
        })
      ),
    })
  );
  return new Table({ width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths: widths, rows: [headerRow, ...bodyRows] });
}

function tableCaption(text) {
  return new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 },
    children: [T(text, { italics: true, size: 20, color: "555555" })] });
}

function AR(text, opts = {}) {
  // Arabic RTL paragraph
  return new Paragraph({
    bidirectional: true,
    alignment: opts.align || AlignmentType.RIGHT,
    spacing: { after: opts.after ?? 140, line: 300 },
    children: [new TextRun({ text, font: ARABIC_FONT, rightToLeft: true, size: opts.size || 26, bold: opts.bold, color: opts.color })],
  });
}

const spacer = (n = 1) => Array.from({ length: n }, () => new Paragraph({ children: [T("")] }));

// =====================================================================
//  COVER PAGE  (preserved data from the previous documentation)
// =====================================================================
const team = [
  ["1", "812563413", "Shady Mohamed Faragallah", "IS"],
  ["2", "812554892", "Mohamed Elsaed Koresh", "CS"],
  ["3", "812563731", "Amir Salah Sobh", "AI"],
  ["4", "808970279", "Mohamed Elsaiead Shalan", "CS"],
  ["5", "804631158", "Amr Talaat Ahmed Ahmed", "IT"],
  ["6", "802323495", "Mohamed Nasser Ramez Elafify", "CS"],
  ["7", "806517931", "Ahmed Waleed Elshety", "CS"],
];

function coverTeamTable() {
  const widths = [900, 2100, 4200, 1826];
  return makeTable(["No.", "ID", "Name", "Department"], team, widths);
}

const cover = [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 },
    children: [T("Damietta University", { bold: true, size: 26 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 },
    children: [T("Faculty of Computers and Artificial Intelligence", { bold: true, size: 24 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 300 },
    children: [T("Information Systems Department", { size: 24 })] }),
  ...spacer(1),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 },
    children: [T("THAQIB", { bold: true, size: 64, color: BLUE })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 20 },
    children: [new TextRun({ text: "ثاقب", font: ARABIC_FONT, rightToLeft: true, size: 44, bold: true, color: BLUE })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 },
    children: [T("A Real-Time, AI-Powered Smart Cheating Detection System", { bold: true, size: 30 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 300 },
    children: [T("Graduation Project Documentation", { italics: true, size: 24, color: "555555" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 },
    children: [T("Submitted by the Project Team", { bold: true, size: 24 })] }),
  coverTeamTable(),
  ...spacer(1),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200, after: 40 },
    children: [T("Under the Supervision of", { size: 24 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
    children: [T("Dr. Wael Abdel Qader Awad", { bold: true, size: 28 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 0 },
    children: [T("Academic Year 2025 / 2026", { bold: true, size: 24 })] }),
];

// =====================================================================
//  FRONT MATTER
// =====================================================================
const dedication = [
  H1("Dedication"),
  P("To our families, whose patience and unconditional support carried us through every late night and every deadline."),
  P("To our supervisor, Dr. Wael Abdel Qader Awad, whose guidance shaped both this project and the way we think about engineering real systems."),
  P("And to every invigilator who has ever tried to watch a crowded examination hall with nothing but two eyes — this work is for you."),
];

const acknowledgement = [
  H1("Acknowledgement"),
  P("First and foremost, we thank God for granting us the health, patience, and persistence to complete this project."),
  P("We extend our sincere gratitude to our supervisor, Dr. Wael Abdel Qader Awad, for his continuous guidance, valuable feedback, and encouragement throughout every stage of this work. His insights helped us turn an ambitious idea into a working system."),
  P("We are also grateful to the staff of the Faculty of Computers and Artificial Intelligence, Damietta University, for the knowledge and academic foundation that made this project possible, and to our colleagues and families for their constant support."),
];

const abstract = [
  H1("Abstract"),
  P("Maintaining integrity during in-person examinations remains a difficult problem: a single invigilator cannot continuously watch every student in a crowded hall, and fatigue, distraction, and limited lines of sight allow some cheating to go unnoticed. This project presents Thaqib (Arabic: ثاقب, “piercing” or “sharp-sighted”), a real-time, AI-powered system that assists — but never replaces — human invigilators."),
  P("Thaqib is deliberately designed as a decision-support, human-in-the-loop tool, analogous to the Video Assistant Referee (VAR) in football: it surfaces likely incidents for human review and takes no disciplinary action automatically. The system fuses two independent perception pipelines. The video pipeline detects students with a YOLOv11 person detector, tracks them across frames with the BoT-SORT tracker, preserves identity through occlusions with an OSNet re-identification model, extracts 478 facial landmarks with MediaPipe, and computes a per-student gaze vector from head orientation and iris deviation. A spatial k-nearest-neighbour model attributes a sustained gaze toward a specific neighbour’s examination paper as a cheating event. A parallel object model flags mobile phones anywhere in the frame. The audio pipeline distinguishes localized whispering from global hall noise using a calibrated multi-microphone energy discriminator, confirms human speech with Silero Voice Activity Detection, and optionally transcribes it with Faster-Whisper for keyword matching."),
  P("Every confirmed event produces tamper-evident forensic evidence — an annotated video clip containing two seconds before and after the incident, or an audio clip with a transcript and SHA-256 hash. Events are delivered to a web-based control room (FastAPI backend, React dashboard with a fully Arabic, right-to-left interface) where assigned operators confirm or dismiss each alert and direct invigilators to the exact seat over a live hall voice channel. The result is a practical, privacy-respecting system that increases the effective “reach” of human supervision without recording or judging students automatically."),
  P([T("Keywords: ", { bold: true, size: 24 }), T("Computer Vision, Real-Time Object Detection, Multi-Object Tracking, Gaze Estimation, Multimodal Analysis, Exam Proctoring, Human-in-the-Loop, Decision Support.", { size: 24 })]),
];

// =====================================================================
//  CHAPTER 1 — INTRODUCTION
// =====================================================================
const ch1 = [
  ...chapterTitle(1, "Introduction"),
  H2("1.1  Background"),
  P("The number of students sitting examinations grows every year, while the number of qualified invigilators per hall does not. Traditional invigilation depends almost entirely on human attention, which is inherently limited: a supervisor cannot simultaneously watch every seat, and fatigue, distraction, and physical occlusions (a raised arm, a neighbour’s back) create blind spots that determined students exploit."),
  P("In parallel, advances in computer vision and audio signal processing have made it possible to analyse human behaviour in real time on commodity hardware. These technologies create an opportunity to augment — not replace — human supervision. Thaqib applies them to the specific, bounded problem of detecting suspicious behaviour during in-person exams and routing it to a human for judgement."),
  H2("1.2  Motivation"),
  P("Cheating undermines the credibility of an institution and the principle of equal opportunity. Crucially, in most academic regulations a cheating decision must be made during the exam, while the act can still be witnessed and verified; evidence surfaced only after the session has ended is often inadmissible. Systems that simply record everything for later review therefore solve the wrong problem and raise their own privacy concerns."),
  P("Thaqib is motivated by the VAR analogy from football. VAR does not overrule the referee; it draws the referee’s attention to an incident worth a second look. Likewise, Thaqib never declares a student guilty. It raises a timely, evidence-backed alert and lets a human decide — reducing legal and ethical risk while making each invigilator far more effective."),
  H2("1.3  Problem Statement"),
  P("Even with invigilators present, behaviours such as copying from a neighbour’s paper, glancing at a hidden phone, or whispering answers are hard to catch reliably and consistently. The difficulty multiplies in crowded halls with background noise and frequent visual occlusion."),
  P("The core problem this project addresses is: how can a system detect cheating-related behaviour in real time, from live video and audio, accurately enough to be useful and with few enough false alarms to be trusted — while respecting student privacy and leaving every final decision to a human?"),
  H2("1.4  Proposed Solution"),
  P("Thaqib integrates live camera and microphone feeds from an examination hall and processes them on-premises. Computer-vision components analyse where each student is looking and whether a phone is visible; audio components distinguish a localized whisper from general hall noise. When a behaviour crosses a configurable threshold sustained over time, the system generates an alert and saves a short evidence clip. Alerts flow to a control-room dashboard for human confirmation; confirmed incidents are pushed to the relevant invigilator, who responds in person."),
  P("No autonomous sanction is ever applied, and no continuous student footage is judged by the machine — only short, event-triggered clips are produced, and only during scheduled sessions."),
  H2("1.5  Objectives"),
  numItem("Design an AI system that detects gaze-based copying, phone usage, and suspicious audio in real time from live exam feeds."),
  numItem("Keep a human firmly in the loop: every alert is reviewed, and the system never issues an automatic verdict."),
  numItem("Attribute a detected gaze precisely — identifying both the suspected student and the specific neighbour whose paper was targeted."),
  numItem("Produce tamper-evident forensic evidence (annotated video / hashed audio) suitable for human review."),
  numItem("Deliver a practical, web-based control room and invigilator interface, with live voice coordination, deployable on a single institution’s on-premises hardware."),
  numItem("Respect privacy by avoiding continuous recording, using geometric (landmark-based) gaze features rather than identity, and storing evidence only for active sessions."),
  H2("1.6  Scope"),
  P("Thaqib targets in-person examinations inside physical halls. It acts as a decision-support tool and operates in real time. The delivered system covers three detection classes — gaze-based paper copying, mobile-phone presence, and localized audio anomalies — together with a complete management and monitoring platform (institutions, halls, devices, users, exam sessions, assignments, alert review, reporting, and a hall voice channel). Wireless-device (RF) detection is designed but reserved as future work (Chapter 5). Confirming guilt, linking incidents to verified student identities, and multi-campus cloud deployment are out of scope for this version."),
  H2("1.7  Document Organization"),
  bullet([T("Chapter 2", { bold: true, size: 24 }), T(" — the detailed problem, a survey of related proctoring systems and research, and the requirements analysis.", { size: 24 })]),
  bullet([T("Chapter 3", { bold: true, size: 24 }), T(" — the proposed framework: system architecture, the video and audio pipelines, the spatial/gaze model, the data model, and the platform design.", { size: 24 })]),
  bullet([T("Chapter 4", { bold: true, size: 24 }), T(" — implementation details grounded in the codebase, the real configuration parameters, evidence generation, deployment, and results.", { size: 24 })]),
  bullet([T("Chapter 5", { bold: true, size: 24 }), T(" — conclusions, recommendations, and future improvements.", { size: 24 })]),
];

// =====================================================================
//  CHAPTER 2 — PROBLEM, RELATED WORK, ANALYSIS
// =====================================================================
const FR = [
  ["FR-1", "Authentication & RBAC", "Authorized users (super-admin, admin, invigilator) log in over JWT sessions; every endpoint is access-controlled by role."],
  ["FR-2", "Institution & Hall Setup", "A super-admin registers the institution (with an optional university→college hierarchy), creates halls with capacity and layout, and registers camera/microphone devices."],
  ["FR-3", "Device Health & Readiness", "Each device reports a status (online/offline/error/maintenance); a hall becomes “ready” only when its registered devices are online."],
  ["FR-4", "Exam Session Management", "An admin schedules exam sessions, spanning one or more halls, and assigns invigilators and co-admins to each session."],
  ["FR-5", "Real-Time Video Monitoring", "The system ingests live camera streams and detects, tracks, and monitors students during the session."],
  ["FR-6", "Gaze-Based Cheating Detection", "The system estimates each monitored student’s gaze and flags a sustained look toward a neighbour’s paper, identifying both parties."],
  ["FR-7", "Phone Detection", "The system detects a mobile phone anywhere in the frame and raises an independent alert."],
  ["FR-8", "Audio Anomaly Detection", "The system distinguishes localized whispering from global hall noise and flags confirmed speech in a silent exam."],
  ["FR-9", "Evidence Generation", "Each event produces an annotated video clip (pre + event + post) or an audio clip with transcript and integrity hash."],
  ["FR-10", "Alert Review Queue", "Alerts enter a shared queue; an assigned admin confirms or cancels each one, with optional notes."],
  ["FR-11", "Invigilator Coordination", "A confirmed incident is pushed to the invigilator’s device; control room and invigilators talk over a live hall voice channel."],
  ["FR-12", "Session Reporting", "After an exam, the system aggregates alerts, resolutions, and response data into a reviewable report."],
];

const NFR = [
  ["NFR-1", "Performance", "Video and audio are processed in real time; detection runs asynchronously so the live view stays smooth."],
  ["NFR-2", "Accuracy", "Time-sustained thresholds and multi-cue confirmation keep false positives low while preserving sensitivity."],
  ["NFR-3", "Security", "JWT auth, CSRF protection, RBAC, rate limiting, and hardened HTTP security headers protect the platform."],
  ["NFR-4", "Privacy", "No continuous judging of students; geometric gaze features (not identity); evidence only during scheduled sessions."],
  ["NFR-5", "Scalability", "A database-agnostic backend (SQLite for development, PostgreSQL for production) supports concurrent multi-hall load."],
  ["NFR-6", "Reliability", "Threaded capture, sticky tracking through brief detection gaps, and graceful evidence flushing on shutdown."],
  ["NFR-7", "Usability", "A simple, fully Arabic, right-to-left dashboard for operators and a focused mobile-friendly invigilator view."],
  ["NFR-8", "Maintainability", "A modular pipeline (camera, detector, tracker, registry, gaze, evaluator) and configuration via a single settings layer."],
  ["NFR-9", "Portability", "Runs on Windows or Linux; works with USB, RTSP, or file video sources and standard microphones."],
];

const ch2 = [
  ...chapterTitle(2, "Problem Definition, Related Work and Analysis"),
  H2("2.1  Detailed Problem Definition"),
  P("Catching exam cheating in real time is fundamentally a perception-under-constraints problem. The system must answer three questions continuously and simultaneously, for every student: Where is this person looking? Is there a forbidden object near them? Is someone speaking when the room should be silent? Each question is individually hard and becomes harder in combination:"),
  bullet("Occlusion and density: students overlap in the camera view; heads turn; arms block faces. Identities must survive these gaps or tracking collapses."),
  bullet("Ambiguity of intent: a brief glance is normal; a sustained, directed look at a neighbour’s paper is not. The system must reason over time, not single frames."),
  bullet("Acoustic clutter: real halls are never silent. Pen clicks, paper shuffling, footsteps, and an invigilator’s own voice must not be mistaken for whispering."),
  bullet("Trust and ethics: a system that fires constantly will be ignored; one that records and judges students raises legal concerns. Precision and restraint are requirements, not features."),
  H2("2.2  Related Work"),
  H3("2.2.1  Online (Remote) Proctoring Platforms"),
  P("Commercial platforms such as ProctorU, Respondus Monitor, and ExamSoft monitor a single examinee through a personal webcam and microphone, usually with cloud-based analysis. They are built for remote, one-student-per-camera settings and depend on continuous internet connectivity and full session recording. They do not address a shared physical hall with many students per camera, and their always-recording model is exactly what an in-person, privacy-respecting design tries to avoid."),
  H3("2.2.2  CCTV-Based Hall Surveillance"),
  P("Many institutions already install CCTV in exam halls. In practice these feeds are watched manually (if at all) and reviewed after the fact. They provide no automated behaviour analysis, no real-time alerting, and no attribution of an incident to a specific pair of students — leaving the core invigilation burden on humans."),
  H3("2.2.3  Research on Multimodal Behaviour Analysis"),
  P("A growing body of academic work shows that combining visual cues (head pose, gaze, objects) with audio cues improves abnormal-behaviour detection over either modality alone. Thaqib builds directly on the mature open models that this research has produced — YOLO-family detectors, BoT-SORT tracking, MediaPipe face geometry, OSNet re-identification, Silero VAD, and Whisper speech recognition — and combines them into a single real-time, on-premises proctoring pipeline."),
  H3("2.2.4  Positioning of Thaqib"),
  P("Unlike remote proctoring, Thaqib targets a shared physical hall with multiple students per camera and runs entirely on-premises, removing the dependency on cloud connectivity and continuous recording. Unlike passive CCTV, it analyses behaviour automatically, attributes a gaze event to a specific neighbour’s paper, and raises an immediate, evidence-backed alert. And unlike any fully automated approach, it keeps a human as the sole decision-maker."),
  tableCaption("Table 2.1  Comparison of Thaqib with existing approaches"),
  makeTable(
    ["Aspect", "Online Proctoring", "Manual CCTV", "Thaqib"],
    [
      ["Setting", "Remote, 1 student/cam", "Physical hall", "Physical hall, many/cam"],
      ["Analysis", "Automated (cloud)", "Manual", "Automated (on-premises)"],
      ["Real-time alerts", "Partial", "No", "Yes"],
      ["Incident attribution", "N/A", "No", "Student + targeted paper"],
      ["Recording model", "Always-on", "Always-on", "Event clips only"],
      ["Decision", "Often automated", "Human", "Human (mandatory)"],
    ],
    [1800, 2400, 2200, 2626]
  ),
  H2("2.3  Requirements Analysis"),
  H3("2.3.1  Functional Requirements"),
  P("Functional requirements describe the services the system must provide. Table 2.2 lists the functions delivered by the implemented system."),
  tableCaption("Table 2.2  Functional requirements"),
  makeTable(["#", "Requirement", "Description"], FR, [900, 2600, 5526]),
  H3("2.3.2  Non-Functional Requirements"),
  P("Non-functional requirements define quality criteria the system is judged by. Table 2.3 lists them."),
  tableCaption("Table 2.3  Non-functional requirements"),
  makeTable(["#", "Requirement", "Description"], NFR, [900, 2400, 5726]),
  H3("2.3.3  User Roles"),
  P("The system enforces three roles server-side, validated from the JWT on every request:"),
  bullet([T("Super-Admin — ", { bold: true, size: 24 }), T("system setup and infrastructure: institutions, halls, devices, user accounts, and global settings; read-only observation of live monitoring.", { size: 24 })]),
  bullet([T("Admin (Control Room) — ", { bold: true, size: 24 }), T("schedules exam sessions, assigns invigilators and co-admins, monitors the live alert queue, confirms or cancels alerts, and talks to invigilators.", { size: 24 })]),
  bullet([T("Invigilator — ", { bold: true, size: 24 }), T("physically present in the hall: starts/stops hall monitoring, receives confirmed incidents on a tablet, walks to the flagged seat, and coordinates over the voice channel.", { size: 24 })]),
  H3("2.3.4  System Context"),
  P("At the highest level, Thaqib sits between the hall’s sensing devices and its human users. Figure 2.1 shows the external entities that exchange data with the system: cameras and microphones feed it; the super-admin configures it; the admin monitors and reviews; and the invigilator receives incident pushes and operates the hall."),
  ...figure("fig_context", "Figure 2.1  System context diagram"),
  H3("2.3.5  Use-Case Overview"),
  P("Figure 2.2 summarizes the primary use cases and the actors that trigger them. Each actor authenticates first, then exercises the use cases permitted by its role; the sequence, activity, state, and class views are presented alongside the design in Chapter 3."),
  ...figure("fig_usecase", "Figure 2.2  Use-Case diagram of the Thaqib system", 460),
];

// =====================================================================
//  CHAPTER 3 — PROPOSED FRAMEWORK / DESIGN
// =====================================================================
const archDiagram = [
  "+-----------------------------------------------------------------+",
  "| 1. DATA ACQUISITION                                             |",
  "|    IP cameras (RTSP / USB / file)      USB / IP microphones     |",
  "+-------------------------------+---------------------------------+",
  "                                |",
  "+-------------------------------v---------------------------------+",
  "| 2. DETECTION ENGINE  (Python)                                   |",
  "|    Video pipeline: YOLOv11 -> BoT-SORT -> OSNet -> MediaPipe    |",
  "|                    -> Gaze -> Cheating Evaluator                |",
  "|    Audio pipeline: Energy discriminator -> Silero VAD          |",
  "|                    -> Faster-Whisper -> Keyword match           |",
  "|    => emits Detection Events + saves evidence clips             |",
  "+-------------------------------+---------------------------------+",
  "                                |",
  "+-------------------------------v---------------------------------+",
  "| 3. BACKEND  (FastAPI + SQLAlchemy)                              |",
  "|    REST API . WebSocket voice . MJPEG streams . Alert review    |",
  "|    SQLite (development)  /  PostgreSQL (production)             |",
  "+-------------------------------+---------------------------------+",
  "                                |",
  "+-------------------------------v---------------------------------+",
  "| 4. DASHBOARD  (React + TypeScript + Tailwind, Arabic RTL)       |",
  "|    Admin / control-room console   .   Invigilator hall view    |",
  "+-----------------------------------------------------------------+",
];

const videoFlow = [
  "Camera frame  (USB / RTSP / file, threaded capture)",
  "      |",
  "      v",
  "YOLOv11 person detection      detector.py   (conf 0.15, imgsz 640, every 1.0s)",
  "      |",
  "      v",
  "BoT-SORT multi-object tracking   tracker.py  (persistent IDs, 30 FPS lock)",
  "      |",
  "      v",
  "OSNet re-identification        reid.py       (cosine >= 0.80 on re-entry)",
  "      |",
  "      v",
  "MediaPipe face landmarks       face_mesh.py  (478 pts, 4 parallel workers)",
  "      |",
  "      v",
  "Gaze vector                    gaze.py        (head matrix + iris deviation)",
  "      |",
  "      v",
  "k-NN neighbour + paper model   neighbors.py   (k = 6, greedy paper ownership)",
  "      |",
  "      v",
  "Cheating evaluator             cheating_evaluator.py",
  "   if cos(gaze, paper_dir) > cos(25 deg) sustained >= 2.0 s -> ALERT",
  "      |",
  "      v",
  "Annotated evidence clip  (alerts/gaze_alert_*.mp4)  +  Detection Event",
];

const erd = [
  "institutions --1:N-- halls --1:N-- devices",
  "     |                 |",
  "     |                 +--M:N-- exam_sessions   (exam_session_halls)",
  "     |",
  "     +--1:N-- users --1:N-- refresh_tokens",
  "                  |",
  "                  +--1:N-- assignments",
  "",
  "exam_sessions --1:N-- assignments --N:1-- halls",
  "exam_sessions --1:N-- detection_events --N:1-- devices",
  "exam_sessions --1:N-- group_events",
  "exam_sessions --1:N-- alerts",
  "",
  "detection_events --N:1(opt)-- group_events",
  "alerts --> detection_event (1)  XOR  group_event (1)",
];

const ch3 = [
  ...chapterTitle(3, "The Proposed Framework"),
  H2("3.1  Architectural Overview"),
  P("Thaqib is organized into four logical layers: data acquisition, a Python detection engine, a FastAPI backend, and a React dashboard. The detection engine does the heavy perception work and emits compact events; the backend stores them, manages the exam lifecycle, and delivers alerts and live video to the dashboard; the dashboard is where humans observe and decide. Figure 3.1 shows the layering."),
  ...figure("fig_arch", "Figure 3.1  High-level four-layer architecture of Thaqib", 540),
  H2("3.2  Technology Stack"),
  P("The system is built entirely on open, well-supported components. The detection engine is the most technology-dense layer; the backend and frontend use mainstream web frameworks."),
  tableCaption("Table 3.1  Implemented technology stack"),
  makeTable(["Layer", "Technologies"], [
    ["Detection — Vision", "Python, PyTorch, Ultralytics YOLOv11 (person), YOLOv8 (papers/phones), BoT-SORT (boxmot), MediaPipe Face Landmarker, OSNet re-identification"],
    ["Detection — Audio", "Silero VAD, Faster-Whisper, NumPy, SciPy, sounddevice, noise-reduction preprocessing"],
    ["Backend", "FastAPI, SQLAlchemy ORM, Alembic migrations, Pydantic v2 settings, slowapi rate limiting, native WebSockets, MJPEG over HTTP"],
    ["Database", "SQLite (development) / PostgreSQL (production), selected by DATABASE_URL with no code change"],
    ["Frontend", "React, TypeScript, Vite, Tailwind CSS, React Router — full right-to-left Arabic interface"],
  ], [2300, 6726]),
  P("There is no external message broker, no Redis, and no Kubernetes: state lives in the relational database and real-time delivery happens in-process through a WebSocket connection manager. This keeps the system deployable on a single institution’s server."),

  H2("3.3  The Video Detection Pipeline"),
  P("The video pipeline (in src/thaqib/video/) turns a raw camera frame into structured, per-student behavioural state. It is engineered for real time: full neural detection runs only about once per second, while a lightweight tracker maintains a smooth 30-frames-per-second lock on every student in between. Figure 3.2 traces the flow."),
  ...diagram(videoFlow, "Figure 3.2  The real-time video detection pipeline"),
  H3("3.3.1  Detection, Tracking and Re-Identification"),
  P("A YOLOv11 detector locates people; a separate YOLOv8 model locates examination papers and phones. Detections feed BoT-SORT, which assigns each student a persistent track ID and keeps it stable between detection cycles using a Kalman-filter motion model. Because students can be briefly occluded, an OSNet re-identification model embeds each face and re-attaches a returning student to their original ID when the cosine similarity of the embeddings exceeds 0.80 — preventing identity churn that would otherwise corrupt the spatial model."),
  H3("3.3.2  Face Geometry and Gaze Estimation"),
  P("For every monitored student, MediaPipe extracts 478 three-dimensional facial landmarks together with a head-orientation matrix. The gaze module combines two signals into a single screen-space direction: the coarse direction the head is facing (the head rotation matrix applied to the forward axis) and the fine deviation of the irises from the eye centres. The iris term is weighted (empirically, so that roughly one eye-width of iris shift corresponds to about a 45-degree gaze swing) and clamped to suppress noise from distant or partially occluded faces. The output is a normalized two-dimensional gaze vector per student."),
  H3("3.3.3  Spatial Neighbour and Paper Model"),
  P("Cheating by copying is inherently relational, so Thaqib continuously models the live seating arrangement. A vectorized k-nearest-neighbour computation (k = 6 by default) links each student to their closest peers from person-detection centroids; the graph is recomputed only when students actually move, saving computation in a mostly static hall. Each detected paper is then assigned to exactly one student through a greedy nearest-owner rule, and where no paper is detected, a heuristic paper region below a seated student’s bounding box is used as a fallback (only for students under active monitoring). Finally, each student inherits the set of papers owned by their neighbours — the candidate “targets” the gaze evaluator will test against."),
  H3("3.3.4  Cheating Evaluation Logic"),
  P("The evaluator runs synchronously, every frame, for each monitored student. For each surrounding (neighbour-owned) paper it computes the direction from the student’s head to that paper and takes the cosine of the angle against the gaze vector. If that angle falls within a tolerance (25 degrees by default) the student is “looking at” the paper. A look must be sustained beyond a duration threshold (2.0 seconds by default) before the student is flagged — this is what separates a normal glance from copying. The evaluator also records which neighbour owns the targeted paper, so an alert names both the suspected copier and the victim. A grace period tolerates brief face-detection dropouts, and a cooldown prevents the flag from oscillating when a gaze breaks for an instant. Equation 3.1 states the core test."),
  P([T("(Eq. 3.1)   ", { bold: true, size: 22 }),
     T("looking(s, p)  =  ( ĝ", { italics: true, size: 24 }),
     T("s", { italics: true, size: 16, subScript: true }),
     T(" · d̂", { italics: true, size: 24 }),
     T("s→p", { italics: true, size: 16, subScript: true }),
     T(" )  >  cos(θ", { italics: true, size: 24 }),
     T("tol", { italics: true, size: 16, subScript: true }),
     T("),   sustained for  t ≥ T", { italics: true, size: 24 }),
     T("susp", { italics: true, size: 16, subScript: true })],
     { align: AlignmentType.CENTER }),
  P("where ĝ is the unit gaze vector, d̂ the unit direction to the paper, θₜₒₗ the angular tolerance (25°), and Tₛᵤₛₚ the sustained-duration threshold (2.0 s)."),
  H3("3.3.5  Phone Detection"),
  P("Phone detection is independent of the gaze logic. The primary YOLO model is used to detect a mobile phone (COCO class “cell phone”) anywhere in the frame; a detected phone is attributed to the nearest active student within a pixel radius and immediately flags that student, triggering an evidence clip. Because it does not depend on tracking or gaze, phone detection works even for students not yet selected for gaze monitoring."),

  H2("3.4  The Audio Detection Pipeline"),
  P("The audio pipeline (in src/thaqib/audio/) runs independently of video and is designed around one realistic assumption: an exam hall is never perfectly silent. Rather than detect “sound”, it detects sound that is localized to one part of the room — the acoustic signature of a whisper between neighbours — as opposed to global noise heard everywhere. It is organized as a three-stage flow: a global/local discriminator, voice-activity detection, and optional speech transcription."),
  H3("3.4.1  Global vs. Local Discrimination"),
  P("Microphones at different positions naturally record different energy even in silence, so a fixed loudness ratio would constantly misfire. The discriminator therefore calibrates: over the first non-silent chunks of a session it learns the structural energy ratio between microphones, then normalizes every subsequent chunk against that baseline. In the two-microphone case, a chunk is flagged local only when the normalized energy imbalance exceeds twice the calibrated normal; in the many-microphone case, a sound heard by fewer than a configurable fraction of microphones is local. A hangover window prevents rapid flip-flopping, periodic recalibration adapts to changing room acoustics, and an optional cross-correlation check catches a soft global sound that merely happened to be quieter on some microphones."),
  H3("3.4.2  Speech Confirmation and Transcription"),
  P("A chunk classified as local is passed to Silero Voice Activity Detection, which confirms whether it actually contains human speech (as opposed to a pen click or chair scrape, which a transient-suppression stage also dampens). In strict mode — the default for silent exams — any confirmed speech is a violation. Optionally, Faster-Whisper transcribes the speech (Arabic by default) so that, in keyword mode, only utterances matching a configurable keyword list are flagged. A sustained-episode tracker groups repeated alerts on the same microphone into a single confirmed cheating episode."),

  H2("3.5  Alerts, Events and the Data Model"),
  P("Perception results are persisted as structured records. A single AI detection becomes a Detection Event; correlated events involving adjacent students can be grouped into a Group Event; and either kind produces an Alert for human review. Each Alert references exactly one detection event or one group event — never both. Alerts are tiered (tier-1 low severity, tier-2 high severity) and move through a reviewable lifecycle."),
  ...diagram([
    "pending  ->  claimed  ->  confirmed         (real incident, action taken)",
    "   |                  ->  cancelled          (no cheating / false positive)",
    "   +------------------>  escalated  ->  confirmed / cancelled",
  ], "Figure 3.3  Alert review lifecycle (as implemented in the Alert model and routes)"),
  P("The relational schema is built on SQLAlchemy with UUID primary keys, created/updated timestamps, and soft-delete support on infrastructure entities. Figure 3.4 shows the core entities and their relationships."),
  ...diagram(erd, "Figure 3.4  Core entity-relationship model"),
  P("Institutions can form a shallow hierarchy (university → college). Halls belong to an institution and contain devices; an exam session can span several halls (many-to-many) and is staffed through invigilator assignments and admin assignments. Detection events, group events, and alerts all hang off the exam session, giving every alert a full chain back to the device and moment that produced it."),

  H2("3.6  Backend Services and Security"),
  P("The FastAPI backend exposes cohesive routers — setup, authentication, institutions, halls, devices, users, exam sessions, detection-event ingestion, alerts, video streaming, settings, and the hall voice channel — plus a static evidence mount. Security is layered: JWT access tokens (short-lived, in an HTTP-only cookie) with rotating refresh tokens; CSRF double-submit protection on cookie-authenticated unsafe requests; role-based access control on every route; rate limiting; and hardened HTTP headers (Content-Security-Policy, X-Frame-Options DENY, X-Content-Type-Options nosniff, HSTS). A production-settings validator refuses to start with a default secret key, an unset internal event token, or wildcard CORS."),
  tableCaption("Table 3.2  Principal backend API groups"),
  makeTable(["Router", "Responsibility"], [
    ["/api/auth", "Login, logout, token refresh, current-user, CSRF"],
    ["/api/setup", "First-run install wizard (institution + admin + halls)"],
    ["/api/institutions, /api/halls, /api/devices", "Infrastructure CRUD and device health / hall readiness"],
    ["/api/users", "Role-based user management"],
    ["/api/sessions", "Exam sessions, assignments, monitoring start/stop, reports"],
    ["/api/events", "Detection-event ingestion from the engine (token-guarded)"],
    ["/api/alerts", "Alert confirm / cancel by the assigned admin"],
    ["/api/stream", "MJPEG live feeds and monitoring/alert/status polling"],
    ["/api/v1/voice", "Stateless per-hall voice-channel WebSocket"],
  ], [3200, 5826]),
  H2("3.7  The Hall Voice Channel"),
  P("Coordination between the control room and the hall is handled by a deliberately minimal, stateless voice subsystem: one WebSocket channel per hall, relaying raw audio frames and presence between participants entirely in memory. Nothing about voice is written to the database and no calls are recorded. When an admin confirms an incident, the backend pushes an incident card into the relevant hall’s channel so the invigilator’s device shows exactly which seat to approach."),
  H2("3.8  The Dashboard"),
  P("The React dashboard presents two experiences. The admin / control-room console offers a live hall grid, the alert stack with one-click confirm/cancel and evidence playback, per-camera statistics, and hold-to-talk voice per hall. The invigilator view is focused for in-hall use: the assigned schedule, a hall readiness check, start/stop monitoring, the live feed, an alert timeline, and a floating hold-to-talk button. The entire interface is right-to-left and Arabic, matching its users."),
  ...figurePlaceholder("Figure 3.5  Control-room dashboard (hall grid and alert queue)",
    "Insert a screenshot of the admin/control-room dashboard."),
  ...figurePlaceholder("Figure 3.6  Invigilator hall-monitoring view",
    "Insert a screenshot of the invigilator monitoring page."),
];

// =====================================================================
//  CHAPTER 4 — IMPLEMENTATION & RESULTS
// =====================================================================
const params = [
  ["detection_interval", "1.0 s", "Seconds between full YOLO detection runs"],
  ["detection_confidence", "0.15", "Person-detection confidence threshold"],
  ["detection_imgsz", "640", "YOLO inference resolution"],
  ["tools_confidence", "0.45", "Paper / object detection threshold"],
  ["phone_confidence", "0.30", "Phone (COCO cell-phone) threshold"],
  ["tracking_max_age", "30", "Frames a lost track survives"],
  ["neighbor_k", "6", "Nearest neighbours computed per student"],
  ["risk_angle_tolerance", "25.0°", "Max gaze-to-paper angle counted as “looking”"],
  ["suspicious_duration_threshold", "2.0 s", "Sustained gaze before flagging"],
  ["reid_match_threshold", "0.80", "OSNet cosine similarity for re-identification"],
  ["face_mesh_workers", "4", "Parallel MediaPipe worker threads"],
];

const audioParams = [
  ["audio_chunk_ms", "500", "Analysis window length"],
  ["audio_sample_rate", "16000", "Required by Silero VAD and Whisper"],
  ["audio_calibration_chunks", "30", "Non-silent chunks used to learn the baseline"],
  ["audio_local_ratio_multiplier", "2.0×", "2-mic imbalance over baseline to call LOCAL"],
  ["audio_global_fraction", "0.6", "N-mic fraction that hears a sound to call GLOBAL"],
  ["audio_vad_threshold", "0.5", "Silero speech-confidence threshold (adaptive)"],
  ["audio_strict_mode", "true", "Any confirmed speech = violation (silent exam)"],
  ["audio_episode_min_sec", "3.0 s", "Sustained duration to confirm an episode"],
  ["audio_clip_sec_before/after", "2.0 s", "Pre / post buffer in the evidence clip"],
];

const ch4 = [
  ...chapterTitle(4, "Implementation and Results"),
  H2("4.1  Implementation Approach"),
  P("The system was implemented in Python (detection engine and backend) and TypeScript/React (frontend), developed with an Agile, sprint-based workflow. Every behaviour described in Chapter 3 corresponds to concrete modules in the codebase; this chapter reports the real implementation choices and the configuration values that govern them, all drawn directly from the source. The configuration is centralized in a single typed settings layer (Pydantic), so every threshold below is overridable per deployment without touching code."),
  H2("4.2  The Detection Engine — Concurrency Model"),
  P("Real-time performance comes from separating slow work from the display loop. A dedicated camera thread captures frames continuously; a detection worker thread runs the YOLO models on the latest frame about once per second; a pool of face-mesh worker threads runs MediaPipe in parallel (MediaPipe releases the interpreter lock during inference, giving true parallelism); and background writer threads encode evidence clips. Between detection cycles, BoT-SORT keeps every student’s bounding box locked at full frame rate, and a stability filter keeps a selected student on screen through brief detection misses. Frames are JPEG-encoded inside a rolling buffer to cut memory use dramatically."),
  H3("4.2.1  Video Configuration Parameters"),
  P("Table 4.1 lists the governing parameters of the video pipeline, with their default values as defined in the settings layer."),
  tableCaption("Table 4.1  Key video-pipeline parameters (defaults)"),
  makeTable(["Parameter", "Default", "Meaning"], params, [3200, 1300, 4526]),
  H3("4.2.2  Audio Configuration Parameters"),
  tableCaption("Table 4.2  Key audio-pipeline parameters (defaults)"),
  makeTable(["Parameter", "Default", "Meaning"], audioParams, [3200, 1500, 4326]),
  H2("4.3  Evidence Generation and Forensics"),
  P("When a student is flagged, the pipeline assembles an evidence clip from a continuously maintained ring buffer: roughly two seconds of footage before the event, the event itself, and a two-second post-event buffer. During the event the frames are annotated — a red box on the flagged student and a yellow box on the targeted neighbour’s paper for a gaze event, or a red box on the phone for a phone event — while the surrounding context frames are kept raw. Clips are written asynchronously by a bounded pool of writer threads (capped at three concurrent recordings to protect memory) and saved as gaze_alert_*.mp4 or phone_alert_*.mp4. The audio pipeline produces an analogous WAV clip with a JSON sidecar carrying the transcript, matched keywords, energy ratios, timestamps, and a SHA-256 hash for chain-of-custody integrity. The full camera feed can also be archived continuously for post-exam review."),
  ...figurePlaceholder("Figure 4.1  Annotated gaze evidence clip (red = student, yellow = targeted paper)",
    "Insert a representative frame from a generated gaze_alert_*.mp4 clip."),
  H2("4.4  Backend and Persistence"),
  P("The backend persists every detection event, group event, and alert against its exam session, giving each alert a full evidentiary chain back to the device and timestamp. The system is database-agnostic: development uses a zero-setup SQLite file, while production targets PostgreSQL — selected purely through a connection-string environment variable — because live multi-hall monitoring is a concurrent-writer workload that PostgreSQL’s multi-version concurrency control handles and SQLite cannot. Schema evolution is managed with Alembic migrations, verified end-to-end against both engines."),
  H2("4.5  Deployment Topology"),
  P("In development the system runs as three cooperating processes on fixed ports, with the frontend proxying API and WebSocket traffic to the backend. Table 4.3 lists them. For phone-based microphone testing the app is exposed over HTTPS (a secure context is required for browser microphone capture)."),
  tableCaption("Table 4.3  Runtime processes (development)"),
  makeTable(["Process", "Port", "Role"], [
    ["Camera simulator", "8000", "Serves MJPEG feeds for seeded devices"],
    ["Backend API (uvicorn)", "8001", "FastAPI application"],
    ["Frontend (Vite)", "5173", "Dashboard; proxies /api to the backend"],
  ], [3000, 1200, 4826]),
  H2("4.6  Results and Observations"),
  P("The integrated system was validated end-to-end against pre-recorded exam footage and a Dockerized multi-camera MJPEG simulator over a local network. The following qualitative and quantitative outcomes were observed:"),
  bullet("Real-time operation: the asynchronous design sustained a smooth live view while running heavy detection only once per second; the lightweight tracker preserved per-student spatial continuity (and therefore gaze accuracy) between detection cycles."),
  bullet("Correct attribution: gaze events consistently named both the suspected student and the specific neighbour whose paper was targeted, rather than a generic “suspicious” flag."),
  bullet("Evidence reliability: because the pre-event ring buffer is larger than the total end-to-end alert latency, every evidence clip captured the moment the behaviour began, not merely the moment the alert fired."),
  bullet("Audio robustness: baseline calibration plus the hangover window markedly reduced false “local” classifications caused by the natural energy imbalance between microphone positions, which a naive fixed-ratio rule produces in abundance."),
  bullet("Privacy in practice: only short, event-triggered clips were generated, gaze used geometric landmarks rather than identity, and audio evidence carried features and transcripts rather than raw speaker identification."),
  tableCaption("Table 4.4  End-to-end latency budget observed in local simulation testing"),
  makeTable(["Stage", "Approx. value", "Note"], [
    ["Network transmission (Wi-Fi MJPEG)", "~25 ms", "Absorbed by the background capture thread"],
    ["Frame decode", "~15 ms", "Concurrent with inference"],
    ["AI inference (YOLO + tools)", "~65 ms", "Non-blocking; runs off the display loop"],
    ["Tracking / spatial logic", "~3 ms", "Per frame"],
    ["Behaviour confirmation", "2000 ms", "Sustained-gaze threshold (by design)"],
    ["Pre-event evidence buffer", "~2–3 s", "Larger than the alert latency — captures the origin"],
  ], [3600, 1600, 3826]),
  P("These figures are engineering measurements from local simulation, not a controlled accuracy study on a labelled benchmark; a formal precision/recall evaluation on annotated exam recordings is identified as future work in Chapter 5. What the implementation does establish is that the full real-time path — capture, detection, tracking, gaze reasoning, alerting, evidence, and human review — functions end-to-end on commodity hardware."),
];

// =====================================================================
//  CHAPTER 5 — CONCLUSION & FUTURE WORK
// =====================================================================
const ch5 = [
  ...chapterTitle(5, "Conclusion, Recommendations and Future Work"),
  H2("5.1  Conclusion"),
  P("This project set out to make in-person examination supervision more effective without removing the human from the decision. The delivered system, Thaqib, achieves that goal: it analyses live video and audio in real time, detects gaze-based copying, phone usage, and localized whispering, attributes each visual incident to a specific pair of students, produces tamper-evident evidence, and routes every alert to a human operator who confirms or dismisses it and directs an invigilator to the seat. It is built end-to-end — detection engine, backend platform, and Arabic control-room and invigilator interfaces — and runs on a single institution’s on-premises hardware."),
  P("Equally important is what the system deliberately does not do. It never issues an automatic verdict, it does not continuously judge students, and it produces only short, event-triggered evidence during scheduled sessions. This restraint is what makes an AI proctoring system defensible to deploy."),
  H2("5.2  Recommendations"),
  numItem("Pilot before scale: deploy first in a small number of halls to tune the gaze tolerance, sustained-duration, and audio thresholds against the institution’s real seating and acoustics before wider rollout."),
  numItem("Use PostgreSQL in production from day one, and enforce the production security settings (strong secret key, internal event token, non-wildcard CORS, secure cookies)."),
  numItem("Treat alerts as leads, not verdicts: train operators and invigilators on the human-in-the-loop model so the system augments judgement rather than replacing it."),
  numItem("Prefer wired Ethernet for cameras in high-stakes halls for the cleanest signal, while keeping the Wi-Fi path as a validated fallback."),
  H2("5.3  Future Work"),
  H3("5.3.1  Passive RF Device Detection"),
  P("A designed-but-unbuilt subsystem would detect any wireless device (phone, Bluetooth earbud, smartwatch) that activates during an exam, without jamming — jamming is rejected because the cameras and invigilator tablet themselves run on Wi-Fi. Inexpensive ESP32 nodes would passively scan for Bluetooth/Wi-Fi advertisements, a pre-exam baseline would whitelist legitimate devices, and any unknown or newly-activated device would raise an alert routed through the existing event-and-alert pipeline, pointing the invigilator to an estimated seating zone."),
  H3("5.3.2  Formal Accuracy Evaluation"),
  P("Future work should build a labelled benchmark of staged exam recordings and report precision, recall, and false-alarm rates per detection class, enabling principled threshold tuning and comparison against alternatives."),
  H3("5.3.3  Verified Student Identity Linking"),
  P("Linking an incident to a verified student record (via seat maps or enrolment data) would streamline post-exam reporting; it is intentionally deferred so that the core system stores geometric features rather than identities."),
  H3("5.3.4  Additional Detection Classes and Model Tuning"),
  bullet("Detection of wired earbuds and concealed notes through targeted, fine-tuned object models."),
  bullet("Fine-tuning the person, paper, and phone detectors on hall-specific footage to raise precision in the local environment."),
  bullet("Coordinated multi-student (group) cheating detection, building on the existing group-event data model."),
  H3("5.3.5  Scale and Operations"),
  bullet("Multi-institution / multi-campus deployment with tenant isolation, building on the existing institution hierarchy."),
  bullet("Operational dashboards for system health, model drift, and per-hall alert statistics over time."),
  P("In summary, Thaqib delivers a complete, working, privacy-respecting foundation for AI-assisted invigilation, and a clear roadmap for hardening and extending it toward institution-wide production use."),
];

// =====================================================================
//  REFERENCES (Vancouver)
// =====================================================================
const refs = [
  "Jocher G, Qiu J, Chaurasia A. Ultralytics YOLO [software]. Ultralytics; 2023. Available from: https://github.com/ultralytics/ultralytics",
  "Redmon J, Divvala S, Girshick R, Farhadi A. You Only Look Once: Unified, Real-Time Object Detection. In: Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition (CVPR); 2016. p. 779–788.",
  "Aharon N, Orfaig R, Bobrovsky BZ. BoT-SORT: Robust Associations Multi-Pedestrian Tracking. arXiv:2206.14651; 2022.",
  "Lugaresi C, Tang J, Nash H, et al. MediaPipe: A Framework for Building Perception Pipelines. arXiv:1906.08172; 2019.",
  "Kartynnik Y, Ablavatski A, Grishchenko I, Grundmann M. Real-time Facial Surface Geometry from Monocular Video on Mobile GPUs. arXiv:1907.06724; 2019.",
  "Zhou K, Yang Y, Cavallaro A, Xiang T. Omni-Scale Feature Learning for Person Re-Identification (OSNet). In: Proceedings of the IEEE/CVF International Conference on Computer Vision (ICCV); 2019. p. 3702–3712.",
  "Silero Team. Silero VAD: pre-trained enterprise-grade Voice Activity Detector [software]; 2021. Available from: https://github.com/snakers4/silero-vad",
  "Radford A, Kim JW, Xu T, Brockman G, McLeavey C, Sutskever I. Robust Speech Recognition via Large-Scale Weak Supervision (Whisper). arXiv:2212.04356; 2022.",
  "Ramírez S. FastAPI [software]; 2018. Available from: https://fastapi.tiangolo.com",
  "Bayer M. SQLAlchemy: The Database Toolkit for Python [software]; 2006. Available from: https://www.sqlalchemy.org",
  "Meta Open Source. React: A JavaScript library for building user interfaces [software]. Available from: https://react.dev",
  "Bradski G. The OpenCV Library. Dr. Dobb’s Journal of Software Tools; 2000.",
  "Harris CR, Millman KJ, van der Walt SJ, et al. Array programming with NumPy. Nature. 2020;585:357–362.",
  "Paszke A, Gross S, Massa F, et al. PyTorch: An Imperative Style, High-Performance Deep Learning Library. In: Advances in Neural Information Processing Systems (NeurIPS); 2019.",
  "Atoum Y, Chen L, Liu AX, Hsu SDH, Liu X. Automated Online Exam Proctoring. IEEE Transactions on Multimedia. 2017;19(7):1609–1624.",
];

const referencesSection = [
  ...chapterTitle("", "References"),
  ...refs.map((r, i) =>
    new Paragraph({
      spacing: { after: 100, line: 276 },
      indent: { left: 520, hanging: 360 },
      children: [T(`[${i + 1}]  `, { bold: true, size: 22 }), T(r, { size: 22 })],
    })
  ),
];

// =====================================================================
//  ARABIC ABSTRACT  +  ARABIC TITLE PAGE
// =====================================================================
const arabicAbstract = [
  new Paragraph({ heading: HeadingLevel.HEADING_1, alignment: AlignmentType.RIGHT, bidirectional: true,
    spacing: { before: 120, after: 160 },
    children: [new TextRun({ text: "ملخص المشروع", font: ARABIC_FONT, rightToLeft: true, bold: true })] }),
  AR("يعالج مشروع «ثاقب» مشكلة مراقبة الامتحانات داخل القاعات في الوقت الحقيقي، حيث يصعب على المراقب البشري متابعة جميع الطلاب في قاعة مزدحمة دون أن تفوته بعض حالات الغش. ويقدِّم النظام حلاً ذكياً يعتمد على الذكاء الاصطناعي لمساعدة المراقب وليس لاستبداله."),
  AR("يعمل النظام كأداة داعمة لاتخاذ القرار مع بقاء الإنسان في مركز القرار، على غرار تقنية حكم الفيديو (VAR) في كرة القدم؛ فهو لا يصدر حكماً نهائياً بل ينبّه إلى السلوكيات المشبوهة ليتخذ المراقب البشري الإجراء المناسب."),
  AR("يجمع النظام بين مسارين للتحليل: مسار الفيديو الذي يكتشف الطلاب ويتتبعهم ويقدّر اتجاه النظر لرصد النظر المستمر إلى ورقة الزميل المجاور وكذلك اكتشاف الهواتف المحمولة؛ ومسار الصوت الذي يميّز الهمس المحلّي عن ضجيج القاعة العام."),
  AR("وينتج عن كل واقعة دليل رقمي موثّق (مقطع فيديو معلّم أو مقطع صوتي مع بصمة تحقّق)، تُرسل إلى غرفة تحكّم عبر واجهة ويب عربية بالكامل، حيث يؤكّد المشرف التنبيه أو يرفضه ويوجّه المراقب إلى مقعد الطالب عبر قناة صوتية مباشرة."),
  AR([new TextRun({ text: "الكلمات المفتاحية: ", font: ARABIC_FONT, rightToLeft: true, bold: true, size: 26 }),
      new TextRun({ text: "الرؤية الحاسوبية، الكشف اللحظي، تتبع الأهداف، تقدير اتجاه النظر، مراقبة الامتحانات، دعم القرار.", font: ARABIC_FONT, rightToLeft: true, size: 26 })]),
];

function arabicTeamTable() {
  const b = { style: BorderStyle.SINGLE, size: 2, color: "BFBFBF" };
  const borders = { top: b, bottom: b, left: b, right: b };
  const widths = [1826, 4200, 2100, 900];
  const head = ["القسم", "الاسم", "الرقم الجامعي", "م"];
  // team rows reversed for RTL (dept, name, id, no)
  const arNames = ["شادي محمد فرج الله","محمد السيد قريش","أمير صلاح صبح","محمد السيد شعلان","عمرو طلعت أحمد","محمد ناصر رامز العفيفي","أحمد وليد الشيتي"];
  const headerRow = new TableRow({ tableHeader: true, children: head.map((h, i) =>
    new TableCell({ borders, width: { size: widths[i], type: WidthType.DXA },
      shading: { fill: BLUE, type: ShadingType.CLEAR }, margins: { top: 60, bottom: 60, left: 110, right: 110 },
      verticalAlign: VerticalAlign.CENTER,
      children: [new Paragraph({ bidirectional: true, alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: h, font: ARABIC_FONT, rightToLeft: true, bold: true, color: "FFFFFF", size: 22 })] })] })) });
  const rows = team.map((t, idx) => {
    const cells = [t[3], arNames[idx], t[1], t[0]];
    return new TableRow({ children: cells.map((c, i) =>
      new TableCell({ borders, width: { size: widths[i], type: WidthType.DXA },
        shading: { fill: idx % 2 ? "FFFFFF" : GREY, type: ShadingType.CLEAR },
        margins: { top: 50, bottom: 50, left: 110, right: 110 }, verticalAlign: VerticalAlign.CENTER,
        children: [new Paragraph({ bidirectional: true, alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: String(c), font: ARABIC_FONT, rightToLeft: true, size: 22 })] })] })) });
  });
  return new Table({ width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA }, columnWidths: widths, rows: [headerRow, ...rows] });
}

const arabicTitlePage = [
  new Paragraph({ children: [new PageBreak()] }),
  new Paragraph({ bidirectional: true, alignment: AlignmentType.CENTER, spacing: { after: 40 },
    children: [new TextRun({ text: "جامعة دمياط", font: ARABIC_FONT, rightToLeft: true, bold: true, size: 30 })] }),
  new Paragraph({ bidirectional: true, alignment: AlignmentType.CENTER, spacing: { after: 40 },
    children: [new TextRun({ text: "كلية الحاسبات والذكاء الاصطناعي", font: ARABIC_FONT, rightToLeft: true, bold: true, size: 26 })] }),
  new Paragraph({ bidirectional: true, alignment: AlignmentType.CENTER, spacing: { after: 320 },
    children: [new TextRun({ text: "قسم نظم المعلومات", font: ARABIC_FONT, rightToLeft: true, size: 26 })] }),
  ...spacer(1),
  new Paragraph({ bidirectional: true, alignment: AlignmentType.CENTER, spacing: { after: 20 },
    children: [new TextRun({ text: "ثاقب", font: ARABIC_FONT, rightToLeft: true, bold: true, size: 60, color: BLUE })] }),
  new Paragraph({ bidirectional: true, alignment: AlignmentType.CENTER, spacing: { after: 360 },
    children: [new TextRun({ text: "نظام ذكي لكشف الغش في الامتحانات في الوقت الحقيقي", font: ARABIC_FONT, rightToLeft: true, bold: true, size: 32 })] }),
  new Paragraph({ bidirectional: true, alignment: AlignmentType.CENTER, spacing: { after: 120 },
    children: [new TextRun({ text: "إعداد فريق المشروع", font: ARABIC_FONT, rightToLeft: true, bold: true, size: 26 })] }),
  arabicTeamTable(),
  ...spacer(1),
  new Paragraph({ bidirectional: true, alignment: AlignmentType.CENTER, spacing: { before: 200, after: 40 },
    children: [new TextRun({ text: "تحت إشراف", font: ARABIC_FONT, rightToLeft: true, size: 26 })] }),
  new Paragraph({ bidirectional: true, alignment: AlignmentType.CENTER, spacing: { after: 200 },
    children: [new TextRun({ text: "د. وائل عبد القادر عوض", font: ARABIC_FONT, rightToLeft: true, bold: true, size: 30 })] }),
  new Paragraph({ bidirectional: true, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "العام الجامعي 2025 / 2026", font: ARABIC_FONT, rightToLeft: true, bold: true, size: 26 })] }),
];

// =====================================================================
//  LISTS (TOC, Figures, Tables, Abbreviations)
// =====================================================================
const tocSection = [
  H1("Table of Contents"),
  new TableOfContents("Table of Contents", { hyperlink: true, headingStyleRange: "1-3" }),
];

function manualList(title, entries) {
  // entries: [label]
  const items = entries.map((e) =>
    new Paragraph({
      tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_W - 100 }],
      spacing: { after: 80, line: 276 },
      children: [T(e, { size: 23 })],
    })
  );
  return [H1(title), ...items];
}

const listOfFigures = manualList("List of Figures", [
  "Figure 2.1  Use-Case diagram of the Thaqib system",
  "Figure 2.2  Sequence diagram — detection-to-confirmation alert flow",
  "Figure 3.1  High-level four-layer architecture of Thaqib",
  "Figure 3.2  The real-time video detection pipeline",
  "Figure 3.3  Alert review lifecycle",
  "Figure 3.4  Core entity-relationship model",
  "Figure 3.5  Control-room dashboard",
  "Figure 3.6  Invigilator hall-monitoring view",
  "Figure 4.1  Annotated gaze evidence clip",
]);

const listOfTables = manualList("List of Tables", [
  "Table 2.1  Comparison of Thaqib with existing approaches",
  "Table 2.2  Functional requirements",
  "Table 2.3  Non-functional requirements",
  "Table 3.1  Implemented technology stack",
  "Table 3.2  Principal backend API groups",
  "Table 4.1  Key video-pipeline parameters",
  "Table 4.2  Key audio-pipeline parameters",
  "Table 4.3  Runtime processes (development)",
  "Table 4.4  End-to-end latency budget (simulation)",
]);

const abbrev = [
  ["AI", "Artificial Intelligence"],
  ["API", "Application Programming Interface"],
  ["BLE", "Bluetooth Low Energy"],
  ["BoT-SORT", "Robust Multi-Object Tracking algorithm"],
  ["CCTV", "Closed-Circuit Television"],
  ["CORS", "Cross-Origin Resource Sharing"],
  ["CSRF", "Cross-Site Request Forgery"],
  ["CV", "Computer Vision"],
  ["ERD", "Entity-Relationship Diagram"],
  ["FPS", "Frames Per Second"],
  ["JWT", "JSON Web Token"],
  ["MJPEG", "Motion JPEG (streaming format)"],
  ["MVCC", "Multi-Version Concurrency Control"],
  ["NMS", "Non-Maximum Suppression"],
  ["ORM", "Object-Relational Mapping"],
  ["OSNet", "Omni-Scale Network (re-identification model)"],
  ["RBAC", "Role-Based Access Control"],
  ["ReID", "Re-Identification"],
  ["REST", "Representational State Transfer"],
  ["RF", "Radio Frequency"],
  ["RMS", "Root Mean Square (energy)"],
  ["RTSP", "Real-Time Streaming Protocol"],
  ["STT", "Speech-to-Text"],
  ["UML", "Unified Modeling Language"],
  ["VAD", "Voice Activity Detection"],
  ["VAR", "Video Assistant Referee"],
  ["YOLO", "You Only Look Once (object detector)"],
];
const listOfAbbrev = [
  H1("List of Abbreviations"),
  makeTable(["Abbreviation", "Meaning"], abbrev, [2400, 6626]),
];

// =====================================================================
//  FOOTERS
// =====================================================================
function footer(format) {
  return new Footer({
    children: [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        border: { top: { style: BorderStyle.SINGLE, size: 4, color: BLUE, space: 6 } },
        children: [
          T("Thaqib — Smart Cheating Detection System    |    ", { size: 16, color: "888888" }),
          new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: "888888" }),
        ],
      }),
    ],
  });
}

// =====================================================================
//  DOCUMENT ASSEMBLY
// =====================================================================
const doc = new Document({
  creator: "Thaqib Project Team",
  title: "Thaqib — Smart Cheating Detection System",
  description: "Graduation Project Documentation",
  styles: {
    default: { document: { run: { font: FONT, size: 24 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: FONT, color: BLUE },
        paragraph: { spacing: { before: 240, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 27, bold: true, font: FONT, color: "2E5496" },
        paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: FONT, color: "1F3864" },
        paragraph: { spacing: { before: 160, after: 80 }, outlineLevel: 2 } },
    ],
  },
  numbering: {
    config: [
      { reference: "bullets", levels: [
        { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
        { level: 1, format: LevelFormat.BULLET, text: "◦", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 1260, hanging: 360 } } } },
      ] },
      { reference: "nums", levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
      ] },
    ],
  },
  sections: [
    // 1) COVER — no page number
    {
      properties: { page: { size: A4, margin: MARGIN } },
      children: cover,
    },
    // 2) FRONT MATTER — roman numerals
    {
      properties: {
        type: SectionType.NEXT_PAGE,
        page: { size: A4, margin: MARGIN,
          pageNumbers: { start: 1, formatType: NumberFormat.LOWER_ROMAN } },
      },
      footers: { default: footer() },
      children: [
        ...dedication, new Paragraph({ children: [new PageBreak()] }),
        ...acknowledgement, new Paragraph({ children: [new PageBreak()] }),
        ...abstract, new Paragraph({ children: [new PageBreak()] }),
        ...arabicAbstract, new Paragraph({ children: [new PageBreak()] }),
        ...tocSection, new Paragraph({ children: [new PageBreak()] }),
        ...listOfFigures, new Paragraph({ children: [new PageBreak()] }),
        ...listOfTables, new Paragraph({ children: [new PageBreak()] }),
        ...listOfAbbrev,
      ],
    },
    // 3) BODY — decimal numerals restart at 1
    {
      properties: {
        type: SectionType.NEXT_PAGE,
        page: { size: A4, margin: MARGIN,
          pageNumbers: { start: 1, formatType: NumberFormat.DECIMAL } },
      },
      footers: { default: footer() },
      children: [
        ...ch1, new Paragraph({ children: [new PageBreak()] }),
        ...ch2, new Paragraph({ children: [new PageBreak()] }),
        ...ch3, new Paragraph({ children: [new PageBreak()] }),
        ...ch4, new Paragraph({ children: [new PageBreak()] }),
        ...ch5, new Paragraph({ children: [new PageBreak()] }),
        ...referencesSection,
      ],
    },
    // 4) ARABIC TITLE PAGE — no number
    {
      properties: { type: SectionType.NEXT_PAGE, page: { size: A4, margin: MARGIN } },
      children: arabicTitlePage,
    },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("Thaqib_Graduation_Documentation.docx", buf);
  console.log("WROTE Thaqib_Graduation_Documentation.docx", buf.length, "bytes");
});
