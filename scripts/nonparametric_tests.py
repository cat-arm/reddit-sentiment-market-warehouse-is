"""Non-parametric tests of the relation between Reddit sentiment and price returns (EXTENSION of system 7.4; the advisor's remark: Pearson needs normal
data, otherwise use non-parametric methods - see scripts/normality_check.py: none of the variables is normal).

For every one of the 34 assets of the panel Global (the Sentiment Score of every text of the market, hourly) and every target (Current Return = log_return,
future return 1h / 2h / 3h / 6h / 12h; the Future Return is the log return, like the Current Return):
  1. Spearman's rho (ranks: no assumption about the distribution), with
       - a 95% interval from a BLOCK bootstrap: the UTC days are resampled with replacement (the hours of a day are not independent),
       - a p-value from a CIRCULAR-SHIFT permutation test: the sentiment series is shifted against the returns by a random number of rows (the ranks are shifted,
         the autocorrelation of both series is kept, only their alignment is broken), which is what the usual formula for p ignores;
       - the usual p-value of the formula, next to it, to show how many results it makes significant that the shift test does not.
  2. Mann-Whitney U: the return of the hours whose majority sentiment is positive against those negative (effect size = the probability that a positive hour
     has the higher return, 0.5 = no difference).
  3. Kruskal-Wallis across positive / negative / neutral hours (effect size epsilon-squared).
All p-values are adjusted with Benjamini-Hochberg inside each family (the same rule as system 7.4).  Pooled over the assets (one row per asset-hour) Pearson,
Spearman and Kendall's tau-b are compared.  Read-only: nothing is written to the database.

Caveats: the rows of an asset are the hours with Reddit data and a price (not every clock hour: a shift is a shift in rows); the Sentiment Score of the market is the
same for every asset in an hour, so the 34 assets are not 34 independent tests; the p-values stay descriptive.

Usage:  python scripts/nonparametric_tests.py [--db output/reddit.sqlite3] [--boot 1000] [--shifts 2000]
Output: output/reports/nonparametric_tests.md and .csv
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from etl.common import DEFAULT_DB, connect, file_header      # noqa: E402

OUT_DIR = ROOT / "output" / "reports"
SEED = 20261116
TARGETS = ["log_return", "future_return_1h", "future_return_2h", "future_return_3h", "future_return_6h", "future_return_12h"]
TARGET_LABEL = {"log_return": "Current Return", **{t: t.replace("future_return_", "") for t in TARGETS[1:]}}
MIN_ROWS = 100                                                # fewer rows than this: no test for the asset and target
MIN_GROUP = 30                                                # hours in a sentiment group for Mann-Whitney / Kruskal-Wallis
MIN_SHIFT = 24                                                # rows: a shift smaller than this keeps too much of the original alignment


def load(db):
    cols = ["ticker", "hour_utc", "sentiment_mean", "majority_final_status"] + TARGETS
    con = connect(db, readonly=True)
    try:
        return pd.read_sql_query("SELECT %s FROM panels WHERE panel_name = 'panel_global' AND has_reddit_data = 1 AND sentiment_mean IS NOT NULL "
                                 "ORDER BY ticker, hour_utc" % ", ".join(cols), con)
    finally:
        con.close()


def bh(pvalues):
    """Benjamini-Hochberg adjusted p-values (input order kept; NaN stays NaN)."""
    p = np.asarray(pvalues, dtype=float)
    out = np.full(len(p), np.nan)
    ok = ~np.isnan(p)
    values = p[ok]
    order = np.argsort(values)
    adjusted = np.empty(len(values))
    running = 1.0
    for rank in range(len(values) - 1, -1, -1):
        i = order[rank]
        running = min(running, values[i] * len(values) / (rank + 1))
        adjusted[i] = running
    out[ok] = adjusted
    return out


def block_indices(starts, counts, rng):
    """Row indices of one bootstrap sample: the days (blocks of consecutive rows) drawn with replacement, concatenated."""
    picked = rng.integers(0, len(starts), len(starts))
    lengths = counts[picked]
    ends = np.cumsum(lengths)
    return np.repeat(starts[picked] - (ends - lengths), lengths) + np.arange(ends[-1])


def corr(a, b):
    a = a - a.mean()
    b = b - b.mean()
    denominator = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / denominator) if denominator > 0 else np.nan


def spearman_block(x, y, days, rng, boot, shifts):
    """rho, the 95% block-bootstrap interval, the circular-shift p-value and the formula's p-value of Spearman's rho of x and y (aligned rows, sorted by time)."""
    rx, ry = stats.rankdata(x), stats.rankdata(y)
    rho = corr(rx, ry)
    if np.isnan(rho):
        return rho, np.nan, np.nan, np.nan, np.nan
    formula_p = float(stats.spearmanr(x, y).pvalue)
    _, first, counts = np.unique(days, return_index=True, return_counts=True)
    values = np.empty(boot)
    for k in range(boot):
        idx = block_indices(first, counts, rng)
        values[k] = corr(stats.rankdata(x[idx]), stats.rankdata(y[idx]))
    low, high = np.nanpercentile(values, [2.5, 97.5])
    n = len(x)
    if n > 2 * MIN_SHIFT + 10:
        moves = rng.integers(MIN_SHIFT, n - MIN_SHIFT, shifts)
        null = np.array([corr(np.roll(rx, int(s)), ry) for s in moves])
        shift_p = (1 + float((np.abs(null) >= abs(rho)).sum())) / (shifts + 1)
    else:
        shift_p = np.nan
    return rho, float(low), float(high), shift_p, formula_p


def group_tests(y, status):
    """Mann-Whitney (positive vs negative hours) and Kruskal-Wallis (positive / negative / neutral) of the target y."""
    pos, neg, neu = y[status == "positive"], y[status == "negative"], y[status == "neutral"]
    row = {"n_pos": len(pos), "n_neg": len(neg), "n_neu": len(neu), "mw_prob_superiority": np.nan, "mw_p": np.nan, "kw_epsilon2": np.nan, "kw_p": np.nan}
    if len(pos) >= MIN_GROUP and len(neg) >= MIN_GROUP:
        u = stats.mannwhitneyu(pos, neg, alternative="two-sided")
        row["mw_prob_superiority"] = float(u.statistic / (len(pos) * len(neg)))
        row["mw_p"] = float(u.pvalue)
    groups = [g for g in (pos, neg, neu) if len(g) >= MIN_GROUP]
    if len(groups) >= 2:
        h = stats.kruskal(*groups)
        total = sum(len(g) for g in groups)
        row["kw_epsilon2"] = float((h.statistic - len(groups) + 1) / (total - len(groups)))
        row["kw_p"] = float(h.pvalue)
    return row


def run(frame, boot, shifts):
    rng = np.random.default_rng(SEED)
    rows = []
    for ticker, part in frame.groupby("ticker"):
        part = part.sort_values("hour_utc")
        for target in TARGETS:
            sub = part[["hour_utc", "sentiment_mean", "majority_final_status", target]].dropna(subset=["sentiment_mean", target])
            if len(sub) < MIN_ROWS:
                continue
            x, y = sub.sentiment_mean.to_numpy(float), sub[target].to_numpy(float)
            days = (sub.hour_utc.to_numpy() // 86400).astype(int)
            rho, low, high, shift_p, formula_p = spearman_block(x, y, days, rng, boot, shifts)
            rows.append({"ticker": ticker, "target": TARGET_LABEL[target], "n": len(sub), "spearman_rho": rho, "ci_low": low, "ci_high": high,
                         "p_formula": formula_p, "p_shift": shift_p, **group_tests(y, sub.majority_final_status.to_numpy())})
    table = pd.DataFrame(rows)
    for col in ("p_formula", "p_shift", "mw_p", "kw_p"):
        table[col + "_bh"] = bh(table[col])
    return table


def pooled(frame):
    """Pearson, Spearman and Kendall's tau-b of the pooled asset-hours (one row per asset-hour): do the three agree?"""
    rows = []
    for target in ("log_return", "future_return_1h"):
        sub = frame[["sentiment_mean", target]].dropna()
        x, y = sub.sentiment_mean.to_numpy(float), sub[target].to_numpy(float)
        rows.append({"pair": "sentiment_mean x %s" % TARGET_LABEL[target], "n": len(sub), "pearson": stats.pearsonr(x, y)[0], "spearman": stats.spearmanr(x, y)[0],
                     "kendall_tau_b": stats.kendalltau(x, y)[0]})
    return pd.DataFrame(rows)


def fmt_p(p):
    return "-" if pd.isna(p) else ("<0.001" if p < 0.001 else "%.3f" % p)


def report(table, comparison, boot, shifts):
    sig = lambda col: int((table[col] < 0.05).sum())
    total = len(table)
    lines = ["# การทดสอบแบบ non-parametric ของความสัมพันธ์ระหว่างความรู้สึก Reddit กับผลตอบแทน (ส่วนขยายของระบบ 7.4)", "",
             *file_header("ผลสหสัมพันธ์อันดับ Spearman พร้อมช่วงความเชื่อมั่นแบบ block bootstrap และ p จาก circular-shift permutation, Mann-Whitney U และ "
                          "Kruskal-Wallis รายสินทรัพย์ × ช่วงเวลา ตอบข้อสังเกตของอาจารย์ที่ว่า Pearson ต้องใช้ข้อมูลปกติ (ข้อมูลเราไม่ปกติ: normality_check.md)",
                          "scripts/nonparametric_tests.py", "python scripts/nonparametric_tests.py --boot %d --shifts %d" % (boot, shifts),
                          "ตาราง panels (panel_global) ใน output/reddit.sqlite3 อ่านอย่างเดียว"), "",
             "วิธี: Spearman ใช้อันดับ ไม่ต้องสมมติการแจกแจง · ช่วงความเชื่อมั่น 95%% จาก block bootstrap (สุ่มทั้งวัน UTC พร้อมคืน %d รอบ) · "
             "p-shift = สัดส่วนของการเลื่อนอนุกรมความรู้สึกแบบวงกลมโดยสุ่ม (%d ครั้ง, เลื่อนอย่างน้อย %d แถว) ที่ให้ |ρ| ไม่น้อยกว่าค่าจริง "
             "(รักษา autocorrelation ของทั้งสองอนุกรม) · p-formula = p ของสูตรปกติ (ไม่คิด autocorrelation) · BH = ปรับ p ทั้งชุดด้วย Benjamini–Hochberg" % (boot, shifts, MIN_SHIFT), "",
             "## 1) สรุป (%d คู่ สินทรัพย์ × ช่วงเวลา)" % total, "",
             "| การทดสอบ | p < 0.05 ก่อนปรับ | p(BH) < 0.05 |", "|---|---|---|",
             "| Spearman — p จากสูตร (เดิม) | %d | %d |" % (sig("p_formula"), sig("p_formula_bh")),
             "| Spearman — p จาก circular-shift (รักษา autocorrelation) | %d | %d |" % (sig("p_shift"), sig("p_shift_bh")),
             "| Mann–Whitney U (ชั่วโมงบวก เทียบ ลบ) | %d | %d |" % (sig("mw_p"), sig("mw_p_bh")),
             "| Kruskal–Wallis (บวก / ลบ / กลาง) | %d | %d |" % (sig("kw_p"), sig("kw_p_bh")), "",
             "ช่วงความเชื่อมั่น 95%% ของ Spearman ρ ไม่คร่อมศูนย์ใน %d จาก %d คู่ · |ρ| มากที่สุด %.3f · ค่ามัธยฐานของ |ρ| %.3f" % (
                 int(((table.ci_low > 0) | (table.ci_high < 0)).sum()), total, table.spearman_rho.abs().max(), table.spearman_rho.abs().median()), "",
             "## 2) Pearson, Spearman และ Kendall's tau-b (รวมสินทรัพย์-ชั่วโมง) สอดคล้องกันหรือไม่", "",
             "| คู่ตัวแปร | n | Pearson | Spearman | Kendall τ-b |", "|---|---|---|---|---|"]
    for r in comparison.itertuples():
        lines.append("| %s | %s | %+.4f | %+.4f | %+.4f |" % (r.pair, "{:,}".format(r.n), r.pearson, r.spearman, r.kendall_tau_b))
    lines += ["", "## 3) ผลรายสินทรัพย์ (เรียงตาม p-shift จากน้อยไปมาก, 20 อันดับแรก)", "",
              "| สินทรัพย์ | ช่วง | n | Spearman ρ | ช่วงเชื่อมั่น 95% | p-formula | p-shift | p-shift (BH) | MW prob.sup. | MW p (BH) | KW ε² | KW p (BH) |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in table.sort_values("p_shift").head(20).itertuples():
        lines.append("| %s | %s | %s | %+.3f | %+.3f ถึง %+.3f | %s | %s | %s | %s | %s | %s | %s |" % (
            r.ticker, r.target, "{:,}".format(r.n), r.spearman_rho, r.ci_low, r.ci_high, fmt_p(r.p_formula), fmt_p(r.p_shift), fmt_p(r.p_shift_bh),
            "-" if pd.isna(r.mw_prob_superiority) else "%.3f" % r.mw_prob_superiority, fmt_p(r.mw_p_bh), "-" if pd.isna(r.kw_epsilon2) else "%.4f" % r.kw_epsilon2, fmt_p(r.kw_p_bh)))
    lines += ["", "ตารางเต็มทุกคู่อยู่ใน `output/reports/nonparametric_tests.csv`", ""]
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--boot", type=int, default=1000)
    parser.add_argument("--shifts", type=int, default=2000)
    args = parser.parse_args(argv)
    frame = load(args.db)
    table = run(frame, args.boot, args.shifts)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUT_DIR / "nonparametric_tests.csv").open("w", newline="", encoding="utf-8") as sink:         # the slow part is done: keep it before the report is built
        sink.write("\n".join(file_header("ผลการทดสอบ non-parametric รายสินทรัพย์ × ช่วงเวลา (ข้อมูลชุดเดียวกับ nonparametric_tests.md)", "scripts/nonparametric_tests.py",
                                         "python scripts/nonparametric_tests.py", "ตาราง panels (panel_global)", comment=True)) + "\n")
        table.to_csv(sink, index=False)
    comparison = pooled(frame)
    lines = report(table, comparison, args.boot, args.shifts)
    (OUT_DIR / "nonparametric_tests.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(lines[:40]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
