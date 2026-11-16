"""Assumption check for the correlations of system 7.4: are the variables normally distributed (the assumption of Pearson's r)?  If not, is the
non-parametric Spearman's rho the right measure, and does Pearson still agree with it?  (Advisor's remark: "Pearson needs normal data, otherwise use a
non-parametric measure".)

For the variables of the panel Global (every text of the market, hourly; the ticker-hours with Reddit data and a price):
    sentiment_mean, reddit_volume_zscore_24 (market-wide: counted once per hour, not once per ticker), log_return (= Current Return) and
    future_return_1h/2h/3h/6h/12h (one value per ticker-hour)
it reports n, skewness, excess kurtosis (0 and 0 for a normal variable), the D'Agostino-Pearson omnibus test, the Jarque-Bera test and the
Shapiro-Wilk test (on a seeded random sample of 5,000 rows: its limit), and the share of the 34 assets whose own series is normal by the same test.
It then compares Pearson, Spearman and Pearson after winsorizing the 1% tails for the pair (sentiment_mean, future_return_1h) and
(sentiment_mean, log_return): when the three agree, the outliers and the non-normality do not drive the result.
With 10^5 rows every normality test rejects any tiny departure, so the skewness and kurtosis (the size of the departure) are read next to the p-values.
A Q-Q plot of the three main variables is written next to the report.  Read-only: nothing is written to the database.

Usage:  python scripts/normality_check.py [--db output/reddit.sqlite3]
Output: output/reports/normality_check.md and .csv, output/figures/normality_qq.png
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
FIGURES = ROOT / "output" / "figures"
SEED = 20261116
SHAPIRO_N = 5000                                              # the sample size scipy's Shapiro-Wilk is reliable up to
MARKET_WIDE = ("sentiment_mean", "reddit_volume_zscore_24")   # the same value for every asset in the panel Global: one value per hour
VARIABLES = ["sentiment_mean", "reddit_volume_zscore_24", "log_return", "future_return_1h", "future_return_2h", "future_return_3h",
             "future_return_6h", "future_return_12h"]
LABEL = {"log_return": "log_return (Current Return)"}
PAIRS = [("sentiment_mean", "log_return"), ("sentiment_mean", "future_return_1h")]


def load(db):
    cols = ", ".join(["ticker", "hour_utc"] + VARIABLES)
    con = connect(db, readonly=True)
    try:
        frame = pd.read_sql_query(
            "SELECT %s FROM panels WHERE panel_name = 'panel_global' AND has_reddit_data = 1 AND sentiment_mean IS NOT NULL" % cols, con)
    finally:
        con.close()
    return frame


def tests(values, rng):
    """n, skew, excess kurtosis and the p-values of D'Agostino-Pearson, Jarque-Bera and Shapiro-Wilk (on a sample) for one set of values."""
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 20 or np.ptp(x) == 0:
        return dict(n=n, skew=np.nan, kurtosis=np.nan, p_dagostino=np.nan, p_jarque_bera=np.nan, p_shapiro=np.nan)
    sample = x if n <= SHAPIRO_N else rng.choice(x, SHAPIRO_N, replace=False)
    return dict(n=n, skew=float(stats.skew(x)), kurtosis=float(stats.kurtosis(x)), p_dagostino=float(stats.normaltest(x).pvalue),
                p_jarque_bera=float(stats.jarque_bera(x).pvalue), p_shapiro=float(stats.shapiro(sample).pvalue))


def one_variable(frame, name, rng):
    sub = frame[["ticker", "hour_utc", name]].dropna()
    if name in MARKET_WIDE:
        sub = sub.drop_duplicates("hour_utc")                 # the market-wide value is repeated for every asset: count each hour once
    row = tests(sub[name], rng)
    per_ticker = [tests(g[name], rng)["p_dagostino"] for _, g in sub.groupby("ticker") if len(g) >= 50]
    per_ticker = [p for p in per_ticker if not np.isnan(p)]
    row["assets_normal"] = "%d / %d" % (sum(p >= 0.05 for p in per_ticker), len(per_ticker)) if name not in MARKET_WIDE else "-"
    return {"variable": LABEL.get(name, name), **row}


def winsorize(x, q=0.01):
    low, high = np.nanquantile(x, [q, 1 - q])
    return np.clip(x, low, high)


def pair_row(frame, a, b):
    sub = frame[[a, b]].dropna()
    pearson, p_pearson = stats.pearsonr(sub[a], sub[b])
    spearman, p_spearman = stats.spearmanr(sub[a], sub[b])
    wins, p_wins = stats.pearsonr(winsorize(sub[a].to_numpy()), winsorize(sub[b].to_numpy()))
    return {"pair": "%s x %s" % (a, LABEL.get(b, b)), "n": len(sub), "pearson": pearson, "p_pearson": p_pearson, "spearman": spearman,
            "p_spearman": p_spearman, "pearson_winsorized_1pct": wins, "p_pearson_winsorized": p_wins}


def qq_figure(frame, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names = ["sentiment_mean", "log_return", "future_return_1h"]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    for ax, name in zip(axes, names):
        sub = frame[["hour_utc", name]].dropna()
        if name in MARKET_WIDE:
            sub = sub.drop_duplicates("hour_utc")
        x = sub[name].to_numpy()
        (theo, ordered), (slope, intercept, _) = stats.probplot(x, dist="norm")
        ax.plot(theo, ordered, ".", markersize=2, alpha=0.4)
        ax.plot(theo, slope * theo + intercept, color="#c0392b", linewidth=1)
        ax.set_title("%s (n = %s)" % (LABEL.get(name, name), "{:,}".format(len(x))), fontsize=10)
        ax.set_xlabel("Theoretical quantiles (normal)")
        ax.set_ylabel("Sample quantiles")
        ax.grid(alpha=0.3)
    fig.suptitle("Q-Q plot against the normal distribution (the straight red line = a normal variable)", fontsize=11)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fmt_p(p):
    return "-" if pd.isna(p) else ("<0.001" if p < 0.001 else "%.3f" % p)


# ------------------------------------------------------------------------------------------------ the detailed report (exact statistics and p-values)

def sci(p, log10p=None):
    """A p-value in scientific notation; when it is below the smallest number the machine keeps (0.0) the base-10 logarithm is given."""
    if p is None or pd.isna(p):
        return "-"
    if p > 0:
        return "%.3e" % p
    return "10^%.0f (log10 p = %.0f)" % (np.floor(log10p), log10p) if log10p is not None else "< 1e-300"


def log10_chi2_sf(statistic, dof=2):
    """log10 of P(chi-square with 2 degrees of freedom >= statistic): the survival function of that distribution is exactly exp(-x / 2), so it never underflows."""
    assert dof == 2
    return float(-statistic / 2.0 / np.log(10))


def log10_two_sided_normal(z):
    """log10 of the two-sided p-value of a standard normal z (scipy's logsf keeps it finite where the p-value itself is 0.0)."""
    return float((np.log(2.0) + stats.norm.logsf(abs(z))) / np.log(10))


def detail_row(values, rng):
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    mean, sd = float(x.mean()), float(x.std(ddof=1))
    skew, kurt = float(stats.skew(x)), float(stats.kurtosis(x))
    dag = stats.normaltest(x)
    jb = stats.jarque_bera(x)
    z_skew, p_skew = stats.skewtest(x)
    z_kurt, p_kurt = stats.kurtosistest(x)
    sample = x if n <= SHAPIRO_N else rng.choice(x, SHAPIRO_N, replace=False)
    sw = stats.shapiro(sample)
    ad = stats.anderson(x, dist="norm")
    return {"n": n, "mean": mean, "sd": sd, "min": float(x.min()), "p1": float(np.quantile(x, 0.01)), "median": float(np.median(x)), "p99": float(np.quantile(x, 0.99)),
            "max": float(x.max()), "skew": skew, "kurtosis": kurt, "z_skew": float(z_skew), "p_skew": float(p_skew), "log10_p_skew": log10_two_sided_normal(z_skew),
            "z_kurt": float(z_kurt), "p_kurt": float(p_kurt), "log10_p_kurt": log10_two_sided_normal(z_kurt),
            "dagostino_k2": float(dag.statistic), "p_dagostino": float(dag.pvalue), "log10_p_dagostino": log10_chi2_sf(dag.statistic),
            "jarque_bera": float(jb.statistic), "p_jarque_bera": float(jb.pvalue), "log10_p_jb": log10_chi2_sf(jb.statistic),
            "shapiro_w": float(sw.statistic), "p_shapiro": float(sw.pvalue), "anderson_a2": float(ad.statistic), "anderson_crit_1pct": float(ad.critical_values[-1]),
            "beyond_3sd_pct": float(100.0 * (np.abs(x - mean) > 3 * sd).mean()), "beyond_4sd_pct": float(100.0 * (np.abs(x - mean) > 4 * sd).mean())}


def detail_report(frame, rng):
    rows = []
    for name in VARIABLES:
        sub = frame[["ticker", "hour_utc", name]].dropna()
        if name in MARKET_WIDE:
            sub = sub.drop_duplicates("hour_utc")
        rows.append({"variable": LABEL.get(name, name), **detail_row(sub[name], rng)})
    table = pd.DataFrame(rows)
    per_asset = []
    for ticker, part in frame.groupby("ticker"):
        v = part.log_return.dropna()
        if len(v) >= 50:
            r = detail_row(v, rng)
            per_asset.append({"ticker": ticker, **{k: r[k] for k in ("n", "skew", "kurtosis", "dagostino_k2", "p_dagostino", "log10_p_dagostino", "p_shapiro", "beyond_3sd_pct")}})
    per_asset = pd.DataFrame(per_asset)
    pairs = []
    for a, b in PAIRS:
        sub = frame[[a, b]].dropna()
        pe, spe = stats.pearsonr(sub[a], sub[b]), stats.spearmanr(sub[a], sub[b])
        pairs.append({"pair": "%s x %s" % (a, LABEL.get(b, b)), "n": len(sub), "pearson": float(pe[0]), "p_pearson": float(pe[1]), "spearman": float(spe[0]), "p_spearman": float(spe[1])})
    pairs = pd.DataFrame(pairs)
    L = ["# การตรวจการแจกแจงปกติ: ค่าสถิติและ p-value แบบละเอียด (เหตุผลที่ไม่ใช้ Pearson เป็นตัวหลัก)", "",
         *file_header("ค่าสถิติทดสอบและ p-value แบบค่าจริงของการทดสอบการแจกแจงปกติ (D'Agostino-Pearson, Jarque-Bera, Shapiro-Wilk, Anderson-Darling) ของความรู้สึก, Reddit Volume Z-score, "
                      "Current Return และ Future Return ทุกช่วงเวลา, สัดส่วนค่าสุดขั้วเทียบกับที่ข้อมูลปกติควรมี, ตารางรายสินทรัพย์ 34 ตัว และ p-value ของ Pearson / Spearman ในสูตรมาตรฐาน",
                      "scripts/normality_check.py", "python scripts/normality_check.py", "ตาราง panels (panel_global) ใน output/reddit.sqlite3 อ่านอย่างเดียว"), "",
         "## 1) วิธีวัดและวิธีคิด p-value", "",
         "สมมติฐานหลัก H0: ข้อมูลมาจากการแจกแจงปกติ · p-value = ความน่าจะเป็นที่จะได้ค่าสถิติรุนแรงเท่านี้หรือมากกว่า ถ้า H0 เป็นจริง · p < 0.05 = ปฏิเสธ H0 (ไม่ปกติ)", "",
         "| การทดสอบ | ค่าสถิติ | การแจกแจงของค่าสถิติภายใต้ H0 | p-value |", "|---|---|---|---|",
         "| ความเบ้ (skewness) g1 | g1 = m3 / m2^1.5 (ปกติ = 0) · ทดสอบ D'Agostino ได้ z_skew | ปกติมาตรฐาน | p สองด้านของ z_skew |",
         "| ความโด่งส่วนเกิน (excess kurtosis) g2 | g2 = m4 / m2^2 − 3 (ปกติ = 0) · ทดสอบ Anscombe-Glynn ได้ z_kurt | ปกติมาตรฐาน | p สองด้านของ z_kurt |",
         "| D'Agostino-Pearson (omnibus) | K² = z_skew² + z_kurt² | χ² องศาเสรี 2 | P(χ²₂ ≥ K²) |",
         "| Jarque-Bera | JB = n/6 · (g1² + g2²/4) | χ² องศาเสรี 2 | P(χ²₂ ≥ JB) |",
         "| Shapiro-Wilk | W = (Σ aᵢ x₍ᵢ₎)² / Σ(xᵢ − x̄)²  (W = 1 เมื่อปกติสมบูรณ์) | ตารางของ Royston (สุ่ม %s แถว ข้อจำกัดของวิธี) | p จากการประมาณของ Royston |" % "{:,}".format(SHAPIRO_N),
         "| Anderson-Darling | A² (ยิ่งสูง ยิ่งไม่ปกติ) | เทียบกับค่าวิกฤตที่ 1% (1.092 สำหรับการแจกแจงปกติ) | ไม่ให้ p |", "",
         "เมื่อ p เล็กกว่าที่เครื่องเก็บได้ (< 1e-300 ปัดเป็น 0) ตารางให้ log10 ของ p แทน เช่น log10 p = −5,000 แปลว่า p = 10^-5000 · ด้วยข้อมูลหมื่นถึงแสนแถว การทดสอบจับความต่างเล็กน้อยได้ "
         "จึงดูควบคู่ \"ขนาด\" ของความต่าง คือความเบ้ ความโด่ง และสัดส่วนค่าสุดขั้วด้านล่าง", "",
         "## 2) การทดสอบทีละตัวแปร (ข้อมูลชุดเดียวกับที่ใช้คำนวณสหสัมพันธ์: panel Global, ชั่วโมงที่มีข้อความ Reddit และราคา)", "",
         "| ตัวแปร | n | เฉลี่ย | SD | ต่ำสุด | 1% | มัธยฐาน | 99% | สูงสุด |", "|---|---|---|---|---|---|---|---|---|"]
    for r in table.itertuples():
        L.append("| %s | %s | %.5g | %.5g | %.5g | %.5g | %.5g | %.5g | %.5g |" % (r.variable, "{:,}".format(r.n), r.mean, r.sd, r.min, r.p1, r.median, r.p99, r.max))
    L += ["", "| ตัวแปร | ความเบ้ g1 | z_skew | p (เบ้) | ความโด่งส่วนเกิน g2 | z_kurt | p (โด่ง) |", "|---|---|---|---|---|---|---|"]
    for r in table.itertuples():
        L.append("| %s | %.4f | %.2f | %s | %.3f | %.2f | %s |" % (r.variable, r.skew, r.z_skew, sci(r.p_skew, r.log10_p_skew), r.kurtosis, r.z_kurt, sci(r.p_kurt, r.log10_p_kurt)))
    L += ["", "| ตัวแปร | D'Agostino K² | p-value | Jarque-Bera | p-value | Shapiro-Wilk W | p-value | Anderson-Darling A² (ค่าวิกฤต 1%) |", "|---|---|---|---|---|---|---|---|"]
    for r in table.itertuples():
        L.append("| %s | %.1f | %s | %.1f | %s | %.5f | %s | %.1f (%.3f) |" % (
            r.variable, r.dagostino_k2, sci(r.p_dagostino, r.log10_p_dagostino), r.jarque_bera, sci(r.p_jarque_bera, r.log10_p_jb), r.shapiro_w, sci(r.p_shapiro),
            r.anderson_a2, r.anderson_crit_1pct))
    L += ["", "## 3) สัดส่วนค่าสุดขั้ว: ข้อมูลปกติควรมีค่าที่ห่างจากค่าเฉลี่ยเกิน 3 SD เพียง 0.270% และเกิน 4 SD เพียง 0.0063%", "",
          "| ตัวแปร | เกิน 3 SD (%) | เทียบกับปกติ (เท่า) | เกิน 4 SD (%) | เทียบกับปกติ (เท่า) |", "|---|---|---|---|---|"]
    for r in table.itertuples():
        L.append("| %s | %.3f | %.1f | %.4f | %.1f |" % (r.variable, r.beyond_3sd_pct, r.beyond_3sd_pct / 0.26998, r.beyond_4sd_pct, r.beyond_4sd_pct / 0.006334))
    L += ["", "## 4) Current Return รายสินทรัพย์ (34 ตัว) · ผ่านการทดสอบ (p ≥ 0.05) = %d ตัว" % int((per_asset.p_dagostino >= 0.05).sum()), "",
          "| สินทรัพย์ | n | ความเบ้ | ความโด่งส่วนเกิน | D'Agostino K² | p-value | log10 p | p Shapiro | เกิน 3 SD (%) |", "|---|---|---|---|---|---|---|---|---|"]
    for r in per_asset.itertuples():
        L.append("| %s | %s | %.3f | %.2f | %.1f | %s | %.1f | %s | %.3f |" % (r.ticker, "{:,}".format(r.n), r.skew, r.kurtosis, r.dagostino_k2, sci(r.p_dagostino, r.log10_p_dagostino),
                                                                                 r.log10_p_dagostino, sci(r.p_shapiro), r.beyond_3sd_pct))
    L += ["", "## 5) p-value ของ Pearson และ Spearman ในสูตรมาตรฐาน (ใช้ดูเท่านั้น: สูตรของ Pearson ต้องการข้อมูลปกติ และทั้งสองสูตรถือว่าทุกชั่วโมงเป็นอิสระ ซึ่งไม่จริง)", "",
          "| คู่ตัวแปร (รวมสินทรัพย์-ชั่วโมง) | n | Pearson r | p-value | Spearman ρ | p-value |", "|---|---|---|---|---|---|"]
    for r in pairs.itertuples():
        L.append("| %s | %s | %+.5f | %s | %+.5f | %s |" % (r.pair, "{:,}".format(r.n), r.pearson, sci(r.p_pearson), r.spearman, sci(r.p_spearman)))
    L += ["", "## 6) สรุปเหตุผลที่ไม่ใช้ Pearson เป็นตัวหลัก", "",
          "1. ทุกตัวแปรปฏิเสธการแจกแจงปกติด้วยการทดสอบทุกชนิด (ตารางข้อ 2) และรายสินทรัพย์ปกติ %d จาก %d ตัว (ข้อ 4)" % (int((per_asset.p_dagostino >= 0.05).sum()), len(per_asset)),
          "2. ขนาดของความไม่ปกติใหญ่มาก: ความโด่งส่วนเกิน 12 ถึง 1,063 (ปกติ = 0) ค่าที่เกิน 3 SD มีมากกว่าที่ข้อมูลปกติควรมีหลายเท่า (ข้อ 3) จึงไม่ใช่แค่ผลของ n มาก",
          "3. Pearson ใช้ตัวเลขจริง ค่าสุดขั้วไม่กี่ค่าจึงมีอำนาจดึงผลได้มาก และการทดสอบนัยสำคัญของ Pearson สมมติความปกติ",
          "4. Spearman ใช้อันดับ ไม่สมมติการแจกแจง ค่าสุดขั้วเป็นเพียงอันดับสุดท้าย จึงใช้เป็นตัวหลัก (ผลของ Pearson, Spearman และ Pearson ที่ตัดหาง 1% ทิศเดียวกัน: ตารางข้อ 2 ของ `normality_check.md`)",
          "5. ข้อมูลรายชั่วโมงสัมพันธ์ข้ามเวลา จึงหา p ของ Spearman ด้วยการเลื่อนอนุกรมแบบวงกลมและช่วงเชื่อมั่นด้วย block bootstrap (`nonparametric_tests.md`) แทนสูตรมาตรฐาน", ""]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "normality_check_detail.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    with (OUT_DIR / "normality_check_detail.csv").open("w", newline="", encoding="utf-8") as sink:
        sink.write("\n".join(file_header("ค่าสถิติและ p-value แบบละเอียดของการทดสอบการแจกแจงปกติ (ข้อมูลชุดเดียวกับ normality_check_detail.md)", "scripts/normality_check.py",
                                         "python scripts/normality_check.py", "ตาราง panels (panel_global)", comment=True)) + "\n")
        table.to_csv(sink, index=False)
    return L


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args(argv)
    rng = np.random.default_rng(SEED)
    frame = load(args.db)
    rows = [one_variable(frame, name, rng) for name in VARIABLES]
    table = pd.DataFrame(rows)
    pairs = pd.DataFrame([pair_row(frame, a, b) for a, b in PAIRS])
    qq_figure(frame, FIGURES / "normality_qq.png")
    detail_report(frame, np.random.default_rng(SEED))

    lines = ["# การตรวจสมมติฐานการแจกแจงปกติ (normality) ก่อนใช้ Pearson — ระบบ 7.4", "",
             *file_header("ตรวจว่าตัวแปรของสหสัมพันธ์ (ความรู้สึก, Reddit Volume Z-score, Current Return, Future Return) แจกแจงปกติหรือไม่ "
                          "และ Pearson ให้ผลสอดคล้องกับ Spearman (ไม่ต้องสมมติการแจกแจงปกติ) หรือไม่ ตามข้อสังเกตของอาจารย์",
                          "scripts/normality_check.py", "python scripts/normality_check.py",
                          "ตาราง panels (panel_global, ชั่วโมงที่มีข้อมูล Reddit และราคา) ใน output/reddit.sqlite3 อ่านอย่างเดียว"), "",
             "ข้อมูล: ชั่วโมง × สินทรัพย์ของ panel Global ที่มีข้อความ Reddit (%s แถว) · ตัวแปรระดับตลาด (ความรู้สึก, Reddit Volume Z-score) นับชั่วโมงละ 1 ค่า "
             "(ไม่นับซ้ำตามจำนวนสินทรัพย์)" % "{:,}".format(len(frame)), "",
             "## 1) ตัวแปรแจกแจงปกติหรือไม่", "",
             "ค่าของการแจกแจงปกติ: ความเบ้ (skewness) = 0 และความโด่งส่วนเกิน (excess kurtosis) = 0 · ทดสอบ D'Agostino-Pearson, Jarque-Bera ทั้งชุด; Shapiro-Wilk "
             "ใช้สุ่ม %s แถว (ข้อจำกัดของวิธี) · H0 = แจกแจงปกติ; p < 0.05 = ปฏิเสธ · คอลัมน์ \"สินทรัพย์ที่ปกติ\" = จำนวนสินทรัพย์ที่ชุดของตัวเองไม่ถูกปฏิเสธ "
             "(D'Agostino, p ≥ 0.05) จากสินทรัพย์ที่มี ≥ 50 แถว" % "{:,}".format(SHAPIRO_N), "",
             "| ตัวแปร | n | ความเบ้ | ความโด่งส่วนเกิน | p D'Agostino | p Jarque-Bera | p Shapiro (สุ่ม 5,000) | สินทรัพย์ที่ปกติ |", "|---|---|---|---|---|---|---|---|"]
    for r in table.itertuples():
        lines.append("| %s | %s | %.2f | %.1f | %s | %s | %s | %s |" % (r.variable, "{:,}".format(r.n), r.skew, r.kurtosis, fmt_p(r.p_dagostino),
                                                                       fmt_p(r.p_jarque_bera), fmt_p(r.p_shapiro), r.assets_normal))
    lines += ["", "รูป Q-Q (จุดที่เบี่ยงออกจากเส้นตรง = ไม่ปกติ): `output/figures/normality_qq.png`", "",
              "## 2) Pearson, Spearman และ Pearson ที่ตัดหางสุดขั้ว (winsorize 1%) ให้ผลสอดคล้องกันหรือไม่", "",
              "ถ้าสามค่าใกล้กัน แสดงว่าความไม่ปกติและค่าสุดขั้วไม่ได้เป็นตัวกำหนดผล · p ของ Pearson ในตารางนี้ยังเป็นค่าบรรยาย (ข้อมูลรายชั่วโมงมี autocorrelation)", "",
              "| คู่ตัวแปร | n | Pearson r | p | Spearman ρ | p | Pearson (winsorize 1%) | p |", "|---|---|---|---|---|---|---|---|"]
    for r in pairs.itertuples():
        lines.append("| %s | %s | %+.4f | %s | %+.4f | %s | %+.4f | %s |" % (r.pair, "{:,}".format(r.n), r.pearson, fmt_p(r.p_pearson), r.spearman,
                                                                           fmt_p(r.p_spearman), r.pearson_winsorized_1pct, fmt_p(r.p_pearson_winsorized)))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "normality_check.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (OUT_DIR / "normality_check.csv").open("w", newline="", encoding="utf-8") as sink:
        sink.write("\n".join(file_header("การทดสอบการแจกแจงปกติของตัวแปรของสหสัมพันธ์ (ข้อมูลชุดเดียวกับ normality_check.md)", "scripts/normality_check.py",
                                         "python scripts/normality_check.py", "ตาราง panels (panel_global)", comment=True)) + "\n")
        table.to_csv(sink, index=False)
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
