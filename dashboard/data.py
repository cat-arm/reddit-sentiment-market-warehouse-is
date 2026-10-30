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

import numpy as np
import pandas as pd
from scipy import stats

from etl.common import NEUTRAL_BAND
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


def _only(tickers, column="m.ticker"):
    """(' AND <column> IN (...)', symbols) for the tickers kept by the filter; ('', ()) = every ticker."""
    if tickers is None:
        return "", ()
    symbols = (tickers,) if isinstance(tickers, str) else tuple(tickers)
    return " AND %s IN (%s)" % (column, ",".join("?" * len(symbols))), symbols


def price_series_for(db_path, tickers, start, end):
    """Hourly close, volume, returns and indicators of several tickers (long format, a `ticker` column)."""
    tf, symbols = _only(tickers, "ticker")
    df = _read(db_path, """
        SELECT ticker, CAST(strftime('%%s', hour_bucket) AS INTEGER) AS hour_utc, %s FROM market_hourly_features
        WHERE CAST(strftime('%%s', hour_bucket) AS INTEGER) BETWEEN ? AND ?%s ORDER BY ticker, hour_utc"""
               % (PRICE_COLUMNS, tf), (start, end, *symbols))
    return to_time(df)


def group_risk(db_path, start, end, tickers=None):
    """Which asset class is most volatile?  Mean Normalized ATR (%) and spread of hourly log returns per group
    (only the chosen tickers when `tickers` is given)."""
    tf, symbols = _only(tickers)
    return _read(db_path, """
        SELECT k.AssetClass AS big_group, COUNT(*) AS bars, COUNT(DISTINCT m.ticker) AS tickers,
               AVG(m.normalized_atr) AS mean_normalized_atr_pct, AVG(ABS(m.log_return)) AS mean_abs_log_return_pct
        FROM market_hourly_features m JOIN DimTicker k ON k.TickerSymbol = m.ticker
        WHERE CAST(strftime('%s', m.hour_bucket) AS INTEGER) BETWEEN ? AND ?""" + tf + """ GROUP BY k.AssetClass
        ORDER BY mean_normalized_atr_pct DESC""", (start, end, *symbols))


def ticker_risk(db_path, start, end, tickers=None):
    """Same per ticker (for the sortable table)."""
    tf, symbols = _only(tickers)
    return _read(db_path, """
        SELECT m.ticker, k.AssetClass AS big_group, COUNT(*) AS bars, AVG(m.normalized_atr) AS mean_normalized_atr_pct,
               AVG(ABS(m.log_return)) AS mean_abs_log_return_pct
        FROM market_hourly_features m JOIN DimTicker k ON k.TickerSymbol = m.ticker
        WHERE CAST(strftime('%s', m.hour_bucket) AS INTEGER) BETWEEN ? AND ?""" + tf + """ GROUP BY m.ticker
        ORDER BY mean_normalized_atr_pct DESC""", (start, end, *symbols))


def ticker_snapshot(db_path, start, end, tickers=None):
    """One row per ticker in the range: asset class, last close and RSI, Current Return (sum), mean Normalized ATR and
    the mean future return of every horizon."""
    tf, symbols = _only(tickers)
    agg = _read(db_path, """
        SELECT m.ticker, k.AssetClass AS big_group, SUM(m.log_return) AS current_return_pct,
               AVG(m.normalized_atr) AS mean_normalized_atr_pct,
               AVG(m.future_return_1h) AS fr_1h, AVG(m.future_return_2h) AS fr_2h, AVG(m.future_return_3h) AS fr_3h,
               AVG(m.future_return_6h) AS fr_6h, AVG(m.future_return_12h) AS fr_12h
        FROM market_hourly_features m JOIN DimTicker k ON k.TickerSymbol = m.ticker
        WHERE CAST(strftime('%s', m.hour_bucket) AS INTEGER) BETWEEN ? AND ?""" + tf + """ GROUP BY m.ticker""",
                (start, end, *symbols))
    last = _read(db_path, """
        SELECT m.ticker, m.close AS last_close, m.rsi AS last_rsi
        FROM market_hourly_features m
        JOIN (SELECT ticker, MAX(hour_bucket) AS hb FROM market_hourly_features
              WHERE CAST(strftime('%s', hour_bucket) AS INTEGER) BETWEEN ? AND ? GROUP BY ticker) x
          ON x.ticker = m.ticker AND x.hb = m.hour_bucket""", (start, end))
    return agg.merge(last, on="ticker", how="left")


def future_return_for_ticker(db_path, ticker, start, end):
    """Mean future return (%) and share of positive returns per ticker and horizon (long format); `ticker` is one
    symbol or several."""
    tf, symbols = _only(ticker, "ticker")
    parts = []
    for h in HORIZONS:
        col = "future_return_" + h
        df = _read(db_path, """
            SELECT ticker, COUNT(%s) AS n, AVG(%s) AS mean_return_pct,
                   AVG(CASE WHEN %s > 0 THEN 1.0 WHEN %s < 0 THEN 0.0 END) AS share_up
            FROM market_hourly_features
            WHERE CAST(strftime('%%s', hour_bucket) AS INTEGER) BETWEEN ? AND ?%s GROUP BY ticker"""
                   % (col, col, col, col, tf), (start, end, *symbols))       # '%%s' is the literal %s of strftime after formatting
        df["horizon"] = h
        parts.append(df)
    return pd.concat(parts, ignore_index=True)


def future_return_by_group(db_path, start, end, tickers=None):
    """Mean future return (%) and share of positive returns per asset class and horizon (long format), over the chosen
    tickers when `tickers` is given."""
    tf, symbols = _only(tickers)
    parts = []
    for h in HORIZONS:
        col = "future_return_" + h
        df = _read(db_path, """
            SELECT k.AssetClass AS big_group, COUNT(m.%s) AS n, AVG(m.%s) AS mean_return_pct,
                   AVG(CASE WHEN m.%s > 0 THEN 1.0 WHEN m.%s < 0 THEN 0.0 END) AS share_up
            FROM market_hourly_features m JOIN DimTicker k ON k.TickerSymbol = m.ticker
            WHERE CAST(strftime('%%s', m.hour_bucket) AS INTEGER) BETWEEN ? AND ?%s GROUP BY k.AssetClass"""
                   % (col, col, col, col, tf), (start, end, *symbols))
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


def sentiment_hourly(db_path, tickers, start, end, communities, model="VADER+FinBERT", variant="all"):
    """Per ticker-hour sums of the texts of the chosen communities (reddit_hourly_community) scored by `model`
    ('VADER+FinBERT' = the final sentiment, 'VADER' or 'FinBERT'), from 24 hours before `start` (the Z-score needs
    them).  `variant` = which texts enter the hour ('all', 'strong' = |score| >= 0.05, 'quality' = |score| >= 0.30; filtered per
    text).  Recombine with `sentiment_frame`."""
    tf, symbols = _only(tickers, "ticker")
    marks = ",".join("?" * len(communities))
    return _read(db_path, """
        SELECT ticker, hour_utc, SUM(texts) AS texts, SUM(sentiment_sum) AS sentiment_sum, SUM(pos_n) AS pos_n,
               SUM(neg_n) AS neg_n, SUM(neu_n) AS neu_n
        FROM reddit_hourly_community
        WHERE model = ? AND variant = ? AND hour_utc BETWEEN ? AND ? AND subreddit IN (%s)%s GROUP BY ticker, hour_utc"""
                 % (marks, tf), (model, variant, start - 86400, end, *communities, *symbols))


def global_hourly(db_path, start, end, communities, model="VADER+FinBERT", variant="all"):
    """The same sums for EVERY text of the market (not only those that mention a ticker), from 24 hours before `start`, as one
    series with the ticker name 'ALL' (reddit_hourly_global).  Recombine with `sentiment_frame`."""
    marks = ",".join("?" * len(communities))
    return _read(db_path, """
        SELECT 'ALL' AS ticker, hour_utc, SUM(texts) AS texts, SUM(sentiment_sum) AS sentiment_sum, SUM(pos_n) AS pos_n,
               SUM(neg_n) AS neg_n, SUM(neu_n) AS neu_n
        FROM reddit_hourly_global
        WHERE model = ? AND variant = ? AND hour_utc BETWEEN ? AND ? AND subreddit IN (%s) GROUP BY hour_utc"""
                 % marks, (model, variant, start - 86400, end, *communities))


def sentiment_frame(sent, start, end, combined=False):
    """KPIs of table 15 per series and hour on the full hourly grid start..end, from the sums of `sentiment_hourly`.
    Series = each ticker, or one series 'รวม' (all the tickers summed) when `combined`.  An hour without text has
    texts = 0 and NULL sentiment / ratios / majority / momentum (never 0).  Rules as in the proposal:
    sentiment_mean = sum(final_sentiment) / texts, momentum = this hour - previous hour (both need text), Volume Z-score
    over the 24 hours before (current hour excluded), majority = most frequent status (ties: neutral, positive, negative)."""
    cols = ["texts", "sentiment_sum", "pos_n", "neg_n", "neu_n"]
    out_cols = ["series", "hour_utc", "texts", "sentiment_mean", "pos_ratio", "neg_ratio", "neu_ratio", "majority",
                "zscore", "momentum"]
    if sent.empty:
        return pd.DataFrame(columns=out_cols)
    if combined:
        sent = sent.assign(ticker="รวม").groupby(["ticker", "hour_utc"], as_index=False)[cols].sum()
    grid = pd.Index(range(int(start) - 86400, int(end) + 3600, 3600), name="hour_utc")
    wide = {c: sent.pivot_table(index="hour_utc", columns="ticker", values=c, aggfunc="sum").reindex(grid) for c in cols}
    texts = wide["texts"].fillna(0)
    z, _ = volume_features(texts)
    has = texts > 0
    mean = wide["sentiment_sum"] / texts.where(has)
    counts = np.stack([wide["neu_n"].fillna(0).to_numpy(), wide["pos_n"].fillna(0).to_numpy(), wide["neg_n"].fillna(0).to_numpy()])
    names = np.array(["neutral", "positive", "negative"], dtype=object)           # argmax takes the first maximum = the tie rule
    majority = pd.DataFrame(np.where(has.to_numpy(), names[counts.argmax(axis=0)], None), index=grid, columns=texts.columns)
    frames = {"texts": texts, "sentiment_mean": mean, "pos_ratio": wide["pos_n"] / texts.where(has),
              "neg_ratio": wide["neg_n"] / texts.where(has), "neu_ratio": wide["neu_n"] / texts.where(has),
              "majority": majority, "zscore": z, "momentum": mean - mean.shift(1)}
    long = pd.concat({k: v.stack(future_stack=True) for k, v in frames.items()}, axis=1).rename_axis(["hour_utc", "series"]).reset_index()
    return long[(long.hour_utc >= start) & (long.hour_utc <= end)][out_cols].reset_index(drop=True)


REDDIT_MEASURES = ("reddit_volume", "sentiment_mean", "pos_ratio", "neg_ratio", "neu_ratio", "zscore", "momentum")


def mask_majority(df, statuses, majority="majority_final_status"):
    """DimMajoritySentiment filter on an hourly frame: hours whose majority status is not in `statuses` lose ALL their
    Reddit measures (volume, sentiment, ratios, Z-score, momentum, the status itself) and become NULL, never 0.
    Hours without text (no status) and the market columns (close, volume) are kept."""
    keep = df[majority].isin(statuses) | df[majority].isna()
    out = df.copy()
    for col in (*REDDIT_MEASURES, majority):
        if col in out:
            out[col] = out[col].where(keep)
    return out


# Fixed sentiment levels (not quantiles): the neutral band (+-0.05, etl.common.NEUTRAL_BAND) and the quality cut (+-0.30,
# configs/detection.yaml sentiment_thresholds) of the proposal.  Edges follow status_of: s >= 0.05 is positive and
# s <= -0.05 is negative, so the neutral band is the open interval (-0.05, 0.05).
QUALITY_CUT = 0.30
SENTIMENT_LEVELS = (("ลบมาก", "< -0.30"), ("ลบ", "-0.30 ถึง -0.05"), ("เป็นกลาง", "-0.05 ถึง +0.05 (ไม่รวมขอบ)"),
                    ("บวก", "+0.05 ถึง +0.30"), ("บวกมาก", "> +0.30"))


def sentiment_level(score):
    """0..4 index into SENTIMENT_LEVELS for a Sentiment Score (NaN stays NaN)."""
    s = pd.Series(score, dtype=float)
    lvl = pd.Series(np.nan, index=s.index)
    lvl[s < -QUALITY_CUT] = 0
    lvl[(s >= -QUALITY_CUT) & (s <= -NEUTRAL_BAND)] = 1
    lvl[(s > -NEUTRAL_BAND) & (s < NEUTRAL_BAND)] = 2
    lvl[(s >= NEUTRAL_BAND) & (s <= QUALITY_CUT)] = 3
    lvl[s > QUALITY_CUT] = 4
    return lvl


def sentiment_buckets(df, value, sentiment="sentiment_mean", min_total=50):
    """Does higher sentiment go with a higher `value` (a return)?  The samples (one per ticker-hour with text) are put into
    the five fixed SENTIMENT_LEVELS and the mean of `value` is taken in each, with its 95% interval (mean +- 1.96 standard
    errors).  -> DataFrame(bucket 0..4, n, sent_mean, mean, ci_lo, ci_hi), always five rows (n = 0 and NaN when a level is
    empty); empty frame when there are fewer than `min_total` samples."""
    out_cols = ["bucket", "n", "sent_mean", "mean", "ci_lo", "ci_hi"]
    d = df[[sentiment, value]].dropna()
    if len(d) < min_total:
        return pd.DataFrame(columns=out_cols)
    d = d.assign(bucket=sentiment_level(d[sentiment].values).values)
    g = d.groupby("bucket").agg(n=(value, "size"), sent_mean=(sentiment, "mean"), mean=(value, "mean"), sd=(value, "std"))
    g = g.reindex([0, 1, 2, 3, 4]).rename_axis("bucket").reset_index()
    g["n"] = g.n.fillna(0).astype(int)
    se = g.sd / np.sqrt(g.n.where(g.n > 0))
    g["ci_lo"], g["ci_hi"] = g["mean"] - 1.96 * se, g["mean"] + 1.96 * se
    return g[out_cols]


def shifted_return(prices, lag, column="log_return"):
    """The Current Return of the hour t + `lag` for every row (ticker, hour_utc = t): lag < 0 looks back (the hours before
    the Reddit hour), lag = 0 is the same hour, lag > 0 looks forward.  NULL when that hour has no return (market closed,
    gap in the bars).  -> Series aligned with prices.index."""
    lookup = prices.set_index(["ticker", "hour_utc"])[column]
    keys = pd.MultiIndex.from_arrays([prices.ticker, prices.hour_utc + lag * 3600])
    return pd.Series(lookup.reindex(keys).values, index=prices.index)


def past_return(prices, hours):
    """Return over the `hours` hours BEFORE the Reddit hour (sum of the hourly log returns of t-hours .. t-1, in %).
    NULL when any of those hours is missing."""
    parts = pd.concat([shifted_return(prices, -k) for k in range(1, hours + 1)], axis=1)
    return parts.sum(axis=1, min_count=hours).where(parts.notna().all(axis=1))


def lag_correlation(samples, lags=range(-6, 7), sentiment="sentiment_mean"):
    """Who moves first?  Spearman correlation between the Sentiment Score of the Reddit hour t and the Current Return of the
    hour t + lag, for every lag.  `samples` has ticker, hour_utc, the sentiment column and the prices' log_return (every
    ticker-hour with text).  Negative lags: the price moved BEFORE the text; positive lags: AFTER it.
    -> DataFrame(lag, rho, n, ci_lo, ci_hi); the interval is the Fisher-z 95% interval."""
    rows = []
    for lag in lags:
        d = pd.DataFrame({"s": samples[sentiment], "r": shifted_return(samples, lag)}).dropna()
        n = len(d)
        rho = d.s.corr(d.r, method="spearman") if n > 3 else np.nan
        half = 1.96 / np.sqrt(n - 3) if n > 3 else np.nan
        z = np.arctanh(rho) if n > 3 and abs(rho) < 1 else np.nan
        rows.append({"lag": lag, "rho": rho, "n": n, "ci_lo": np.tanh(z - half), "ci_hi": np.tanh(z + half)})
    return pd.DataFrame(rows)


def return_buckets(df, past, sentiment="sentiment_mean", bins=5, min_total=50):
    """Does the price move first?  The samples are put into `bins` groups of equal size by their return BEFORE the Reddit hour
    (lowest to highest) and the average Sentiment Score of each group is taken with its 95% interval (mean +- 1.96 standard
    errors).  -> DataFrame(bucket, lo, hi, n, mean_return, mean, ci_lo, ci_hi); empty below `min_total` samples."""
    out_cols = ["bucket", "lo", "hi", "n", "mean_return", "mean", "ci_lo", "ci_hi"]
    d = df[[sentiment, past]].dropna()
    if len(d) < min_total:
        return pd.DataFrame(columns=out_cols)
    d = d.assign(bucket=pd.qcut(d[past].rank(method="first"), bins, labels=False))
    g = d.groupby("bucket").agg(lo=(past, "min"), hi=(past, "max"), n=(sentiment, "size"), mean_return=(past, "mean"),
                                mean=(sentiment, "mean"), sd=(sentiment, "std")).reset_index()
    se = g.sd / np.sqrt(g.n)
    g["ci_lo"], g["ci_hi"] = g["mean"] - 1.96 * se, g["mean"] + 1.96 * se
    return g[out_cols]


def threshold_mask(df, z_min, s_min, z="zscore", sentiment="sentiment_mean"):
    """DimDetectionConfig on the hours of a frame: True where the Reddit Volume Z-score is ABOVE `z_min` and the
    |Sentiment Score| is at least `s_min`.  A threshold of 0 switches that test off (every hour passes it, also an hour with a
    negative Z-score or without text); with both at 0 every hour passes.  Hours with no text never pass a positive threshold."""
    ok = pd.Series(True, index=df.index)
    if z_min > 0:
        ok &= df[z] > z_min
    if s_min > 0:
        ok &= df[sentiment].abs() >= s_min
    return ok


def mask_thresholds(df, z_min, s_min, majority="majority_final_status"):
    """The thresholds as a filter of the hourly frame: hours that fail lose ALL their Reddit measures (volume, sentiment,
    ratios, Z-score, momentum, majority status) and become NULL, never 0; price and market volume stay.  With both thresholds
    at 0 the frame is returned unchanged."""
    keep = threshold_mask(df, z_min, s_min)
    out = df.copy()
    for col in (*REDDIT_MEASURES, majority):
        if col in out:
            out[col] = out[col].where(keep)
    return out


def vote_shares(df, rule=None, majority="majority_final_status"):
    """Majority vote of the hours: per period (`rule` = an entry of common.RESAMPLE; None = every hour on its own) the
    number of hours whose majority status is positive / negative / neutral and its share of the hours that have a status.
    Hours without text (no status) and hours removed by the majority filter are not counted: a status that was ticked
    out has no hours, so its share is 0.  -> DataFrame(time, status, hours, share)."""
    votes = df.loc[df[majority].notna(), ["time", majority]]
    if votes.empty:
        return pd.DataFrame(columns=["time", "status", "hours", "share"])
    key = "time" if rule is None else pd.Grouper(key="time", freq=rule["rule"], **{k: v for k, v in rule.items() if k != "rule"})
    counts = votes.groupby([key, majority]).size().rename("hours").reset_index().rename(columns={majority: "status"})
    counts["share"] = counts.hours / counts.groupby("time").hours.transform("sum")
    return counts


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


HORIZON_LABELS = {"log_return": "Current Return", "1h": "1h", "2h": "2h", "3h": "3h", "6h": "6h", "12h": "12h"}


PANEL_VARIANTS = {"all": "ทุกข้อความ", "strong": "ความรู้สึกชัดเจน (|s| ≥ 0.05)", "quality": "ความรู้สึกคุณภาพ (|s| ≥ 0.30)",
                  "spike": "ปริมาณพุ่ง (Z-score > 1.5)", "baseline": "Baseline ทิศทางสุ่ม"}
PANEL_FAMILIES = {"global": "ข้อความทั้งตลาด (ความรู้สึกรวม ใช้กับทุกสินทรัพย์)", "Ticker": "เฉพาะข้อความที่พูดถึงสินทรัพย์นั้นโดยตรง"}   # the first is the default
STORED_PANELS = {"panel_global": "Global", "panel_global_strong": "Global strong", "panel_global_quality": "Global quality",
                 "panel_global_spike": "Global spike", "panel_Ticker": "Ticker", "panel_Ticker_strong": "Ticker strong",
                 "panel_Ticker_quality": "Ticker quality", "panel_Ticker_spike": "Ticker spike", "panel_baseline": "Baseline"}


# the variables of the Logistic Regression (proposal table 13 and 7.4: six variable groups): Thai name and group
VARIABLE_GROUPS = {"Level": "Level (ระดับความรู้สึก)", "Direction": "Direction (ทิศทาง บวก/ลบ)", "Vote": "Vote (โหวตส่วนใหญ่)",
                   "Volume": "Volume (ปริมาณโพสต์)", "Lag": "Lag (ความรู้สึกย้อนหลัง)", "Momentum": "Momentum (การเปลี่ยนแปลง)",
                   "Random": "Random (ทิศทางสุ่ม)"}
VARIABLES = {"sentiment_mean": ("ค่าความรู้สึกเฉลี่ย", "Level"),
             "sentiment_abs_mean": ("ความแรงของความรู้สึก (ค่าสัมบูรณ์)", "Level"),
             "pos_ratio": ("สัดส่วนความคิดเห็นเชิงบวก", "Direction"),
             "neg_ratio": ("สัดส่วนความคิดเห็นเชิงลบ", "Direction"),
             "majority_final_status_num": ("ประเภทความรู้สึกส่วนใหญ่ บวก +1 กลาง 0 ลบ −1", "Vote"),
             "voter_agreement_ratio": ("สัดส่วนข้อความที่ตรงกับประเภทส่วนใหญ่", "Vote"),
             "reddit_volume_zscore_24": ("Reddit Volume Z-score", "Volume"),
             "sentiment_lag_1h": ("ความรู้สึก 1 ชั่วโมงก่อนหน้า", "Lag"), "sentiment_lag_2h": ("ความรู้สึก 2 ชั่วโมงก่อนหน้า", "Lag"),
             "sentiment_lag_3h": ("ความรู้สึก 3 ชั่วโมงก่อนหน้า", "Lag"), "sentiment_lag_6h": ("ความรู้สึก 6 ชั่วโมงก่อนหน้า", "Lag"),
             "sentiment_lag_12h": ("ความรู้สึก 12 ชั่วโมงก่อนหน้า", "Lag"),
             "sentiment_momentum_1h": ("การเปลี่ยนแปลงของความรู้สึกจากชั่วโมงก่อน", "Momentum"),
             "random_direction": ("ทิศทางสุ่ม +1/−1", "Random")}


def effect_points(coef):
    """A standardized coefficient of the Logistic Regression as a change of the chance that the price goes UP, in percentage points
    for one standard deviation more of the variable.  The slope of the logistic curve at 50% is 1/4, so the change is about
    coef / 4 x 100 points; it holds near 50%, where every model of this project lives (the AUC is about 0.5)."""
    return np.asarray(coef, dtype=float) * 25.0


def effect_summary(coefs):
    """Per variable: the mean effect (percentage points, see `effect_points`) over the FUTURE horizons 1h .. 12h and in how many of
    those horizons the sign is the mean's sign.  `coefs` has `column`, `horizon`, `value`.  -> DataFrame(column, effect, same_sign, horizons)."""
    future = coefs[coefs.horizon != "log_return"].copy()
    future["effect"] = effect_points(future.value)
    rows = []
    for column, part in future.groupby("column", sort=False):
        mean = part.effect.mean()
        rows.append({"column": column, "effect": mean, "same_sign": int((np.sign(part.effect) == np.sign(mean)).sum()), "horizons": len(part)})
    return pd.DataFrame(rows, columns=["column", "effect", "same_sign", "horizons"])


def variable_label(column):
    """Label of a Logistic Regression variable: its column name, the Thai name in brackets and its variable group."""
    thai, group = VARIABLES.get(column, ("", ""))
    return "%s (%s) · กลุ่ม %s" % (column, thai, group) if thai else column


def panel_name(variant, family="Ticker"):
    """`analysis_results` name of the panel of a variant (a key of PANEL_VARIANTS) and a family ('Ticker' or 'global')."""
    if variant == "baseline":
        return "panel_baseline"
    return "panel_%s%s" % (family, "" if variant == "all" else "_" + variant)


def bh_adjust(p):
    """Benjamini-Hochberg adjusted p-values of an array (NaN stays NaN and is not counted as a test)."""
    p = np.asarray(p, dtype=float)
    out = np.full(p.shape, np.nan)
    ok = np.where(~np.isnan(p))[0]
    if len(ok) == 0:
        return out
    order = ok[np.argsort(p[ok])]
    scaled = p[order] * len(ok) / np.arange(1, len(ok) + 1)
    out[order] = np.minimum(np.minimum.accumulate(scaled[::-1])[::-1], 1.0)
    return out


def panel_samples(base, own, returns, family, variant, statuses, z_min, s_min, seed=42, spike_z=1.5):
    """The ticker-hours of ONE panel of the proposal (table 12), live, after every filter of the dashboard.
    `base` = `sentiment_frame` of ALL the texts of the family (series = the tickers for the family 'Ticker', the one series 'ALL'
    for 'global'); `own` = the same for the texts of the variant ('strong' / 'quality'), else None; `returns` = DataFrame(ticker,
    hour_utc, log_return, future_return_*).
    The predictor is the Sentiment Score of the variant's texts (per-text filter, as in `reddit_hourly`); the Volume Z-score and the
    majority status are always those of ALL the texts of the hour.  An hour is kept when its majority status is in `statuses`, it passes
    `threshold_mask` (Z-score above `z_min`, |predictor| at least `s_min`; 0 = off) and has a predictor; the variant 'spike' also
    needs a Z-score above `spike_z` (that ticker's own volume, or the volume of the whole market for 'global').  'global' uses the
    same market-wide hour for every ticker.  'baseline' = the rows of the global panel with a random direction (+1 / -1, fixed seed)
    instead of the sentiment: the 'no signal' yardstick.  -> DataFrame(ticker, hour_utc, sentiment_mean, zscore, returns...)."""
    b = base[["series", "hour_utc", "zscore", "majority", "sentiment_mean"]].rename(columns={"series": "ticker"})
    if own is not None and variant in ("strong", "quality"):
        v = own[["series", "hour_utc", "sentiment_mean"]].rename(columns={"series": "ticker", "sentiment_mean": "predictor"})
        b = b.drop(columns="sentiment_mean").merge(v, on=["ticker", "hour_utc"], how="left").rename(columns={"predictor": "sentiment_mean"})
    keep = b.majority.isin(statuses) & threshold_mask(b, z_min, s_min) & b.sentiment_mean.notna()
    if variant == "spike":
        keep &= b.zscore > spike_z
    b = b[keep]
    if family == "global" or variant == "baseline":
        samples = returns.merge(b.drop(columns="ticker"), on="hour_utc")
    else:
        samples = returns.merge(b, on=["ticker", "hour_utc"])
    if variant == "baseline":
        samples = samples.sort_values(["ticker", "hour_utc"]).reset_index(drop=True)
        samples["sentiment_mean"] = np.random.default_rng(seed).choice([-1.0, 1.0], size=len(samples))
    return samples


STAT_TARGETS = ("log_return", "1h", "2h", "3h", "6h", "12h")      # Current Return, then the future returns of the proposal
STAT_COLUMN = {"log_return": "log_return", **{h: "future_return_" + h for h in HORIZONS}}
STAT_COLUMNS = ["ticker", "target", "n", "spearman_rho", "spearman_p", "spearman_bh", "pearson_rho", "pearson_p", "pearson_bh",
                "win_n", "win_hits", "winrate", "win_p", "win_bh"]


def stat_table(samples, min_n=30, sentiment="sentiment_mean"):
    """A1 / A2 computed live on the ticker-hours of a panel: per ticker and target (the Current Return and the future returns
    1h .. 12h) the Spearman and Pearson correlation of the predictor with the return and the Historical Win Rate (share of hours in
    which the sign of the predictor equals the direction of the return; for the Current Return that is the same-hour co-movement), each with its p-value (Binomial against 50% for the win
    rate) and the Benjamini-Hochberg p-value over the tickers.  Pairs with a NULL are dropped (never 0); a return of exactly 0 or a
    predictor of exactly 0 is not a direction; fewer than `min_n` pairs -> NaN.
    `samples` has `ticker`, the predictor column and `log_return`, `future_return_1h` .. `future_return_12h`.
    -> DataFrame(STAT_COLUMNS), one row per ticker and target (target = a key of STAT_TARGETS)."""
    rows = []
    for ticker, part in samples.groupby("ticker"):
        for target in STAT_TARGETS:
            pair = part[[sentiment, STAT_COLUMN[target]]].dropna()
            pair.columns = ["s", "r"]
            row = dict.fromkeys(STAT_COLUMNS[3:], np.nan)
            row.update(ticker=ticker, target=target, n=len(pair))
            if len(pair) >= min_n and pair.s.nunique() > 1 and pair.r.nunique() > 1:
                sp = stats.spearmanr(pair.s, pair.r)
                pe = stats.pearsonr(pair.s, pair.r)
                row.update(spearman_rho=float(sp.statistic), spearman_p=float(sp.pvalue),
                           pearson_rho=float(pe.statistic), pearson_p=float(pe.pvalue))
            directional = pair[(pair.s != 0) & (pair.r != 0)]      # for the Current Return it is the same-hour co-movement, not a prediction
            if len(directional) >= min_n:
                hits = int((np.sign(directional.s) == np.sign(directional.r)).sum())
                row.update(win_n=len(directional), win_hits=hits, winrate=100.0 * hits / len(directional),
                           win_p=float(stats.binomtest(hits, len(directional), 0.5).pvalue))
            rows.append(row)
    out = pd.DataFrame(rows, columns=STAT_COLUMNS)
    if out.empty:
        return out
    for p_col, bh_col in (("spearman_p", "spearman_bh"), ("pearson_p", "pearson_bh"), ("win_p", "win_bh")):
        out[bh_col] = out.groupby("target")[p_col].transform(lambda s: pd.Series(bh_adjust(s.to_numpy()), index=s.index))
    return out


def stored_stat_table(db_path, panel="panel_Ticker"):
    """A1 / A2 of the proposal's system 7.4 for one of its nine panels, as stored in `analysis_results` (the whole data set,
    so the time / community / majority filters do not change it), in the same shape as `stat_table`.  NULL = not enough
    data (n < 30)."""
    predictor, win_predictor = ("random_direction",) * 2 if panel == "panel_baseline" else ("sentiment_mean", "sign(sentiment_mean)")
    cor = _read(db_path, """
        SELECT ticker, horizon AS target, metric_name AS method, metric_value AS rho, p_value AS p, p_value_bh AS bh, n_samples AS n
        FROM analysis_results WHERE analysis = 'correlation' AND panel_name = ? AND level = 'ticker' AND predictor = ?
          AND metric_name IN ('pearson', 'spearman')""", (panel, predictor))
    win = _read(db_path, """
        SELECT ticker, horizon AS target, metric_value * 100.0 AS winrate, p_value AS win_p, p_value_bh AS win_bh, n_samples AS win_n
        FROM analysis_results WHERE analysis = 'winrate' AND panel_name = ? AND level = 'ticker' AND predictor = ?
          AND metric_name = 'winrate'""", (panel, win_predictor))
    out = None
    for method in ("spearman", "pearson"):
        part = cor[cor.method == method].rename(columns={"rho": method + "_rho", "p": method + "_p", "bh": method + "_bh"}).drop(columns="method")
        part = part.rename(columns={"n": "n_" + method})
        out = part if out is None else out.merge(part, on=["ticker", "target"], how="outer")
    out["n"] = out[["n_spearman", "n_pearson"]].max(axis=1)
    out = out.drop(columns=["n_spearman", "n_pearson"]).merge(win, on=["ticker", "target"], how="outer")
    out["win_hits"] = np.round(out.winrate / 100.0 * out.win_n)
    for col in STAT_COLUMNS:
        if col not in out:
            out[col] = np.nan
    out["n"] = out.n.fillna(out.win_n)
    return out[STAT_COLUMNS]


def logistic_results(db_path):
    """A3: Logistic Regression (TimeSeriesSplit 5 folds, gap 12) of the up/down of the future return, for the nine panels: AUC,
    its spread over the folds, standardized coefficients and the importance of each variable group, for all tickers pooled
    ('all') and per asset class ('big_group').  -> DataFrame(panel, level, big_group, horizon, metric, value, n, status)."""
    return _read(db_path, """
        SELECT panel_name AS panel, level, big_group, horizon, metric_name AS metric, metric_value AS value,
               n_samples AS n, status
        FROM analysis_results WHERE analysis = 'logistic' AND level IN ('all', 'big_group')""")


def significant_share(df, p="p_value", alpha=0.05):
    """(tests with p < alpha, tests that have a p-value): rows without a p-value (not enough data) are not tests."""
    ok = df[p].dropna()
    return int((ok < alpha).sum()), int(len(ok))


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
               majority_final_status, future_return_1h, future_return_2h, future_return_3h, future_return_6h, future_return_12h
        FROM merged_hourly_panel
        WHERE scope = 'ticker' AND variant = 'all' AND has_reddit_data = 1 AND reddit_volume >= ?
          AND reddit_volume_zscore_24 > ? AND ABS(sentiment_mean) >= ? AND hour_utc BETWEEN ? AND ?
        ORDER BY hour_utc DESC""", (min_texts, z_min, s_min, start, end))
