"""How much did adding the post title to every comment change the sentiment?  (cleaner_version 1.0 -> 2.0)

Compares the archived text-only results (sentiment_item_v1, made before 2026-10-24) with the rebuilt
sentiment_item for every text that has a score in both.  Comments and submissions are reported separately: a
submission is unchanged by design, so it doubles as a control (its statuses must not move).
Read-only.  Needs scripts/archive_sentiment_v1.py to have been run before the rebuild.

Usage:  python scripts/compare_context_effect.py [--db output/reddit.sqlite3]
Output: output/reports/context_effect.md
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from etl.common import DEFAULT_DB, connect, file_header  # noqa: E402

OUT = ROOT / "output" / "reports" / "context_effect.md"
MODELS = (("VADER", "vader_status", "vader_score"), ("FinBERT", "finbert_status", "finbert_score"),
          ("final (รวมผล)", "final_status", "final_sentiment"))


def query(db, status_col, score_col):
    """Per content_type: texts compared, texts whose status changed, mean score before / after."""
    return db.execute(
        "SELECT p.content_type, COUNT(*), SUM(o.%(s)s != n.%(s)s), AVG(o.%(v)s), AVG(n.%(v)s) "
        "FROM sentiment_item n JOIN sentiment_item_v1 o ON o.src_rowid = n.src_rowid "
        "JOIN processed_text p ON p.src_rowid = n.src_rowid GROUP BY 1" % {"s": status_col, "v": score_col}).fetchall()


def transitions(db):
    return db.execute(
        "SELECT o.final_status, n.final_status, COUNT(*) FROM sentiment_item n "
        "JOIN sentiment_item_v1 o ON o.src_rowid = n.src_rowid JOIN processed_text p ON p.src_rowid = n.src_rowid "
        "WHERE p.content_type = 'comment' AND o.final_status != n.final_status GROUP BY 1, 2 ORDER BY 3 DESC").fetchall()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    db = connect(args.db, readonly=True)
    try:
        lines = ["# ผลของการใส่ title โพสต์แม่ให้คอมเมนต์ (final_text เวอร์ชัน 1.0 → 2.0)", "",
                 *file_header("เทียบความรู้สึกก่อน (เฉพาะข้อความของคอมเมนต์) กับหลัง (title โพสต์แม่ + คอมเมนต์) ของข้อความที่มีคะแนนทั้งสองรอบ",
                              "scripts/compare_context_effect.py", "python scripts/compare_context_effect.py",
                              "sentiment_item_v1 (ก่อน) เทียบ sentiment_item (หลัง) ใน output/reddit.sqlite3 อ่านอย่างเดียว"), "",
                 "ข้อความประเภท submission ไม่ถูกเปลี่ยนโดยการออกแบบ จึงใช้เป็นตัวควบคุม (ต้องเป็น 0%)", ""]
        for name, status_col, score_col in MODELS:
            lines += ["## %s" % name, "", "| ประเภท | ข้อความที่เทียบ | ป้ายเปลี่ยน | % เปลี่ยน | คะแนนเฉลี่ยก่อน | หลัง |",
                      "|---|---|---|---|---|---|"]
            for ctype, n, changed, before, after in query(db, status_col, score_col):
                lines.append("| %s | %d | %d | %.2f%% | %.4f | %.4f |" % (
                    ctype, n, changed or 0, 100.0 * (changed or 0) / n, before or 0, after or 0))
            lines.append("")
        lines += ["## final_status ของคอมเมนต์ที่เปลี่ยน (ก่อน → หลัง)", "", "| ก่อน | หลัง | จำนวน |", "|---|---|---|"]
        lines += ["| %s | %s | %d |" % row for row in transitions(db)]
    finally:
        db.close()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
