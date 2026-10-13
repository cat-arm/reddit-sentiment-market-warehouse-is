"""W3: fill the star-schema fact table `FactMarketSentiment` (proposal figure 4 / tables 14-15).

GRAIN (decision recorded in TASKS W3): one row per  hour x ticker  -  the same size as FactMarketPrice.
The figure also has DetectionConfigID, but a win rate is a summary over MANY hours, so multiplying every hour by the
30 detection configs would only repeat the same numbers 30 times (~7.5 M rows).  So:

  TimeID             DimTime row of the (floored) hour             <- merged_hourly_panel.hour_utc
  TickerID           DimTicker row                                 <- merged_hourly_panel.ticker
  SentimentSourceID  the 'ALL' row of DimSentimentSource  (sentiment is pooled over the 6 communities)
  DetectionConfigID  ONE default config (z = 1.5, sentiment = 0.30, horizon = 1h, see DEFAULT_CONFIG); the other 29
                     configs stay in DimDetectionConfig and are evaluated on demand by the signal stage (G),
                     whose results go to `signal_events` with their own config_id
  MajorityID         majority_final_status of that ticker-hour  (NULL when no text, never a made-up 'neutral')
  close, volume, future_return_*        price side, straight from the panel (M1 already floored/aligned them)
  sentiment_mean, pos/neg/neu_ratio, reddit_volume
                     the TICKER-level sentiment (only texts that mention the ticker, variant 'all').
                     NULL = no text that hour.  NULL is NOT 0 (0 means neutral).  reddit_volume is 0 in that case.
  winrate_<h>        Historical Win Rate in PERCENT (table 14 unit) of the ticker, taken from analysis A2:
                     panel_Ticker, predictor sign(sentiment_mean).  NULL when A2 says insufficient_data (n < 30).
  winrate_p_value_<h>  the two-sided Binomial p-value of that win rate vs the random baseline (A2)

WARNING (leakage): winrate_* / winrate_p_value_* are FULL-SAMPLE summaries of the ticker, repeated on every one of its
rows.  They are for ranking and display on the dashboard only; never use them as model inputs or as a signal known
"at that hour" - they contain information from the future of every row they sit on.

Run order: etl.merge_panel, analysis.winrate (needs `analysis_results`), then this module.  Rebuilt on every run.

Usage:  python -m etl.load_fact_market_sentiment [--db output/reddit.sqlite3]
"""

import argparse
import sys

from etl.common import DEFAULT_DB, connect, load_yaml
from etl.seed_dims import seed

HORIZONS = ("1h", "2h", "3h", "6h", "12h")
# (Z-score threshold, sentiment threshold, horizon) stored in the fact; must exist in DimDetectionConfig.
# 1.5 = the spike cut of panel_*_spike, 0.30 = the quality cut of panel_*_quality (proposal table 12).
_DEFAULT = load_yaml("detection.yaml")["default_config"]          # configs/detection.yaml is the single source
DEFAULT_CONFIG = (_DEFAULT["zscore_threshold"], _DEFAULT["sentiment_threshold"], _DEFAULT["horizon"])


def _winrate_columns():
    """SQL fragments that pivot the A2 rows (one row per horizon) into one row per ticker."""
    pick = []
    for h in HORIZONS:
        # status = 'ok' guard: an 'insufficient_data' row has NULL value anyway, but the guard makes it explicit.
        pick.append("MAX(CASE WHEN horizon = '%s' AND status = 'ok' THEN metric_value * 100.0 END) AS winrate_%s" % (h, h))
    for h in HORIZONS:
        pick.append("MAX(CASE WHEN horizon = '%s' AND status = 'ok' THEN p_value END) AS winrate_p_value_%s" % (h, h))
    return ", ".join(pick)


def load(db):
    """Rebuild FactMarketSentiment from merged_hourly_panel + analysis_results; returns a small summary dict."""
    seed(db)                                              # make sure schema + dimensions exist
    z, s, horizon = DEFAULT_CONFIG
    config = db.execute("SELECT ConfigID FROM DimDetectionConfig WHERE ZscoreThreshold = ? AND SentimentThreshold = ? "
                        "AND Horizon = ?", (z, s, horizon)).fetchone()
    source = db.execute("SELECT SourceID FROM DimSentimentSource WHERE Subreddit = 'ALL'").fetchone()
    if config is None or source is None:
        raise SystemExit("default detection config %s or the 'ALL' sentiment source is missing from the dimensions"
                         % (DEFAULT_CONFIG,))
    base = db.execute("SELECT COUNT(*) FROM merged_hourly_panel WHERE scope = 'ticker' AND variant = 'all'").fetchone()[0]

    db.execute("DELETE FROM FactMarketSentiment")
    db.execute("""
        INSERT INTO FactMarketSentiment (
            TimeID, TickerID, SentimentSourceID, DetectionConfigID, MajorityID, close, volume,
            sentiment_mean, pos_ratio, neg_ratio, neu_ratio, reddit_volume,
            future_return_1h, future_return_2h, future_return_3h, future_return_6h, future_return_12h,
            winrate_1h, winrate_2h, winrate_3h, winrate_6h, winrate_12h,
            winrate_p_value_1h, winrate_p_value_2h, winrate_p_value_3h, winrate_p_value_6h, winrate_p_value_12h)
        SELECT t.TimeID, k.TickerID, ?, ?, m.MajorityID, p.close, p.volume,
               p.sentiment_mean, p.pos_ratio, p.neg_ratio, p.neu_ratio, p.reddit_volume,
               p.future_return_1h, p.future_return_2h, p.future_return_3h, p.future_return_6h, p.future_return_12h,
               w.winrate_1h, w.winrate_2h, w.winrate_3h, w.winrate_6h, w.winrate_12h,
               w.winrate_p_value_1h, w.winrate_p_value_2h, w.winrate_p_value_3h, w.winrate_p_value_6h,
               w.winrate_p_value_12h
        FROM merged_hourly_panel p
        -- DimTime keeps its key as ISO text; the panel keeps epoch seconds, so convert to the same text format
        JOIN DimTime t ON t.ts_utc = strftime('%Y-%m-%dT%H:%M:%S+00:00', p.hour_utc, 'unixepoch')
        JOIN DimTicker k ON k.TickerSymbol = p.ticker
        LEFT JOIN DimMajoritySentiment m ON m.MajorityStatus = p.majority_final_status   -- NULL status -> NULL id
        LEFT JOIN (SELECT ticker, """ + _winrate_columns() + """
                   FROM analysis_results
                   WHERE analysis = 'winrate' AND panel_name = 'panel_Ticker' AND level = 'ticker'
                     AND predictor = 'sign(sentiment_mean)' AND metric_name = 'winrate'
                   GROUP BY ticker) w ON w.ticker = p.ticker
        WHERE p.scope = 'ticker' AND p.variant = 'all'""", (source[0], config[0]))
    db.commit()

    loaded = db.execute("SELECT COUNT(*) FROM FactMarketSentiment").fetchone()[0]
    if loaded != base:                                    # a lost row means a broken time/ticker join
        raise SystemExit("FactMarketSentiment has %d rows but the panel has %d" % (loaded, base))
    stats = db.execute("""SELECT SUM(sentiment_mean IS NOT NULL), SUM(winrate_1h IS NOT NULL),
                                 SUM(winrate_12h IS NOT NULL), SUM(MajorityID IS NOT NULL) FROM FactMarketSentiment""").fetchone()
    return {"fact_rows": loaded, "rows_with_sentiment": stats[0], "rows_with_winrate_1h": stats[1],
            "rows_with_winrate_12h": stats[2], "rows_with_majority": stats[3], "config_id": config[0]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args(argv)
    db = connect(args.db)
    try:
        print(load(db))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
