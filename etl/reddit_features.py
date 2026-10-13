"""P2: lag / z-score / momentum on top of `reddit_hourly` -> table `reddit_hourly_features`.

Same keys as reddit_hourly (variant, ticker, hour_utc) plus (proposal table 13, rows "Volume & Momentum"):
  reddit_volume_zscore_24   (volume_t - mean) / std of the PRIOR 24 clock hours, current hour excluded
  reddit_volume_lag_1h      volume of the previous clock hour
  sentiment_lag_1h/2h/3h/6h/12h   sentiment_mean of the clock hour t-k
  sentiment_momentum_1h     sentiment_mean(t) - sentiment_lag_1h

Rules (all by CLOCK hour on a full hourly grid, never by "previous row", and never across tickers):
  * Volume series: always taken from variant 'all' of the same ticker. A clock hour with no row there means
    zero texts, so it is filled with 0 (a real count).  The z-score and volume lag are then copied onto the
    strong/quality rows of that ticker, so spike panels (z > 1.5) are defined the same way for every variant.
  * z-score: population std (ddof=0, same as M1), needs >= MIN_PRIOR prior hours inside the data range and
    std > 0, otherwise NULL.  The first hours of the data therefore stay NULL, never 0.
  * Sentiment lags/momentum: from the row's own variant.  If the lagged hour has no texts the value is NULL
    (NOT 0: 0 would mean "neutral").
Rebuilt on every run.

Usage:  python -m etl.reddit_features [--db output/reddit.sqlite3]
"""

import argparse
import sys

import numpy as np
import pandas as pd

from etl.common import DEFAULT_DB, connect

WINDOW = 24
MIN_PRIOR = 6
LAGS = (1, 2, 3, 6, 12)
HOUR = 3600
FEATURES = (["reddit_volume_zscore_24", "reddit_volume_lag_1h"]
            + ["sentiment_lag_%dh" % k for k in LAGS] + ["sentiment_momentum_1h"])


def volume_features(volume):
    """volume: DataFrame index=hour grid, columns=tickers, 0-filled counts -> (zscore, lag_1h) same shape."""
    prior = volume.shift(1)
    roll = prior.rolling(WINDOW, min_periods=MIN_PRIOR)
    mean, std = roll.mean(), roll.std(ddof=0)
    zscore = (volume - mean) / std.where(std > 0)
    return zscore, prior


def build_features(hourly):
    """hourly: DataFrame of reddit_hourly rows -> same rows (variant, ticker, hour_utc) + FEATURES columns."""
    grid = np.arange(hourly["hour_utc"].min(), hourly["hour_utc"].max() + HOUR, HOUR)
    allv = hourly[hourly["variant"] == "all"]
    volume = allv.pivot(index="hour_utc", columns="ticker", values="reddit_volume").reindex(grid).fillna(0)
    zscore, lag1 = volume_features(volume)
    z_long = zscore.stack().rename("reddit_volume_zscore_24")
    v_long = lag1.stack().rename("reddit_volume_lag_1h")
    volume_feats = pd.concat([z_long, v_long], axis=1).rename_axis(["hour_utc", "ticker"]).reset_index()

    pieces = []
    for variant, part in hourly.groupby("variant"):
        sent = part.pivot(index="hour_utc", columns="ticker", values="sentiment_mean").reindex(grid)
        cols = {"sentiment_lag_%dh" % k: sent.shift(k).stack() for k in LAGS}
        cols["sentiment_momentum_1h"] = (sent - sent.shift(1)).stack()
        feats = pd.DataFrame(cols).rename_axis(["hour_utc", "ticker"]).reset_index()
        keep = part.merge(feats, on=["hour_utc", "ticker"], how="left")
        pieces.append(keep)
    out = pd.concat(pieces, ignore_index=True)
    out = out.merge(volume_feats, on=["hour_utc", "ticker"], how="left")
    return out


def build(db_path=DEFAULT_DB):
    db = connect(db_path)
    try:
        hourly = pd.read_sql_query("SELECT * FROM reddit_hourly", db)
        out = build_features(hourly).sort_values(["variant", "ticker", "hour_utc"])
        db.execute("DROP TABLE IF EXISTS reddit_hourly_features")
        out.to_sql("reddit_hourly_features", db, index=False, chunksize=100_000)
        db.execute("CREATE UNIQUE INDEX reddit_hourly_features_key ON reddit_hourly_features(variant, ticker, hour_utc)")
        db.commit()
        stats = {c: int(out[c].notna().sum()) for c in FEATURES}
        print("rows=%d  non-null: %s" % (len(out), stats))
        return out
    finally:
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    build(parser.parse_args(argv).db)
    return 0


if __name__ == "__main__":
    sys.exit(main())
