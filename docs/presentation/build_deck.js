// Generator of docs/presentation/defence_deck.pptx (written by Claude 2026-11-07). Numbers: output/tables/*.csv, output/reports/*.md, analysis_results (read-only SQL).
// Needs: npm i pptxgenjs in a scratch folder (NODE_PATH), the pptx skill's apply_theme.js (machine-specific path below), and dashboard screenshots from shoot_dashboard.py cropped into <crops_dir>/{home,p1..p7}.png + sizes.json.
// Run: NODE_PATH=<folder>/node_modules node build_deck.js <repo_root> <crops_dir> docs/presentation/defence_deck.pptx
// Full defence deck v2 (7 parts).  Numbers: output/tables/*.csv, output/reports/*.md, analysis_results (read-only SQL, 2026-11-07).
// Run: NODE_PATH=<scratch>/node_modules node build_deck2.js <repo_root> <crops_dir> <out.pptx>
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require("C:/Users/paiigak/.claude/skills/synced/74d9102e-f432-4242-9908-d57add8d1b8b_c6ca036c-a871-48cb-a49f-51c6fdc4d213/pptx/scripts/apply_theme.js");

const ROOT = process.argv[2], CROPS = process.argv[3], OUT = process.argv[4];
const FIG = (f) => path.join(ROOT, "output", "figures", f);
let SIZES = {};
try { SIZES = JSON.parse(fs.readFileSync(path.join(CROPS, "sizes.json"), "utf8")); } catch (e) { /* no screenshots */ }

const FONT = "Leelawadee UI";
const THEME = { name: "Reddit Sentiment Finance", headFontFace: FONT, bodyFontFace: FONT, colors: {
  dk1: "14213D", lt1: "FFFFFF", dk2: "0B1F3A", lt2: "F3F6FA", accent1: "0B7A75", accent2: "C8372D", accent3: "D9A21B", accent4: "3B6EA8",
  accent5: "6B7A90", accent6: "1F9D6B", hlink: "3B6EA8", folHlink: "6B7A90" } };
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.theme = { headFontFace: FONT, bodyFontFace: FONT };
pres.title = "Reddit Sentiment vs Market - defence";
pres.author = "Rithipong Leanghirunkun";
const C = pres.SchemeColor;
const NAVY = "0B1F3A", TEAL = "0B7A75", RED = "C8372D", GREEN = "1F9D6B", GOLD = "D9A21B", BLUE = "3B6EA8", GREY = "6B7A90", INK = "14213D";

const footer = { x: 12.4, y: 7.05, w: 0.6, h: 0.3, fontSize: 10, color: C.accent5, fontFace: FONT };
pres.defineSlideMaster({ title: "DARK", background: { color: C.text2 }, objects: [], slideNumber: footer });
pres.defineSlideMaster({ title: "LIGHT", background: { color: C.background2 }, objects: [], slideNumber: footer });

let sectionNow = null;
function newSlide(master, section) {
  if (section !== sectionNow) { pres.addSection({ title: section }); sectionNow = section; }
  return pres.addSlide({ masterName: master, sectionTitle: section });
}
function head(s, text, tag, dark) {
  s.addText(text, { x: 0.6, y: 0.35, w: 10.6, h: 0.95, fontSize: 28, bold: true, color: dark ? C.background1 : C.text2, valign: "top", margin: 0, isTextBox: true, objectName: "Title" });
  if (tag) s.addText(tag, { x: 10.0, y: 0.38, w: 2.75, h: 0.34, fontSize: 12, bold: true, color: C.accent1, align: "right", margin: 0, isTextBox: true, objectName: "SectionTag" });
}
function card(s, x, y, w, h, title, body, opt = {}) {
  if (Array.isArray(body)) body = body.map((t) => (typeof t === "string" ? { text: t } : t));
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: opt.fill || C.background1 }, line: { color: "DCE3EC", width: 0.75 },
    shadow: { type: "outer", color: "000000", blur: 6, offset: 2, angle: 90, opacity: 0.12 }, objectName: "Card" });
  s.addText(title, { x: x + 0.25, y: y + 0.15, w: w - 0.5, h: 0.45, fontSize: opt.headSize || 19, bold: true, color: opt.headColor || C.text2, margin: 0, valign: "top", isTextBox: true });
  s.addText(body, { x: x + 0.25, y: y + 0.65, w: w - 0.5, h: h - 0.8, fontSize: opt.size || 16, color: C.text1, margin: 0, valign: "top", isTextBox: true, paraSpaceAfter: 6 });
}
const bl = (items) => items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } }));
function stat(s, x, y, w, big, label, color, bigSize) {
  s.addText(big, { x, y, w, h: 0.85, fontSize: bigSize || 36, bold: true, color: color || C.accent1, margin: 0, isTextBox: true, valign: "bottom" });
  s.addText(label, { x, y: y + 0.9, w, h: 0.8, fontSize: 14, color: C.text1, margin: 0, isTextBox: true, valign: "top" });
}
function pill(s, x, y, w, text, fill) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 0.45, fill: { color: fill || C.accent1 }, rectRadius: 0.1, objectName: "Pill" });
  s.addText(text, { x, y, w, h: 0.45, fontSize: 15, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0, isTextBox: true });
}
function openPage(s, name) { pill(s, 0.6, 6.78, 5.9, "เปิดหน้าจริง: " + name, TEAL); }
function box(s, x, y, w, h, title, sub, fill, tcolor) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill || C.background1 }, line: { color: "C9D3E0", width: 0.75 }, rectRadius: 0.08, objectName: "Box" });
  s.addText(title, { x: x + 0.1, y: y + 0.08, w: w - 0.2, h: 0.4, fontSize: 15, bold: true, color: tcolor || C.text2, margin: 0, isTextBox: true, align: "center", valign: "top" });
  if (sub) s.addText(sub, { x: x + 0.1, y: y + 0.5, w: w - 0.2, h: h - 0.58, fontSize: 12.5, color: tcolor || C.text1, margin: 0, isTextBox: true, align: "center", valign: "top" });
}
function arrow(s, x1, y1, x2, y2) {
  s.addShape(pres.shapes.LINE, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1), h: Math.abs(y2 - y1), flipV: y2 < y1, flipH: x2 < x1,
    line: { color: GREY, width: 2, endArrowType: "triangle" } });
}
function shot(s, key, x, y, w, h, caption) {                 // real dashboard screenshot, fitted into w x h
  const sz = SIZES[key];
  s.addShape(pres.shapes.RECTANGLE, { x: x - 0.04, y: y - 0.04, w: w + 0.08, h: h + 0.08, fill: { color: "FFFFFF" }, line: { color: "C9D3E0", width: 1 }, objectName: "ShotFrame" });
  if (sz && fs.existsSync(path.join(CROPS, key + ".png"))) {
    const r = Math.min(w / sz[0], h / sz[1]);
    s.addImage({ path: path.join(CROPS, key + ".png"), x: x + (w - sz[0] * r) / 2, y, w: sz[0] * r, h: sz[1] * r, altText: "ภาพหน้าจอแดชบอร์ด " + key });
  }
  if (caption) s.addText(caption, { x, y: y + h + 0.06, w, h: 0.3, fontSize: 11, color: C.accent5, margin: 0, isTextBox: true });
}
const chartCommon = { catAxisLabelColor: "14213D", valAxisLabelColor: "6B7A90", catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
  catAxisLabelFontSize: 13, valAxisLabelFontSize: 12, valGridLine: { color: "DCE3EC", size: 0.5 }, catGridLine: { style: "none" }, dataLabelFontFace: "+mn-lt",
  dataLabelFontSize: 13, dataLabelColor: "14213D", legendFontFace: "+mn-lt", legendFontSize: 13, legendColor: "14213D", titleFontFace: "+mn-lt", titleFontSize: 15, titleColor: "14213D" };
function table(s, rows, opt) {
  const hdr = rows[0].map((t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: NAVY } } }));
  s.addTable([hdr, ...rows.slice(1)], Object.assign({ fontSize: 13, fontFace: FONT, color: INK, border: { type: "solid", pt: 0.75, color: "DCE3EC" }, fill: { color: "FFFFFF" },
    valign: "middle", margin: [0.05, 0.1, 0.05, 0.1] }, opt));
}

// =============================================================== 1 Title
{
  const s = newSlide("DARK", "เปิด");
  s.addText("ความรู้สึกบน Reddit สอนอะไรเราเกี่ยวกับตลาด", { x: 0.8, y: 1.6, w: 11.7, h: 1.6, fontSize: 40, bold: true, color: C.background1, margin: 0, isTextBox: true, valign: "top" });
  s.addText("คลังข้อมูลและแดชบอร์ดเทียบความรู้สึกจาก Reddit กับราคา 34 สินทรัพย์ รายชั่วโมง", { x: 0.8, y: 3.3, w: 11.7, h: 0.8, fontSize: 20, color: "CADCFC", margin: 0, isTextBox: true, valign: "top" });
  s.addText("Rithipong Leanghirunkun  |  จุฬาลงกรณ์มหาวิทยาลัย MSc BIT", { x: 0.8, y: 6.3, w: 11.7, h: 0.4, fontSize: 15, color: "CADCFC", margin: 0, isTextBox: true });
  s.addText("ข้อมูลย้อนหลัง ต.ค. 2024 ถึง ส.ค. 2026  |  ไม่ใช่ real-time และไม่ใช่คำแนะนำการลงทุน", { x: 0.8, y: 6.7, w: 11.7, h: 0.4, fontSize: 13, color: "9FB3D1", margin: 0, isTextBox: true });
  s.addNotes("เปิด: แนะนำตัวสั้น ๆ แล้วบอกทันทีว่างานนี้ตอบคำถามเดียว: ตลาดเริ่มพูดถึงสินทรัพย์ไหนในทางบวกหรือลบตอนไหน และข้อมูลนี้ช่วยการตัดสินใจลงทุนได้จริงแค่ไหน. ระบุขอบเขตตั้งแต่ต้น: ข้อมูลย้อนหลัง ไม่ใช่คำแนะนำการลงทุน. เวลารวมโดยประมาณ 40 ถึง 45 นาทีรวม demo สด และ Q&A.");
}
// =============================================================== 2 Agenda
{
  const s = newSlide("LIGHT", "เปิด");
  head(s, "เส้นทางการนำเสนอ 7 ช่วง", null);
  const items = [["1", "Pain point", "ทำไมต้องมีระบบนี้"], ["2", "ผู้ใช้", "ใครใช้ และใช้ทำอะไร"], ["3", "สถาปัตยกรรม", "ข้อมูลไหลผ่านระบบอย่างไร"],
    ["4", "แดชบอร์ดทีละหน้า", "8 หน้า หน้าละอะไร"], ["5", "เล่าเรื่องพร้อมเปิดหน้าจริง", "BTC-USD เป็นตัวอย่างหลัก"], ["6", "คำถามผู้บริหาร", "แต่ละข้อ ตอบด้วยกราฟไหน"], ["7", "QA", "คุณภาพระบบ และถาม-ตอบ"]];
  items.forEach((it, i) => {
    const col = i < 4 ? 0 : 1, row = i < 4 ? i : i - 4;
    const x = 0.6 + col * 6.2, y = 1.6 + row * 1.25;
    s.addShape(pres.shapes.OVAL, { x, y, w: 0.85, h: 0.85, fill: { color: i === 4 ? C.accent2 : C.accent1 }, objectName: "Num" + it[0] });
    s.addText(it[0], { x, y, w: 0.85, h: 0.85, fontSize: 26, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0, isTextBox: true });
    s.addText(it[1], { x: x + 1.05, y: y - 0.02, w: 4.9, h: 0.5, fontSize: 22, bold: true, color: C.text2, margin: 0, isTextBox: true });
    s.addText(it[2], { x: x + 1.05, y: y + 0.45, w: 4.9, h: 0.4, fontSize: 15, color: C.accent5, margin: 0, isTextBox: true });
  });
  s.addNotes("ช่วงที่ 5 คือหัวใจ: เปิดแดชบอร์ดจริงแล้วเล่าเป็นเรื่องตามลำดับ. ช่วงที่ 3 และ 4 ให้เร็ว เพราะช่วง 5 จะกลับไปแตะทุกหน้าอีกครั้งพร้อมตัวเลขจริง.");
}

// =============================================================== PART 1: PAIN POINT
{
  const s = newSlide("LIGHT", "1 Pain point");
  head(s, "เห็นราคาวิ่งแล้วค่อยซื้อ มักได้ราคาที่แพงที่สุดของรอบนั้น", "1 Pain point");
  card(s, 0.6, 1.6, 3.9, 3.9, "เกิดอะไรขึ้นในตลาด", bl(["ราคาเริ่มขยับ คนในโซเชียลเริ่มพูดถึง", "ราคาวิ่งต่อ คนที่ตกรถเริ่มรีบซื้อ (FOMO)", "นักลงทุนรายย่อยมักเข้าเมื่อราคาไปไกลแล้ว"]));
  card(s, 4.7, 1.6, 3.9, 3.9, "สิ่งที่นักลงทุนอยากรู้", bl(["อารมณ์ตลาดเปลี่ยนเป็นบวกหรือลบตอนไหน", "ก่อนราคาขยับ หรือหลังราคาขยับ", "ช่วงไหนคนพูดถึงมากผิดปกติ"]), { headColor: C.accent2 });
  card(s, 8.8, 1.6, 3.9, 3.9, "สิ่งที่ผมทำ", bl(["รวบรวมข้อความ Reddit 22.0 ล้านข้อความ", "วัดความรู้สึกรายชั่วโมง", "เทียบกับราคา 34 สินทรัพย์ แล้วตรวจว่าใช้ประกอบการตัดสินใจได้ไหม"]), { headColor: C.accent1 });
  s.addText("ในทางการเงิน พฤติกรรมนี้คือการไล่ราคา (momentum chasing) และความกลัวพลาดโอกาส (FOMO)", { x: 0.6, y: 5.85, w: 12.1, h: 0.8, fontSize: 18, bold: true, color: C.text2, margin: 0, isTextBox: true, valign: "middle" });
  s.addNotes("เล่าจากประสบการณ์ตัวเอง: เคยตกรถเพราะเห็นหุ้นขึ้นแล้วตามช้า. ในทางการเงินเรียกพฤติกรรมนี้ว่าการไล่ราคา หรือ FOMO. คำถามคือ มีสัญญาณจากความเห็นของคนจำนวนมากที่มาก่อนราคาไหม. ย้ำว่าคำตอบอาจเป็น 'ไม่' ก็ได้ และนั่นก็เป็นผลวิจัยที่มีค่า.");
}
{
  const s = newSlide("LIGHT", "1 Pain point");
  head(s, "คำถามวิจัย: ความรู้สึกบน Reddit นำราคา ตามราคา หรือไม่เกี่ยวกัน", "1 Pain point");
  card(s, 0.6, 1.6, 5.9, 2.5, "ระบบพยายามตอบ", bl(["ช่วงไหนที่คนพูดถึงตลาดมากผิดปกติ", "สินทรัพย์ไหนถูกพูดถึงในทางบวกหรือลบ", "ความรู้สึกสัมพันธ์กับราคาทันทีหรือราคาในอนาคต"]));
  card(s, 6.8, 1.6, 5.9, 2.5, "ขอบเขต", bl(["6 ชุมชน: wallstreetbets, stocks, investing, StockMarket, options, CryptoCurrency", "34 สินทรัพย์ (หุ้นและ ETF 22, คริปโต 6, ฟิวเจอร์ส 6)", "ข้อมูลรายชั่วโมง ต.ค. 2024 ถึง ส.ค. 2026"]), { size: 14 });
  card(s, 0.6, 4.35, 12.1, 2.3, "ผลลัพธ์ที่ได้ จะเป็นเครื่องมือสนับสนุนการวิเคราะห์ (Analytical Decision Support)", bl(["ไม่ใช่คำแนะนำการลงทุน ไม่ใช่การทำนายราคา และไม่ใช่ real-time", "ถ้าผลสรุปคือ \"ทำนายอนาคตไม่ได้\" ก็ถือเป็นข้อค้นพบที่ตรวจสอบได้ และช่วยกันไม่ให้ไล่ตามสัญญาณที่ไม่มีอยู่จริง"]), { headColor: C.accent2, size: 16 });
  s.addNotes("ย้ำขอบเขตตาม proposal: เป็น Analytical Decision Support ไม่ใช่คำแนะนำการลงทุนหรือการทำนายราคา.");
}

// =============================================================== PART 2: USERS
{
  const s = newSlide("LIGHT", "2 ผู้ใช้");
  head(s, "ผู้ใช้ของระบบ คือทีมนักวิเคราะห์ที่ต้องการอ่านสภาวะตลาดเพิ่มเติม", "2 ผู้ใช้");
  s.addShape(pres.shapes.OVAL, { x: 0.8, y: 1.9, w: 2.4, h: 2.4, fill: { color: C.accent1 }, objectName: "UserCircle" });
  s.addText("ทีม\nนักวิเคราะห์ฯ", { x: 0.8, y: 1.9, w: 2.4, h: 2.4, fontSize: 22, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0, isTextBox: true });
  s.addText("ผู้ใช้กลุ่มเดียวตาม proposal ทุกระบบย่อย", { x: 0.6, y: 4.5, w: 3.0, h: 0.9, fontSize: 14, color: C.accent5, align: "center", margin: 0, isTextBox: true, valign: "top" });
  card(s, 4.0, 1.6, 4.3, 2.2, "ประเมินความตื่นตัวของรายย่อย", ["ดูปริมาณการกล่าวถึงสินทรัพย์ในชุมชน Reddit (ระบบ 7.1)"], { size: 15 });
  card(s, 8.5, 1.6, 4.2, 2.2, "ติดตามราคาและผลตอบแทน", ["ราคา ปริมาณซื้อขาย และผลตอบแทนล่วงหน้าของแต่ละสินทรัพย์ (ระบบ 7.2)"], { size: 15 });
  card(s, 4.0, 4.0, 4.3, 2.65, "ตรวจความสัมพันธ์", ["ใช้ความรู้สึกและสถิติเป็นข้อมูลเสริม (Alternative Data) ประกอบการประเมินสภาวะตลาด (ระบบ 7.3 ถึง 7.5)"], { size: 15 });
  card(s, 8.5, 4.0, 4.2, 2.65, "หาช่วงที่ควรวิเคราะห์ต่อ", ["ใช้รายการสัญญาณ (Z-score สูง ความรู้สึกชัด) เป็นจุดเริ่มต้นตรวจเชิงลึก (ระบบ 7.6)"], { size: 15 });
  s.addNotes("ตาม proposal ผู้ใช้คือ 'ทีมนักวิเคราะห์ฯ' ทุกระบบ. ไม่ใช่นักเทรดที่ต้องการสัญญาณซื้อขาย และไม่ได้รับการแนะนำการลงทุน. ใช้เป็นข้อมูลเสริมประกอบการวิเคราะห์.");
}
{
  const s = newSlide("LIGHT", "2 ผู้ใช้");
  head(s, "ผู้ใช้ทำงานกับระบบเป็น 4 ขั้น และแต่ละขั้นมีหน้าแดชบอร์ดรองรับ", "2 ผู้ใช้");
  const steps = [["1  เฝ้าดู", "ตอนนี้ตลาดคุยเรื่องอะไร\nผิดปกติตรงไหน", "หน้า 1, 2, Home", C.accent1],
    ["2  เทียบกับราคา", "ราคาเป็นอย่างไร\nความรู้สึกไปทางเดียวกันไหม", "หน้า 3, 4", C.accent4],
    ["3  ตรวจสอบ", "ใครมาก่อน\nและเชื่อถือได้แค่ไหน", "หน้า 6, 5", C.accent3],
    ["4  ตามต่อ", "ตั้งเกณฑ์\nแล้วไล่ช่วงที่ควรวิเคราะห์", "หน้า 7", C.accent2]];
  steps.forEach((st, i) => {
    const x = 0.6 + i * 3.1;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.9, w: 2.9, h: 3.3, fill: { color: C.background1 }, line: { color: "DCE3EC", width: 0.75 }, objectName: "Flow" + i,
      shadow: { type: "outer", color: "000000", blur: 6, offset: 2, angle: 90, opacity: 0.12 } });
    s.addShape(pres.shapes.OVAL, { x: x + 0.2, y: 2.1, w: 0.6, h: 0.6, fill: { color: st[3] }, objectName: "FlowDot" + i });
    s.addText(st[0], { x: x + 0.95, y: 2.1, w: 1.85, h: 0.6, fontSize: 18, bold: true, color: C.text2, margin: 0, isTextBox: true, valign: "middle" });
    s.addText(st[1], { x: x + 0.2, y: 3.0, w: 2.5, h: 1.3, fontSize: 16, color: C.text1, margin: 0, isTextBox: true, valign: "top" });
    s.addText(st[2], { x: x + 0.2, y: 4.5, w: 2.5, h: 0.45, fontSize: 15, bold: true, color: st[3], margin: 0, isTextBox: true });
    if (i < 3) arrow(s, x + 2.92, 3.55, x + 3.08, 3.55);
  });
  s.addText("ตัวกรองกลางชุดเดียวกัน (เวลา, ชุมชน, สินทรัพย์) ใช้ได้ทุกหน้า ผู้ใช้จึงเลือกครั้งเดียวแล้วดูต่อได้ทั้งเส้นทาง", { x: 0.6, y: 5.6, w: 12.1, h: 0.9, fontSize: 17, color: C.text2, bold: true, margin: 0, isTextBox: true, valign: "top" });
  s.addNotes("อธิบายว่าลำดับหน้าในการเล่าเรื่องมาจากวิธีที่นักวิเคราะห์ทำงานจริง: เฝ้าดู เทียบ ตรวจสอบ แล้วตามต่อ. ช่วงเล่าเรื่องจะเดินตามเส้นทางนี้.");
}

// =============================================================== PART 3: ARCHITECTURE
{
  const s = newSlide("LIGHT", "3 สถาปัตยกรรม");
  head(s, "สถาปัตยกรรม: ข้อมูลไหลจากแหล่งดิบ ผ่าน SQLite ไปจบที่แดชบอร์ด", "3 สถาปัตยกรรม");
  box(s, 0.45, 1.55, 2.2, 1.55, "Academic Torrents", "Reddit ย้อนหลัง\n(.zst) 6 ชุมชน", "E8EEF6");
  box(s, 0.45, 3.45, 2.2, 1.55, "yfinance", "ราคารายชั่วโมง\n34 สินทรัพย์", "E8EEF6");
  box(s, 3.0, 1.55, 2.0, 1.55, "นำเข้า", "ingest/\nreddit_extract.py", "FFFFFF");
  box(s, 3.0, 3.45, 2.0, 1.55, "นำเข้า", "ingest/\nmarket_fetch.py", "FFFFFF");
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.4, y: 1.55, w: 2.6, h: 3.45, fill: { color: NAVY }, rectRadius: 0.1, objectName: "SQLiteBox" });
  s.addText("SQLite", { x: 5.4, y: 1.65, w: 2.6, h: 0.5, fontSize: 22, bold: true, color: C.background1, align: "center", margin: 0, isTextBox: true });
  s.addText("แหล่งความจริงเดียว\noutput/reddit.sqlite3", { x: 5.5, y: 2.2, w: 2.4, h: 0.7, fontSize: 13, color: "CADCFC", align: "center", margin: 0, isTextBox: true });
  s.addText([{ text: "ชั้นดิบ", options: { bold: true, breakLine: true } }, { text: "ชั้นประมวลผล และฟีเจอร์", options: { bold: true, breakLine: true } }, { text: "Star schema (Fact 3 / Dim 6)", options: { bold: true, breakLine: true } },
    { text: "ผลวิเคราะห์ และสัญญาณ", options: { bold: true } }], { x: 5.55, y: 3.0, w: 2.3, h: 1.9, fontSize: 13, color: C.background1, margin: 0, isTextBox: true, valign: "top", paraSpaceAfter: 5 });
  box(s, 8.35, 1.55, 2.4, 3.45, "ประมวลผล (etl/ analysis/)", "ล้างข้อความ กรอง สกัด Ticker\nฟีเจอร์ราคา\nVADER + FinBERT + กฎรวมผล\nCorrelation, Win Rate, Logistic\nตรวจจับสัญญาณ", "FFFFFF");
  box(s, 11.05, 1.55, 1.85, 3.45, "แดชบอร์ด", "Streamlit\nHome + 7 หน้า\nอ่านอย่างเดียว", C.accent1, C.background1);
  arrow(s, 2.67, 2.3, 2.98, 2.3); arrow(s, 2.67, 4.2, 2.98, 4.2);
  arrow(s, 5.02, 2.3, 5.38, 2.9); arrow(s, 5.02, 4.2, 5.38, 3.9);
  arrow(s, 8.02, 3.3, 8.33, 3.3); arrow(s, 10.77, 3.3, 11.03, 3.3);
  s.addText("ระบบ 1 และ 2 เป็นข้อมูลเข้า  |  ระบบ 3 วัดความรู้สึก  |  ระบบ 4 วิเคราะห์สถิติ  |  ระบบ 5 แดชบอร์ด  |  ระบบ 6 ตรวจจับสัญญาณและค่าวัด", { x: 0.45, y: 5.3, w: 12.4, h: 0.5, fontSize: 15, bold: true, color: C.text2, margin: 0, isTextBox: true });
  s.addText("ทุกขั้นเป็นสคริปต์ที่รันซ้ำได้ (steps/01 ถึง 33) เวลาทุกชุดเป็น UTC และไฟล์ข้อมูลดิบถูกเก็บเป็นสำเนาเดียวห้ามแก้", { x: 0.45, y: 5.85, w: 12.4, h: 0.8, fontSize: 15, color: C.text1, margin: 0, isTextBox: true, valign: "top" });
  s.addNotes("อธิบายจากซ้ายไปขวา. จุดเน้น: SQLite เป็นแหล่งความจริงเดียว (ตัด PostgreSQL ตาม proposal), ทุกชั้นอยู่ในฐานเดียว จึงตรวจย้อนกลับได้. แดชบอร์ดอ่านอย่างเดียว ไม่แก้ข้อมูล. ทุกขั้นเป็นสคริปต์ steps/ ที่รันซ้ำได้ ตัวเลขในเล่มจึงมาจากสคริปต์ ไม่ใช่ query มือ.");
}
{
  const s = newSlide("LIGHT", "3 สถาปัตยกรรม");
  head(s, "จากข้อความดิบ 24.5 ล้าน เหลือ 22.0 ล้านข้อความที่ใช้วิเคราะห์", "3 สถาปัตยกรรม");
  s.addChart(pres.charts.BAR, [{ name: "จำนวนข้อความ (ล้าน)", labels: ["ข้อมูลดิบ 6 ชุมชน", "อ่านได้ (ไม่ถูกลบ)", "ล้างข้อความแล้ว", "ผ่านตัวกรองคุณภาพ", "พูดถึง Ticker เป้าหมาย"],
    values: [24.519, 22.841, 22.522, 22.029, 3.473] }], {
    x: 0.6, y: 1.5, w: 7.2, h: 5.0, barDir: "bar", chartColors: [TEAL], showLegend: false, showTitle: true, title: "ข้อความในแต่ละขั้น (ล้านข้อความ)", showValue: true, dataLabelPosition: "outEnd",
    dataLabelFormatCode: "0.00", valAxisHidden: true, valGridLine: { style: "none" }, catAxisOrientation: "maxMin", valAxisMaxVal: 29, ...chartCommon });
  card(s, 8.1, 1.6, 4.6, 2.5, "ตัดอะไรออก", bl(["ถูกลบหรือนำออกโดยผู้ใช้ Reddit 1.68 ล้าน", "บอทและข้อความผู้ดูแล 417,853", "สั้นเกินไป 69,049 และไม่ใช่ภาษาอังกฤษ 5,729"]), { size: 14 });
  card(s, 8.1, 4.3, 4.6, 2.3, "ในมุมการเงิน", bl(["ราว 15.8% ของข้อความพูดถึงสินทรัพย์เป้าหมาย ที่เหลือเป็นบรรยากาศตลาดทั่วไป", "wallstreetbets คิดเป็น 73.2% ของข้อความ"]), { size: 14, headColor: C.accent1 });
  s.addNotes("ตัวเลขจาก t1_data_funnel.csv และ 3_final_summary.md. ข้อสังเกตที่ต้องพูดเอง: wallstreetbets ครอง 73.2% ของข้อความ ภาพรวมจึงเป็นบรรยากาศของ WSB เป็นหลัก. ข้อความที่พูดถึง Ticker เป้าหมายมี 3,472,975 ข้อความ (15.8%).");
}
{
  const s = newSlide("LIGHT", "3 สถาปัตยกรรม");
  head(s, "คลังข้อมูล Star schema: 3 ตารางข้อเท็จจริง กับ 6 มิติ", "3 สถาปัตยกรรม");
  const facts = [["FactRedditVolume", "618,518 แถว", "ปริมาณข้อความ และจำนวนการกล่าวถึง\nมิติ: DimTime, DimTicker, DimSource", C.accent1],
    ["FactMarketPrice", "250,253 แถว", "ราคา ปริมาณซื้อขาย Current Return RSI ATR\nมิติ: DimTime, DimTicker", C.accent4],
    ["FactMarketSentiment", "250,253 แถว", "ความรู้สึก ผลตอบแทนล่วงหน้า Win Rate\nมิติ: DimTime, DimTicker, DimSentimentSource", C.accent3]];
  facts.forEach((f, i) => {
    const y = 1.55 + i * 1.45;
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y, w: 7.4, h: 1.3, fill: { color: C.background1 }, line: { color: "DCE3EC", width: 0.75 }, objectName: "Fact" + i,
      shadow: { type: "outer", color: "000000", blur: 6, offset: 2, angle: 90, opacity: 0.12 } });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y, w: 2.5, h: 1.3, fill: { color: f[3] }, objectName: "FactHead" + i });
    s.addText(f[0], { x: 0.65, y: y + 0.15, w: 2.4, h: 0.6, fontSize: 15, bold: true, color: C.background1, margin: 0, isTextBox: true, align: "center", valign: "middle" });
    s.addText(f[1], { x: 0.65, y: y + 0.75, w: 2.4, h: 0.4, fontSize: 14, color: C.background1, margin: 0, isTextBox: true, align: "center" });
    s.addText(f[2], { x: 3.3, y: y + 0.1, w: 4.6, h: 1.1, fontSize: 14, color: C.text1, margin: 0, isTextBox: true, valign: "middle" });
  });
  const dims = [["DimTime", "17,544 ชั่วโมง ปี > เดือน > สัปดาห์ > วัน > ชั่วโมง"], ["DimTicker", "34 สินทรัพย์ กลุ่ม > สัญลักษณ์ > ชื่อ"], ["DimSource", "12 แหล่ง ชุมชน x ประเภท (โพสต์/คอมเมนต์)"],
    ["DimSentimentSource", "7 แหล่ง แพลตฟอร์ม > ชุมชน > แบบจำลอง"], ["DimMajoritySentiment", "3 ประเภท บวก ลบ กลาง"], ["DimDetectionConfig", "30 ชุดเกณฑ์ Z-score x Sentiment x Horizon"]];
  card(s, 8.3, 1.55, 4.4, 4.2, "6 มิติ (ตัวกรองของแดชบอร์ด)", dims.map((d, i) => ({ text: d[0] + "  " + d[1], options: { bullet: true, breakLine: i < dims.length - 1 } })), { size: 12.5, headSize: 17 });
  s.addText("ชื่อตารางและคอลัมน์ตรงตามรูปที่ 2 ถึง 4 ของ proposal เพื่ออ้างอิงในรายงานได้ตรงกัน", { x: 0.6, y: 6.0, w: 12.1, h: 0.7, fontSize: 15, bold: true, color: C.text2, margin: 0, isTextBox: true });
  s.addNotes("Star schema เพื่อให้ BI ถามคำถามหลายมิติได้: เวลา สินทรัพย์ แหล่งข้อมูล. จำนวนแถวมาจากรายงานสรุปขั้นตอน (3_final_summary.md) และ system_tests.md. DimDetectionConfig ใช้ตั้งเกณฑ์ตรวจจับสัญญาณในหน้า Hot Events.");
}
{
  const s = newSlide("LIGHT", "3 สถาปัตยกรรม");
  head(s, "ระบบ 3: สองโมเดลเห็นตรงกันแค่ครึ่งเดียว จึงต้องมีกฎรวมผล", "3 สถาปัตยกรรม");
  s.addChart(pres.charts.DOUGHNUT, [{ name: "สัดส่วน", labels: ["เห็นตรงกัน", "ตัวหนึ่งกลาง อีกตัวมีทิศ", "ทิศตรงข้ามกัน"], values: [50.15, 37.59, 12.25] }], {
    x: 0.5, y: 1.5, w: 6.0, h: 5.0, holeSize: 50, chartColors: [GREEN, GOLD, RED], showLegend: true, legendPos: "b", showPercent: true, showValue: false, dataLabelColor: "FFFFFF", dataLabelFontSize: 15,
    showTitle: true, title: "VADER เทียบ FinBERT บน 22.0 ล้านข้อความ", ...chartCommon, dataLabelColor: "FFFFFF" });
  card(s, 6.9, 1.6, 5.8, 2.3, "กฎรวมผล (final_sentiment)", bl(["เห็นตรงกัน: ใช้ค่าเฉลี่ย", "ตัวหนึ่งกลาง: ใช้ตัวที่มีทิศ", "ตรงข้ามกัน: ดูคำสำคัญ ถ้าไม่มีให้เป็น 0", "แบนด์กลาง ±0.05"]), { size: 14 });
  card(s, 6.9, 4.1, 5.8, 2.5, "ในมุมการเงิน", bl(["VADER จับอารมณ์ของคำทั่วไป FinBERT เรียนจากภาษาการเงิน จึงตัดสินต่างกัน", "คำอย่าง calls, puts, bullish บอกทิศชัดกว่าน้ำเสียง จึงใช้ตัดสินเมื่อขัดกัน", "ข้อความที่ตัดสินไม่ได้ (12.3%) ถูกตั้งเป็น 0 และติดธง is_ambiguous"]), { size: 14, headColor: C.accent1 });
  s.addNotes("ตัวเลขจาก t3_final_method.csv: ทิศเดียวกัน = same_direction 21.76 + same_direction_far 7.85 + both_neutral 20.54 = 50.15%. ตัวหนึ่งกลาง = small_conflict_* 37.59%. ตรงข้าม = hard_conflict_* 12.25%. ผลสุดท้ายทุกข้อความมี final_method บันทึกไว้ เพื่อตรวจสอบย้อนหลัง.");
}
{
  const s = newSlide("LIGHT", "3 สถาปัตยกรรม");
  head(s, "ทดสอบกฎรวมผลกับป้ายคน 400 ข้อความ ผลคือคงกฎเดิม", "3 สถาปัตยกรรม");
  s.addChart(pres.charts.BAR, [
    { name: "VADER เดี่ยว", labels: ["ทุกกลุ่มรวม", "ขัดกันแรงและมีคำสำคัญ"], values: [43.3, 46] },
    { name: "FinBERT เดี่ยว", labels: ["ทุกกลุ่มรวม", "ขัดกันแรงและมีคำสำคัญ"], values: [47.9, 42] },
    { name: "กฎรวมผล", labels: ["ทุกกลุ่มรวม", "ขัดกันแรงและมีคำสำคัญ"], values: [47.1, 68] }], {
    x: 0.6, y: 1.5, w: 6.6, h: 4.0, barDir: "col", chartColors: ["9FB3D1", "6B7A90", TEAL], showLegend: true, legendPos: "b", showTitle: true, title: "ความแม่นเทียบกับป้ายของคน (%)",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0", valAxisHidden: true, valGridLine: { style: "none" }, valAxisMinVal: 0, valAxisMaxVal: 80, ...chartCommon });
  s.addText("ส่วนขยายนอก proposal  |  ผู้ติดป้ายคนเดียว  |  ป้าย neutral 163 จาก 400 ข้อความ", { x: 0.6, y: 5.65, w: 6.6, h: 0.4, fontSize: 12, color: C.accent5, margin: 0, isTextBox: true });
  s.addText("ความแม่นรวมราว 47% ไม่สูง เพราะวัดกับท่าทีของผู้เขียนคอมเมนต์ ไม่ใช่แค่น้ำเสียงข้อความ", { x: 0.6, y: 6.1, w: 6.6, h: 0.7, fontSize: 14, color: C.text1, margin: 0, isTextBox: true, valign: "top" });
  card(s, 7.5, 1.6, 5.2, 2.5, "วิธีทดสอบ", bl(["สุ่ม 400 คอมเมนต์ จาก 7 กลุ่มกฎ แบ่งชุด tune กับ test", "ตั้งเกณฑ์ก่อนดูผล: ต้องชนะอย่างน้อย 5 จุดบน tune และยืนยันบน test"]), { size: 14 });
  card(s, 7.5, 4.3, 5.2, 2.35, "ผลและความหมาย", bl(["ไม่มีทางเลือกใดชนะถึงเกณฑ์ จึงคงกฎ", "ขัดกันแรง: กฎรวมผล 68% เทียบ 42 ถึง 46%", "เติมเนื้อโพสต์แล้วแย่ลง (35.9% เทียบ 47.1%)"]), { size: 14, headColor: C.accent1 });
  s.addNotes("ตัวเลขจาก output/reports/rule_validation/rule_validation.md และ docs/RULE_VALIDATION_SUMMARY_TH.md. ตั้งเกณฑ์ก่อนดูผลเพื่อไม่เลือกตัวที่ดูดีทีหลัง. ข้อจำกัดที่ต้องพูดเอง: ผู้ติดป้ายคนเดียว ป้ายกลางเยอะ เป็นส่วนขยายนอก proposal. ภาพสำรอง: output/figures/s5_confusion_matrices.png.");
}
{
  const s = newSlide("LIGHT", "3 สถาปัตยกรรม");
  head(s, "ข้อกำหนดที่ทำให้ผลเชื่อถือได้: ไม่ให้ข้อมูลอนาคตรั่ว และรันซ้ำได้", "3 สถาปัตยกรรม");
  card(s, 0.6, 1.6, 3.9, 4.9, "ไม่ให้ข้อมูลอนาคตรั่ว", bl(["Z-score เทียบ 24 ชม.ก่อนหน้า ไม่รวมชั่วโมงนี้", "ไม่ใช้ผลตอบแทนอนาคต หรือคะแนนโหวตโพสต์ เป็นตัวทำนาย", "แบ่งข้อมูลตามเวลา เว้นช่วง 12 ชม. ไม่สุ่มสลับ"]), { size: 14, headColor: C.accent2 });
  card(s, 4.7, 1.6, 3.9, 4.9, "จัดข้อมูลให้เทียบกันได้", bl(["เวลาทุกชุดเป็น UTC", "บาร์เริ่ม xx:30 (หุ้น) และ xx:00 (คริปโต) ปัดเป็นต้นชั่วโมง", "ไม่มีข้อความ = NULL ไม่ใช่ 0 (ไม่เท่ากับเป็นกลาง)", "ตัดแถวที่ตลาดปิดไม่มีราคา"]), { size: 14 });
  card(s, 8.8, 1.6, 3.9, 4.9, "ตรวจสอบย้อนหลังได้", bl(["33 สคริปต์ตามลำดับ steps/", "ตั้งค่า (6 ชุมชน, 34 สินทรัพย์, เกณฑ์) ไว้ที่เดียว", "ทุกแถวเก็บรุ่นของวิธีและเวลาสร้าง", "ตัวเลขในเล่มมาจากสคริปต์ ไม่ใช่ query มือ"]), { size: 14, headColor: C.accent1 });
  s.addNotes("ในมุมการเงิน: look-ahead bias คือการใช้ข้อมูลที่นักลงทุนจริงยังไม่รู้ ณ เวลานั้น ทำให้ backtest สวยเกินจริง. ระบบกันด้วย 3 วิธี. ข้อ 'ไม่มีข้อความ = NULL' สำคัญ: ชั่วโมงที่ไม่มีใครพูดถึงต่างจากชั่วโมงที่ทุกคนเป็นกลาง.");
}

// =============================================================== PART 4: DASHBOARD EACH
{
  const s = newSlide("LIGHT", "4 แดชบอร์ด");
  head(s, "แดชบอร์ด: Home + 7 หน้า ใช้ตัวกรองกลางชุดเดียวกัน", "4 แดชบอร์ด");
  const rows = [["หน้า", "ระบบ (proposal)", "ตอบเรื่อง"],
    ["Home", "ภาพรวม", "การ์ดสรุปตามตัวกรอง ช่วงข้อมูลทั้งหมด วิธีใช้"],
    ["1 Reddit Volume", "7.1", "ช่วงไหนพูดมากผิดปกติ"],
    ["2 Ticker Mentions", "7.1", "สินทรัพย์ไหนถูกพูดถึงมาก"],
    ["3 Price and Return", "7.2", "ราคา ผลตอบแทน ความผันผวน"],
    ["4 Market and Sentiment", "7.3 และ 7.5 (แดชบอร์ด 1)", "ความรู้สึกเทียบราคา ตารางอันดับ"],
    ["5 Statistical Analysis", "7.4 และ 7.5 (แดชบอร์ด 2)", "Correlation, Win Rate, Logistic"],
    ["6 Lead and Lag", "ส่วนขยาย", "ใครขยับก่อน ความรู้สึกหรือราคา"],
    ["7 Hot Events", "7.6", "รายการสัญญาณและเกณฑ์ที่ตั้งเอง"]];
  table(s, rows, { x: 0.6, y: 1.5, w: 7.6, colW: [2.4, 2.4, 2.8], fontSize: 12.5, rowH: 0.52 });
  card(s, 8.5, 1.5, 4.2, 5.1, "ตัวกรองกลาง (แถบซ้าย)", bl(["เวลา (DimTime) ค่าเริ่มต้นย้อนหลัง 1 ปี ระดับชั่วโมงถึงปี", "แหล่งข้อมูล (DimSource) ชุมชน และโพสต์/คอมเมนต์", "หลักทรัพย์ (DimTicker) กลุ่มและสัญลักษณ์", "ประเภทความรู้สึกส่วนใหญ่ (DimMajoritySentiment)", "เกณฑ์สัญญาณ (DimDetectionConfig) ในหน้า 7"]), { size: 14 });
  s.addNotes("เป็นแผนที่ของแดชบอร์ดทั้งหมด. จุดที่ต้องบอก: หน้า 1 และ 2 แยกจากแดชบอร์ดที่ 1 ของ 7.1 เป็นสองหน้า. หน้า 6 เป็นส่วนขยายนอก proposal. ทุกหน้าอ่านฐานข้อมูลอย่างเดียว.");
}
const pageSlides = [
  { key: "home", title: "Home: ภาพรวมก่อนเริ่มสำรวจ", tag: "ภาพรวม", cards: [
    ["ตอบอะไร", bl(["ข้อมูลที่มีอยู่ ช่วงเวลา และจำนวนข้อความ", "การ์ดสรุปตามตัวกรองที่เลือก"])], ["วิธีใช้", bl(["เลือกช่วงเวลา สินทรัพย์ แล้วไปหน้าที่ต้องการ", "ข้อจำกัดที่ต้องรู้อยู่บนหน้าแรก"])]],
    note: "Home คือหน้าเปิด: บอกช่วงข้อมูลทั้งหมด (Reddit และราคา) และการ์ดตามตัวกรอง. ใช้เป็นจุดเริ่มก่อนไปหน้า 1." },
  { key: "p1", title: "หน้า 1 Reddit Volume: ช่วงไหนที่ตลาดพูดมากผิดปกติ", tag: "7.1", cards: [
    ["ค่าวัด และ KPI", bl(["Reddit_volume (ครั้ง)", "Reddit Volume Z-score = (ปริมาณ − ค่าเฉลี่ย 24 ชม.ก่อนหน้า) ÷ SD"])],
    ["กราฟในหน้า", bl(["การ์ด 5 ใบ: รวม เฉลี่ยต่อชม. ชม.สูงสุด Z สูงสุด ชม.ที่ Z > 1.5", "ปริมาณรวม และโพสต์ ตามเวลา", "Z-score พร้อมเส้นเกณฑ์ 1.5", "ตารางแยกตามชุมชน"])]],
    note: "หน้า 1 ตอบ 'ปริมาณรายชั่วโมงเพิ่มหรือลด'. KPI คือ Reddit Volume Z-score ตามสูตรตารางที่ 4 ของ proposal. ภาพนี้คือค่าเริ่มต้น (ย้อนหลัง 1 ปี) ตัวเลขจึงต่างจากช่วงเต็ม." },
  { key: "p2", title: "หน้า 2 Ticker Mentions: สินทรัพย์ไหนถูกพูดถึงมากที่สุด", tag: "7.1", cards: [
    ["ค่าวัด และ KPI", bl(["Ticker_mention_count (ครั้ง)", "Ticker Mention Rate = จำนวนกล่าวถึง ÷ ปริมาณ × 100"])],
    ["กราฟในหน้า", bl(["อันดับสินทรัพย์ที่ถูกพูดถึงมากสุด", "แนวโน้มการถูกพูดถึงตามเวลา", "พูดถึงที่ไหน (ชุมชน x ประเภทเนื้อหา)"])]],
    note: "หน้า 2 ตอบ 'สินทรัพย์ใดถูกกล่าวถึงมากที่สุด'. ช่วงเต็ม: BTC-USD 900,891 ครั้ง, TSLA 759,742, NVDA 601,744, SPY 545,960." },
  { key: "p3", title: "หน้า 3 Price and Return: ราคา ผลตอบแทน และความผันผวน", tag: "7.2", cards: [
    ["ค่าวัด และ KPI", bl(["Current Return (%), Volume Z-score ของตลาด, Normalized ATR (%)", "ผลตอบแทนล่วงหน้า 1, 2, 3, 6, 12 ชม."])],
    ["กราฟในหน้า", bl(["ราคา (ปรับค่าแรก = 100 เมื่อเลือกหลายตัว) RSI ATR", "ตารางค่าวัดของสินทรัพย์ที่เลือก", "ผลตอบแทนล่วงหน้า และความผันผวนแยกกลุ่ม"])]],
    note: "หน้า 3 ตอบ 3 คำถามของ 7.2: ราคาและปริมาณเป็นอย่างไร, ผลตอบแทนล่วงหน้าแต่ละกลุ่ม 1/2/3/6/12 ชม., กลุ่มไหนผันผวนสูงสุด. หุ้นและ ETF ไม่มีข้อมูล 12 ชม. เพราะตลาดปิดคั่น." },
  { key: "p4", title: "หน้า 4 Market and Sentiment: ความรู้สึกเทียบกับราคา", tag: "7.3 / 7.5", cards: [
    ["ค่าวัด และ KPI", bl(["Sentiment Score, Sentiment Momentum, Reddit Volume Z-score", "สัดส่วนบวก ลบ กลาง และประเภทส่วนใหญ่"])],
    ["กราฟในหน้า", bl(["ราคา เทียบ ความรู้สึก และเทียบ Volume Z", "ระดับความรู้สึก เทียบ ผลตอบแทน", "สัดส่วนบวก ลบ กลาง รายช่วงเวลา", "ตารางจัดอันดับสินทรัพย์ตามความรู้สึก"])]],
    note: "หน้า 4 คือแดชบอร์ดที่ 1 ของ 7.5 (Market and Sentiment Overview) และตอบคำถาม 7.3 ข้อ 1, 2 และ 4. ตารางอันดับเป็นของเพิ่มตามที่ผู้ใช้สั่ง เพื่อตอบ 'สินทรัพย์ไหนบวกหรือลบสุด'." },
  { key: "p5", title: "หน้า 5 Statistical Analysis: ความสัมพันธ์เชื่อถือได้แค่ไหน", tag: "7.4 / 7.5", cards: [
    ["ค่าวัด และ KPI", bl(["Spearman, Pearson, Historical Win Rate (Binomial Test)", "Logistic Regression: AUC และค่าสัมประสิทธิ์"])],
    ["กราฟในหน้า", bl(["การ์ดสรุป (panel Global)", "heatmap สินทรัพย์ x กรอบเวลา (ค่า / p-value)", "AUC และตัวแปรสรุป", "ความสำคัญ 6 กลุ่มตัวแปร"])]],
    note: "หน้า 5 คือแดชบอร์ดที่ 2 ของ 7.5 ในส่วนผลสถิติ และแสดงผล 7.4 ทั้งหมด. คำนวณสดตามตัวกรอง. ดอกจันใน heatmap คือผ่านค่า p หลังปรับ BH (ส่วนขยาย)." },
  { key: "p6", title: "หน้า 6 Lead and Lag: ใครขยับก่อน ความรู้สึกหรือราคา", tag: "ส่วนขยาย", cards: [
    ["ตอบอะไร", bl(["ความรู้สึกชั่วโมงนี้ สัมพันธ์กับผลตอบแทนของชั่วโมงก่อนหน้าหรือถัดไป", "หลังราคาขึ้นหรือลงแรง ความรู้สึกเปลี่ยนไหม"])],
    ["กราฟในหน้า", bl(["ความรู้สึกหรือราคาเปลี่ยนก่อนกัน (lag)", "ความรู้สึกหลังราคาขึ้นหรือลง (แบ่งช่วงผลตอบแทน)", "คำอธิบาย \"วิธีอ่าน\" ใต้ทุกกราฟ"])]],
    note: "หน้า 6 เป็นส่วนขยายนอก proposal เพื่อตอบ 7.4 ข้อ 3 (ข้อมูลก่อนหน้าดีกว่าปัจจุบันไหม) ให้เห็นภาพ. ต้องติดป้ายส่วนขยายในรายงาน." },
  { key: "p7", title: "หน้า 7 Hot Events: รายการสัญญาณที่ควรตรวจต่อ", tag: "7.6", cards: [
    ["ค่าวัด และตัวกรอง", bl(["Z-score ขั้นต่ำ และ Sentiment ขั้นต่ำ (ผู้ใช้ตั้งเอง)", "จำนวนข้อความขั้นต่ำต่อชั่วโมง และระดับสัญญาณ"])],
    ["กราฟในหน้า", bl(["การ์ดและตารางนับสัญญาณตามประเภท", "รายการสัญญาณล่าสุด 300 รายการ", "Win Rate หลังสัญญาณ (เส้นประ 50%)"])]],
    note: "หน้า 7 คือ Detected Signal List ของระบบ 7.6 (ตารางที่ 18) เชื่อมกับ DimDetectionConfig. มีเพิ่ม Current Return ในกราฟ Win Rate เป็นส่วนขยาย." },
];
pageSlides.forEach((p) => {
  const s = newSlide("LIGHT", "4 แดชบอร์ด");
  head(s, p.title, "4 แดชบอร์ด · " + p.tag);
  card(s, 0.6, 1.5, 5.8, 2.35, p.cards[0][0], p.cards[0][1], { size: 16, headSize: 19 });
  card(s, 0.6, 4.0, 5.8, 2.75, p.cards[1][0], p.cards[1][1], { size: 15, headSize: 19 });
  shot(s, p.key, 6.7, 1.5, 6.1, 5.2, "ภาพหน้าจอจริง ตัวกรองเริ่มต้น (ย้อนหลัง 1 ปี) ตัวเลขต่างจากช่วงเต็ม");
  s.addNotes(p.note);
});

// =============================================================== PART 5: STORIES (live)
{
  const s = newSlide("DARK", "5 เล่าเรื่อง");
  head(s, "เล่าเรื่องพร้อมเปิดแดชบอร์ดจริง ตัวอย่างหลักคือ BTC-USD", "5 เล่าเรื่อง", true);
  const acts = [["1", "ตลาดคุยกันตอนไหน", "หน้า 1"], ["2", "คุยเรื่องอะไร", "หน้า 2"], ["3", "ราคาทำอะไร", "หน้า 3"], ["4", "อารมณ์ไปกับราคาไหม", "หน้า 4"], ["5", "ใครมาก่อน", "หน้า 6"], ["6", "เชื่อถือได้แค่ไหน", "หน้า 5"], ["7", "ใช้อย่างไร", "หน้า 7"]];
  acts.forEach((a, i) => {
    const x = 0.6 + i * 1.77;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.9, w: 1.65, h: 2.3, fill: { color: "16305A" }, line: { color: "2D4B7C", width: 1 }, rectRadius: 0.1, objectName: "Act" + a[0] });
    s.addText(a[0], { x, y: 2.0, w: 1.65, h: 0.7, fontSize: 32, bold: true, color: "7FD6CF", align: "center", margin: 0, isTextBox: true });
    s.addText(a[1], { x: x + 0.08, y: 2.75, w: 1.49, h: 0.9, fontSize: 14, bold: true, color: C.background1, align: "center", margin: 0, isTextBox: true, valign: "top" });
    s.addText(a[2], { x, y: 3.7, w: 1.65, h: 0.4, fontSize: 13, color: "CADCFC", align: "center", margin: 0, isTextBox: true });
  });
  s.addText("ทำไมเลือก BTC-USD", { x: 0.6, y: 4.6, w: 5.0, h: 0.5, fontSize: 20, bold: true, color: C.background1, margin: 0, isTextBox: true });
  s.addText("ถูกกล่าวถึงมากที่สุด (900,891 ครั้ง) ซื้อขายตลอด 24 ชั่วโมง มีผลตอบแทนล่วงหน้าครบทุกกรอบเวลา และเป็นหนึ่งใน 3 ช่องที่ Current Return ผ่านนัยสำคัญหลังปรับ BH", { x: 0.6, y: 5.1, w: 7.3, h: 1.4, fontSize: 16, color: "CADCFC", margin: 0, isTextBox: true, valign: "top" });
  s.addText("ก่อนเปิด: เลือก Ticker = BTC-USD ในแถบซ้าย และเลือกช่วงเวลาให้ชัดเจนทุกหน้า", { x: 8.2, y: 4.6, w: 4.6, h: 1.4, fontSize: 15, bold: true, color: "FFD98A", margin: 0, isTextBox: true, valign: "top" });
  s.addNotes("เตรียมก่อนขึ้น: เปิดแดชบอร์ด (steps/23_run_dashboard.py) และกดผ่านทุกหน้าหนึ่งรอบให้ cache อุ่น. เลือก BTC-USD ซ้ำทุกหน้า. สลับลำดับ: เล่นหน้า 6 Lead and Lag ก่อนหน้า 5 Statistical Analysis เพราะตอบ 'ก่อนหรือหลัง' ตรงกว่า. มีภาพหน้าจอสำรองในสไลด์ส่วนที่ 4 ถ้าจอค้าง.");
}
function act(num, title, openName, steps, say, hasChart) {
  const s = newSlide("LIGHT", "5 เล่าเรื่อง");
  head(s, "เรื่องที่ " + num + ": " + title, "5 เล่าเรื่อง · เปิดจอจริง");
  openPage(s, openName);
  card(s, 0.6, 1.5, 5.9, 2.75, "คลิกตามลำดับ", steps, { size: 16, headSize: 19 });
  card(s, 0.6, 4.4, 5.9, 2.2, "พูดอะไร (มุมการเงิน)", say, { size: 15, headSize: 19, headColor: C.accent1 });
  return s;
}
// Act 1
{
  const s = act("1", "ตลาดคุยกันตอนไหน", "หน้า 1 Reddit Volume (เลือกช่วงเต็ม)",
    bl(["เลือกช่วงเต็ม ทุกชุมชน แล้วดูการ์ด 5 ใบ", "ชี้เส้นแดง Z-score กับเส้นประ 1.5", "หาจุดสูงสุด 9 เม.ย. 2025 17:00 UTC", "ไปหน้า 3 เช็กราคาชั่วโมงเดียวกัน"]),
    bl(["Z-score คือปริมาณผิดปกติเทียบ 24 ชม.ก่อนหน้า เหมือน abnormal volume ในตลาด", "ชั่วโมงพีคตรงกับราคาขยับแรงของหลายสินทรัพย์พร้อมกัน"]));
  s.addChart(pres.charts.BAR, [{ name: "ผลตอบแทนชั่วโมงนั้น (%)", labels: ["BTC-USD", "SPY", "TSLA"], values: [4.959, 2.672, 7.363] }], {
    x: 6.8, y: 1.5, w: 6.0, h: 3.2, barDir: "col", chartColors: [GOLD], showLegend: false, showTitle: true, title: "Current Return ในชั่วโมงที่ข้อความพุ่งสูงสุด (%)", showValue: true, dataLabelPosition: "outEnd",
    dataLabelFormatCode: "0.00", valAxisHidden: true, valGridLine: { style: "none" }, valAxisMinVal: 0, ...chartCommon });
  stat(s, 6.8, 4.85, 2.9, "17,362", "ข้อความในชั่วโมงเดียว (เฉลี่ย 1,311) 9 เม.ย. 2025 17:00 UTC", C.accent2);
  stat(s, 9.9, 4.85, 2.9, "1,968", "ชั่วโมงที่ Z-score เกิน 1.5 จากทั้งช่วง", C.accent2);
  s.addNotes("เรื่องที่ 1 (ประมาณ 2 นาที). เปิดหน้า 1 Reddit Volume เลือกช่วงเต็ม: การ์ด รวม 22,029,119 / เฉลี่ย 1,311 ต่อชม. / สูงสุด 17,362 (2025-04-09 17:00 UTC) / Z สูงสุด 92.14 / ชม. Z>1.5 = 1,968. จุดที่ตรวจเองจากฐานข้อมูล (market_hourly_features): ในชั่วโมงเดียวกันนั้น Current Return ของ BTC-USD +4.96%, SPY +2.67% (บาร์ 17:30), TSLA +7.36% (บาร์ 17:30). ตัวเลขราคายืนยันจากข้อมูล แต่สาเหตุ (ข่าวของตลาดวันนั้น) ยังไม่ได้พิสูจน์ในระบบ ให้พูดว่า 'สอดคล้องกับ' ไม่ใช่ 'เพราะ'. ถ้าถูกถาม: Z-score ของชั่วโมงนี้เทียบ 24 ชม.ก่อนหน้า ไม่รวมชั่วโมงนี้. ประโยคเชื่อม: คนคุยกันมากตอนไหนเห็นแล้ว ต่อไปคุยเรื่องอะไร.");
}
// Act 2
{
  const s = act("2", "คุยกันเรื่องอะไร", "หน้า 2 Ticker Mentions (เลือก BTC-USD)",
    bl(["ดูแท่งอันดับสินทรัพย์ที่ถูกพูดถึงมากสุด", "เลือก BTC-USD ดูแนวโน้มการถูกพูดถึง", "ดูตารางชุมชน x ประเภทเนื้อหา"]),
    bl(["ความสนใจรายย่อยกระจุกที่ไม่กี่ชื่อ", "สินทรัพย์ที่ถูกพูดถึงมากมีข้อมูลพอให้วัดความรู้สึกได้น่าเชื่อกว่า"]));
  const names = ["MSTR", "AAPL", "AMD", "ETH-USD", "MSFT", "GC=F", "SPY", "NVDA", "TSLA", "BTC-USD"], vals = [165173, 169589, 169937, 208030, 213956, 289269, 545960, 601744, 759742, 900891];
  s.addChart(pres.charts.BAR, [{ name: "การกล่าวถึง", labels: names, values: vals }], {
    x: 6.8, y: 1.5, w: 6.0, h: 5.1, barDir: "bar", chartColors: names.map((n) => (n === "BTC-USD" ? RED : TEAL)), invertedColors: [TEAL], showLegend: false, showTitle: true, title: "10 อันดับที่ถูกพูดถึงมากสุด (ครั้ง)",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "#,##0", valAxisHidden: true, valGridLine: { style: "none" }, valAxisMaxVal: 1150000, ...chartCommon });
  s.addNotes("เรื่องที่ 2 (ประมาณ 1.5 นาที). หน้า 2 Ticker Mentions: BTC-USD ถูกกล่าวถึง 900,891 ครั้ง (Mention Rate 4.09%), TSLA 759,742, NVDA 601,744, SPY 545,960. ตัวเลขช่วงเต็มจาก dashboard_answers.md. ตัวกรองเริ่มต้นย้อนหลัง 1 ปีจะให้ตัวเลขต่างไป ให้เลือกช่วงเต็มก่อน. ชี้ตาราง ชุมชน x ประเภทเนื้อหา: wallstreetbets ครอง 73.2% ของข้อความ. ประโยคเชื่อม: รู้แล้วว่าพูดถึงอะไร ต่อไปราคาทำอะไร.");
}
// Act 3
{
  const s = act("3", "ราคาทำอะไร", "หน้า 3 Price and Return (เลือก BTC-USD)",
    bl(["ดูกราฟราคา RSI และ ATR ของ BTC-USD", "ดูตารางค่าวัด (Current Return, ATR, ผลตอบแทนล่วงหน้า)", "ติ๊กหลายตัว ราคาจะปรับให้ค่าแรก = 100", "ดูผลตอบแทนล่วงหน้าและความผันผวนแยกกลุ่ม"]),
    bl(["Current Return = ln(ราคาปิดชั่วโมงนี้ ÷ ก่อนหน้า) × 100", "ผลตอบแทนล่วงหน้าเฉลี่ยใกล้ 0 สัดส่วนที่ราคาขึ้นราว 50 ถึง 52%"]));
  stat(s, 6.8, 1.5, 2.9, "+23.7%", "BTC-USD ราคาปิดแรก 63,491 เป็นแท่งสุดท้าย 78,563 (ช่วงเต็ม)", C.accent1);
  stat(s, 9.9, 1.5, 2.9, "0.58%", "ความผันผวนเฉลี่ย (Normalized ATR) ของ BTC-USD ต่อชั่วโมง", C.accent3);
  s.addChart(pres.charts.BAR, [{ name: "ATR (%)", labels: ["หุ้นและ ETF", "คริปโต", "ฟิวเจอร์ส"], values: [1.1661, 0.8758, 0.5309] }], {
    x: 6.8, y: 3.5, w: 6.0, h: 3.1, barDir: "col", chartColors: [GOLD], showLegend: false, showTitle: true, title: "ความผันผวนเฉลี่ยตามกลุ่ม (Normalized ATR %)", showValue: true, dataLabelPosition: "outEnd",
    dataLabelFormatCode: "0.00", valAxisHidden: true, valGridLine: { style: "none" }, valAxisMinVal: 0, ...chartCommon });
  s.addNotes("เรื่องที่ 3 (ประมาณ 2 นาที). หน้า 3 Price and Return: BTC-USD ราคาปิดแท่งแรก 63,491.17 แท่งสุดท้าย 78,562.73 (+23.7%) Normalized ATR เฉลี่ย 0.5753%. ผลตอบแทนล่วงหน้าเฉลี่ยของ BTC ใกล้ 0 (1 ชม. 0.0024%, 12 ชม. 0.0291%). ความผันผวนตามกลุ่ม (ข้อ 3 ของ 7.2): หุ้นและ ETF 1.17%, คริปโต 0.88%, ฟิวเจอร์ส 0.53%. หุ้นและ ETF ไม่มี 12 ชม. เพราะตลาดปิดคั่น (ตัวอย่างน้อยที่ 6 ชม.). ประโยคเชื่อม: ถึงเวลานำความรู้สึกมาวางเทียบกับราคา.");
}
// Act 4
{
  const s = act("4", "อารมณ์ไปกับราคาไหม", "หน้า 4 Market and Sentiment (เลือก BTC-USD)",
    bl(["กราฟราคา เทียบ ความรู้สึก", "กราฟ Volume Z เทียบ ความรู้สึก", "กราฟระดับความรู้สึก เทียบ ผลตอบแทน (อ่านกล่อง วิธีอ่าน)", "เลื่อนลงดูสัดส่วนบวก ลบ กลาง และตารางอันดับ (ติ๊กหลายตัว)"]),
    bl(["ความรู้สึกคือความเห็นต่อข่าวและราคา ไม่ใช่การคาดการณ์ทิศทาง", "ติดลบ ไม่ได้แปลว่าราคาจะลง"]));
  const names = ["CL=F", "ES=F", "SPY", "BTC-USD", "KO", "SHIB-USD", "NG=F"], vals = [-0.217, -0.116, -0.0095, 0.0261, 0.1143, 0.1212, 0.1214];
  s.addChart(pres.charts.BAR, [{ name: "Sentiment Score", labels: names, values: vals }], {
    x: 6.8, y: 1.5, w: 6.0, h: 4.0, barDir: "bar", chartColors: vals.map((v) => (v >= 0 ? GREEN : RED)), invertedColors: [RED], showLegend: false, showTitle: true, title: "Sentiment Score เฉลี่ย (ข้อความ >= 1,000)",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "+0.000;-0.000", valAxisHidden: true, valGridLine: { style: "none" }, valAxisMinVal: -0.3, valAxisMaxVal: 0.2, catAxisLabelPos: "low", ...chartCommon });
  s.addText("BTC-USD: Sentiment +0.026, บวก 41.0%, ลบ 33.8% จากข้อความ 607,251 ชิ้น", { x: 6.8, y: 5.65, w: 6.0, h: 0.9, fontSize: 15, bold: true, color: C.text2, margin: 0, isTextBox: true, valign: "top" });
  s.addNotes("เรื่องที่ 4 (ประมาณ 3 นาที, หน้าแกนของเรื่อง). หน้า 4: ติ๊ก BTC-USD ดูกราฟราคาปิดเทียบ Sentiment Score เฉลี่ย, Volume Z เทียบความรู้สึก, ราคาเทียบ Volume Z, ระดับความรู้สึกกับผลตอบแทน, สัดส่วนบวก/ลบ/กลาง. ตารางอันดับ (ช่วงเต็ม ขั้นต่ำ 1,000 ข้อความ): บวกสุด NG=F +0.1214, SHIB-USD +0.1212, KO +0.1143; ลบสุด CL=F -0.217, ES=F -0.116, NQ=F -0.090. BTC-USD +0.0261 อยู่อันดับ 20 จาก 33 สินทรัพย์ที่ผ่านเกณฑ์ (BITO ถูกตัดเพราะ 645 ข้อความ). น้ำมัน CL=F ลบสุด ยังไม่ทราบสาเหตุ ห้ามอ้างเหตุผลโดยไม่มีหลักฐาน. ประโยคเชื่อม: เห็นว่าไปด้วยกัน แต่ใครมาก่อน.");
}
// Act 5
{
  const s = act("5", "ใครขยับก่อน", "หน้า 6 Lead and Lag (เลือก BTC-USD)",
    bl(["ดูกราฟ lag: ความรู้สึกสัมพันธ์กับผลตอบแทนชั่วโมงก่อนหรือหลัง", "ดูกราฟความรู้สึกหลังราคาขึ้นหรือลง", "อ่านตามกล่อง วิธีอ่าน ใต้กราฟ"]),
    bl(["ถ้าความรู้สึกนำราคา ใช้เป็นสัญญาณได้", "ถ้าตามราคา ก็คือไล่ตาม momentum ซึ่งไม่ช่วยให้ไม่ตกรถ"]));
  s.addChart(pres.charts.BAR, [{ name: "Spearman rho", labels: ["Current Return", "ล่วงหน้า 1 ชม.", "2 ชม.", "3 ชม.", "6 ชม.", "12 ชม."], values: [0.0232, -0.0032, -0.0084, -0.0101, -0.0131, -0.0029] }], {
    x: 6.8, y: 1.5, w: 6.0, h: 3.9, barDir: "col", chartColors: [0.0232, -0.0032, -0.0084, -0.0101, -0.0131, -0.0029].map((v) => (v >= 0 ? GREEN : RED)), invertedColors: [RED], showLegend: false, showTitle: true,
    title: "BTC-USD: ความรู้สึก เทียบ ผลตอบแทน (Spearman rho)", showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "+0.000;-0.000", valAxisHidden: true, valGridLine: { style: "none" }, valAxisMinVal: -0.03, valAxisMaxVal: 0.035, catAxisLabelPos: "low", catAxisLabelFontSize: 11, ...chartCommon });
  s.addText("มีแค่ Current Return ที่ผ่านนัยสำคัญหลังปรับ BH (p = 0.036) ผลตอบแทนล่วงหน้าทุกกรอบไม่ผ่าน และค่า rho เล็กมาก (ไม่เกิน 0.023)", { x: 6.8, y: 5.55, w: 6.0, h: 1.1, fontSize: 15, bold: true, color: C.text2, margin: 0, isTextBox: true, valign: "top" });
  s.addNotes("เรื่องที่ 5 (ประมาณ 2.5 นาที). ข้ามมาหน้า 6 ก่อนหน้า 5. ตัวเลข BTC-USD (panel_Ticker, sentiment_mean, Spearman) จาก analysis_results: Current Return +0.0232 (p ดิบ 0.0027, BH 0.0363), ล่วงหน้า 1h -0.0032 (BH 0.92), 2h -0.0084, 3h -0.0101, 6h -0.0131 (BH 0.49), 12h -0.0029. ภาพรวม 34 สินทรัพย์: Current Return เป็นบวก 28 จาก 34 และผ่าน BH 3 ช่อง (BTC-USD, GC=F, SPY). ผลตอบแทนอนาคต 147 ช่อง ผ่าน BH 0 ช่อง. ความรู้สึก lag 1 ชั่วโมงแรงกว่าปัจจุบันเพียง 15 จาก 40 ช่อง |rho| สูงสุด 0.023. สรุป: ความรู้สึกไปพร้อมราคาที่เพิ่งเกิด แต่ยังไม่พิสูจน์ว่าใครเป็นเหตุของใคร. ข้อมูลรายชั่วโมงสัมพันธ์กันเอง ค่า p ใช้ประกอบ.");
}
// Act 6
{
  const s = act("6", "เชื่อถือได้แค่ไหน", "หน้า 5 Statistical Analysis",
    bl(["ดูการ์ดสรุปด้านบน (panel Global)", "heatmap: สลับ ค่า / p-value, Spearman / Pearson / Win Rate", "ดู AUC แล้วดูความสำคัญ 6 กลุ่มตัวแปร", "ไม่ต้องเปิดทุกกราฟ เน้น heatmap กับ AUC"]),
    bl(["ทดสอบหลายร้อยช่อง ย่อมเจอบางช่องดีโดยบังเอิญ (data snooping)", "AUC 0.5 คือเท่ากับการเดา"]));
  s.addChart(pres.charts.BAR, [{ name: "AUC เฉลี่ย", labels: ["baseline (สุ่ม)", "ราย Ticker", "ราย Ticker คุณภาพ", "รวม Global", "รวม Global คุณภาพ", "รวม Global spike"], values: [0.5002, 0.5004, 0.4976, 0.5036, 0.503, 0.5048] }], {
    x: 6.8, y: 1.5, w: 6.0, h: 3.7, barDir: "bar", chartColors: [TEAL], showLegend: false, showTitle: true, title: "AUC เฉลี่ยของ Logistic (0.5 = เดา)", showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.000",
    valAxisMinVal: 0.45, valAxisMaxVal: 0.55, valAxisHidden: true, valGridLine: { style: "none" }, catAxisOrientation: "maxMin", ...chartCommon });
  stat(s, 6.8, 5.3, 2.9, "96.6%", "ของ 147 ช่อง Spearman มี |rho| ต่ำกว่า 0.1", C.accent2, 32);
  stat(s, 9.9, 5.3, 2.9, "0 ช่อง", "ผลตอบแทนอนาคตที่ผ่าน BH (ผ่านก่อนปรับ 7 ช่อง)", C.accent2, 32);
  s.addNotes("เรื่องที่ 6 (ประมาณ 3 นาที, หน้าหนักสุด). ตัวเลขจาก t7 และ t12: panel_Ticker mean AUC 0.5004, panel_global 0.5036, baseline 0.5002. Win Rate 43.1% ถึง 55.1% (ผ่าน BH 2 ช่อง). AUC อนาคต 0.488-0.510, Current Return 0.509-0.536. ระดับรวม Global มีช่องผ่านมากกว่า (17 จาก 148) เพราะแถวเยอะมาก ค่า p เล็กง่ายแม้ขนาดผลเล็ก ให้พูดขนาดผลไม่ใช่แค่ค่า p. ภาพสำรอง: output/figures/a1_panel_Ticker_spearman.png และ a3_auc.png. BH เป็นส่วนขยาย (METHOD_DECISIONS ข้อ 15).");
}
// Act 7
{
  const s = act("7", "ใช้อย่างไรในทางปฏิบัติ", "หน้า 7 Hot Events",
    bl(["ตั้ง Z-score ขั้นต่ำ 1.5 และ Sentiment ขั้นต่ำ 0.05", "ดูตารางนับสัญญาณตามประเภท", "ไล่รายการล่าสุด แล้วเลือกแถว BTC-USD", "ดูกราฟ Win Rate หลังสัญญาณ ชี้เส้นประ 50%", "ลองเพิ่ม Z เป็น 2.5 ดูจำนวนลด"]),
    bl(["คือ event study แบบง่าย: หลังเหตุการณ์ผิดปกติ ราคาทำอะไร", "ผลใกล้ 50% จึงใช้เฝ้าดู ไม่ใช่สั่งซื้อ"]));
  s.addChart(pres.charts.BAR, [
    { name: "Sentiment >= 0.05", labels: ["Z 1.5", "Z 2.0", "Z 2.5"], values: [15060, 11062, 8361] },
    { name: "Sentiment >= 0.30", labels: ["Z 1.5", "Z 2.0", "Z 2.5"], values: [2086, 1660, 1315] }], {
    x: 6.8, y: 1.5, w: 6.0, h: 3.7, barDir: "col", chartColors: [GOLD, BLUE], showLegend: true, legendPos: "b", showTitle: true, title: "สัญญาณ Combined (ชั่วโมง x สินทรัพย์) ตามเกณฑ์", showValue: true, dataLabelPosition: "outEnd",
    dataLabelFormatCode: "#,##0", valAxisHidden: true, valGridLine: { style: "none" }, valAxisMaxVal: 18000, ...chartCommon });
  s.addText("BTC-USD (Z 1.5, Sentiment 0.05): บวกพุ่ง 6,515 · ลบพุ่ง 3,868 · Combined 1,286 · ปริมาณพุ่ง 590 ครั้ง", { x: 6.8, y: 5.4, w: 6.0, h: 1.2, fontSize: 15, bold: true, color: C.text2, margin: 0, isTextBox: true, valign: "top" });
  s.addNotes("เรื่องที่ 7 (ประมาณ 2.5 นาที). หน้า 7 Hot Events: ตัวเลขสัญญาณจาก t9_signal_counts.csv และตาราง signal_events. ทั้ง 34 สินทรัพย์ (Z 1.5, S 0.05): บวกพุ่ง 28,398, ลบพุ่ง 18,426, ปริมาณพุ่ง 16,234, Combined 15,060. BTC-USD: 6,515 / 3,868 / 590 / 1,286. เกณฑ์เข้มขึ้น สัญญาณลดลง: Combined 15,060 (Z 1.5) -> 11,062 (2.0) -> 8,361 (2.5) ที่ S 0.05, และ 2,086 -> 1,660 -> 1,315 ที่ S 0.30. กราฟ Win Rate หลังสัญญาณคำนวณสดตามตัวกรอง ให้อ่านจากจอ. ปิดเรื่อง: ความรู้สึกเป็นภาพสะท้อนของตลาด ไม่ใช่ตัวชี้นำ.");
}

// =============================================================== PART 6: EXECUTIVE QUESTIONS
function qslide(title, tag, rows, note) {
  const s = newSlide("LIGHT", "6 คำถามผู้บริหาร");
  head(s, title, "6 คำถามผู้บริหาร · " + tag);
  table(s, rows, { x: 0.5, y: 1.45, w: 12.35, colW: [3.4, 5.6, 3.35], fontSize: 14, rowH: 0.8 });
  s.addNotes(note);
  return s;
}
qslide("ระบบ 7.1 และ 7.2: ตอบ 5 คำถาม", "7.1 / 7.2", [
  ["คำถามผู้บริหาร", "คำตอบจากข้อมูล (ช่วงเต็ม)", "ดูที่ไหน"],
  ["สินทรัพย์ใดถูกกล่าวถึงมากที่สุด", "BTC-USD 900,891 ครั้ง (4.09%) รองลงมา TSLA, NVDA, SPY", "หน้า 2 กราฟแท่งอันดับ"],
  ["ปริมาณรายชั่วโมงเพิ่มหรือลด", "ไม่มีแนวโน้มชัด (rho -0.060, p 0.111 บน 700 วัน) เฉลี่ย 1,311 ต่อชม. สูงสุดเม.ย. 2025", "หน้า 1 กราฟปริมาณ และ Z-score"],
  ["ราคาและปริมาณซื้อขายเป็นอย่างไร", "ตัวอย่าง BTC-USD ปิดแรก 63,491 เป็น 78,563 (+23.7%)", "หน้า 3 ราคา RSI ATR ตารางค่าวัด"],
  ["ผลตอบแทนล่วงหน้าแต่ละกลุ่ม 1/2/3/6/12 ชม.", "ค่าเฉลี่ยใกล้ 0 สัดส่วนที่ราคาขึ้น 49.9 ถึง 52.5% หุ้นและ ETF ข้อมูล 6 ชม.น้อย 12 ชม.ไม่มี", "หน้า 3 ผลตอบแทนล่วงหน้าแยกกลุ่ม"],
  ["กลุ่มใดผันผวนสูงสุด", "หุ้นและ ETF 1.17% > คริปโต 0.88% > ฟิวเจอร์ส 0.53% (Normalized ATR)", "หน้า 3 ความผันผวนแยกกลุ่ม"]],
  "ตารางสรุปคำถามผู้บริหาร 7.1 (2 ข้อ) และ 7.2 (3 ข้อ แต่ข้อผลตอบแทนล่วงหน้าแยกกลุ่มและความผันผวนเป็นข้อแยก). แนวโน้มปริมาณรายวัน (Spearman) เป็นส่วนขยาย. ตัวเลขจาก dashboard_answers.md.");
qslide("ระบบ 7.3: ตอบ 4 คำถามเรื่องความรู้สึก", "7.3", [
  ["คำถามผู้บริหาร", "คำตอบจากข้อมูล (ช่วงเต็ม)", "ดูที่ไหน"],
  ["ความรู้สึกรวมเป็นบวกหรือลบ", "สมดุล เอียงลบเล็กน้อย: บวก 32.4% กลาง 32.9% ลบ 34.7%", "หน้า 4 สัดส่วนบวก ลบ กลาง และ Home"],
  ["สินทรัพย์ใดบวกหรือลบมากที่สุด", "บวก: NG=F +0.121, SHIB-USD +0.121, KO +0.114 / ลบ: CL=F -0.217, ES=F -0.116, NQ=F -0.090", "หน้า 4 ตารางจัดอันดับ"],
  ["VADER และ FinBERT สอดคล้องแค่ไหน แก้ขัดแย้งอย่างไร", "ทิศเดียวกัน 50.2% ตัวหนึ่งกลาง 37.6% ตรงข้าม 12.3% แก้ด้วยกฎรวมผล และคำสำคัญ", "ตาราง t3 (final_method) และสไลด์ระบบ 3"],
  ["สัดส่วนบวก ลบ กลาง แต่ละชั่วโมง", "ดูกราฟพื้นที่สัดส่วนตามเวลา เลือกระดับชั่วโมงถึงปี", "หน้า 4 กราฟสัดส่วน"]],
  "ตัวเลขข้อ 1 จาก t2_sentiment_distribution.csv (ผลสุดท้าย). ข้อ 3 จาก t3_final_method.csv. ข้อ 3 ไม่มีกราฟบนแดชบอร์ดโดยตรง ตอบจากตารางรายงานระบบ 3.");
qslide("ระบบ 7.4: ตอบ 4 คำถามความสัมพันธ์", "7.4", [
  ["คำถามผู้บริหาร", "คำตอบจากข้อมูล", "ดูที่ไหน"],
  ["ความรู้สึกสอดคล้องกับทิศทางราคาอนาคตอย่างไร", "ไม่สอดคล้อง: 96.6% ของ 147 ช่อง |rho| < 0.1, ผ่าน BH 0 ช่อง, Win Rate 43.1 ถึง 55.1%, AUC 0.488 ถึง 0.510", "หน้า 5 heatmap และ AUC"],
  ["รูปแบบต่างกันตามกลุ่มสินทรัพย์ไหม", "ไม่ต่างอย่างมีนัย: AUC ทุกกลุ่ม 0.489 ถึง 0.506", "หน้า 5 กรองกลุ่มสินทรัพย์"],
  ["ข้อมูลก่อนหน้า (lag) ดีกว่าปัจจุบันไหม", "ไม่ดีกว่า: lag 1 ชม.แรงกว่าเพียง 15 จาก 40 ช่อง |rho| สูงสุด 0.023", "หน้า 6 และหน้า 5"],
  ["ปัจจัยใดควรให้น้ำหนักมากสุด", "Lag (0.056) > Direction (0.049) > Level (0.045) > Vote (0.030) > Volume (0.017) > Momentum (0.009) แต่ AUC ≈ 0.5 จึงไม่ควรอ่านเป็นสัญญาณ", "หน้า 5 ความสำคัญ 6 กลุ่มตัวแปร"]],
  "ตัวเลขจาก t12_relationship_key_numbers.csv, t8_asset_class_results.csv (AUC รายกลุ่ม: crypto 0.4993-0.5064, futures 0.4893-0.5009, stock_etf 0.4954-0.5045) และตาราง evaluation_factor_importance (panel_Ticker รวมทุกกลุ่ม ค่าเฉลี่ย |ค่าสัมประสิทธิ์| ของ 6 กลุ่มตัวแปร). ข้อ 4 ต้องระวัง: น้ำหนักสูงไม่ได้แปลว่าทำนายได้ เพราะโมเดลโดยรวมไม่ดีกว่าเดา.");
qslide("ระบบ 7.5 และ 7.6: ตอบคำถามสัญญาณและเกณฑ์", "7.5 / 7.6", [
  ["คำถามผู้บริหาร", "คำตอบจากข้อมูล", "ดูที่ไหน"],
  ["สินทรัพย์ใดมี Z-score หรือความรู้สึกสูงกว่าปกติ", "ชั่วโมงที่ Reddit รวมมี Z > 1.5 มี 1,968 ชั่วโมง ระดับสินทรัพย์ดูตามตัวกรอง", "หน้า 1, 2, 4 และ Home"],
  ["Win Rate และความสัมพันธ์รายสินทรัพย์", "Win Rate 43.1 ถึง 55.1% ผ่าน BH 2 ช่อง Current Return เป็นบวก 28 จาก 34 สินทรัพย์", "หน้า 5 heatmap Win Rate"],
  ["สัญญาณที่ตรวจพบเป็นประเภทไหน", "บวกพุ่ง 28,398 · ลบพุ่ง 18,426 · ปริมาณพุ่ง 16,234 · Combined 15,060 (Z 1.5, S 0.05)", "หน้า 7 ตารางนับสัญญาณ"],
  ["สถิติย้อนหลังของสินทรัพย์ที่ตรวจพบ", "Win Rate เฉลี่ยของกลุ่ม spike 49.9% ใกล้เดา อ่านค่าสดจากกราฟหลังสัญญาณ", "หน้า 7 กราฟ Win Rate หลังสัญญาณ"],
  ["เกณฑ์ส่งผลต่อจำนวนอย่างไร", "เข้มขึ้นสัญญาณลดลง: Combined 15,060 → 8,361 (Z 1.5 → 2.5) และ → 2,086 (S 0.05 → 0.30)", "หน้า 7 ตัวกรอง Z และ Sentiment"]],
  "ตัวเลขสัญญาณจาก t9_signal_counts.csv. Win Rate เฉลี่ย panel_Ticker_spike = 49.87% (t7_panel_results.csv). ข้อ 'สถิติย้อนหลัง' กราฟบนหน้า 7 คำนวณสดตามตัวกรอง ให้อ่านจากจอในวันพรีเซนต์.");
{
  const s = newSlide("DARK", "6 คำถามผู้บริหาร");
  head(s, "คำตอบรวม: ความรู้สึกบน Reddit บอกตลาดตอนนี้ แต่ไม่ได้บอกตลาดข้างหน้า", "6 คำถามผู้บริหาร", true);
  const cols = [["บอกได้", GREEN, ["ตลาดกำลังคุยเรื่องอะไรผิดปกติ (Z-score)", "สินทรัพย์ไหนอยู่ในความสนใจ", "อารมณ์ไปพร้อมราคาที่เพิ่งเกิด (28 จาก 34 เป็นบวก)"]],
    ["บอกไม่ได้", RED, ["ทิศทางราคาข้างหน้า (AUC ≈ 0.5, Win Rate ≈ 50%)", "จังหวะซื้อขายที่ทำกำไรได้", "สาเหตุของการขยับราคา"]],
    ["จึงใช้เป็น", GOLD, ["เครื่องมือเฝ้าดูความสนใจและอารมณ์ตลาด", "จุดเริ่มต้นของการตรวจเชิงลึกต่อ", "ตัวเตือนเรื่อง FOMO"]]];
  cols.forEach((c, i) => {
    const x = 0.6 + i * 4.1;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.6, w: 3.9, h: 4.6, fill: { color: "16305A" }, line: { color: "2D4B7C", width: 1 }, objectName: "Sum" + i });
    s.addText(c[0], { x: x + 0.25, y: 1.8, w: 3.4, h: 0.6, fontSize: 24, bold: true, color: c[1] === GOLD ? "FFD98A" : (c[1] === GREEN ? "7FE0B0" : "FF9A92"), margin: 0, isTextBox: true });
    s.addText(c[2].map((t, k) => ({ text: t, options: { bullet: true, breakLine: k < c[2].length - 1 } })), { x: x + 0.25, y: 2.55, w: 3.4, h: 3.5, fontSize: 16, color: C.background1, margin: 0, isTextBox: true, valign: "top", paraSpaceAfter: 8 });
  });
  s.addText("ย้อนไปที่ pain point: ข้อมูลนี้ไม่ได้ทำให้ไม่ตกรถ แต่ช่วยให้รู้ว่ากำลังไล่ตามความตื่นเต้น ไม่ใช่ตามสัญญาณ", { x: 0.6, y: 6.4, w: 12.1, h: 0.6, fontSize: 16, bold: true, color: "CADCFC", margin: 0, isTextBox: true });
  s.addNotes("สรุปคำตอบรวมของทุกคำถามผู้บริหารใน 3 คอลัมน์. คำตอบที่ตรงไปตรงมาแบบนี้ตรวจสอบได้ และสอดคล้องกับ 3_final_summary.md: ไม่พบความสามารถทำนายทิศทางราคาจากความรู้สึกบน Reddit.");
}

// =============================================================== PART 7: QA
{
  const s = newSlide("LIGHT", "7 QA");
  head(s, "QA: ระบบผ่านการทดสอบ 3 ส่วนตาม proposal ข้อ 8.4", "7 QA");
  stat(s, 0.6, 1.6, 2.9, "32 / 32", "ตรวจข้อมูลจริง: ตรรกะข้อมูล และความเชื่อมโยงของตาราง (system_tests)", C.accent1, 40);
  stat(s, 3.7, 1.6, 2.9, "371 / 371", "ตัวเลขบนแดชบอร์ดตรงกับ SQL อิสระ (dashboard_kpi_check)", C.accent1, 40);
  stat(s, 6.8, 1.6, 2.9, "81 / 81", "ค่าวัดและ KPI ตามตารางของ proposal พบครบ ไม่พบช่องโหว่", C.accent1, 40);
  stat(s, 9.9, 1.6, 2.9, "237", "Unit test ผ่านทั้งหมด (รันเมื่อ 7 พ.ย. 2026)", C.accent1, 40);
  card(s, 0.6, 3.75, 3.9, 2.9, "Unit และ Logic", bl(["คะแนนอยู่ในช่วง −1 ถึง +1 ไม่เป็น NULL", "สถานะตรงกับเกณฑ์ ±0.05", "Current Return และ Future Return คำนวณซ้ำจากราคาแล้วตรงกัน"]), { size: 13, headSize: 17 });
  card(s, 4.7, 3.75, 3.9, 2.9, "Integration", bl(["ไม่มีแถวซ้ำใน key ของ Fact", "ทุก TimeID/TickerID มีในมิติ", "ผลรวมรายชั่วโมงเท่ากับจำนวนข้อความที่ผ่านตัวกรอง"]), { size: 13, headSize: 17 });
  card(s, 8.8, 3.75, 3.9, 2.9, "Dashboard", bl(["เทียบตัวเลขแต่ละหน้ากับ SQL ตรงบนฐานข้อมูล", "ครอบคลุมทั้ง 7 หน้า", "ตรวจว่าทุกค่าวัดใน proposal แสดงบนหน้าจอ"]), { size: 13, headSize: 17 });
  s.addNotes("QA เชิงระบบ (ตัวเลขจากไฟล์): output/reports/system_tests.md ผ่าน 32 จาก 32 (สร้าง 2026-10-25); output/reports/dashboard_kpi_check.md ผ่าน 371 จาก 371 (2026-10-30); output/reports/proposal_coverage.md ครบ 2+9+22+11+26+11 = 81 รายการ ไม่พบช่องโหว่ (2026-10-30); unittest 237 ตัว ผ่านทั้งหมดที่รันเมื่อ 2026-11-07 ในเครื่องนี้. ข้อจำกัดของ QA: ตรวจความถูกต้องของการคำนวณและการเชื่อมข้อมูล ไม่ได้ตรวจว่าความรู้สึกถูกต้องแค่ไหน (เรื่องนั้นคือการทดสอบกฎรวมผล 400 ข้อความ).");
}
{
  const s = newSlide("LIGHT", "7 QA");
  head(s, "คำถามที่น่าจะถูกถาม (1/2)", "7 QA");
  card(s, 0.6, 1.5, 6.0, 2.5, "ทำนายไม่ได้ แล้วระบบมีประโยชน์อะไร", ["เป็นเครื่องมือเฝ้าดูความสนใจและอารมณ์ตลาด และเป็นจุดเริ่มตรวจต่อ ผลว่า \"ไม่พบสัญญาณ\" ที่ตรวจสอบได้ก็ช่วยกันไม่ให้ไล่ตามสัญญาณที่ไม่มี"], { size: 14, headSize: 17 });
  card(s, 6.8, 1.5, 5.9, 2.5, "ทำไมต้องปรับค่า p ด้วย BH", ["ทดสอบ 147 ช่อง คาดว่าผ่านโดยบังเอิญราว 7 ช่อง ตรงกับที่ผ่านก่อนปรับ 7 ช่อง หลังปรับเหลือ 0 (เป็นส่วนขยาย ผู้ใช้เลือกคงไว้)"], { size: 14, headSize: 17 });
  card(s, 0.6, 4.2, 6.0, 2.45, "ข้อมูล Reddit เป็นตัวแทนตลาดไหม", ["ไม่ทั้งหมด: wallstreetbets คิดเป็น 73.2% ของข้อความ ภาพรวมจึงเป็นบรรยากาศของนักลงทุนรายย่อยกลุ่มนั้นเป็นหลัก (ข้อจำกัดที่เขียนในเล่ม)"], { size: 14, headSize: 17 });
  card(s, 6.8, 4.2, 5.9, 2.45, "ข้อมูลรายชั่วโมงสัมพันธ์กันเอง กระทบอะไร", ["ผลตอบแทนต่างกรอบเวลาซ้อนทับกัน และข้อมูลต่อเนื่องกัน ค่า p จึงใช้ประกอบการตีความ ไม่ใช่ตัวตัดสิน และดูขนาดผลควบคู่เสมอ"], { size: 14, headSize: 17 });
  s.addNotes("เตรียมตอบ 4 คำถามแรก. ตัวเลข BH จาก t12 และ METHOD_DECISIONS ข้อ 15. สัดส่วน wallstreetbets จาก 3_final_summary.md (Step 05).");
}
{
  const s = newSlide("LIGHT", "7 QA");
  head(s, "คำถามที่น่าจะถูกถาม (2/2)", "7 QA");
  card(s, 0.6, 1.5, 6.0, 2.5, "ความแม่นของความรู้สึก 47% ต่ำไหม", ["ต่ำถ้ามองเป็นคะแนนสอบ แต่วัดกับท่าทีของผู้เขียนคอมเมนต์ ป้ายกลางมี 163 จาก 400 ผู้ติดป้ายคนเดียว จึงรายงานเป็นข้อจำกัดและคงกฎตามเกณฑ์ที่ตั้งไว้ก่อน"], { size: 14, headSize: 17 });
  card(s, 6.8, 1.5, 5.9, 2.5, "ถ้าเปลี่ยนเกณฑ์ ผลเปลี่ยนไหม", ["ทดสอบแล้ว: neutral ±0.10 ทำให้ FinBERT 47.9 เป็น 50.3% แต่กฎรวมผล 47.1 เป็น 45.2% จึงคง ±0.05 และเกณฑ์สัญญาณที่เข้มขึ้นไม่ทำให้ Win Rate ดีกว่าสุ่ม"], { size: 14, headSize: 17 });
  card(s, 0.6, 4.2, 6.0, 2.45, "นำไปเทรดได้ไหม ต้นทุนเท่าไร", ["ไม่แนะนำ ผลไม่เหนือการเดา และยังไม่ได้รวมค่าธรรมเนียมหรือ slippage งานนี้เป็นข้อมูลสนับสนุนการวิเคราะห์ ไม่ใช่กลยุทธ์ทำกำไร"], { size: 14, headSize: 17 });
  card(s, 6.8, 4.2, 5.9, 2.45, "ทำไมเป็นข้อมูลย้อนหลัง ไม่ real-time", ["ตาม proposal: ใช้ข้อมูลย้อนหลังจาก Academic Torrents และ yfinance (730 วัน) เพื่อวิเคราะห์ความสัมพันธ์ ข้อมูลสดเป็นงานต่อยอด"], { size: 14, headSize: 17 });
  s.addNotes("ตัวเลข neutral band จาก band_and_confusion.md และ neutral_band_sensitivity.md: FinBERT 47.9 -> 50.3%, final 47.1 -> 45.2% ที่ ±0.10. ตัวเลขเกณฑ์สัญญาณเข้มขึ้นไม่ช่วย จาก super_signal_sensitivity.md และ 3_final_summary.md.");
}
{
  const s = newSlide("DARK", "7 QA");
  s.addText("Q&A", { x: 0.8, y: 2.0, w: 11.7, h: 1.6, fontSize: 80, bold: true, color: C.background1, margin: 0, isTextBox: true });
  s.addText("ขอบคุณครับ  |  พร้อมตอบคำถาม และเปิดแดชบอร์ดให้ดูหน้าไหนก็ได้", { x: 0.8, y: 3.9, w: 11.7, h: 0.7, fontSize: 22, color: "CADCFC", margin: 0, isTextBox: true });
  s.addText("ข้อมูลย้อนหลัง ไม่ใช่ real-time ไม่ใช่คำแนะนำการลงทุน", { x: 0.8, y: 6.6, w: 11.7, h: 0.4, fontSize: 14, color: "9FB3D1", margin: 0, isTextBox: true });
  s.addNotes("เปิดแดชบอร์ดค้างไว้ที่หน้า Home เพื่อ demo ตามคำขอของกรรมการ. สไลด์สำรอง: ภาพ s5_confusion_matrices.png, a1_panel_Ticker_spearman.png, a3_auc.png ในโฟลเดอร์ output/figures.");
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("written", OUT);
})();
