// Thai defence deck (red / white).  Numbers come from scripts/deck_th_numbers.py; the charts are drawn as native shapes (no pictures), so they stay editable.
// Needs pptxgenjs (npm i pptxgenjs in a scratch folder, then NODE_PATH=<that folder>/node_modules).
// Run:  python scripts/deck_th_numbers.py && node docs/presentation/build_deck_th.js [--plain]
//   --plain = no decoration: no shapes, fills, colours or charts, only black text and borderless tables in the same layout (defence_deck_th_plain.pptx).
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");

const PLAIN = process.argv.includes("--plain");
const ROOT = path.resolve(__dirname, "..", "..");
const D = JSON.parse(fs.readFileSync(path.join(ROOT, "output", "reports", "deck_th_numbers.json"), "utf8"));
const OUT = path.join(__dirname, PLAIN ? "defence_deck_th_plain.pptx" : "defence_deck_th_v1.pptx");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5 in
pres.title = "คลังข้อมูล ธุรกิจอัจฉริยะ และการวิเคราะห์ขั้นสูงของความรู้สึกของชุมชนเรดดิตต่อการเคลื่อนไหวของราคาหลักทรัพย์";
pres.author = "ฤทธิพงศ์ เหลืองหิรัญกุล";

const C = { red: "C8102E", dark: "2B2B2B", grey: "6B6B6B", mid: "B3B3B3", light: "F3F3F3", line: "DADADA", white: "FFFFFF", pale: "FBE8EB" };
const F = "Tahoma";
const n0 = (v) => Math.round(v).toLocaleString("en-US");
const p1 = (v) => v.toFixed(1);

// Plain mode: every slide loses its shapes, fills, outlines and colours; text and tables keep their position.
if (PLAIN) {
  const addSlide = pres.addSlide.bind(pres);
  const strip = (o = {}) => { const { fill, line, shape, rectRadius, highlight, ...rest } = o; return { ...rest, color: "000000" }; };
  pres.addSlide = (...args) => {
    const s = addSlide(...args);
    const addText = s.addText.bind(s), addTable = s.addTable.bind(s);
    s.addShape = () => s;
    s.addText = (t, o) => addText(Array.isArray(t) ? t.map((r) => ({ text: r.text, options: strip(r.options) })) : t, strip(o));
    s.addTable = (rows, o) => addTable(rows.map((r) => r.map((c) => ({ text: c.text, options: Object.assign(strip(c.options), { border: [{ type: "none" }, { type: "none" }, { type: "none" }, { type: "none" }] }) }))), o);
    Object.defineProperty(s, "background", { set() {}, get() { return { color: "FFFFFF" }; } });
    return s;
  };
}

// ---------- building blocks ----------
function chip(s, kind, x, y, w = 1.4) {
  const style = { Descriptive: { fill: C.dark, line: C.dark, color: C.white }, Diagnostic: { fill: C.white, line: C.red, color: C.red },
                  Predictive: { fill: C.red, line: C.red, color: C.white } }[kind];
  s.addText(kind, { x, y, w, h: 0.3, fontFace: F, fontSize: 11, bold: true, align: "center", valign: "middle", color: style.color, margin: 0,
                    fill: { color: style.fill }, line: { color: style.line, width: 1 }, rectRadius: 0.15, shape: pres.ShapeType.roundRect });
}

function base(title, tag, chips) {
  const s = pres.addSlide();
  s.background = { color: C.white };
  s.addShape(pres.ShapeType.rect, { x: 0.6, y: 0.38, w: 0.7, h: 0.07, fill: { color: C.red }, line: { color: C.red, width: 0 } });
  if (tag) s.addText(tag, { x: 0.6, y: 0.5, w: 8, h: 0.3, fontFace: F, fontSize: 13, bold: true, color: C.red, margin: 0 });
  s.addText(title, { x: 0.6, y: 0.82, w: chips ? 9.3 : 12.1, h: 0.7, fontFace: F, fontSize: 26, bold: true, color: C.dark, margin: 0, valign: "top" });
  if (chips) chips.forEach((k, i) => chip(s, k, 13.33 - 0.6 - 1.4 - i * 1.5, 0.55));
  if (!PLAIN) s.addText("Reddit Sentiment × Securities Price Movement", { x: 0.6, y: 7.08, w: 6, h: 0.25, fontFace: F, fontSize: 10, color: C.mid, margin: 0 });
  s.slideNumber = { x: 12.3, y: 7.05, w: 0.43, h: 0.25, fontFace: F, fontSize: 10, color: C.mid, align: "right" };
  return s;
}

function text(s, t, x, y, w, h, o = {}) {
  s.addText(t, Object.assign({ x, y, w, h, fontFace: F, fontSize: 15, color: C.dark, margin: 0, valign: "top" }, o));
}

function bullets(s, items, x, y, w, h, o = {}) {
  const runs = items.map((t, i) => ({ text: t, options: { bullet: { indent: 16 }, breakLine: i < items.length - 1, paraSpaceAfter: o.gap === undefined ? 8 : o.gap } }));
  text(s, runs, x, y, w, h, Object.assign({ fontSize: 15 }, o));
}

function table(s, head, body, x, y, colW, o = {}) {
  const size = o.fontSize || 13;
  const hdr = head.map((t, i) => ({ text: t, options: { bold: true, color: C.white, fill: { color: C.red }, fontFace: F, fontSize: size, valign: "middle", align: (o.align || [])[i] || "left" } }));
  const rows = body.map((r, ri) => r.map((c, i) => {
    const cell = typeof c === "object" && c !== null && !Array.isArray(c) ? c : { text: String(c) };
    const opt = Object.assign({ fontFace: F, fontSize: size, color: C.dark, valign: "middle", align: (o.align || [])[i] || "left",
                                border: [{ type: "none" }, { type: "none" }, { type: "solid", pt: 0.75, color: C.line }, { type: "none" }] }, cell.options || {});
    return { text: cell.text, options: opt };
  }));
  s.addTable([hdr, ...rows], { x, y, w: colW.reduce((a, b) => a + b, 0), colW, rowH: o.rowH || 0.42, margin: [0.04, 0.1, 0.04, 0.1] });
}

function stat(s, value, label, x, y, w, o = {}) {
  text(s, value, x, y, w, 0.75, { fontSize: o.size || 36, bold: true, color: o.color || C.red });
  text(s, label, x, y + (o.gap || 0.75), w, 0.6, { fontSize: o.labelSize || 13, color: C.grey });
}

function formula(s, t, x, y, w, h, o = {}) {
  s.addShape(pres.ShapeType.rect, { x, y, w: 0.06, h, fill: { color: C.red }, line: { color: C.red, width: 0 } });
  s.addText(t, Object.assign({ x: x + 0.06, y, w: w - 0.06, h, fontFace: F, fontSize: 14, color: C.dark, fill: { color: C.light }, margin: [5, 12, 5, 12], valign: "middle" }, o));
}

// Charts as shapes: they print the same in PowerPoint and Keynote and the user can edit them.
function legend(s, items, x, y, step = 1.7) {
  items.forEach(([label, color], i) => {
    s.addShape(pres.ShapeType.rect, { x: x + i * step, y: y + 0.07, w: 0.16, h: 0.16, fill: { color }, line: { color, width: 0 } });
    text(s, label, x + i * step + 0.24, y, step - 0.3, 0.3, { fontSize: 12, color: C.grey, valign: "middle" });
  });
}

function hbars(s, items, x, y, w, rowH, o = {}) {
  const labelW = o.labelW || 2.5, valueW = o.valueW || 1.4, barW = w - labelW - valueW, max = o.max || Math.max(...items.map((i) => i.value));
  items.forEach((it, i) => {
    const yy = y + i * rowH, len = Math.max(0.03, barW * it.value / max), color = it.color || C.mid;
    text(s, it.label, x, yy, labelW - 0.12, rowH, { fontSize: o.fontSize || 13, align: "right", valign: "middle" });
    s.addShape(pres.ShapeType.rect, { x: x + labelW, y: yy + rowH * 0.17, w: len, h: rowH * 0.66, fill: { color }, line: { color, width: 0 } });
    text(s, it.text, PLAIN ? x + labelW + 0.1 : x + labelW + len + 0.1, yy, valueW, rowH, { fontSize: o.fontSize || 13, bold: !!it.bold, valign: "middle" });
  });
}

// 100% stacked rows: rows = [{label, parts: [{value, color, dark}]}]
function stack(s, rows, x, y, w, rowH, o = {}) {
  const labelW = o.labelW || 2.2, barW = w - labelW;
  rows.forEach((r, i) => {
    const yy = y + i * rowH;
    let cx = x + labelW;
    text(s, r.label, x, yy, labelW - 0.12, rowH, { fontSize: 13, align: "right", valign: "middle", bold: !!r.bold });
    r.parts.forEach((p) => {
      const pw = barW * p.value / 100;
      s.addShape(pres.ShapeType.rect, { x: cx, y: yy + rowH * 0.14, w: pw, h: rowH * 0.72, fill: { color: p.color }, line: { color: C.white, width: 1 } });
      text(s, p1(p.value), cx, yy + rowH * 0.14, pw, rowH * 0.72, { fontSize: 13, align: "center", valign: "middle", color: p.dark ? C.dark : C.white, bold: true });
      cx += pw;
    });
  });
}

// Vertical (grouped) bars: groups = [{label, bars: [{value, color, text}]}]; o.max = top of the scale, o.ref = value of the dashed line, o.top = room for a legend.
function vbars(s, groups, x, y, w, h, o = {}) {
  const catH = 0.45, top = o.top || 0.4, base = y + h - catH, plotH = h - catH - top, gw = w / groups.length, nb = groups[0].bars.length, bw = Math.min(0.95, gw * 0.8 / nb);
  s.addShape(pres.ShapeType.line, { x, y: base, w, h: 0, line: { color: C.mid, width: 1 } });
  if (o.ref !== undefined) s.addShape(pres.ShapeType.line, { x, y: base - plotH * o.ref / o.max, w, h: 0, line: { color: C.dark, width: 1.25, dashType: "dash" } });
  groups.forEach((g, gi) => {
    const gx = x + gi * gw + (gw - nb * bw) / 2;
    g.bars.forEach((b, bi) => {
      const bh = Math.max(0.02, plotH * b.value / o.max), bx = gx + bi * bw;
      s.addShape(pres.ShapeType.rect, { x: bx + 0.03, y: base - bh, w: bw - 0.06, h: bh, fill: { color: b.color }, line: { color: b.color, width: 0 } });
      s.addText(b.text, { x: bx + 0.03, y: base - bh - 0.3, w: bw - 0.06, h: 0.27, fontFace: F, fontSize: o.fontSize || 13, bold: true, color: C.dark, align: "center", valign: "middle", margin: 0,
                          fill: { color: C.white } });
    });
    text(s, g.label, x + gi * gw, base + 0.07, gw, catH - 0.07, { fontSize: 13, align: "center" });
  });
}

function steps(s, labels, notes, y) {
  const w = 12.1 / labels.length;
  labels.forEach((l, i) => {
    s.addText(l, { x: 0.6 + i * w, y, w: w + (i < labels.length - 1 ? 0.12 : 0), h: 0.62, fontFace: F, fontSize: 13, bold: true, color: i === labels.length - 1 ? C.white : C.dark,
                   align: "center", valign: "middle", margin: [0, 0.2, 0, 0.2], shape: i === 0 ? pres.ShapeType.homePlate : pres.ShapeType.chevron,
                   fill: { color: i === labels.length - 1 ? C.red : C.light }, line: { color: C.white, width: 1.5 } });
    if (notes[i]) text(s, notes[i], 0.6 + i * w + 0.1, y + 0.72, w - 0.2, 1.0, { fontSize: 12, color: C.grey });
  });
}

// ---------- 1 cover ----------
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  s.addShape(pres.ShapeType.rect, { x: 0, y: 0, w: 4.4, h: 7.5, fill: { color: C.red }, line: { color: C.red, width: 0 } });
  text(s, "โครงการพิเศษ", 0.6, 0.7, 3.4, 0.4, { fontSize: 16, color: C.white, bold: true });
  text(s, "หลักสูตรวิทยาศาสตรมหาบัณฑิต\nสาขาวิชาเทคโนโลยีสารสนเทศทางธุรกิจ", 0.6, 1.15, 3.4, 0.8, { fontSize: 13, color: C.white });
  text(s, "คณะพาณิชยศาสตร์และการบัญชี\nจุฬาลงกรณ์มหาวิทยาลัย", 0.6, 6.3, 3.4, 0.7, { fontSize: 13, color: C.white });
  text(s, "คลังข้อมูล ธุรกิจอัจฉริยะ และการวิเคราะห์ขั้นสูงของความรู้สึกของชุมชนเรดดิตต่อการเคลื่อนไหวของราคาหลักทรัพย์", 5.0, 1.5, 7.7, 2.3,
       { fontSize: 29, bold: true, valign: "top" });
  s.addShape(pres.ShapeType.rect, { x: 5.0, y: 3.95, w: 0.9, h: 0.07, fill: { color: C.red }, line: { color: C.red, width: 0 } });
  text(s, "Data Warehouse, Business Intelligence and Advanced Data Analytics of Reddit Sentiment and Securities Price Movement", 5.0, 4.2, 7.7, 0.9,
       { fontSize: 15, color: C.grey });
  text(s, [{ text: "นายฤทธิพงศ์ เหลืองหิรัญกุล", options: { bold: true, breakLine: true } }, { text: "รหัสนิสิต 6782094726", options: { breakLine: true } },
           { text: "อาจารย์ที่ปรึกษา ผู้ช่วยศาสตราจารย์ ดร.สุรณพีร์ ภูมิวุฒิสาร" }], 5.0, 5.5, 7.7, 1.1, { fontSize: 15 });
}

// ---------- 2 pain point ----------
{
  const s = base("ปัญหา: ข้อมูลการเงินดูง่าย แต่กระแสบนโซเชียลดูยาก", "ที่มาของโครงการ");
  const days = Math.round((new Date("2026-09-01") - new Date("2024-10-01")) / 86400000);
  text(s, "ที่นักวิเคราะห์ดูได้อยู่แล้ว", 0.6, 1.85, 5.6, 0.35, { fontSize: 14, color: C.grey, bold: true });
  ["ราคา", "ปริมาณซื้อขาย", "ตัวชี้วัดทางเทคนิค"].forEach((t, i) => {
    text(s, t, 0.6, 2.35 + i * 0.7, 5.6, 0.5, { fontSize: 22, bold: true });
    s.addShape(pres.ShapeType.line, { x: 0.6, y: 2.95 + i * 0.7, w: 5.6, h: 0, line: { color: C.line, width: 0.75 } });
  });
  text(s, "เป็นตัวเลข เรียงตามเวลา พร้อมนำไปวิเคราะห์", 0.6, 4.55, 5.6, 0.4, { fontSize: 14, color: C.grey });
  text(s, "ที่ดูได้ยาก", 7.0, 1.85, 5.7, 0.35, { fontSize: 14, color: C.red, bold: true });
  text(s, "ความรู้สึกของนักลงทุนบนโซเชียล", 7.0, 2.3, 5.7, 0.5, { fontSize: 22, bold: true });
  stat(s, "≈ " + n0(D.reddit.clean / days / 1000) + ",000", "ข้อความต่อวัน จาก Reddit 6 ชุมชนที่คุยเรื่องการลงทุน", 7.0, 3.0, 5.7, { size: 38, gap: 0.8 });
  bullets(s, ["อ่านเองไม่ทัน", "เป็นข้อความอิสระ ไม่ใช่ตัวเลข", "ไม่ผูกกับราคาตามเวลา"], 7.0, 4.65, 5.7, 1.2, { fontSize: 15, gap: 4 });
  s.addShape(pres.ShapeType.rect, { x: 0, y: 6.15, w: 13.33, h: 0.75, fill: { color: C.red }, line: { color: C.red, width: 0 } });
  text(s, "โครงการนี้แปลงข้อความเป็นตัวเลขรายชั่วโมง แล้ววางคู่กับราคาของ 34 สินทรัพย์", 0.6, 6.15, 12.1, 0.75, { fontSize: 18, color: C.white, bold: true, valign: "middle" });
}

// ---------- 3 users ----------
{
  const s = base("ผู้ใช้งาน: นักวิเคราะห์การลงทุน", "ใครใช้ระบบนี้");
  const cards = [["1", "วิเคราะห์ส่วนตัว", "ดูว่าชั่วโมงหรือวันไหน Reddit คุยผิดปกติ ความรู้สึกเอียงบวกหรือลบ แล้วเทียบกับราคา ก่อนสรุปมุมมองของตัวเอง"],
                 ["2", "แจ้งข้อมูลให้ลูกค้า", "ใช้กราฟและตัวเลขจากแดชบอร์ดอธิบายกระแสตลาด พร้อมบอกตรง ๆ ว่าความสัมพันธ์ที่เห็นเชื่อได้แค่ไหน"]];
  cards.forEach(([num, head, body], i) => {
    const x = 0.6 + i * 6.2;
    s.addShape(pres.ShapeType.rect, { x, y: 1.85, w: 5.9, h: 2.45, fill: { color: C.light }, line: { color: C.light, width: 0 } });
    s.addShape(pres.ShapeType.rect, { x, y: 1.85, w: 0.08, h: 2.45, fill: { color: C.red }, line: { color: C.red, width: 0 } });
    text(s, num, x + 0.35, 2.0, 0.7, 0.8, { fontSize: 40, bold: true, color: C.red });
    text(s, head, x + 1.1, 2.12, 4.6, 0.5, { fontSize: 21, bold: true });
    text(s, body, x + 1.1, 2.75, 4.6, 1.4, { fontSize: 15, color: C.grey });
  });
  text(s, "ตัวอย่างการใช้งานตอนเช้า", 0.6, 4.65, 6, 0.35, { fontSize: 14, bold: true, color: C.grey });
  const flow = [["Hot Events", "ดูชั่วโมงที่ได้ระดับสูง"], ["Market and Sentiment", "ดูว่าตลาดรู้สึกไปทางไหน"], ["Statistical Analysis", "เช็กว่าความสัมพันธ์เชื่อได้แค่ไหน"]];
  flow.forEach(([h, b], i) => {
    const x = 0.6 + i * 4.15;
    text(s, h, x, 5.1, 3.6, 0.4, { fontSize: 17, bold: true, color: C.red });
    text(s, b, x, 5.5, 3.6, 0.4, { fontSize: 14, color: C.grey });
    if (i < 2) s.addShape(pres.ShapeType.line, { x: x + 3.65, y: 5.3, w: 0.4, h: 0, line: { color: C.mid, width: 1.5, endArrowType: "triangle" } });
  });
  ["ข้อมูลย้อนหลัง", "ไม่ใช่ real-time", "ไม่ใช่คำแนะนำการลงทุน"].forEach((t, i) => {
    s.addText(t, { x: 0.6 + i * 2.55, y: 6.35, w: 2.4, h: 0.34, fontFace: F, fontSize: 12, color: C.grey, align: "center", valign: "middle", margin: 0, shape: pres.ShapeType.roundRect,
                   rectRadius: 0.17, line: { color: C.mid, width: 1 } });
  });
}

// ---------- 4 overview ----------
{
  const s = base("ภาพรวม 6 ระบบ", "สถาปัตยกรรม");
  const sys = [
    ["7.1", "ระบบคลังข้อมูลชุมชนนักลงทุนเรดดิต", "Reddit Investor Community Data Warehouse", ["Descriptive"]],
    ["7.2", "ระบบคลังข้อมูลราคาหลักทรัพย์", "Securities Price Data Warehouse", ["Descriptive"]],
    ["7.3", "ระบบวิเคราะห์ความรู้สึก", "Sentiment Analysis System", ["Descriptive"]],
    ["7.4", "ระบบวิเคราะห์ความสัมพันธ์", "Relationship Analysis System", ["Diagnostic", "Predictive"]],
    ["7.5", "ระบบวิเคราะห์การลงทุน", "Investment Analysis System", ["Descriptive", "Diagnostic"]],
    ["7.6", "ระบบตรวจจับสัญญาณเชิงข้อมูล", "Data-driven Signal Detection System", ["Diagnostic", "Predictive"]]];
  const pos = { "7.1": [0, 0], "7.3": [1, 0], "7.5": [2, 0], "7.2": [0, 1], "7.4": [1, 1], "7.6": [2, 1] };
  const X = [0.6, 4.8, 9.0], Y = [1.75, 4.2], BW = 3.73, BH = 2.15;
  sys.forEach(([id, th, en, kinds]) => {
    const [c, r] = pos[id];
    const x = X[c], y = Y[r];
    s.addShape(pres.ShapeType.rect, { x, y, w: BW, h: BH, fill: { color: C.white }, line: { color: C.line, width: 1 } });
    s.addShape(pres.ShapeType.rect, { x, y, w: BW, h: 0.07, fill: { color: C.red }, line: { color: C.red, width: 0 } });
    text(s, id, x + 0.2, y + 0.2, 1.2, 0.5, { fontSize: 26, bold: true, color: C.red });
    text(s, th, x + 0.2, y + 0.78, BW - 0.4, 0.5, { fontSize: 14, bold: true });
    text(s, en, x + 0.2, y + 1.3, BW - 0.4, 0.4, { fontSize: 10.5, color: C.grey });
    kinds.forEach((k, i) => chip(s, k, x + 0.2 + i * 1.5, y + BH - 0.45, 1.4));
  });
  const arrow = (x1, y1, x2, y2) => s.addShape(pres.ShapeType.line, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1), h: Math.abs(y2 - y1), flipV: y2 < y1,
                                                                    line: { color: C.grey, width: 1.75, endArrowType: "triangle" } });
  arrow(X[0] + BW, Y[0] + BH / 2, X[1], Y[0] + BH / 2); // 7.1 -> 7.3
  arrow(X[0] + BW, Y[1] + BH / 2, X[1], Y[1] + BH / 2); // 7.2 -> 7.4
  arrow(X[1] + BW / 2, Y[0] + BH, X[1] + BW / 2, Y[1]); // 7.3 -> 7.4
  arrow(X[1] + BW, Y[1] + BH / 2, X[2], Y[1] + BH / 2); // 7.4 -> 7.6
  arrow(X[2] + BW / 2, Y[1], X[2] + BW / 2, Y[0] + BH); // 7.6 -> 7.5
  arrow(X[1] + BW, Y[1] + 0.3, X[2], Y[0] + BH - 0.3); // 7.4 -> 7.5
  text(s, "Descriptive = เกิดอะไรขึ้น      Diagnostic = สัมพันธ์ / ผิดปกติไหม      Predictive = จะเกิดอะไรต่อ", 0.6, 6.6, 12.1, 0.35, { fontSize: 12, color: C.grey });
}

// ---------- 5 system 7.1: what ----------
{
  const s = base("Reddit คืออะไร และเอาข้อมูลมาจากไหน", "ระบบ 7.1  ระบบคลังข้อมูลชุมชนนักลงทุนเรดดิต", ["Descriptive"]);
  const blocks = [["Reddit", "เว็บชุมชนพูดคุย แบ่งเป็นห้องตามหัวข้อ เรียกว่า subreddit มีสองชนิดข้อความ คือโพสต์ (submission) และคอมเมนต์ (comment)"],
                  ["แหล่งข้อมูล", "Academic Torrents ไฟล์ดัมพ์รายเดือน (.zst) ของ Reddit ย้อนหลัง 23 เดือน ตั้งแต่ ต.ค. 2024 ถึง ส.ค. 2026 ไม่ได้เรียก API ตรง"],
                  ["ทำไมเลือก 6 ชุมชน", "เลือกห้องที่คุยเรื่องการลงทุนโดยตรง ครอบคลุมหุ้น ออปชัน และคริปโต อีก 3 ห้องที่ดาวน์โหลดมา (Bitcoin, Daytrading, dogecoin) ไม่นำมาใช้"]];
  blocks.forEach(([h, b], i) => {
    const y = 1.85 + i * 1.65;
    text(s, h, 0.6, y, 4.6, 0.35, { fontSize: 16, bold: true, color: C.red });
    text(s, b, 0.6, y + 0.4, 4.6, 1.2, { fontSize: 13, color: C.dark });
  });
  const about = { "r/wallstreetbets": "รายย่อยสายเสี่ยง หุ้นมีม", "r/stocks": "คุยหุ้นทั่วไป", "r/CryptoCurrency": "คริปโตเคอร์เรนซี", "r/StockMarket": "ข่าวและภาพรวมตลาดหุ้น",
                  "r/investing": "ลงทุนระยะยาว", "r/options": "ซื้อขายออปชัน" };
  table(s, ["ชุมชน", "เนื้อหา", "ข้อความ", "สัดส่วน"], D.reddit.communities.map((c, i) => [{ text: c.name, options: { bold: i === 0 } }, about[c.name], n0(c.texts),
        { text: p1(c.share) + "%", options: { bold: i === 0, color: i === 0 ? C.red : C.dark } }]), 5.7, 1.85, [2.2, 2.5, 1.35, 0.95], { fontSize: 13, align: ["left", "left", "right", "right"], rowH: 0.5 });
  text(s, "ข้อความหลังคัดกรองรวม " + n0(D.reddit.clean) + " ข้อความ wallstreetbets ครองเกือบสามในสี่ ภาพ \"ความรู้สึกตลาด\" จึงเป็นเสียงของห้องนี้เป็นหลัก", 5.7, 5.7, 7.0, 0.8,
       { fontSize: 13, color: C.grey });
}

// ---------- 6 system 7.1: ETL ----------
{
  const s = base("ETL ข้อมูล Reddit: จากไฟล์ดัมพ์ถึงข้อความที่ใช้วิเคราะห์", "ระบบ 7.1  ระบบคลังข้อมูลชุมชนนักลงทุนเรดดิต", ["Descriptive"]);
  steps(s, ["ไฟล์ดัมพ์ .zst", "นำเข้า SQLite", "ล้างข้อความ", "กรองคุณภาพ", "หา Ticker", "สรุปรายชั่วโมง"],
        ["Academic Torrents 23 ไฟล์", "9 ชุมชน " + n0(D.reddit.raw_all) + " แถว เลือก 6 ชุมชน", "ลบ URL markdown @mention แปลงอีโมจิเป็นคำ คอมเมนต์ = หัวข้อโพสต์แม่ + เนื้อคอมเมนต์",
         "ตัดบอท / ผู้ดูแล, ข้อความสั้นกว่า 2 ตัวอักษร, ไม่ใช่ภาษาอังกฤษ", "จับคู่พจนานุกรม 34 สินทรัพย์ (ชื่อ, ตัวย่อ, $cashtag)", "นับข้อความต่อชั่วโมง × สินทรัพย์ × ชุมชน"], 1.75);
  const funnel = [["ข้อมูลดิบ 6 ชุมชน", D.reddit.raw6], ["ตัดข้อความที่ถูกลบ / นำออก", D.reddit.raw6 - D.reddit.removed], ["ล้างข้อความแล้ว", D.reddit.processed],
                  ["ผ่านตัวกรองคุณภาพ", D.reddit.clean]];
  hbars(s, funnel.map(([label, v], i) => ({ label, value: v, text: n0(v), color: i === 3 ? C.red : C.mid, bold: i === 3 })), 0.6, 4.1, 7.4, 0.7, { labelW: 2.9, valueW: 1.6, fontSize: 12 });
  stat(s, p1(D.reddit.kept_pct) + "%", "ของข้อมูลดิบ 6 ชุมชน เหลือเป็นข้อความที่ใช้ได้", 8.4, 4.15, 4.3, { size: 40, gap: 0.8 });
  text(s, [{ text: "ตัดออกที่ขั้นกรองคุณภาพ", options: { bold: true, breakLine: true } }, { text: "บอท / ผู้ดูแล " + n0(D.reddit.bot), options: { breakLine: true } },
           { text: "สั้นกว่า 2 ตัวอักษร " + n0(D.reddit.short), options: { breakLine: true } }, { text: "ไม่ใช่ภาษาอังกฤษ " + n0(D.reddit.non_english) }], 8.4, 5.5, 4.3, 1.3,
       { fontSize: 13, color: C.grey });
}

// ---------- 7 system 7.1: KPI ----------
{
  const s = base("ตัวชี้วัดของข้อมูล Reddit", "ระบบ 7.1  ระบบคลังข้อมูลชุมชนนักลงทุนเรดดิต", ["Descriptive"]);
  table(s, ["ตัวชี้วัด", "ความหมาย", "สูตร"], [
    [{ text: "Reddit Volume", options: { bold: true } }, "จำนวนโพสต์ + คอมเมนต์ทั้งตลาดในชั่วโมงนั้น (หลังคัดกรอง)", "V(t) = จำนวนข้อความในชั่วโมง t"],
    [{ text: "Reddit Volume Z-score", options: { bold: true } }, "ชั่วโมงนี้คุยมากผิดปกติแค่ไหน เทียบ 24 ชั่วโมงก่อนหน้า (ไม่รวมชั่วโมงปัจจุบัน)", "Z(t) = ( V(t) − μ ) / σ     μ, σ = ค่าเฉลี่ยและส่วนเบี่ยงเบนมาตรฐาน 24 ชม.ก่อนหน้า"],
    [{ text: "Ticker Mention Count", options: { bold: true } }, "จำนวนข้อความที่พูดถึงสินทรัพย์นั้นในชั่วโมงนั้น", "นับข้อความที่ตรงพจนานุกรม ticker"],
    [{ text: "Ticker Mention Rate (%)", options: { bold: true } }, "สัดส่วนการพูดถึงสินทรัพย์ เทียบกับทั้งตลาด", "Mention Count / Reddit Volume × 100"]],
    0.6, 1.8, [2.7, 4.6, 4.8], { fontSize: 13, rowH: 0.85 });
  const top = D.reddit.top_mentions.slice().sort((a, b) => b.mentions - a.mentions);
  text(s, "พบ Ticker ใน " + n0(D.reddit.texts_with_ticker) + " ข้อความ (" + p1(100 * D.reddit.texts_with_ticker / D.reddit.clean) + "%)  ถูกพูดถึงมากสุด", 0.6, 5.55, 12.1, 0.35, { fontSize: 14, bold: true });
  top.forEach((t, i) => {
    const x = 0.6 + i * 2.45;
    text(s, t.ticker, x, 5.95, 2.3, 0.4, { fontSize: 18, bold: true, color: C.red });
    text(s, n0(t.mentions) + " ครั้ง", x, 6.35, 2.3, 0.3, { fontSize: 13, color: C.grey });
  });
}

// ---------- 8 system 7.2: yfinance + ETL ----------
{
  const s = base("yfinance และ ETL ข้อมูลราคา", "ระบบ 7.2  ระบบคลังข้อมูลราคาหลักทรัพย์", ["Descriptive"]);
  text(s, "yfinance คืออะไร", 0.6, 1.8, 5.2, 0.35, { fontSize: 16, bold: true, color: C.red });
  text(s, "ไลบรารี Python ที่ดึงราคาจาก Yahoo Finance ใช้ Ticker(...).history(interval=\"60m\") ได้ราคาเปิด สูง ต่ำ ปิด และปริมาณซื้อขายรายชั่วโมง", 0.6, 2.2, 5.2, 1.1, { fontSize: 13 });
  text(s, "ดึงอย่างไร", 0.6, 3.4, 5.2, 0.35, { fontSize: 16, bold: true, color: C.red });
  bullets(s, ["ดึงทีละสินทรัพย์ ทีละวัน เก็บลงตาราง market_bars", "ตรวจกับเวลาเปิดตลาด: หุ้น 9:00–16:00 เวลานิวยอร์ก จันทร์–ศุกร์, คริปโต 24 ชม., ฟิวเจอร์สตามเวลาเปิดของตลาด", "ชั่วโมงที่ควรมีแต่ขาด บันทึกสถานะไว้ตรวจ"],
          0.6, 3.8, 5.2, 2.4, { fontSize: 13, gap: 5 });
  const g = D.market.groups, name = { stock_etf: "หุ้น / ETF", crypto: "คริปโต", futures: "ฟิวเจอร์ส" };
  const body = ["stock_etf", "crypto", "futures"].map((k) => [{ text: name[k], options: { bold: true } }, g[k].n, n0(g[k].raw), n0(g[k].clean), n0(g[k].raw - g[k].clean)]);
  body.push([{ text: "รวม", options: { bold: true, color: C.red } }, { text: "34", options: { bold: true, color: C.red } }, { text: n0(D.market.raw), options: { bold: true, color: C.red } },
             { text: n0(D.market.clean), options: { bold: true, color: C.red } }, { text: n0(D.market.raw - D.market.clean), options: { bold: true, color: C.red } }]);
  text(s, "ล้างข้อมูล: ตัดแท่งที่ราคาปิดว่าง", 6.4, 1.8, 6.3, 0.35, { fontSize: 16, bold: true, color: C.red });
  table(s, ["กลุ่ม", "สินทรัพย์", "แท่งดิบ", "เหลือ", "ตัดออก"], body, 6.4, 2.25, [1.6, 1.1, 1.3, 1.2, 1.1], { fontSize: 13, align: ["left", "right", "right", "right", "right"], rowH: 0.5 });
  text(s, "แท่งที่ราคาปิดว่างคือตัวแทน (placeholder) ตอนตลาดปิด ไม่ใช่ราคาจริง จึงตัดออก ฟิวเจอร์สถูกตัดมากสุดเพราะตลาดปิดช่วงสั้น ๆ ทุกวัน", 6.4, 5.0, 6.3, 0.9, { fontSize: 13, color: C.grey });
  text(s, "ช่วงข้อมูลรายชั่วโมง 2 ปี ตั้งแต่ ต.ค. 2024", 6.4, 5.95, 6.3, 0.3, { fontSize: 13, color: C.grey });
}

// ---------- 9 system 7.2: assets ----------
{
  const s = base("34 สินทรัพย์ แบ่งเป็น 3 กลุ่มใหญ่", "ระบบ 7.2  ระบบคลังข้อมูลราคาหลักทรัพย์", ["Descriptive"]);
  const A = D.market.assets;
  const pick = (grp, sub) => A.filter((a) => a.group === grp && (sub === undefined || a.sub === sub)).map((a) => a.ticker.replace("-USD", "").replace("=F", "")).join(" ");
  const keep = (k) => D.market.groups[k];
  const col = [
    { x: 0.6, head: "หุ้น / ETF", n: 22, kept: 100 * keep("stock_etf").clean / keep("stock_etf").raw, rows: [
      ["หุ้น 17", ""], ["เทคโนโลยี", pick("stock_etf", "tech")], ["มีม", pick("stock_etf", "meme")], ["การเงิน", pick("stock_etf", "finance")],
      ["เกี่ยวกับคริปโต", pick("stock_etf", "crypto_related")], ["ป้องกันความเสี่ยง", pick("stock_etf", "defensive")], ["ETF 5", ""],
      ["ดัชนี", pick("stock_etf", "index_etf")], ["Bitcoin ETF", pick("stock_etf", "bitcoin_etf")]] },
    { x: 5.0, head: "คริปโต", n: 6, kept: 100 * keep("crypto").clean / keep("crypto").raw, rows: [["", pick("crypto")]] },
    { x: 8.9, head: "ฟิวเจอร์ส", n: 6, kept: 100 * keep("futures").clean / keep("futures").raw, rows: [
      ["ดัชนี", "ES  NQ  RTY"], ["สินค้าโภคภัณฑ์", "CL  NG  GC"]] }];
  col.forEach((c) => {
    const w = c.x === 0.6 ? 4.1 : c.x === 5.0 ? 3.5 : 3.8;
    s.addShape(pres.ShapeType.rect, { x: c.x, y: 1.8, w, h: 0.08, fill: { color: C.red }, line: { color: C.red, width: 0 } });
    text(s, c.head, c.x, 1.98, w - 1.2, 0.5, { fontSize: 22, bold: true });
    text(s, String(c.n), c.x + w - 1.2, 1.95, 1.2, 0.55, { fontSize: 30, bold: true, color: C.red, align: "right" });
    text(s, "ใช้ได้ " + p1(c.kept) + "% ของแท่งที่ดึงมา", c.x, 2.55, w, 0.3, { fontSize: 12, color: C.grey });
    c.rows.forEach(([h, b], i) => {
      const y = 3.0 + i * 0.4;
      if (b === "" && h) { text(s, h, c.x, y + (i ? 0.08 : 0), w, 0.35, { fontSize: 13, bold: true, color: C.red }); return; }
      if (h) { text(s, h, c.x, y, 1.3, 0.35, { fontSize: 12, color: C.grey }); text(s, b, c.x + 1.3, y, w - 1.3, 0.35, { fontSize: 12 }); } else text(s, b, c.x, y, w, 1.2, { fontSize: 14 });
    });
  });
  text(s, "กลุ่มใหญ่ 3 กลุ่มเป็นไปตามข้อเสนอโครงการ ส่วนกลุ่มย่อยเป็นการจัดเพิ่มเพื่อดูความผันผวนแยกประเภท  ตารางจำนวนแท่งรายตัวอยู่ในภาคผนวก", 0.6, 6.55, 12.1, 0.4, { fontSize: 12, color: C.grey });
}

// ---------- 10 system 7.2: KPI ----------
{
  const s = base("ตัวชี้วัดของข้อมูลราคา", "ระบบ 7.2  ระบบคลังข้อมูลราคาหลักทรัพย์", ["Descriptive"]);
  table(s, ["ตัวชี้วัด", "ความหมาย", "สูตร"], [
    [{ text: "Current Return (%)", options: { bold: true } }, "ผลตอบแทนของชั่วโมงนั้น", "ln( close(t) / close(t−1) ) × 100"],
    [{ text: "Future Return h (%)", options: { bold: true } }, "ผลตอบแทนอีก h ชั่วโมงข้างหน้า (h = 1, 2, 3, 6, 12) ใช้เป็นตัวที่ถูกทำนาย ไม่ใช้เป็นตัวแปรต้น", "ln( close(t+h) / close(t) ) × 100"],
    [{ text: "RSI", options: { bold: true } }, "แรงซื้อเทียบแรงขาย 14 แท่ง (Wilder)", "RSI = 100 − 100 / (1 + RS)     RS = กำไรเฉลี่ย / ขาดทุนเฉลี่ย"],
    [{ text: "Normalized ATR (%)", options: { bold: true } }, "ราคาแกว่งกี่ % ต่อชั่วโมง", "ATR / close × 100     ATR = ค่าเฉลี่ย True Range 24 ชม."],
    [{ text: "Trading Volume Z-score", options: { bold: true } }, "ปริมาณซื้อขายผิดปกติแค่ไหน เทียบ 24 ชม.ก่อนหน้า", "( Vol(t) − μ ) / σ"]],
    0.6, 1.8, [2.7, 4.6, 4.8], { fontSize: 13, rowH: 0.72 });
  const cov = D.market.coverage, name = { stock_etf: "หุ้น / ETF", crypto: "คริปโต", futures: "ฟิวเจอร์ส" };
  text(s, "สัดส่วนแถวที่คำนวณ Future Return ได้", 0.6, 5.7, 5.5, 0.3, { fontSize: 13, bold: true });
  ["stock_etf", "crypto", "futures"].forEach((k, i) => {
    const x = 0.6 + i * 4.1;
    text(s, name[k], x, 6.05, 1.5, 0.3, { fontSize: 13, color: C.grey });
    text(s, "1h " + p1(cov[k].h1) + "%   6h " + p1(cov[k].h6) + "%   12h " + p1(cov[k].h12) + "%", x, 6.35, 4.0, 0.3, { fontSize: 13 });
  });
}

// ---------- 11 system 7.3: three methods ----------
{
  const s = base("วัดความรู้สึกด้วย 3 วิธี", "ระบบ 7.3  ระบบวิเคราะห์ความรู้สึก", ["Descriptive"]);
  const cols = [
    ["VADER", "Lexicon + กฎไวยากรณ์", [["เด่น", "เร็ว อ่านภาษาโซเชียลได้ เช่น ตัวพิมพ์ใหญ่ เครื่องหมาย ! คำปฏิเสธ (don't) และอีโมจิ"],
                                      ["Library", "NLTK  nltk.sentiment.vader"], ["ที่มา", "พจนานุกรมคำราว 7,500 คำ ที่คนให้คะแนนความรู้สึกจากข้อความโซเชียล ไม่ได้เทรนโมเดล"],
                                      ["จุดอ่อน", "ไม่รู้ศัพท์การเงิน เช่น puts, short"]]],
    ["FinBERT", "โมเดล BERT เฉพาะการเงิน", [["เด่น", "เข้าใจบริบทและภาษาการเงิน"], ["Library", "Hugging Face Transformers  โมเดล ProsusAI/finbert  score = P(positive) − P(negative)"],
                                          ["ที่มา", "BERT ที่เรียนข่าวการเงินของ Reuters เพิ่ม แล้วฝึกต่อกับ Financial PhraseBank (ประโยคข่าวการเงินที่ผู้เชี่ยวชาญติดป้าย)"],
                                          ["จุดอ่อน", "เรียนจากภาษาข่าว ไม่ใช่ภาษาเว็บบอร์ด และให้ neutral เยอะ"]]],
    ["กฎรวมผล", "ผู้พัฒนาออกแบบ", [["เด่น", "ตัดสินใจเมื่อสองโมเดลขัดกัน"], ["ใช้อะไร", "คะแนนจากสองโมเดล + คำสำคัญทางการเงิน เช่น bullish, buy calls, buy puts, go short"],
                                  ["ที่มา", "ตามขั้นตอนที่ 3 ของข้อเสนอ 7.3 ค่าเฉลี่ยเมื่อไปทางเดียวกัน และใช้คำสำคัญช่วยเมื่อขัดกัน"], ["เกณฑ์", "neutral เมื่อ |score| < 0.05"]]]];
  cols.forEach(([name, kind, rows], i) => {
    const x = 0.6 + i * 4.15, last = i === 2;
    s.addShape(pres.ShapeType.rect, { x, y: 1.8, w: 3.95, h: 0.95, fill: { color: last ? C.red : C.dark }, line: { color: last ? C.red : C.dark, width: 0 } });
    text(s, name, x + 0.2, 1.88, 3.5, 0.5, { fontSize: 22, bold: true, color: C.white });
    text(s, kind, x + 0.2, 2.35, 3.5, 0.3, { fontSize: 12, color: C.white });
    rows.forEach(([h, b], j) => {
      const yy = [2.95, 3.85, 4.55, 5.65][j];
      text(s, h, x, yy, 0.9, 0.3, { fontSize: 12, bold: true, color: C.red });
      text(s, b, x + 0.9, yy, 3.05, 1.0, { fontSize: 12 });
    });
  });
}

// ---------- 12 system 7.3: why the rule ----------
{
  const s = base("ทำไมต้องมีกฎรวมผล: สองโมเดลมองไม่ตรงกัน", "ระบบ 7.3  ระบบวิเคราะห์ความรู้สึก", ["Descriptive"]);
  const dist = D.sentiment.distribution, part = (m) => [{ value: dist[m].negative, color: C.dark }, { value: dist[m].neutral, color: C.mid, dark: true }, { value: dist[m].positive, color: C.red }];
  if (PLAIN) {
    table(s, ["% ของข้อความ", "Negative", "Neutral", "Positive"], [["VADER", "vader"], ["FinBERT", "finbert"], ["ผลสุดท้าย (กฎรวมผล)", "final"]].map(([label, m]) => [label, p1(dist[m].negative), p1(dist[m].neutral), p1(dist[m].positive)]),
          0.6, 1.9, [2.4, 1.1, 1.1, 1.1], { fontSize: 13, rowH: 0.5, align: ["left", "right", "right", "right"] });
  } else {
    legend(s, [["Negative", C.dark], ["Neutral", C.mid], ["Positive", C.red]], 2.8, 1.8, 1.3);
    stack(s, [{ label: "VADER", parts: part("vader") }, { label: "FinBERT", parts: part("finbert") }, { label: "ผลสุดท้าย (กฎรวมผล)", parts: part("final"), bold: true }], 0.6, 2.25, 6.0, 0.7,
          { labelW: 2.1 });
    text(s, "% ของข้อความ", 2.7, 4.3, 3.9, 0.3, { fontSize: 11, color: C.grey });
  }
  text(s, "ข้อความเดียวกัน " + n0(D.reddit.clean) + " ข้อความ VADER ให้ positive " + p1(D.sentiment.distribution.vader.positive) + "% แต่ FinBERT ให้เพียง "
        + p1(D.sentiment.distribution.finbert.positive) + "% และให้ neutral ถึง " + p1(D.sentiment.distribution.finbert.neutral) + "%", 0.6, 4.7, 6.0, 1.0, { fontSize: 14, color: C.grey });
  const c = D.sentiment.conflict;
  table(s, ["สองโมเดลตอบ", "สัดส่วน", "กฎตัดสิน"], [
    ["ทิศเดียวกัน", p1(c.same_direction) + "%", "เฉลี่ย ถ้าห่างกันเกิน 0.50 ใช้ค่าที่ใกล้ 0"],
    ["เป็นกลางทั้งคู่", p1(c.both_neutral) + "%", "neutral"],
    ["ขัดกันเล็กน้อย (กลาง 1 มีทิศ 1)", p1(c.small_conflict) + "%", "ใช้ตัวที่มีทิศ ถ้าคำสำคัญไม่ค้าน"],
    ["ขัดกันรุนแรง (บวก 1 ลบ 1)", p1(c.hard_conflict) + "%", "ใช้โมเดลที่ตรงกับคำสำคัญ ไม่มีคำสำคัญ = กำกวม (0)"]],
    6.9, 1.8, [2.2, 0.95, 2.65], { fontSize: 12, rowH: [0.45, 0.8, 0.8, 0.8, 0.8], align: ["left", "right", "left"] });
  text(s, "ผลสุดท้ายของกฎ: positive " + p1(D.sentiment.distribution.final.positive) + "%  neutral " + p1(D.sentiment.distribution.final.neutral) + "%  negative "
        + p1(D.sentiment.distribution.final.negative) + "%", 6.9, 5.7, 5.8, 0.5, { fontSize: 13, bold: true });
}

// ---------- 13 system 7.3: 400-sample test ----------
{
  const s = base("ทดสอบกฎด้วยป้ายจริง 400 คอมเมนต์", "ระบบ 7.3  ระบบวิเคราะห์ความรู้สึก", ["Descriptive"]);
  const L = D.sentiment.labels;
  const st = [["1", "สุ่ม 400 คอมเมนต์", "แบ่งตาม 7 สถานการณ์ของกฎ กลุ่มละ 50 (กลุ่มใหญ่สุด 100)"], ["2", "แบ่งสองชุด", "tune 200 ไว้ดูแนวโน้ม  test 200 ไว้ยืนยัน"],
              ["3", "ติดป้ายเอง", "ผู้พัฒนาติดป้ายแบบปิดตา ไม่เห็นคะแนนของโมเดล และไม่ใช้ AI ติดป้าย  positive " + L.positive + "  negative " + L.negative + "  neutral " + L.neutral],
              ["4", "วัดความแม่น", "เทียบ VADER, FinBERT และกฎรวมผล กับป้าย"]];
  st.forEach(([num, h, b], i) => {
    const y = 1.85 + i * 1.12;
    text(s, num, 0.6, y, 0.7, 0.8, { fontSize: 34, bold: true, color: C.red });
    text(s, h, 1.4, y + 0.02, 4.5, 0.4, { fontSize: 18, bold: true });
    text(s, b, 1.4, y + 0.45, 5.0, 0.7, { fontSize: 13, color: C.grey });
  });
  formula(s, "กติกาที่ตั้งก่อนดูผล: จะเปลี่ยนกฎก็ต่อเมื่อทางเลือกใหม่ชนะอย่างน้อย 5 จุดในชุด tune และชุด test ยืนยันทิศเดียวกัน (p < 0.05)", 7.0, 1.9, 5.7, 1.6, { fontSize: 14 });
  text(s, "ทำไมต้องตั้งก่อน", 7.0, 3.8, 5.7, 0.35, { fontSize: 15, bold: true, color: C.red });
  text(s, "ถ้าตั้งกติกาหลังดูผล จะเลือกวิธีที่ผลสวยโดยไม่รู้ตัว ส่วนการแบ่ง tune / test ก็กันไม่ให้ปรับกฎกับข้อมูลชุดเดียวกับที่ใช้วัดผล", 7.0, 4.2, 5.7, 1.3, { fontSize: 13, color: C.grey });
}

// ---------- 14 system 7.3: results ----------
{
  const s = base("ผลทดสอบ: ใช้กฎรวมผลต่อได้", "ระบบ 7.3  ระบบวิเคราะห์ความรู้สึก", ["Descriptive"]);
  const acc = D.sentiment.accuracy, tests = [["tune", "ชุด tune (200)"], ["test", "ชุด test (200)"], ["ทั้งหมด", "รวม 400"]];
  const method = [["vader", "VADER", C.mid], ["finbert", "FinBERT", C.dark], ["final", "กฎรวมผล", C.red]];
  if (PLAIN) {
    table(s, ["ความแม่น (%)", ...method.map(([, l]) => l)], tests.map(([k, label]) => [label, ...method.map(([m]) => p1(acc[k][m]))]), 0.6, 1.9, [2.4, 1.4, 1.4, 1.4],
          { fontSize: 13, rowH: 0.55, align: ["left", "right", "right", "right"] });
  } else {
    legend(s, method.map(([, l, c]) => [l, c]), 1.6, 1.75, 1.6);
    vbars(s, tests.map(([k, label]) => ({ label, bars: method.map(([m, , color]) => ({ value: acc[k][m], color, text: p1(acc[k][m]) })) })), 0.6, 1.75, 6.9, 3.55, { max: 60, ref: 100 / 3, fontSize: 11 });
  }
  const hk = D.sentiment.hard_keyword;
  const pts = [["ทุกวิธีสูงกว่าเดาสุ่ม", "แต่ความต่างระหว่างวิธีแยกจากความบังเอิญไม่ได้ ความแม่นรวมอยู่ราว 43–48%"],
               ["จุดที่กฎช่วยชัด", "เมื่อสองโมเดลขัดกันรุนแรงและมีคำสำคัญ กฎถูก " + Math.round(hk.final) + "% เทียบ VADER " + Math.round(hk.vader) + "% และ FinBERT " + Math.round(hk.finbert) + "%"],
               ["ผลสรุป", "ไม่มีทางเลือกใดผ่านเกณฑ์ที่ตั้งไว้ จึงคงกฎตามข้อเสนอ"]];
  pts.forEach(([h, b], i) => {
    const y = 1.85 + i * 1.45;
    text(s, h, 8.0, y, 4.7, 0.35, { fontSize: 16, bold: true, color: i === 2 ? C.red : C.dark });
    text(s, b, 8.0, y + 0.4, 4.7, 0.95, { fontSize: 13, color: C.grey });
  });
  text(s, "ความแม่น ~47% ไม่สูง และผู้ติดป้ายมีคนเดียว จึงเป็นข้อจำกัดข้อหนึ่งของงานนี้   " + (PLAIN ? "ค่าเดาสุ่ม = 33.3%" : "เส้นประในกราฟ = เดาสุ่ม 33.3%"), 0.6, 5.7, 12.1, 0.4, { fontSize: 13, color: C.grey });
}

// ---------- 15 system 7.4: measures ----------
{
  const s = base("วัดความสัมพันธ์ 4 แบบ", "ระบบ 7.4  ระบบวิเคราะห์ความสัมพันธ์", ["Diagnostic", "Predictive"]);
  table(s, ["วิธี", "วัดอะไร", "วัดทำไม", "สูตร"], [
    [{ text: "Spearman ρ", options: { bold: true } }, "ความสัมพันธ์ของอันดับความรู้สึกกับ Future Return", "ไม่ตั้งสมมติฐานเส้นตรง และทนค่าสุดโต่ง", "ρ = 1 − 6 Σd² / ( n (n² − 1) )     d = ผลต่างของอันดับ"],
    [{ text: "Pearson r", options: { bold: true } }, "ความสัมพันธ์เชิงเส้น", "ดูขนาดความสัมพันธ์ตามค่าจริง", "r = cov(x, y) / ( σx · σy )"],
    [{ text: "Win Rate", options: { bold: true } }, "ทิศความรู้สึกตรงกับทิศราคากี่ %", "ตอบตรง ๆ ว่าทายทิศถูกบ่อยแค่ไหน เทียบ 50% ด้วย Binomial test", "Win Rate = จำนวนชั่วโมงที่ sign(s) = sign(r) / จำนวนชั่วโมงที่ทิศไม่เป็น 0 × 100"],
    [{ text: "Logistic Regression", options: { bold: true, color: C.red } }, "ทายว่า Future Return > 0 หรือไม่ จากตัวแปร 13 ตัว (6 กลุ่ม)", "ดูว่าทำนายได้ดีกว่าสุ่มไหม ด้วย AUC (0.5 = สุ่ม)", "P(ขึ้น) = 1 / ( 1 + e^(−z) )     z = β0 + Σ βi xi"]],
    0.6, 1.8, [2.0, 3.2, 3.2, 3.7], { fontSize: 12, rowH: 0.95 });
  text(s, "ตัวแปรของ Logistic: ระดับความรู้สึก, ความรู้สึกชั่วโมงก่อนหน้า (1, 2, 3, 6, 12), การเปลี่ยนแปลง, Reddit Volume Z, สัดส่วนบวก/ลบ, ผลโหวตส่วนใหญ่",
       0.6, 5.85, 12.1, 0.5, { fontSize: 12, color: C.grey });
  text(s, "แบ่งข้อมูลตามเวลาแบบ TimeSeriesSplit 5 รอบ เว้นช่วง 12 ชั่วโมง ไม่สลับข้อมูล  ปรับค่า p หลายการทดสอบด้วย Benjamini–Hochberg", 0.6, 6.35, 12.1, 0.4, { fontSize: 12, color: C.grey });
}

// ---------- 16 system 7.4: panels ----------
{
  const s = base("Panel: ชุดข้อมูลที่ใช้วิเคราะห์", "ระบบ 7.4  ระบบวิเคราะห์ความสัมพันธ์", ["Diagnostic", "Predictive"]);
  const P = D.analysis.panels;
  const rows = [
    ["panel_global", "ความรู้สึกรวมของทั้งตลาดในชั่วโมงนั้น ทุกสินทรัพย์ใช้ค่าเดียวกัน", P.panel_global],
    ["panel_global_strong", "เฉพาะชั่วโมงที่ |ค่าเฉลี่ยความรู้สึก| ≥ 0.05", P.panel_global_strong],
    ["panel_global_quality", "เฉพาะชั่วโมงที่ |ค่าเฉลี่ยความรู้สึก| ≥ 0.30", P.panel_global_quality],
    ["panel_global_spike", "เฉพาะชั่วโมงที่ Reddit Volume Z > 1.5", P.panel_global_spike],
    ["panel_Ticker", "ความรู้สึกจากข้อความที่พูดถึงสินทรัพย์นั้นเท่านั้น", P.panel_Ticker],
    ["panel_Ticker_strong", "เฉพาะ |ค่าเฉลี่ย| ≥ 0.05", P.panel_Ticker_strong],
    ["panel_Ticker_quality", "เฉพาะ |ค่าเฉลี่ย| ≥ 0.30", P.panel_Ticker_quality],
    ["panel_Ticker_spike", "เฉพาะชั่วโมงที่ Reddit Volume Z > 1.5", P.panel_Ticker_spike],
    [{ text: "panel_baseline", options: { bold: true, color: C.red } }, "ชุดเดียวกับ panel_global แต่ทิศถูกสุ่ม ไว้เทียบว่าผลดีกว่าการสุ่มไหม", P.panel_baseline]];
  table(s, ["Panel", "เงื่อนไข", "แถว"], rows.map(([a, b, c]) => [typeof a === "string" ? { text: a, options: { bold: true } } : a, b, n0(c)]), 0.6, 1.8, [3.0, 7.0, 2.1],
        { fontSize: 13, rowH: 0.47, align: ["left", "left", "right"] });
  text(s, "Panel เหล่านี้คือค่า default ของการวิเคราะห์ในระบบ 7.4 และ 7.5   panel_global_quality มีเพียง " + n0(P.panel_global_quality) + " ชั่วโมง ใช้สรุปผลไม่ได้",
       0.6, 6.45, 12.1, 0.4, { fontSize: 12, color: C.grey });
}

// ---------- 17 system 7.4: results ----------
{
  const s = base("ผล: ไปพร้อมราคาเล็กน้อย แต่ทายล่วงหน้าไม่ดีกว่าสุ่ม", "ระบบ 7.4  ระบบวิเคราะห์ความสัมพันธ์", ["Diagnostic", "Predictive"]);
  const A = D.analysis;
  table(s, ["กรอบเวลา", "Logistic Regression", "Baseline สุ่ม", "ต่างกัน"], A.horizons.map((hz, i) => [hz === "log_return" ? "Current Return" : hz,
        { text: A.auc_global[i].toFixed(3), options: { bold: true, color: C.red } }, A.auc_baseline[i].toFixed(3), (A.auc_global[i] - A.auc_baseline[i] >= 0 ? "+" : "") + (A.auc_global[i] - A.auc_baseline[i]).toFixed(3)]),
        0.6, 1.8, [2.0, 2.1, 1.6, 1.3], { fontSize: 13, rowH: 0.43, align: ["left", "right", "right", "right"] });
  text(s, "AUC ของ Logistic Regression เทียบกับ Baseline สุ่ม (panel_global)", 0.6, 5.3, 7.0, 0.35, { fontSize: 12, color: C.grey });
  const items = [[A.auc_global[0].toFixed(3), "AUC กับ Current Return (Baseline " + A.auc_baseline[0].toFixed(3) + ") ความรู้สึกไปพร้อมราคาเล็กน้อย บอกไม่ได้ว่าอะไรเป็นเหตุ"],
                 [A.auc_global[1].toFixed(3) + " – " + A.auc_global[5].toFixed(3), "AUC กับ Future Return 1–12 ชม. เกือบเท่า Baseline (0.500)"],
                 [p1(Math.min(...A.win_global.slice(1))) + " – " + p1(Math.max(...A.win_global.slice(1))) + "%", "Win Rate ล่วงหน้า ใกล้ 50% ซึ่งเท่าการสุ่ม"]];
  items.forEach(([v, b], i) => stat(s, v, b, 8.2, 1.85 + i * 1.6, 4.5, { size: 30, gap: 0.62, labelSize: 13 }));
  text(s, "|Spearman ρ| ≤ " + Math.max(...A.spearman.map(Math.abs)).toFixed(2) + " ทุกกรอบเวลา", 0.6, 5.9, 7, 0.4, { fontSize: 13, color: C.grey });
}

// ---------- 18 system 7.5: dashboard ----------
{
  const s = base("Dashboard การลงทุน: รวมผลจาก 7.4 และ 7.6", "ระบบ 7.5  ระบบวิเคราะห์การลงทุน", ["Descriptive", "Diagnostic"]);
  table(s, ["หน้า", "ตอบคำถาม", "ตัวชี้วัดหลัก"], [
    ["Reddit Volume", "คุยมากผิดปกติตอนไหน", "Reddit Volume, Z-score"],
    ["Ticker Mentions", "คุยเรื่องสินทรัพย์ไหน", "Mention Count, Mention Rate = Count / Volume × 100"],
    ["Price and Return", "ราคา ผลตอบแทน ความผันผวนเป็นอย่างไร", "Current Return, Future Return, Normalized ATR, Trading Volume Z"],
    ["Price and Reddit", "ราคากับปริมาณการคุยขยับพร้อมกันไหม", "ราคาเทียบ Reddit Volume (สองแกน)"],
    ["Market and Sentiment", "ตลาดรู้สึกบวกหรือลบ เทียบราคา", "Sentiment Score = ค่าเฉลี่ย final_sentiment ของชั่วโมง, สัดส่วนบวก / ลบ"],
    [{ text: "Statistical Analysis", options: { bold: true, color: C.red } }, "ความสัมพันธ์เชื่อได้แค่ไหน (จาก 7.4)", "Win Rate, Spearman, Pearson, p-value คำนวณสดตามตัวกรอง เทียบ panel ได้"],
    [{ text: "Logistic Regression", options: { bold: true, color: C.red } }, "ทายดีกว่าสุ่มไหม (จาก 7.4)", "AUC, สัมประสิทธิ์ของตัวแปร"],
    [{ text: "Hot Events", options: { bold: true, color: C.red } }, "ชั่วโมงไหนควรดู (จาก 7.6)", "คะแนนและระดับ low / medium / high"]],
    0.6, 1.8, [2.5, 4.0, 5.6], { fontSize: 12.5, rowH: 0.55 });
  text(s, "ตัวกรองด้านข้างเรียงตามมิติ: เวลา › แหล่งข้อมูล (ชุมชน, โพสต์ / คอมเมนต์) › สินทรัพย์ (กลุ่ม › Ticker)", 0.6, 6.5, 12.1, 0.35, { fontSize: 12, color: C.grey });
}

// ---------- 19 system 7.6: concept ----------
{
  const s = base("Hot Events: วัดระดับ high / medium / low ด้วยจำนวน KPI ที่ผ่านเกณฑ์", "ระบบ 7.6  ระบบตรวจจับสัญญาณเชิงข้อมูล", ["Diagnostic", "Predictive"]);
  const H = D.hot;
  const side = { rz: "Reddit", mr: "Reddit", ss: "Reddit", tz: "ราคา", na: "ราคา", cr: "ราคา" };
  table(s, ["KPI (ผ่านเมื่อค่า >)", "เกณฑ์", "ฝั่ง"], H.kpis.map((k) => [k.label.replace(" >", ""), k.threshold.toFixed(2), side[k.key]]), 0.6, 1.8, [3.9, 1.1, 1.1],
        { fontSize: 13, rowH: 0.5, align: ["left", "right", "left"] });
  text(s, "เกณฑ์ของแต่ละตัว = ค่าที่มีเพียง " + Math.round(100 * H.top_share) + "% ของชั่วโมง × สินทรัพย์สูงกว่า เรียนจากช่วง ต.ค. 2024 – ก.ย. 2025 เท่านั้น", 0.6, 5.45, 6.1, 0.8, { fontSize: 12, color: C.grey });
  text(s, "คะแนน = ผ่านกี่ตัวจาก 6", 7.3, 1.8, 5.4, 0.4, { fontSize: 16, bold: true, color: C.red });
  [["low", H.cuts.low, C.mid, C.dark], ["medium", H.cuts.medium, "E06A7D", C.white], ["high", H.cuts.high, C.red, C.white]].forEach(([lv, cut, fill, col], i) => {
    const y = 2.4 + i * 1.05, off = PLAIN ? 0 : i * 0.5;
    s.addShape(pres.ShapeType.rect, { x: 7.3, y, w: 1.9 + i * 0.5, h: 0.8, fill: { color: fill }, line: { color: fill, width: 0 } });
    text(s, lv, 7.5, y, 1.7, 0.8, { fontSize: 20, bold: true, color: col, valign: "middle" });
    text(s, "ผ่านตั้งแต่ " + cut + " ตัว", 9.8 + off, y, 3.0 - off, 0.45, { fontSize: 15, bold: true });
    text(s, "ราว " + p1(H.share_reaching[cut]) + "% ของชั่วโมง × สินทรัพย์", 9.8 + off, y + 0.4, 3.0 - off, 0.4, { fontSize: 11, color: C.grey });
  });
  formula(s, "ระดับตั้งจากสัดส่วนแถวที่ผ่าน ไม่ได้ปรับตามผลราคา และใช้เฉพาะข้อมูลที่รู้ ณ ชั่วโมงนั้น ผู้ใช้ปรับเกณฑ์และระดับได้บนแดชบอร์ด", 7.3, 5.6, 5.4, 0.9, { fontSize: 12 });
}

// ---------- 20 system 7.6: result ----------
{
  const s = base("ผลย้อนหลัง: ระดับสูงขึ้น ราคาขยับแรงขึ้น", "ระบบ 7.6  ระบบตรวจจับสัญญาณเชิงข้อมูล", ["Diagnostic", "Predictive"]);
  const H = D.hot;
  const shade = [C.mid, "E06A7D", "D63B53", C.red], top = Math.ceil(Math.max(...H.ladder.map((l) => l.move)) * 2) / 2;
  if (PLAIN) {
    table(s, ["ระดับ", "ราคาขยับ (เท่าของปกติ)", "จำนวนแถว"], H.ladder.map((l) => [l.level, l.move.toFixed(2), n0(l.n)]), 0.6, 1.9, [2.0, 2.6, 1.6], { fontSize: 14, rowH: 0.6, align: ["left", "right", "right"] });
    text(s, "ราคาขยับเฉลี่ยในอีก 1 ชั่วโมง เทียบกับค่าปกติของสินทรัพย์นั้น (1 = เท่าปกติ)", 0.6, 5.6, 6.2, 0.5, { fontSize: 12 });
  } else {
  vbars(s, H.ladder.map((l, i) => ({ label: l.level, bars: [{ value: l.move, color: shade[i], text: l.move.toFixed(2) }] })), 0.6, 1.8, 6.2, 3.7, { max: top, ref: 1, fontSize: 15 });
  text(s, "ราคาขยับเฉลี่ยในอีก 1 ชั่วโมง เทียบกับค่าปกติของสินทรัพย์นั้น เส้นประ = 1 เท่าของปกติ (ข้อมูล " + n0(H.n) + " แถว)", 0.6, 5.6, 6.2, 0.5, { fontSize: 12, color: C.grey });
  }
  stat(s, p1(100 * H.auc_all) + "%", "AUC ของคะแนนต่อการขยับแรงใน 1 ชม. (50% = สุ่ม) ช่วงที่ไม่ได้ใช้เรียน " + p1(100 * H.auc_holdout) + "%", 7.4, 1.85, 5.3, { size: 34, gap: 0.65 });
  text(s, [{ text: "KPI ฝั่ง Reddit อย่างเดียว  " + p1(100 * H.auc_reddit) + "%", options: { breakLine: true } }, { text: "KPI ฝั่งราคาอย่างเดียว  " + p1(100 * H.auc_price) + "%" }], 7.4, 3.45, 5.3, 0.8,
       { fontSize: 15, bold: true });
  text(s, "ความสามารถส่วนใหญ่มาจากฝั่งราคา ส่วน Reddit เพิ่มได้เล็กน้อย", 7.4, 4.35, 5.3, 0.6, { fontSize: 13, color: C.grey });
  const hit = H.ladder.map((l) => l.hit);
  formula(s, "บอกได้ว่าชั่วโมงไหน \"ควรดู\" แต่บอกทิศไม่ได้ ทิศตรงความรู้สึกอยู่ที่ " + p1(Math.min(...hit)) + "–" + p1(Math.max(...hit)) + "% ทุกระดับ", 7.4, 5.2, 5.3, 0.95, { fontSize: 13 });
}

// ---------- 21 limitations ----------
{
  const s = base("ข้อจำกัด", "ปิดท้าย");
  const left = [["Reddit ต่อ API ตรงไม่ได้", "ใช้ไฟล์ดัมพ์รายเดือน จึงได้เฉพาะข้อมูลย้อนหลัง ข้อความที่ถูกลบก่อนเก็บดัมพ์หายไป (" + n0(D.reddit.removed) + " แถว)"],
                ["yfinance ย้อนหลังได้จำกัด", "รายชั่วโมงย้อนได้ราว 2 ปี (730 วัน) ความละเอียด 30 / 15 นาทีย้อนได้แค่ราว 60 วัน จึงทำรายครึ่งชั่วโมงหรือ 15 นาทีย้อนหลังไม่ได้"],
                ["เสียงของ wallstreetbets", "ครอง " + p1(D.reddit.communities[0].share) + "% ของข้อความ ภาพความรู้สึกรวมจึงเอนไปทางห้องนี้"],
                ["หุ้นสหรัฐเปิดไม่ครบวัน", "Future Return 12 ชม. คำนวณไม่ได้ (" + p1(D.market.coverage.stock_etf.h12) + "%) และ 6 ชม. ได้เพียง " + p1(D.market.coverage.stock_etf.h6) + "%"]];
  const right = [["Win Rate และ Spearman อาจเป็นเรื่องบังเอิญ", "ทดสอบหลายร้อยคู่ และข้อมูลรายชั่วโมงไม่อิสระต่อกัน ค่า p เล็กจึงไม่ได้แปลว่าผลมีขนาดใหญ่"],
                 ["Logistic ทายได้เกือบเท่าสุ่ม", "AUC " + D.analysis.auc_global[1].toFixed(3) + " – " + D.analysis.auc_global[5].toFixed(3) + " และค่าสัมประสิทธิ์น้อยมาก"],
                 ["ป้ายทดสอบความรู้สึกมีคนติดคนเดียว", "400 ข้อความ ความแม่นของกฎราว 47%"],
                 ["สัมพันธ์ไม่ใช่เหตุและผล", "ไม่รวมต้นทุนซื้อขาย ไม่ใช่คำแนะนำการลงทุน"]];
  [[left, 0.6, "ข้อมูล"], [right, 6.9, "วิธีวิเคราะห์"]].forEach(([items, x, head]) => {
    text(s, head, x, 1.8, 5.8, 0.4, { fontSize: 16, bold: true, color: C.red });
    items.forEach(([h, b], i) => {
      const y = 2.35 + i * 1.12;
      s.addShape(pres.ShapeType.line, { x, y: y - 0.06, w: 5.8, h: 0, line: { color: C.line, width: 0.75 } });
      text(s, h, x, y, 5.8, 0.35, { fontSize: 14, bold: true });
      text(s, b, x, y + 0.38, 5.8, 0.7, { fontSize: 12, color: C.grey });
    });
  });
}

// ---------- 22 future work ----------
{
  const s = base("พัฒนาต่อ", "ปิดท้าย");
  const rows = [["Reddit", "ตอนนี้: ไฟล์ดัมพ์ย้อนหลัง", "ต่อไป: ขอใช้ API ผ่านบริษัทที่ได้รับอนุญาต เพื่อได้ข้อมูลต่อเนื่อง"],
                ["yfinance", "ตอนนี้: รายชั่วโมง ย้อนหลังราว 2 ปี", "ต่อไป: ดึงเก็บสะสมรายนาทีหรือราย 15 นาที ต่อเนื่องไปเรื่อย ๆ"],
                ["โมเดลความรู้สึก", "ตอนนี้: VADER + FinBERT + กฎรวมผล", "ต่อไป: ฝึกโมเดลเองจากป้ายภาษาของชุมชนนักลงทุน"],
                ["ภาษา", "ตอนนี้: ภาษาอังกฤษ", "ต่อไป: ใช้กับข้อความภาษาไทย"]];
  rows.forEach(([h, a, b], i) => {
    const y = 1.9 + i * 1.12;
    text(s, String(i + 1), 0.6, y, 0.7, 0.8, { fontSize: 34, bold: true, color: C.red });
    text(s, h, 1.4, y + 0.02, 3.2, 0.5, { fontSize: 20, bold: true });
    text(s, a, 4.7, y + 0.05, 3.5, 0.7, { fontSize: 14, color: C.grey });
    s.addShape(pres.ShapeType.line, { x: 8.0, y: y + 0.27, w: 0.45, h: 0, line: { color: C.red, width: 1.75, endArrowType: "triangle" } });
    text(s, b, 8.65, y + 0.05, 4.05, 0.9, { fontSize: 14 });
    s.addShape(pres.ShapeType.line, { x: 0.6, y: y + 0.95, w: 12.1, h: 0, line: { color: C.line, width: 0.75 } });
  });
}

// ---------- 23 Q&A ----------
{
  const s = pres.addSlide();
  s.background = { color: C.red };
  text(s, "ถาม - ตอบ", 0.9, 2.6, 11.5, 1.2, { fontSize: 54, bold: true, color: C.white });
  s.addShape(pres.ShapeType.rect, { x: 0.9, y: 3.95, w: 0.9, h: 0.07, fill: { color: C.white }, line: { color: C.white, width: 0 } });
  text(s, "ขอบคุณครับ\nนายฤทธิพงศ์ เหลืองหิรัญกุล", 0.9, 4.3, 11.5, 1.2, { fontSize: 20, color: C.white });
}

// ---------- appendix ----------
{
  const s = base("ภาคผนวก: จำนวนแท่งราคาของทั้ง 34 สินทรัพย์", "ระบบ 7.2");
  const A = D.market.assets;
  const mk = (list) => list.map((a) => [a.ticker, n0(a.raw), n0(a.clean), n0(a.raw - a.clean)]);
  const stock = A.filter((a) => a.group === "stock_etf"), other = A.filter((a) => a.group !== "stock_etf");
  table(s, ["หุ้น / ETF", "ดิบ", "เหลือ", "ตัด"], mk(stock), 0.6, 1.7, [1.5, 1.0, 1.0, 0.8], { fontSize: 10, rowH: 0.205, align: ["left", "right", "right", "right"] });
  table(s, ["คริปโต / ฟิวเจอร์ส", "ดิบ", "เหลือ", "ตัด"], mk(other), 5.5, 1.7, [1.9, 1.0, 1.0, 0.9], { fontSize: 10, rowH: 0.205, align: ["left", "right", "right", "right"] });
  text(s, "หุ้นและ ETF: ตัดเฉพาะแท่งที่ราคาปิดว่างไม่กี่แท่งต่อตัว  คริปโตเทรด 24 ชม. ตัดน้อยมาก  ฟิวเจอร์สมีช่วงตลาดปิดทุกวัน จึงถูกตัดมากกว่า", 10.4, 1.7, 2.4, 2.8, { fontSize: 11, color: C.grey });
}

pres.writeFile({ fileName: OUT }).then(() => console.log("wrote", OUT));
