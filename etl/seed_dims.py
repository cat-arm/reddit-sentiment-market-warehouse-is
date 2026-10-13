"""W2 + W4: create the star-schema tables (db/schema.sql) and fill the six dimension tables.

Everything is derived from config files, nothing is typed twice:
  DimTicker             34 rows   configs/tickers.yaml
  DimSource             12 rows   6 communities (configs/subreddits.yaml) x {Post, Comment}
  DimSentimentSource     7 rows   6 communities + 'ALL' (pooled panel, an EXTENSION) x VADER+FinBERT
  DimMajoritySentiment   3 rows   positive / negative / neutral
  DimDetectionConfig    30 rows   z-score {1.5, 2.0, 2.5} x sentiment {0.05, 0.30} x horizon {1h,2h,3h,6h,12h}
                                  (the proposal's example 2.0 / 0.3 / 1h is one of them)
  DimTime            17,520 rows  every UTC hour from 2024-09-30 to 2026-09-30 (the range of market_bars)

Idempotent: INSERT OR IGNORE on natural keys, so rerunning never duplicates or renumbers rows.

Usage:
    python -m etl.seed_dims [--db output/reddit.sqlite3]
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone

from etl.common import DEFAULT_DB, ROOT, connect, load_yaml, subreddits

TIME_START = datetime(2024, 9, 30, tzinfo=timezone.utc)
TIME_END = datetime(2026, 9, 30, 23, tzinfo=timezone.utc)         # last hour, inclusive
# The detection grid lives in configs/detection.yaml (single source for the dimension, the signal engine and the dashboard)
_GRID = load_yaml("detection.yaml")["grid"]
Z_THRESHOLDS = tuple(_GRID["zscore_thresholds"])
SENTIMENT_THRESHOLDS = tuple(_GRID["sentiment_thresholds"])
HORIZONS = tuple(_GRID["horizons"])
MODEL_USED = "VADER+FinBERT"


def ts_text(moment):
    """Same text format as market_bars.timestamp_utc, e.g. 2025-03-04T14:00:00+00:00."""
    return moment.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def seed(db):
    db.executescript((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))

    tickers = load_yaml("tickers.yaml")["tickers"]
    db.executemany("INSERT OR IGNORE INTO DimTicker (AssetClass, TickerSymbol, TickerName) VALUES (?,?,?)",
                   [(spec["asset_class"], symbol, spec["name"]) for symbol, spec in tickers.items()])

    names = subreddits()
    db.executemany("INSERT OR IGNORE INTO DimSource (Platform, Subreddit, ContentType) VALUES ('Reddit', ?, ?)",
                   [("r/" + name, kind) for name in names for kind in ("Post", "Comment")])
    db.executemany("INSERT OR IGNORE INTO DimSentimentSource (Platform, Subreddit, ModelUsed) VALUES ('Reddit', ?, ?)",
                   [("r/" + name, MODEL_USED) for name in names] + [("ALL", MODEL_USED)])
    db.executemany("INSERT OR IGNORE INTO DimMajoritySentiment (MajorityStatus) VALUES (?)",
                   [("positive",), ("negative",), ("neutral",)])
    db.executemany("INSERT OR IGNORE INTO DimDetectionConfig (ZscoreThreshold, SentimentThreshold, Horizon) "
                   "VALUES (?,?,?)",
                   [(z, s, h) for z in Z_THRESHOLDS for s in SENTIMENT_THRESHOLDS for h in HORIZONS])

    hours, moment = [], TIME_START
    while moment <= TIME_END:
        iso = moment.isocalendar()
        hours.append((moment.year, moment.month, iso.week, moment.day, moment.hour, ts_text(moment)))
        moment += timedelta(hours=1)
    db.executemany("INSERT OR IGNORE INTO DimTime (Year, Month, Week, Day, Hour, ts_utc) VALUES (?,?,?,?,?,?)", hours)
    db.commit()
    return {table: db.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]
            for table in ("DimTicker", "DimSource", "DimSentimentSource", "DimMajoritySentiment",
                          "DimDetectionConfig", "DimTime")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args(argv)
    db = connect(args.db)
    try:
        print(seed(db))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
