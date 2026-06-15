/* Generates all UML / system diagrams as PNG images into docs/figures/.
   Pure SVG -> PNG via @resvg/resvg-js. Returns a manifest for build_doc.js. */
const fs = require("fs");
const path = require("path");
const { Resvg } = require("@resvg/resvg-js");

const FIG_DIR = path.join(__dirname, "figures");
fs.mkdirSync(FIG_DIR, { recursive: true });

// palette
const C = {
  stroke: "#1F4E79", fill: "#DCE6F4", text: "#1F3864",
  acc: "#F4B183", accFill: "#FCE4D6", accStroke: "#C55A11",
  grn: "#A9D08E", grnFill: "#E2EFDA", grnStroke: "#548235",
  hdr: "#1F4E79", white: "#FFFFFF", grey: "#808080", line: "#404040",
};
const FF = "Arial, Helvetica, sans-serif";

// ---------- SVG primitives ----------
function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }

function textLines(cx, cy, label, opts = {}) {
  const { size = 15, color = C.text, bold = false, anchor = "middle", lh = 18 } = opts;
  const lines = String(label).split("\n");
  const startY = cy - ((lines.length - 1) * lh) / 2;
  return lines.map((ln, i) =>
    `<text x="${cx}" y="${startY + i * lh}" font-family="${FF}" font-size="${size}" fill="${color}" ` +
    `text-anchor="${anchor}" dominant-baseline="middle" ${bold ? 'font-weight="700"' : ""}>${esc(ln)}</text>`
  ).join("");
}

function box(x, y, w, h, label, o = {}) {
  const fill = o.fill || C.fill, stroke = o.stroke || C.stroke, r = o.r ?? 8;
  return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" ry="${r}" fill="${fill}" stroke="${stroke}" stroke-width="${o.sw || 1.5}"/>` +
    textLines(x + w / 2, y + h / 2, label, { size: o.size || 14, color: o.color || C.text, bold: o.bold });
}

function ellipse(cx, cy, rx, ry, label, o = {}) {
  return `<ellipse cx="${cx}" cy="${cy}" rx="${rx}" ry="${ry}" fill="${o.fill || C.grnFill}" stroke="${o.stroke || C.grnStroke}" stroke-width="1.5"/>` +
    textLines(cx, cy, label, { size: o.size || 12.5, color: o.color || "#2C4A1E" });
}

function actor(cx, topY, label) {
  const r = 9;
  const headY = topY + r;
  return `<g stroke="${C.line}" stroke-width="2" fill="none">` +
    `<circle cx="${cx}" cy="${headY}" r="${r}" fill="#fff"/>` +
    `<line x1="${cx}" y1="${headY + r}" x2="${cx}" y2="${headY + r + 26}"/>` +
    `<line x1="${cx - 16}" y1="${headY + r + 8}" x2="${cx + 16}" y2="${headY + r + 8}"/>` +
    `<line x1="${cx}" y1="${headY + r + 26}" x2="${cx - 13}" y2="${headY + r + 46}"/>` +
    `<line x1="${cx}" y1="${headY + r + 26}" x2="${cx + 13}" y2="${headY + r + 46}"/>` +
    `</g>` + textLines(cx, headY + r + 62, label, { size: 13, bold: true, color: C.text });
}

function line(x1, y1, x2, y2, o = {}) {
  const dash = o.dash ? `stroke-dasharray="${o.dash}"` : "";
  const marker = o.arrow === false ? "" : `marker-end="url(#arrow)"`;
  return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${o.color || C.line}" stroke-width="${o.sw || 1.5}" ${dash} ${marker}/>`;
}

function lbl(x, y, t, o = {}) {
  return `<text x="${x}" y="${y}" font-family="${FF}" font-size="${o.size || 12}" fill="${o.color || C.line}" text-anchor="${o.anchor || "middle"}" ${o.bold ? 'font-weight="700"' : ""}>${esc(t)}</text>`;
}

function svgDoc(w, h, body, title) {
  const cap = ""; // captions live in the Word document, not the image
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">` +
    `<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">` +
    `<path d="M0,0 L10,5 L0,10 z" fill="${C.line}"/></marker>` +
    `<marker id="arrowOpen" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="11" markerHeight="11" orient="auto-start-reverse">` +
    `<path d="M1,1 L11,6 L1,11" fill="none" stroke="${C.line}" stroke-width="1.5"/></marker>` +
    `<marker id="diamond" viewBox="0 0 14 10" refX="13" refY="5" markerWidth="14" markerHeight="10" orient="auto">` +
    `<path d="M0,5 L7,0 L14,5 L7,10 z" fill="#fff" stroke="${C.line}" stroke-width="1.2"/></marker>` +
    `<marker id="tri" viewBox="0 0 14 12" refX="13" refY="6" markerWidth="13" markerHeight="11" orient="auto">` +
    `<path d="M0,1 L13,6 L0,11 z" fill="#fff" stroke="${C.line}" stroke-width="1.3"/></marker></defs>` +
    `<rect width="${w}" height="${h}" fill="#ffffff"/>` + body + cap + `</svg>`;
}

// ---------- render helper ----------
const manifest = {};
function render(key, w, h, svg) {
  const r = new Resvg(svg, { fitTo: { mode: "zoom", value: 2 }, font: { loadSystemFonts: true } });
  const png = r.render().asPng();
  const file = path.join(FIG_DIR, key + ".png");
  fs.writeFileSync(file, png);
  manifest[key] = { path: "figures/" + key + ".png", w, h };
}

// =====================================================================
// 1. CONTEXT DIAGRAM
// =====================================================================
(function () {
  const w = 900, h = 520, cx = 450, cy = 250;
  let b = "";
  // central system
  b += `<ellipse cx="${cx}" cy="${cy}" rx="150" ry="95" fill="${C.fill}" stroke="${C.stroke}" stroke-width="2.5"/>`;
  b += textLines(cx, cy, "THAQIB\nSmart Cheating\nDetection System", { size: 17, bold: true, color: C.stroke });
  // external entities
  const ents = [
    { x: 60, y: 60, t: "IP Cameras", out: "video streams" },
    { x: 60, y: 360, t: "Microphones", out: "audio streams" },
    { x: 650, y: 40, t: "Super-Admin", in2: "config, users" },
    { x: 650, y: 180, t: "Admin\n(Control Room)", in2: "schedule, confirm" },
    { x: 650, y: 330, t: "Invigilator", in2: "start/stop, voice" },
  ];
  ents.forEach((e) => { b += box(e.x, e.y, 190, 64, e.t, { fill: "#fff", stroke: C.grey, bold: true, size: 14 }); });
  // arrows + labels
  b += line(250, 92, 330, 200) + lbl(280, 130, "video", { size: 11 });
  b += line(250, 392, 330, 300) + lbl(280, 360, "audio", { size: 11 });
  b += line(650, 72, 575, 190) + lbl(640, 120, "manage", { size: 11, anchor: "end" });
  b += line(650, 212, 600, 240) + lbl(640, 200, "monitor / review", { size: 11, anchor: "end" });
  b += line(575, 305, 650, 360) + lbl(600, 345, "incident push", { size: 11, anchor: "start" });
  render("fig_context", w, h, svgDoc(w, h, b, "Figure 2.1  Context diagram"));
})();

// =====================================================================
// 2. USE-CASE DIAGRAM
// =====================================================================
(function () {
  const w = 1000, h = 760;
  let b = "";
  const ucx = 500, RX = 130, RY = 19;
  // system boundary
  b += `<rect x="${ucx - 175}" y="30" width="350" height="700" rx="10" fill="#F7FAFF" stroke="${C.stroke}" stroke-width="2"/>`;
  b += lbl(ucx, 54, "Thaqib System", { size: 16, bold: true, color: C.stroke });
  // single-column use cases (no overlap): id, y, label, actors[]
  const SA = "sa", AD = "ad", IN = "in";
  const uc = [
    [90, "Authenticate / Login", [SA, AD, IN]],
    [138, "Manage Institution & Halls", [SA]],
    [186, "Register Devices", [SA]],
    [234, "Manage Users", [SA]],
    [282, "Schedule Exam Session", [AD]],
    [330, "Assign Invigilators / Admins", [AD]],
    [378, "Monitor Live Feeds", [AD]],
    [426, "Review & Confirm Alerts", [AD]],
    [474, "View Evidence Clips", [AD]],
    [522, "View Assigned Schedule", [IN]],
    [570, "Start / Stop Hall Monitoring", [IN]],
    [618, "Hall Voice Communication", [AD, IN]],
    [666, "Generate Session Report", [AD]],
  ];
  uc.forEach((u) => { b += ellipse(ucx, u[0], RX, RY, u[1]); });
  // actors
  b += actor(75, 130, "Super-Admin");
  b += actor(75, 360, "Admin");
  b += actor(895, 360, "Invigilator");
  const anchors = { sa: [110, 165], ad: [110, 405], in: [880, 405] };
  uc.forEach((u) => {
    u[2].forEach((who) => {
      const a = anchors[who];
      const tx = who === "in" ? ucx + RX : ucx - RX;
      b += line(a[0], a[1], tx, u[0], { arrow: false, color: C.grey, sw: 1 });
    });
  });
  b += lbl(ucx, 715, "All actors «include» Authenticate / Login", { size: 11, color: C.grey });
  render("fig_usecase", w, h, svgDoc(w, h, b, "Figure 2.2  Use-Case diagram"));
})();

// =====================================================================
// 3. CLASS DIAGRAM (domain model)
// =====================================================================
(function () {
  const w = 1020, h = 760;
  let b = "";
  function cls(x, y, wd, name, attrs) {
    const hh = 26 + attrs.length * 16 + 8;
    let s = `<rect x="${x}" y="${y}" width="${wd}" height="${hh}" fill="#fff" stroke="${C.stroke}" stroke-width="1.5"/>`;
    s += `<rect x="${x}" y="${y}" width="${wd}" height="24" fill="${C.fill}" stroke="${C.stroke}" stroke-width="1.5"/>`;
    s += lbl(x + wd / 2, y + 16, name, { size: 13.5, bold: true, color: C.stroke });
    attrs.forEach((a, i) => { s += `<text x="${x + 8}" y="${y + 42 + i * 16}" font-family="${FF}" font-size="11.5" fill="${C.text}">${esc(a)}</text>`; });
    return { svg: s, x, y, w: wd, h: hh, cx: x + wd / 2, cy: y + hh / 2 };
  }
  const inst = cls(40, 40, 215, "Institution", ["id : UUID", "name, code", "type, parent_id"]);
  const hall = cls(40, 250, 215, "Hall", ["id : UUID", "name, building, floor", "capacity, status"]);
  const dev = cls(40, 470, 215, "Device", ["id : UUID", "type (camera/mic)", "stream_url, status"]);
  const user = cls(330, 40, 215, "User", ["id : UUID", "username, role", "full_name, status"]);
  const exam = cls(330, 280, 230, "ExamSession", ["id : UUID", "exam_name, type", "scheduled/actual times", "status, student_count"]);
  const assign = cls(330, 540, 230, "Assignment", ["id : UUID", "role (primary/secondary)", "monitoring_started/ended"]);
  const det = cls(660, 40, 230, "DetectionEvent", ["id : UUID", "event_type, severity", "student_position : JSON", "confidence, clip paths"]);
  const grp = cls(660, 250, 230, "GroupEvent", ["id : UUID", "event_type, severity", "student_positions : JSON"]);
  const alert = cls(660, 470, 230, "Alert", ["id : UUID", "alert_type (tier_1/2)", "status, claimed_by", "confirmed_by / cancelled_by"]);
  [inst, hall, dev, user, exam, assign, det, grp, alert].forEach((c) => (b += c.svg));
  // relations (composition diamond at the 'whole')
  const comp = (a, bx) => line(a.x + a.w / 2, a.y + a.h, bx.x + bx.w / 2, bx.y, { color: C.line }) ; // simple
  // Institution 1..* Hall
  b += `<line x1="147" y1="${inst.y + inst.h}" x2="147" y2="${hall.y}" stroke="${C.line}" stroke-width="1.5" marker-start="url(#diamond)"/>`;
  b += lbl(160, 235, "1   *", { size: 11, anchor: "start" });
  // Hall 1..* Device
  b += `<line x1="147" y1="${hall.y + hall.h}" x2="147" y2="${dev.y}" stroke="${C.line}" stroke-width="1.5" marker-start="url(#diamond)"/>`;
  b += lbl(160, 455, "1   *", { size: 11, anchor: "start" });
  // Institution 1..* User
  b += line(255, 95, 330, 95, { arrow: false }) ; b += lbl(292, 88, "1  *", { size: 10 });
  // ExamSession *..* Hall
  b += line(330, 320, 255, 300, { color: C.line, arrow: false }); b += lbl(290, 295, "*  *", { size: 10 });
  // ExamSession 1..* Assignment
  b += line(445, exam.y + exam.h, 445, assign.y, { color: C.line, arrow: false }); b += lbl(458, 525, "1  *", { size: 10, anchor: "start" });
  // Assignment -> User / Hall
  b += line(assign.x, 580, 255, 110, { color: C.grey, dash: "4 3", arrow: false });
  // ExamSession 1..* DetectionEvent
  b += line(exam.x + exam.w, 300, det.x, 110, { color: C.line, arrow: false }); b += lbl(610, 200, "1  *", { size: 10 });
  // DetectionEvent *..1 GroupEvent
  b += line(775, det.y + det.h, 775, grp.y, { color: C.line, arrow: false }); b += lbl(788, 235, "*  0..1", { size: 10, anchor: "start" });
  // GroupEvent / DetectionEvent -> Alert
  b += line(775, grp.y + grp.h, 775, alert.y, { color: C.line, arrow: false }); b += lbl(788, 455, "1  *", { size: 10, anchor: "start" });
  // ExamSession 1..* Alert
  b += line(545, 360, 660, 500, { color: C.line, arrow: false }); b += lbl(600, 445, "1  *", { size: 10 });
  render("fig_class", w, h, svgDoc(w, h, b, "Figure 3.7  Domain class diagram (core entities)"));
})();

// =====================================================================
// 4. SEQUENCE DIAGRAM
// =====================================================================
(function () {
  const w = 1000, h = 620;
  let b = "";
  const actors = [
    { x: 90, t: "Detection\nEngine" },
    { x: 290, t: "Backend API\n(FastAPI)" },
    { x: 490, t: "Database" },
    { x: 690, t: "Admin\n(Control Room)" },
    { x: 890, t: "Invigilator" },
  ];
  const topY = 30, lifeBottom = 560;
  actors.forEach((a) => {
    b += box(a.x - 70, topY, 140, 44, a.t, { fill: C.fill, bold: true, size: 12.5 });
    b += `<line x1="${a.x}" y1="${topY + 44}" x2="${a.x}" y2="${lifeBottom}" stroke="${C.grey}" stroke-width="1.2" stroke-dasharray="4 4"/>`;
  });
  function msg(y, x1, x2, t, dashed) {
    const d = dashed ? `stroke-dasharray="5 4"` : "";
    const dir = x2 > x1 ? "start" : "end";
    return `<line x1="${x1}" y1="${y}" x2="${x2}" y2="${y}" stroke="${C.line}" stroke-width="1.5" ${d} marker-end="url(#arrowOpen)"/>` +
      lbl((x1 + x2) / 2, y - 7, t, { size: 11.5 });
  }
  function self(y, x, t) {
    return `<path d="M${x},${y} h40 v22 h-40" fill="none" stroke="${C.line}" stroke-width="1.5" marker-end="url(#arrowOpen)"/>` + lbl(x + 70, y + 6, t, { size: 11, anchor: "start" });
  }
  let y = 110;
  b += self(y, 90, "detect gaze/phone/audio event"); y += 50;
  b += msg(y, 90, 290, "POST /api/events (+ evidence clip)"); y += 34;
  b += msg(y, 290, 490, "store DetectionEvent", false); y += 30;
  b += msg(y, 490, 290, "ok", true); y += 34;
  b += msg(y, 290, 690, "alert appears in shared queue (poll/WS)"); y += 40;
  b += self(y, 690, "review evidence, decide"); y += 50;
  b += msg(y, 690, 290, "POST /api/alerts/{id}/confirm"); y += 30;
  b += msg(y, 290, 490, "update Alert = confirmed", false); y += 34;
  b += msg(y, 290, 890, "notify_hall: incident card (voice WS)"); y += 40;
  b += self(y, 890, "walk to seat, take action"); y += 46;
  render("fig_sequence", w, h, svgDoc(w, h, b, "Figure 3.8  Sequence diagram — detection to confirmation"));
})();

// =====================================================================
// 5. ACTIVITY DIAGRAM
// =====================================================================
(function () {
  const w = 760, h = 940;
  let b = "";
  const cx = 380;
  b += `<circle cx="${cx}" cy="35" r="14" fill="${C.line}"/>`;
  function act(y, t, wd = 230) { b += box(cx - wd / 2, y, wd, 42, t, { fill: C.fill, size: 13 }); return y + 42; }
  function diamond(y, t) {
    b += `<path d="M${cx},${y} L${cx + 70},${y + 35} L${cx},${y + 70} L${cx - 70},${y + 35} z" fill="#fff" stroke="${C.stroke}" stroke-width="1.5"/>`;
    b += textLines(cx, y + 35, t, { size: 12, color: C.text });
    return y + 70;
  }
  function arr(y1, y2) { b += line(cx, y1, cx, y2); }
  arr(49, 70); let y = 70;
  y = act(y, "Admin schedules exam &\nassigns invigilators"); arr(y, y + 18); y += 18;
  y = act(y, "Invigilator opens hall &\nruns readiness check"); arr(y, y + 18); y += 18;
  let dy = diamond(y, "All devices\nonline?");
  b += lbl(cx + 80, y + 35, "no → fix device", { size: 11, anchor: "start", color: C.accStroke });
  b += `<path d="M${cx + 70},${y + 35} h40 v-120 h-40" fill="none" stroke="${C.line}" stroke-width="1.3" marker-end="url(#arrow)"/>`;
  arr(dy, dy + 18); b += lbl(cx + 8, dy + 6, "yes", { size: 11, anchor: "start", color: C.grnStroke }); y = dy + 18;
  y = act(y, "Start monitoring — engine\nprocesses live frames"); arr(y, y + 18); y += 18;
  let d2 = diamond(y, "Suspicious\nbehaviour?");
  b += `<path d="M${cx - 70},${y + 35} h-70 v-120 h70" fill="none" stroke="${C.line}" stroke-width="1.3" marker-end="url(#arrow)"/>`;
  b += lbl(cx - 150, y + 35, "no\n(keep watching)", { size: 10.5, anchor: "middle", color: C.grey });
  arr(d2, d2 + 18); b += lbl(cx + 8, d2 + 6, "yes", { size: 11, anchor: "start", color: C.accStroke }); y = d2 + 18;
  y = act(y, "Generate alert + save\nannotated evidence clip"); arr(y, y + 18); y += 18;
  y = act(y, "Admin reviews evidence"); arr(y, y + 18); y += 18;
  let d3 = diamond(y, "Confirm?");
  b += `<path d="M${cx - 70},${y + 35} h-90 v40 h90" fill="none" stroke="${C.line}" stroke-width="1.3" marker-end="url(#arrow)"/>`;
  b += lbl(cx - 165, y + 35, "cancel\n(false +)", { size: 10.5, color: C.grey });
  arr(d3, d3 + 18); b += lbl(cx + 8, d3 + 6, "yes", { size: 11, anchor: "start", color: C.grnStroke }); y = d3 + 18;
  y = act(y, "Push incident to invigilator\n(voice channel)"); arr(y, y + 18); y += 18;
  y = act(y, "Invigilator acts in hall"); arr(y, y + 18); y += 18;
  let d4 = diamond(y, "Exam\nfinished?");
  b += `<path d="M${cx + 70},${y + 35} h150 v-300 h-150" fill="none" stroke="${C.line}" stroke-width="1.3" marker-end="url(#arrow)"/>`;
  b += lbl(cx + 230, y - 110, "no — continue monitoring", { size: 10.5, anchor: "middle", color: C.grey });
  arr(d4, d4 + 18); b += lbl(cx + 8, d4 + 6, "yes", { size: 11, anchor: "start", color: C.grnStroke }); y = d4 + 18;
  y = act(y, "End session &\ngenerate report"); arr(y, y + 16);
  b += `<circle cx="${cx}" cy="${y + 30}" r="14" fill="#fff" stroke="${C.line}" stroke-width="2"/><circle cx="${cx}" cy="${y + 30}" r="7" fill="${C.line}"/>`;
  render("fig_activity", 760, 940, svgDoc(760, 940, b, "Figure 3.9  Activity diagram — exam monitoring workflow"));
})();

// =====================================================================
// 6. STATE DIAGRAM (alert lifecycle)
// =====================================================================
(function () {
  const w = 920, h = 380;
  let b = "";
  b += `<circle cx="60" cy="170" r="13" fill="${C.line}"/>`;
  const pending = box(120, 145, 130, 50, "pending", { fill: C.fill, bold: true });
  const claimed = box(330, 145, 130, 50, "claimed", { fill: C.fill, bold: true });
  const confirmed = box(560, 60, 150, 50, "confirmed", { fill: C.grnFill, stroke: C.grnStroke, bold: true });
  const cancelled = box(560, 250, 150, 50, "cancelled", { fill: C.accFill, stroke: C.accStroke, bold: true });
  const escalated = box(330, 250, 130, 50, "escalated", { fill: "#FFF2CC", stroke: "#BF9000", bold: true });
  b += pending + claimed + confirmed + cancelled + escalated;
  b += line(73, 170, 120, 170);
  b += line(250, 170, 330, 170) + lbl(290, 162, "claim", { size: 11 });
  b += line(460, 160, 560, 95) + lbl(515, 115, "confirm", { size: 11 });
  b += line(460, 180, 560, 270) + lbl(515, 235, "cancel", { size: 11 });
  b += line(395, 195, 395, 250) + lbl(430, 225, "escalate", { size: 11, anchor: "start" });
  b += line(460, 275, 560, 285) + lbl(515, 305, "confirm /\ncancel", { size: 10.5 });
  // final
  b += `<circle cx="790" cy="85" r="12" fill="#fff" stroke="${C.line}" stroke-width="2"/><circle cx="790" cy="85" r="6" fill="${C.line}"/>`;
  b += `<circle cx="790" cy="275" r="12" fill="#fff" stroke="${C.line}" stroke-width="2"/><circle cx="790" cy="275" r="6" fill="${C.line}"/>`;
  b += line(710, 85, 778, 85); b += line(710, 275, 778, 275);
  render("fig_state", w, h, svgDoc(w, h, b, "Figure 3.3  State diagram — alert lifecycle"));
})();

// =====================================================================
// 7. ARCHITECTURE (4 layers)
// =====================================================================
(function () {
  const w = 880, h = 600;
  let b = "";
  const lw = 760, lx = 60;
  function layer(y, title, sub, fill, stroke) {
    b += `<rect x="${lx}" y="${y}" width="${lw}" height="92" rx="8" fill="${fill}" stroke="${stroke}" stroke-width="1.8"/>`;
    b += lbl(lx + 16, y + 26, title, { size: 15, bold: true, anchor: "start", color: stroke });
    b += textLines(lx + lw / 2 + 40, y + 60, sub, { size: 12.5, color: C.text });
  }
  layer(40, "1. Data Acquisition", "IP cameras (RTSP / USB / file)        USB / IP microphones", "#EAF1FB", C.stroke);
  layer(180, "2. Detection Engine  (Python)", "Video: YOLOv11 → BoT-SORT → OSNet → MediaPipe → Gaze → Evaluator\nAudio: Energy discriminator → Silero VAD → Faster-Whisper", C.accFill, C.accStroke);
  layer(320, "3. Backend  (FastAPI + SQLAlchemy)", "REST API · WebSocket voice · MJPEG streams · Alert review\nSQLite (dev) / PostgreSQL (prod)", "#EAF1FB", C.stroke);
  layer(460, "4. Dashboard  (React + TypeScript, Arabic RTL)", "Admin / control-room console      ·      Invigilator hall view", C.grnFill, C.grnStroke);
  // connectors
  [132, 272, 412].forEach((y) => { b += line(440, y, 440, y + 48); });
  render("fig_arch", w, h, svgDoc(w, h, b, "Figure 3.1  Four-layer system architecture"));
})();

// =====================================================================
// 8. VIDEO PIPELINE
// =====================================================================
(function () {
  const w = 820, h = 760;
  let b = "";
  const cx = 410, bw = 470;
  const steps = [
    ["Camera capture  (USB / RTSP / file, threaded)", C.fill, C.stroke],
    ["YOLOv11 person detection   — conf 0.15, every 1.0 s", C.accFill, C.accStroke],
    ["BoT-SORT tracking   — persistent IDs, 30 FPS lock", C.accFill, C.accStroke],
    ["OSNet re-identification   — cosine ≥ 0.80", C.accFill, C.accStroke],
    ["MediaPipe face landmarks   — 478 pts, 4 workers", C.accFill, C.accStroke],
    ["Gaze vector   — head matrix + iris deviation", C.accFill, C.accStroke],
    ["k-NN neighbour + paper model   — k = 6", C.fill, C.stroke],
    ["Cheating evaluator   — cos(θ) > cos(25°), ≥ 2.0 s", C.grnFill, C.grnStroke],
    ["Annotated evidence clip  +  Detection Event", C.fill, C.stroke],
  ];
  let y = 30;
  steps.forEach((s, i) => {
    b += box(cx - bw / 2, y, bw, 52, s[0], { fill: s[1], stroke: s[2], size: 12.5 });
    if (i < steps.length - 1) b += line(cx, y + 52, cx, y + 78);
    y += 78;
  });
  // phone branch
  b += box(cx + bw / 2 + 20, 186, 150, 130, "Phone detection\n(COCO cell-phone)\n→ nearest student\n→ instant alert", { fill: "#FFF2CC", stroke: "#BF9000", size: 11.5 });
  b += `<path d="M${cx + bw / 2},212 h${20}" fill="none" stroke="${C.line}" stroke-width="1.3" marker-end="url(#arrow)"/>`;
  render("fig_video", w, h, svgDoc(w, h, b, "Figure 3.2  Real-time video detection pipeline"));
})();

// =====================================================================
// 9. AUDIO PIPELINE (3-thread)
// =====================================================================
(function () {
  const w = 940, h = 470;
  let b = "";
  function lane(y, title) {
    b += `<rect x="30" y="${y}" width="880" height="120" rx="6" fill="#F7FAFF" stroke="${C.grey}" stroke-width="1" stroke-dasharray="6 4"/>`;
    b += lbl(44, y + 20, title, { size: 12.5, bold: true, anchor: "start", color: C.stroke });
  }
  lane(30, "Main thread");
  b += box(70, 60, 180, 56, "Read 500 ms\nmulti-mic chunks", { size: 12 });
  b += box(300, 60, 220, 56, "Global/Local discriminator\n(calibrated energy ratio)", { fill: C.accFill, stroke: C.accStroke, size: 12 });
  b += box(580, 60, 150, 56, "LOCAL?\nroute onward", { fill: "#FFF2CC", stroke: "#BF9000", size: 12 });
  b += line(250, 88, 300, 88); b += line(520, 88, 580, 88);
  lane(170, "VAD worker");
  b += box(300, 198, 220, 56, "Silero VAD\nconfirm human speech", { fill: C.accFill, stroke: C.accStroke, size: 12 });
  b += line(655, 116, 520, 198) + lbl(620, 165, "local chunk", { size: 11, anchor: "start" });
  lane(310, "Whisper worker");
  b += box(300, 338, 220, 56, "Faster-Whisper STT\n+ keyword match", { fill: C.accFill, stroke: C.accStroke, size: 12 });
  b += box(580, 338, 300, 56, "Evidence: WAV + JSON (transcript,\nratios, SHA-256)  →  Audio Alert", { fill: C.grnFill, stroke: C.grnStroke, size: 11.5 });
  b += line(410, 254, 410, 338) + lbl(470, 300, "speech buffer", { size: 11, anchor: "start" });
  b += line(520, 366, 580, 366);
  b += lbl(700, 230, "STRICT mode: any confirmed speech = violation", { size: 11, color: C.grey });
  render("fig_audio", w, h, svgDoc(w, h, b, "Figure 3.4  Three-stage audio detection pipeline"));
})();

// =====================================================================
// 10. ERD
// =====================================================================
(function () {
  const w = 1000, h = 640;
  let b = "";
  function ent(x, y, name, rows) {
    const wd = 200, rh = 18, hh = 26 + rows.length * rh;
    let s = `<rect x="${x}" y="${y}" width="${wd}" height="${hh}" fill="#fff" stroke="${C.stroke}" stroke-width="1.5"/>`;
    s += `<rect x="${x}" y="${y}" width="${wd}" height="24" fill="${C.stroke}"/>`;
    s += lbl(x + wd / 2, y + 16, name, { size: 13, bold: true, color: "#fff" });
    rows.forEach((r, i) => { s += `<text x="${x + 8}" y="${y + 40 + i * rh}" font-family="${FF}" font-size="11" fill="${C.text}">${esc(r)}</text>`; });
    return { svg: s, x, y, w: wd, h: hh };
  }
  const inst = ent(40, 40, "institutions", ["PK id", "name, code", "type, parent_id"]);
  const user = ent(40, 240, "users", ["PK id", "FK institution_id", "username, role"]);
  const hall = ent(40, 440, "halls", ["PK id", "FK institution_id", "capacity, status"]);
  const dev = ent(330, 440, "devices", ["PK id", "FK hall_id", "type, stream_url"]);
  const exam = ent(360, 60, "exam_sessions", ["PK id", "FK institution_id", "status, times"]);
  const esh = ent(360, 250, "exam_session_halls", ["FK exam_session_id", "FK hall_id"]);
  const assign = ent(660, 250, "assignments", ["PK id", "FK exam_session_id", "FK invigilator_id", "FK hall_id"]);
  const det = ent(680, 40, "detection_events", ["PK id", "FK exam_session_id", "FK device_id", "FK group_id"]);
  const grp = ent(680, 450, "group_events", ["PK id", "FK exam_session_id", "severity"]);
  const alert = ent(360, 470, "alerts", ["PK id", "FK exam_session_id", "FK detection_event_id", "FK group_event_id"]);
  [inst, user, hall, dev, exam, esh, assign, det, grp, alert].forEach((e) => (b += e.svg));
  const rel = (x1, y1, x2, y2, t) => line(x1, y1, x2, y2, { arrow: false, color: C.line }) + (t ? lbl((x1 + x2) / 2, (y1 + y2) / 2 - 4, t, { size: 10, color: C.grnStroke }) : "");
  b += rel(140, 124, 140, 240, "1:N");
  b += rel(140, 304, 140, 440, "1:N");
  b += rel(240, 470, 330, 470, "1:N");
  b += rel(460, 124, 460, 250, "M:N");
  b += rel(560, 270, 660, 290, "1:N");
  b += rel(560, 90, 680, 90, "1:N");
  b += rel(660, 300, 240, 480, "");
  b += rel(560, 490, 680, 480, "1:N");
  b += rel(680, 480, 560, 500, "");
  render("fig_erd", w, h, svgDoc(w, h, b, "Figure 3.5  Entity-Relationship diagram"));
})();

// =====================================================================
// 11. GAZE GEOMETRY
// =====================================================================
(function () {
  const w = 820, h = 460;
  let b = "";
  // student head
  const hx = 180, hy = 230;
  b += `<circle cx="${hx}" cy="${hy}" r="34" fill="${C.fill}" stroke="${C.stroke}" stroke-width="2"/>`;
  b += `<circle cx="${hx + 14}" cy="${hy - 6}" r="5" fill="${C.stroke}"/>`;
  b += lbl(hx, hy + 56, "Monitored student", { size: 12, bold: true, color: C.stroke });
  // own paper
  b += box(120, 330, 120, 46, "own paper", { fill: "#fff", stroke: C.grey, size: 11 });
  // neighbour paper
  const px = 600, py = 160;
  b += box(px, py, 130, 50, "neighbour's\npaper (target)", { fill: "#FFF2CC", stroke: "#BF9000", size: 11.5 });
  // gaze vector
  b += `<line x1="${hx + 20}" y1="${hy - 8}" x2="${px - 6}" y2="${py + 30}" stroke="${C.accStroke}" stroke-width="3" marker-end="url(#arrow)"/>`;
  b += lbl(400, 150, "gaze vector  ́g", { size: 13, bold: true, color: C.accStroke });
  // direction to paper (dashed)
  b += `<line x1="${hx + 20}" y1="${hy - 8}" x2="${px - 10}" y2="${py + 44}" stroke="${C.line}" stroke-width="1.5" stroke-dasharray="6 4"/>`;
  b += lbl(430, 250, "direction to paper  ́d", { size: 12, color: C.line });
  // tolerance cone
  b += `<path d="M${hx + 20},${hy - 8} L${px},${py + 10} L${px},${py + 70} z" fill="${C.accStroke}" fill-opacity="0.10" stroke="none"/>`;
  b += lbl(360, 205, "θ ≤ 25°", { size: 13, bold: true, color: C.accStroke });
  // rule
  b += `<rect x="120" y="400" width="600" height="40" rx="6" fill="#F7FAFF" stroke="${C.stroke}" stroke-width="1.2"/>`;
  b += lbl(420, 424, "Flag when  cos(∠(́g, ́d)) > cos(25°)  sustained ≥ 2.0 s", { size: 13, bold: true, color: C.stroke });
  render("fig_gaze", w, h, svgDoc(w, h, b, "Figure 3.6  Gaze-to-paper geometry and the risk-angle rule"));
})();

// =====================================================================
// 12. EXPERIMENTAL / DEPLOYMENT TOPOLOGY  (Docker-simulated hall)
// =====================================================================
(function () {
  const w = 940, h = 480;
  let b = "";
  const lx = 70, lw = 210, lcx = lx + lw / 2;
  // LEFT COLUMN: footage -> simulator -> [network band] -> engine
  b += box(lx, 36, lw, 56, "Real Damietta exam footage\n(cam1.mp4, cam2.mp4 …)", { fill: "#fff", stroke: C.grey, size: 12 });
  b += line(lcx, 92, lcx, 126, { color: C.line });
  b += box(lx, 126, lw, 80, "Camera Simulator\n(Docker container)\nMJPEG streams @ :8000", { fill: C.accFill, stroke: C.accStroke, bold: true, size: 12.5 });
  // network band (left column only)
  b += `<rect x="${lx - 28}" y="240" width="${lw + 56}" height="60" rx="8" fill="#EAF1FB" stroke="${C.stroke}" stroke-width="1.5" stroke-dasharray="7 4"/>`;
  b += textLines(lcx, 270, "Docker bridge network\nsimulated Wi-Fi / LAN", { size: 12.5, bold: true, color: C.stroke });
  b += line(lcx, 206, lcx, 240, { color: C.line });
  b += line(lcx, 300, lcx, 336, { color: C.line });
  b += box(lx, 336, lw, 92, "Detection Engine (Python)\ncv2.VideoCapture → YOLO,\nBoT-SORT, MediaPipe, gaze …", { fill: C.accFill, stroke: C.accStroke, bold: true, size: 12 });
  // RIGHT COLUMN: backend -> dashboard -> invigilator
  const rx = 590, rw = 210, rcx = rx + rw / 2;
  b += box(rx, 60, rw, 70, "Backend API\n(FastAPI @ :8001)", { fill: C.fill, bold: true, size: 13 });
  b += box(rx, 196, rw, 66, "Control-room\ndashboard (:5173)", { fill: C.grnFill, stroke: C.grnStroke, size: 12.5 });
  b += box(rx, 330, rw, 66, "Invigilator hall view", { fill: C.grnFill, stroke: C.grnStroke, size: 12.5 });
  b += line(rcx, 130, rcx, 196, { color: C.line });
  b += line(rcx, 262, rcx, 330, { color: C.line });
  // engine -> backend (events)
  b += line(lx + lw, 360, rx, 110, { color: C.line });
  b += textLines(445, 232, "POST /api/events\n(+ evidence clips)", { size: 11.5, color: C.grey, lh: 15 });
  render("fig_setup", w, h, svgDoc(w, h, b));
})();

// =====================================================================
// 13. CONFUSION MATRIX  (alert-centric; numbers filled in from exam test)
// =====================================================================
(function () {
  // Edit CONF.data with your measured counts and re-run, or leave null for placeholders.
  const CONF = {
    rows: ["Gaze cheating", "Phone use", "Audio anomaly", "No cheating"],   // ACTUAL
    cols: ["Gaze", "Phone", "Audio", "No alert"],                            // PREDICTED (alert type)
    data: null, // e.g. [[18,0,0,2],[1,11,0,1],[0,0,9,1],[3,1,2,"–"]]
  };
  const w = 760, h = 560;
  let b = "";
  const x0 = 240, y0 = 110, cw = 110, ch = 70;
  const nC = CONF.cols.length, nR = CONF.rows.length;
  // axis titles
  b += lbl(x0 + (nC * cw) / 2, 40, "Predicted (alert type)", { size: 15, bold: true, color: C.stroke });
  b += `<text x="70" y="${y0 + (nR * ch) / 2}" font-family="${FF}" font-size="15" font-weight="700" fill="${C.stroke}" text-anchor="middle" transform="rotate(-90 70 ${y0 + (nR * ch) / 2})">Actual behaviour</text>`;
  // column headers
  CONF.cols.forEach((c, j) => { b += lbl(x0 + j * cw + cw / 2, y0 - 14, c, { size: 12.5, bold: true, color: C.text }); });
  // row headers + cells
  CONF.rows.forEach((r, i) => {
    b += lbl(x0 - 12, y0 + i * ch + ch / 2, r, { size: 12.5, bold: true, anchor: "end", color: C.text });
    CONF.cols.forEach((c, j) => {
      const correct = (i === j);
      const isMiss = (CONF.cols[j] === "No alert" && CONF.rows[i] !== "No cheating");
      const isFP = (CONF.rows[i] === "No cheating" && CONF.cols[j] !== "No alert");
      let fill = "#F4F7FC";
      if (correct && CONF.rows[i] !== "No cheating") fill = C.grnFill;
      else if (isMiss || isFP) fill = C.accFill;
      const val = CONF.data ? CONF.data[i][j] : "–";
      b += `<rect x="${x0 + j * cw}" y="${y0 + i * ch}" width="${cw}" height="${ch}" fill="${fill}" stroke="${C.stroke}" stroke-width="1.2"/>`;
      b += lbl(x0 + j * cw + cw / 2, y0 + i * ch + ch / 2, String(val), { size: 19, bold: true, color: C.text });
    });
  });
  // legend
  const ly = y0 + nR * ch + 36;
  const leg = [[C.grnFill, "Correct detection (TP)"], [C.accFill, "False alarm / missed (FP / FN)"]];
  let lx = x0;
  leg.forEach((g) => {
    b += `<rect x="${lx}" y="${ly}" width="22" height="16" fill="${g[0]}" stroke="${C.stroke}" stroke-width="1"/>`;
    b += lbl(lx + 30, ly + 13, g[1], { size: 12, anchor: "start", color: C.text });
    lx += 250;
  });
  if (!CONF.data) b += lbl(w / 2, ly + 56, "Cells show – ; replace with measured counts from the exam-test log.", { size: 12, color: C.grey });
  render("fig_confusion", w, h, svgDoc(w, h, b));
})();

fs.writeFileSync(path.join(FIG_DIR, "manifest.json"), JSON.stringify(manifest, null, 2));
console.log("Generated", Object.keys(manifest).length, "diagrams:", Object.keys(manifest).join(", "));
