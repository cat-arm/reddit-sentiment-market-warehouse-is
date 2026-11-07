"""Numbers for two management questions of the proposal that no other report covers (read-only).

  * System 7.5, question 4: does the majority sentiment of an hour agree with the direction of the future return?
  * System 7.6, question 1: which assets meet the signal conditions most often (Z 1.5, sentiment 0.05)?

Usage:  python scripts/exec_answers_sys5_sys6.py [--db output/reddit.sqlite3]
Output: output/reports/exec_answers_sys5_sys6.md
"""
import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd                                    # noqa: E402

from etl.common import DEFAULT_DB, file_header         # noqa: E402

OUT = ROOT / "output" / "reports" / "exec_answers_sys5_sys6.md"
HORIZONS = (1, 2, 3, 6, 12)


def md(frame):
    cols = list(frame.columns)
    rows = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, row in frame.iterrows():
        rows.append("| " + " | ".join(str(v) for v in row) + " |")
    return "\n".join(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args()
    con = sqlite3.connect("file:%s?mode=ro" % Path(args.db).as_posix(), uri=True)

    cols = ", ".join("future_return_%dh" % h for h in HORIZONS)
    panel = pd.read_sql_query(
        "SELECT majority_final_status AS majority, %s FROM merged_hourly_panel "
        "WHERE scope = 'ticker' AND variant = 'all' AND majority_final_status IS NOT NULL" % cols, con)
    rows = []
    for status in ("positive", "neutral", "negative"):
        part = panel[panel.majority == status]
        row = {"majority sentiment": status, "hours": "{:,}".format(len(part))}
        for h in HORIZONS:
            r = part["future_return_%dh" % h].dropna()
            row["up %dh (%%)" % h] = "%.1f" % ((r > 0).mean() * 100) if len(r) else "n/a"
        rows.append(row)
    table_a = pd.DataFrame(rows)

    top = pd.read_sql_query(
        "SELECT ticker, COUNT(*) AS combined_signals FROM signal_events "
        "WHERE z_threshold = 1.5 AND s_threshold = 0.05 AND signal_type = 'combined_signal' "
        "GROUP BY ticker ORDER BY combined_signals DESC LIMIT 10", con)
    tickers = pd.read_sql_query(
        "SELECT COUNT(DISTINCT ticker) AS n FROM signal_events "
        "WHERE z_threshold = 1.5 AND s_threshold = 0.05 AND signal_type = 'combined_signal'", con).n[0]

    head = file_header("ตัวเลขตอบคำถามผู้บริหาร 2 ข้อของ proposal: ประเภทความรู้สึกส่วนใหญ่เทียบกับทิศทางผลตอบแทนล่วงหน้า (7.5 ข้อ 4) "
                       "และสินทรัพย์ที่เข้าเงื่อนไขสัญญาณ (7.6 ข้อ 1)", "scripts/exec_answers_sys5_sys6.py",
                       "python scripts/exec_answers_sys5_sys6.py", "output/reddit.sqlite3 อ่านอย่างเดียว")
    body = ["## System 7.5, question 4: majority sentiment vs share of hours where the future return is positive",
            "(ticker scope, all texts; hours without a price at that horizon are skipped)", "", md(table_a), "",
            "## System 7.6, question 1: assets with the most combined signals (Z 1.5, sentiment 0.05)",
            "%d assets have at least one combined signal." % tickers, "", md(top), ""]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(head) + "\n\n" + "\n".join(body), encoding="utf-8")
    print("\n".join(body))


if __name__ == "__main__":
    main()
