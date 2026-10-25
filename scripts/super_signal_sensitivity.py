"""EXTENSION (not in the proposal): do stricter signal filters - "super quality" and "super spike" - score better?

The proposal fixes quality = |final_sentiment| >= 0.30 and spike = reddit_volume_zscore_24 > 1.5.  This script adds two
stricter panels per scope and compares them with the proposal panels, using the same win-rate / Spearman definitions as
analysis.winrate / analysis.correlation:
    super_quality  |final_sentiment| >= 0.50 per text, before averaging (same as quality, stricter edge)
    super_spike    reddit_volume_zscore_24 > 2.0 (same as spike, stricter edge)
Thresholds were fixed BEFORE looking at results (docs/METHOD_DECISIONS_NOT_IN_PROPOSAL.md).  Each panel is also
evaluated on two periods (explore: before 2025-10-01, hold-out: from 2025-10-01) so a lucky result in one period shows up.
The baseline of each row set is a random direction on exactly the same (ticker, hour) rows.
Read-only: the database is opened with mode=ro and nothing is written to it.

Usage:  python scripts/super_signal_sensitivity.py [--db output/reddit.sqlite3]
Output: output/reports/super_signal_sensitivity.md and .csv
"""
import argparse
import csv
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.correlation import correlate                      # noqa: E402
from etl.common import DEFAULT_DB, file_header                  # noqa: E402
from etl.reddit_hourly import aggregate                         # noqa: E402

OUT_DIR = ROOT / "output" / "reports"
MIN_N = 30
SUPER_QUALITY = 0.50
SUPER_SPIKE_Z = 2.0
SPLIT_UTC = 1759276800                                          # 2025-10-01 00:00 UTC
HORIZONS = ("1h", "2h", "3h", "6h", "12h")
PERIODS = {"all": (0, 10 ** 12), "explore": (0, SPLIT_UTC), "holdout": (SPLIT_UTC, 10 ** 12)}
COLS = ["ticker", "big_group", "hour_utc", "sentiment_mean", "reddit_volume_zscore_24"] + \
       ["future_return_" + h for h in HORIZONS]


def load(db):
    q = "SELECT %s FROM panels WHERE panel_name = ?" % ", ".join(COLS)
    base = pd.read_sql_query("SELECT ticker, hour_utc, random_direction FROM panels WHERE panel_name = 'panel_baseline'", db)
    return {n: pd.read_sql_query(q, db, params=(n,)) for n in
            ("panel_Ticker", "panel_Ticker_quality", "panel_Ticker_spike",
             "panel_global", "panel_global_quality", "panel_global_spike")}, base


def super_quality_means(db, per_ticker):
    rows = aggregate(db, "superq", "ABS(s.final_sentiment) >= %s" % SUPER_QUALITY, "__each__" if per_ticker else None)
    return pd.DataFrame([(r[1], r[2], r[4]) for r in rows], columns=["ticker", "hour_utc", "sentiment_mean"])


def build_panels(db, panels):
    out = dict(panels)
    out["panel_Ticker_super_quality"] = panels["panel_Ticker"].drop(columns="sentiment_mean").merge(
        super_quality_means(db, True), on=["ticker", "hour_utc"])
    out["panel_global_super_quality"] = panels["panel_global"].drop(columns=["sentiment_mean"]).merge(
        super_quality_means(db, False).drop(columns="ticker"), on="hour_utc")
    for scope in ("Ticker", "global"):
        out["panel_%s_super_spike" % scope] = panels["panel_%s" % scope].query(
            "reddit_volume_zscore_24 > %s" % SUPER_SPIKE_Z)
    return out


def win(sign, ret):
    r = np.sign(ret).replace(0, np.nan)
    both = pd.concat([sign, r], axis=1, keys=["s", "r"]).dropna()
    return int((both["s"] == both["r"]).sum()), len(both)


def evaluate(name, df, base):
    """Rows: pooled + each ticker, for every period and horizon."""
    df = df.merge(base, on=["ticker", "hour_utc"], how="left")
    rows = []
    for period, (lo, hi) in PERIODS.items():
        part = df[(df.hour_utc >= lo) & (df.hour_utc < hi)]
        groups = [("pooled", "ALL", part)] + [("ticker", t, p) for t, p in part.groupby("ticker")]
        for level, ticker, g in groups:
            sign = np.sign(g["sentiment_mean"]).replace(0, np.nan)
            for h in HORIZONS:
                col = "future_return_" + h
                wins, n = win(sign, g[col])
                bwins, bn = win(g["random_direction"].astype(float), g[col])
                rate = wins / n if n >= MIN_N else np.nan
                p0 = bwins / bn if bn >= MIN_N else 0.5
                p = float(stats.binomtest(wins, n, p0).pvalue) if n >= MIN_N else np.nan
                rho = np.nan
                if level == "pooled":
                    rho = correlate(g, "sentiment_mean", col)[2]
                rows.append(dict(panel=name, period=period, level=level, ticker=ticker, horizon=h, n=n, winrate=rate,
                                 baseline=p0 if n >= MIN_N else np.nan, p_value=p, spearman=rho))
    return rows


def add_bh(frame):
    """Benjamini-Hochberg across tickers within (panel, period, horizon); pooled rows stay unadjusted."""
    frame["p_bh"] = np.nan
    mask = frame.level == "ticker"
    for _, idx in frame[mask & frame.p_value.notna()].groupby(["panel", "period", "horizon"]).groups.items():
        frame.loc[idx, "p_bh"] = stats.false_discovery_control(frame.loc[idx, "p_value"].to_numpy())
    return frame


def pct(v):
    return "n/a" if pd.isna(v) else "%.1f%%" % (100 * v)


def report(frame, order):
    L = ["# Super quality / super spike — เทียบกับเกณฑ์ใน proposal (ส่วนขยาย)", ""]
    L += file_header("ผลทดสอบว่าเกณฑ์เข้มขึ้น (super quality \\|score\\| >= 0.50, super spike z > 2.0) ให้ win rate / Spearman ดีกว่า quality (0.30) และ spike (1.5) หรือไม่ (ส่วนขยาย ไม่อยู่ใน proposal)",
                     "scripts/super_signal_sensitivity.py", "python scripts/super_signal_sensitivity.py",
                     "ตาราง panels / sentiment_item / ticker_mentions ใน output/reddit.sqlite3 (อ่านอย่างเดียว)")
    L += ["", "วิธีอ่าน: win rate เทียบ baseline = ทิศทางสุ่มบนแถวชุดเดียวกัน (ควรใกล้ 50%); p = binomial test (ดิบ ไม่ปรับ); "
          "ช่วง explore = ก่อน 2025-10-01, hold-out = ตั้งแต่ 2025-10-01 เป็นต้นไป; ข้อมูลรายชั่วโมงมี autocorrelation และ horizon ซ้อนกัน "
          "p-value จึงใช้ประกอบเท่านั้น; panel_global ใช้ความรู้สึกรวมค่าเดียวต่อชั่วโมงร่วมกันทั้ง 34 สินทรัพย์ แถว pooled จึงไม่อิสระกัน", ""]
    pooled = frame[(frame.level == "pooled")]
    L += ["## ทั้งช่วง: รวมทุกสินทรัพย์ (pooled)", "",
          "| panel | horizon | n | win rate | baseline | p | Spearman |", "|---|---|---|---|---|---|---|"]
    for name in order:
        for h in HORIZONS:
            r = pooled[(pooled.panel == name) & (pooled.period == "all") & (pooled.horizon == h)].iloc[0]
            L.append("| %s | %s | %s | %s | %s | %s | %s |" % (name, h, "{:,}".format(r.n), pct(r.winrate), pct(r.baseline),
                     "n/a" if pd.isna(r.p_value) else "%.3f" % r.p_value, "n/a" if pd.isna(r.spearman) else "%.4f" % r.spearman))
    L += ["", "## แยกช่วงเวลา: win rate (pooled) ช่วง explore เทียบ hold-out", "",
          "| panel | horizon | explore win rate (n) | hold-out win rate (n) |", "|---|---|---|---|"]
    for name in order:
        for h in HORIZONS:
            a, b = [pooled[(pooled.panel == name) & (pooled.period == p) & (pooled.horizon == h)].iloc[0] for p in ("explore", "holdout")]
            L.append("| %s | %s | %s (%s) | %s (%s) |" % (name, h, pct(a.winrate), "{:,}".format(a.n), pct(b.winrate), "{:,}".format(b.n)))
    tick = frame[(frame.level == "ticker") & (frame.period == "all")]
    L += ["", "## รายสินทรัพย์ (ทั้งช่วง): กี่ตัวจาก 34 ที่คำนวณได้ (n >= 30) และมี BH p < 0.05", "",
          "| panel | horizon | ตัวที่คำนวณได้ | win rate เฉลี่ย | BH p < 0.05 (เหนือ baseline / ต่ำกว่า) |", "|---|---|---|---|---|"]
    for name in order:
        for h in HORIZONS:
            t = tick[(tick.panel == name) & (tick.horizon == h) & tick.winrate.notna()]
            sig = t[t.p_bh < 0.05]
            L.append("| %s | %s | %d | %s | %d / %d |" % (name, h, len(t), pct(t.winrate.mean()),
                     (sig.winrate > sig.baseline).sum(), (sig.winrate < sig.baseline).sum()))
    return "\n".join(L) + "\n"


def run(db_path):
    db = sqlite3.connect("file:%s?mode=ro" % Path(db_path).as_posix(), uri=True)
    try:
        panels, base = load(db)
        panels = build_panels(db, panels)
    finally:
        db.close()
    order = [n for n in ("panel_Ticker", "panel_Ticker_quality", "panel_Ticker_super_quality", "panel_Ticker_spike",
                         "panel_Ticker_super_spike", "panel_global", "panel_global_quality", "panel_global_super_quality",
                         "panel_global_spike", "panel_global_super_spike")]
    frame = pd.DataFrame([r for n in order for r in evaluate(n, panels[n], base)])
    frame = add_bh(frame)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "super_signal_sensitivity.csv", "w", encoding="utf-8-sig", newline="") as f:
        for line in file_header("ผลดิบ win rate / Spearman ของ panel ที่เข้มขึ้น แยกช่วงเวลา (ข้อมูลชุดเดียวกับ super_signal_sensitivity.md; ส่วนขยาย)",
                                "scripts/super_signal_sensitivity.py", "python scripts/super_signal_sensitivity.py",
                                "panels / sentiment_item / ticker_mentions ใน output/reddit.sqlite3", comment=True):
            f.write(line + "\n")
        frame.to_csv(f, index=False)
    (OUT_DIR / "super_signal_sensitivity.md").write_text(report(frame, order), encoding="utf-8")
    print("wrote", OUT_DIR / "super_signal_sensitivity.md")
    return frame


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    run(parser.parse_args(argv).db)
    return 0


if __name__ == "__main__":
    sys.exit(main())
