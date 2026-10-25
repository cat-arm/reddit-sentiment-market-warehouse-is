"""System tests of the real database (proposal 8.4): data logic checks and data integration checks.

Each check counts the rows that break a rule, so the target is 0 violations.  The Streamlit dashboard tests
(8.4 third part) live in tests/test_dashboard_smoke.py and the rule-validation labelling (7.3 step 5) in
scripts/rule_validation.py; this script covers what those do not: the numbers inside the finished tables.
Read-only.

Usage:  python scripts/system_tests.py [--db output/reddit.sqlite3]
Output: output/reports/system_tests.md
"""
import argparse
import math
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from etl.common import DEFAULT_DB, NEUTRAL_BAND, connect, file_header  # noqa: E402
from etl.ticker_dict import load_tickers  # noqa: E402

OUT = ROOT / "output" / "reports" / "system_tests.md"
HORIZONS = (1, 2, 3, 6, 12)
TOLERANCE = 1e-6                      # percent points; stored prices are float32-like, returns are float64


def one(db, sql):
    return db.execute(sql).fetchone()[0]


def sql_checks(db):
    """(part, name, rows checked, violations) from plain SQL."""
    out = []
    n_text = one(db, "SELECT COUNT(*) FROM filtered_text")
    out.append(("ตรรกะ", "ข้อความที่ล้างแล้ว (final_text) ไม่เป็นค่าว่าง", n_text,
                one(db, "SELECT COUNT(*) FROM filtered_text WHERE final_text IS NULL OR TRIM(final_text) = ''")))
    n_item = one(db, "SELECT COUNT(*) FROM sentiment_item")
    for col in ("vader_score", "finbert_score", "final_sentiment"):
        out.append(("ตรรกะ", "%s อยู่ในช่วง -1 ถึง +1 (ไม่เป็น NULL)" % col, n_item,
                    one(db, "SELECT COUNT(*) FROM sentiment_item WHERE %s IS NULL OR %s < -1 OR %s > 1" % (col, col, col))))
    band = NEUTRAL_BAND
    for status, score in (("vader_status", "vader_score"), ("finbert_status", "finbert_score"), ("final_status", "final_sentiment")):
        out.append(("ตรรกะ", "%s ตรงกับ %s ตามเกณฑ์ ±%.2f" % (status, score, band), n_item, one(
            db, "SELECT COUNT(*) FROM sentiment_item WHERE %s != CASE WHEN %s >= %r THEN 'positive' "
                "WHEN %s <= %r THEN 'negative' ELSE 'neutral' END" % (status, score, band, score, -band))))
    out.append(("ตรรกะ", "is_ambiguous เป็น 0/1 และ final = 0.0 ทุกแถวที่ ambiguous", n_item, one(
        db, "SELECT COUNT(*) FROM sentiment_item WHERE is_ambiguous NOT IN (0, 1) OR (is_ambiguous = 1 AND final_sentiment != 0)")))
    symbols = set(load_tickers()["tickers"])
    marks = ",".join("?" * len(symbols))
    out.append(("ตรรกะ", "ticker ที่สกัดได้อยู่ใน 34 สินทรัพย์เป้าหมายเท่านั้น", one(db, "SELECT COUNT(*) FROM ticker_mentions"),
                db.execute("SELECT COUNT(*) FROM ticker_mentions WHERE ticker NOT IN (%s)" % marks, sorted(symbols)).fetchone()[0]))
    out.append(("ตรรกะ", "จำนวน ticker เป้าหมายใน DimTicker = 34", 1, int(one(db, "SELECT COUNT(*) FROM DimTicker") != 34)))
    # integration
    out.append(("เชื่อมโยง", "ทุกข้อความที่ผ่านตัวกรองมีคะแนนความรู้สึกครบ (filtered_text ↔ sentiment_item)", n_text, one(
        db, "SELECT COUNT(*) FROM filtered_text t LEFT JOIN sentiment_item s ON s.src_rowid = t.src_rowid WHERE s.src_rowid IS NULL")))
    out.append(("เชื่อมโยง", "ไม่มีคะแนนความรู้สึกที่ไม่มีข้อความรองรับ", n_item, one(
        db, "SELECT COUNT(*) FROM sentiment_item s LEFT JOIN filtered_text t ON t.src_rowid = s.src_rowid WHERE t.src_rowid IS NULL")))
    out.append(("เชื่อมโยง", "ผลรวมข้อความรายชั่วโมง (reddit_volume_hourly) = จำนวนข้อความที่ผ่านตัวกรอง", 1,
                int(one(db, "SELECT SUM(texts) FROM reddit_volume_hourly") != n_text)))
    out.append(("เชื่อมโยง", "ผลรวม ticker_mention_count ใน FactRedditVolume = ผลรวม mention_count ใน ticker_mentions", 1, int(
        one(db, "SELECT SUM(ticker_mention_count) FROM FactRedditVolume") != one(db, "SELECT SUM(mention_count) FROM ticker_mentions"))))
    for fact, keys in (("FactMarketPrice", ("TimeID", "TickerID")), ("FactMarketSentiment", ("TimeID", "TickerID", "SentimentSourceID")),
                       ("FactRedditVolume", ("TimeID", "TickerID", "SourceID"))):
        total = one(db, "SELECT COUNT(*) FROM %s" % fact)
        dups = one(db, "SELECT COUNT(*) FROM (SELECT 1 FROM %s GROUP BY %s HAVING COUNT(*) > 1)" % (fact, ", ".join(keys)))
        out.append(("เชื่อมโยง", "%s ไม่มีแถวซ้ำใน key (%s)" % (fact, ", ".join(keys)), total, dups))
        out.append(("เชื่อมโยง", "%s: TimeID ทุกแถวมีใน DimTime" % fact, total, one(
            db, "SELECT COUNT(*) FROM %s f LEFT JOIN DimTime d ON d.TimeID = f.TimeID WHERE d.TimeID IS NULL" % fact)))
        out.append(("เชื่อมโยง", "%s: TickerID ทุกแถวมีใน DimTicker" % fact, total, one(
            db, "SELECT COUNT(*) FROM %s f LEFT JOIN DimTicker d ON d.TickerID = f.TickerID WHERE d.TickerID IS NULL" % fact)))
    out.append(("เชื่อมโยง", "ราคา close ใน FactMarketSentiment = FactMarketPrice (key เดียวกัน)", one(db, "SELECT COUNT(*) FROM FactMarketSentiment"),
                one(db, "SELECT COUNT(*) FROM FactMarketSentiment s JOIN FactMarketPrice p ON p.TimeID = s.TimeID AND p.TickerID = s.TickerID "
                        "WHERE ABS(s.close - p.close) > 1e-9")))
    out.append(("เชื่อมโยง", "จำนวนแถว FactMarketPrice = market_hourly_features (ชั่วโมงเริ่มบาร์ join DimTime ได้ครบ)",
                1, int(one(db, "SELECT COUNT(*) FROM FactMarketPrice") != one(db, "SELECT COUNT(*) FROM market_hourly_features"))))
    out.append(("เชื่อมโยง", "ไม่มีแถวราคาที่ close เป็น NULL ใน market_hourly_features", one(db, "SELECT COUNT(*) FROM market_hourly_features"),
                one(db, "SELECT COUNT(*) FROM market_hourly_features WHERE close IS NULL")))
    return out


def _epoch(text):
    return int(datetime.fromisoformat(text).timestamp())


def return_checks(db):
    """Recompute log_return and future_return_nh from close prices; compare with the stored columns."""
    rows = db.execute("SELECT ticker, bar_ts, close, log_return, future_return_1h, future_return_2h, future_return_3h, "
                      "future_return_6h, future_return_12h FROM market_hourly_features").fetchall()
    by_ticker = {}
    for row in rows:
        by_ticker.setdefault(row[0], {})[_epoch(row[1])] = row
    bad = {"log": 0}
    bad.update({h: 0 for h in HORIZONS})
    checked = {"log": 0}
    checked.update({h: 0 for h in HORIZONS})
    for bars in by_ticker.values():
        for ts, row in bars.items():
            close = row[2]
            prev = bars.get(ts - 3600)
            expected = math.log(close / prev[2]) * 100 if prev and prev[2] and close > 0 else None
            checked["log"] += 1
            bad["log"] += _differs(row[3], expected)
            for i, h in enumerate(HORIZONS):
                later = bars.get(ts + h * 3600)
                expected = (later[2] - close) / close * 100 if later else None
                checked[h] += 1
                bad[h] += _differs(row[4 + i], expected)
    out = [("ตรรกะ", "Current Return (log_return) = ln(close_t / close_t-1) × 100 คำนวณซ้ำจากราคา", checked["log"], bad["log"])]
    for h in HORIZONS:
        out.append(("ตรรกะ", "future_return_%dh = (close_t+%dh − close_t) / close_t × 100 (%%) คำนวณซ้ำจากราคา" % (h, h), checked[h], bad[h]))
    return out


def _differs(stored, expected):
    if stored is None or expected is None:
        return int(stored is not expected)
    return int(abs(stored - expected) > TOLERANCE)


def completeness(db):
    """Share of price rows that have a future return, per asset class and horizon (not a pass/fail check)."""
    lines = ["| กลุ่มสินทรัพย์ | แถวราคา | " + " | ".join("%dh" % h for h in HORIZONS) + " |", "|---|---|" + "---|" * len(HORIZONS)]
    for cls, in db.execute("SELECT DISTINCT AssetClass FROM DimTicker ORDER BY 1").fetchall():
        sums = ", ".join("SUM(p.future_return_%dh IS NOT NULL)" % h for h in HORIZONS)
        n, *have = db.execute("SELECT COUNT(*), %s FROM FactMarketPrice p JOIN DimTicker d ON d.TickerID = p.TickerID "
                              "WHERE d.AssetClass = ?" % sums, (cls,)).fetchone()
        lines.append("| %s | %d | %s |" % (cls, n, " | ".join("%.1f%%" % (100.0 * x / n) for x in have)))
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    db = connect(args.db, readonly=True)
    try:
        checks = sql_checks(db) + return_checks(db)
        table = completeness(db)
    finally:
        db.close()
    failed = [c for c in checks if c[3]]
    lines = ["# ผลทดสอบระบบกับข้อมูลจริง (proposal 8.4)", "",
             *file_header("ตรวจตัวเลขในตารางผลลัพธ์จริงด้วยกฎของ proposal ข้อ 8.4 (ส่วนตรรกะข้อมูลและส่วนการเชื่อมโยงข้อมูล) "
                          "แต่ละข้อนับจำนวนแถวที่ผิดกฎ เป้าหมายคือ 0",
                          "scripts/system_tests.py", "python scripts/system_tests.py", "output/reddit.sqlite3 อ่านอย่างเดียว"), "",
             "ผ่าน %d จาก %d ข้อ" % (len(checks) - len(failed), len(checks)), "",
             "| ส่วน | ข้อตรวจ | แถวที่ตรวจ | แถวที่ผิดกฎ | ผล |", "|---|---|---|---|---|"]
    for part, name, n, bad in checks:
        lines.append("| %s | %s | %d | %d | %s |" % (part, name, n, bad, "ผ่าน" if not bad else "**ไม่ผ่าน**"))
    lines += ["", "## ความครบถ้วนของ future return แยกตามกรอบเวลา (สัดส่วนแถวที่คำนวณได้)", "", *table, "",
              "ค่าว่างไม่ใช่ข้อผิดพลาด: หุ้นและกองทุนดัชนีปิดตลาดข้ามคืน จึงไม่มีราคาที่ตรงกับเวลา +6/+12 ชั่วโมงเสมอ (proposal ข้อ 3.4 และ 4.2)"]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
