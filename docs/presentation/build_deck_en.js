// English version of the defence deck (written by Claude 2026-11-07). Speaker notes are read from notes_th.json (Thai, same slide order).
// Run: NODE_PATH=<scratch>/node_modules node build_deck_en.js <repo_root> <crops_dir> docs/presentation/defence_deck_en.pptx   (see build_deck.js for the screenshot prerequisites)
// Full defence deck v2 (7 parts).  Numbers: output/tables/*.csv, output/reports/*.md, analysis_results (read-only SQL, 2026-11-07).
// Run: NODE_PATH=<scratch>/node_modules node build_deck2.js <repo_root> <crops_dir> <out.pptx>
// Full defence deck v2 (7 parts).  Numbers: output/tables/*.csv, output/reports/*.md, analysis_results (read-only SQL, 2026-11-07).
// Run: NODE_PATH=<scratch>/node_modules node build_deck2.js <repo_root> <crops_dir> <out.pptx>
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require("C:/Users/paiigak/.claude/skills/synced/74d9102e-f432-4242-9908-d57add8d1b8b_c6ca036c-a871-48cb-a49f-51c6fdc4d213/pptx/scripts/apply_theme.js");

const ROOT = process.argv[2], CROPS = process.argv[3], OUT = process.argv[4];
const NOTES = JSON.parse(fs.readFileSync(path.join(__dirname, "notes_th.json"), "utf8"));
let SLIDE_IDX = 0;
const FIG = (f) => path.join(ROOT, "output", "figures", f);
let SIZES = {};
try { SIZES = JSON.parse(fs.readFileSync(path.join(CROPS, "sizes.json"), "utf8")); } catch (e) { /* no screenshots */ }

const FONT = "Calibri";
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
pres.defineSlideMaster({ title: "LIGHT", background: { color: C.background1 }, objects: [], slideNumber: footer });

let sectionNow = null;
function newSlide(master, section) {
  if (section !== sectionNow) { pres.addSection({ title: section }); sectionNow = section; }
  const sl = pres.addSlide({ masterName: master, sectionTitle: section });
  if (NOTES[SLIDE_IDX]) sl.addNotes(NOTES[SLIDE_IDX]);   // speaker notes stay in Thai (my working language), same order as the Thai deck
  SLIDE_IDX += 1;
  return sl;
}
function head(s, text, tag, dark) {
  s.addText(text, { x: 0.6, y: 0.35, w: 10.6, h: 0.95, fontSize: 30, bold: true, color: dark ? C.background1 : C.text2, valign: "top", margin: 0, isTextBox: true, objectName: "Title" });
  if (tag) s.addText(tag, { x: 8.0, y: 0.08, w: 4.75, h: 0.3, fontSize: 12, bold: false, color: dark ? "7FD6CF" : C.accent5, align: "right", margin: 0, isTextBox: true, objectName: "SectionTag" });
}
function card(s, x, y, w, h, title, body, opt = {}) {
  if (Array.isArray(body)) body = body.map((t) => (typeof t === "string" ? { text: t } : t));
  s.addShape(pres.shapes.LINE, { x, y, w, h: 0, line: { color: opt.headColor || C.accent1, width: 1.5 } });
  s.addText(title, { x, y: y + 0.12, w, h: 0.45, fontSize: (opt.headSize || 19) + 1, bold: true, color: opt.headColor || C.text2, margin: 0, valign: "top", isTextBox: true });
  s.addText(body, { x, y: y + 0.65, w, h: h - 0.7, fontSize: (opt.size || 16) + 1, color: C.text1, margin: 0, valign: "top", isTextBox: true, paraSpaceAfter: 6 });
}
const bl = (items) => items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } }));
function stat(s, x, y, w, big, label, color, bigSize) {
  s.addText(big, { x, y, w, h: 0.85, fontSize: bigSize || 36, bold: true, color: color || C.accent1, margin: 0, isTextBox: true, valign: "bottom" });
  s.addText(label, { x, y: y + 0.9, w, h: 0.8, fontSize: 15, color: C.text1, margin: 0, isTextBox: true, valign: "top" });
}
function pill(s, x, y, w, text, fill) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 0.45, fill: { color: fill || C.accent1 }, rectRadius: 0.1, objectName: "Pill" });
  s.addText(text, { x, y, w, h: 0.45, fontSize: 15, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0, isTextBox: true });
}
function openPage(s, name) { pill(s, 0.6, 6.78, 5.9, "Live demo  ·  " + name, TEAL); }
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
  const hdr = rows[0].map((t) => ({ text: t, options: { bold: true, color: NAVY, fill: { color: "EAF0F6" } } }));
  s.addTable([hdr, ...rows.slice(1)], Object.assign({ fontSize: 13, fontFace: FONT, color: INK, border: [{ type: "none" }, { type: "none" }, { type: "solid", pt: 0.75, color: "DCE3EC" }, { type: "none" }], fill: { color: "FFFFFF" },
    valign: "middle", margin: [0.05, 0.1, 0.05, 0.1] }, opt));
}
// =============================================================== 1 Title
{
  const s = newSlide("DARK", "Opening");
  s.addText("What Reddit's mood tells us about the market.", { x: 0.8, y: 1.9, w: 11.7, h: 1.4, fontSize: 44, bold: true, color: C.background1, margin: 0, isTextBox: true, valign: "top" });
  s.addText("Data warehouse, business intelligence and advanced analytics of Reddit community sentiment toward securities price movements.", { x: 0.8, y: 3.5, w: 11.7, h: 0.9, fontSize: 20, color: "CADCFC", margin: 0, isTextBox: true, valign: "top" });
  s.addText("Rithipong Leanghirunkun  |  Chulalongkorn University, MSc BIT", { x: 0.8, y: 6.3, w: 11.7, h: 0.4, fontSize: 16, color: "CADCFC", margin: 0, isTextBox: true });
  s.addText("Historical data, Oct 2024 to Aug 2026. Not real-time. Not investment advice.", { x: 0.8, y: 6.7, w: 11.7, h: 0.4, fontSize: 14, color: "9FB3D1", margin: 0, isTextBox: true });
}
// =============================================================== 2 Agenda
{
  const s = newSlide("LIGHT", "Opening");
  head(s, "Seven parts.", null);
  const items = ["The pain point", "The users", "The architecture", "The dashboards", "A live walk-through", "Executive questions", "QA"];
  items.forEach((t, i) => {
    const col = i < 4 ? 0 : 1, row = i < 4 ? i : i - 4;
    const x = 0.6 + col * 6.2, y = 1.8 + row * 1.15;
    s.addText(String(i + 1), { x, y, w: 0.7, h: 0.7, fontSize: 32, bold: true, color: i === 4 ? C.accent2 : C.accent1, margin: 0, isTextBox: true, valign: "middle" });
    s.addText(t, { x: x + 0.8, y, w: 4.9, h: 0.7, fontSize: 24, color: C.text2, margin: 0, isTextBox: true, valign: "middle" });
  });
}

// =============================================================== PART 1: PAIN POINT
{
  const s = newSlide("LIGHT", "1 Pain point");
  head(s, "Analysts have no single place to see Reddit sentiment next to prices.", "1 Pain point");
  card(s, 0.6, 1.8, 2.8, 3.4, "No organised data", bl(["Reddit data is collected by hand.", "It is scattered and not ready to use with prices."]), { size: 15, headSize: 18 });
  card(s, 3.65, 1.8, 2.8, 3.4, "No text metrics", bl(["Posts are not turned into numbers.", "No sentiment score, volume or positive and negative share."]), { size: 15, headSize: 18, headColor: C.accent2 });
  card(s, 6.7, 1.8, 2.8, 3.4, "Data lives apart", bl(["Prices and sentiment sit in different places.", "No single source of truth."]), { size: 15, headSize: 18, headColor: C.accent4 });
  card(s, 9.75, 1.8, 2.8, 3.4, "No signal flags", bl(["Nothing flags unusual volume.", "Nothing flags clear sentiment shifts."]), { size: 15, headSize: 18, headColor: C.accent3 });
}
{
  const s = newSlide("LIGHT", "1 Pain point");
  head(s, "Does Reddit sentiment relate to future price?", "1 Pain point");
  card(s, 0.6, 1.8, 5.9, 2.7, "What the project does", bl(["Stores Reddit and price data in one warehouse.", "Scores every text with VADER and FinBERT.", "Shows everything on one dashboard.", "Tests links to future return against a random baseline.", "Flags unusual hours."]), { size: 15, headSize: 18 });
  card(s, 6.9, 1.8, 5.7, 2.7, "Scope", bl(["Six communities, from wallstreetbets to CryptoCurrency.", "34 assets: 22 stocks and ETFs, 6 crypto, 6 futures.", "Hourly data, Oct 2024 to Aug 2026."]), { size: 15, headSize: 18, headColor: C.accent4 });
  card(s, 0.6, 4.8, 12.0, 1.8, "What it is not", bl(["Not investment advice, not an exact price forecast, not real-time.", "A clear \"no signal\" is still a result."]), { size: 16, headSize: 18, headColor: C.accent2 });
}

// =============================================================== PART 2: USERS
{
  const s = newSlide("LIGHT", "2 Users");
  head(s, "An analyst team that wants another read on the market.", "2 Users");
  s.addShape(pres.shapes.OVAL, { x: 0.8, y: 2.2, w: 2.4, h: 2.4, fill: { color: C.accent1 }, objectName: "UserCircle" });
  s.addText("Analyst\nteam", { x: 0.8, y: 2.2, w: 2.4, h: 2.4, fontSize: 24, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0, isTextBox: true });
  card(s, 4.0, 1.8, 4.2, 2.1, "Gauge attention", ["How often assets are mentioned on Reddit."], { size: 16 });
  card(s, 8.6, 1.8, 4.0, 2.1, "Follow prices", ["Price, volume and future returns per asset."], { size: 16, headColor: C.accent4 });
  card(s, 4.0, 4.3, 4.2, 2.3, "Check relationships", ["Use sentiment and statistics as an extra input when reading the market."], { size: 16, headColor: C.accent3 });
  card(s, 8.6, 4.3, 4.0, 2.3, "Find hours to review", ["Use the signal list as a starting point for deeper checks."], { size: 16, headColor: C.accent2 });
}
{
  const s = newSlide("LIGHT", "2 Users");
  head(s, "A path through the dashboard in four steps.", "2 Users");
  const steps = [["1  Watch", "What is the market talking about? What looks unusual?", "Home, pages 1 and 2", C.accent1],
    ["2  Compare", "What did price do? Did sentiment move with it?", "Pages 3 and 4", C.accent4],
    ["3  Verify", "Who moved first? How far can we trust it?", "Pages 6 and 5", C.accent3],
    ["4  Follow up", "Set thresholds and list the hours to review.", "Page 7", C.accent2]];
  steps.forEach((st, i) => {
    const x = 0.6 + i * 3.1;
    card(s, x, 2.0, 2.8, 3.4, st[0], [st[1]], { size: 16, headSize: 20, headColor: st[3] });
    s.addText(st[2], { x, y: 4.7, w: 2.8, h: 0.45, fontSize: 16, bold: true, color: st[3], margin: 0, isTextBox: true });
  });
  s.addText("One shared filter set works on every page.", { x: 0.6, y: 5.9, w: 12.0, h: 0.5, fontSize: 18, color: C.text2, margin: 0, isTextBox: true });
}

// =============================================================== PART 3: ARCHITECTURE
{
  const s = newSlide("LIGHT", "3 Architecture");
  head(s, "Raw sources flow through SQLite to the dashboard.", "3 Architecture");
  box(s, 0.45, 1.6, 2.2, 1.5, "Academic Torrents", "Historical Reddit\n6 communities", "F3F6FA");
  box(s, 0.45, 3.5, 2.2, 1.5, "yfinance", "Hourly prices\n34 assets", "F3F6FA");
  box(s, 3.0, 1.6, 2.0, 1.5, "Ingest", "Reddit extract", "FFFFFF");
  box(s, 3.0, 3.5, 2.0, 1.5, "Ingest", "Market fetch", "FFFFFF");
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.4, y: 1.6, w: 2.6, h: 3.4, fill: { color: NAVY }, rectRadius: 0.1, objectName: "SQLiteBox" });
  s.addText("SQLite", { x: 5.4, y: 1.7, w: 2.6, h: 0.5, fontSize: 22, bold: true, color: C.background1, align: "center", margin: 0, isTextBox: true });
  s.addText("Single source of truth.", { x: 5.5, y: 2.2, w: 2.4, h: 0.4, fontSize: 13, color: "CADCFC", align: "center", margin: 0, isTextBox: true });
  s.addText([{ text: "Raw layer", options: { breakLine: true } }, { text: "Features", options: { breakLine: true } }, { text: "Star schema", options: { breakLine: true } }, { text: "Analysis results", options: {} }],
    { x: 5.7, y: 2.9, w: 2.2, h: 1.9, fontSize: 15, color: C.background1, margin: 0, isTextBox: true, valign: "top", paraSpaceAfter: 6 });
  box(s, 8.35, 1.6, 2.4, 3.4, "Processing", "Clean text and tag tickers\nPrice features\nVADER + FinBERT\nStatistics\nSignal detection", "FFFFFF");
  box(s, 11.05, 1.6, 1.85, 3.4, "Dashboard", "Streamlit\nHome + 7 pages\nRead-only", C.accent1, C.background1);
  arrow(s, 2.67, 2.35, 2.98, 2.35); arrow(s, 2.67, 4.25, 2.98, 4.25);
  arrow(s, 5.02, 2.35, 5.38, 2.9); arrow(s, 5.02, 4.25, 5.38, 3.9);
  arrow(s, 8.02, 3.3, 8.33, 3.3); arrow(s, 10.77, 3.3, 11.03, 3.3);
  s.addText("1 Reddit warehouse   2 Price warehouse   3 Sentiment   4 Relationships   5 Investment analysis   6 Signal detection", { x: 0.45, y: 5.45, w: 12.4, h: 0.5, fontSize: 15, bold: true, color: C.text2, margin: 0, isTextBox: true });
  s.addText("Every step is a repeatable script. All times are UTC. Raw data is never edited.", { x: 0.45, y: 6.0, w: 12.4, h: 0.5, fontSize: 15, color: C.text1, margin: 0, isTextBox: true });
}
{
  const s = newSlide("LIGHT", "3 Architecture");
  head(s, "From 24.5 million raw texts to 22.0 million usable ones.", "3 Architecture");
  s.addChart(pres.charts.BAR, [{ name: "Texts (millions)", labels: ["Raw, 6 communities", "Readable", "Cleaned", "Passed quality filter", "Mention a target asset"],
    values: [24.519, 22.841, 22.522, 22.029, 3.473] }], {
    x: 0.6, y: 1.5, w: 7.4, h: 5.0, barDir: "bar", chartColors: [TEAL], showLegend: false, showTitle: false, showValue: true, dataLabelPosition: "outEnd",
    dataLabelFormatCode: "0.00", valAxisHidden: true, valGridLine: { style: "none" }, catAxisOrientation: "maxMin", valAxisMaxVal: 29, ...chartCommon });
  card(s, 8.5, 1.8, 4.1, 2.3, "Removed", bl(["1.68 million deleted on Reddit.", "417,853 from bots and moderators.", "69,049 too short, 5,729 not English."]), { size: 14, headSize: 17 });
  card(s, 8.5, 4.4, 4.1, 2.2, "Worth knowing", bl(["15.8% of texts mention a target asset.", "wallstreetbets is 73.2% of all texts."]), { size: 14, headSize: 17, headColor: C.accent4 });
}
{
  const s = newSlide("LIGHT", "3 Architecture");
  head(s, "Star schema with 3 fact tables and 6 dimensions.", "3 Architecture");
  const facts = [["FactRedditVolume", "618,518 rows", "Message volume and mention counts.\nDimTime, DimTicker, DimSource.", C.accent1],
    ["FactMarketPrice", "250,253 rows", "Price, volume, Current Return, RSI, ATR.\nDimTime, DimTicker.", C.accent4],
    ["FactMarketSentiment", "250,253 rows", "Sentiment, future returns, win rate.\nDimTime, DimTicker, DimSentimentSource, DimDetectionConfig, DimMajoritySentiment.", C.accent3]];
  facts.forEach((f, i) => {
    const y = 1.6 + i * 1.6;
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y, w: 2.5, h: 1.4, fill: { color: f[3] }, objectName: "FactHead" + i });
    s.addText(f[0], { x: 0.65, y: y + 0.15, w: 2.4, h: 0.6, fontSize: 16, bold: true, color: C.background1, margin: 0, isTextBox: true, align: "center", valign: "middle" });
    s.addText(f[1], { x: 0.65, y: y + 0.8, w: 2.4, h: 0.4, fontSize: 15, color: C.background1, margin: 0, isTextBox: true, align: "center" });
    s.addText(f[2], { x: 3.3, y, w: 4.7, h: 1.4, fontSize: 15, color: C.text1, margin: 0, isTextBox: true, valign: "middle" });
  });
  const dims = [["DimTime", "17,544 hours, from year down to hour."], ["DimTicker", "34 assets, by group, symbol and name."], ["DimSource", "12 sources, community by post or comment."],
    ["DimSentimentSource", "7 sources, by platform, community and model."], ["DimMajoritySentiment", "Positive, negative or neutral."], ["DimDetectionConfig", "30 stored settings, Z-score by sentiment by horizon."]];
  card(s, 8.4, 1.6, 4.2, 4.8, "Dimensions", dims.map((d, i) => ({ text: d[0] + ". " + d[1], options: { bullet: true, breakLine: i < dims.length - 1 } })), { size: 13, headSize: 17 });
}
{
  const s = newSlide("LIGHT", "3 Architecture");
  head(s, "The two sentiment models agree only half the time, so we need a merge rule.", "3 Architecture");
  s.addChart(pres.charts.DOUGHNUT, [{ name: "Share", labels: ["Same direction", "One neutral, one directional", "Opposite directions"], values: [50.15, 37.59, 12.25] }], {
    x: 0.5, y: 1.6, w: 6.0, h: 5.0, holeSize: 50, chartColors: [GREEN, GOLD, RED], showLegend: true, legendPos: "b", showPercent: true, showValue: false, dataLabelColor: "FFFFFF", dataLabelFontSize: 15,
    showTitle: false, ...chartCommon, dataLabelColor: "FFFFFF" });
  card(s, 6.9, 1.8, 5.7, 2.7, "Merge rule", bl(["Same direction. Average the scores. If they differ by more than 0.50, use the smaller one.", "One neutral. Use the directional one, unless a finance keyword disagrees.", "Opposite. A keyword decides, otherwise the result is 0.", "The neutral band is ±0.05."]), { size: 13, headSize: 17 });
  card(s, 6.9, 4.7, 5.7, 1.9, "Why", bl(["VADER reads everyday mood. FinBERT learned financial language.", "The 12.3% that cannot be resolved are set to 0 and flagged."]), { size: 13, headSize: 17, headColor: C.accent4 });
}
{
  const s = newSlide("LIGHT", "3 Architecture");
  head(s, "Tested against 400 human labels, the rule stays as it is.", "3 Architecture");
  s.addChart(pres.charts.BAR, [
    { name: "VADER alone", labels: ["All groups", "Strong conflict with keyword"], values: [43.3, 46] },
    { name: "FinBERT alone", labels: ["All groups", "Strong conflict with keyword"], values: [47.9, 42] },
    { name: "Merge rule", labels: ["All groups", "Strong conflict with keyword"], values: [47.1, 68] }], {
    x: 0.6, y: 1.6, w: 6.8, h: 4.2, barDir: "col", chartColors: ["9FB3D1", "6B7A90", TEAL], showLegend: true, legendPos: "b", showTitle: true, title: "Accuracy against human labels (%)",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0", valAxisHidden: true, valGridLine: { style: "none" }, valAxisMinVal: 0, valAxisMaxVal: 80, ...chartCommon });
  s.addText("One labeller. 163 of 400 labelled neutral.", { x: 0.6, y: 6.0, w: 6.8, h: 0.4, fontSize: 14, color: C.accent5, margin: 0, isTextBox: true });
  card(s, 7.9, 1.8, 4.7, 2.2, "Method", bl(["400 comments across 7 rule groups, split into tune and test.", "A new rule had to win by 5 points on tune and hold on test."]), { size: 14, headSize: 17 });
  card(s, 7.9, 4.3, 4.7, 2.3, "Result", bl(["No alternative cleared the bar.", "With a keyword conflict the merge rule scores 68%, against 42 to 46%.", "Overall accuracy is about 47%, because labels follow the commenter's stance."]), { size: 14, headSize: 17, headColor: C.accent4 });
}
{
  const s = newSlide("LIGHT", "3 Architecture");
  head(s, "Three habits keep the results honest.", "3 Architecture");
  card(s, 0.6, 1.8, 3.8, 4.6, "No future data", bl(["Z-score uses the previous 24 hours only.", "No future returns or vote counts as predictors.", "Time-ordered splits with a 12-hour gap."]), { size: 15, headSize: 19, headColor: C.accent2 });
  card(s, 4.8, 1.8, 3.8, 4.6, "Comparable data", bl(["All times in UTC.", "Bars rounded to the hour.", "No text means NULL, not 0.", "Closed-market rows without a price are dropped."]), { size: 15, headSize: 19 });
  card(s, 9.0, 1.8, 3.6, 4.6, "Traceable", bl(["Fixed order of scripts.", "Settings live in one place.", "Thesis numbers come from scripts."]), { size: 15, headSize: 19, headColor: C.accent4 });
}

// =============================================================== PART 4: DASHBOARD EACH
{
  const s = newSlide("LIGHT", "4 Dashboards");
  head(s, "Home plus seven pages, with one shared filter set.", "4 Dashboards");
  const rows = [["Page", "System", "Answers"],
    ["Home", "Overview", "Summary cards and how to use."],
    ["1 Reddit Volume", "1", "When is chatter unusually high?"],
    ["2 Ticker Mentions", "1", "Which assets are talked about most?"],
    ["3 Price and Return", "2", "Price, returns and volatility."],
    ["4 Market and Sentiment", "3 and 5", "Sentiment against price."],
    ["5 Statistical Analysis", "4 and 5", "Correlation, win rate, logistic."],
    ["6 Lead and Lag", "Extra", "Who moves first?"],
    ["7 Hot Events", "6", "Signals at thresholds you set."]];
  table(s, rows, { x: 0.6, y: 1.6, w: 7.8, colW: [2.6, 1.3, 3.9], fontSize: 14, rowH: 0.52 });
  card(s, 8.9, 1.6, 3.7, 4.6, "Filters", bl(["Time.", "Community, post or comment.", "Asset group and symbol.", "Majority sentiment.", "Page 7 adds Z-score and sentiment. Horizons show side by side."]), { size: 14, headSize: 18 });
}
const pageSlides = [
  { key: "home", title: "Home gives the overview before you dig in.", tag: "Home", cards: [
    ["Shows", bl(["The data range and text counts.", "Summary cards for the selected filters."])], ["Use it to", bl(["Pick a time range and assets, then open a page."])]] },
  { key: "p1", title: "When is the market unusually chatty?", tag: "Page 1 Reddit Volume", cards: [
    ["Measures", bl(["Reddit volume.", "Z-score, volume against the previous 24 hours."])],
    ["On the page", bl(["Five summary cards.", "Volume over time.", "Z-score with the 1.5 line.", "Split by community."])]] },
  { key: "p2", title: "Which assets get talked about most?", tag: "Page 2 Ticker Mentions", cards: [
    ["Measures", bl(["Mention count.", "Mention rate, mentions divided by volume."])],
    ["On the page", bl(["Ranking of top assets.", "Mention trend.", "Community by content type."])]] },
  { key: "p3", title: "What did price do?", tag: "Page 3 Price and Return", cards: [
    ["Measures", bl(["Current Return, volume Z-score and Normalized ATR.", "Future returns at 1, 2, 3, 6 and 12 hours."])],
    ["On the page", bl(["Price, RSI and ATR.", "A measures table.", "Future returns and volatility by group."])]] },
  { key: "p4", title: "Does sentiment move with price?", tag: "Page 4 Market and Sentiment", cards: [
    ["Measures", bl(["Sentiment score and momentum.", "Positive, negative and neutral shares."])],
    ["On the page", bl(["Price against sentiment.", "Sentiment level against return.", "Shares over time.", "Asset ranking."])]] },
  { key: "p5", title: "How far can we trust the relationship?", tag: "Page 5 Statistical Analysis", cards: [
    ["Measures", bl(["Spearman, Pearson and win rate.", "Logistic regression, AUC."])],
    ["On the page", bl(["Summary cards.", "Heatmap of asset by horizon.", "AUC.", "Importance of six variable groups."])]] },
  { key: "p6", title: "Who moves first, sentiment or price?", tag: "Page 6 Lead and Lag", cards: [
    ["Asks", bl(["Does sentiment relate to earlier or later returns?", "Does sentiment change after big moves?"])],
    ["On the page", bl(["Lead and lag correlation.", "Sentiment after price rises or falls."])]] },
  { key: "p7", title: "Which hours deserve a second look?", tag: "Page 7 Hot Events", cards: [
    ["You set", bl(["Minimum Z-score and sentiment.", "Minimum texts per hour."])],
    ["On the page", bl(["Counts by signal type.", "The latest 300 signals.", "Win rate after a signal."])]] },
];
pageSlides.forEach((p) => {
  const s = newSlide("LIGHT", "4 Dashboards");
  head(s, p.title, "4 Dashboards  ·  " + p.tag);
  card(s, 0.6, 1.7, 5.6, 2.2, p.cards[0][0], p.cards[0][1], { size: 15, headSize: 18 });
  card(s, 0.6, 4.2, 5.6, 2.5, p.cards[1][0], p.cards[1][1], { size: 15, headSize: 18, headColor: C.accent4 });
  shot(s, p.key, 6.7, 1.5, 6.1, 5.2, "Default filter, last year. The dashboard itself is in Thai.");
});

// =============================================================== PART 5: STORIES (live)
{
  const s = newSlide("DARK", "5 Walk-through");
  head(s, "A live walk-through, with BTC-USD as the example.", "5 Walk-through", true);
  const acts = [["1", "When does the market talk?", "Page 1"], ["2", "What does it talk about?", "Page 2"], ["3", "What did price do?", "Page 3"], ["4", "Does mood follow price?", "Page 4"], ["5", "Who moves first?", "Page 6"], ["6", "How far can we trust it?", "Page 5"], ["7", "How do we use it?", "Page 7"]];
  acts.forEach((a, i) => {
    const x = 0.6 + i * 1.77;
    s.addText(a[0], { x, y: 1.9, w: 1.65, h: 0.8, fontSize: 36, bold: true, color: "7FD6CF", margin: 0, isTextBox: true });
    s.addText(a[1], { x, y: 2.75, w: 1.6, h: 0.9, fontSize: 15, bold: true, color: C.background1, margin: 0, isTextBox: true, valign: "top" });
    s.addText(a[2], { x, y: 3.7, w: 1.6, h: 0.4, fontSize: 14, color: "CADCFC", margin: 0, isTextBox: true });
  });
  s.addText("BTC-USD is the most-mentioned asset (900,891 mentions), trades around the clock and has future returns at every horizon.", { x: 0.6, y: 4.9, w: 8.0, h: 1.2, fontSize: 18, color: "CADCFC", margin: 0, isTextBox: true, valign: "top" });
  s.addText("Before you start, pick BTC-USD and set the date range on every page.", { x: 9.0, y: 4.9, w: 3.8, h: 1.4, fontSize: 16, bold: true, color: "FFD98A", margin: 0, isTextBox: true, valign: "top" });
}
function act(num, title, openName, steps, say) {
  const s = newSlide("LIGHT", "5 Walk-through");
  head(s, title, "5 Walk-through  ·  Story " + num);
  openPage(s, openName);
  card(s, 0.6, 1.6, 5.9, 2.8, "Steps", steps, { size: 15, headSize: 18 });
  card(s, 0.6, 4.55, 5.9, 2.1, "Finance view", say, { size: 14, headSize: 18, headColor: C.accent4 });
  return s;
}
{
  const s = act("1", "When does the market talk?", "Page 1 Reddit Volume, full range",
    bl(["Pick the full range and all communities.", "Point at the Z-score line and the 1.5 line.", "Find the peak, 9 Apr 2025, 17:00 UTC.", "Check price in the same hour on page 3."]),
    bl(["Z-score is abnormal volume against the previous 24 hours.", "The peak lines up with sharp moves in several assets."]));
  s.addChart(pres.charts.BAR, [{ name: "Return in that hour (%)", labels: ["BTC-USD", "SPY", "TSLA"], values: [4.959, 2.672, 7.363] }], {
    x: 6.8, y: 1.5, w: 6.0, h: 3.2, barDir: "col", chartColors: [GOLD], showLegend: false, showTitle: true, title: "Current Return in the peak hour (%)", showValue: true, dataLabelPosition: "outEnd",
    dataLabelFormatCode: "0.00", valAxisHidden: true, valGridLine: { style: "none" }, valAxisMinVal: 0, ...chartCommon });
  stat(s, 6.8, 4.85, 2.9, "17,362", "texts in one hour, against an average of 1,311.", C.accent2);
  stat(s, 9.9, 4.85, 2.9, "1,968", "hours with a Z-score above 1.5.", C.accent2);
}
{
  const s = act("2", "What does it talk about?", "Page 2 Ticker Mentions, BTC-USD",
    bl(["Read the ranking of most-mentioned assets.", "Pick BTC-USD and read its trend.", "Check community by content type."]),
    bl(["Attention piles into a handful of names.", "Assets with many texts give steadier sentiment readings."]));
  const names = ["MSTR", "AAPL", "AMD", "ETH-USD", "MSFT", "GC=F", "SPY", "NVDA", "TSLA", "BTC-USD"], vals = [165173, 169589, 169937, 208030, 213956, 289269, 545960, 601744, 759742, 900891];
  s.addChart(pres.charts.BAR, [{ name: "Mentions", labels: names, values: vals }], {
    x: 6.8, y: 1.5, w: 6.0, h: 5.1, barDir: "bar", chartColors: names.map((n) => (n === "BTC-USD" ? RED : TEAL)), invertedColors: [TEAL], showLegend: false, showTitle: true, title: "Top 10 most-mentioned assets",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "#,##0", valAxisHidden: true, valGridLine: { style: "none" }, valAxisMaxVal: 1150000, ...chartCommon });
}
{
  const s = act("3", "What did price do?", "Page 3 Price and Return, BTC-USD",
    bl(["Look at BTC-USD price, RSI and ATR.", "Open the measures table.", "Tick several assets to rebase price to 100.", "Check future returns and volatility by group."]),
    bl(["Current Return is the log change from the previous close.", "Average future return is near 0, and price rises 50 to 52% of the time."]));
  stat(s, 6.8, 1.5, 2.9, "+23.7%", "BTC-USD, first close 63,491 to last close 78,563.", C.accent1);
  stat(s, 9.9, 1.5, 2.9, "0.58%", "BTC-USD average hourly volatility.", C.accent3);
  s.addChart(pres.charts.BAR, [{ name: "ATR (%)", labels: ["Stocks and ETFs", "Crypto", "Futures"], values: [1.1661, 0.8758, 0.5309] }], {
    x: 6.8, y: 3.5, w: 6.0, h: 3.1, barDir: "col", chartColors: [GOLD], showLegend: false, showTitle: true, title: "Average volatility by group (Normalized ATR %)", showValue: true, dataLabelPosition: "outEnd",
    dataLabelFormatCode: "0.00", valAxisHidden: true, valGridLine: { style: "none" }, valAxisMinVal: 0, ...chartCommon });
}
{
  const s = act("4", "Does mood follow price?", "Page 4 Market and Sentiment, BTC-USD",
    bl(["Price against sentiment.", "Volume Z against sentiment.", "Sentiment level against return.", "Shares and the ranking table, with several assets ticked."]),
    bl(["Sentiment is opinion about news and price, not a forecast.", "Negative sentiment does not mean the price will fall."]));
  const names = ["CL=F", "ES=F", "SPY", "BTC-USD", "KO", "SHIB-USD", "NG=F"], vals = [-0.217, -0.116, -0.0095, 0.0261, 0.1143, 0.1212, 0.1214];
  s.addChart(pres.charts.BAR, [{ name: "Sentiment Score", labels: names, values: vals }], {
    x: 6.8, y: 1.5, w: 6.0, h: 4.0, barDir: "bar", chartColors: vals.map((v) => (v >= 0 ? GREEN : RED)), invertedColors: [RED], showLegend: false, showTitle: true, title: "Average Sentiment Score (assets with 1,000+ texts)",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "+0.000;-0.000", valAxisHidden: true, valGridLine: { style: "none" }, valAxisMinVal: -0.3, valAxisMaxVal: 0.2, catAxisLabelPos: "low", ...chartCommon });
  s.addText("BTC-USD scores +0.026, with 41.0% positive and 33.8% negative texts, from 607,251 texts.", { x: 6.8, y: 5.65, w: 6.0, h: 0.9, fontSize: 16, bold: true, color: C.text2, margin: 0, isTextBox: true, valign: "top" });
}
{
  const s = act("5", "Who moves first?", "Page 6 Lead and Lag, BTC-USD",
    bl(["Read the lag chart.", "Read sentiment after price moves.", "Use the how-to-read note under each chart."]),
    bl(["If sentiment led price, it could work as a signal.", "If it follows, it only chases momentum."]));
  const rho = [0.0232, -0.0032, -0.0084, -0.0101, -0.0131, -0.0029];
  s.addChart(pres.charts.BAR, [{ name: "Spearman rho", labels: ["Current Return", "Future 1h", "2h", "3h", "6h", "12h"], values: rho }], {
    x: 6.8, y: 1.5, w: 6.0, h: 3.9, barDir: "col", chartColors: rho.map((v) => (v >= 0 ? GREEN : RED)), invertedColors: [RED], showLegend: false, showTitle: true,
    title: "BTC-USD, sentiment against return (Spearman rho)", showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "+0.000;-0.000", valAxisHidden: true, valGridLine: { style: "none" }, valAxisMinVal: -0.03, valAxisMaxVal: 0.035, catAxisLabelPos: "low", catAxisLabelFontSize: 12, ...chartCommon });
  s.addText("Only Current Return passes the BH test (p = 0.036). Every future horizon fails, and rho never exceeds 0.023.", { x: 6.8, y: 5.55, w: 6.0, h: 1.1, fontSize: 16, bold: true, color: C.text2, margin: 0, isTextBox: true, valign: "top" });
}
{
  const s = act("6", "How far can we trust it?", "Page 5 Statistical Analysis",
    bl(["Read the summary cards.", "Heatmap, switching value, p-value and method.", "Check AUC, then the six variable groups."]),
    bl(["Test hundreds of cells and some look good by chance.", "An AUC of 0.5 is no better than guessing."]));
  s.addChart(pres.charts.BAR, [{ name: "Average AUC", labels: ["Baseline (random)", "Ticker", "Ticker quality", "Global", "Global quality", "Global spike"], values: [0.5002, 0.5004, 0.4976, 0.5036, 0.503, 0.5048] }], {
    x: 6.8, y: 1.5, w: 6.0, h: 3.7, barDir: "bar", chartColors: [TEAL], showLegend: false, showTitle: true, title: "Average logistic AUC (0.5 is guessing)", showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.000",
    valAxisMinVal: 0.45, valAxisMaxVal: 0.55, valAxisHidden: true, valGridLine: { style: "none" }, catAxisOrientation: "maxMin", ...chartCommon });
  stat(s, 6.8, 5.3, 2.9, "96.6%", "of 147 cells have |rho| below 0.1.", C.accent2, 32);
  stat(s, 9.9, 5.3, 2.9, "0 cells", "pass BH on future returns. Seven pass before adjustment.", C.accent2, 32);
}
{
  const s = act("7", "How do we use it?", "Page 7 Hot Events",
    bl(["Set Z-score 1.5 and sentiment 0.05.", "Read the count table by signal type.", "Pick a BTC-USD row in the latest signals.", "Check win rate after a signal against the 50% line.", "Raise Z to 2.5 and watch the count drop."]),
    bl(["A simple event study. What did price do after an unusual hour?", "A win rate near 50% means watch, not buy."]));
  s.addChart(pres.charts.BAR, [
    { name: "Sentiment ≥ 0.05", labels: ["Z 1.5", "Z 2.0", "Z 2.5"], values: [15060, 11062, 8361] },
    { name: "Sentiment ≥ 0.30", labels: ["Z 1.5", "Z 2.0", "Z 2.5"], values: [2086, 1660, 1315] }], {
    x: 6.8, y: 1.5, w: 6.0, h: 3.7, barDir: "col", chartColors: [GOLD, BLUE], showLegend: true, legendPos: "b", showTitle: true, title: "Combined signals by threshold", showValue: true, dataLabelPosition: "outEnd",
    dataLabelFormatCode: "#,##0", valAxisHidden: true, valGridLine: { style: "none" }, valAxisMaxVal: 18000, ...chartCommon });
  s.addText("BTC-USD at Z 1.5 and sentiment 0.05 has 6,515 positive spikes, 3,868 negative, 1,286 combined and 590 volume spikes.", { x: 6.8, y: 5.4, w: 6.0, h: 1.2, fontSize: 16, bold: true, color: C.text2, margin: 0, isTextBox: true, valign: "top" });
}

// =============================================================== PART 6: EXECUTIVE QUESTIONS
function qslide(title, tag, rows) {
  const s = newSlide("LIGHT", "6 Executive questions");
  head(s, title, "6 Executive questions  ·  " + tag);
  table(s, rows, { x: 0.5, y: 1.5, w: 12.35, colW: [3.9, 5.7, 2.75], fontSize: 15, rowH: 0.8 });
  return s;
}
qslide("Five questions on volume and prices, and what the data says.", "Systems 1 and 2", [
  ["Question", "Answer", "Where"],
  ["Which asset is mentioned most?", "BTC-USD, with 900,891 mentions (4.09%), then TSLA, NVDA and SPY.", "Page 2"],
  ["Is hourly volume rising or falling?", "No clear trend (rho −0.060, p 0.111). It averages 1,311 an hour and peaked in Apr 2025.", "Page 1"],
  ["What do price and trading volume look like?", "BTC-USD went from 63,491 to 78,563, up 23.7%.", "Page 3"],
  ["How do future returns differ by group?", "Averages are near 0 and price rises 49.9 to 52.5% of the time. Stocks and ETFs have little data at 6 hours and none at 12.", "Page 3"],
  ["Which group is most volatile?", "Stocks and ETFs at 1.17%, then crypto at 0.88%, then futures at 0.53%.", "Page 3"]]);
qslide("Four questions on sentiment.", "System 3", [
  ["Question", "Answer", "Where"],
  ["Is overall sentiment positive or negative?", "Balanced, leaning slightly negative. 32.4% positive, 32.9% neutral, 34.7% negative.", "Page 4"],
  ["Which assets are most positive or negative?", "Most positive are NG=F, SHIB-USD and KO. Most negative are CL=F, ES=F and NQ=F.", "Page 4 ranking"],
  ["How well do VADER and FinBERT agree?", "They agree on direction 50.2% of the time. The merge rule and keywords settle the rest.", "Slide 10"],
  ["What are the hourly positive, negative and neutral shares?", "See the share chart over time. It can switch from hourly to yearly.", "Page 4"]]);
qslide("Four questions on relationships.", "System 4", [
  ["Question", "Answer", "Where"],
  ["How does sentiment relate to future price direction?", "It does not. 96.6% of 147 cells have |rho| below 0.1, none pass BH, win rate is 43.1 to 55.1% and AUC is 0.488 to 0.510.", "Page 5"],
  ["Does the pattern differ by asset group?", "Not meaningfully. AUC is 0.489 to 0.506 in every group.", "Page 5"],
  ["Is earlier sentiment better than current?", "No. Lag 1h is stronger in only 15 of 40 cells, and the largest |rho| is 0.023.", "Pages 5 and 6"],
  ["Which factor deserves the most weight?", "Lag, direction, level, vote, volume, then momentum. But AUC is about 0.5, so do not read it as a signal.", "Page 5"]]);
qslide("Four questions on investment analysis.", "System 5", [
  ["Question", "Answer", "Where"],
  ["Which assets have unusually high sentiment or volume Z-score?", "Across Reddit, 1,968 hours have Z above 1.5. Per-asset values follow the filters.", "Pages 1, 2 and 4"],
  ["Which assets show an interesting win rate, by horizon?", "Win rate is 43.1 to 55.1% and 2 cells pass BH. Current Return is positive for 28 of 34 assets.", "Page 5"],
  ["How do the thresholds change the number of conditions found?", "Stricter means fewer. Combined signals fall from 15,060 to 8,361 (Z 1.5 to 2.5), and to 2,086 (sentiment 0.05 to 0.30).", "Page 7"],
  ["Does majority sentiment agree with the future return direction?", "No visible link. Price is up after 50.7% of positive hours and 50.4% of negative hours (1 hour).", "Page 4"]]);
qslide("Four questions on signal detection.", "System 6", [
  ["Question", "Answer", "Where"],
  ["Which assets meet the signal conditions?", "All 34 do. ETH-USD has the most (1,358), then BTC-USD (1,286) and XRP-USD (1,030).", "Page 7"],
  ["Which types of signal were found?", "Positive spike 28,398, negative spike 18,426, volume spike 16,234 and combined 15,060.", "Page 7"],
  ["What do past statistics say for flagged assets?", "The average win rate is 49.9%, close to guessing. The chart shows the live value.", "Page 7"],
  ["How do thresholds change the number and type of signals?", "Stricter thresholds give fewer signals. Combined falls from 15,060 to 8,361 at Z 2.5.", "Page 7"]]);
{
  const s = newSlide("DARK", "6 Executive questions");
  head(s, "Reddit sentiment describes the market now, not where it goes next.", "6 Executive questions", true);
  const cols = [["It can tell you", "7FE0B0", ["What the market is unusually busy talking about.", "Which assets hold attention.", "Mood that moves with the latest price."]],
    ["It cannot tell you", "FF9A92", ["Where price goes next.", "A timing rule that makes money.", "Why price moved."]],
    ["Use it as", "FFD98A", ["A watch tool for attention and mood.", "A starting point for deeper checks."]]];
  cols.forEach((c, i) => {
    const x = 0.6 + i * 4.1;
    s.addText(c[0], { x, y: 1.9, w: 3.7, h: 0.6, fontSize: 24, bold: true, color: c[1], margin: 0, isTextBox: true });
    s.addText(c[2].map((t, k) => ({ text: t, options: { bullet: true, breakLine: k < c[2].length - 1 } })), { x, y: 2.7, w: 3.7, h: 3.0, fontSize: 18, color: C.background1, margin: 0, isTextBox: true, valign: "top", paraSpaceAfter: 10 });
  });
  s.addText("Analysts now have one place for sentiment and prices, and it shows the sentiment does not predict the next move.", { x: 0.6, y: 6.0, w: 12.1, h: 0.8, fontSize: 18, color: "CADCFC", margin: 0, isTextBox: true });
}

// =============================================================== PART 7: QA
{
  const s = newSlide("LIGHT", "7 QA");
  head(s, "The system passed all three groups of tests.", "7 QA");
  stat(s, 0.6, 1.7, 2.9, "32 / 32", "real-data checks on logic and table links.", C.accent1, 40);
  stat(s, 3.7, 1.7, 2.9, "371 / 371", "dashboard numbers match independent SQL.", C.accent1, 40);
  stat(s, 6.8, 1.7, 2.9, "81 / 81", "required measures and KPIs found.", C.accent1, 40);
  stat(s, 9.9, 1.7, 2.9, "237", "unit tests passing, run on 7 Nov 2026.", C.accent1, 40);
  card(s, 0.6, 4.0, 3.8, 2.6, "Unit and logic", bl(["Scores stay between −1 and +1.", "Labels match the ±0.05 band.", "Returns recomputed from prices match."]), { size: 14, headSize: 17 });
  card(s, 4.8, 4.0, 3.8, 2.6, "Integration", bl(["No duplicate keys in fact tables.", "Every key exists in its dimension.", "Hourly totals match the filtered text count."]), { size: 14, headSize: 17, headColor: C.accent4 });
  card(s, 9.0, 4.0, 3.6, 2.6, "Dashboard", bl(["Every page checked against direct SQL.", "Every required measure appears on screen."]), { size: 14, headSize: 17, headColor: C.accent3 });
}
{
  const s = newSlide("LIGHT", "7 QA");
  head(s, "Questions you may get, part one.", "7 QA");
  card(s, 0.6, 1.7, 5.9, 2.4, "If it cannot predict, what is it for?", ["It is a watch tool for attention and mood. A verified \"no signal\" also stops you chasing signals that are not there."], { size: 15, headSize: 18 });
  card(s, 6.8, 1.7, 5.8, 2.4, "Why adjust p-values with BH?", ["With 147 cells, about 7 pass by chance, and 7 did before adjustment. After it, none do."], { size: 15, headSize: 18, headColor: C.accent4 });
  card(s, 0.6, 4.4, 5.9, 2.3, "Is Reddit a proxy for the market?", ["Not fully. wallstreetbets is 73.2% of the texts, so the picture is mostly that crowd's mood."], { size: 15, headSize: 18, headColor: C.accent3 });
  card(s, 6.8, 4.4, 5.8, 2.3, "Does autocorrelation matter?", ["Yes. Hourly data runs in sequence and horizons overlap, so p-values support the reading but do not decide it. Effect size is always shown."], { size: 15, headSize: 18, headColor: C.accent2 });
}
{
  const s = newSlide("LIGHT", "7 QA");
  head(s, "Questions you may get, part two.", "7 QA");
  card(s, 0.6, 1.7, 5.9, 2.4, "Is 47% accuracy low?", ["Low as an exam score, but labels follow the commenter's stance. 163 of 400 are neutral and there is one labeller."], { size: 15, headSize: 18 });
  card(s, 6.8, 1.7, 5.8, 2.4, "Do other thresholds change the results?", ["A ±0.10 neutral band lifts FinBERT from 47.9 to 50.3% but drops the merge rule from 47.1 to 45.2%. Stricter signal thresholds did not beat random either."], { size: 15, headSize: 18, headColor: C.accent4 });
  card(s, 0.6, 4.4, 5.9, 2.3, "Can you trade on it?", ["I would not. Results do not beat guessing, and fees and slippage are not included."], { size: 15, headSize: 18, headColor: C.accent3 });
  card(s, 6.8, 4.4, 5.8, 2.3, "Why historical data, not real-time?", ["The scope is historical Reddit data with hourly prices. Real-time is out of scope."], { size: 15, headSize: 18, headColor: C.accent2 });
}
{
  const s = newSlide("DARK", "7 QA");
  s.addText("Q&A", { x: 0.8, y: 2.3, w: 11.7, h: 1.6, fontSize: 80, bold: true, color: C.background1, margin: 0, isTextBox: true });
  s.addText("Thank you. Happy to open any page.", { x: 0.8, y: 4.1, w: 11.7, h: 0.7, fontSize: 24, color: "CADCFC", margin: 0, isTextBox: true });
}

(async () => {
  if (SLIDE_IDX !== NOTES.length) console.warn("slide count " + SLIDE_IDX + " differs from notes " + NOTES.length);
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("written", OUT);
})();
