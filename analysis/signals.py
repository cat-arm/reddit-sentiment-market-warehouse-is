"""G2 + G3: data-driven signal detection (proposal 7.6) -> `signal_events`, `signal_summary`, view `v_signal_list`.

What a "signal" is  (all per ticker-hour, using the TICKER-level Reddit sentiment, i.e. only texts that mention it):
    volume_spike              Reddit Volume Z-score  >  z threshold               (sentiment not clearly directional)
    positive_sentiment_spike  sentiment_mean         >=  +sentiment threshold      (no volume spike)
    negative_sentiment_spike  sentiment_mean         <=  -sentiment threshold      (no volume spike)
    combined_signal           volume spike AND a clearly directional sentiment      (proposal 7.6 "combined")
  A sentiment signal needs >= rules.min_texts_for_sentiment texts in that hour (EXTENSION, avoids a "mean of 1 text").
  An hour without Reddit data can never be a signal (sentiment_mean and z-score are NULL there, never 0).
  The z-score is the same one as everywhere else: prior 24 clock hours, current hour excluded (P2).

signal_level (low / medium / high) is NOT defined by the proposal; the rule is written in configs/detection.yaml
(EXTENSION): points from how far the hour is beyond the thresholds, capped at 3, 1 = low, 2 = medium, 3 = high.

Storage design (see TASKS G1): the 6 combinations of (z threshold x sentiment threshold) are PRECOMPUTED into
`signal_events`; the 5 horizons only change which historical statistic is attached, so they are added by the view
`v_signal_list` (= proposal table 18: timestamp, Ticker, Big_Group, sentiment_mean, Reddit_volume, zscore, horizon,
winrate, correlation_value, signal_type, signal_level).  That avoids storing 5 identical copies of every signal.

G3 - historical statistics attached to a signal come from analysis A1/A2 of the SAME ticker, panel_Ticker,
predictor sentiment_mean: win rate in % (+ its Binomial p-value) and Spearman correlation with the future return of
the config's horizon.  They are FULL-SAMPLE summaries shown as context; they do not confirm any return and are not
investment advice.  `stat_status` = 'insufficient_data' when A2 had fewer than 30 events for that ticker/horizon.

Usage:  python -m analysis.signals [--db output/reddit.sqlite3]
"""

import argparse
import sys

import numpy as np
import pandas as pd

from analysis import results_store
from etl.common import DEFAULT_DB, connect, load_yaml
from ingest.pipeline_logs import run_id as new_run_id

CONFIG = load_yaml("detection.yaml")
GRID = CONFIG["grid"]
RULES = CONFIG["rules"]
LEVELS = {1: "low", 2: "medium", 3: "high"}
TYPES = ("volume_spike", "positive_sentiment_spike", "negative_sentiment_spike", "combined_signal")

SCHEMA = """CREATE TABLE signal_events (
    z_threshold REAL NOT NULL, s_threshold REAL NOT NULL,
    hour_utc INTEGER NOT NULL, timestamp TEXT NOT NULL,
    ticker TEXT NOT NULL, big_group TEXT NOT NULL,
    sentiment_mean REAL, reddit_volume INTEGER NOT NULL, reddit_volume_zscore REAL, majority_final_status TEXT,
    signal_type TEXT NOT NULL, signal_level TEXT NOT NULL, run_id TEXT NOT NULL, detected_at TEXT NOT NULL)"""
INDEXES = ("CREATE INDEX signal_events_cfg ON signal_events(z_threshold, s_threshold, ticker, hour_utc)",
           "CREATE INDEX signal_events_time ON signal_events(z_threshold, s_threshold, hour_utc)")

# Table 18 + the statistics of G3.  One row per signal x horizon, joined only to the matching config / ticker.
VIEW = """CREATE VIEW v_signal_list AS
SELECT s.timestamp, s.hour_utc, s.ticker, s.big_group, s.sentiment_mean, s.reddit_volume,
       s.reddit_volume_zscore, s.majority_final_status, c.ConfigID AS config_id, s.z_threshold, s.s_threshold,
       c.Horizon AS horizon,
       w.metric_value * 100.0 AS winrate, w.p_value AS winrate_p_value, r.metric_value AS correlation_value,
       CASE WHEN w.metric_value IS NULL THEN 'insufficient_data' ELSE 'ok' END AS stat_status,
       s.signal_type, s.signal_level,
       'historical statistic of this ticker, not a confirmation of return and not investment advice' AS note
FROM signal_events s
JOIN DimDetectionConfig c ON c.ZscoreThreshold = s.z_threshold AND c.SentimentThreshold = s.s_threshold
LEFT JOIN analysis_results w ON w.analysis = 'winrate' AND w.panel_name = 'panel_Ticker' AND w.level = 'ticker'
      AND w.predictor = 'sign(sentiment_mean)' AND w.metric_name = 'winrate' AND w.ticker = s.ticker
      AND w.horizon = c.Horizon
LEFT JOIN analysis_results r ON r.analysis = 'correlation' AND r.panel_name = 'panel_Ticker' AND r.level = 'ticker'
      AND r.predictor = 'sentiment_mean' AND r.metric_name = 'spearman' AND r.ticker = s.ticker
      AND r.horizon = c.Horizon"""


def detect(df, z_th, s_th, rules=RULES):
    """Signals of one (z, s) configuration.  `df` = one row per ticker-hour of the ticker-level panel."""
    z = df["reddit_volume_zscore_24"]
    sm = df["sentiment_mean"]
    enough_text = df["reddit_volume"] >= rules["min_texts_for_sentiment"]
    volume = z > z_th                                    # NaN z compares False: no history -> no volume spike
    positive = enough_text & (sm >= s_th)
    negative = enough_text & (sm <= -s_th)
    directional = positive | negative

    kind = np.select([volume & directional, volume, positive, negative],
                     ["combined_signal", "volume_spike", "positive_sentiment_spike", "negative_sentiment_spike"], None)

    # points: 1 for crossing the threshold, +1 per extra z_step; sentiment: one point per reached cut-off
    volume_points = np.where(volume, 1 + np.floor((z.fillna(0) - z_th) / rules["z_step"]), 0)
    cuts = [s_th if c == 0.0 else c for c in rules["sentiment_levels"]]
    magnitude = sm.abs().fillna(0)
    sentiment_points = np.where(directional, sum((magnitude >= c).astype(int) for c in cuts), 0)
    points = np.minimum(np.maximum(volume_points, sentiment_points), 3).astype(int)

    out = df.loc[kind != None].copy()                    # noqa: E711  (kind is an object array with None)
    out["signal_type"] = kind[kind != None]              # noqa: E711
    out["signal_level"] = [LEVELS[p] for p in points[kind != None]]   # noqa: E711
    out["z_threshold"], out["s_threshold"] = z_th, s_th
    return out


def build(db_path=DEFAULT_DB):
    db = connect(db_path)
    try:
        # ticker-level, all texts, rows that really have Reddit data (has_reddit_data = 1)
        panel = pd.read_sql_query(
            "SELECT ticker, big_group, hour_utc, sentiment_mean, reddit_volume, reddit_volume_zscore_24, "
            "majority_final_status FROM merged_hourly_panel WHERE scope = 'ticker' AND variant = 'all' "
            "AND has_reddit_data = 1", db)
        this_run, stamp = new_run_id(), results_store.now()
        parts = [detect(panel, z, s) for z in GRID["zscore_thresholds"] for s in GRID["sentiment_thresholds"]]
        events = pd.concat(parts, ignore_index=True)
        events["timestamp"] = pd.to_datetime(events["hour_utc"], unit="s", utc=True).dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        events = events.rename(columns={"reddit_volume_zscore_24": "reddit_volume_zscore"})
        events["run_id"], events["detected_at"] = this_run, stamp
        cols = ["z_threshold", "s_threshold", "hour_utc", "timestamp", "ticker", "big_group", "sentiment_mean",
                "reddit_volume", "reddit_volume_zscore", "majority_final_status", "signal_type", "signal_level",
                "run_id", "detected_at"]
        events = events[cols].sort_values(["z_threshold", "s_threshold", "ticker", "hour_utc"])

        db.execute("DROP VIEW IF EXISTS v_signal_list")
        db.execute("DROP TABLE IF EXISTS signal_events")
        db.execute(SCHEMA)
        db.executemany("INSERT INTO signal_events VALUES (%s)" % ",".join("?" * len(cols)),
                       [tuple(None if (isinstance(v, float) and np.isnan(v)) else v for v in row)
                        for row in events.itertuples(index=False, name=None)])
        for statement in INDEXES:
            db.execute(statement)
        db.execute(VIEW)
        db.execute("DROP TABLE IF EXISTS signal_summary")      # proposal 4.6 "number of signals / assets that met the rule"
        db.execute("""CREATE TABLE signal_summary AS
            SELECT z_threshold, s_threshold, signal_type, big_group, COUNT(*) AS n_signals,
                   COUNT(DISTINCT ticker) AS n_tickers
            FROM signal_events GROUP BY 1, 2, 3, 4""")
        db.commit()
        counts = db.execute("SELECT z_threshold, s_threshold, COUNT(*), COUNT(DISTINCT ticker) FROM signal_events "
                            "GROUP BY 1, 2 ORDER BY 1, 2").fetchall()
        for z, s, n, tickers in counts:
            print("z>%.1f |sentiment|>=%.2f  signals=%-7d tickers=%d" % (z, s, n, tickers))
        return counts
    finally:
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    build(parser.parse_args(argv).db)
    return 0


if __name__ == "__main__":
    sys.exit(main())
