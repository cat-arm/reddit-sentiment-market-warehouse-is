"""Rank-based tests that need no normal data and respect the time structure of the hourly series (used by the dashboard, live; the offline report of the same
methods is scripts/nonparametric_tests.py).

  circular_shift_p   p-value of Spearman's rho from ALL the circular shifts of one series against the other (>= `min_shift` rows away from the real alignment).
                     A shift keeps the autocorrelation of both series and breaks only their alignment, which the usual formula for p ignores (it takes every
                     hour as independent, so its p is too small).  All the shifts at once with a Fourier transform: O(n log n).
  block_indices      one bootstrap sample of row indices: whole UTC days (blocks of consecutive rows) drawn with replacement.
  decile_table       mean return per decile of the sentiment (the deciles of the distinct hours), its 95% block-bootstrap interval, the top decile minus the bottom
                     one and the Spearman of the order of the deciles with their means (does the return rise with the sentiment?).
  spearman_with_ci   Spearman's rho with a 95% block-bootstrap interval and the circular-shift p-value.
  spearman_ci_fast   the same interval for MANY pairs at once cheaply (the table of the Statistical Analysis page: 34 assets x 6 horizons, live): the ranks of the whole sample
                     are computed once and every bootstrap sample is the sum of the per-day sums of the drawn days (a multinomial draw of days), so a replicate costs O(days)
                     instead of a new ranking.  It resamples the days with the ranks of the full sample (a standard shortcut); the exact version re-ranks every replicate.
"""
import numpy as np
from scipy import stats

MIN_SHIFT = 24                                              # rows: a shift smaller than this keeps too much of the real alignment


def corr(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a = a - a.mean()
    b = b - b.mean()
    denominator = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / denominator) if denominator > 0 else np.nan


def circular_shift_p(x, y, min_shift=MIN_SHIFT):
    """Two-sided p-value: the share of circular shifts (>= min_shift rows) whose |rho| is at least the real |rho| (the real alignment counts as one).  NaN when too short."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(x)
    if n < 2 * min_shift + 10:
        return np.nan
    rx = stats.rankdata(x)
    ry = stats.rankdata(y)
    rx -= rx.mean()
    ry -= ry.mean()
    denominator = np.sqrt((rx * rx).sum() * (ry * ry).sum())
    if denominator == 0:
        return np.nan
    cross = np.fft.irfft(np.fft.rfft(rx) * np.conj(np.fft.rfft(ry)), n) / denominator      # cross[s] = sum_i rx[i + s] * ry[i] / norm: rho of the shift s
    rho = abs(cross[0])
    shifts = np.abs(cross[min_shift:n - min_shift + 1])
    return float((1 + np.sum(shifts >= rho - 1e-12)) / (1 + len(shifts)))


def day_blocks(hours_sorted):
    days = (np.asarray(hours_sorted) // 86400).astype(np.int64)
    _, first, counts = np.unique(days, return_index=True, return_counts=True)
    return first, counts


def block_indices(first, counts, rng):
    """Row indices of one bootstrap sample: the days (first row, number of rows) drawn with replacement and concatenated."""
    picked = rng.integers(0, len(first), len(first))
    lengths = counts[picked]
    ends = np.cumsum(lengths)
    return np.repeat(first[picked] - (ends - lengths), lengths) + np.arange(ends[-1])


def decile_table(sentiment, returns, hours, groups=10, boot=200, seed=20261116):
    """-> dict(means, low, high, counts, diff, diff_ci, trend, trend_ci, edges) or None when there is too little data.
    The edges are the quantiles of the sentiment of the DISTINCT hours (a market-wide hour that is repeated for many assets counts once)."""
    s = np.asarray(sentiment, dtype=float)
    r = np.asarray(returns, dtype=float)
    h = np.asarray(hours)
    ok = ~(np.isnan(s) | np.isnan(r))
    s, r, h = s[ok], r[ok], h[ok]
    if len(s) < 50 * groups or len(np.unique(h)) < 10 * groups:
        return None
    order = np.argsort(h, kind="stable")
    s, r, h = s[order], r[order], h[order]
    _, first_index = np.unique(h, return_index=True)
    edges = np.unique(np.quantile(s[first_index], np.linspace(0, 1, groups + 1)))
    k = len(edges) - 1
    if k < 3:
        return None
    dec = np.clip(np.searchsorted(edges, s, side="right") - 1, 0, k - 1)

    def means(d, v):
        return np.bincount(d, weights=v, minlength=k) / np.maximum(np.bincount(d, minlength=k), 1)

    base = means(dec, r)
    first, counts = day_blocks(h)
    rng = np.random.default_rng(seed)
    boots, diffs, trends = [], [], []
    for _ in range(boot):
        idx = block_indices(first, counts, rng)
        m = means(dec[idx], r[idx])
        boots.append(m)
        diffs.append(m[-1] - m[0])
        trends.append(stats.spearmanr(np.arange(k), m)[0])
    low, high = np.nanpercentile(np.asarray(boots), [2.5, 97.5], axis=0)
    return {"means": base, "low": low, "high": high, "counts": np.bincount(dec, minlength=k), "edges": edges, "diff": float(base[-1] - base[0]),
            "diff_ci": tuple(np.nanpercentile(diffs, [2.5, 97.5])), "trend": float(stats.spearmanr(np.arange(k), base)[0]),
            "trend_ci": tuple(np.nanpercentile(trends, [2.5, 97.5]))}


def spearman_with_ci(x, y, hours, boot=200, seed=20261116, rows_per_hour=1.0):
    """-> (rho, low, high, p_shift, n) of the rows sorted by hour; the shifts are at least 24 hours (24 x rows_per_hour rows) long.  NaN pairs are dropped."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    h = np.asarray(hours)
    ok = ~(np.isnan(x) | np.isnan(y))
    x, y, h = x[ok], y[ok], h[ok]
    if len(x) < 100:
        return np.nan, np.nan, np.nan, np.nan, len(x)
    order = np.argsort(h, kind="stable")
    x, y, h = x[order], y[order], h[order]
    rho = corr(stats.rankdata(x), stats.rankdata(y))
    first, counts = day_blocks(h)
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(boot):
        idx = block_indices(first, counts, rng)
        values.append(corr(stats.rankdata(x[idx]), stats.rankdata(y[idx])))
    low, high = np.nanpercentile(values, [2.5, 97.5])
    return rho, float(low), float(high), circular_shift_p(x, y, int(MIN_SHIFT * max(rows_per_hour, 1.0))), len(x)


def spearman_ci_fast(x, y, days, boot=1000, seed=20261116):
    """95% interval (low, high) of Spearman's rho: days = the UTC day of every pair (any integer label); the days are drawn with replacement `boot` times."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    days = np.asarray(days)
    ok = ~(np.isnan(x) | np.isnan(y))
    x, y, days = x[ok], y[ok], days[ok]
    labels, inverse = np.unique(days, return_inverse=True)
    n_days = len(labels)
    if len(x) < 30 or n_days < 10:
        return np.nan, np.nan
    rx, ry = stats.rankdata(x), stats.rankdata(y)
    sums = np.column_stack([np.bincount(inverse, minlength=n_days).astype(float), np.bincount(inverse, rx, n_days), np.bincount(inverse, ry, n_days),
                            np.bincount(inverse, rx * rx, n_days), np.bincount(inverse, ry * ry, n_days), np.bincount(inverse, rx * ry, n_days)])
    counts = np.random.default_rng(seed).multinomial(n_days, np.full(n_days, 1.0 / n_days), size=boot)        # how many times each day is drawn
    total = counts @ sums
    n = total[:, 0]
    covariance = total[:, 5] - total[:, 1] * total[:, 2] / n
    variance = (total[:, 3] - total[:, 1] ** 2 / n) * (total[:, 4] - total[:, 2] ** 2 / n)
    with np.errstate(invalid="ignore", divide="ignore"):
        rho = covariance / np.sqrt(variance)
    low, high = np.nanpercentile(rho, [2.5, 97.5])
    return float(low), float(high)
