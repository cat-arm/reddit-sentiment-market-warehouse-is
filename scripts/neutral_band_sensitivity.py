"""S5 (proposal 7.3 step 5): how sensitive is the sentiment split to the neutral band, 0.05 vs 0.10?

Re-applies the conflict-resolution rules of etl.resolve_sentiment to the STORED VADER / FinBERT scores and keyword
signals of every text, once per band, and compares the share of positive / negative / neutral (VADER, FinBERT and
the final sentiment), the share of each final_method, the share of is_ambiguous, and how many texts change final
status between the two bands.  Read-only: nothing is written to the database.

Usage:
    python scripts/neutral_band_sensitivity.py [--db output/reddit.sqlite3] [--bands 0.05 0.10] [--limit N]
Output: output/reports/neutral_band_sensitivity.md and .csv
"""
import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from etl.common import DEFAULT_DB, connect, file_header, status_of                       # noqa: E402
from etl.resolve_sentiment import is_ambiguous, resolve, same_direction_max_gap  # noqa: E402

OUT_DIR = ROOT / "output" / "reports"
STATUSES = ("positive", "neutral", "negative")


def tally(rows, bands, max_gap):
    """One pass over (vader, finbert, rule) rows -> per-band Counters + changed-status counts vs the first band."""
    counts = {b: {"vader": Counter(), "finbert": Counter(), "final": Counter(),
                  "method": Counter(), "ambiguous": Counter()} for b in bands}
    changed, total = Counter(), 0
    for vader, finbert, rule in rows:
        total += 1
        finals = []
        for band in bands:
            score, method = resolve(vader, finbert, rule, max_gap, band)
            final = status_of(score, band)
            finals.append(final)
            c = counts[band]
            c["vader"][status_of(vader, band)] += 1
            c["finbert"][status_of(finbert, band)] += 1
            c["final"][final] += 1
            c["method"][method] += 1
            c["ambiguous"][is_ambiguous(method)] += 1
        for other in range(1, len(bands)):
            if finals[other] != finals[0]:
                changed[(finals[0], finals[other])] += 1
    return counts, changed, total


def report_lines(bands, counts, changed, total):
    def pct(n):
        return "%.2f%%" % (100.0 * n / total)

    lines = ["# Neutral-band sensitivity (proposal 7.3 step 5)", "",
             *file_header("ผลทดสอบความไวของเกณฑ์ neutral: สัดส่วน positive/negative/neutral เมื่อใช้เกณฑ์ " +
                          " เทียบ ".join("±%.2f" % b for b in bands) + " (proposal 7.3 ขั้นตอนที่ 5)",
                          "scripts/neutral_band_sensitivity.py", "python steps/25_neutral_band_sensitivity.py",
                          "ตาราง sentiment_item (%d ข้อความ) ใน output/reddit.sqlite3 อ่านอย่างเดียว" % total), "",
             "## สัดส่วนประเภทความรู้สึก", "",
             "| แบบจำลอง | ประเภท | " + " | ".join("band ±%.2f" % b for b in bands) + " |",
             "|---|---|" + "---|" * len(bands)]
    for model in ("vader", "finbert", "final"):
        for status in STATUSES:
            lines.append("| %s | %s | %s |" % (model, status, " | ".join(pct(counts[b][model][status]) for b in bands)))
    lines += ["", "## final_method", "", "| final_method | " + " | ".join("band ±%.2f" % b for b in bands) + " |",
              "|---|" + "---|" * len(bands)]
    methods = sorted({m for b in bands for m in counts[b]["method"]})
    for method in methods:
        lines.append("| %s | %s |" % (method, " | ".join(pct(counts[b]["method"][method]) for b in bands)))
    lines += ["", "## is_ambiguous = 1", "",
              " | ".join("band ±%.2f: %s" % (b, pct(counts[b]["ambiguous"][1])) for b in bands), ""]
    moved = sum(changed.values())
    lines += ["## ข้อความที่ final_status เปลี่ยนเมื่อเทียบ band ±%.2f กับ ±%.2f" % (bands[0], bands[-1]), "",
              "รวม %d ข้อความ (%s)" % (moved, pct(moved)), "", "| จาก | เป็น | จำนวน |", "|---|---|---|"]
    for (a, b), n in sorted(changed.items(), key=lambda kv: -kv[1]):
        lines.append("| %s | %s | %d |" % (a, b, n))
    return lines


def csv_rows(bands, counts):
    for band in bands:
        for model in ("vader", "finbert", "final"):
            for status in STATUSES:
                yield (band, model, status, counts[band][model][status])
        for method, n in sorted(counts[band]["method"].items()):
            yield (band, "final_method", method, n)
        yield (band, "is_ambiguous", "1", counts[band]["ambiguous"][1])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--bands", type=float, nargs="+", default=[0.05, 0.10])
    parser.add_argument("--limit", type=int, help="only the first N rows (trial)")
    parser.add_argument("--out-dir", default=str(OUT_DIR))
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")        # the report is Thai; the Windows console default is cp1252
    sql = "SELECT vader_score, finbert_score, rule_signal FROM sentiment_item"
    if args.limit:
        sql += " LIMIT %d" % args.limit
    db = connect(args.db, readonly=True)
    try:
        counts, changed, total = tally(db.execute(sql), args.bands, same_direction_max_gap())
    finally:
        db.close()
    lines = report_lines(args.bands, counts, changed, total)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "neutral_band_sensitivity.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (out / "neutral_band_sensitivity.csv").open("w", newline="", encoding="utf-8") as sink:
        sink.write("\n".join(file_header(
            "จำนวนข้อความต่อประเภทความรู้สึกที่เกณฑ์ neutral แต่ละค่า (ข้อมูลชุดเดียวกับ neutral_band_sensitivity.md)",
            "scripts/neutral_band_sensitivity.py", "python steps/25_neutral_band_sensitivity.py",
            "ตาราง sentiment_item ใน output/reddit.sqlite3", comment=True)) + "\n")
        writer = csv.writer(sink)
        writer.writerow(("band", "group", "label", "n"))
        writer.writerows(csv_rows(args.bands, counts))
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
