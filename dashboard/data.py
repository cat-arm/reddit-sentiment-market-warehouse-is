"""Data layer of the Streamlit dashboard (TASKS D0): every query the pages run, in one place.

Rules (proposal 7.5, TASKS D0):
  * READ-ONLY: connections are opened with mode=ro, nothing here can change the database.
  * The pages read only the tables built by the pipeline (reddit_hourly*, market_hourly_features,
    merged_hourly_panel, Fact*, analysis_results, signal_events, ...), never the 28 M-row raw tables.
  * Every function takes `db_path` first and returns a pandas DataFrame, so the pages can wrap them in
    st.cache_data and the Q4 test can compare each number with a direct SQL query.
  * Times are UTC.  `start` / `end` are epoch seconds of the first / last hour (inclusive).
  * NULL stays NULL (a missing sentiment is not 0).  The Reddit author is never selected.
"""

import sqlite3
from pathlib import Path

import pandas as pd

from etl.reddit_features import volume_features

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "output" / "reddit.sqlite3"
HORIZONS = ("1h", "2h", "3h", "6h", "12h")


def _read(db_path, sql, params=()):
    """Run one SELECT on a read-only connection and return a DataFrame (connection closed afterwards)."""
    db = sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True, timeout=60)
    try:
        return pd.read_sql_query(sql, db, params=params)
    finally:
        db.close()


def _src_filter(source_ids, column="v.SourceID"):
    """(' AND <column> IN (?,?,..)', ids) for a tuple of DimSource ids; ('', ()) = every source."""
    if source_ids is None:
        return "", ()
    ids = tuple(int(i) for i in source_ids)
    return " AND %s IN (%s)" % (column, ",".join("?" * len(ids))), ids


def _all_sources(db_path, source_ids):
    """True when the filter keeps every source (then the stored all-source statistics can be used)."""
    return source_ids is None or len(set(source_ids)) == len(sources(db_path))


def _prior24_zscore(hours, counts, start, end):
    """Volume Z-score of the proposal (mean / std of the 24 clock hours BEFORE, current hour excluded) for the hourly
    counts `counts` indexed by epoch `hours`; hours without any text are real zeros.  `hours` must start 24 hours
    before `start`; returns a DataFrame(hour_utc, zscore) for start..end only."""
    grid = pd.Index(range(int(start) - 86400, int(end) + 3600, 3600), name="hour_utc")
    series = pd.Series(counts, index=hours).groupby(level=0).sum().reindex(grid).fillna(0)
    z, _ = volume_features(series.to_frame("v"))
    out = z["v"].reset_index().rename(columns={"v": "zscore"})
    return out[(out.hour_utc >= start) & (out.hour_utc <= end)].reset_index(drop=True)


def to_time(df, col="hour_utc"):
    """Add a timezone-aware `time` column from the epoch-second hour."""
    out = df.copy()
    out["time"] = pd.to_datetime(out[col], unit="s", utc=True)
    return out


# ------------------------------------------------------------------------------------------------ meta
def tickers(db_path):
    """The 34 target assets with their group (DimTicker)."""
    return _read(db_path, "SELECT TickerSymbol AS ticker, AssetClass AS big_group, TickerName AS name "
                          "FROM DimTicker ORDER BY CASE AssetClass WHEN 'stock_etf' THEN 1 WHEN 'futures' THEN 2 ELSE 3 END, "
                          "TickerSymbol")


def sources(db_path):
    """DimSource: the 12 sources (6 communities x Post / Comment) with their ids."""
    return _read(db_path, "SELECT SourceID AS source_id, Platform AS platform, Subreddit AS subreddit, "
                          "ContentType AS content_type FROM DimSource ORDER BY SourceID")


def data_range(db_path):
    """First/last hour that has Reddit data and market data (epoch seconds) + row counts for the home page."""
    reddit = _read(db_path, "SELECT MIN(hour_utc) AS lo, MAX(hour_utc) AS hi FROM reddit_hourly "
                            "WHERE variant = 'all' AND ticker = 'ALL'").iloc[0]
    market = _read(db_path, "SELECT MIN(hour_utc) AS lo, MAX(hour_utc) AS hi, COUNT(*) AS n FROM merged_hourly_panel "
                            "WHERE scope = 'ticker' AND variant = 'all'").iloc[0]
    return {"reddit_lo": int(reddit.lo), "reddit_hi": int(reddit.hi), "market_lo": int(market.lo),
            "market_hi": int(market.hi), "market_rows": int(market.n)}


def overview_filtered(db_path, start, end, groups):
    """Home-page numbers that follow the central filter (date range + asset classes).
    Returns one row per asset class: tickers, price hours, and the price hours in which the asset was talked about.
    (Total texts are market-wide, so they follow the date range only: see `texts_in_range`.)"""
    marks = ",".join("?" * len(groups))
    return _read(db_path, """
        SELECT big_group, COUNT(DISTINCT ticker) AS tickers, COUNT(*) AS price_hours,
               SUM(has_reddit_data) AS talked_hours
        FROM merged_hourly_panel WHERE scope = 'ticker' AND variant = 'all' AND hour_utc BETWEEN ? AND ?
          AND big_group IN (%s) GROUP BY big_group""" % marks, (start, end, *groups))


def texts_in_range(db_path, start, end):
    """Texts that got a sentiment score in the date range (all 6 communities, not split by asset class)."""
    return _read(db_path, """
        SELECT COALESCE(SUM(v.texts), 0) AS texts FROM reddit_volume_hourly v JOIN DimTime t USING (TimeID)
        WHERE CAST(strftime('%s', t.ts_utc) AS INTEGER) BETWEEN ? AND ?""", (start, end)).iloc[0].texts


def overview_counts(db_path):
    """Headline numbers for the home page (all come from small summary tables)."""
    return _read(db_path, """
        SELECT (SELECT COUNT(*) FROM sentiment_item) AS texts_scored,
               (SELECT COUNT(*) FROM FactMarketSentiment) AS fact_rows,
               (SELECT COUNT(*) FROM FactMarketSentiment WHERE sentiment_mean IS NOT NULL) AS fact_rows_with_sentiment,
               (SELECT COUNT(*) FROM signal_events WHERE z_threshold = 1.5 AND s_threshold = 0.3) AS default_signals,
               (SELECT COUNT(DISTINCT ticker) FROM merged_hourly_panel WHERE scope = 'ticker') AS tickers""").iloc[0]


# ------------------------------------------------------------------------------------------------ D1: Reddit volume
def total_volume_series(db_path, start, end, source_ids=None):
    """Reddit_volume of proposal table 3: ALL posts and comments per hour (6 communities), split Post / Comment,
    plus the Volume Z-score of the hourly total (24 prior hours, current hour excluded).  Hours without any text
    are missing here; the page fills them with 0 (no texts is a real count).
    `source_ids` (DimSource ids) keeps only those communities / content types; the Z-score is then recomputed from the
    filtered hourly total with the same rule (it equals the stored all-source value when nothing is filtered out)."""
    flt, extra = _src_filter(source_ids)
    df = _read(db_path, """
        SELECT CAST(strftime('%s', t.ts_utc) AS INTEGER) AS hour_utc,
               SUM(CASE WHEN s.ContentType = 'Post' THEN v.texts ELSE 0 END) AS posts,
               SUM(CASE WHEN s.ContentType = 'Comment' THEN v.texts ELSE 0 END) AS comments, SUM(v.texts) AS texts
        FROM reddit_volume_hourly v JOIN DimTime t USING (TimeID) JOIN DimSource s ON s.SourceID = v.SourceID
        WHERE CAST(strftime('%s', t.ts_utc) AS INTEGER) BETWEEN ? AND ?""" + flt + """
        GROUP BY t.ts_utc ORDER BY hour_utc""", (start, end, *extra))
    if _all_sources(db_path, source_ids):
        z = _read(db_path, "SELECT hour_utc, reddit_volume_zscore_24 AS zscore FROM reddit_hourly_features "
                           "WHERE variant = 'all' AND ticker = 'ALL' AND hour_utc BETWEEN ? AND ?", (start, end))
    else:
        back = _read(db_path, """
            SELECT CAST(strftime('%s', t.ts_utc) AS INTEGER) AS hour_utc, SUM(v.texts) AS n
            FROM reddit_volume_hourly v JOIN DimTime t USING (TimeID)
            WHERE CAST(strftime('%s', t.ts_utc) AS INTEGER) BETWEEN ? AND ?""" + flt + """
            GROUP BY t.ts_utc""", (start - 86400, end, *extra))
        z = _prior24_zscore(back.hour_utc, back.n.to_numpy(float), start, end)
    return to_time(df.merge(z, on="hour_utc", how="left"))


def total_volume_by_source(db_path, start, end, source_ids=None):
    """Total posts/comments per community and content type in the range (DimSource)."""
    flt, extra = _src_filter(source_ids)
    return _read(db_path, """
        SELECT s.Subreddit AS subreddit, s.ContentType AS content_type, SUM(v.texts) AS texts
        FROM reddit_volume_hourly v JOIN DimTime t USING (TimeID) JOIN DimSource s ON s.SourceID = v.SourceID
        WHERE CAST(strftime('%s', t.ts_utc) AS INTEGER) BETWEEN ? AND ?""" + flt + """
        GROUP BY s.Subreddit, s.ContentType ORDER BY texts DESC""", (start, end, *extra))


def volume_series(db_path, ticker, start, end):
    """Hourly texts that mention `ticker` + its Volume Z-score; ticker='ALL' = every text of the 6 communities."""
    df = _read(db_path, """
        SELECT hour_utc, reddit_volume, reddit_volume_zscore_24 AS zscore
        FROM reddit_hourly_features
        WHERE variant = 'all' AND ticker = ? AND hour_utc BETWEEN ? AND ? ORDER BY hour_utc""", (ticker, start, end))
    return to_time(df)


def _ticker_filter(tickers, column="k.TickerSymbol"):
    """(' AND <column> IN (?,..)', symbols) for one symbol or a tuple of them."""
    symbols = (tickers,) if isinstance(tickers, str) else tuple(tickers)
    return " AND %s IN (%s)" % (column, ",".join("?" * len(symbols))), symbols


def mention_series(db_path, ticker, start, end, source_ids=None):
    """Hourly number of mentions of the ticker(s) (summed over the chosen tickers and communities) = Ticker_mention_count
    of FactRedditVolume.  `ticker` is one symbol or a tuple of symbols."""
    flt, extra = _src_filter(source_ids, "f.SourceID")
    tf, symbols = _ticker_filter(ticker)
    df = _read(db_path, """
        SELECT CAST(strftime('%s', t.ts_utc) AS INTEGER) AS hour_utc, SUM(f.ticker_mention_count) AS mentions
        FROM FactRedditVolume f JOIN DimTime t USING (TimeID) JOIN DimTicker k USING (TickerID)
        WHERE CAST(strftime('%s', t.ts_utc) AS INTEGER) BETWEEN ? AND ?""" + tf + flt + """
        GROUP BY t.ts_utc ORDER BY hour_utc""", (start, end, *symbols, *extra))
    return to_time(df)


def mention_series_by_ticker(db_path, tickers, start, end, source_ids=None):
    """Hourly mentions per ticker (long format: hour_utc, ticker, mentions) for the chosen tickers."""
    flt, extra = _src_filter(source_ids, "f.SourceID")
    tf, symbols = _ticker_filter(tickers)
    df = _read(db_path, """
        SELECT CAST(strftime('%s', t.ts_utc) AS INTEGER) AS hour_utc, k.TickerSymbol AS ticker,
               SUM(f.ticker_mention_count) AS mentions
        FROM FactRedditVolume f JOIN DimTime t USING (TimeID) JOIN DimTicker k USING (TickerID)
        WHERE CAST(strftime('%s', t.ts_utc) AS INTEGER) BETWEEN ? AND ?""" + tf + flt + """
        GROUP BY t.ts_utc, k.TickerSymbol ORDER BY hour_utc""", (start, end, *symbols, *extra))
    return to_time(df)


def ticker_volume_series(db_path, tickers, start, end, source_ids=None):
    """Hourly Ticker_mention_count of the chosen ticker(s) split into mentions inside posts and inside comments."""
    flt, extra = _src_filter(source_ids, "f.SourceID")
    tf, symbols = _ticker_filter(tickers)
    df = _read(db_path, """
        SELECT CAST(strftime('%s', t.ts_utc) AS INTEGER) AS hour_utc,
               SUM(CASE WHEN s.ContentType = 'Post' THEN f.ticker_mention_count ELSE 0 END) AS posts,
               SUM(CASE WHEN s.ContentType = 'Comment' THEN f.ticker_mention_count ELSE 0 END) AS comments,
               SUM(f.ticker_mention_count) AS mentions
        FROM FactRedditVolume f JOIN DimTime t USING (TimeID) JOIN DimTicker k USING (TickerID)
        JOIN DimSource s ON s.SourceID = f.SourceID
        WHERE CAST(strftime('%s', t.ts_utc) AS INTEGER) BETWEEN ? AND ?""" + tf + flt + """
        GROUP BY t.ts_utc ORDER BY hour_utc""", (start, end, *symbols, *extra))
    return to_time(df)


def ticker_zscore(db_path, ticker, start, end, source_ids=None):
    """Volume Z-score per hour of one ticker, or of several tickers taken together (their summed mentions).
    One ticker, all sources: the stored value, based on the number of TEXTS that mention it (the one panel_Ticker_spike
    uses; hours with Reddit data only, the page treats the others as unknown).
    Several tickers or narrowed sources: the same rule on the Ticker_mention_count of the chosen tickers and sources
    (texts per source are not stored, and a text can mention several tickers).
    Column `basis` says which one it is ('texts' / 'mentions')."""
    symbols = (ticker,) if isinstance(ticker, str) else tuple(ticker)
    if len(symbols) == 1 and _all_sources(db_path, source_ids):
        df = _read(db_path, """
            SELECT hour_utc, reddit_volume_zscore_24 AS zscore FROM reddit_hourly_features
            WHERE variant = 'all' AND ticker = ? AND hour_utc BETWEEN ? AND ? ORDER BY hour_utc""", (symbols[0], start, end))
        df["basis"] = "texts"
    else:
        flt, extra = _src_filter(source_ids, "f.SourceID")
        tf, symbols = _ticker_filter(symbols)
        back = _read(db_path, """
            SELECT CAST(strftime('%s', t.ts_utc) AS INTEGER) AS hour_utc, SUM(f.ticker_mention_count) AS n
            FROM FactRedditVolume f JOIN DimTime t USING (TimeID) JOIN DimTicker k USING (TickerID)
            WHERE CAST(strftime('%s', t.ts_utc) AS INTEGER) BETWEEN ? AND ?""" + tf + flt + """
            GROUP BY t.ts_utc""", (start - 86400, end, *symbols, *extra))
        df = _prior24_zscore(back.hour_utc, back.n.to_numpy(float), start, end)
        df["basis"] = "mentions"
    return to_time(df)


def volume_by_source(db_path, ticker, start, end, source_ids=None):
    """Where the ticker(s) are discussed: mentions per community and content type (DimSource) in the range."""
    flt, extra = _src_filter(source_ids, "f.SourceID")
    tf, symbols = _ticker_filter(ticker)
    return _read(db_path, """
        SELECT s.Subreddit AS subreddit, s.ContentType AS content_type, SUM(f.ticker_mention_count) AS mentions
        FROM FactRedditVolume f JOIN DimTime t USING (TimeID) JOIN DimTicker k USING (TickerID)
        JOIN DimSource s ON s.SourceID = f.SourceID
        WHERE CAST(strftime('%s', t.ts_utc) AS INTEGER) BETWEEN ? AND ?""" + tf + flt + """
        GROUP BY s.Subreddit, s.ContentType ORDER BY mentions DESC""", (start, end, *symbols, *extra))


def mention_ranking(db_path, start, end, source_ids=None):
    """Most discussed tickers in the range: Ticker_mention_count, texts that mention it, and the proposal's KPI
    Ticker Mention Rate (%) = Ticker_mention_count / Reddit_volume (ALL posts and comments) x 100.
    With `source_ids` both the mentions and the Reddit_volume denominator keep only those sources; the number of
    TEXTS that mention a ticker (`texts_about`, `peak_hour_texts`) is not stored per source, so it is NaN then."""
    flt, extra = _src_filter(source_ids, "f.SourceID")
    flt_v, extra_v = _src_filter(source_ids, "v.SourceID")
    out = _read(db_path, """
        SELECT k.TickerSymbol AS ticker, k.AssetClass AS big_group, SUM(f.ticker_mention_count) AS mentions
        FROM FactRedditVolume f JOIN DimTime t USING (TimeID) JOIN DimTicker k USING (TickerID)
        WHERE CAST(strftime('%s', t.ts_utc) AS INTEGER) BETWEEN ? AND ?""" + flt + """
        GROUP BY k.TickerSymbol""", (start, end, *extra))
    total = _read(db_path, """
        SELECT SUM(v.texts) AS n FROM reddit_volume_hourly v JOIN DimTime t USING (TimeID)
        WHERE CAST(strftime('%s', t.ts_utc) AS INTEGER) BETWEEN ? AND ?""" + flt_v, (start, end, *extra_v)).iloc[0].n
    if _all_sources(db_path, source_ids):
        texts = _read(db_path, """
            SELECT h.ticker, SUM(h.reddit_volume) AS texts_about, MAX(h.reddit_volume) AS peak_hour_texts
            FROM reddit_hourly h WHERE h.variant = 'all' AND h.ticker != 'ALL' AND h.hour_utc BETWEEN ? AND ?
            GROUP BY h.ticker""", (start, end))
        out = out.merge(texts, on="ticker", how="left")
    else:
        out["texts_about"] = float("nan")
        out["peak_hour_texts"] = float("nan")
    out = out.sort_values("mentions", ascending=False)
    out["total_volume"] = total
    out["mention_rate_pct"] = 100.0 * out["mentions"] / total if total else float("nan")
    return out.reset_index(drop=True)


# ------------------------------------------------------------------------------------------------ D2: price and return
# log_return = current_return (proposal's "Current Return"; shown on the page under that name)
PRICE_COLUMNS = ("close, volume, log_return, future_return_1h, future_return_2h, future_return_3h, "
                 "future_return_6h, future_return_12h, rsi, atr, normalized_atr, volume_zscore_24")


def price_series(db_path, ticker, start, end):
    """Hourly close, volume, returns and technical indicators of one ticker (valid bars only)."""
    df = _read(db_path, """
        SELECT CAST(strftime('%%s', hour_bucket) AS INTEGER) AS hour_utc, %s FROM market_hourly_features
        WHERE ticker = ? AND CAST(strftime('%%s', hour_bucket) AS INTEGER) BETWEEN ? AND ? ORDER BY hour_utc"""
               % PRICE_COLUMNS, (ticker, start, end))
    return to_time(df)


def group_risk(db_path, start, end):
    """Which asset class is most volatile?  Mean Normalized ATR (%) and spread of hourly log returns per group."""
    return _read(db_path, """
        SELECT k.AssetClass AS big_group, COUNT(*) AS bars, AVG(m.normalized_atr) AS mean_normalized_atr_pct,
               AVG(ABS(m.log_return)) AS mean_abs_log_return_pct
        FROM market_hourly_features m JOIN DimTicker k ON k.TickerSymbol = m.ticker
        WHERE CAST(strftime('%s', m.hour_bucket) AS INTEGER) BETWEEN ? AND ? GROUP BY k.AssetClass
        ORDER BY mean_normalized_atr_pct DESC""", (start, end))


def ticker_risk(db_path, start, end):
    """Same per ticker (for the sortable table)."""
    return _read(db_path, """
        SELECT m.ticker, k.AssetClass AS big_group, COUNT(*) AS bars, AVG(m.normalized_atr) AS mean_normalized_atr_pct,
               AVG(ABS(m.log_return)) AS mean_abs_log_return_pct
        FROM market_hourly_features m JOIN DimTicker k ON k.TickerSymbol = m.ticker
        WHERE CAST(strftime('%s', m.hour_bucket) AS INTEGER) BETWEEN ? AND ? GROUP BY m.ticker
        ORDER BY mean_normalized_atr_pct DESC""", (start, end))


def future_return_by_group(db_path, start, end):
    """Mean future return (%) and share of positive returns per asset class and horizon (long format)."""
    parts = []
    for h in HORIZONS:
        col = "future_return_" + h
        df = _read(db_path, """
            SELECT k.AssetClass AS big_group, COUNT(m.%s) AS n, AVG(m.%s) AS mean_return_pct,
                   AVG(CASE WHEN m.%s > 0 THEN 1.0 WHEN m.%s < 0 THEN 0.0 END) AS share_up
            FROM market_hourly_features m JOIN DimTicker k ON k.TickerSymbol = m.ticker
            WHERE CAST(strftime('%%s', m.hour_bucket) AS INTEGER) BETWEEN ? AND ? GROUP BY k.AssetClass"""
                   % (col, col, col, col), (start, end))      # '%%s' is the literal %s of strftime after formatting
        df["horizon"] = h
        parts.append(df)
    return pd.concat(parts, ignore_index=True)


# ------------------------------------------------------------------------------------------------ D3: market and sentiment
def overview_series(db_path, ticker, start, end):
    """Price + Reddit sentiment of one ticker per hour (ticker-level texts, all variants of text = 'all')."""
    df = _read(db_path, """
        SELECT hour_utc, close, volume, sentiment_mean, pos_ratio, neg_ratio, neu_ratio, majority_final_status,
               reddit_volume, reddit_volume_zscore_24 AS zscore, sentiment_momentum_1h AS momentum, has_reddit_data
        FROM merged_hourly_panel WHERE scope = 'ticker' AND variant = 'all' AND ticker = ?
          AND hour_utc BETWEEN ? AND ? ORDER BY hour_utc""", (ticker, start, end))
    return to_time(df)


def sentiment_by_ticker(db_path, start, end):
    """Which assets are most positive / negative in the range (mean of hourly sentiment_mean, hours with text only)."""
    return _read(db_path, """
        SELECT ticker, big_group, COUNT(sentiment_mean) AS hours_with_text, AVG(sentiment_mean) AS mean_sentiment,
               AVG(pos_ratio) AS pos_ratio, AVG(neg_ratio) AS neg_ratio, SUM(reddit_volume) AS texts
        FROM merged_hourly_panel WHERE scope = 'ticker' AND variant = 'all' AND hour_utc BETWEEN ? AND ?
        GROUP BY ticker HAVING COUNT(sentiment_mean) > 0 ORDER BY mean_sentiment DESC""", (start, end))


def majority_vs_return(db_path, ticker, start, end):
    """Does the majority sentiment of the hour agree with the direction of the future return?  Per horizon."""
    parts = []
    for h in HORIZONS:
        col = "future_return_" + h
        df = _read(db_path, """
            SELECT majority_final_status AS majority, COUNT(%s) AS n, AVG(%s) AS mean_future_return_pct,
                   AVG(CASE WHEN %s > 0 THEN 1.0 WHEN %s < 0 THEN 0.0 END) AS share_up
            FROM merged_hourly_panel WHERE scope = 'ticker' AND variant = 'all' AND ticker = ?
              AND majority_final_status IS NOT NULL AND hour_utc BETWEEN ? AND ? GROUP BY majority_final_status"""
                   % (col, col, col, col), (ticker, start, end))
        df["horizon"] = h
        parts.append(df)
    return pd.concat(parts, ignore_index=True)


# ------------------------------------------------------------------------------------------------ D4: ranking and signals
def ranking_table(db_path):
    """One row per ticker: Historical Win Rate (%), Binomial p-value and Spearman rho for each horizon (A1/A2,
    panel_Ticker = the ticker's own texts).  NULL = not enough data (n < 30)."""
    win = _read(db_path, """
        SELECT ticker, big_group, horizon, metric_value * 100.0 AS winrate, p_value, n_samples
        FROM analysis_results WHERE analysis = 'winrate' AND panel_name = 'panel_Ticker' AND level = 'ticker'
          AND predictor = 'sign(sentiment_mean)' AND metric_name = 'winrate'""")
    cor = _read(db_path, """
        SELECT ticker, horizon, metric_value AS correlation FROM analysis_results
        WHERE analysis = 'correlation' AND panel_name = 'panel_Ticker' AND level = 'ticker'
          AND predictor = 'sentiment_mean' AND metric_name = 'spearman'""")
    return win.merge(cor, on=["ticker", "horizon"], how="left")


def ticker_period_stats(db_path, start, end, horizon):
    """Per ticker in the range: mean future return (%) of the horizon and mean / max Reddit Volume Z-score."""
    col = "future_return_" + horizon
    if horizon not in HORIZONS:                       # the column name is built from the argument: whitelist it
        raise ValueError("unknown horizon %r" % horizon)
    return _read(db_path, """
        SELECT ticker, AVG(%s) AS mean_future_return_pct, COUNT(%s) AS return_n,
               AVG(reddit_volume_zscore_24) AS mean_zscore, MAX(reddit_volume_zscore_24) AS max_zscore
        FROM merged_hourly_panel WHERE scope = 'ticker' AND variant = 'all' AND has_reddit_data = 1
          AND hour_utc BETWEEN ? AND ? GROUP BY ticker""" % (col, col), (start, end))


def signal_panel(db_path):
    """Ticker-hours with Reddit data (input of the on-demand signal engine, ~120 k rows)."""
    return _read(db_path, """
        SELECT ticker, big_group, hour_utc, sentiment_mean, reddit_volume, reddit_volume_zscore_24,
               majority_final_status FROM merged_hourly_panel
        WHERE scope = 'ticker' AND variant = 'all' AND has_reddit_data = 1""")


def signal_counts(db_path):
    """Pre-computed counts per configuration (proposal 4.6: number of signals / assets that met the rule)."""
    return _read(db_path, "SELECT * FROM signal_summary ORDER BY z_threshold, s_threshold, signal_type, big_group")


# ------------------------------------------------------------------------------------------------ D6: hot events (EXTENSION)
def hot_events(db_path, start, end, z_min, s_min, min_texts):
    """EXTENSION (not in the proposal): ticker-hours in which Reddit was unusually busy (Volume Z-score > z_min) AND the
    sentiment was clearly directional (|sentiment_mean| >= s_min, at least min_texts texts), with the forward returns
    that followed.  Descriptive history only; hours without a computable return keep NULL."""
    return _read(db_path, """
        SELECT ticker, big_group, hour_utc, sentiment_mean, reddit_volume, reddit_volume_zscore_24 AS zscore,
               future_return_1h, future_return_2h, future_return_3h, future_return_6h, future_return_12h
        FROM merged_hourly_panel
        WHERE scope = 'ticker' AND variant = 'all' AND has_reddit_data = 1 AND reddit_volume >= ?
          AND reddit_volume_zscore_24 > ? AND ABS(sentiment_mean) >= ? AND hour_utc BETWEEN ? AND ?
        ORDER BY hour_utc DESC""", (min_texts, z_min, s_min, start, end))
