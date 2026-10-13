"""S2 pre-check: do FinBERT fp16 and fp32 give the same sentiment? (closes the open item of docs/benchmark_finbert.md)

Scores N cleaned texts (filtered_text, deterministic sample) with both precisions and reports the largest and
mean score difference and how many texts change status (positive / negative / neutral).

Usage:
    python scripts/compare_finbert_precision.py [--db output/reddit.sqlite3] [--n 1000]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from etl.common import DEFAULT_DB, connect, status_of          # noqa: E402
from etl.sentiment_finbert import FinBert                      # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--n", type=int, default=1000)
    args = parser.parse_args()
    db = connect(args.db, readonly=True)
    texts = [row[0] for row in db.execute(
        "SELECT final_text FROM filtered_text WHERE src_rowid % 20011 = 5 LIMIT ?", (args.n,))]
    db.close()
    half, full = FinBert("fp16").score(texts), FinBert("fp32").score(texts)
    diffs = [abs(a - b) for a, b in zip(half, full)]
    changed = sum(status_of(a) != status_of(b) for a, b in zip(half, full))
    print(json.dumps({"n": len(texts), "max_abs_diff": round(max(diffs), 5),
                      "mean_abs_diff": round(sum(diffs) / len(diffs), 6),
                      "status_changed": changed, "status_changed_pct": round(100 * changed / len(texts), 2)}))


if __name__ == "__main__":
    main()
