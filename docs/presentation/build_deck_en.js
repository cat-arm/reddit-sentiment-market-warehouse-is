// English defence deck, v5 = dark redesign in the seven parts the author asked for (2026-11-08). Every statement and number comes from the proposal and the thesis book (nothing else); sources are not named on the slides.
// Speaker notes are not attached (see NOTES below).
// Run: NODE_PATH=<dir with node_modules/pptxgenjs> node build_deck_en.js <repo_root> <crops_dir> docs/presentation/defence_deck_en_v4.pptx
//   <crops_dir> holds home.png, p1.png ... p7.png (dashboard screenshots, see shoot_dashboard.py) and sizes.json ({"home":[w,h], ...}).
// Design: deep navy background, raised cards with a coloured top rule, teal/amber/coral/blue accents, one idea per title, big numbers for facts.
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");

const ROOT = process.argv[2], CROPS = process.argv[3], OUT = process.argv[4];
const NOTES = [];   // speaker notes: none attached in v4 (the Thai notes in notes_th.json were written for the v3 content and must be rewritten for these slides)
let SLIDE_IDX = 0;
const STORY = JSON.parse(fs.readFileSync(path.join(ROOT, "output", "reports", "deck_story_btc.json"), "utf8"));   // scripts/deck_story_btc.py
let SIZES = {};
try { SIZES = JSON.parse(fs.readFileSync(path.join(CROPS, "sizes.json"), "utf8")); } catch (e) { /* no screenshots */ }

// ---- palette (hex without #)
const BG = "0A1020", BG2 = "0F1A33", SURF = "141F3A", EDGE = "26355A";
const INK = "F4F7FC", SOFT = "C3CFE4", MUTE = "8392B0";
const TEAL = "2DD4BF", AMBER = "F5B942", CORAL = "FF7A70", BLUE = "6AA6FF", GREEN = "3DDC97", VIOLET = "A78BFA";
const HEAD = "Calibri", BODY = "Calibri";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";                                   // 13.33 x 7.5 in
pres.theme = { headFontFace: HEAD, bodyFontFace: BODY };
pres.title = "Reddit Sentiment vs Market - defence";
pres.author = "Rithipong Leanghirunkun";

const num = { x: 12.3, y: 7.02, w: 0.7, h: 0.3, fontSize: 10, color: MUTE, fontFace: BODY, align: "right" };
pres.defineSlideMaster({ title: "DARK", background: { color: BG }, objects: [], slideNumber: num });
pres.defineSlideMaster({ title: "HERO", background: { color: BG }, objects: [], slideNumber: num });

let sectionNow = null;
function newSlide(master, section) {
  if (section !== sectionNow) { pres.addSection({ title: section }); sectionNow = section; }
  const sl = pres.addSlide({ masterName: master, sectionTitle: section });
  if (NOTES[SLIDE_IDX]) sl.addNotes(NOTES[SLIDE_IDX]);
  SLIDE_IDX += 1;
  return sl;
}
const T = (s, text, o) => s.addText(text, Object.assign({ fontFace: BODY, color: INK, margin: 0, isTextBox: true, valign: "top" }, o));

// ---- building blocks -------------------------------------------------------------------------
function head(s, title, tag, color) {
  const c = color || TEAL;
  if (tag) {
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 0.42, w: 0.38, h: 0.06, fill: { color: c }, line: { color: c, width: 0 } });
    T(s, tag.toUpperCase(), { x: 1.1, y: 0.3, w: 9, h: 0.3, fontSize: 11, bold: true, color: c, charSpacing: 3, valign: "middle" });
  }
  T(s, title, { x: 0.6, y: 0.72, w: 12.1, h: 0.95, fontSize: 30, bold: true, fontFace: HEAD, color: INK, objectName: "Title" });
}
function card(s, x, y, w, h, title, body, opt = {}) {
  const c = opt.color || TEAL;
  if (Array.isArray(body)) body = body.map((t) => (typeof t === "string" ? { text: t } : t));
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: SURF }, line: { color: EDGE, width: 0.75 }, rectRadius: 0.08, objectName: "Card" });
  s.addShape(pres.shapes.RECTANGLE, { x: x + 0.22, y: y + 0.2, w: 0.42, h: 0.05, fill: { color: c }, line: { color: c, width: 0 } });
  T(s, title, { x: x + 0.22, y: y + 0.32, w: w - 0.44, h: 0.45, fontSize: (opt.headSize || 18) + 1.5, bold: true, color: c });
  T(s, body, { x: x + 0.22, y: y + 0.85, w: w - 0.44, h: h - 1.0, fontSize: (opt.size || 15) + 1.5, color: SOFT, paraSpaceAfter: 8 });
}
const bl = (items) => items.map((t, i) => ({ text: t, options: { bullet: { indent: 14 }, breakLine: i < items.length - 1 } }));
function stat(s, x, y, w, big, label, color, bigSize) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 1.75, fill: { color: SURF }, line: { color: EDGE, width: 0.75 }, rectRadius: 0.08, objectName: "Stat" });
  T(s, big, { x: x + 0.2, y: y + 0.12, w: w - 0.4, h: 0.85, fontSize: bigSize || 36, bold: true, color: color || TEAL, valign: "middle" });
  T(s, label, { x: x + 0.2, y: y + 0.98, w: w - 0.4, h: 0.7, fontSize: 14.5, color: SOFT });
}
function pill(s, x, y, w, text, fill) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 0.42, fill: { color: fill || TEAL }, line: { color: fill || TEAL, width: 0 }, rectRadius: 0.21, objectName: "Pill" });
  T(s, text, { x, y, w, h: 0.42, fontSize: 14, bold: true, color: BG, align: "center", valign: "middle" });
}
function openPage(s, name) { pill(s, 0.6, 6.82, 5.9, "Live demo  ·  " + name, TEAL); }
function box(s, x, y, w, h, title, sub, o = {}) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: o.fill || SURF }, line: { color: o.line || EDGE, width: 1 }, rectRadius: 0.1, objectName: "Box" });
  T(s, title, { x: x + 0.1, y: y + 0.12, w: w - 0.2, h: 0.4, fontSize: 15, bold: true, color: o.tcolor || INK, align: "center" });
  if (sub) T(s, sub, { x: x + 0.12, y: y + 0.58, w: w - 0.24, h: h - 0.66, fontSize: 12.5, color: o.scolor || SOFT, align: "center" });
}
function arrow(s, x1, y1, x2, y2) {
  s.addShape(pres.shapes.LINE, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1), h: Math.abs(y2 - y1), flipV: y2 < y1, flipH: x2 < x1,
    line: { color: TEAL, width: 2, endArrowType: "triangle" } });
}
function shot(s, key, x, y, w, h, caption) {                    // real dashboard screenshot, fitted into w x h
  const sz = SIZES[key];
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x - 0.06, y: y - 0.06, w: w + 0.12, h: h + 0.12, fill: { color: "FFFFFF" }, line: { color: EDGE, width: 1 }, rectRadius: 0.06, objectName: "ShotFrame" });
  if (sz && fs.existsSync(path.join(CROPS, key + ".png"))) {
    const r = Math.min(w / sz[0], h / sz[1]);
    s.addImage({ path: path.join(CROPS, key + ".png"), x: x + (w - sz[0] * r) / 2, y: y + (h - sz[1] * r) / 2, w: sz[0] * r, h: sz[1] * r, altText: "Dashboard screenshot " + key });
  }
  if (caption) T(s, caption, { x, y: y + h + 0.1, w, h: 0.3, fontSize: 11, color: MUTE });
}
const chartCommon = { catAxisLabelColor: SOFT, valAxisLabelColor: MUTE, catAxisLabelFontFace: BODY, valAxisLabelFontFace: BODY,
  catAxisLabelFontSize: 13, valAxisLabelFontSize: 12, valGridLine: { color: EDGE, size: 0.5 }, catGridLine: { style: "none" }, dataLabelFontFace: BODY,
  dataLabelFontSize: 13, dataLabelColor: INK, legendFontFace: BODY, legendFontSize: 13, legendColor: SOFT, titleFontFace: BODY, titleFontSize: 15, titleColor: INK,
  catAxisLineShow: false, valAxisLineShow: false };
function table(s, rows, opt) {
  const hdr = rows[0].map((t) => ({ text: t, options: { bold: true, color: TEAL, fill: { color: BG2 } } }));
  const body = rows.slice(1).map((r, i) => r.map((t, k) => ({ text: t, options: { color: k === 0 ? INK : SOFT, bold: k === 0, fill: { color: i % 2 ? BG2 : SURF } } })));
  s.addTable([hdr, ...body], Object.assign({ fontSize: 13, fontFace: BODY, color: SOFT, border: { type: "solid", pt: 0.5, color: EDGE },
    valign: "middle", margin: [0.05, 0.12, 0.05, 0.12] }, opt));
}
// big background glow for hero slides (two soft circles)
function glow(s) {
  s.addShape(pres.shapes.OVAL, { x: 8.6, y: -2.2, w: 7.5, h: 7.5, fill: { color: TEAL, transparency: 90 }, line: { color: TEAL, width: 0, transparency: 100 } });
  s.addShape(pres.shapes.OVAL, { x: -3.0, y: 4.6, w: 7.0, h: 7.0, fill: { color: BLUE, transparency: 92 }, line: { color: BLUE, width: 0, transparency: 100 } });
}

// ---- small layout helpers used by the seven parts
const fmt = (n) => Number(n).toLocaleString("en-US");
function rowList(s, items, y0, step, h, colors, titleW) {           // numbered rows: [title, text]
  items.forEach((r, i) => {
    const y = y0 + i * step, c = colors[i % colors.length];
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y, w: 12.1, h, fill: { color: SURF }, line: { color: EDGE, width: 0.75 }, rectRadius: 0.08, objectName: "Row" });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: y + 0.1, w: 0.07, h: h - 0.2, fill: { color: c }, line: { color: c, width: 0 } });
    T(s, String(i + 1), { x: 0.85, y, w: 0.6, h, fontSize: 26, bold: true, color: c, valign: "middle" });
    T(s, r[0], { x: 1.55, y, w: titleW || 3.9, h, fontSize: 18, bold: true, valign: "middle" });
    T(s, r[1], { x: 1.55 + (titleW || 3.9) + 0.2, y, w: 12.1 - (titleW || 3.9) - 1.5, h, fontSize: 15.5, color: SOFT, valign: "middle" });
  });
}
function sowhat(s, x, y, w, h, text) {                              // the amber "so what" box
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: AMBER, transparency: 86 }, line: { color: AMBER, width: 1 }, rectRadius: 0.08, objectName: "SoWhat" });
  T(s, text, { x: x + 0.2, y, w: w - 0.4, h, fontSize: 16, bold: true, color: AMBER, valign: "middle" });
}
function story(n, title, page, doItems, stats, so, key) {
  const s = newSlide("DARK", "5 User story");
  head(s, title, "5 User story  ·  Step " + n + "  ·  " + page, CORAL);
  card(s, 0.6, 1.85, 5.9, 1.9, "What the analyst does", bl(doItems), { size: 14, headSize: 17, color: BLUE });
  stats.forEach((st, i) => stat(s, 0.6 + i * 3.05, 3.95, 2.85, st[0], st[1], st[2], st[3] || 32));
  sowhat(s, 0.6, 5.9, 5.9, 0.95, so);
  shot(s, key, 6.85, 1.8, 5.9, 4.75, "Default filters. Choose BTC-USD in the sidebar to follow along. The dashboard is in Thai.");
  return s;
}
function qslide(title, tag, rows) {
  const s = newSlide("DARK", "6 Executive questions");
  head(s, title, "6 Executive questions  ·  " + tag, GREEN);
  table(s, rows, { x: 0.5, y: 1.85, w: 12.35, colW: [3.9, 6.3, 2.15], fontSize: 15, rowH: 0.85 });
}

// =============================================================== OPENING
{
  const s = newSlide("HERO", "Opening");
  glow(s);
  s.addShape(pres.shapes.RECTANGLE, { x: 0.8, y: 1.35, w: 0.9, h: 0.08, fill: { color: TEAL }, line: { color: TEAL, width: 0 } });
  T(s, "Data Warehouse, Business Intelligence and Advanced Data Analytics of Reddit Sentiment and Securities Price Movement", { x: 0.8, y: 1.65, w: 11.0, h: 2.4, fontSize: 40, bold: true, fontFace: HEAD });
  T(s, "Reddit community sentiment against hourly prices of 34 assets, from one warehouse to one dashboard.", { x: 0.8, y: 4.3, w: 9.6, h: 0.9, fontSize: 20, color: SOFT });
  T(s, "Rithipong Leanghirunkun", { x: 0.8, y: 5.9, w: 11, h: 0.4, fontSize: 18, bold: true });
  T(s, "Chulalongkorn University  ·  MSc Information Technology in Business", { x: 0.8, y: 6.3, w: 11, h: 0.35, fontSize: 15, color: SOFT });
  T(s, "Historical data, Oct 2024 to Aug 2026. Not real-time. Not investment advice.", { x: 0.8, y: 6.75, w: 11, h: 0.3, fontSize: 12, color: MUTE });
}
{
  const s = newSlide("DARK", "Opening");
  head(s, "Seven parts, one story.", "Agenda");
  const items = [["The pain point", "Why a single view is missing"], ["The users", "Who uses it, and for what"], ["The architecture", "Data flow, tools and models"], ["The six systems", "What each one does, and the dashboards"],
    ["A user story", "One asset, BTC-USD, page by page"], ["Executive questions", "Every question, answered, with its page"], ["QA", "Tests, limits, questions"]];
  items.forEach((t, i) => {
    const col = i < 4 ? 0 : 1, row = i < 4 ? i : i - 4;
    const x = 0.6 + col * 6.2, y = 1.9 + row * 1.2;
    const c = i === 4 ? CORAL : TEAL;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 5.8, h: 1.0, fill: { color: SURF }, line: { color: EDGE, width: 0.75 }, rectRadius: 0.08, objectName: "AgendaRow" });
    T(s, String(i + 1), { x: x + 0.2, y, w: 0.7, h: 1.0, fontSize: 34, bold: true, color: c, valign: "middle" });
    T(s, t[0], { x: x + 1.0, y: y + 0.1, w: 4.7, h: 0.45, fontSize: 21, bold: true, valign: "middle" });
    T(s, t[1], { x: x + 1.0, y: y + 0.55, w: 4.7, h: 0.35, fontSize: 13.5, color: MUTE });
  });
}

// =============================================================== 1 PAIN POINT
{
  const s = newSlide("DARK", "1 Pain point");
  head(s, "Analysts have no single place to see Reddit sentiment next to prices.", "1 Pain point", CORAL);
  card(s, 0.6, 2.0, 2.85, 4.4, "No organised data", bl(["Analysts follow Reddit by hand.", "Data is scattered and not ready to use with prices."]), { color: TEAL, size: 16 });
  card(s, 3.65, 2.0, 2.85, 4.4, "Limited analysis", bl(["Text is not turned into numbers.", "No sentiment score, volume or positive and negative share."]), { color: CORAL, size: 16 });
  card(s, 6.7, 2.0, 2.85, 4.4, "Scattered data", bl(["Prices and sentiment sit apart.", "No single source of truth, no single dashboard."]), { color: BLUE, size: 16 });
  card(s, 9.75, 2.0, 2.95, 4.4, "No signal detection", bl(["Nothing flags unusual volume.", "Nothing flags a clear sentiment shift."]), { color: AMBER, size: 16 });
}
{
  const s = newSlide("DARK", "1 Pain point");
  head(s, "The project answers with six goals.", "1 Pain point", CORAL);
  rowList(s, [["Collect and process Reddit data", "Historical posts and comments from six communities, in one warehouse."],
    ["Score sentiment", "VADER and FinBERT on every text, with a rule to settle conflicts."],
    ["One BI dashboard", "Price, volume, Reddit volume and sentiment side by side."],
    ["Test the link to future returns", "Correlation, historical win rate and logistic regression."],
    ["Detect signals", "Flag unusual volume and clear sentiment in historical data."],
    ["Judge the evidence", "Compare Reddit indicators against a random baseline."]], 1.85, 0.82, 0.72, [TEAL, TEAL, BLUE, BLUE, AMBER, CORAL], 4.3);
}

// =============================================================== 2 USERS
{
  const s = newSlide("DARK", "2 Users");
  head(s, "The users: the investment analyst team of a FinTech trading platform.", "2 Users", BLUE);
  s.addShape(pres.shapes.OVAL, { x: 0.7, y: 2.6, w: 2.7, h: 2.7, fill: { color: TEAL, transparency: 80 }, line: { color: TEAL, width: 2 }, objectName: "UserCircle" });
  T(s, "Investment\nanalyst team", { x: 0.7, y: 2.6, w: 2.7, h: 2.7, fontSize: 24, bold: true, align: "center", valign: "middle" });
  card(s, 4.0, 1.95, 4.3, 2.3, "Gauge attention", ["Which assets are mentioned most, and when volume is unusually high."], { color: TEAL, size: 16 });
  card(s, 8.5, 1.95, 4.2, 2.3, "Follow prices", ["Price, trading volume and future returns of each asset."], { color: BLUE, size: 16 });
  card(s, 4.0, 4.5, 4.3, 2.3, "Check relationships", ["Whether sentiment relates to future returns, as extra data for reading the market."], { color: AMBER, size: 16 });
  card(s, 8.5, 4.5, 4.2, 2.3, "Find hours to review", ["Signals at thresholds the analyst sets, as a start for deeper checks."], { color: CORAL, size: 16 });
}
{
  const s = newSlide("DARK", "2 Users");
  head(s, "What the team gets out of it.", "2 Users", BLUE);
  rowList(s, [["Saves time, reduces bias", "Large, unstructured community text becomes numbers instead of being read by hand."],
    ["One source of truth", "Prices, Reddit sentiment and statistics sit in one system."],
    ["Evidence from history", "Relationships, direction accuracy and several data conditions are compared."],
    ["A start for deeper checks", "Signals point to hours, assets or groups worth analysing next."],
    ["Room to grow", "The design can extend to other sources, such as Twitter/X, or other assets."]], 1.95, 0.95, 0.82, [TEAL, TEAL, BLUE, CORAL, AMBER], 3.9);
}

// =============================================================== 3 ARCHITECTURE
{
  const s = newSlide("DARK", "3 Architecture");
  head(s, "Data flow: two sources, one SQLite database, one dashboard.", "3 Architecture", VIOLET);
  box(s, 0.45, 1.85, 2.2, 1.5, "Academic Torrents", "Historical Reddit\nposts and comments");
  box(s, 0.45, 3.65, 2.2, 1.5, "yfinance", "Hourly prices\n34 assets");
  box(s, 3.0, 1.85, 2.0, 1.5, "Import", "Monthly files,\n6 communities");
  box(s, 3.0, 3.65, 2.0, 1.5, "Import", "Price download");
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.4, y: 1.85, w: 2.6, h: 3.3, fill: { color: TEAL, transparency: 85 }, line: { color: TEAL, width: 1.5 }, rectRadius: 0.1, objectName: "SQLiteBox" });
  T(s, "SQLite", { x: 5.4, y: 1.97, w: 2.6, h: 0.5, fontSize: 24, bold: true, align: "center", color: TEAL });
  T(s, "Single source of truth", { x: 5.5, y: 2.5, w: 2.4, h: 0.35, fontSize: 13, color: SOFT, align: "center" });
  T(s, "All six systems read and write here, so no data is duplicated between them.", { x: 5.65, y: 3.05, w: 2.3, h: 1.9, fontSize: 14, align: "center", color: INK });
  box(s, 8.35, 1.85, 2.4, 3.3, "Processing", "Clean text\nTransform\nAlign to the hour\nSentiment\nRelationships\nSignals");
  box(s, 11.05, 1.85, 1.85, 3.3, "Dashboard", "Streamlit\nHome + 7 pages", { fill: TEAL, line: TEAL, tcolor: BG, scolor: BG });
  arrow(s, 2.67, 2.6, 2.98, 2.6); arrow(s, 2.67, 4.4, 2.98, 4.4);
  arrow(s, 5.02, 2.6, 5.38, 3.1); arrow(s, 5.02, 4.4, 5.38, 3.9);
  arrow(s, 8.02, 3.5, 8.33, 3.5); arrow(s, 10.77, 3.5, 11.03, 3.5);
  const sys = ["1 Reddit warehouse", "2 Price warehouse", "3 Sentiment analysis", "4 Relationship analysis", "5 Investment analysis", "6 Signal detection"];
  sys.forEach((t, i) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.45 + i * 2.08, y: 5.5, w: 1.96, h: 0.5, fill: { color: SURF }, line: { color: EDGE, width: 0.75 }, rectRadius: 0.25, objectName: "SysChip" });
    T(s, t, { x: 0.45 + i * 2.08, y: 5.5, w: 1.96, h: 0.5, fontSize: 11.5, bold: true, align: "center", valign: "middle", color: INK });
  });
  T(s, "Every step is a Python script that can be re-run. The raw data is never edited.", { x: 0.45, y: 6.3, w: 12.4, h: 0.4, fontSize: 16, color: SOFT });
}
{
  const s = newSlide("DARK", "3 Architecture");
  head(s, "Tools: Python end to end, on one Windows PC.", "3 Architecture", VIOLET);
  const rows = [["Job", "Tools"],
    ["Language and editor", "Python 3.14, Visual Studio Code"],
    ["Store", "SQLite (one database file)"],
    ["Import", "zstandard (Reddit files), yfinance (prices)"],
    ["Manage and compute data", "pandas, NumPy"],
    ["Sentiment", "NLTK 3.10.3 (VADER), PyTorch 2.11.0 with CUDA 12.8, Transformers 5.19.0 (FinBERT)"],
    ["Statistics and machine learning", "SciPy 1.18.1, scikit-learn 1.9.1"],
    ["Display", "Streamlit 1.65.0, Matplotlib 3.11.2, Seaborn 0.13.2"],
    ["Machine", "Windows 11, NVIDIA RTX 5070 (12 GB), 32 GB RAM"]];
  table(s, rows, { x: 0.6, y: 1.9, w: 12.1, colW: [3.9, 8.2], fontSize: 15, rowH: 0.55 });
}
{
  const s = newSlide("DARK", "3 Architecture");
  head(s, "Models: two for sentiment, one for relationships.", "3 Architecture", VIOLET);
  card(s, 0.6, 1.95, 3.9, 3.4, "VADER", bl(["Rule-based, built for social media.", "Reads symbols such as $, % and !.", "Score from −1 to +1."]), { size: 15, headSize: 20, color: TEAL });
  card(s, 4.7, 1.95, 3.9, 3.4, "FinBERT", bl(["Language model trained on financial text (ProsusAI/finbert).", "Score = P(positive) − P(negative), from −1 to +1."]), { size: 15, headSize: 20, color: BLUE });
  card(s, 8.8, 1.95, 3.9, 3.4, "Logistic regression", bl(["scikit-learn.", "Predicts up or down of the future return.", "Judged by AUC-ROC, 5 time-ordered folds."]), { size: 15, headSize: 20, color: AMBER });
  card(s, 0.6, 5.5, 12.1, 1.35, "How the two sentiment models are joined", ["A neutral band of ±0.05 turns scores into positive, neutral or negative. A merge rule settles conflicts and records which rule decided."], { size: 15, headSize: 18, color: VIOLET });
}
{
  const s = newSlide("DARK", "3 Architecture");
  head(s, "Star schema with 3 fact tables and 6 dimensions.", "3 Architecture", VIOLET);
  const facts = [["FactRedditVolume", "618,518 rows", "Reddit volume and ticker mention counts.\nDimTime, DimTicker, DimSource.", TEAL],
    ["FactMarketPrice", "250,253 rows", "Close, volume, future returns 1 to 12 hours, RSI, ATR.\nDimTime, DimTicker.", BLUE],
    ["FactMarketSentiment", "250,253 rows", "Sentiment, class shares, win rate, p-values.\nDimTime, DimTicker, DimSentimentSource, DimDetectionConfig, DimMajoritySentiment.", AMBER]];
  facts.forEach((f, i) => {
    const y = 1.85 + i * 1.65;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y, w: 7.4, h: 1.45, fill: { color: SURF }, line: { color: EDGE, width: 0.75 }, rectRadius: 0.08, objectName: "FactRow" + i });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y, w: 2.55, h: 1.45, fill: { color: f[3] }, line: { color: f[3], width: 0 }, rectRadius: 0.08, objectName: "FactHead" + i });
    T(s, f[0], { x: 0.65, y: y + 0.2, w: 2.45, h: 0.6, fontSize: 16, bold: true, color: BG, align: "center", valign: "middle" });
    T(s, f[1], { x: 0.65, y: y + 0.85, w: 2.45, h: 0.4, fontSize: 15, color: BG, align: "center", bold: true });
    T(s, f[2], { x: 3.35, y, w: 4.5, h: 1.45, fontSize: 14, color: SOFT, valign: "middle" });
  });
  const dims = [["DimTime", "17,544 hours."], ["DimTicker", "34 assets, by asset group."], ["DimSource", "12 sources: 6 communities by post or comment."],
    ["DimSentimentSource", "7 sources: 6 communities plus all combined."], ["DimMajoritySentiment", "3 classes: positive, negative, neutral."], ["DimDetectionConfig", "30 signal settings."]];
  card(s, 8.3, 1.85, 4.4, 4.9, "Dimensions", dims.map((d, i) => ({ text: d[0] + ". " + d[1], options: { bullet: { indent: 14 }, breakLine: i < dims.length - 1 } })), { size: 12, headSize: 17, color: VIOLET });
}
{
  const s = newSlide("DARK", "3 Architecture");
  head(s, "Built in seven steps, each one a numbered Python script.", "3 Architecture", VIOLET);
  rowList(s, [["Install the software", "Python, libraries, GPU for FinBERT."],
    ["Import the data", "Monthly Reddit files for 6 communities; hourly prices for 34 assets."],
    ["Build the warehouse", "Fact and dimension tables, with the 34 assets loaded."],
    ["Clean text, extract tickers", "Cleaned text, quality filter, ticker mentions."],
    ["Score sentiment", "VADER and FinBERT, merge rule, hand-labelled check."],
    ["Analyse and detect", "Hourly dataset, 9 panels, statistics, signals."],
    ["Dashboard and tests", "Streamlit dashboard, then three groups of tests."]], 1.8, 0.72, 0.62, [TEAL, TEAL, BLUE, BLUE, AMBER, AMBER, CORAL], 3.7);
}

// =============================================================== 4 THE SIX SYSTEMS
{
  const s = newSlide("DARK", "4 Six systems");
  head(s, "Six systems, from raw data to signals.", "4 Six systems", AMBER);
  const rows = [["System", "Takes in", "Produces", "Shown on"],
    ["1 Reddit warehouse", "Academic Torrents monthly files", "Hourly volume and mentions per asset and community", "Reddit Volume, Ticker Mentions"],
    ["2 Price warehouse", "yfinance hourly bars", "Close, volume, future returns, RSI, ATR", "Price and Return"],
    ["3 Sentiment analysis", "Cleaned texts", "Final sentiment of every text, with its rule", "Market and Sentiment"],
    ["4 Relationship analysis", "Sentiment and returns", "Correlation, win rate, logistic regression in 9 panels", "Statistical Analysis"],
    ["5 Investment analysis", "Results of systems 1 to 4", "Overview, ranking and threshold settings", "Market and Sentiment, Statistical Analysis, Lead and Lag"],
    ["6 Signal detection", "Thresholds the user sets", "List of signals with past statistics", "Hot Events"]];
  table(s, rows, { x: 0.5, y: 1.9, w: 12.35, colW: [2.6, 2.9, 4.0, 2.85], fontSize: 13.5, rowH: 0.7 });
}
{
  const s = newSlide("DARK", "4 Six systems");
  head(s, "System 1, Reddit warehouse: 22 million texts from six communities.", "4 Six systems  ·  System 1", AMBER);
  const comm = [["wallstreetbets", 16130876], ["stocks", 1909932], ["CryptoCurrency", 1536115], ["StockMarket", 1063472], ["investing", 1013010], ["options", 375714]];
  s.addChart(pres.charts.BAR, [{ name: "Texts", labels: comm.map((c) => "r/" + c[0]), values: comm.map((c) => c[1]) }], {
    x: 0.5, y: 1.85, w: 7.0, h: 4.95, barDir: "bar", chartColors: [TEAL], showLegend: false, showTitle: true, title: "Texts per community (cleaned, scored)", showValue: true, dataLabelPosition: "outEnd",
    dataLabelFormatCode: "#,##0", valAxisHidden: true, valGridLine: { style: "none" }, catAxisOrientation: "maxMin", valAxisMaxVal: 21000000, ...chartCommon });
  stat(s, 7.9, 1.95, 2.35, "22,029,119", "texts in total", TEAL, 24);
  stat(s, 10.4, 1.95, 2.3, "73.2%", "from wallstreetbets", AMBER, 34);
  card(s, 7.9, 3.9, 4.8, 2.9, "Source and dashboards", bl(["Academic Torrents monthly files, six communities, English only.", "275,242 posts and 21,753,877 comments.", "Dashboards: Reddit Volume and Ticker Mentions."]), { size: 12.5, headSize: 17, color: BLUE });
}
{
  const s = newSlide("DARK", "4 Six systems");
  head(s, "System 2, price warehouse: hourly prices of 34 assets from yfinance.", "4 Six systems  ·  System 2", AMBER);
  card(s, 0.6, 1.95, 4.0, 2.55, "22 stocks and ETFs", "AAPL, AMC, AMD, BITO, BRK-B, COIN, GME, HOOD, IBIT, IWM, JNJ, JPM, KO, MARA, MSFT, MSTR, NVDA, PLTR, QQQ, SPY, TSLA, XOM", { size: 12, headSize: 17, color: BLUE });
  card(s, 4.7, 1.95, 4.0, 2.55, "6 crypto", "BTC-USD, DOGE-USD, ETH-USD, SHIB-USD, SOL-USD, XRP-USD", { size: 14, headSize: 17, color: GREEN });
  card(s, 8.8, 1.95, 3.9, 2.55, "6 futures", "CL=F, ES=F, GC=F, NG=F, NQ=F, RTY=F", { size: 14, headSize: 17, color: AMBER });
  card(s, 0.6, 4.7, 6.0, 2.1, "What is stored per hour", bl(["Close and trading volume.", "Future returns after 1, 2, 3, 6 and 12 hours.", "RSI and ATR."]), { size: 13.5, headSize: 17 });
  card(s, 6.8, 4.7, 5.9, 2.1, "Limits and dashboard", bl(["250,253 hourly rows. Stocks and ETFs have about 7 bars a day.", "Dashboard: Price and Return."]), { size: 13.5, headSize: 17, color: CORAL });
}
{
  const s = newSlide("DARK", "4 Six systems");
  head(s, "System 3, sentiment: two models, one merge rule.", "4 Six systems  ·  System 3", AMBER);
  s.addChart(pres.charts.DOUGHNUT, [{ name: "Share", labels: ["Same direction", "One neutral, one directional", "Opposite directions"], values: [50.15, 37.59, 12.26] }], {
    x: 0.5, y: 1.9, w: 6.0, h: 4.9, holeSize: 55, chartColors: [GREEN, AMBER, CORAL], showLegend: true, legendPos: "b", showPercent: true, showValue: false, dataLabelColor: BG, dataLabelFontSize: 15,
    showTitle: false, dataBorder: { pt: 2, color: BG }, ...chartCommon, dataLabelColor: BG });
  card(s, 6.9, 1.95, 5.8, 3.0, "Merge rule", bl(["Same direction: average the scores, or take the one closer to 0 if they differ by over 0.50.", "One neutral: use the directional model, unless a finance keyword disagrees (then 0).", "Opposite: a finance keyword decides, otherwise 0.", "Neutral band: ±0.05."]), { size: 11.5, headSize: 16 });
  card(s, 6.9, 5.15, 5.8, 1.65, "Why two models", bl(["VADER is built for social media, FinBERT for financial text.", "2,714,134 texts (12.3%) cannot be decided: set to 0 and flagged."]), { size: 11.5, headSize: 16, color: BLUE });
}
{
  const s = newSlide("DARK", "4 Six systems");
  head(s, "System 3 result: overall sentiment is balanced, leaning slightly negative.", "4 Six systems  ·  System 3", AMBER);
  s.addChart(pres.charts.BAR, [
    { name: "VADER", labels: ["Positive", "Neutral", "Negative"], values: [38.81, 30.27, 30.92] },
    { name: "FinBERT", labels: ["Positive", "Neutral", "Negative"], values: [17.25, 48.41, 34.35] },
    { name: "Final sentiment", labels: ["Positive", "Neutral", "Negative"], values: [32.41, 32.86, 34.72] }], {
    x: 0.5, y: 1.85, w: 7.6, h: 4.9, barDir: "col", chartColors: [MUTE, BLUE, TEAL], showLegend: true, legendPos: "b", showTitle: true, title: "Share of texts by class (%), neutral band ±0.05",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0", valAxisHidden: true, valGridLine: { style: "none" }, valAxisMinVal: 0, valAxisMaxVal: 60, ...chartCommon });
  card(s, 8.5, 1.95, 4.2, 2.4, "Reading it", bl(["VADER leans positive, FinBERT leans neutral.", "The merged result is close to a third each."]), { size: 13.5, headSize: 17 });
  card(s, 8.5, 4.55, 4.2, 2.25, "Careful", bl(["The final neutral share includes the 12.32% undecided texts.", "Truly neutral texts are about 20.5%."]), { size: 13.5, headSize: 17, color: AMBER });
}
{
  const s = newSlide("DARK", "4 Six systems");
  head(s, "System 3 test: against 210 hand labels the merge beats VADER, not FinBERT.", "4 Six systems  ·  System 3", AMBER);
  s.addChart(pres.charts.BAR, [
    { name: "VADER alone", labels: ["Tune set", "Test set", "All 210"], values: [40.6, 37.1, 38.8] },
    { name: "FinBERT alone", labels: ["Tune set", "Test set", "All 210"], values: [56.4, 42.9, 49.6] },
    { name: "Merge rule", labels: ["Tune set", "Test set", "All 210"], values: [47.3, 41.3, 44.3] }], {
    x: 0.5, y: 1.85, w: 7.3, h: 4.4, barDir: "col", chartColors: [MUTE, BLUE, TEAL], showLegend: true, legendPos: "b", showTitle: true, title: "Accuracy against hand labels (%)",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0", valAxisHidden: true, valGridLine: { style: "none" }, valAxisMinVal: 0, valAxisMaxVal: 70, ...chartCommon });
  T(s, "One labeller. 105 texts per set. Accuracy is weighted by group size.", { x: 0.6, y: 6.4, w: 7.2, h: 0.4, fontSize: 13, color: MUTE });
  card(s, 8.2, 1.95, 4.5, 2.35, "Method", bl(["7 rule groups, 30 texts each, split into a tune set and a test set.", "Labels were made without seeing any score."]), { size: 13, headSize: 17 });
  card(s, 8.2, 4.5, 4.5, 2.3, "Result", bl(["On the test set the gap to FinBERT is 1.6 points, inside the sampling error.", "The rules stay as in the proposal."]), { size: 13, headSize: 17, color: BLUE });
}
{
  const s = newSlide("DARK", "4 Six systems");
  head(s, "System 3 test: a wider neutral band of ±0.10 does not help, so ±0.05 stays.", "4 Six systems  ·  System 3", AMBER);
  stat(s, 0.6, 1.95, 3.9, "48.41% → 63.09%", "FinBERT texts called neutral, band ±0.05 against ±0.10.", AMBER, 30);
  stat(s, 4.7, 1.95, 3.9, "44.3% → 42.4%", "Merge-rule accuracy on all 210 labels.", CORAL, 30);
  stat(s, 8.8, 1.95, 3.9, "8.69%", "of texts (1,914,518) change final class between the two bands.", BLUE, 40);
  card(s, 0.6, 4.0, 6.0, 2.8, "What changes", bl(["FinBERT puts far more texts in neutral at ±0.10.", "The final class shares move only a little.", "Undecided texts fall from 12.32% to 8.49%."]), { size: 14, color: TEAL });
  card(s, 6.8, 4.0, 5.9, 2.8, "Decision", bl(["Keep ±0.05, the band the VADER authors recommend.", "The band is a parameter, so it can be changed later."]), { size: 15, color: BLUE });
}
{
  const s = newSlide("DARK", "4 Six systems");
  head(s, "System 4, relationships: nine data panels, three methods.", "4 Six systems  ·  System 4", AMBER);
  const cols = [["Baseline", ["Random direction, no Reddit data"]], ["Global (all assets pooled)", ["all texts", "strong, |score| ≥ 0.05", "quality, |score| ≥ 0.30", "volume spike, Z > 1.5"]], ["Ticker (per asset)", ["all texts", "strong, |score| ≥ 0.05", "quality, |score| ≥ 0.30", "volume spike, Z > 1.5"]]];
  cols.forEach((c, i) => card(s, 0.6 + i * 2.75, 1.95, 2.6, 3.0, c[0], bl(c[1]), { size: 11.5, headSize: 14, color: [MUTE, TEAL, BLUE][i] }));
  card(s, 8.9, 1.95, 3.8, 3.0, "Three methods", bl(["Pearson and Spearman correlation.", "Historical win rate against a 50% baseline.", "Logistic regression, AUC-ROC."]), { size: 12.5, headSize: 17, color: AMBER });
  card(s, 0.6, 5.15, 12.1, 1.65, "What it found", ["No ability to predict price direction. Direction accuracy is about 50%, AUC about 0.50 and correlation near zero, like the random panel. Stricter filters did not help."], { size: 15, headSize: 17, color: CORAL });
}
{
  const s = newSlide("DARK", "4 Six systems");
  head(s, "System 5, investment analysis: the analyst's view of the results.", "4 Six systems  ·  System 5", AMBER);
  card(s, 0.6, 1.95, 3.9, 4.85, "Dashboard 1: overview", bl(["Close against average sentiment.", "Volume Z-score against sentiment.", "Positive, negative and neutral shares.", "Most positive and negative assets."]), { size: 13.5, headSize: 17, color: TEAL });
  card(s, 4.7, 1.95, 3.9, 4.85, "Dashboard 2: ranking", bl(["Historical win rate and p-values by asset and horizon.", "Thresholds the user sets: Z-score, sentiment, horizon.", "Feeds system 6."]), { size: 13.5, headSize: 17, color: BLUE });
  card(s, 8.8, 1.95, 3.9, 4.85, "Extension: Lead and Lag", bl(["Does sentiment relate to returns before or after an hour?", "Average sentiment after price rises or falls."]), { size: 13.5, headSize: 17, color: AMBER });
}
{
  const s = newSlide("DARK", "4 Six systems");
  head(s, "System 6, signal detection: from thresholds the user sets to a signal list.", "4 Six systems  ·  System 6", AMBER);
  const types = ["Volume Spike", "Positive Sentiment Spike", "Negative Sentiment Spike", "Combined Signal"];
  types.forEach((t, i) => pill(s, 0.6 + i * 3.08, 1.95, 2.9, t, [TEAL, GREEN, CORAL, AMBER][i]));
  const rows = [["Setting", "Choices", "Default"], ["Reddit Volume Z-score", "1.5, 2.0, 2.5", "1.5"], ["Sentiment threshold (absolute)", "0.05, 0.30", "0.30"], ["Horizon", "1h, 2h, 3h, 6h, 12h", "1h"]];
  table(s, rows, { x: 0.6, y: 2.75, w: 7.0, colW: [3.2, 2.4, 1.4], fontSize: 14, rowH: 0.6 });
  card(s, 7.9, 2.75, 4.8, 4.05, "What it gives", bl(["3 × 2 × 5 = 30 settings.", "Six threshold sets found 312,115 signals.", "Each signal has a level: low, medium or high.", "Shown on Hot Events. No outside alerts."]), { size: 13.5, headSize: 17, color: AMBER });
  T(s, "A signal is a place to look, not an order to trade.", { x: 0.6, y: 5.5, w: 7.0, h: 0.9, fontSize: 18, bold: true, color: SOFT });
}
{
  const s = newSlide("DARK", "4 Six systems");
  head(s, "The dashboard: Home plus seven pages, one question per page.", "4 Six systems  ·  Dashboards", AMBER);
  const rows = [["Page", "What the analyst does with it"],
    ["1 Reddit Volume", "See hourly post and comment volume and unusually high hours."],
    ["2 Ticker Mentions", "See which assets are mentioned most, the trend, and in which community."],
    ["3 Price and Return", "See price, trading volume, future returns 1 to 12 hours, the most volatile group."],
    ["4 Market and Sentiment", "Compare price with sentiment, see class shares and the standout assets."],
    ["5 Statistical Analysis", "Check whether sentiment relates to returns: correlation, win rate, logistic regression."],
    ["6 Lead and Lag  (extension)", "See whether sentiment or price changes first."],
    ["7 Hot Events  (extension)", "See the signals at thresholds you set, with returns after each signal."]];
  table(s, rows, { x: 0.6, y: 1.9, w: 12.1, colW: [3.6, 8.5], fontSize: 15.5, rowH: 0.6 });
}
{
  const s = newSlide("DARK", "4 Six systems");
  head(s, "Every page has the same layout and the same filters.", "4 Six systems  ·  Dashboards", AMBER);
  const parts = [["1  Navigation bar", "On top: Home plus the seven pages."],
    ["2  Filters (left)", "Time: date range and chart level. Source: community, post or comment. Asset: group and symbol. Some pages: majority sentiment, signal thresholds."],
    ["3  Summary cards", "Key numbers of the page for the chosen filters."],
    ["4  View options", "Above each chart: return horizon, how shares are counted, data panel."]];
  parts.forEach((p, i) => {
    const y = 1.95 + i * 1.2;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y, w: 6.0, h: 1.08, fill: { color: SURF }, line: { color: EDGE, width: 0.75 }, rectRadius: 0.08, objectName: "LayoutRow" });
    T(s, p[0], { x: 0.8, y: y + 0.08, w: 5.6, h: 0.3, fontSize: 15, bold: true, color: AMBER });
    T(s, p[1], { x: 0.8, y: y + 0.4, w: 5.6, h: 0.66, fontSize: 13, color: SOFT });
  });
  shot(s, "home", 6.9, 1.85, 5.85, 4.75, "The dashboard itself is in Thai.");
}

// =============================================================== 5 USER STORY
{
  const s = newSlide("HERO", "5 User story");
  glow(s);
  head(s, "User story: is Reddit chatter about BTC-USD telling me anything about its price?", "5 User story", CORAL);
  T(s, "An investment analyst opens the dashboard with one question and walks through the pages in order. All numbers are what the pages show for the full range, all communities.", { x: 0.6, y: 1.95, w: 12.0, h: 0.9, fontSize: 18, color: SOFT });
  const acts = [["1", "How busy is Reddit?", "Reddit Volume"], ["2", "Is BTC-USD talked about?", "Ticker Mentions"], ["3", "What did price do?", "Price and Return"], ["4", "What is the mood?", "Market and Sentiment"], ["5", "Who moves first?", "Lead and Lag"], ["6", "Is it reliable?", "Statistical Analysis"], ["7", "What to watch?", "Hot Events"]];
  acts.forEach((a, i) => {
    const x = 0.6 + i * 1.77;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 3.1, w: 1.63, h: 2.7, fill: { color: SURF }, line: { color: EDGE, width: 0.75 }, rectRadius: 0.08, objectName: "ActCard" });
    T(s, a[0], { x: x + 0.15, y: 3.2, w: 1.3, h: 0.75, fontSize: 38, bold: true, color: i === 6 ? CORAL : TEAL });
    T(s, a[1], { x: x + 0.15, y: 4.0, w: 1.38, h: 1.1, fontSize: 14, bold: true });
    T(s, a[2], { x: x + 0.15, y: 5.1, w: 1.38, h: 0.6, fontSize: 12.5, color: MUTE });
  });
  T(s, "Why BTC-USD: it is the most-mentioned asset and trades around the clock, so it has the most hours to test.", { x: 0.6, y: 6.1, w: 12.0, h: 0.7, fontSize: 16, color: SOFT });
}
{
  const p1 = STORY.p1;
  story("1", "First, how busy is Reddit overall?", "Reddit Volume",
    ["Pick the full range and all communities.", "Find the highest hour and the Z-score line."],
    [[p1["ชั่วโมงที่สูงสุด"].split(" (")[0], "texts in the peak hour, 9 Apr 2025, 17:00 UTC", CORAL, 30], [p1["เฉลี่ยต่อชั่วโมง"], "texts in an average hour. " + p1["ชั่วโมงที่ Z-score > 1.5"] + " hours had Z-score above 1.5", AMBER, 30]],
    "Big spikes are rare. Note the date and look at prices in that hour.", "p1");
}
{
  const p2 = STORY.p2;
  story("2", "Is BTC-USD talked about enough to judge?", "Ticker Mentions",
    ["Read the ranking of most-mentioned assets.", "Open the BTC-USD trend."],
    [["#" + p2.rank + " of " + p2.of, "BTC-USD is the most-mentioned asset. Next is " + p2.second + " (" + fmt(p2.second_mentions) + ")", TEAL, 34], [fmt(p2.mentions), "mentions, " + p2.mention_rate_pct.toFixed(2) + "% of all texts", BLUE, 30]],
    "Plenty of text, so BTC-USD is a fair asset to test.", "p2");
}
{
  const p3 = STORY.p3;
  story("3", "What did BTC-USD's price do?", "Price and Return",
    ["Look at price, RSI and volatility.", "Check future returns by asset group."],
    [["+" + p3.change_pct + "%", "close from " + fmt(Math.round(p3.first_close)) + " to " + fmt(Math.round(p3.last_close)), GREEN, 34], [(p3.crypto_1h_share_up * 100).toFixed(1) + "%", "of crypto hours were up after 1 hour. Average return " + p3.crypto_1h_mean_pct + "%", AMBER, 34]],
    "A strong rise overall, but any single hour is close to a coin flip.", "p3");
}
{
  const p4 = STORY.p4;
  story("4", "What is the mood on BTC-USD?", "Market and Sentiment",
    ["Put price next to average sentiment.", "Read the positive and negative shares and the ranking."],
    [[(p4.sentiment >= 0 ? "+" : "") + p4.sentiment.toFixed(3), "Sentiment Score from " + fmt(p4.texts) + " texts", TEAL, 34], [p4.pos_pct.toFixed(1) + "% / " + p4.neg_pct.toFixed(1) + "%", "positive / negative texts. Rank " + p4.rank_from_top + " of " + p4.ranked, BLUE, 28]],
    "Mildly positive, close to neutral. BTC-USD is not an outlier.", "p4");
}
{
  const lags = STORY.p6, before = lags.filter((l) => l.lag < 0), after = lags.filter((l) => l.lag > 0);
  const mean = (a) => a.reduce((t, l) => t + l.rho, 0) / a.length;
  story("5", "Does sentiment move before price, or after?", "Lead and Lag",
    ["Read the lag chart, from 6 hours before to 6 hours after.", "Compare the bars on each side of zero."],
    [[(mean(before) >= 0 ? "+" : "") + mean(before).toFixed(3), "average correlation with returns in the 6 hours BEFORE the text", CORAL, 34], [(mean(after) >= 0 ? "+" : "") + mean(after).toFixed(3), "average correlation with returns in the 6 hours AFTER the text", BLUE, 34]],
    "Price moves first, then people talk. Sentiment does not lead price.", "p6");
}
{
  const f = {}; STORY.p5.forEach((r) => { f[r.target] = r; });
  const fut = ["1h", "2h", "3h", "6h", "12h"].map((k) => f[k]);
  const lo = Math.min(...fut.map((r) => r.spearman_rho)), hi = Math.max(...fut.map((r) => r.spearman_rho));
  story("6", "How far can the analyst trust a link?", "Statistical Analysis",
    ["Open the BTC-USD row for each return horizon.", "Read the correlation, its adjusted p-value and the win rate."],
    [[lo.toFixed(3) + " to " + hi.toFixed(3), "correlation with returns 1 to 12 hours ahead. Adjusted p-values " + Math.min(...fut.map((r) => r.bh)).toFixed(2) + " to " + Math.max(...fut.map((r) => r.bh)).toFixed(2), CORAL, 24], [Math.min(...fut.map((r) => r.winrate)).toFixed(1) + "% to " + Math.max(...fut.map((r) => r.winrate)).toFixed(1) + "%", "win rate, against a 50% baseline", AMBER, 28]],
    "No reliable link to future price. Only the same hour's return shows a small one.", "p5");
}
{
  const p7 = STORY.p7, t = p7.by_type;
  story("7", "So what should the analyst watch?", "Hot Events",
    ["Set Z-score 1.5 and sentiment 0.05.", "Read the signal list and what price did after each."],
    [[fmt(p7.total_default), "BTC-USD signals: " + fmt(t.positive_sentiment_spike) + " positive, " + fmt(t.negative_sentiment_spike) + " negative, " + fmt(t.combined_signal) + " combined, " + fmt(t.volume_spike) + " volume", TEAL, 34], [p7.share_same_direction_1h.toFixed(1) + "%", "of signal hours: price moved the way sentiment pointed (1 hour)", AMBER, 34]],
    "About a coin flip. Use signals to pick hours to study, not to trade.", "p7");
}
{
  const s = newSlide("HERO", "5 User story");
  glow(s);
  head(s, "The analyst's conclusion on BTC-USD.", "5 User story", CORAL);
  card(s, 0.6, 1.95, 3.9, 3.85, "What was found", bl(["BTC-USD is the most-talked-about asset.", "Its mood is mildly positive.", "Sentiment follows price, not the other way round.", "No reliable link to future returns."]), { size: 14, headSize: 20, color: CORAL });
  card(s, 4.7, 1.95, 3.9, 3.85, "What to do with it", bl(["Watch Reddit as a mood and attention gauge.", "Use signals to choose hours to examine.", "Do not trade on Reddit sentiment alone."]), { size: 14, headSize: 20, color: GREEN });
  card(s, 8.8, 1.95, 3.9, 3.85, "Why it still helps", bl(["One place to see it all.", "A verified \"no signal\" stops the team chasing patterns that are not there."]), { size: 14, headSize: 20, color: AMBER });
  T(s, "Historical data. Not investment advice.", { x: 0.6, y: 6.1, w: 12.0, h: 0.6, fontSize: 16, color: SOFT });
}

// =============================================================== 6 EXECUTIVE QUESTIONS
qslide("Systems 1 and 2: volume and prices.", "Systems 1 and 2", [
  ["Question", "Answer", "Page"],
  ["Which asset is mentioned most?", "BTC-USD, 900,891 mentions (4.09% of texts). Then TSLA, NVDA and SPY.", "Ticker Mentions"],
  ["Is hourly volume rising or falling?", "No clear trend (ρ −0.060, p 0.111). Average 1,311 texts an hour, peak 17,362 on 9 Apr 2025.", "Reddit Volume"],
  ["What are the price and volume of each asset?", "Chosen per asset. BTC-USD went from 63,491 to 78,563, up 23.7%.", "Price and Return"],
  ["How do future returns differ by group?", "Averages near 0. Price rose in about 50 to 52% of hours. Stocks and ETFs have few samples at 6 hours and none at 12.", "Price and Return"],
  ["Which group is the most volatile?", "Stocks and ETFs (Normalized ATR 1.17%), then crypto 0.88%, then futures 0.53%.", "Price and Return"]]);
qslide("System 3: sentiment.", "System 3", [
  ["Question", "Answer", "Page"],
  ["Is overall sentiment positive or negative?", "Balanced, leaning slightly negative: 32.4% positive, 32.9% neutral, 34.7% negative.", "Market and Sentiment"],
  ["Which assets are most positive or negative?", "Most positive: NG=F +0.121, SHIB-USD +0.121, KO +0.114. Most negative: CL=F −0.217, ES=F −0.116, NQ=F −0.090.", "Market and Sentiment"],
  ["How well do VADER and FinBERT agree?", "Same class 50.15%, one neutral 37.59%, opposite 12.26%. The merge rule settles conflicts. 12.3% stay undecided and are flagged.", "Market and Sentiment"],
  ["What are the hourly positive, negative and neutral shares?", "A share chart over time, switchable from hourly to yearly.", "Market and Sentiment"]]);
qslide("System 4: relationships.", "System 4", [
  ["Question", "Answer", "Page"],
  ["How does sentiment relate to future price direction?", "No ability to predict was found: win rate about 50%, AUC about 0.50, correlation near zero. BTC-USD: ρ −0.013 to −0.003.", "Statistical Analysis"],
  ["Does the pattern differ by asset group?", "Across the nine panels the result stays near 50%. Stricter filters (clear-direction texts, volume spikes) did not help.", "Statistical Analysis"],
  ["Is earlier sentiment better than current?", "No. For BTC-USD price moves first: average ρ +0.026 for the 6 hours before a text, −0.003 for the 6 hours after.", "Lead and Lag"],
  ["Which factor deserves the most weight?", "Logistic regression compares six variable groups: level, direction, vote, volume, lag, momentum. With AUC near 0.50 it is not read as a signal.", "Statistical Analysis"]]);
qslide("System 5: investment analysis.", "System 5", [
  ["Question", "Answer", "Page"],
  ["Which assets have unusually high sentiment or volume Z-score?", "Ranking by sentiment (top: NG=F, SHIB-USD, KO) and by Z-score for the chosen period. Market-wide, 1,968 hours have Z above 1.5.", "Market and Sentiment"],
  ["Which assets show an interesting win rate, by horizon?", "Win rates sit near 50% in every horizon. BTC-USD: 49.3% to 50.1%.", "Statistical Analysis"],
  ["How do thresholds change the number of conditions found?", "Stricter means fewer. BTC-USD at sentiment 0.05: 12,259 signals at Z 1.5, 11,912 at Z 2.5. At sentiment 0.30: 2,371 and 1,326.", "Hot Events"],
  ["Does majority sentiment agree with the future return direction?", "No visible link. After BTC-USD signal hours, price moved the way sentiment pointed 50.9% of the time (1 hour).", "Hot Events"]]);
qslide("System 6: signal detection.", "System 6", [
  ["Question", "Answer", "Page"],
  ["Which assets meet the signal conditions?", "The signal list shows every asset that meets the thresholds in the period. BTC-USD alone has 12,259 at Z 1.5 and sentiment 0.05.", "Hot Events"],
  ["Which types of signal were found?", "BTC-USD: 6,515 positive spikes, 3,868 negative spikes, 1,286 combined, 590 volume spikes.", "Hot Events"],
  ["What do past statistics say about flagged assets?", "Historical win rate and correlation sit beside each signal: near 50% and near 0. Not a promise of return.", "Hot Events"],
  ["How do thresholds change the number and type of signals?", "30 settings (Z-score × sentiment × horizon). Six threshold sets found 312,115 signals in total.", "Hot Events"]]);
{
  const s = newSlide("HERO", "6 Executive questions");
  glow(s);
  head(s, "Reddit sentiment describes the market, not where it goes next.", "6 Executive questions", GREEN);
  card(s, 0.6, 1.95, 3.9, 3.75, "What the system gives", bl(["One place for sentiment and prices.", "A tool to explore history and test hypotheses.", "Signals as a start for deeper checks."]), { size: 14.5, headSize: 21, color: GREEN });
  card(s, 4.7, 1.95, 3.9, 3.75, "What the results show", bl(["No ability to predict price direction in this data.", "Direction accuracy about 50%, AUC about 0.50, correlation near zero.", "Stricter filters did not help."]), { size: 14.5, headSize: 21, color: CORAL });
  card(s, 8.8, 1.95, 3.9, 3.75, "How to use it", bl(["As supporting data for interpretation.", "Not as a price signal on its own.", "Not investment advice."]), { size: 14.5, headSize: 21, color: AMBER });
  T(s, "A clear \"no signal\" is still a result: it stops the team from chasing patterns that are not there.", { x: 0.6, y: 6.0, w: 12.1, h: 0.8, fontSize: 18, bold: true, color: SOFT });
}

// =============================================================== 7 QA
{
  const s = newSlide("DARK", "7 QA");
  head(s, "The system was tested in three parts.", "7 QA", BLUE);
  stat(s, 0.6, 1.95, 5.9, "32 / 32", "checks passed on data logic and linking (25 Oct 2026).", TEAL, 44);
  stat(s, 6.8, 1.95, 5.9, "371 / 371", "dashboard numbers matched direct SQL (30 Oct 2026).", TEAL, 44);
  card(s, 0.6, 3.95, 3.9, 2.85, "Data logic", bl(["Cleaned text is never empty.", "Final sentiment stays within −1 and +1.", "Future returns are right for each horizon.", "Only the 34 assets are extracted."]), { size: 12.5, headSize: 17 });
  card(s, 4.7, 3.95, 3.9, 2.85, "Data linking", bl(["Tables join correctly on timestamp and Ticker.", "The merge rule was checked on a hand-labelled sample."]), { size: 13, headSize: 17, color: BLUE });
  card(s, 8.8, 3.95, 3.9, 2.85, "Display", bl(["Charts, tables, filters and key numbers on Streamlit match the database."]), { size: 13.5, headSize: 17, color: AMBER });
}
{
  const s = newSlide("DARK", "7 QA");
  head(s, "Five problems met along the way, and how each was handled.", "7 QA", BLUE);
  const probs = [["Price data", "Few hourly bars for stocks and ETFs; rows with no close price.", "Returns only when a bar sits exactly n hours later; unavailable cases say insufficient data.", TEAL],
    ["Sentiment", "FinBERT 48.4% neutral against VADER 30.3%; slang; 12.3% undecidable; parent title shifts about 21.8%.", "Keyword merge rule, an is_ambiguous flag, a hand-labelled check, and the post title is always included.", BLUE],
    ["Statistics", "Many tests raise the chance of lucky results; time series can leak the future.", "Benjamini–Hochberg adjustment and time-ordered splits with a gap.", AMBER],
    ["Size and tools", "A 12.8 GB database; FinBERT on 22 million texts took hours.", "GPU with fp16, resumable scripts, read-only database access.", VIOLET],
    ["Reddit access", "Reddit changed its API access policy in March 2026.", "Use historical monthly files; scope is historical, not real-time.", CORAL]];
  probs.forEach((p, i) => {
    const y = 1.85 + i * 1.0;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y, w: 12.1, h: 0.88, fill: { color: SURF }, line: { color: EDGE, width: 0.75 }, rectRadius: 0.08, objectName: "ProblemRow" });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: y + 0.1, w: 0.07, h: 0.68, fill: { color: p[3] }, line: { color: p[3], width: 0 } });
    T(s, p[0], { x: 0.85, y, w: 1.9, h: 0.88, fontSize: 15, bold: true, color: p[3], valign: "middle" });
    T(s, p[1], { x: 2.8, y, w: 4.6, h: 0.88, fontSize: 12.5, color: SOFT, valign: "middle" });
    T(s, p[2], { x: 7.6, y, w: 5.0, h: 0.88, fontSize: 12.5, color: INK, valign: "middle" });
  });
}
{
  const s = newSlide("DARK", "7 QA");
  head(s, "Questions you may get.", "7 QA", BLUE);
  card(s, 0.6, 1.9, 6.0, 2.4, "If it cannot predict, what is it for?", ["It is a tool to explore historical data and test hypotheses. Reddit sentiment should not be used alone as a price signal."], { size: 15, headSize: 18 });
  card(s, 6.8, 1.9, 5.9, 2.4, "Why adjust the p-values?", ["Tests run across assets, horizons and 9 data panels, so some look significant by chance. Benjamini–Hochberg controls the false discovery rate."], { size: 15, headSize: 18, color: BLUE });
  card(s, 0.6, 4.5, 6.0, 2.3, "Is Reddit a proxy for the market?", ["Not fully. r/wallstreetbets is 73.2% of the texts, so pooled results mostly reflect that crowd."], { size: 15, headSize: 18, color: AMBER });
  card(s, 6.8, 4.5, 5.9, 2.3, "Why historical data, not real-time?", ["Reddit tightened API access in March 2026, so the scope is historical data from Academic Torrents."], { size: 15, headSize: 18, color: CORAL });
}
{
  const s = newSlide("HERO", "7 QA");
  glow(s);
  s.addShape(pres.shapes.RECTANGLE, { x: 0.8, y: 2.0, w: 0.9, h: 0.08, fill: { color: TEAL }, line: { color: TEAL, width: 0 } });
  T(s, "Q&A", { x: 0.8, y: 2.3, w: 11.7, h: 1.8, fontSize: 88, bold: true, fontFace: HEAD });
  T(s, "Thank you. Happy to open any page.", { x: 0.8, y: 4.3, w: 11.7, h: 0.7, fontSize: 24, color: SOFT });
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  console.log("written", OUT, SLIDE_IDX + " slides");
})();
