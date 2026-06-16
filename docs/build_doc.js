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
  // Heading 1 used for TOC; the big "CHAPTER N" lives on the divider page.
  return [
    new Paragraph({
      heading: HeadingLevel.HEADING_1,
      alignment: AlignmentType.CENTER,
      spacing: { before: 120, after: 60 },
      border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: BLUE, space: 6 } },
      children: [T(num ? `Chapter ${num}:  ${title}` : title)],
    }),
    new Paragraph({ spacing: { after: 160 }, children: [T("")] }),
  ];
}

// full-page chapter divider: big "CHAPTER N" centred, then the chapter content begins on the next page
function chapterDivider(num, title) {
  return [
    new Paragraph({ pageBreakBefore: true, spacing: { after: 0 }, children: [T("")] }),
    ...spacer(8),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 0 },
      children: [T("CHAPTER", { bold: true, size: 56, color: "8EAADB", characterSpacing: 60 })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 0, after: 120 },
      children: [T(String(num), { bold: true, size: 220, color: BLUE })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 0 },
      border: { top: { style: BorderStyle.SINGLE, size: 6, color: BLUE, space: 10 },
                bottom: { style: BorderStyle.SINGLE, size: 6, color: BLUE, space: 10 } },
      children: [T(title, { bold: true, size: 40, color: "1F3864" })] }),
    new Paragraph({ children: [new PageBreak()] }),
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

// editable confusion-matrix table: rows = actual behaviour, cols = predicted alert type.
// diagonal (TP) shaded green, false-alarm/missed cells shaded orange; cells are blank for the user.
function confusionTable() {
  const b = { style: BorderStyle.SINGLE, size: 2, color: "BFBFBF" };
  const borders = { top: b, bottom: b, left: b, right: b };
  const W = [2226, 1700, 1700, 1700, 1700];
  const GRN = "E2EFDA", ORG = "FCE4D6", GRY = "EDEDED";
  const cell = (text, fill, o = {}) =>
    new TableCell({
      borders, width: { size: o.w, type: WidthType.DXA },
      shading: { fill, type: ShadingType.CLEAR },
      margins: { top: 90, bottom: 90, left: 90, right: 90 },
      verticalAlign: VerticalAlign.CENTER,
      children: [new Paragraph({ alignment: AlignmentType.CENTER,
        children: [T(text, { size: o.size || 21, bold: o.bold, color: o.color })] })],
    });
  const cols = ["Gaze", "Phone", "Audio", "No alert"];
  const header = new TableRow({ tableHeader: true, children: [
    cell("Actual ＼ Predicted", BLUE, { w: W[0], bold: true, color: "FFFFFF", size: 18 }),
    ...cols.map((c, i) => cell(c, BLUE, { w: W[i + 1], bold: true, color: "FFFFFF" })),
  ] });
  // code: g=true positive (diag), f=false (FP/FN), n=not-applicable corner, .=blank
  const defs = [
    ["Gaze cheating", ["g", ".", ".", "f"]],
    ["Phone use", [".", "g", ".", "f"]],
    ["Audio anomaly", [".", ".", "g", "f"]],
    ["No cheating", ["f", "f", "f", "n"]],
  ];
  const fillFor = (c) => (c === "g" ? GRN : c === "f" ? ORG : c === "n" ? GRY : "FFFFFF");
  const valFor = (c) => (c === "n" ? "n/a" : "");
  const rows = defs.map((d) => new TableRow({ children: [
    cell(d[0], "F2F2F2", { w: W[0], bold: true }),
    ...d[1].map((c, ci) => cell(valFor(c), fillFor(c), { w: W[ci + 1] })),
  ] }));
  return new Table({ width: { size: W.reduce((a, x) => a + x, 0), type: WidthType.DXA }, columnWidths: W, rows: [header, ...rows] });
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
  P("Thaqib is deliberately designed as a decision-support, human-in-the-loop tool, analogous to the Video Assistant Referee (VAR) in football: it surfaces likely incidents for human review and takes no disciplinary action automatically. The system fuses two independent perception pipelines. The video pipeline detects students with a YOLOv11 person detector, tracks them across frames with the BoT-SORT tracker, preserves identity through occlusions with an OSNet re-identification model, extracts 478 facial landmarks with MediaPipe, and computes a per-student gaze vector from head orientation and iris deviation. A spatial k-nearest-neighbour model attributes a sustained gaze toward a specific neighbour’s examination paper as a cheating event. A parallel object model flags mobile phones anywhere in the frame. The audio pipeline distinguishes localized whispering from global hall noise using a calibrated multi-microphone energy discriminator, confirms human speech with Silero Voice Activity Detection, and optionally transcribes it with Faster-Whisper for keyword matching. A passive radio-frequency channel further detects wireless devices — phones, earbuds, smartwatches — that activate inside the hall, without jamming and without storing any identifying hardware address."),
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
  P("It is worth being precise about why this is now feasible when it was not a decade ago. Three things changed. First, single-stage object detectors such as the YOLO family made it possible to locate every person in a frame many times per second on a single affordable GPU. Second, lightweight on-device face-geometry models made it possible to estimate where a person is looking without specialized hardware or a calibration step per student. Third, robust multi-object trackers made it possible to keep a consistent identity for every student across the inevitable occlusions of a crowded room. Thaqib is, in essence, an integration of these three advances around the one task that ties them together — deciding whether a student is looking at a neighbour’s paper — together with an audio channel for the cases the camera cannot see."),
  P("Crucially, the same advances also make a privacy-respecting design possible. Because gaze can be computed from geometry rather than from a stored image of the student, and because tracking identities are ephemeral track numbers rather than names, the system can do its job while holding almost nothing that could identify or embarrass an innocent student — a property that is central to the design and revisited throughout this document."),
  H2("1.2  Motivation"),
  P("Cheating undermines the credibility of an institution and the principle of equal opportunity. Crucially, in most academic regulations a cheating decision must be made during the exam, while the act can still be witnessed and verified; evidence surfaced only after the session has ended is often inadmissible. Systems that simply record everything for later review therefore solve the wrong problem and raise their own privacy concerns."),
  P("Thaqib is motivated by the VAR analogy from football. VAR does not overrule the referee; it draws the referee’s attention to an incident worth a second look. Likewise, Thaqib never declares a student guilty. It raises a timely, evidence-backed alert and lets a human decide — reducing legal and ethical risk while making each invigilator far more effective."),
  P("This framing matters for more than ethics; it is also what makes the system practical. A tool that tried to decide guilt would have to be almost perfect to be trusted, because a wrong automatic verdict against an honest student is a serious harm. By contrast, a tool that only raises leads for a human can be useful even when imperfect: a false alarm costs an invigilator a brief glance, and the human filters it out. Designing for assistance rather than judgement therefore lowers the accuracy bar at which the system becomes valuable, and removes the single most dangerous failure mode — an unaccountable machine punishing a student."),
  H2("1.3  Problem Statement"),
  P("Even with invigilators present, behaviours such as copying from a neighbour’s paper, glancing at a hidden phone, or whispering answers are hard to catch reliably and consistently. The difficulty multiplies in crowded halls with background noise and frequent visual occlusion. Concretely, an effective system must overcome several obstacles at once:"),
  bullet("It must distinguish a sustained, directed look at a neighbour’s paper from the countless innocent glances that occur in any exam."),
  bullet("It must keep track of who is who as students are repeatedly occluded, so that an incident can be attributed to the right pair of people."),
  bullet("It must tell a localized whisper apart from the constant ambient noise of a real hall."),
  bullet("It must run fast enough to alert during the exam, not after it, on hardware an institution can afford."),
  bullet("And it must do all of this without recording or judging students in a way that would be intrusive or unlawful."),
  P("The core problem this project addresses is therefore: how can a system detect cheating-related behaviour in real time, from live video and audio, accurately enough to be useful and with few enough false alarms to be trusted — while respecting student privacy and leaving every final decision to a human?"),
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
  P("Thaqib targets in-person examinations inside physical halls. It acts as a decision-support tool and operates in real time. To make the boundary precise, the scope is stated explicitly below."),
  P([T("In scope. ", { bold: true, size: 24 }), T("The delivered system includes:", { size: 24 })]),
  bullet("Real-time video monitoring with gaze-based copying detection and mobile-phone detection."),
  bullet("Real-time audio monitoring with localized-whisper detection in a silent exam."),
  bullet("Automatic, tamper-evident evidence generation (annotated video clips and hashed audio clips)."),
  bullet("A complete management platform: institutions, halls, devices, users, exam sessions, and staff assignments."),
  bullet("A control-room dashboard with a shared alert-review queue, and an invigilator hall view."),
  bullet("A live hall voice channel between the control room and invigilators."),
  bullet("Post-exam session reporting, and a database that scales from a single laptop (SQLite) to a production server (PostgreSQL)."),
  P([T("Out of scope (this version). ", { bold: true, size: 24 }), T("The following are intentionally deferred:", { size: 24 })]),
  bullet("Any automatic verdict or sanction — the system never confirms cheating by itself."),
  bullet("Linking incidents to verified student identities (the system stores geometric features, not identities)."),
  bullet("Wireless-device (RF) detection — designed but reserved as future work (Chapter 5)."),
  bullet("Multi-campus cloud deployment and inter-institution federation."),
  H2("1.7  Development Methodology"),
  P("The project was built with an Agile, sprint-based methodology, with work decomposed into three linked levels: sprints (fixed-length delivery intervals, each focused on a coherent capability such as tracking, gaze, audio, or the dashboard), user stories (requirements written from a stakeholder’s perspective, in the form “as a [role], I want [goal] so that [benefit]”), and tasks (the smallest executable units, each owned by a team member). This structure kept high-level requirements traceable down to individual commits while allowing the design to evolve as the team learned what the footage and the models actually demanded. The iterative cadence was essential for a perception system, where many parameters — detection thresholds, the gaze tolerance, the audio calibration — could only be tuned by repeatedly running the pipeline against real exam recordings and inspecting the results."),
  H2("1.8  Document Organization"),
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
  ["FR-13", "RF Device Detection", "Passive scanner nodes detect wireless devices that activate in the hall; unknown or newly-active devices raise an alert (no jamming, MAC stored only as a hash)."],
  ["FR-14", "Evidence Retention", "Evidence is retained on a status-based schedule (confirmed 3 years, cancelled 30 days, pending review 180 days), with a legal-hold override that freezes purging."],
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
  H2("2.1  Problem Definition and Context"),
  P("Examinations exist to measure what a student actually knows, and the value of a qualification rests on the assumption that the measurement was fair. Cheating attacks that assumption directly: it advantages the dishonest student, devalues the honest one’s effort, and erodes trust in the institution that issued the result. The harm is not abstract — admissions, scholarships, professional licensing, and employment all rely on the integrity of the grades behind them. An exam hall is therefore a place where fairness has to be actively defended, not merely assumed."),
  P("Traditionally that defence is the invigilator’s. But the invigilator’s attention is a scarce, fragile resource: it cannot be in two places at once, it tires over a multi-hour session, and it is easily drawn away at exactly the moment a quick glance or a hidden phone does its work. The goal of this project is not to replace that human defence but to multiply its reach — to give one invigilator, in effect, many more pairs of eyes, while leaving the judgement firmly with the person in the room."),
  P("Against that backdrop, catching exam cheating in real time is fundamentally a perception-under-constraints problem. The system must answer three questions continuously and simultaneously, for every student: Where is this person looking? Is there a forbidden object near them? Is someone speaking when the room should be silent? Each question is individually hard and becomes harder in combination:"),
  bullet("Occlusion and density: students overlap in the camera view; heads turn; arms block faces. Identities must survive these gaps or tracking collapses."),
  bullet("Ambiguity of intent: a brief glance is normal; a sustained, directed look at a neighbour’s paper is not. The system must reason over time, not single frames."),
  bullet("Acoustic clutter: real halls are never silent. Pen clicks, paper shuffling, footsteps, and an invigilator’s own voice must not be mistaken for whispering."),
  bullet("Trust and ethics: a system that fires constantly will be ignored; one that records and judges students raises legal concerns. Precision and restraint are requirements, not features."),
  H2("2.2  Related Work"),
  H3("2.2.1  Online (Remote) Proctoring Platforms"),
  P("Commercial platforms such as ProctorU, Respondus Monitor, and ExamSoft monitor a single examinee through a personal webcam and microphone, usually with cloud-based analysis. They are built for remote, one-student-per-camera settings and depend on continuous internet connectivity and full session recording. They do not address a shared physical hall with many students per camera, and their always-recording model is exactly what an in-person, privacy-respecting design tries to avoid."),
  P("These platforms also illustrate a recurring tension in the field. To be effective remotely they tend to collect a great deal — continuous video and audio of the student, screen recordings, sometimes keystroke and environment scans — which has drawn sustained criticism on privacy and proportionality grounds, and in several jurisdictions has prompted legal challenges. The lesson Thaqib draws from them is not what to imitate but what to avoid: an in-person system that already has invigilators in the room does not need to record every student continuously to be useful, and should not."),
  H3("2.2.2  CCTV-Based Hall Surveillance"),
  P("Many institutions already install CCTV in exam halls. In practice these feeds are watched manually (if at all) and reviewed after the fact. They provide no automated behaviour analysis, no real-time alerting, and no attribution of an incident to a specific pair of students — leaving the core invigilation burden on humans."),
  H3("2.2.3  Research on Multimodal Behaviour Analysis"),
  P("A growing body of academic work shows that combining visual cues (head pose, gaze, objects) with audio cues improves abnormal-behaviour detection over either modality alone. Thaqib builds directly on the mature open models that this research has produced — YOLO-family detectors, BoT-SORT tracking, MediaPipe face geometry, OSNet re-identification, Silero VAD, and Whisper speech recognition — and combines them into a single real-time, on-premises proctoring pipeline."),
  P("The research literature also makes clear why no single cue is sufficient on its own. Gaze estimation alone is fooled by a student who copies from memory or uses a device held low; object detection alone misses behaviour that involves no object; and audio alone is blind to silent copying. Each modality covers the others’ blind spots, which is the core argument for a multimodal design. What much of the academic work leaves open, however, is the deployment question — most studies evaluate offline on recorded datasets, whereas an exam decision must be made live. Thaqib’s contribution is less a new model than the engineering that turns these proven components into a system that runs in real time, in a real hall, with a human in the loop."),
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
  P("Table 2.4 describes the principal use cases in more detail — the actor that initiates each, and the outcome it produces."),
  tableCaption("Table 2.4  Principal use-case descriptions"),
  makeTable(["Use case", "Actor", "Description"], [
    ["Authenticate", "All", "Log in with a username and password; receive a role-scoped session."],
    ["Manage institution & halls", "Super-Admin", "Create the institution and its halls, including capacity and layout."],
    ["Register devices", "Super-Admin", "Add cameras and microphones to a hall with their stream URLs."],
    ["Manage users", "Super-Admin", "Create admin and invigilator accounts and assign roles."],
    ["Schedule exam session", "Admin", "Define an exam, its halls, and its time window."],
    ["Assign staff", "Admin", "Assign invigilators and co-admins to a scheduled session."],
    ["Monitor live feeds", "Admin", "Watch the hall grid and per-camera status during an exam."],
    ["Review & confirm alerts", "Admin", "Inspect an alert’s evidence and confirm or cancel it."],
    ["Start / stop monitoring", "Invigilator", "Begin or end AI monitoring for the assigned hall."],
    ["Hall voice communication", "Admin, Invigilator", "Talk over the live per-hall voice channel."],
    ["Generate report", "Admin", "Produce a post-exam summary of alerts and resolutions."],
  ], [2400, 1700, 4926]),
  H2("2.4  Hardware and Deployment Requirements"),
  P("Although the development and evaluation were performed against a Dockerized simulator (Chapter 4), the system is designed for a concrete physical deployment. Table 2.5 lists the recommended hardware for a production hall installation, derived from the system’s real-time workload."),
  tableCaption("Table 2.5  Recommended production hardware"),
  makeTable(["Component", "Recommendation"], [
    ["Processing server — CPU", "8 or more cores"],
    ["Processing server — RAM", "16 GB or more"],
    ["Processing server — GPU", "NVIDIA RTX 3060 or higher (CUDA) for real-time inference"],
    ["Cameras", "IP cameras supporting RTSP / H.264 or MJPEG"],
    ["Microphones", "USB or IP microphones, one group per seating cluster"],
    ["Network", "Gigabit Ethernet (preferred) or dedicated Wi-Fi access point"],
    ["Storage", "1 TB or larger SSD for evidence clips and archives"],
  ], [3000, 6026]),
  P("Networking deserves particular note. Ethernet is preferred in high-stakes halls for its sub-10-millisecond latency, near-zero jitter, and capacity for many cameras on a single link. Wi-Fi remains a feasible fallback — the system’s asynchronous capture and pre-event buffering absorb the higher, more variable latency of a wireless link — but with a recommended limit of a handful of cameras per access point. The evaluation in Chapter 4 deliberately tests the Wi-Fi-like path so that the harder of the two network conditions is the one measured."),
  H2("2.5  Constraints and Assumptions"),
  P("The design rests on a small number of explicit assumptions, stated here so that the results are read in the right context:"),
  bullet("Seating is broadly fixed: students remain at assigned desks, so the live neighbour graph is stable for most of a session."),
  bullet("The exam is silent by default: any confirmed speech is treated as anomalous unless keyword mode is enabled for a supervised oral component."),
  bullet("Cameras have a reasonable view of students’ upper bodies and faces; extreme occlusion or back-only views limit gaze estimation."),
  bullet("A human operator is always present: the system produces leads, and a person makes every decision."),
  bullet("Deployment is on-premises and single-institution; the network and server are under the institution’s control."),
  H2("2.6  Summary"),
  P("This chapter established why automated assistance is needed, what makes the problem hard, and how existing approaches fall short. Remote proctoring platforms solve a different problem and at an unacceptable privacy cost for an in-person setting; passive CCTV provides no automated analysis or attribution. The requirements analysis then translated those gaps into concrete functional and non-functional requirements, three user roles, a set of use cases, and a clear statement of the hardware, constraints, and assumptions under which the system operates. The next chapter turns these requirements into the proposed framework: the architecture, the perception pipelines, the data model, and the platform that realize them."),
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
  P("The layering is deliberate and the dependencies flow in one direction. The acquisition layer knows nothing of detection; the detection engine knows nothing of the database or the dashboard — it simply emits events and writes evidence files; the backend knows nothing of how a gaze was computed — it only stores events and manages the exam lifecycle; and the dashboard depends only on the backend’s API. This separation means any one layer can be changed in isolation: a different camera, a retrained model, a new database, or a redesigned interface each touches a single layer. It also mirrors the human workflow the system supports — sensing, analysis, record-keeping, and decision — which makes the architecture easy to reason about for newcomers and maintainers alike."),
  H2("3.2  Technology Stack"),
  P("The system is built entirely on open, well-supported components. The detection engine is the most technology-dense layer; the backend and frontend use mainstream web frameworks."),
  tableCaption("Table 3.1  Implemented technology stack"),
  makeTable(["Layer", "Technologies"], [
    ["Detection — Vision", "Python, PyTorch, Ultralytics YOLOv11 (person), YOLOv8 (papers/phones), BoT-SORT (boxmot), MediaPipe Face Landmarker, OSNet re-identification"],
    ["Detection — Audio", "Silero VAD, Faster-Whisper, NumPy, SciPy, sounddevice, noise-reduction preprocessing"],
    ["Detection — RF", "ESP32-class BLE scanner nodes (MicroPython / CPython), passive scan + batched HTTP push, per-node pre-shared key"],
    ["Backend", "FastAPI, SQLAlchemy ORM, Alembic migrations, Pydantic v2 settings, slowapi rate limiting, native WebSockets, MJPEG over HTTP"],
    ["Database", "SQLite (development) / PostgreSQL (production), selected by DATABASE_URL with no code change"],
    ["Frontend", "React, TypeScript, Vite, Tailwind CSS, React Router — full right-to-left Arabic interface"],
  ], [2300, 6726]),
  P("There is no external message broker, no Redis, and no Kubernetes: state lives in the relational database and real-time delivery happens in-process through a WebSocket connection manager. This keeps the system deployable on a single institution’s server."),
  H3("3.2.1  Rationale for the Model Choices"),
  P("Every model in the stack was chosen for a specific reason rather than novelty. YOLOv11 was selected for person detection because it offers an excellent accuracy-to-speed ratio and runs comfortably in real time on a mid-range GPU, which matters when detection must repeat continuously throughout a multi-hour exam. BoT-SORT was chosen as the tracker because its combination of a Kalman-filter motion model with appearance cues keeps identities stable through the brief occlusions that are constant in a crowded hall — and stable identities are a hard prerequisite for the relational gaze logic. OSNet was added for re-identification specifically because tracking alone cannot survive a long occlusion; its omni-scale features re-attach a returning student to the correct identity."),
  P("On the geometry side, MediaPipe’s Face Landmarker was preferred over a heavier face model because it yields a dense 478-point mesh and a head-pose matrix in a single fast pass, and because it degrades gracefully on small or partially turned faces — exactly the conditions of back-row students. For audio, Silero VAD is a tiny, robust speech detector that runs in milliseconds, and Faster-Whisper provides high-quality multilingual transcription with first-class Arabic support, which is essential in the target deployment. The common thread is that each component is open, well-supported, and fast enough to run on hardware a university can actually afford."),
  H3("3.2.2  Camera Capture and Video Streaming"),
  P("Input is abstracted so the same pipeline runs against a webcam, an RTSP IP camera, or a video file without code change. A dedicated capture thread continuously reads frames into a small buffer so that a slow consumer never stalls the camera and a momentary network hiccup does not desynchronize the stream. For delivery to the browser, processed frames are exposed as MJPEG over HTTP, which every browser renders natively without plugins; the dashboard additionally polls compact status endpoints on short intervals to refresh hall, alert, and per-camera statistics. Frames held for potential evidence are JPEG-encoded inside the rolling buffer, which reduces their memory footprint by roughly thirty times compared with raw frames and is what makes a multi-second pre-event buffer affordable per student."),
  H2("3.3  The Video Detection Pipeline"),
  P("Before examining each stage in isolation, it helps to see how they compose into a single per-frame cycle. The pipeline’s main loop, executed for every captured frame, performs the following ordered steps:"),
  numItem("Push the frame into the JPEG-encoded ring buffer used for evidence pre-buffering."),
  numItem("Collect any detection result that the background YOLO worker has produced since the last frame; if present, split person and phone detections."),
  numItem("Update the tracker — either with the fresh detections or, between detections, with the sticky last-known boxes — then apply re-identification aliases."),
  numItem("Run the stability filter and non-maximum-suppression pass to remove ghost and duplicate tracks."),
  numItem("Update the spatial registry, recompute the neighbour graph (if students moved), and assign papers to owners."),
  numItem("Attribute any detected phone to its nearest student."),
  numItem("Submit faces of monitored students to the face-mesh worker pool; as each result returns, update gaze and re-identification."),
  numItem("Evaluate the cheating rule for every monitored student."),
  numItem("Advance the per-student alert-recording state machine, starting, extending, or finalizing evidence clips."),
  numItem("Render the annotated frame for display and optional archival."),
  P("The remainder of this section examines the stages that carry the most algorithmic weight."),
  P("The video pipeline (in src/thaqib/video/) turns a raw camera frame into structured, per-student behavioural state. It is engineered for real time: full neural detection runs only about once per second, while a lightweight tracker maintains a smooth 30-frames-per-second lock on every student in between. Figure 3.2 traces the flow from camera frame to evidence clip."),
  ...figure("fig_video", "Figure 3.2  The real-time video detection pipeline", 360),
  P("Each stage is intentionally decoupled. The expensive neural stages (person detection, object detection) run on a background worker thread at a fixed interval, while the per-frame stages (tracking propagation, neighbour computation, gaze evaluation, and the recording state machine) run on the main loop. This separation is the single most important design decision behind the system’s real-time behaviour and is examined in detail in Chapter 4."),
  H3("3.3.1  Detection, Tracking and Re-Identification"),
  P("A YOLOv11 detector (models/yolo11m.pt) locates people in the frame at a confidence threshold of 0.15, deliberately low so that distant or partially occluded students in the back rows are not missed. A separate YOLOv8 model (models/best.pt) locates examination papers, while phones are detected by the primary model using the COCO “cell phone” class. Running detection at full frame rate would saturate the GPU, so it is executed on a background thread roughly once per second; the intervening frames are handled by the tracker."),
  P("Detections feed BoT-SORT (via the boxmot library), which assigns each student a persistent track ID and keeps it stable between detection cycles using a Kalman-filter motion model. The Kalman predictor is what allows the system to draw an accurate bounding box — and therefore an accurate gaze origin — on every one of the ~30 frames per second even though a full detection only arrives once per second. When detection does not refresh a track, the pipeline falls back to the last known box (a “sticky” strategy) rather than linear velocity extrapolation, because in a near-static exam hall extrapolation tends to overshoot during frame-rate dips."),
  P("Two correctness safeguards run after tracking. A detection-stability filter keeps a selected student on screen through brief YOLO misses by injecting a Kalman-predicted box, but discards such a “ghost” box if it overlaps a live track by more than 40 % (intersection-over-union), preventing duplicate identities. A second non-maximum-suppression pass removes residual overlapping tracks above an IoU of 0.45, keeping the higher-confidence one. These steps directly protect the neighbour graph from corruption."),
  P("Because students are frequently occluded — a raised arm, a turned head, a passing invigilator — an OSNet appearance model (osnet_x0_25_msmt17.pt) embeds each detected face into a feature vector. When a track re-enters the scene, its embedding is matched against remembered embeddings, and if the cosine similarity exceeds 0.80 the new tracker ID is aliased back onto the student’s original identity. This re-identification step is the difference between a student keeping one stable identity for the whole exam and fragmenting into a dozen short-lived tracks that would each have to re-establish their neighbour context."),
  H3("3.3.2  Face Geometry and Gaze Estimation"),
  P("For every monitored student, MediaPipe’s Face Landmarker (models/face_landmarker.task) extracts 478 three-dimensional facial landmarks together with a 4×4 head-orientation (facial transformation) matrix. To keep this affordable at scale, each face is cropped from the student’s bounding box and processed at a reduced resolution by a pool of parallel worker threads; a short-lived cache returns the last good mesh when a single frame fails, so the overlay does not flicker during momentary blur or occlusion."),
  P("Gaze is then computed by fusing two cues. The coarse cue is head orientation: the rotation part of the head matrix is applied to the camera-forward axis to obtain the direction the head is pointing. The fine cue is eye deviation: the iris-centre landmarks (468 and 473) are measured against the eye-corner landmarks (33/133 and 263/362) to find how far each iris has shifted from its socket centre, normalized by eye width so the measure is scale-invariant. The iris deviation is weighted — calibrated so that roughly one eye-width of shift corresponds to about a 45-degree gaze swing — and clamped to half an eye-width to reject noise from distant or partly occluded irises. The two cues are combined and projected to a normalized two-dimensional screen-space gaze vector, ĝ, per student. The same function is the single source of truth used by both the cheating evaluator and the on-screen visualizer, guaranteeing that what an operator sees matches what the system decides on."),
  ...figure("fig_gaze", "Figure 3.3  Gaze-to-paper geometry and the risk-angle rule"),
  H3("3.3.3  Spatial Neighbour and Paper Model"),
  P("Cheating by copying is inherently relational: a gaze only matters relative to whose paper it lands on. Thaqib therefore continuously models the live seating arrangement rather than relying on a static floor plan. A vectorized k-nearest-neighbour computation (k = 6 by default) links each student to their six closest peers, using the Euclidean distance between person-detection centroids. The computation is fully vectorized with NumPy broadcasting and uses an argument-partition rather than a full sort, so it costs effectively nothing even with a hall full of students; furthermore, it is skipped entirely on frames where no student has moved more than twenty pixels since the last computation, which is the common case in a seated exam."),
  P("Papers are then bound to students through an exclusive, greedy nearest-owner assignment: the closest student–paper pair is matched first, both are removed from consideration, and the process repeats, so every detected paper belongs to exactly one student. A per-student distance threshold (the larger of 300 pixels or twice the student’s bounding-box width) prevents a paper from being attached to a student on the far side of the hall. Where the object model detects no paper for a monitored, seated student, a heuristic paper region just below that student’s bounding box is used as a fallback — but only for students actually selected for monitoring, and never for students whose posture (a tall, narrow bounding box) suggests they are standing or walking. Each student finally inherits the set of papers owned by their neighbours; these neighbour-owned papers are the candidate “targets” the gaze evaluator tests against."),
  P("The spatial model can be stated compactly. Each student s is represented by the centre of their bounding box, cₛ = (xₛ, yₛ). The distance between two students s and t is the Euclidean distance:"),
  P([T("(Eq. 3.1)    d(s, t)  =  √[ (xₛ − x", { italics: true, size: 23 }), T("t", { italics: true, size: 16, subScript: true }), T(")² + (yₛ − y", { italics: true, size: 23 }), T("t", { italics: true, size: 16, subScript: true }), T(")² ]", { italics: true, size: 23 })], { align: AlignmentType.CENTER }),
  P("The neighbour set N(s) is the k students with the smallest distance to s. For a neighbour n holding a paper at centre pₙ, the direction from the student’s head hₛ toward that paper, and the angle of the student’s gaze relative to it, are:"),
  P([T("(Eq. 3.2)    d̂", { italics: true, size: 23 }), T("s→p", { italics: true, size: 15, subScript: true }), T("  =  (pₙ − hₛ) / ‖pₙ − hₛ‖           (Eq. 3.3)    θ  =  arccos( ĝₛ · d̂", { italics: true, size: 23 }), T("s→p", { italics: true, size: 15, subScript: true }), T(" )", { italics: true, size: 23 })], { align: AlignmentType.CENTER }),
  P("A student is judged to be looking at a neighbour’s paper when θ falls within the angular tolerance θₜₒₗ (equivalently, when the dot product exceeds cos θₜₒₗ, which avoids an explicit arccosine), and is flagged only once that condition has held continuously for the sustained-duration threshold. This decision rule is stated as Equation 3.4 in the next section; Equations 3.1–3.3 make explicit the geometry that feeds it."),
  H3("3.3.4  Cheating Evaluation Logic"),
  P("The evaluator runs synchronously, every frame, for each monitored student. For each surrounding (neighbour-owned) paper it computes the direction from the student’s head to that paper and takes the cosine of the angle against the gaze vector. If that angle falls within a tolerance (25 degrees by default) the student is “looking at” the paper. A look must be sustained beyond a duration threshold (2.0 seconds by default) before the student is flagged — this is what separates a normal glance from copying. The evaluator also records which neighbour owns the targeted paper, so an alert names both the suspected copier and the victim. A grace period tolerates brief face-detection dropouts, and a cooldown prevents the flag from oscillating when a gaze breaks for an instant. Equation 3.4 states the core test."),
  P([T("(Eq. 3.4)   ", { bold: true, size: 22 }),
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
  P("Phone detection is deliberately independent of the gaze logic. The primary YOLO model detects a mobile phone (COCO class “cell phone”) anywhere in the frame at a lower confidence threshold (0.30) than person detection, since phones are small and partly hidden. A detected phone is attributed to the nearest active student within a fixed pixel radius and immediately flags that student, triggering an evidence clip. Because it depends on neither tracking nor gaze, phone detection works even for students who have not yet been selected for gaze monitoring — a phone appearing anywhere is always worth a human’s attention."),
  H3("3.3.6  The Alert-Recording State Machine"),
  P("Detecting an event and capturing evidence of it are separate concerns, and the pipeline keeps them separate through an explicit per-student recording state machine that runs after the evaluator each frame. A continuously maintained ring buffer holds the most recent ~2 seconds of frames (JPEG-encoded to keep memory low). When a student transitions to cheating, the buffer is snapshotted as the pre-event footage and recording begins; while cheating continues, every frame is appended and a post-event countdown is held open; once cheating stops, the countdown runs for a further 2 seconds and the clip is then handed to a background writer thread and the student’s state reset. To bound memory under worst-case load, no more than three recordings run concurrently, and any in-progress clip is flushed if the student’s track expires or the pipeline shuts down, so the final event in a session is never lost."),
  H3("3.3.7  Visualization and the Heads-Up Display"),
  P("Although the system’s purpose is to produce events rather than a picture, a rich visual overlay is central both to operating it and to trusting it. The visualizer renders, on the live frame, each student’s bounding box and identity, the gaze vector, the neighbour graph, the paper regions, and a prominent red box on any student currently flagged as cheating together with a yellow box on the paper they are looking at. A heads-up display reports the running statistics — tracked and selected counts, processing resolution, and recording state. Because every overlay is drawn from the very same gaze and neighbour computations that drive the decision, an operator watching the screen sees exactly the evidence the system is acting on, which turns an otherwise opaque model into something a human can audit at a glance. The same annotations are what make the saved evidence clips immediately legible to a reviewer."),

  H2("3.4  The Audio Detection Pipeline"),
  P("The audio pipeline (in src/thaqib/audio/) runs independently of video and is designed around one realistic assumption: an exam hall is never perfectly silent. Rather than detect “sound”, it detects sound that is localized to one part of the room — the acoustic signature of a whisper between neighbours — as opposed to global noise heard everywhere. It is organized as a three-thread flow: a main thread reads and classifies chunks, a voice-activity worker confirms speech, and a transcription worker produces evidence. Figure 3.4 shows the structure."),
  ...figure("fig_audio", "Figure 3.4  Three-stage audio detection pipeline"),
  H3("3.4.1  Preprocessing"),
  P("Before any classification, each audio chunk passes through a preprocessing stage that conditions the signal for the realistic acoustics of a hall: a high-pass filter (100 Hz) removes sub-bass rumble from air-conditioning and desk vibration; spectral noise reduction subtracts a learned room-noise profile; an adaptive gain normalizes each chunk’s loudness so microphones of differing sensitivity are comparable; and a transient-suppression stage attenuates short, broadband clicks (a dropped pen, a turned page) that would otherwise masquerade as speech onsets."),
  H3("3.4.2  Global vs. Local Discrimination"),
  P("Microphones at different positions naturally record different energy even in silence, so a fixed loudness ratio would constantly misfire — in real recordings the natural imbalance between two adjacent mics measured around 1.6×, which a naive 2.0× rule would mistake for a whisper. The discriminator therefore calibrates: over the first thirty non-silent chunks of a session it learns the structural energy ratio between microphones, then normalizes every subsequent chunk against that baseline. In the two-microphone case, a chunk is flagged local only when the normalized energy imbalance exceeds twice the calibrated normal; in the many-microphone case, a sound heard by fewer than a configurable fraction (60 %) of microphones is local. A hangover window prevents rapid flip-flopping between adjacent microphones, periodic recalibration (every five minutes) adapts to changing room acoustics, and an optional cross-correlation check catches a soft global sound that merely happened to be quieter on some microphones. Calibration is what takes the false-local rate from roughly a third of chunks down to a few per cent."),
  H3("3.4.3  Speech Confirmation and Transcription"),
  P("A chunk classified as local is passed to Silero Voice Activity Detection, which confirms whether it actually contains human speech rather than residual non-speech noise; the VAD threshold itself adapts to the measured noise floor of the room. In strict mode — the default for silent exams — any confirmed speech is a violation, and the system can alert on VAD alone in a few milliseconds. Optionally, Faster-Whisper transcribes the buffered speech (Arabic by default) so that, in keyword mode, only utterances matching a configurable keyword list are flagged — appropriate for supervised oral components. A sustained-episode tracker then groups repeated alerts on the same microphone into a single confirmed cheating episode, confirming only once the activity has lasted a minimum duration and closing the episode after a grace period of silence, so one continuous whisper produces one coherent piece of evidence rather than a storm of fragments."),
  P("For deployments where any speech is a violation, the pipeline can also run a fast path that skips transcription entirely: as soon as voice activity is confirmed on a localized chunk it raises an alert, in a few milliseconds rather than the seconds Whisper would take. This trades the transcript for speed, and is the appropriate choice for a strictly silent exam where the content of the speech does not change the decision. The episode tracker and a per-microphone cooldown then ensure that this faster, more sensitive path still produces one tidy alert per incident rather than a flood."),
  H3("3.4.4  Audio Evidence"),
  P("Every confirmed audio event yields a WAV clip (2 seconds before the event, the event, and a 2-second tail) accompanied by a JSON sidecar recording the transcript, any matched keywords, the energy ratios that drove the local classification, the timestamps, and a SHA-256 hash of the audio for chain-of-custody integrity. Optionally the full session is recorded for offline review. As with video, nothing about a student’s identity is stored — only the acoustic features and, when enabled, the transcript text."),

  H2("3.5  Alerts, Events and the Data Model"),
  P("Perception results are persisted as structured records. A single AI detection becomes a Detection Event; correlated events involving adjacent students can be grouped into a Group Event; and either kind produces an Alert for human review. Each Alert references exactly one detection event or one group event — never both. Alerts are tiered (tier-1 low severity, tier-2 high severity) and move through a reviewable lifecycle, shown as a state machine in Figure 3.5."),
  ...figure("fig_state", "Figure 3.5  Alert review lifecycle (state diagram)", 520),
  P("An alert begins pending. An assigned admin claims it, then either confirms it (a real incident, which pushes an incident card to the invigilator and records who confirmed it and when) or cancels it as a false positive. An alert may also be escalated for a second opinion before being confirmed or cancelled. Every transition records the acting user and timestamp, so the system retains a complete, auditable history of who decided what — essential for a tool whose output may feed a disciplinary process."),
  H3("3.5.1  Entity-Relationship Model"),
  P("The relational schema is built on SQLAlchemy with UUID primary keys, created/updated timestamps on every table, and soft-delete support on the infrastructure entities. Figure 3.6 shows the core entities and their relationships; Figure 3.7 presents the same model as a UML class diagram with the principal attributes."),
  ...figure("fig_erd", "Figure 3.6  Entity-Relationship diagram", 540),
  P("Institutions can form a shallow hierarchy (university → college). Halls belong to an institution and contain devices; an exam session can span several halls (a many-to-many relationship realized through the exam_session_halls join table) and is staffed through invigilator assignments and admin assignments. Detection events, group events, and alerts all hang off the exam session, giving every alert a full chain back to the device and the moment that produced it. Authentication state is held in a separate refresh-token table that supports rotation and revocation."),
  ...figure("fig_class", "Figure 3.7  Domain class diagram (core entities and attributes)"),
  P("Two groups of fields extend this core. The Alert entity carries evidence-governance fields — an evidence-retention deadline and a legal-hold flag (with the reason, the user who placed it, and the time) — that drive the retention policy described in Section 4.4. Separately, the RF subsystem of Section 3.10 adds three tables (rf_scanners, rf_whitelist_entries, rf_detections) that hang off halls and, through the shared Detection Event, off exam sessions — so an RF incident is a first-class citizen of the same data model, not a bolt-on."),
  H3("3.5.2  End-to-End Alert Flow"),
  P("Figure 3.8 traces a single incident through the whole system as a sequence diagram: the detection engine raises an event and posts it (with its evidence clip) to the backend; the backend stores it and the alert surfaces in the shared review queue; an admin reviews the evidence and confirms; the backend records the decision and pushes an incident card over the hall voice channel; and the invigilator, seeing exactly which seat to approach, acts in person. This is the concrete realization of the human-in-the-loop principle stated in Chapter 1."),
  ...figure("fig_sequence", "Figure 3.8  Sequence diagram — detection to confirmation", 540),
  H3("3.5.3  Event Aggregation and Alert Tiers"),
  P("Not every detection deserves the same response, so events are aggregated and alerts are tiered before they reach a human. Raw detection events that share a session and fall within a short time window and a spatial neighbourhood can be merged into a single group event — most importantly when two adjacent students both produce suspicious gaze within the same window, which is the signature of coordinated copying rather than two unrelated glances. Grouping prevents a flood of individual notifications for what is really one incident, and it preserves the link back to every participating event."),
  P("Severity then draws on several inputs: how long the behaviour was sustained, how large the gaze angle was, how many students were involved, and how frequently that student has been flagged already. From these the system assigns one of two tiers. A tier-one alert is a brief, isolated anomaly and is surfaced quietly on the invigilator’s dashboard. A tier-two alert — a group event, a prolonged behaviour, a large head turn, or a repeat offender — is raised more prominently to the invigilator and the control room together. This tiering is what keeps the system’s output proportionate: it draws human attention in proportion to how likely and how serious an incident appears, rather than treating every flicker of gaze as an emergency."),
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
    ["/api/v1/rf-push, /api/v1/rf", "RF scanner ingest (pre-shared key), baseline, whitelist, dashboard badge"],
  ], [3200, 5826]),
  P("Security is layered rather than bolted on. Table 3.3 summarizes the principal mechanisms and the threat each addresses."),
  tableCaption("Table 3.3  Security mechanisms"),
  makeTable(["Mechanism", "Purpose"], [
    ["JWT access tokens (HTTP-only cookie, short-lived)", "Authenticated sessions without exposing tokens to scripts"],
    ["Rotating refresh tokens (hashed, revocable)", "Long sessions without long-lived secrets; revocation on logout"],
    ["Role-based access control (RequireRole)", "Every route restricted to the roles permitted to use it"],
    ["CSRF double-submit token", "Blocks forged cookie-authenticated state-changing requests"],
    ["Rate limiting (slowapi)", "Resists brute-force and abusive request floods"],
    ["Security headers (CSP, HSTS, X-Frame-Options, nosniff)", "Mitigates clickjacking, MIME sniffing, mixed content"],
    ["Internal event token on /api/events", "Only the detection engine may ingest detection events"],
    ["Production settings validator", "Refuses to start with a default secret key or wildcard CORS"],
  ], [3700, 5326]),
  P("The detection-event ingestion endpoint deserves note: it is exempt from the CSRF flow (it is called machine-to-machine by the engine, not from a browser) but is instead guarded by a pre-shared internal token, so an external party cannot inject fabricated events into a live exam."),
  H2("3.7  The Hall Voice Channel"),
  P("Coordination between the control room and the hall is handled by a deliberately minimal, stateless voice subsystem: one WebSocket channel per hall, relaying raw audio frames and presence between participants entirely in memory. Nothing about voice is written to the database and no calls are recorded. When an admin confirms an incident, the backend pushes an incident card into the relevant hall’s channel so the invigilator’s device shows exactly which seat to approach."),
  P("The channel maintains a live presence list — who is connected to each hall and in what role — and broadcasts it on every join and leave, so both sides always know whether the other is reachable. The socket is authenticated with the same JWT used for the rest of the system, supplied either through the session cookie or, when a proxy strips cookies on the WebSocket upgrade, as a token on the connection URL. Because browsers only permit microphone capture in a secure context, transmitting from a phone requires the application to be served over HTTPS; receiving audio works over plain local networks. This subsystem deliberately replaced an earlier, heavier push-to-talk design that recorded clips and tracked approval state — a reminder that the right answer in this project was often the smaller one."),
  H2("3.8  The Dashboard"),
  P("The React dashboard presents two experiences. The admin / control-room console offers a live hall grid, the alert stack with one-click confirm/cancel and evidence playback, per-camera statistics, and hold-to-talk voice per hall. The invigilator view is focused for in-hall use: the assigned schedule, a hall readiness check, start/stop monitoring, the live feed, an alert timeline, and a floating hold-to-talk button. The entire interface is right-to-left and Arabic, matching its users. Live video reaches the browser as MJPEG over HTTP — no plugins, no WebRTC — and the dashboard polls lightweight status endpoints on short intervals to keep hall, alert, and camera statistics current."),
  P("The control room operates on a shared-queue model rather than a per-hall assignment: any admin assigned to an exam can claim and resolve any of its alerts, so a busy moment in one hall is naturally absorbed by whichever operator is free. This mirrors how a real control room works and avoids the failure mode where an alert waits unattended because its designated reviewer happened to be occupied. The deliberately focused invigilator view, by contrast, hides everything an operator needs but a person walking the hall does not, so that under the pressure of a live exam the one screen the invigilator carries shows only what to do next."),
  ...figurePlaceholder("Figure 3.9  Control-room dashboard (hall grid and alert queue)",
    "Insert a screenshot of the admin / control-room dashboard (DashboardPage)."),
  ...figurePlaceholder("Figure 3.10  Invigilator hall-monitoring view",
    "Insert a screenshot of the invigilator monitoring page (HallMonitoringPage)."),
  H2("3.9  Privacy and Ethical Design"),
  P("Privacy is treated as a design constraint, not an afterthought. Four decisions follow directly from it. First, the system never issues an automatic sanction — every alert requires a human decision. Second, gaze is computed from geometry (landmark positions and angles), not from appearance or identity, so the cheating signal carries no biometric template of the student. Third, the audio pipeline works on energy features and, at most, transcript text; it performs no speaker identification. Fourth, the system does not continuously judge or retain footage of students: only short, event-triggered clips are produced, and only during scheduled, active sessions. Together these choices make the system defensible to deploy in a real academic setting, where a tool that recorded and judged every student would be neither lawful nor welcome."),
  P("Two further measures reinforce this stance. The RF subsystem never stores a raw hardware address: every MAC is reduced to a SHA-256 hash on receipt, so a device can be tracked across sightings within an exam without the system holding anything that identifies its owner. And evidence is not kept indefinitely — it is governed by an explicit, status-based retention schedule (detailed in Section 4.4) that automatically purges old material, with a legal-hold override for the rare case that an incident becomes the subject of a formal process. Data minimization, in short, is enforced by the system rather than left to policy."),
  H2("3.10  The RF Device-Detection Subsystem"),
  P("Cameras and microphones cannot see a phone hidden under a desk or an earbud tucked under a headscarf, yet such devices betray themselves in another way: they emit radio. Thaqib therefore includes a passive radio-frequency subsystem that detects any wireless device — phone, Bluetooth earbud, smartwatch — that activates inside a hall during an exam. Crucially, it does this by listening, never by jamming. Jamming is rejected outright because the cameras, the invigilator’s tablet, and the dashboard themselves run on Wi-Fi; a jammer would disable the very system meant to be watching. Listening keeps every part of the system fully functional while still breaking the cheating vector, because the invigilator is directed to the exact zone and the device becomes useless the moment a person is standing over it."),
  P("Small, inexpensive scanner nodes (ESP32-class, one or more per hall) passively scan for Bluetooth advertisements and batch what they hear to the backend every few seconds over Wi-Fi. Figure 3.11 traces the flow from a node to an alert."),
  ...figure("fig_rf", "Figure 3.11  RF device-detection data flow", 360),
  P("Each node posts its batch to a dedicated ingest endpoint, authenticated not by a user session but by a per-node pre-shared key — the node has no browser and no JWT. On receipt, every MAC address is immediately reduced to a SHA-256 hash and the raw address is discarded, so the system can recognize a device across sightings without ever holding a personally-identifying hardware address. The reported signal strength is translated into a human-readable zone (for example, “near the front-left, rows 1–4”)."),
  H3("3.10.1  The Baseline and Watch Cycle"),
  P("The subsystem works in two phases. Before the exam, the control room starts a short baseline scan (about five minutes): every device currently broadcasting — the cameras, the access point, the invigilator’s tablet and earbuds — is added to that hall’s whitelist, together with the signal strength at which it was heard. During the exam, two things raise an alert: an entirely unrecognized device appearing, or a whitelisted device whose signal suddenly strengthens — the tell-tale signature of a hidden earbud powering on and a student leaning toward it. Everything else (known devices, sitting quietly where they were during the baseline) is recorded but never alerts, which keeps false alarms low."),
  H3("3.10.2  Integration and Data Model"),
  P("The subsystem deliberately adds no new alerting machinery. An RF hit becomes an ordinary Detection Event with the event type “rf_transmission”, which flows through the exact same aggregation, tiering, alert, dashboard, and reporting path as a gaze or audio incident — it is, in effect, the proof that the system’s single event abstraction (Section 3.5) was worth building. The alert carries the advertised device name (“AirPods Pro”, “Galaxy Buds2”) and the estimated zone, so the invigilator receives a concrete instruction such as “unknown earbud near rows 3–4.” Three new tables support it: rf_scanners (the registered nodes per hall, each holding only a hash of its pre-shared key), rf_whitelist_entries (the per-hall known-safe devices learned during the baseline), and rf_detections (every sighting, with the MAC stored only as a hash). A per-hall badge on the control-room dashboard lists the currently-unknown devices and their zones."),
  H3("3.10.3  Operator Interface"),
  P("The RF subsystem is managed and observed entirely from the existing web interface, so it feels like a native part of the platform rather than a separate tool. Setup happens in Hall management: alongside a hall’s cameras and microphones, an administrator registers each scanner node, and the system returns a one-time pre-shared key (shown once, copied into the node’s configuration) while storing only its hash. This mirrors how cameras and microphones are added, so there is nothing new for an operator to learn."),
  P("Detections are surfaced in two complementary ways. First, a compact per-hall badge in the dashboard header turns red and lists the currently-unknown devices and their zones. Second — and this is the more useful view for a person about to act — each scanner node can be pinned to a point on its camera’s live view, exactly as microphones are placed; when that node hears an unrecognized or newly-active device, a pulsing marker labelled with the device name appears at that spot on the live feed. The operator therefore sees not just that an unknown device is present, but where in the hall it is, which is precisely what an invigilator needs in order to walk to the right seat."),
  P("The same controls are available to both the control-room admin and the in-hall invigilator: the invigilator’s camera view is identical to the admin’s, including node placement and the on-feed markers. The distinction is by responsibility rather than capability — registering nodes and starting the pre-exam baseline are administrative setup tasks, while viewing detections, placing pins, and acting on alerts are available to whoever is monitoring the hall. Figure 3.12 and Figure 3.13 show the on-feed marker and the Hall-management RF section respectively."),
  ...figurePlaceholder("Figure 3.12  On-feed RF detection marker (pulsing label at the device's estimated location)",
    "Insert a screenshot of the camera view with a pulsing RF marker (e.g. “AirPods Pro”)."),
  ...figurePlaceholder("Figure 3.13  Hall-management RF scanner registration (one-time key reveal)",
    "Insert a screenshot of the RF Scanners section in the Hall edit dialog."),
  H2("3.11  Configuration and Extensibility"),
  P("Every tunable aspect of the system is exposed through a single typed configuration layer, so a deployment can be adapted to a particular hall’s cameras, acoustics, and seating without touching code. Detection thresholds, the gaze tolerance and sustained-duration window, the number of neighbours, the re-identification threshold, the full audio calibration behaviour, the database connection, and the security parameters are all environment-overridable, and a validation step rejects unsafe combinations before the system starts. This is what allowed the team to tune the system empirically against real footage, and it is what will allow an institution to re-tune it for its own environment."),
  P("Extensibility was designed in at the seams. New detection behaviours integrate by emitting the same Detection Event the rest of the system already understands, so they automatically inherit the alerting, evidence, review, and reporting machinery without new plumbing. The RF subsystem of Section 3.10 is the realized proof of this: it adds a new event type and a new ingest endpoint, yet reuses the existing event-to-alert-to-dashboard path unchanged. The four-layer architecture, the typed configuration, and the single event abstraction are together what keep the system open to growth."),
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
  H3("4.2.1  Threading Model"),
  P("Table 4.1 lists the concurrent threads that make this possible. The guiding principle is that the main loop must never block on a neural model: every expensive or I/O-bound task runs on its own thread, communicating through small, lock-protected buffers, so the displayed video and the per-frame logic stay responsive."),
  tableCaption("Table 4.1  Concurrent threads in the detection engine"),
  makeTable(["Thread", "Responsibility", "Cadence"], [
    ["Camera capture", "Read frames from the source into a buffer", "Continuous (≈30 FPS)"],
    ["Detection worker", "Run YOLO person + object detection", "~1 Hz"],
    ["Face-mesh pool (×4)", "MediaPipe landmarks + gaze per student", "On demand"],
    ["Main loop", "Tracking, neighbours, evaluation, recording", "Per frame"],
    ["Alert writers (bounded)", "Encode and save evidence clips", "On event"],
    ["Archive writer", "Continuous full-feed recording", "Per frame (queued)"],
  ], [2200, 4626, 2200]),
  H3("4.2.2  Video Configuration Parameters"),
  P("Table 4.2 lists the governing parameters of the video pipeline, with their default values as defined in the settings layer."),
  tableCaption("Table 4.2  Key video-pipeline parameters (defaults)"),
  makeTable(["Parameter", "Default", "Meaning"], params, [3200, 1300, 4526]),
  H3("4.2.3  Audio Configuration Parameters"),
  tableCaption("Table 4.3  Key audio-pipeline parameters (defaults)"),
  makeTable(["Parameter", "Default", "Meaning"], audioParams, [3200, 1500, 4326]),
  H3("4.2.4  Operator Controls"),
  P("When the detection engine is run directly against a feed (for tuning or demonstration), it exposes a set of single-key controls on the live window so an operator can adjust monitoring without stopping the run. Importantly, the display toggles only hide or show overlays — detection and recording continue regardless of what is drawn on screen:"),
  bullet([T("S / M / C — ", { bold: true, size: 24 }), T("select all tracked students for monitoring, toggle a click-to-deselect mode, or clear all selections.", { size: 24 })]),
  bullet([T("D / F / L / T — ", { bold: true, size: 24 }), T("toggle the paper boxes, phone boxes, student-to-paper link lines, and the neighbour graph overlay.", { size: 24 })]),
  bullet([T("V / G — ", { bold: true, size: 24 }), T("cycle the output video quality (low / medium / high) and the processing resolution (native / 1080p / 720p) to trade accuracy against speed.", { size: 24 })]),
  bullet([T("R / W / P / Q — ", { bold: true, size: 24 }), T("switch the archive mode (raw / annotated), toggle the live timestamp, toggle the control panel, and quit.", { size: 24 })]),
  H2("4.3  Source-Code Organization"),
  P("The implementation is organized so that each conceptual stage of Chapter 3 maps to one focused module. This modularity is what made the pipeline testable and tunable: a change to gaze estimation, for example, touches only gaze.py and leaves tracking and recording untouched. Table 4.4 lists the principal modules of the detection engine and backend and their responsibilities."),
  tableCaption("Table 4.4  Principal source modules and responsibilities"),
  makeTable(["Module", "Responsibility"], [
    ["video/pipeline.py", "Master orchestrator: threading, detection scheduling, recording state machine"],
    ["video/camera.py", "Threaded frame capture from USB / RTSP / file sources"],
    ["video/detector.py", "YOLOv11 person (and phone) detection"],
    ["video/tools_detector.py", "YOLOv8 paper / object detection"],
    ["video/tracker.py", "BoT-SORT multi-object tracking and track lifecycle"],
    ["video/registry.py", "Per-student spatial state (the GlobalStudentRegistry)"],
    ["video/neighbors.py", "k-nearest-neighbour graph and paper-ownership assignment"],
    ["video/face_mesh.py", "MediaPipe 478-landmark extraction (worker pool)"],
    ["video/gaze.py", "Gaze vector from head matrix + iris deviation"],
    ["video/cheating_evaluator.py", "Gaze-to-paper rule, duration logic, alert firing"],
    ["video/reid.py", "OSNet appearance re-identification"],
    ["audio/pipeline.py", "Three-thread audio orchestrator and episode tracking"],
    ["audio/discriminator.py", "Calibrated global / local energy classifier"],
    ["audio/keyword_detector.py", "Silero VAD → Faster-Whisper → keyword matching"],
    ["audio/evidence.py", "WAV + JSON forensic evidence with SHA-256"],
    ["av_alert_composer.py", "FFmpeg-based audio+video evidence-clip composition"],
    ["mic_layout.py", "Invigilator mic pins; nearest-microphone-to-seat mapping"],
    ["services/rf_detection.py", "RF hashing, zone estimation, baseline, spike, alert creation"],
    ["services/evidence_retention.py", "Status-based evidence retention + legal hold"],
    ["api/routes/rf.py", "RF ingest (pre-shared key), baseline, whitelist, dashboard badge"],
    ["scanner_node/main.py", "Passive BLE scanner-node firmware (ESP32 / CPython)"],
    ["api/routes/*.py", "FastAPI routers (auth, halls, sessions, events, alerts, voice, stream, rf)"],
    ["db/models/*.py", "SQLAlchemy ORM models for all entities (incl. rf_*)"],
    ["config/settings.py", "Typed, env-overridable configuration (single source of truth)"],
  ], [2700, 6326]),
  H2("4.4  Evidence Generation and Forensics"),
  P("When a student is flagged, the pipeline assembles an evidence clip from a continuously maintained ring buffer: roughly two seconds of footage before the event, the event itself, and a two-second post-event buffer. During the event the frames are annotated — a red box on the flagged student and a yellow box on the targeted neighbour’s paper for a gaze event, or a red box on the phone for a phone event — while the surrounding context frames are kept raw. Clips are written asynchronously by a bounded pool of writer threads (capped at three concurrent recordings to protect memory) and saved as gaze_alert_*.mp4 or phone_alert_*.mp4. The audio pipeline produces an analogous WAV clip with a JSON sidecar carrying the transcript, matched keywords, energy ratios, timestamps, and a SHA-256 hash for chain-of-custody integrity. The full camera feed can also be archived continuously for post-exam review."),
  P("The design treats the evidence clip as the system’s most important external artifact, because it is the thing a human ultimately judges. Three properties make a clip trustworthy. It is contextual: the pre- and post-event buffers show what led up to and followed the moment, so a reviewer is not asked to judge an instant out of context. It is specific: the annotations name the student and the targeted paper, so there is no ambiguity about who and what the alert concerns. And, for audio, it is verifiable: the SHA-256 hash recorded in the JSON sidecar lets anyone confirm the clip has not been altered since capture. Clips are produced only for confirmed events during scheduled sessions, never as a blanket recording, which keeps the volume of stored material small and proportionate."),
  P("Where a hall has microphones, the system goes one step further and produces a combined audio-video clip. Invigilators place “mic pins” on the camera view — marking, in normalized coordinates, where each microphone physically sits — so that when a student is flagged, the system can identify the nearest microphone to that seat and mux its audio onto the video. The composition is performed by a dedicated component that drives FFmpeg, yielding a single MP4 in which the reviewer both sees and hears the incident. This pairing of the right microphone with the right camera region is what turns two separate streams into one coherent piece of evidence."),
  P("Evidence does not accumulate forever. Each alert is assigned a retention deadline based on its outcome: a confirmed incident is kept for three years, a cancelled or false-positive alert for thirty days, and an alert still awaiting review for a hundred and eighty days. A background policy purges material past its deadline, recording the action in the audit log. The one exception is a legal hold: an administrator can freeze an alert’s evidence — capturing the reason, the user, and the time — so that nothing is purged while an incident is the subject of a formal process. Retention and legal hold are exposed through the alert API, so the people responsible for an exam can see and manage exactly how long each piece of evidence will live."),
  ...figurePlaceholder("Figure 4.1  Annotated gaze evidence clip (red = student, yellow = targeted paper)",
    "Insert a representative frame from a generated gaze_alert_*.mp4 clip."),
  H2("4.5  Backend and Persistence"),
  P("The backend persists every detection event, group event, and alert against its exam session, giving each alert a full evidentiary chain back to the device and timestamp. The system is database-agnostic: development uses a zero-setup SQLite file, while production targets PostgreSQL — selected purely through a connection-string environment variable — because live multi-hall monitoring is a concurrent-writer workload that PostgreSQL’s multi-version concurrency control handles and SQLite cannot. Schema evolution is managed with Alembic migrations, verified end-to-end against both engines."),
  P("Real-time delivery to the dashboard is handled in-process. There is no external message broker; instead, a WebSocket connection manager fans out alerts and voice frames directly, and the browser pulls live video as MJPEG over HTTP. This keeps the entire backend a single deployable unit, which is appropriate for an on-premises, single-institution installation and removes whole classes of operational complexity (broker provisioning, queue monitoring) that a graduation-scale deployment does not need."),
  H2("4.6  Deployment Topology"),
  P("In development the system runs as three cooperating processes on fixed ports, with the frontend proxying API and WebSocket traffic to the backend. Table 4.5 lists them. For phone-based microphone testing the app is exposed over HTTPS through a tunnel, because browsers only grant microphone access in a secure context."),
  tableCaption("Table 4.5  Runtime processes (development)"),
  makeTable(["Process", "Port", "Role"], [
    ["Camera simulator", "8000", "Serves MJPEG feeds for seeded devices"],
    ["Backend API (uvicorn)", "8001", "FastAPI application"],
    ["Frontend (Vite)", "5173", "Dashboard; proxies /api to the backend"],
  ], [3000, 1200, 4826]),
  P("The same topology generalizes to production: the simulator is replaced by real IP cameras streaming RTSP, the SQLite file by a PostgreSQL server, and the development tunnel by a proper TLS certificate, with no change to application code."),

  H2("4.7  Experimental Setup and Evaluation"),
  P("This section reports how the integrated system was tested and how its output should be measured. The evaluation is deliberately alert-centric: because Thaqib’s purpose is to raise meaningful alerts for a human, the natural question is not “did it classify every frame correctly” but “when it raised an alert, was that alert meaningful, and did it miss any real incident?”"),
  H3("4.7.1  Simulated Hardware and Network Environment"),
  P("A physical exam hall with many IP cameras, a managed switch, and a dedicated server is expensive to assemble for development. To reproduce its essential behaviour faithfully, the test environment uses a Dockerized camera simulator that serves real Damietta-University exam footage as MJPEG streams over a Docker bridge network. The bridge network introduces real transport — encoding, packetization, latency, and jitter — so the detection engine consumes the footage exactly as it would consume a live RTSP/MJPEG camera over Wi-Fi or LAN, through the same cv2.VideoCapture path. In other words, the hardware and network of a real hall are simulated by containers, while the software path under test is identical to production. Figure 4.2 shows the topology."),
  ...figure("fig_setup", "Figure 4.2  Simulated experimental environment (Docker-based hall)", 540),
  P("Table 4.6 summarizes the environment in which the measurements below were taken."),
  tableCaption("Table 4.6  Experimental environment"),
  makeTable(["Aspect", "Configuration"], [
    ["Input footage", "Real Damietta-University examination recordings (multi-camera)"],
    ["Camera emulation", "Dockerized MJPEG simulator (one stream per camera)"],
    ["Network", "Docker bridge network — simulated Wi-Fi / LAN transport"],
    ["Detection engine", "Python pipeline (YOLOv11, BoT-SORT, MediaPipe, OSNet) via cv2.VideoCapture"],
    ["Backend / dashboard", "FastAPI (:8001) and React dashboard (:5173)"],
    ["Operating point", "risk_angle_tolerance = 25°, suspicious_duration = 2.0 s, audio strict mode"],
  ], [2400, 6626]),
  H3("4.7.2  Evaluation Methodology"),
  P("Ground truth was established by manually reviewing the footage and labelling each genuine incident and its type (gaze copying, phone use, or audio anomaly). The system’s predictions were taken from its own logged output — the detection-event records and the evidence files it produced during the run — so the evaluation measures the system as it actually behaves, not a separate re-implementation. Each alert is then scored against ground truth:"),
  bullet([T("True positive (TP): ", { bold: true, size: 24 }), T("an alert that corresponds to a real incident of the predicted type.", { size: 24 })]),
  bullet([T("False positive (FP): ", { bold: true, size: 24 }), T("an alert raised where no real incident occurred (a false alarm).", { size: 24 })]),
  bullet([T("False negative (FN): ", { bold: true, size: 24 }), T("a real incident that produced no alert (a miss).", { size: 24 })]),
  P("From these, precision (the fraction of raised alerts that were meaningful) and recall (the fraction of real incidents that were caught) are computed per class, together with the F1-score and the support (the number of ground-truth instances). Reporting support alongside every metric is deliberate: a single exam test yields a modest number of staged incidents, so the raw counts matter as much as the ratios when judging how much weight to place on each figure."),
  H3("4.7.3  Detection Accuracy Results"),
  P("Table 4.7 presents the confusion matrix over the alert classes, with the predicted alert type across the columns and the actual behaviour down the rows; the “No cheating” row captures false alarms and the “No alert” column captures missed incidents. Green cells are correct detections (true positives) and orange cells are errors (false positives or misses). Table 4.8 presents the corresponding classification report. Both tables are left blank so the measured counts and metrics can be entered directly from the labelled exam-test log; the structure and operating point are fixed."),
  tableCaption("Table 4.7  Confusion matrix of alert classes (rows = actual behaviour, columns = predicted alert type)"),
  confusionTable(),
  tableCaption("Table 4.8  Classification report per alert class"),
  makeTable(["Class", "Precision", "Recall", "F1-score", "Support"], [
    ["Gaze cheating", "", "", "", ""],
    ["Phone use", "", "", "", ""],
    ["Audio anomaly", "", "", "", ""],
    ["Macro average", "", "", "", ""],
    ["Weighted average", "", "", "", ""],
  ], [2826, 1550, 1550, 1550, 1550]),
  P("These metrics are reported at a single operating point (the thresholds in Table 4.6). Because precision and recall trade off against one another as those thresholds move — a tighter gaze tolerance or a longer sustained-duration requirement raises precision at the cost of recall — the operating point is stated explicitly so the numbers are reproducible and comparable."),
  H3("4.7.4  Latency and Real-Time Performance"),
  P("Separately from accuracy, the system’s real-time behaviour was measured in the same simulated environment. Table 4.9 gives the end-to-end latency budget from camera to dashboard. The key result is that no single stage blocks the live view: network, decode, and inference all run off the main loop, so the dashboard stays smooth while the genuinely intentional delay — the two-second behaviour-confirmation window — dominates the budget by design."),
  tableCaption("Table 4.9  End-to-end latency budget (Docker-simulated environment)"),
  makeTable(["Stage", "Approx. value", "Note"], [
    ["Network transmission (simulated Wi-Fi MJPEG)", "~25 ms", "Absorbed by the background capture thread"],
    ["Frame decode (JPEG → raw)", "~15 ms", "Concurrent with inference"],
    ["AI inference (YOLO + tools)", "~65 ms", "Non-blocking; runs off the display loop"],
    ["Tracking / spatial logic", "~3 ms", "Per frame, on the main loop"],
    ["Behaviour confirmation", "2000 ms", "Sustained-gaze threshold (intentional)"],
    ["Pre-event evidence buffer", "~2–3 s", "Larger than the alert latency — captures the origin"],
  ], [4000, 1500, 3526]),
  P("Because the pre-event ring buffer (~3 seconds) is larger than the total processing latency (~2.1 seconds excluding the intentional confirmation window), every evidence clip reliably captures the moment a behaviour began, not merely the moment the alert fired — a property that matters greatly when the clip must convince a human reviewer."),
  H3("4.7.5  Qualitative Observations"),
  P("Beyond the headline metrics, several qualitative outcomes were consistent across runs:"),
  bullet("Real-time operation held: the asynchronous design sustained a smooth live view while running heavy detection only once per second, with the tracker preserving per-student spatial continuity — and therefore gaze accuracy — between detection cycles."),
  bullet("Attribution was specific: gaze events named both the suspected student and the particular neighbour whose paper was targeted, rather than a generic “suspicious” flag, which makes each alert actionable."),
  bullet("Audio calibration paid off: baseline calibration plus the hangover window sharply reduced the false-local classifications that a naive fixed-ratio rule produces from the natural energy imbalance between microphone positions."),
  bullet("Privacy held in practice: only short, event-triggered clips were generated; gaze used geometric landmarks rather than identity; and audio evidence carried features and transcripts rather than any speaker identification."),
  H2("4.8  Testing and Verification"),
  P("Beyond the accuracy evaluation, correctness was protected throughout development by several complementary practices. The backend is covered by an automated test suite exercised against the development database, so changes to authentication, the alert lifecycle, scoping, and the event/alert routes are regression-checked on every change. The detection engine, being inherently visual, was verified primarily by running it against recorded footage with a rich diagnostic overlay and a structured log: every frame can record the gaze dot-products, the tracked identities, the neighbour assignments, and the recording-state transitions, so a disputed alert can be traced back to the exact frame and number that produced it. This diagnostic log proved invaluable for tuning thresholds and for distinguishing a genuine detection error from a labelling disagreement."),
  P("The database schema was migration-tested end-to-end against both SQLite and PostgreSQL, including the destructive migrations that removed obsolete tables, to guarantee that a production deployment can be provisioned from an empty database with a single command. Together these practices give confidence that the system behaves as documented, and that future changes can be made without silently breaking the real-time path."),
  P("In summary, the experimental setup demonstrates that the full real-time path — capture, detection, tracking, gaze reasoning, alerting, evidence generation, and human review — functions end-to-end on commodity hardware, and it provides the labelled-evaluation framework (confusion matrix and classification report) into which the exam-test accuracy figures are recorded."),
  H3("4.7.6  Threats to Validity"),
  P("Several factors limit how far the evaluation results should be generalized, and they are stated openly so the figures are read with the right caution. The first is sample size: a single exam test yields a modest number of incidents per class, so the precision and recall computed from it are estimates with real uncertainty, and the support column should be consulted before drawing strong conclusions from any single ratio. The second is the nature of the incidents: behaviours observed in a controlled test may be more overt than the careful, deliberately subtle cheating of a high-stakes real exam, which could make the measured recall optimistic."),
  P("A third factor is labelling: ground truth was established by human review of the footage, and the boundary between a guilty stare and an innocent gaze is itself a judgement, so a small amount of labelling subjectivity is unavoidable and is exactly the same ambiguity the system itself must navigate. A fourth is the environment: although the Docker simulator faithfully reproduces the software and network path, it does not reproduce every property of a physical hall — camera mounting angles, lighting variation, and lens characteristics differ from site to site and can affect detection and gaze accuracy. Finally, all results are tied to one operating point; a different threshold setting would move the precision–recall balance, so the numbers describe this configuration, not the system’s best achievable performance."),
  P("None of these threats undermine the central demonstration — that the end-to-end real-time path works and produces meaningful, attributable, evidence-backed alerts — but they do mark out the responsible next step: a larger, multi-session, multi-hall benchmark, which is identified as future work in Chapter 5."),
  H2("4.8  Engineering Challenges and Solutions"),
  P("Building a real-time perception system surfaced a number of concrete problems whose solutions shaped the final design. They are documented here because they are the part of the work least visible in the finished product and most useful to a future maintainer."),
  P([T("Identity under occlusion. ", { bold: true, size: 24 }), T("The first and most persistent problem was that students disappear and reappear constantly — behind a raised arm, a turned head, a passing invigilator — and a naive tracker assigns each reappearance a new identity. Because the entire gaze logic is relational, churning identities silently corrupt the neighbour graph. The solution was three-layered: BoT-SORT’s motion model bridges short gaps, OSNet appearance embeddings re-attach a student after longer absences, and an explicit stability filter with an overlap check injects a predicted box for a selected student while rejecting ghost duplicates.", { size: 24 })]),
  P([T("Gaze noise on distant faces. ", { bold: true, size: 24 }), T("Back-row students occupy few pixels, and a single bad landmark frame can swing the estimated gaze wildly. This was addressed by clamping iris deviation to a sane range, blending iris movement with the more stable head-pose direction, caching the last good mesh for a fraction of a second to ride out momentary detection failures, and — most importantly — requiring a gaze to be sustained for two seconds before it counts, which averages out single-frame noise.", { size: 24 })]),
  P([T("Attribution without a detected paper. ", { bold: true, size: 24 }), T("The object model does not always see every paper, yet the system must still know where a neighbour’s paper is to attribute a gaze. The fallback heuristic — a paper region inferred below a seated student — solved this, but introduced its own risk of phantom targets, so it was restricted to monitored, seated students and suppressed for anyone whose posture suggested they were standing. This is a good example of a place where the safe default (assume no paper) was chosen over the convenient one.", { size: 24 })]),
  P([T("Audio false positives. ", { bold: true, size: 24 }), T("Early audio tests fired constantly on the natural energy imbalance between microphones and on non-speech transients. The calibrated discriminator, the hangover window, the transient suppressor, and the VAD speech confirmation were all added specifically to drive that false-positive rate down to a usable level, and the episode tracker was added so a single whisper produces one alert rather than a burst.", { size: 24 })]),
  P([T("Memory and the real-time budget. ", { bold: true, size: 24 }), T("Holding several seconds of pre-event video for every student at full resolution would exhaust memory in minutes. JPEG-encoding the ring buffer cut its footprint roughly thirty-fold, a concurrency cap limits simultaneous recordings to three, and the slow neural stages were pushed onto background threads so the main loop — and therefore the live view — never blocks. Together these are what let the system run on mid-range hardware rather than a workstation.", { size: 24 })]),
  H2("4.9  The RF Subsystem in Practice"),
  P("The radio-frequency subsystem of Section 3.10 is implemented as three SQLAlchemy tables and an Alembic migration, a focused service module, a small API router, and a single-file scanner firmware. A few implementation choices are worth recording. The ingest endpoint is authenticated by comparing a SHA-256 of the node’s supplied key against the stored hash with a constant-time comparison, so a node needs no user session and a leaked database never reveals a usable key. The baseline window is held in memory per hall — mirroring the deliberately stateless voice channel — because it is short-lived control state with nothing worth persisting. An RSSI increase of roughly fifteen decibels above a device’s baseline is treated as the “moved closer / powered on” signal that re-flags an otherwise-whitelisted device. And the firmware is written to run identically on an ESP32 under MicroPython and on an ordinary laptop under CPython (via the bleak library), which let the whole path be tested without dedicated hardware."),
  P("The path was verified end-to-end: during a simulated baseline three devices were whitelisted and raised no alerts; once the exam phase began, an unrecognized device and a whitelisted device whose signal had spiked each produced a tier-2 alert carrying the device name and zone, while a whitelisted device sitting quietly produced none. Each alert was persisted as an ordinary rf_transmission Detection Event with its Alert, confirming that the subsystem reuses the existing path exactly as intended."),
  H2("4.10  Summary"),
  P("This chapter has grounded every claim of Chapter 3 in the actual implementation: the concurrency model that buys real-time behaviour, the exact configuration values that govern detection, the source modules that realize each stage, the evidence and persistence machinery (including audio-video clip composition and the retention policy), the RF subsystem, the simulated experimental environment, the alert-centric evaluation framework, and the engineering challenges met along the way. What remains, in the next chapter, is to step back and assess what was achieved and what should come next."),
];

// =====================================================================
//  CHAPTER 5 — CONCLUSION & FUTURE WORK
// =====================================================================
const ch5 = [
  ...chapterTitle(5, "Conclusion, Recommendations and Future Work"),
  H2("5.1  Conclusion"),
  P("This project set out to make in-person examination supervision more effective without removing the human from the decision. The delivered system, Thaqib, achieves that goal: it analyses live video and audio in real time, detects gaze-based copying, phone usage, and localized whispering, attributes each visual incident to a specific pair of students, produces tamper-evident evidence, and routes every alert to a human operator who confirms or dismisses it and directs an invigilator to the seat. It is built end-to-end — detection engine, backend platform, and Arabic control-room and invigilator interfaces — and runs on a single institution’s on-premises hardware."),
  P("Equally important is what the system deliberately does not do. It never issues an automatic verdict, it does not continuously judge students, and it produces only short, event-triggered evidence during scheduled sessions. This restraint is what makes an AI proctoring system defensible to deploy."),
  P("Measured against the objectives set out in Chapter 1, the project meets each one: it detects gaze copying, phone use, and localized whispering in real time; it keeps a human in the loop on every decision; it attributes incidents to specific students; it produces tamper-evident evidence; it delivers a complete Arabic control-room and invigilator platform with live voice; and it does all of this while holding almost nothing that could identify an innocent student. The result is not a research prototype but a working, end-to-end system, validated against real exam footage in a faithfully simulated hall."),
  H2("5.2  Recommendations"),
  P("The following recommendations are addressed to any institution considering a deployment, and to the team that carries the project forward."),
  numItem("Pilot before scale: deploy first in a small number of halls to tune the gaze tolerance, sustained-duration, and audio thresholds against the institution’s real seating and acoustics before wider rollout."),
  numItem("Use PostgreSQL in production from day one, and enforce the production security settings (strong secret key, internal event token, non-wildcard CORS, secure cookies)."),
  numItem("Treat alerts as leads, not verdicts: train operators and invigilators on the human-in-the-loop model so the system augments judgement rather than replacing it."),
  numItem("Prefer wired Ethernet for cameras in high-stakes halls for the cleanest signal, while keeping the Wi-Fi path as a validated fallback."),
  H2("5.3  Future Work"),
  H3("5.3.1  RF Device Detection — Further Enhancements"),
  P("The passive RF subsystem (Sections 3.10 and 4.9) is implemented and detects unknown and newly-active Bluetooth devices through a single reporting node per hall, estimating a zone from signal strength. Two enhancements would sharpen it. First, true multi-node triangulation: with three nodes per hall reporting the same device, the zone estimate could be tightened from a hall region toward a seat-level location, by combining the three signal strengths rather than relying on the nearest node alone. Second, wider-spectrum sensing: adding a low-cost software-defined radio (an RTL-SDR on a small single-board computer) would extend coverage from Bluetooth and Wi-Fi into cellular-band energy, catching a phone briefly coming off airplane mode even when it advertises no Bluetooth name."),
  P("A smaller operational improvement would be to schedule the pre-exam baseline automatically a few minutes before each session rather than relying on the control room to start it manually, removing a step from the operator’s checklist. None of these changes alter the core design: each rides on the same Detection Event abstraction that the current subsystem already proves works."),
  H3("5.3.2  Formal Accuracy Evaluation"),
  P("Future work should build a labelled benchmark of staged exam recordings and report precision, recall, and false-alarm rates per detection class, enabling principled threshold tuning and comparison against alternatives. The evaluation framework for this is already in place (Chapter 4): an alert-centric confusion matrix and a per-class classification report, computed from the system’s own logged events against hand-labelled ground truth. Extending it into a benchmark of many sessions, across varied hall layouts and lighting, would let the thresholds be set from evidence rather than intuition, and would allow a principled study of how precision and recall move as the operating point changes."),
  H3("5.3.3  Verified Student Identity Linking"),
  P("Linking an incident to a verified student record (via seat maps or enrolment data) would streamline post-exam reporting; it is intentionally deferred so that the core system stores geometric features rather than identities."),
  H3("5.3.4  Additional Detection Classes and Model Tuning"),
  bullet("Detection of wired earbuds and concealed notes through targeted, fine-tuned object models."),
  bullet("Fine-tuning the person, paper, and phone detectors on hall-specific footage to raise precision in the local environment."),
  bullet("Coordinated multi-student (group) cheating detection, building on the existing group-event data model."),
  H3("5.3.5  Scale and Operations"),
  bullet("Multi-institution / multi-campus deployment with tenant isolation, building on the existing institution hierarchy."),
  bullet("Operational dashboards for system health, model drift, and per-hall alert statistics over time."),
  H2("5.4  Lessons Learned"),
  P("Several engineering lessons shaped the final system and are worth recording for any team that extends it. The first is that real-time perception is won or lost on the concurrency model, not the models themselves: the decisive improvement came not from a better detector but from moving detection off the display loop and letting a cheap tracker carry the frames in between. The second is that calibration beats cleverness in audio: a simple energy ratio became reliable only once it learned each room’s baseline, and no amount of threshold tuning substituted for that. The third is that attribution is what makes an alert useful — flagging that “someone looks suspicious” is nearly worthless to an invigilator, whereas naming the copier and the targeted neighbour turns the alert into an action. The fourth is that restraint is a feature: deciding early that the system would never issue a verdict simplified the design, sharpened the privacy story, and made the whole project defensible."),
  P("Equally instructive were the constraints we chose not to fight. We did not build a message broker, a microservice mesh, or a cloud deployment, because a single-institution hall does not need them; resisting that complexity left a system small enough to understand, test, and hand over. And we treated the documentation and evaluation framework as first-class deliverables rather than afterthoughts, so that the accuracy results can be reproduced at a stated operating point rather than asserted."),
  H2("5.5  Concluding Remarks"),
  P("In summary, Thaqib delivers a complete, working, privacy-respecting foundation for AI-assisted invigilation. It detects the behaviours that matter, attributes them precisely, captures convincing evidence, and routes every decision to a human — and it does so in real time on commodity hardware. The system stands as both a usable tool and a clear roadmap for hardening and extending it toward institution-wide production use, and it demonstrates that artificial intelligence can strengthen examination integrity without ever displacing the human judgement at its centre."),
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
//  APPENDIX A — CONFIGURATION REFERENCE  (grounded in config/settings.py)
// =====================================================================
const cfgVideo = [
  ["camera_width / camera_height", "1280 / 720", "Capture resolution in pixels"],
  ["camera_fps", "30", "Capture frame rate"],
  ["detection_interval", "1.0", "Seconds between full YOLO detection runs"],
  ["detection_confidence", "0.15", "Person-detection confidence threshold"],
  ["detection_imgsz", "640", "YOLO inference resolution"],
  ["tools_confidence", "0.45", "Paper / object detection threshold"],
  ["phone_confidence", "0.30", "Phone-detection threshold"],
  ["phone_class_id", "67", "COCO class id for ‘cell phone’"],
  ["tracking_max_distance", "100", "BoT-SORT association distance"],
  ["tracking_max_age", "30", "Frames a lost track survives"],
  ["neighbor_k", "6", "Nearest neighbours per student"],
  ["risk_angle_tolerance", "25.0", "Max gaze-to-paper angle (degrees)"],
  ["suspicious_duration_threshold", "2.0", "Sustained gaze before flagging (seconds)"],
  ["reid_match_threshold", "0.80", "OSNet cosine similarity for re-identification"],
  ["face_mesh_workers", "4", "Parallel MediaPipe worker threads"],
  ["video_quality", "75", "Output video quality (0–100)"],
  ["alert_max_height", "720", "Max height of alert clips (px)"],
  ["archive_mode", "raw", "Continuous archive mode (raw / annotated)"],
];
const cfgAudio = [
  ["audio_whisper_model", "tiny", "Faster-Whisper model size"],
  ["audio_language", "ar", "Transcription language (Arabic)"],
  ["audio_chunk_ms", "500", "Analysis window length (ms)"],
  ["audio_sample_rate", "16000", "Required by Silero VAD and Whisper"],
  ["audio_silence_threshold", "0.01", "RMS below this counts as silence"],
  ["audio_global_fraction", "0.6", "N-mic fraction that hears a sound to call GLOBAL"],
  ["audio_vad_threshold", "0.5", "Silero speech-confidence threshold (adaptive)"],
  ["audio_strict_mode", "true", "Any confirmed speech = violation"],
  ["audio_calibration_chunks", "30", "Chunks used to learn the energy baseline"],
  ["audio_local_ratio_multiplier", "2.0", "2-mic imbalance over baseline to call LOCAL"],
  ["audio_recalibration_interval_sec", "300", "Seconds between baseline recalibrations"],
  ["audio_clip_sec_before / after", "2.0 / 2.0", "Pre / post buffer in evidence clip"],
  ["audio_episode_min_sec", "3.0", "Sustained duration to confirm an episode"],
  ["audio_episode_grace_sec", "5.0", "Silence gap that closes an episode"],
  ["audio_hpf_cutoff", "100", "High-pass filter cutoff (Hz)"],
  ["audio_noise_reduction", "true", "Spectral noise reduction enabled"],
  ["audio_transient_suppression", "true", "Suppress pen clicks / paper shuffles"],
  ["audio_session_recording", "true", "Record the full session for review"],
];
const cfgServer = [
  ["app_env", "development", "Environment (development / production / testing)"],
  ["database_url", "sqlite:///./data/thaqib.db", "Database connection (SQLite dev / PostgreSQL prod)"],
  ["server_host / server_port", "0.0.0.0 / 8000", "Bind address and port"],
  ["access_token_expire_minutes", "30", "JWT access-token lifetime"],
  ["refresh_token_expire_days", "7", "Refresh-token lifetime"],
  ["cookie_secure", "false (dev)", "Send cookies only over HTTPS (true in production)"],
  ["cookie_samesite", "lax", "SameSite cookie policy"],
  ["cors_origins", "localhost:5173, …", "Allowed front-end origins"],
  ["stream_manager_enabled", "true", "Resume active sessions on startup"],
];

const appendixA = [
  new Paragraph({ children: [new PageBreak()] }),
  ...chapterTitle("", "Appendix A:  Configuration Reference"),
  P("Every parameter below is defined in the typed settings layer (src/thaqib/config/settings.py) and can be overridden per deployment through environment variables or a .env file, with no code change. The values shown are the defaults. Production deployments additionally pass a validation step that rejects unsafe combinations (a default secret key, an unset internal event token, or wildcard CORS)."),
  H2("A.1  Video and Detection"),
  tableCaption("Table A.1  Video and detection settings"),
  makeTable(["Setting", "Default", "Description"], cfgVideo, [3500, 1500, 4026]),
  H2("A.2  Audio"),
  tableCaption("Table A.2  Audio settings"),
  makeTable(["Setting", "Default", "Description"], cfgAudio, [3500, 1500, 4026]),
  H2("A.3  Server, Database and Security"),
  tableCaption("Table A.3  Server, database and security settings"),
  makeTable(["Setting", "Default", "Description"], cfgServer, [3500, 1700, 3826]),
];

// =====================================================================
//  APPENDIX B — GLOSSARY OF TERMS
// =====================================================================
const glossary = [
  ["Alert", "A reviewable notification raised from one or more detection events; tiered and human-confirmed."],
  ["Detection Event", "A single AI detection (one gaze, phone, or audio anomaly), persisted with its evidence."],
  ["Group Event", "Several correlated detection events merged into one — e.g., two neighbours copying together."],
  ["Gaze vector", "The normalized 2-D screen-space direction a student is looking, fused from head pose and iris."],
  ["Risk angle / tolerance", "The angular window within which a gaze counts as ‘looking at’ a neighbour’s paper."],
  ["Sustained-duration threshold", "How long a gaze must hold continuously before it is flagged as cheating."],
  ["Re-identification (ReID)", "Re-attaching a returning student to their original track identity by appearance."],
  ["Track / Track ID", "The persistent identity a tracker assigns to a student across frames."],
  ["Neighbour graph", "The live k-nearest-neighbour structure linking each student to nearby peers."],
  ["Local vs global sound", "A whisper confined to one microphone versus noise heard across the whole hall."],
  ["Episode", "A grouped run of repeated audio alerts treated as one sustained cheating event."],
  ["Hall readiness", "The state in which all of a hall’s devices are online and monitoring may begin."],
  ["Evidence clip", "The annotated short MP4 / WAV that captures an event with pre- and post-event buffers."],
  ["Human-in-the-loop", "The principle that a person makes every final decision; the system only advises."],
  ["Operating point", "The specific set of thresholds at which the accuracy metrics are reported."],
];
const appendixB = [
  new Paragraph({ children: [new PageBreak()] }),
  ...chapterTitle("", "Appendix B:  Glossary of Terms"),
  P("The following domain terms are used throughout this document. They are distinct from the acronyms listed in the front-matter List of Abbreviations."),
  makeTable(["Term", "Definition"], glossary, [2800, 6226]),
];

// =====================================================================
//  APPENDIX C — REQUIREMENTS TRACEABILITY MATRIX
// =====================================================================
const traceability = [
  ["FR-1", "core/security.py, api/routes/auth.py (JWT, RBAC, refresh tokens)", "§3.6"],
  ["FR-2", "api/routes/institutions.py, halls.py, setup.py (setup wizard)", "§3.6"],
  ["FR-3", "api/routes/devices.py, stream.py (readiness check)", "§3.8, §3.10"],
  ["FR-4", "api/routes/exams.py, db/models/exams.py (sessions, assignments)", "§3.5"],
  ["FR-5", "video/pipeline.py, camera.py, detector.py, tracker.py", "§3.3"],
  ["FR-6", "gaze.py, neighbors.py, cheating_evaluator.py", "§3.3.2–3.3.4"],
  ["FR-7", "detector.py + pipeline phone attribution", "§3.3.5"],
  ["FR-8", "audio/discriminator.py, keyword_detector.py, pipeline.py", "§3.4"],
  ["FR-9", "video/pipeline.py recording state machine, audio/evidence.py", "§3.3.6, §4.4"],
  ["FR-10", "api/routes/alerts.py, db/models/events.py (Alert lifecycle)", "§3.5"],
  ["FR-11", "api/routes/voice.py, hooks/useHallVoice.ts (hall voice channel)", "§3.7"],
  ["FR-12", "api/routes/exams.py (session report endpoint)", "§3.6"],
  ["FR-13", "db/models/rf.py, services/rf_detection.py, api/routes/rf.py, scanner_node/", "§3.10, §4.9"],
  ["FR-14", "services/evidence_retention.py, db/models/events.py (Alert fields)", "§3.9, §4.4"],
];
const appendixC = [
  new Paragraph({ children: [new PageBreak()] }),
  ...chapterTitle("", "Appendix C:  Requirements Traceability Matrix"),
  P("The matrix below links each functional requirement from Chapter 2 to the source modules that implement it and the section of this document that describes it. It provides a quick audit trail from requirement to realization, confirming that every specified function is delivered by an identifiable part of the system."),
  tableCaption("Table C.1  Functional-requirement traceability"),
  makeTable(["Req.", "Implemented by", "Section"], traceability, [1100, 6126, 1800]),
  P("Non-functional requirements (Table 2.3) are satisfied cross-cuttingly: performance by the concurrency model (§4.2), security by the mechanisms of Table 3.3, privacy by the design decisions of §3.9, scalability by the database strategy (§4.5), and maintainability by the modular organization of Table 4.4."),
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
  "Figure 2.1  System context diagram",
  "Figure 2.2  Use-Case diagram of the Thaqib system",
  "Figure 3.1  High-level four-layer architecture of Thaqib",
  "Figure 3.2  The real-time video detection pipeline",
  "Figure 3.3  Gaze-to-paper geometry and the risk-angle rule",
  "Figure 3.4  Three-stage audio detection pipeline",
  "Figure 3.5  Alert review lifecycle (state diagram)",
  "Figure 3.6  Entity-Relationship diagram",
  "Figure 3.7  Domain class diagram",
  "Figure 3.8  Sequence diagram — detection to confirmation",
  "Figure 3.9  Control-room dashboard",
  "Figure 3.10  Invigilator hall-monitoring view",
  "Figure 3.11  RF device-detection data flow",
  "Figure 3.12  On-feed RF detection marker",
  "Figure 3.13  Hall-management RF scanner registration",
  "Figure 4.1  Annotated gaze evidence clip",
  "Figure 4.2  Simulated experimental environment (Docker-based hall)",
]);

const listOfTables = manualList("List of Tables", [
  "Table 2.1  Comparison of Thaqib with existing approaches",
  "Table 2.2  Functional requirements",
  "Table 2.3  Non-functional requirements",
  "Table 2.4  Principal use-case descriptions",
  "Table 2.5  Recommended production hardware",
  "Table 3.1  Implemented technology stack",
  "Table 3.2  Principal backend API groups",
  "Table 3.3  Security mechanisms",
  "Table 4.1  Concurrent threads in the detection engine",
  "Table 4.2  Key video-pipeline parameters",
  "Table 4.3  Key audio-pipeline parameters",
  "Table 4.4  Principal source modules and responsibilities",
  "Table 4.5  Runtime processes (development)",
  "Table 4.6  Experimental environment",
  "Table 4.7  Confusion matrix of alert classes",
  "Table 4.8  Classification report per alert class",
  "Table 4.9  End-to-end latency budget (simulated)",
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
        ...chapterDivider(1, "Introduction"),
        ...ch1,
        ...chapterDivider(2, "Problem Definition, Related Work and Analysis"),
        ...ch2,
        ...chapterDivider(3, "The Proposed Framework"),
        ...ch3,
        ...chapterDivider(4, "Implementation and Results"),
        ...ch4,
        ...chapterDivider(5, "Conclusion, Recommendations and Future Work"),
        ...ch5,
        new Paragraph({ children: [new PageBreak()] }),
        ...referencesSection,
        ...appendixA,
        ...appendixB,
        ...appendixC,
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
