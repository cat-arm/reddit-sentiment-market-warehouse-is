"""Checks behind the use of Spearman's rho for "does the price go up when the Reddit sentiment goes up, and down when it goes down?" (EXTENSION of system 7.4).

Spearman needs no normal data (scripts/normality_check.py shows there is none) but it does need: (2) a monotonic relation, (3) not too many tied values, (4) independent
observations, (5) stationary series.  This script checks them with the sentiment of every text of the market (VADER+FinBERT, panel Global, hourly) and the hourly log
return (Current Return) of the 34 assets, in four groups: index futures (ES=F, NQ=F, RTY=F), commodity futures (CL=F, GC=F, NG=F), crypto (6) and stocks / ETFs (22).

  A. The question itself, per group (rows pooled over the assets of the group, the days resampled as blocks for the 95% intervals):
       A1 deciles of the sentiment of the hour -> mean return of the same hour, top decile minus bottom decile, Spearman of the decile order with its mean (monotonic?);
       A2 the relation in the half of the hours with the higher sentiment and in the half with the lower one (up -> up AND down -> down?);
       A3 the change of the sentiment from the previous hour against the return of the hour and of the next hour;
       A4 who leads whom: sentiment(t) against the return of hour t+k for k = -12 ... +12 (k < 0: the return came first).
  B. Ties: the share of rows whose value is shared with another row, and of the returns that are exactly 0.
  C. Autocorrelation at lag 1 / 6 / 24 and the Ljung-Box test (24 lags): the reason for the block bootstrap and the circular-shift p-value of scripts/nonparametric_tests.py.
  D. Stationarity: Augmented Dickey-Fuller (H0: unit root; 12 lags, constant) and KPSS (H0: stationary; level) written here with numpy (no dependency; statsmodels, if installed, is used only to check them);
       the statistics are compared with the standard critical values and checked against statsmodels when it is installed.
  E. Stability: Spearman per calendar month (the share of months with a positive sign) and with the 1% most extreme returns of each asset removed.
Read-only: nothing is written to the database.  Caveats: the sentiment of the market is one value per hour, shared by every asset; the rows of an asset are the hours with
a price (gaps at night for stocks); the p-values and intervals are descriptive.

Usage:  python scripts/spearman_assumptions_check.py [--db output/reddit.sqlite3] [--boot 300]
Output: output/reports/spearman_assumptions_check.md and .csv, output/figures/spearman_deciles.png, output/figures/spearman_leadlag.png
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dashboard import data                                    # noqa: E402
from etl.common import DEFAULT_DB, file_header                # noqa: E402
from scripts import nonparametric_tests as npt                # noqa: E402

OUT_DIR = ROOT / "output" / "reports"
FIGURES = ROOT / "output" / "figures"
SEED = 20261116
INDEX_FUTURES = ("ES=F", "NQ=F", "RTY=F")
LAGS = (-12, -6, -3, -2, -1, 0, 1, 2, 3, 6, 12)
GROUP_ORDER = ["ฟิวเจอร์สดัชนี", "คริปโต", "หุ้นและ ETF", "ฟิวเจอร์สสินค้าโภคภัณฑ์"]
ADF_CRITICAL = {"1%": -3.43, "5%": -2.86, "10%": -2.57}       # MacKinnon, constant, large sample
KPSS_CRITICAL = {"10%": 0.347, "5%": 0.463, "1%": 0.739}      # Kwiatkowski et al., level stationarity


def group_of(ticker, klass):
    if ticker in INDEX_FUTURES:
        return GROUP_ORDER[0]
    if klass == "crypto":
        return GROUP_ORDER[1]
    if klass == "stock_etf":
        return GROUP_ORDER[2]
    return GROUP_ORDER[3]


def load(db):
    info = data.data_range(db)
    start, end = int(info["reddit_lo"]), int(info["reddit_hi"])
    communities = tuple(dict.fromkeys(data.sources(db).subreddit))
    sent = data.global_hourly(db, start, end, communities, "VADER+FinBERT", "all", ("Post", "Comment"))
    senti = data.sentiment_frame(sent, start, end)[["hour_utc", "sentiment_mean"]].dropna().sort_values("hour_utc").reset_index(drop=True)
    uni = data.tickers(db)
    prices = data.price_series_for(db, tuple(uni.ticker), start, end)[["ticker", "hour_utc", "log_return"]].dropna()
    klass = dict(zip(uni.ticker, uni.big_group))
    prices["group"] = [group_of(t, klass[t]) for t in prices.ticker]
    return senti, prices


# ---------------------------------------------------------------------------------------------------------- statistics

def rank_corr(x, y):
    return npt.corr(stats.rankdata(x), stats.rankdata(y))


def day_blocks(hours_sorted):
    days = (np.asarray(hours_sorted) // 86400).astype(int)
    _, first, counts = np.unique(days, return_index=True, return_counts=True)
    return first, counts


def boot_ci(stat, hours_sorted, rng, boot, *arrays):
    """95% interval of stat(*arrays) with the UTC days of `hours_sorted` resampled as blocks (arrays sorted by hour)."""
    first, counts = day_blocks(hours_sorted)
    values = []
    for _ in range(boot):
        idx = npt.block_indices(first, counts, rng)
        values.append(stat(*[a[idx] for a in arrays]))
    values = np.asarray(values, dtype=float)
    return tuple(np.nanpercentile(values, [2.5, 97.5]))


def lag_corr(x, k):
    """Correlation of x(t) with x(t-k) over the pairs that are exactly k steps apart (x: Series on an integer hour grid)."""
    a, b = x.to_numpy(float), x.shift(k).to_numpy(float)
    ok = ~(np.isnan(a) | np.isnan(b))
    return npt.corr(a[ok], b[ok]) if ok.sum() > 10 else np.nan


def ljung_box(x, lags=24):
    r = [lag_corr(x, k) for k in range(1, lags + 1)]
    n = int(x.notna().sum())
    q = n * (n + 2) * sum(rk ** 2 / (n - k) for k, rk in enumerate(r, 1) if not np.isnan(rk))
    return float(q), float(stats.chi2.sf(q, lags))


def adf(y, lags=12):
    """Augmented Dickey-Fuller t statistic (constant, `lags` lagged differences): H0 unit root; compare with ADF_CRITICAL (more negative = stationary)."""
    y = np.asarray(y, dtype=float)
    dy = np.diff(y)
    rows = len(dy) - lags
    columns = [y[lags:-1], np.ones(rows)] + [dy[lags - i:len(dy) - i] for i in range(1, lags + 1)]
    design, target = np.column_stack(columns), dy[lags:]
    beta, *_ = np.linalg.lstsq(design, target, rcond=None)
    resid = target - design @ beta
    sigma2 = resid @ resid / (rows - design.shape[1])
    cov = sigma2 * np.linalg.inv(design.T @ design)
    return float(beta[0] / np.sqrt(cov[0, 0]))


def kpss_stat(y):
    """KPSS statistic for level stationarity (Bartlett kernel): H0 stationary; compare with KPSS_CRITICAL (larger = not stationary)."""
    y = np.asarray(y, dtype=float)
    n = len(y)
    e = y - y.mean()
    s = np.cumsum(e)
    bandwidth = int(12 * (n / 100) ** 0.25)
    lrv = e @ e / n
    for lag in range(1, min(bandwidth, n - 1) + 1):
        lrv += 2 * (1 - lag / (bandwidth + 1)) * (e[lag:] @ e[:-lag]) / n
    return float((s @ s) / (n ** 2 * lrv))


def ties(values):
    v = pd.Series(np.asarray(values, dtype=float))
    return float(v.duplicated(keep=False).mean())


# ---------------------------------------------------------------------------------------------------------- the checks

def pooled_rows(senti, prices, group):
    """Hour x asset rows of one group with the sentiment of the hour (sorted by hour)."""
    return prices[prices.group == group].merge(senti, on="hour_utc", how="inner").sort_values("hour_utc").reset_index(drop=True)


def decile_check(rows, senti, rng, boot):
    edges = np.unique(np.quantile(senti.sentiment_mean, np.linspace(0, 1, 11)))
    dec = np.clip(np.searchsorted(edges, rows.sentiment_mean.to_numpy(), side="right") - 1, 0, len(edges) - 2)
    y, hours = rows.log_return.to_numpy(float), rows.hour_utc.to_numpy()
    k = len(edges) - 1

    def means(d, v):
        return np.bincount(d, weights=v, minlength=k) / np.maximum(np.bincount(d, minlength=k), 1)

    base = means(dec, y)
    first, counts = day_blocks(hours)
    rng_local = np.random.default_rng(rng.integers(1 << 31))
    boots, diffs, trends = [], [], []
    for _ in range(boot):
        idx = npt.block_indices(first, counts, rng_local)
        m = means(dec[idx], y[idx])
        boots.append(m)
        diffs.append(m[-1] - m[0])
        trends.append(stats.spearmanr(np.arange(k), m)[0])
    boots = np.asarray(boots)
    low, high = np.nanpercentile(boots, [2.5, 97.5], axis=0)
    return {"means": base, "low": low, "high": high, "diff": float(base[-1] - base[0]), "diff_ci": tuple(np.nanpercentile(diffs, [2.5, 97.5])),
            "trend": float(stats.spearmanr(np.arange(k), base)[0]), "trend_ci": tuple(np.nanpercentile(trends, [2.5, 97.5])),
            "u_shape": float((base[0] + base[-1]) / 2 - base[3:7].mean()), "counts": np.bincount(dec, minlength=k)}


def half_check(rows, senti, rng, boot):
    cut = senti.sentiment_mean.median()
    out = {}
    for name, part in (("ความรู้สึกสูง (เหนือมัธยฐาน)", rows[rows.sentiment_mean > cut]), ("ความรู้สึกต่ำ (ใต้มัธยฐาน)", rows[rows.sentiment_mean <= cut])):
        x, y = part.sentiment_mean.to_numpy(float), part.log_return.to_numpy(float)
        low, high = boot_ci(rank_corr, part.hour_utc.to_numpy(), rng, boot, x, y)
        out[name] = (len(part), rank_corr(x, y), low, high)
    return out


def change_check(senti, prices, group, rng, boot):
    s = senti.set_index("hour_utc").sentiment_mean
    prev = s.reindex(s.index - 3600)
    delta = pd.DataFrame({"hour_utc": s.index, "delta": s.to_numpy() - prev.to_numpy()}).dropna()
    rows = prices[prices.group == group][["ticker", "hour_utc", "log_return"]].merge(delta, on="hour_utc").sort_values("hour_utc").reset_index(drop=True)
    nxt = prices[["ticker", "hour_utc", "log_return"]].assign(hour_utc=lambda d: d.hour_utc - 3600).rename(columns={"log_return": "next_return"})
    rows = rows.merge(nxt, on=["ticker", "hour_utc"], how="left")
    out = {}
    for name, col in (("ผลตอบแทนชั่วโมงเดียวกัน", "log_return"), ("ผลตอบแทนชั่วโมงถัดไป", "next_return")):
        part = rows.dropna(subset=[col])
        low, high = boot_ci(rank_corr, part.hour_utc.to_numpy(), rng, boot, part.delta.to_numpy(float), part[col].to_numpy(float))
        out[name] = (len(part), rank_corr(part.delta.to_numpy(float), part[col].to_numpy(float)), low, high)
    return out


def leadlag_check(senti, prices, group, rng, boot):
    g = prices[prices.group == group][["ticker", "hour_utc", "log_return"]]
    out = {}
    for k in LAGS:
        shifted = g.assign(hour_utc=g.hour_utc - 3600 * k)                 # the return of hour t+k is placed on hour t
        rows = shifted.merge(senti, on="hour_utc").sort_values("hour_utc")
        x, y = rows.sentiment_mean.to_numpy(float), rows.log_return.to_numpy(float)
        low, high = boot_ci(rank_corr, rows.hour_utc.to_numpy(), rng, max(boot // 2, 100), x, y)
        out[k] = (len(rows), rank_corr(x, y), low, high)
    return out


def figures(deciles, leadlag):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 4, figsize=(16, 3.8), sharey=False)
    for ax, group in zip(axes, GROUP_ORDER):
        d = deciles[group]
        xs = np.arange(1, len(d["means"]) + 1)
        ax.bar(xs, d["means"], color="#4c78a8")
        ax.errorbar(xs, d["means"], yerr=[d["means"] - d["low"], d["high"] - d["means"]], fmt="none", ecolor="#333333", capsize=2, linewidth=1)
        ax.axhline(0, color="#555555", linewidth=0.8)
        ax.set_title("%s\nสูงสุด − ต่ำสุด = %+.3f%%" % (group, d["diff"]), fontsize=9)
        ax.set_xlabel("กลุ่มความรู้สึก (1 = ต่ำสุด, 10 = สูงสุด)", fontsize=8)
        ax.set_ylabel("ผลตอบแทนเฉลี่ยของชั่วโมงเดียวกัน (%)", fontsize=8)
        ax.set_xticks(xs)
        ax.tick_params(labelsize=7)
    fig.tight_layout()
    fig.savefig(FIGURES / "spearman_deciles.png", dpi=150)
    plt.close(fig)
    fig, axes = plt.subplots(1, 4, figsize=(16, 3.8), sharey=True)
    for ax, group in zip(axes, GROUP_ORDER):
        ll = leadlag[group]
        ks = list(ll)
        rho = np.array([ll[k][1] for k in ks])
        lo = np.array([ll[k][2] for k in ks])
        hi = np.array([ll[k][3] for k in ks])
        ax.plot(ks, rho, marker="o", color="#4c78a8")
        ax.fill_between(ks, lo, hi, color="#4c78a8", alpha=0.2)
        ax.axhline(0, color="#555555", linewidth=0.8)
        ax.axvline(0, color="#999999", linewidth=0.8, linestyle="--")
        ax.set_title(group, fontsize=9)
        ax.set_xlabel("k (ชั่วโมง)  k > 0: ความรู้สึกมาก่อนราคา, k < 0: ราคามาก่อน", fontsize=7)
        ax.tick_params(labelsize=7)
    axes[0].set_ylabel("Spearman ρ ของความรู้สึก(t) กับผลตอบแทน(t+k)", fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES / "spearman_leadlag.png", dpi=150)
    plt.close(fig)


def monthly_and_trim(rows, prices_group):
    months = pd.to_datetime(rows.hour_utc, unit="s", utc=True).dt.strftime("%Y-%m")
    rho = []
    for _, part in rows.groupby(months):
        if len(part) >= 100:
            rho.append(rank_corr(part.sentiment_mean.to_numpy(float), part.log_return.to_numpy(float)))
    rho = np.array(rho)
    trimmed = rows[rows.groupby("ticker").log_return.transform(lambda s: s.abs() <= s.abs().quantile(0.99))]
    return {"months": len(rho), "positive": int((rho > 0).sum()), "median": float(np.median(rho)) if len(rho) else np.nan,
            "full": rank_corr(rows.sentiment_mean.to_numpy(float), rows.log_return.to_numpy(float)),
            "trimmed": rank_corr(trimmed.sentiment_mean.to_numpy(float), trimmed.log_return.to_numpy(float)), "n_trimmed": len(trimmed)}


def series_checks(senti, prices):
    """Ties, autocorrelation and stationarity of the sentiment (market level) and of the return of every asset."""
    grid = pd.Series(senti.sentiment_mean.to_numpy(), index=(senti.hour_utc // 3600).to_numpy())
    grid = grid.reindex(range(int(grid.index.min()), int(grid.index.max()) + 1))
    rows = [{"series": "ความรู้สึกของตลาด", "group": "-", "n": int(grid.notna().sum()), "ties_share": ties(senti.sentiment_mean), "zero_share": np.nan,
             "acf1": lag_corr(grid, 1), "acf6": lag_corr(grid, 6), "acf24": lag_corr(grid, 24), "lb_p": ljung_box(grid)[1],
             "adf": adf(senti.sentiment_mean), "kpss": kpss_stat(senti.sentiment_mean)}]
    for ticker, part in prices.groupby("ticker"):
        part = part.sort_values("hour_utc")
        g = pd.Series(part.log_return.to_numpy(), index=(part.hour_utc // 3600).to_numpy())
        g = g[~g.index.duplicated()]
        g = g.reindex(range(int(g.index.min()), int(g.index.max()) + 1))
        rows.append({"series": ticker, "group": part.group.iloc[0], "n": int(g.notna().sum()), "ties_share": ties(part.log_return), "zero_share": float((part.log_return == 0).mean()),
                     "acf1": lag_corr(g, 1), "acf6": lag_corr(g, 6), "acf24": lag_corr(g, 24), "lb_p": ljung_box(g)[1], "adf": adf(part.log_return), "kpss": kpss_stat(part.log_return)})
    return pd.DataFrame(rows)


def fmt_acf(v):
    return "-" if pd.isna(v) else "%+.3f" % v


def crosscheck(senti, prices):
    """ADF and KPSS written here against statsmodels (when it is installed) on the sentiment and three assets: the largest difference of the statistics."""
    try:
        from statsmodels.tsa.stattools import adfuller, kpss
    except ImportError:
        return "ไม่ได้ตรวจทานกับ statsmodels (ไม่ได้ติดตั้ง)"
    worst = 0.0
    series = [senti.sentiment_mean.to_numpy(float)] + [prices[prices.ticker == t].sort_values("hour_utc").log_return.to_numpy(float) for t in ("ES=F", "BTC-USD", "AAPL")]
    for v in series:
        bandwidth = int(12 * (len(v) / 100) ** 0.25)
        worst = max(worst, abs(adf(v) - adfuller(v, maxlag=12, regression="c", autolag=None)[0]), abs(kpss_stat(v) - kpss(v, regression="c", nlags=bandwidth)[0]))
    return "ตรวจทานกับ statsmodels (ความรู้สึก, ES=F, BTC-USD, AAPL): ค่าสถิติ ADF และ KPSS ต่างกันมากสุด %.1e" % worst


def fmt_p(p):
    return "-" if pd.isna(p) else ("<0.001" if p < 0.001 else "%.3f" % p)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--boot", type=int, default=300)
    args = parser.parse_args(argv)
    rng = np.random.default_rng(SEED)
    senti, prices = load(args.db)
    table = series_checks(senti, prices)
    deciles, halves, changes, leadlags, stability = {}, {}, {}, {}, {}
    for group in GROUP_ORDER:
        rows = pooled_rows(senti, prices, group)
        deciles[group] = decile_check(rows, senti, rng, args.boot)
        halves[group] = half_check(rows, senti, rng, args.boot)
        changes[group] = change_check(senti, prices, group, rng, args.boot)
        leadlags[group] = leadlag_check(senti, prices, group, rng, args.boot)
        stability[group] = monthly_and_trim(rows, prices)
        print("done", group, flush=True)
    figures(deciles, leadlags)

    returns = table[table.group != "-"]
    sent = table[table.group == "-"].iloc[0]
    lines = ["# การตรวจสมมติฐานของ Spearman และตอบคำถาม \"sentiment ขึ้น ราคาขึ้นไหม / sentiment ลง ราคาลงไหม\" — ระบบ 7.4 (ส่วนขยาย)", "",
             *file_header("ผลตรวจสมมติฐาน 4 ข้อของ Spearman (monotonic, ค่าซ้ำ, autocorrelation, stationarity) และการวิเคราะห์ทิศทาง (ขึ้น-ขึ้น/ลง-ลง, การเปลี่ยนแปลง, ใครนำใคร, ความเสถียร) ของความรู้สึก Reddit เทียบผลตอบแทน แยก 4 กลุ่มสินทรัพย์",
                          "scripts/spearman_assumptions_check.py", "python scripts/spearman_assumptions_check.py --boot %d" % args.boot,
                          "reddit_hourly_global + market_hourly_features ใน output/reddit.sqlite3 อ่านอย่างเดียว"), "",
             "ความรู้สึก = คะแนนเฉลี่ยของทุกข้อความของตลาด (VADER+FinBERT, panel Global) ในชั่วโมงนั้น · ผลตอบแทน = Current Return (log return ชั่วโมงเดียวกัน) · "
             "กลุ่มรวมแถว ชั่วโมง × สินทรัพย์ · ช่วงเชื่อมั่น 95%% จาก block bootstrap รายวัน UTC (%d รอบ) · ตัวแปรเดียวกับ `normality_check.md` และ `nonparametric_tests.md`" % args.boot, "",
             "## A1) ความรู้สึกสูง → ผลตอบแทนสูงไหม (แบ่งความรู้สึกเป็น 10 กลุ่มเท่า ๆ กัน ดูผลตอบแทนเฉลี่ยของแต่ละกลุ่ม)", "",
             "กลุ่ม 1 = ความรู้สึกต่ำสุด 10% ของชั่วโมง, กลุ่ม 10 = สูงสุด 10% · \"สูงสุด − ต่ำสุด\" = ผลตอบแทนเฉลี่ยกลุ่ม 10 ลบกลุ่ม 1 (หน่วย %) · \"เรียงทิศเดียว\" = Spearman ของลำดับกลุ่มกับผลตอบแทนเฉลี่ย (+1 = เรียงขึ้นเรื่อย ๆ) · "
             "\"ปลายสองด้านสูงกว่ากลาง\" = ค่าเฉลี่ยของกลุ่ม 1 และ 10 ลบค่าเฉลี่ยกลุ่ม 4 ถึง 7 (ใกล้ 0 หรือติดลบ = ไม่เป็นรูปตัว U)", "",
             "| กลุ่มสินทรัพย์ | n แถว | สูงสุด − ต่ำสุด (%) | ช่วงเชื่อมั่น 95% | เรียงทิศเดียว (ρ) | ช่วงเชื่อมั่น | ปลายสองด้านสูงกว่ากลาง (%) |", "|---|---|---|---|---|---|---|"]
    for group in GROUP_ORDER:
        d = deciles[group]
        lines.append("| %s | %s | %+.4f | %+.4f ถึง %+.4f | %+.2f | %+.2f ถึง %+.2f | %+.4f |" % (group, "{:,}".format(int(d["counts"].sum())), d["diff"], *d["diff_ci"], d["trend"], *d["trend_ci"], d["u_shape"]))
    lines += ["", "ผลตอบแทนเฉลี่ย (%) ของแต่ละกลุ่มความรู้สึก (1 → 10)", "", "| กลุ่มสินทรัพย์ | " + " | ".join(str(i) for i in range(1, 11)) + " |", "|---|" + "---|" * 10]
    for group in GROUP_ORDER:
        lines.append("| %s | " % group + " | ".join("%+.3f" % v for v in deciles[group]["means"]) + " |")
    lines += ["", "รูป: `output/figures/spearman_deciles.png`", "",
              "## A2) ขึ้น → ขึ้น และ ลง → ลง ทิศเดียวกันทั้งสองฝั่งไหม (Spearman แยกครึ่งชั่วโมงที่ความรู้สึกสูง กับต่ำ)", "",
              "| กลุ่มสินทรัพย์ | ครึ่งที่วัด | n | Spearman ρ | ช่วงเชื่อมั่น 95% |", "|---|---|---|---|---|"]
    for group in GROUP_ORDER:
        for name, (n, rho, low, high) in halves[group].items():
            lines.append("| %s | %s | %s | %+.4f | %+.4f ถึง %+.4f |" % (group, name, "{:,}".format(n), rho, low, high))
    lines += ["", "## A3) ความรู้สึก \"เปลี่ยน\" ขึ้น/ลงจากชั่วโมงก่อน เทียบผลตอบแทน (Spearman)", "",
              "| กลุ่มสินทรัพย์ | เทียบกับ | n | Spearman ρ | ช่วงเชื่อมั่น 95% |", "|---|---|---|---|---|"]
    for group in GROUP_ORDER:
        for name, (n, rho, low, high) in changes[group].items():
            lines.append("| %s | %s | %s | %+.4f | %+.4f ถึง %+.4f |" % (group, name, "{:,}".format(n), rho, low, high))
    lines += ["", "## A4) ใครนำใคร: Spearman ของความรู้สึก(t) กับผลตอบแทนของชั่วโมง t+k", "",
              "k > 0 = ความรู้สึกมาก่อนผลตอบแทน k ชั่วโมง (ทำนายล่วงหน้า) · k < 0 = ผลตอบแทนมาก่อนความรู้สึก (ราคานำ) · k = 0 = ชั่วโมงเดียวกัน · ช่วงเชื่อมั่นที่ไม่คร่อม 0 มี ★", "",
              "| k | " + " | ".join(GROUP_ORDER) + " |", "|---|" + "---|" * len(GROUP_ORDER)]
    for k in LAGS:
        cells = []
        for group in GROUP_ORDER:
            n, rho, low, high = leadlags[group][k]
            cells.append("%+.4f%s" % (rho, "★" if (low > 0 or high < 0) else ""))
        lines.append("| %+d | " % k + " | ".join(cells) + " |")
    lines += ["", "รูป: `output/figures/spearman_leadlag.png`", "",
              "## B) ค่าซ้ำ (ties) และ ## C) autocorrelation และ ## D) stationarity", "",
              "ค่าซ้ำ = สัดส่วนแถวที่ค่าเท่ากับแถวอื่น · acf = สหสัมพันธ์ของค่ากับค่าเมื่อ k ชั่วโมงก่อน · Ljung–Box 24 lag (H0: ไม่มี autocorrelation) · ADF (H0: unit root; ค่าสถิติต่ำกว่า %.2f = ปฏิเสธที่ 5%% = นิ่ง) · KPSS (H0: นิ่ง; ค่าสถิติสูงกว่า %.3f = ปฏิเสธที่ 5%% = ไม่นิ่ง)" % (ADF_CRITICAL["5%"], KPSS_CRITICAL["5%"]), "",
              "| ตัวแปร | n | ค่าซ้ำ | acf lag 1 | lag 6 | lag 24 | p Ljung–Box | ADF | KPSS |", "|---|---|---|---|---|---|---|---|---|",
              "| ความรู้สึกของตลาด | %s | %.1f%% | %+.3f | %+.3f | %+.3f | %s | %.2f | %.3f |" % ("{:,}".format(sent.n), 100 * sent.ties_share, sent.acf1, sent.acf6, sent.acf24, fmt_p(sent.lb_p), sent.adf, sent.kpss)]
    for group in GROUP_ORDER:
        g = returns[returns.group == group]
        lines.append("| ผลตอบแทน %s (มัธยฐานของ %d สินทรัพย์) | %s | %.1f%% (ผลตอบแทนเป็น 0: %.1f%%) | %s | %s | %s | ผ่าน(p<0.05) %d/%d | %.2f | %.3f |" % (
            group, len(g), "{:,}".format(int(g.n.median())), 100 * g.ties_share.median(), 100 * g.zero_share.median(), fmt_acf(g.acf1.median()), fmt_acf(g.acf6.median()), fmt_acf(g.acf24.median()),
            int((g.lb_p < 0.05).sum()), len(g), g.adf.median(), g.kpss.median()))
    lines += ["", "(คอลัมน์ p Ljung–Box ของผลตอบแทน: จำนวนสินทรัพย์ที่ปฏิเสธ \"ไม่มี autocorrelation\" จากทั้งกลุ่ม · ADF และ KPSS เป็นมัธยฐานของสินทรัพย์ในกลุ่ม)", "",
              "ผลตอบแทนรายสินทรัพย์ที่ \"นิ่ง\" ทั้งสองการทดสอบ (ADF ปฏิเสธ unit root และ KPSS ไม่ปฏิเสธความนิ่ง ที่ 5%%): %d จาก %d สินทรัพย์" % (
                  int(((returns.adf < ADF_CRITICAL["5%"]) & (returns.kpss < KPSS_CRITICAL["5%"])).sum()), len(returns)), "",
              "## E) ความเสถียร: รายเดือน และตัดผลตอบแทนสุดขั้ว 1% ของแต่ละสินทรัพย์", "",
              "| กลุ่มสินทรัพย์ | เดือนที่ทดสอบ | เดือนที่ ρ เป็นบวก | มัธยฐาน ρ รายเดือน | ρ ทั้งช่วง | ρ หลังตัดสุดขั้ว 1% |", "|---|---|---|---|---|---|"]
    for group in GROUP_ORDER:
        s = stability[group]
        lines.append("| %s | %d | %d | %+.4f | %+.4f | %+.4f |" % (group, s["months"], s["positive"], s["median"], s["full"], s["trimmed"]))
    lines += ["", "ข้อจำกัด: ความรู้สึกของตลาดมีค่าเดียวต่อชั่วโมงใช้ร่วมกันทุกสินทรัพย์ (แถวที่รวมกลุ่มจึงไม่อิสระกัน ช่วงเชื่อมั่นใช้บล็อกรายวันเพื่อชดเชย) · แถวของสินทรัพย์คือชั่วโมงที่มีราคา (หุ้นมีช่องว่างตอนกลางคืน ADF และ KPSS ทำกับแถวต่อเนื่องกันตามที่มี) · "
              "ADF และ KPSS เขียนเองด้วย numpy เทียบกับค่าวิกฤตมาตรฐาน · " + crosscheck(senti, prices) + " · หุ้นมีแท่งราคาแค่ 6 ชั่วโมงต่อวัน จึงไม่มีคู่ที่ห่างกัน 6 ชั่วโมง (acf lag 6 = \"-\") · ค่าทั้งหมดเป็นค่าบรรยาย", ""]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "spearman_assumptions_check.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (OUT_DIR / "spearman_assumptions_check.csv").open("w", newline="", encoding="utf-8") as sink:
        sink.write("\n".join(file_header("ผลตรวจรายอนุกรม (ค่าซ้ำ, autocorrelation, Ljung-Box, ADF, KPSS) ของความรู้สึกและผลตอบแทนรายสินทรัพย์ (ข้อมูลชุดเดียวกับ spearman_assumptions_check.md)",
                                         "scripts/spearman_assumptions_check.py", "python scripts/spearman_assumptions_check.py", "reddit_hourly_global + market_hourly_features", comment=True)) + "\n")
        table.to_csv(sink, index=False)
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
