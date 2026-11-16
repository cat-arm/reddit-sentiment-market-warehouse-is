"""System 7.6 Hot Events: the score of a signal, its level, and what happened AFTER it (the predictive check).

EXTENSION: the proposal (7.6) names the levels low / medium / high but not how a signal reaches them, and it does not test the
signals forward.  Decisions in docs/METHOD_DECISIONS_NOT_IN_PROPOSAL.md.

score     the number of KPIs a row passes.  Six KPIs, each with ONE threshold (value > threshold; a missing value never passes), all
          known in the hour itself or from the hours before it: no statistic of the whole history (Spearman, Win Rate ...), which
          could not be known when the signal appeared.  No weights: the variables of the Logistic Regression (ratios, majority, lags,
          momentum) are not scored, because that page tested them and found an AUC near 0.5.
level     low / medium / high by how many KPIs pass ("" = below low).
forward   the predictive check: does a higher score come before a BIGGER price move?  The move of a row is
          |future_return_h| divided by the asset's normal move, the mean |future_return_h| of the same asset over the rows
          whose horizon had ENDED by the hour of the row (hour <= t - h): nothing after t is used.  A "big move" is a move
          above that normal (relative move > 1).  The score is judged with the AUC of the score for the big moves (0.5 =
          no better than chance), and the direction with the hit rate sign(sentiment) = sign(future return).
"""

import numpy as np
import pandas as pd

LEVELS = ("low", "medium", "high")
# (key, label, default threshold, step of the input).  Six KPIs, no weights (user decision 2026-11-14: the 17-KPI weighted score was hard to explain,
# 12 of its KPIs sat at the 2 % floor, and the Reddit KPIs added only 0.007 AUC to the price KPIs).
# The default thresholds are the values `learn_defaults` learns on the TRAINING PERIOD ONLY (before SPLIT_UTC = 2025-10-01): the value a KPI exceeds in only
# 20 % of the asset x hours of the training period, ROUNDED to a value that is easy to read (user, 2026-11-15): Reddit Volume Z 1.45 -> 1.5 (the Z > 1.5 of
# the proposal), |Sentiment| 0.06 -> 0.05 (the neutral band of the proposal), Mention Rate 1.03 -> 1.0, Normalized ATR 1.23 -> 1.2, |Current Return| 0.71 -> 0.7.
METRICS = [("rz", "Reddit Volume Z-score >", 1.5, 0.05), ("mr", "Ticker Mention Rate (%) >", 1.0, 0.05),
           ("ss", "|Sentiment| >", 0.05, 0.01), ("tz", "Trading Volume Z-score >", 1.0, 0.05),
           ("na", "Normalized ATR (%) >", 1.2, 0.01), ("cr", "|Current Return| (%) >", 0.7, 0.01)]
DEFAULT_RULES = {m: float(t) for m, _, t, _ in METRICS}
SPLIT_UTC = 1759276800                                                # 2025-10-01 00:00 UTC: training period before, later period from
TOP_SHARE = 0.20

# what every KPI is (the tooltip of the page); where every default comes from is the same rule for all of them (see above)
ORIGIN = "ปัดจากค่าที่เรียนในช่วงฝึก (ต.ค. 2024 – ก.ย. 2025) เท่านั้น: ค่าที่มีเพียง 20% ของชั่วโมง × สินทรัพย์สูงกว่า · ตรวจกับช่วงหลัง ต.ค. 2025 แล้ว"
ABOUT = {
    "rz": ("ปริมาณโพสต์+คอมเมนต์ของทั้งตลาดในชั่วโมงนี้ เทียบ 24 ชม. ก่อนหน้า (กี่ SD)", ORIGIN),
    "mr": ("ข้อความที่พูดถึงสินทรัพย์นี้ ÷ ข้อความทั้งตลาด × 100", ORIGIN),
    "ss": ("ขนาดของความรู้สึกเฉลี่ยทั้งตลาด (ไม่สนบวกลบ)", ORIGIN),
    "tz": ("ปริมาณซื้อขายของสินทรัพย์ เทียบ 24 ชม. ก่อนหน้า (กี่ SD)", ORIGIN),
    "na": ("ATR 24 ชม. ÷ ราคา × 100 = ราคาแกว่งกี่ % ต่อชั่วโมง", ORIGIN),
    "cr": ("ขนาดผลตอบแทนของชั่วโมงนี้ (ไม่สนขึ้นลง)", ORIGIN)}
# The level of a signal is read from its SCORE IN % (user, 2026-11-16: not from how many KPIs pass): every KPI passed adds its weight, the sum is the score (e.g. a Ticker Mention
# Rate that passes = 17 %), low 40-59 %, medium 60-79 %, high 80-100 %.  With the default weights 3 KPIs score 49-51, 4 KPIs 64-68, 5 KPIs 83-100, so the cuts 40 / 60 / 80 sit between those
# steps whichever KPIs pass.  Rows that reach each level (of 239,394 asset x hours): >= 40 % = 9.2 % (21,944), >= 60 % = 1.9 % (4,517), >= 80 % = 0.22 % (531).
DEFAULT_CUTS_PCT = {"low": 40.0, "medium": 60.0, "high": 80.0}
# The weight of every KPI in the score, in % (they total 100; user, 2026-11-15).  Equal as far as 100 allows (17 / 17 / 17 / 17 / 16 / 16): no result says that one KPI deserves
# more, so the default score is still "how many KPIs pass" (2 of 6 = 32-34 %, 3 = 49-51 %, 4 = 64-68 %), 5 = 83-84 %), and the cuts 40 / 60 / 80 sit between those steps whichever KPIs pass.
DEFAULT_WEIGHTS = {"rz": 17.0, "mr": 17.0, "ss": 17.0, "tz": 17.0, "na": 16.0, "cr": 16.0}
PRICE_KPIS = ("tz", "na", "cr")                                        # the KPIs that come from the price; every other one comes from Reddit
REDDIT_KPIS = tuple(m for m, *_ in METRICS if m not in PRICE_KPIS)
HORIZONS = ("now", "1h", "2h", "3h", "6h", "12h")                      # "now" = Current Return (the hour itself)
FORWARD_HORIZONS = HORIZONS[1:]
MIN_PRIOR = 168                                                        # rows of the same asset the normal move needs (one week of hours)


def _num(d, col):
    return pd.to_numeric(d[col], errors="coerce") if col in d else pd.Series(np.nan, index=d.index)


SOURCE = {"rz": lambda d: d.reddit_volume_zscore_24, "mr": lambda d: d.mention_rate, "ss": lambda d: d.sentiment_mean.abs(),
          "tz": lambda d: _num(d, "volume_zscore_24"), "na": lambda d: _num(d, "normalized_atr"),
          "cr": lambda d: _num(d, "log_return").abs()}


def learn_defaults(df, horizon="1h", split=SPLIT_UTC, top_share=TOP_SHARE):
    """The default thresholds, learned on the rows before `split` only.  -> DataFrame(kpi, threshold, auc_train): threshold = the (1 - top_share)
    quantile of the KPI in the training rows; auc_train = AUC of the flag "passes" for a move bigger than normal (information only, not a weight)."""
    rel = relative_move(df, horizon)
    big = (rel > 1).astype(float).where(rel.notna())
    train = (df.hour_utc < split) & rel.notna()
    rows = []
    for m, *_ in METRICS:
        v = pd.to_numeric(SOURCE[m](df), errors="coerce")
        t = float(v[train].quantile(1 - top_share))
        rows.append((m, t, auc((v > t).astype(float)[train], big[train])))
    return pd.DataFrame(rows, columns=["kpi", "threshold", "auc_train"])


def target(horizon):
    """(column of the move, hours until the move is known) for a horizon: 'now' = Current Return of the hour (known one hour later)."""
    return ("log_return", 1) if horizon == "now" else ("future_return_" + horizon, int(horizon[:-1]))


def score(df, rules=None):
    """How many KPIs every row passes.  `rules` = {kpi: threshold} (default: DEFAULT_RULES)."""
    rules = DEFAULT_RULES if rules is None else rules
    total = pd.Series(0, index=df.index)
    for m, threshold in rules.items():
        total += (pd.to_numeric(SOURCE[m](df), errors="coerce") > threshold).astype(int)
    return total


def score_pct(df, rules=None, weights=None):
    """The score as a percent, 0 - 100: the weight of the KPIs a row passes over the weight of the KPIs in use (`rules`; a KPI that is switched off, or left out,
    does not count).  `weights` = {kpi: weight in %}; None = equal weights (the share of the KPIs passed)."""
    rules = DEFAULT_RULES if rules is None else rules
    weights = {m: 1.0 for m in rules} if weights is None else weights
    total = sum(weights[m] for m in rules)
    got = pd.Series(0.0, index=df.index)
    for m, threshold in rules.items():
        got += weights[m] * (pd.to_numeric(SOURCE[m](df), errors="coerce") > threshold).astype(float)
    return 100.0 * got / total if total else got


def level(points, cuts=None):
    """'' (below low) / 'low' / 'medium' / 'high' for every score in % (cuts = the score in % a row must reach; default DEFAULT_CUTS_PCT)."""
    cuts = DEFAULT_CUTS_PCT if cuts is None else cuts
    out = pd.Series("", index=points.index)
    return out.mask(points >= cuts["low"], "low").mask(points >= cuts["medium"], "medium").mask(points >= cuts["high"], "high")


def relative_move(df, horizon, min_prior=MIN_PRIOR):
    """|future_return_<horizon>| of every row divided by the normal move of its asset known at the hour of the row: the mean
    |future_return_<horizon>| over the rows of the same ticker with hour <= hour - horizon (their horizon has ended).
    NaN without a future return or with fewer than `min_prior` earlier rows.  Index = df.index."""
    col, hours = target(horizon)
    a = df[["ticker", "hour_utc"]].assign(move=pd.to_numeric(df[col], errors="coerce").abs())
    known = a.dropna(subset=["move"]).sort_values(["ticker", "hour_utc"])
    known = known.assign(csum=known.groupby("ticker").move.cumsum(), cnt=known.groupby("ticker").cumcount() + 1)
    ask = a.assign(t_known=a.hour_utc - hours * 3600).reset_index().sort_values("t_known")
    base = known[["ticker", "hour_utc", "csum", "cnt"]].rename(columns={"hour_utc": "t_known"}).sort_values("t_known")
    got = pd.merge_asof(ask, base, on="t_known", by="ticker", direction="backward", allow_exact_matches=True).set_index("index")
    normal = (got.csum / got.cnt).where(got.cnt >= min_prior)
    return (got.move / normal).reindex(df.index)


def auc(points, big):
    """AUC of `points` for the boolean `big` (rows with NaN dropped); NaN when one class is missing.  Ties count one half."""
    keep = points.notna() & big.notna()
    x, y = points[keep].to_numpy(float), big[keep].to_numpy(bool)
    n1, n0 = int(y.sum()), int((~y).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    ranks = pd.Series(x).rank(method="average").to_numpy()
    return float((ranks[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def forward(df, points, horizon, cuts=None):
    """The predictive check of one horizon.  -> (table, auc_move): table per level ('ไม่ถึง low', low, medium, high) with
    n, move = mean relative move, big = share of big moves (relative move > 1), hit = share with sign(sentiment) = sign(future
    return) among the rows where both are non-zero; auc_move = AUC of the score for a big move."""
    rel = relative_move(df, horizon)
    fut = pd.to_numeric(df[target(horizon)[0]], errors="coerce")
    sgn = np.sign(df.sentiment_mean) * np.sign(fut)
    frame = pd.DataFrame({"level": level(points, cuts).replace("", "ไม่ถึง low"), "rel": rel,
                          "big": (rel > 1).where(rel.notna()), "hit": (sgn > 0).astype(float).where(sgn != 0)})
    frame = frame[frame.rel.notna()]
    order = ["ไม่ถึง low", *LEVELS]
    table = frame.groupby("level").agg(n=("rel", "size"), move=("rel", "mean"), big=("big", "mean"), hit=("hit", "mean"))
    table = table.reindex([lv for lv in order if lv in table.index]).reset_index()
    return table, auc(points[frame.index], frame.big.astype(float))
