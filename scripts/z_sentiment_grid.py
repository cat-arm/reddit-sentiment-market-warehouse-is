"""EXTENSION (not in the proposal): does the direction of Reddit sentiment line up with the following return better when
the volume spike is stronger (Volume Z-score > 1.5 / 2.0 / 2.5) and the sentiment is stronger (|sentiment_mean| >= 0.05 / 0.30 /
0.50 / 0.80)?  This is the accuracy test behind the signal-detection thresholds of proposal 7.5/7.6 (which only count signals).

Event  = a ticker-hour (merged_hourly_panel, scope 'ticker') with Volume Z-score > z, |sentiment_mean| >= s and at least
         MIN_TEXTS texts (same rule as analysis/signals.py).  The grid is fixed BEFORE looking at the results.
Win    = sign(sentiment_mean) == sign(future_return_h); returns of exactly 0 / NULL are not events (as in A2).
Test   = two-sided exact Binomial test against the win rate of a random +-1 direction (fixed seed) on the SAME rows.
         Raw p-values; with 12 configurations x 5 horizons = 60 tests about 3 are expected below 0.05 by chance alone.
Split  = explore (before 2025-10-01) and hold-out (from 2025-10-01): a result that is real should survive in both.
Fewer than MIN_N = 30 events -> 'ข้อมูลไม่เพียงพอ'.  Read-only on the database.

Usage:  python scripts/z_sentiment_grid.py [--db output/reddit.sqlite3]
Output: output/reports/z_sentiment_grid.md and .csv
"""
import argparse
import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np                                                    # noqa: E402
import pandas as pd                                                   # noqa: E402
from scipy import stats                                               # noqa: E402

from etl.common import DEFAULT_DB, file_header                        # noqa: E402

OUT = ROOT / "output" / "reports"
Z_GRID = (1.5, 2.0, 2.5)
S_GRID = (0.05, 0.30, 0.50, 0.80)
HORIZONS = ("1h", "2h", "3h", "6h", "12h")
MIN_TEXTS = 3
MIN_N = 30
SEED = 20261025
SPLIT = 1759276800                                  # 2025-10-01 00:00 UTC


def evaluate(frame, horizon, rng):
    """(wins, events, baseline_rate, p_value) for one horizon, or None when there are fewer than MIN_N events."""
    ret = np.sign(frame["future_return_" + horizon]).replace(0, np.nan)
    sig = np.sign(frame.sentiment_mean)
    keep = ret.notna() & (sig != 0)
    n = int(keep.sum())
    if n < MIN_N:
        return None
    wins = int((sig[keep] == ret[keep]).sum())
    rand = rng.choice([-1, 1], size=n)
    p0 = float((rand == ret[keep].to_numpy()).mean())
    return wins, n, p0, float(stats.binomtest(wins, n, p0).pvalue)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args(argv)
    db = sqlite3.connect("file:%s?mode=ro" % Path(args.db).resolve().as_posix(), uri=True)
    panel = pd.read_sql_query(
        "SELECT ticker, big_group, hour_utc, sentiment_mean, reddit_volume, reddit_volume_zscore_24 AS z, " +
        ", ".join("future_return_" + h for h in HORIZONS) +
        " FROM merged_hourly_panel WHERE scope = 'ticker' AND variant = 'all' AND has_reddit_data = 1 AND reddit_volume >= ?",
        db, params=(MIN_TEXTS,))
    db.close()
    rows = []
    for z in Z_GRID:
        for s in S_GRID:
            events = panel[(panel.z > z) & (panel.sentiment_mean.abs() >= s)]
            for h in HORIZONS:
                for part, frame in (("ทั้งช่วง", events), ("explore", events[events.hour_utc < SPLIT]),
                                    ("hold-out", events[events.hour_utc >= SPLIT])):
                    res = evaluate(frame, h, np.random.default_rng(SEED))
                    rows.append(dict(z=z, s=s, horizon=h, part=part, events=len(frame),
                                     n=res[1] if res else 0, win=res[0] / res[1] if res else None,
                                     baseline=res[2] if res else None, p=res[3] if res else None))
    result = pd.DataFrame(rows)
    full = result[result.part == "ทั้งช่วง"]
    tested = full.dropna(subset=["p"])

    def cell(r):
        return "ข้อมูลไม่พอ" if r.win != r.win else "%.1f%% (n=%s)%s" % (100 * r.win, "{:,}".format(r.n), "*" if r.p < 0.05 else "")

    lines = ["# เกณฑ์ Z-score × ความรู้สึก: ชั่วโมงที่ปริมาณพุ่งและความรู้สึกชัด ทิศความรู้สึกตรงกับทิศราคาบ่อยแค่ไหน (ส่วนขยาย)", "",
             *file_header("win rate ของทิศความรู้สึกเทียบ Future Return เมื่อเกณฑ์ Z-score = 1.5/2.0/2.5 และ |ความรู้สึก| ≥ 0.05/0.30/0.50/0.80 พร้อมแยกช่วง explore / hold-out",
                          "scripts/z_sentiment_grid.py", "python steps/32_z_sentiment_grid.py",
                          "ตาราง merged_hourly_panel ใน output/reddit.sqlite3 (อ่านอย่างเดียว)"), "",
             "เหตุการณ์ = ชั่วโมง × สินทรัพย์ที่ Volume Z-score เกิน z, |sentiment_mean| ≥ s และมี ≥ %d ข้อความ; ชนะ = ทิศความรู้สึกตรงกับทิศผลตอบแทน (ผลตอบแทน 0 ไม่นับ); "
             "`*` = binomial p < 0.05 เทียบทิศสุ่มบนแถวชุดเดียวกัน (ค่าดิบ ไม่ปรับ)" % MIN_TEXTS, "",
             "กริดถูกกำหนดก่อนดูผล ทดสอบทั้งหมด %d ครั้ง ถ้าสุ่มล้วนคาดว่ามีราว %.0f ครั้งที่ p < 0.05; เหตุการณ์ในชั่วโมงติดกันและหลายสินทรัพย์ในชั่วโมงเดียวกันไม่อิสระ p-value จึงใช้ประกอบเท่านั้น" %
             (len(tested), 0.05 * len(tested)), "",
             "สัญญาณที่ p < 0.05 ในช่วงทั้งหมด: **%d จาก %d** " % ((tested.p < 0.05).sum(), len(tested)), ""]
    for h in HORIZONS:
        lines += ["## กรอบเวลา %s" % h, "", "| Z-score > | " + " | ".join("\\|s\\| ≥ %.2f" % s for s in S_GRID) + " |", "|---|" + "---|" * len(S_GRID)]
        for z in Z_GRID:
            lines.append("| %.1f | " % z + " | ".join(cell(full[(full.z == z) & (full.s == s) & (full.horizon == h)].iloc[0]) for s in S_GRID) + " |")
        lines.append("")
    lines += ["## ผลที่ดูเด่น (p < 0.05) แยกช่วง explore / hold-out", "",
              "| Z > | \\|s\\| ≥ | horizon | ทั้งช่วง | explore | hold-out |", "|---|---|---|---|---|---|"]
    hits = tested[tested.p < 0.05]
    for r in hits.itertuples():
        sub = result[(result.z == r.z) & (result.s == r.s) & (result.horizon == r.horizon)].set_index("part")
        fmt = lambda part: "ข้อมูลไม่พอ" if sub.loc[part, "win"] != sub.loc[part, "win"] else "%.1f%% (n=%s)" % (100 * sub.loc[part, "win"], "{:,}".format(sub.loc[part, "n"]))
        lines.append("| %.1f | %.2f | %s | %.1f%% | %s | %s |" % (r.z, r.s, r.horizon, 100 * r.win, fmt("explore"), fmt("hold-out")))
    if hits.empty:
        lines.append("| (ไม่มี) | | | | | |")
    both = 0
    for r in hits.itertuples():
        sub = result[(result.z == r.z) & (result.s == r.s) & (result.horizon == r.horizon)].set_index("part")
        sign = np.sign(r.win - 0.5)
        both += all(sub.loc[p, "win"] == sub.loc[p, "win"] and np.sign(sub.loc[p, "win"] - 0.5) == sign for p in ("explore", "hold-out"))
    lines += ["", "ในจำนวนนี้ทิศเดียวกัน (สูงกว่าหรือต่ำกว่า 50%%) ทั้งสองช่วง: %d จาก %d" % (both, len(hits)), ""]
    best = tested.sort_values("win", ascending=False).head(3)
    lines += ["win rate สูงสุด 3 อันดับ (เพื่อเตือนว่าค่าสูงสุดจากหลายสิบช่องคือโชค): " +
              "; ".join("z>%.1f, |s|≥%.2f, %s = %.1f%% (n=%s)" % (r.z, r.s, r.horizon, 100 * r.win, "{:,}".format(r.n)) for r in best.itertuples()), ""]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "z_sentiment_grid.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (OUT / "z_sentiment_grid.csv").open("w", newline="", encoding="utf-8") as sink:
        sink.write("\n".join(file_header("ข้อมูลชุดเดียวกับ z_sentiment_grid.md (ทุกช่อง ทุกช่วง)", "scripts/z_sentiment_grid.py",
                                         "python steps/32_z_sentiment_grid.py", "merged_hourly_panel", comment=True)) + "\n")
        result.to_csv(sink, index=False, lineterminator="\n")
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
