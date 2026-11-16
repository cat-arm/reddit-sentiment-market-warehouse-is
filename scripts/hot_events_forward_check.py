"""EXTENSION (system 7.6 as a predictive system): does the Hot Events score, computed only from what is known in the hour, come before a
bigger price move?  And does it tell the direction?

The score (the number of the six KPIs a row passes), its default thresholds and cuts are those of the Hot Events page (analysis/hot_events.py);
the thresholds are learned on the training period only.  For every asset x hour of the whole period (the rows the page lays on the table):
    relative move  |future_return_h| / the normal move of the asset known at the hour (mean over rows whose horizon had ended)
    big move       relative move > 1
    AUC            of the score for a big move (0.5 = chance), with a 95% interval from a block bootstrap over UTC days (the hours of a day
                   are not independent), for the full score, the Reddit KPIs only and the price KPIs only
    hit rate       sign(sentiment_mean) = sign(future return), binomial test against 50%
Each number is also given for two periods, explore (before 2025-10-01) and hold-out (from 2025-10-01), the split of
scripts/super_signal_sensitivity.py, so a result that holds in one period only shows up.
Read-only: nothing is written to the database.

Usage:  python scripts/hot_events_forward_check.py [--db output/reddit.sqlite3] [--boot 200]
Output: output/reports/hot_events_forward_check.md and .csv
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis import hot_events as he                           # noqa: E402
from dashboard import data                                      # noqa: E402
from etl.common import DEFAULT_DB, file_header                  # noqa: E402

OUT_DIR = ROOT / "output" / "reports"
SPLIT_UTC = he.SPLIT_UTC                                        # 2025-10-01 00:00 UTC (same split as super_signal_sensitivity.py)
SEED = 20261114
PRICE_KPIS = he.PRICE_KPIS


def load(db):
    """Every asset x hour of the Reddit period, as the Hot Events page reads it (no filter before the score)."""
    info = data.data_range(db)
    start, end = int(info["reddit_lo"]), int(info["reddit_hi"])
    tickers = tuple(data.tickers(db).ticker)
    communities = tuple(dict.fromkeys(data.sources(db).subreddit))
    found = data.market_signals(db, start, end, tickers, ("positive", "negative", "neutral"), 0.0, 0.0, communities, "VADER+FinBERT",
                                ("Post", "Comment"), 0, 1.5)
    bars = data.price_series_for(db, tickers, start, end)[["ticker", "hour_utc", "normalized_atr"]]
    return found.merge(bars, on=["ticker", "hour_utc"], how="left").reset_index(drop=True)


def boot_auc(points, big, day, n_boot, rng):
    """95% interval of the AUC by resampling whole UTC days."""
    frame = pd.DataFrame({"p": points.to_numpy(), "b": big.to_numpy(), "d": day.to_numpy()})
    groups = [g for _, g in frame.groupby("d")]
    out = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(groups), len(groups))
        sample = pd.concat([groups[i] for i in pick], ignore_index=True)
        out.append(he.auc(sample.p, sample.b))
    return np.nanpercentile(out, [2.5, 97.5])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--boot", type=int, default=200)
    args = ap.parse_args()
    df = load(args.db)
    W = he.DEFAULT_WEIGHTS                                            # the score is in %: the weights of the KPIs a row passes (a subset of KPIs is scaled to 100 %)
    scores = {"all KPIs": he.score_pct(df, he.DEFAULT_RULES, W), "Reddit KPIs only": he.score_pct(df, {k: v for k, v in he.DEFAULT_RULES.items() if k in he.REDDIT_KPIS}, W),
              "price KPIs only": he.score_pct(df, {k: v for k, v in he.DEFAULT_RULES.items() if k in PRICE_KPIS}, W)}
    learned = he.learn_defaults(df)                                   # learned on the training period only; the code's defaults must be its rounding
    code = {m: t for m, _, t, _ in he.METRICS}
    learned = learned.assign(code_threshold=learned.kpi.map(code))
    learned["matches"] = (learned.threshold - learned.code_threshold).abs().lt(0.011)
    periods = {"all": df.hour_utc >= 0, "explore": df.hour_utc < SPLIT_UTC, "holdout": df.hour_utc >= SPLIT_UTC}
    day = df.hour_utc // 86400
    rng = np.random.default_rng(SEED)
    auc_rows, level_rows = [], []
    for h in he.FORWARD_HORIZONS:
        rel = he.relative_move(df, h)
        big = (rel > 1).astype(float).where(rel.notna())
        for pname, mask in periods.items():
            keep = mask & rel.notna()
            for sname, pts in scores.items():
                lo, hi = boot_auc(pts[keep], big[keep], day[keep], args.boot, rng) if pname == "all" and args.boot else (np.nan, np.nan)
                auc_rows.append({"horizon": h, "period": pname, "score": sname, "n": int(keep.sum()), "auc": he.auc(pts[keep], big[keep]),
                                 "ci_lo": lo, "ci_hi": hi})
            table, _ = he.forward(df[mask], scores["all KPIs"][mask], h)
            for r in table.itertuples(index=False):
                fut = pd.to_numeric(df.loc[mask, "future_return_" + h], errors="coerce")
                lv = he.level(scores["all KPIs"][mask]).replace("", "ไม่ถึง low")
                sgn = (np.sign(df.loc[mask, "sentiment_mean"]) * np.sign(fut))[(lv == r.level) & keep[mask]]
                wins, n_dir = int((sgn > 0).sum()), int((sgn != 0).sum())
                p = stats.binomtest(wins, n_dir, 0.5).pvalue if n_dir else np.nan
                level_rows.append({"horizon": h, "period": pname, "level": r.level, "n": r.n, "move": r.move, "big": r.big, "hit": r.hit, "hit_p": p})
    aucs, levels = pd.DataFrame(auc_rows), pd.DataFrame(level_rows)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rerun = "python steps/34_hot_events_forward_check.py"
    what = "ทดสอบว่าคะแนน Hot Events (ระบบ 7.6) บอกล่วงหน้าได้ไหมว่าราคาจะขยับแรงกว่าปกติ และบอกทิศได้ไหม (ส่วนขยาย: 7.6 ในฐานะระบบ Predictive)"
    src = "output/reddit.sqlite3 อ่านอย่างเดียว ผ่าน dashboard/data.py (ข้อมูลชุดเดียวกับหน้า Hot Events), คะแนนจาก analysis/hot_events.py"
    with open(OUT_DIR / "hot_events_forward_check.csv", "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(file_header(what, "scripts/hot_events_forward_check.py", rerun, src, comment=True)) + "\n")
        aucs.assign(table="auc").to_csv(f, index=False)
        levels.assign(table="level").to_csv(f, index=False)

    def pct(x):
        return "-" if x != x else "%.1f%%" % (100.0 * x)

    lines = ["# Hot Events ในฐานะระบบ Predictive: ราคาหลังสัญญาณ", "", *file_header(what, "scripts/hot_events_forward_check.py", rerun, src), "",
             "คะแนน (%%) = ผลรวมน้ำหนักของ KPI ที่ผ่านเกณฑ์ (6 ตัว น้ำหนัก 17/17/17/17/16/16 รวม 100%%) ใช้เฉพาะข้อมูลที่รู้ ณ ชั่วโมงนั้น; ระดับ low / medium / high = คะแนน ≥ "
             "%d / %d / %d%%. "
             "**ขยับกี่เท่าของปกติ** = |future return| ÷ ค่าเฉลี่ยของขนาดการขยับของสินทรัพย์เดียวกันในอดีตที่รู้ได้ ณ ชั่วโมงนั้น; "
             "**ขยับแรง** = มากกว่า 1 เท่า; **AUC** ของคะแนนสำหรับการขยับแรง (0.5 = สุ่ม), ช่วงเชื่อมั่น 95%% จาก block bootstrap รายวัน %d รอบ; "
             "**ทิศตรง** = เครื่องหมายความรู้สึกตรงกับเครื่องหมาย future return (binomial เทียบ 50%%). explore = ก่อน 2025-10-01, hold-out = ตั้งแต่ 2025-10-01"
             % (he.DEFAULT_CUTS_PCT["low"], he.DEFAULT_CUTS_PCT["medium"], he.DEFAULT_CUTS_PCT["high"], args.boot), "",
             "## AUC ของคะแนน (ทำนายว่าจะขยับแรงกว่าปกติ)", "",
             "| ช่วงหลังสัญญาณ | คะแนน | ทั้งหมด (95% CI) | explore | hold-out | n |", "|---|---|---|---|---|---|"]
    for h in he.FORWARD_HORIZONS:
        for sname in scores:
            a = aucs[(aucs.horizon == h) & (aucs.score == sname)].set_index("period")
            lines.append("| %s | %s | %.3f (%.3f–%.3f) | %.3f | %.3f | %s |" % (h, sname, a.auc["all"], a.ci_lo["all"], a.ci_hi["all"], a.auc["explore"],
                                                                           a.auc["holdout"], "{:,}".format(int(a.n["all"]))))
    lines += ["", "## ค่าเริ่มต้นของเกณฑ์: เรียนจากช่วงฝึกเท่านั้น (ก่อน 2025-10-01)", "",
              "เกณฑ์ = ค่าที่มีเพียง %d%% ของชั่วโมง × สินทรัพย์ในช่วงฝึกสูงกว่า (ไม่มีน้ำหนัก). "
              "AUC ช่วงฝึก = ความสามารถของ \"ผ่านเกณฑ์\" ตัวเดียวในการทายการขยับแรง 1 ชม. ข้างหน้า (ข้อมูลประกอบ ไม่ได้ใช้คำนวณ; 0.5 = สุ่ม). "
              "คอลัมน์ \"ในโค้ด\" = ค่าที่ analysis/hot_events.py ใช้เป็นค่าเริ่มต้น (ปัดแล้ว); ตรง = ใช่ คือค่าในโค้ดมาจากการคำนวณนี้" % (100 * he.TOP_SHARE), "",
              "| KPI | เกณฑ์ที่เรียน | เกณฑ์ในโค้ด | AUC ช่วงฝึก | ตรง |", "|---|---|---|---|---|"]
    for r in learned.itertuples(index=False):
        lines.append("| %s | %.4f | %.2f | %.3f | %s |" % (r.kpi, r.threshold, r.code_threshold, r.auc_train, "ใช่" if r.matches else "**ไม่**"))
    lines += ["", "## แยกตามระดับ (คะแนนทุก KPI)", "",
              "| ช่วงหลังสัญญาณ | ช่วงข้อมูล | ระดับ | n | ขยับกี่เท่าของปกติ | ขยับแรง | ทิศตรง | p ทิศ |", "|---|---|---|---|---|---|---|---|"]
    for r in levels.itertuples(index=False):
        lines.append("| %s | %s | %s | %s | %.2f | %s | %s | %.3f |" % (r.horizon, r.period, r.level, "{:,}".format(int(r.n)), r.move, pct(r.big), pct(r.hit), r.hit_p))
    full = aucs[(aucs.period == "all") & (aucs.score == "all KPIs")].set_index("horizon").auc
    hold = aucs[(aucs.period == "holdout") & (aucs.score == "all KPIs")].set_index("horizon").auc
    lines += ["", "## ข้อสรุป", "",
              "- ขนาดการขยับ: AUC ของคะแนนเต็ม %s (ทั้งช่วง) และ %s (hold-out) ทุกช่วงเวลาหลังสัญญาณ" % (
                  " / ".join("%s %.3f" % (h, full[h]) for h in he.FORWARD_HORIZONS), " / ".join("%s %.3f" % (h, hold[h]) for h in he.FORWARD_HORIZONS)),
              "- ทิศ: ดูคอลัมน์ทิศตรงในตารางระดับ (ใกล้ 50% = บอกทิศไม่ได้) — คะแนนเป็นสัญญาณเตือนว่าราคาจะผันผวน ไม่ใช่สัญญาณซื้อหรือขาย",
              "- AUC เฉพาะ KPI ฝั่ง Reddit เทียบ เฉพาะ KPI ฝั่งราคา บอกว่า Reddit เพิ่มข้อมูลจากราคามากน้อยเพียงใด",
              "- ข้อจำกัด: ไม่รวมต้นทุนซื้อขาย; ผลเป็นของข้อมูลย้อนหลัง; 'ปกติ' ของสินทรัพย์ต้องมีอดีตอย่างน้อย %d แถว" % he.MIN_PRIOR]
    (OUT_DIR / "hot_events_forward_check.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[-4:]))


if __name__ == "__main__":
    main()
