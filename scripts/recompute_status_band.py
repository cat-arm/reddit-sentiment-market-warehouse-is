"""Re-derive vader_status / finbert_status from the stored scores with the VADER convention
(s >= 0.05 positive, s <= -0.05 negative, otherwise neutral).  Scores are never touched, only the label.

Default is a dry run that just counts rows whose stored status differs from the rule.
    python scripts/recompute_status_band.py --db output/reddit.sqlite3           # count only
    python scripts/recompute_status_band.py --db output/reddit.sqlite3 --apply   # fix labels
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from etl.common import DEFAULT_DB, connect  # noqa: E402

# Same rule as etl.common.status_of, expressed in SQL so 22M rows need no Python loop.
EXPECTED = ("CASE WHEN {c} >= 0.05 THEN 'positive' WHEN {c} <= -0.05 THEN 'negative' ELSE 'neutral' END")
TABLES = (("sentiment_vader", "vader_score", "vader_status"),
          ("sentiment_finbert", "finbert_score", "finbert_status"))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    con = connect(args.db)
    for table, score, status in TABLES:
        exp = EXPECTED.format(c=score)
        total = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        rows = con.execute(f"SELECT {status}, {exp}, COUNT(*) FROM {table} "
                           f"WHERE {status} IS NOT {exp} GROUP BY 1, 2").fetchall()
        print(f"{table}: total={total:,} mismatched={sum(r[2] for r in rows):,}")
        for old, new, n in rows:
            print(f"   {old} -> {new}: {n:,}")
        if args.apply and rows:
            con.execute(f"UPDATE {table} SET {status} = {exp} WHERE {status} IS NOT {exp}")
            con.commit()
            print("   applied")
    con.close()


if __name__ == "__main__":
    main()
