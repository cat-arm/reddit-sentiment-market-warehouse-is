"""Does the warehouse and the dashboard answer the proposal?  (TASKS Q-stage, checklist before closing the thesis)

Reads the proposal PDF (the source of truth) and lists, for every measure table (3, 7, 14), every data-variable table
(11, 13, 18) and every KPI table (4, 8, 15):
  * measures / variables: is there a column of that name in the database (and how much of it is filled)?
  * KPIs: which dashboard page shows it (searched in the page source)?
Writes a Markdown report; read-only on the database.

Run:  python scripts/check_proposal_coverage.py [--db output/reddit.sqlite3] [--out output/reports/proposal_coverage.md]
"""

import argparse
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from etl.common import DEFAULT_DB, connect  # noqa: E402

PROPOSAL = ROOT / "data" / "Wait_for_approve_Proposal_6782094726_Rithipong_Leanghirunkun_rev1.pdf"
DEFAULT_OUT = ROOT / "output" / "reports" / "proposal_coverage.md"

# proposal table number -> (title, kind, database tables that should hold the columns)
TABLES = {
    3: ("ค่าวัด 7.1 (FactRedditVolume)", "measure", ["FactRedditVolume"]),
    7: ("ค่าวัด 7.2 (FactMarketPrice)", "measure", ["FactMarketPrice"]),
    14: ("ค่าวัด 7.5 (FactMarketSentiment)", "measure", ["FactMarketSentiment"]),
    11: ("ตัวแปร 7.3 ระบบวิเคราะห์ความรู้สึก", "variable", ["sentiment_item", "processed_text"]),
    13: ("ตัวแปร 7.4 ระบบวิเคราะห์ความสัมพันธ์", "variable", ["merged_hourly_panel"]),
    18: ("ตัวแปร 7.6 ระบบตรวจจับสัญญาณ (ตาราง 18)", "variable", ["v_signal_list"]),
}
# proposal name -> names it has in the database (names the proposal writes in another case or style)
ALIASES = {"timestamp": ["timestamp", "hour_utc"], "datetime": ["created_utc"], "Ticker": ["ticker"],
           "Big_Group": ["big_group"], "Reddit_volume": ["reddit_volume"], "Reddit_volume_zscore": ["reddit_volume_zscore"]}

# KPI tables 4, 8, 15: (table, KPI, labels searched in the dashboard code, where the formula is computed)
KPIS = [
    (4, "Reddit Volume Z-score", ["Reddit Volume Z-score"], "reddit_hourly_features.reddit_volume_zscore_24"),
    (4, "Ticker Mention Rate (%)", ["Ticker Mention Rate"], "คำนวณตอนแสดง = mention_count ÷ Reddit_volume × 100"),
    (8, "Current Return (%)", ["Current Return"], "market_hourly_features.log_return (คอลัมน์ในฐานข้อมูลยังชื่อ log_return)"),
    (8, "Volume Z-score (ตลาด)", ["volume_zscore_24"], "market_hourly_features.volume_zscore_24"),
    (8, "Normalized ATR (%)", ["Normalized ATR", "normalized_atr"], "market_hourly_features.normalized_atr"),
    (15, "Sentiment Score", ["Sentiment Score"], "reddit_hourly.sentiment_mean"),
    (15, "Sentiment Momentum", ["Sentiment Momentum"], "reddit_hourly_features.sentiment_momentum_1h"),
    (15, "Reddit Volume Z-score", ["Reddit Volume Z-score"], "reddit_hourly_features.reddit_volume_zscore_24"),
    (15, "Historical Win Rate (%)", ["Historical Win Rate", "Win Rate"], "analysis_results / FactMarketSentiment.winrate_*"),
]


def body_of(text, number, end_marker):
    """Text of the proposal table `number` (its LAST mention = the body, the first is the list of tables)."""
    starts = [m.start() for m in re.finditer(r"ตารางที่ %d:" % number, text)]
    if not starts:
        return ""
    chunk = text[starts[-1]:]
    cut = chunk.find(end_marker)
    return chunk[:cut] if cut > 0 else chunk[:6000]


def proposal_text():
    import pypdf
    reader = pypdf.PdfReader(str(PROPOSAL))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def names_in(body, kind):
    if kind == "measure":                  # "3 future_return_1h Future Return 1h (%) ..."
        found = re.findall(r"^\d+\s+([A-Za-z][A-Za-z0-9_]*)\s", body, re.M)
    else:                                  # "sentiment_mean ทศนิยม (Float) ..."
        found = re.findall(r"^([A-Za-z][A-Za-z0-9_]*)\s+(?:วันเวลา|ข้อความ|ทศนิยม|จำนวนเต็ม)", body, re.M)
    seen = []
    for name in found:
        if name not in seen:
            seen.append(name)
    return seen


def columns(db, table):
    return [row[1] for row in db.execute("PRAGMA table_info(%s)" % table)]


def fill(db, table, column):
    """(non-null rows, all rows) of one column; the big tables take a few seconds."""
    return db.execute('SELECT COUNT("%s"), COUNT(*) FROM %s' % (column, table)).fetchone()


def check_table(db, number, spec, text):
    title, kind, db_tables = spec
    end = "7. ตัวชี้วัด" if kind == "measure" else "ขั้นตอนที่ 2"
    names = names_in(body_of(text, number, end), kind)
    lines = ["### ตารางที่ %d: %s" % (number, title), "",
             "ฐานข้อมูล: %s" % ", ".join("`%s`" % t for t in db_tables), "",
             "| ตัวแปร/ค่าวัดใน proposal | พบในตาราง | แถวที่มีค่า | หมายเหตุ |", "|---|---|---|---|"]
    missing = []
    for name in names:
        candidates = ALIASES.get(name, [name])
        hit = None
        for table in db_tables:
            cols = {c.lower(): c for c in columns(db, table)}
            for cand in candidates:
                if cand.lower() in cols:
                    hit = (table, cols[cand.lower()])
                    break
            if hit:
                break
        if not hit:
            missing.append(name)
            lines.append("| %s | **ไม่พบ** | | |" % name)
            continue
        table, column = hit
        non_null, total = fill(db, table, column) if table.startswith("Fact") or table.endswith("sentiment_item") else (None, None)
        share = "" if not total else "{:,} / {:,} ({:.1%})".format(non_null, total, non_null / total)
        note = "" if column == name else "ชื่อในฐานข้อมูล: `%s`" % column
        lines.append("| %s | `%s` | %s | %s |" % (name, table, share, note))
    return lines, names, missing


def dashboard_source():
    files = sorted((ROOT / "dashboard").rglob("*.py"))
    return {str(f.relative_to(ROOT)).replace("\\", "/"): f.read_text(encoding="utf-8") for f in files}


def kpi_section(sources):
    lines = ["### KPI (ตารางที่ 4, 8, 15) กับหน้า dashboard", "",
             "| ตาราง | KPI | หน้าที่แสดง | คำนวณที่ |", "|---|---|---|---|"]
    gaps = []
    for number, kpi, labels, where in KPIS:
        pages = [name.replace("dashboard/pages/", "").replace("dashboard/", "") for name, src in sources.items()
                 if name != "dashboard/data.py" and name != "dashboard/common.py" and any(l in src for l in labels)]
        if not pages:
            gaps.append(kpi)
        lines.append("| %d | %s | %s | %s |" % (number, kpi, ", ".join(pages) if pages else "**ยังไม่แสดง**", where))
    return lines, gaps


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    text = proposal_text()
    db = connect(args.db, readonly=True)
    report = ["# Proposal coverage: ฐานข้อมูลและ dashboard ตอบ proposal ครบหรือไม่", "",
              "สร้างจาก `scripts/check_proposal_coverage.py` (อ่าน proposal rev1 + ฐานข้อมูลแบบอ่านอย่างเดียว)", ""]
    problems = []
    for number, spec in TABLES.items():
        block, names, missing = check_table(db, number, spec, text)
        report += block + ["", "ครบ %d / %d" % (len(names) - len(missing), len(names)), ""]
        problems += ["ตาราง %d: %s" % (number, m) for m in missing]
        if not names:
            problems.append("ตาราง %d: อ่านรายชื่อจาก proposal ไม่ได้" % number)
    block, gaps = kpi_section(dashboard_source())
    report += block + [""]
    problems += ["KPI ไม่แสดง: %s" % g for g in gaps]
    report += ["## สรุป", "", "ไม่พบช่องโหว่" if not problems else "\n".join("- " + p for p in problems)]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    print("\nเขียนรายงานที่ %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
