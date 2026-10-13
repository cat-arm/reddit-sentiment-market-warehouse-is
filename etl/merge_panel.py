"""P3: merged hourly panel = market rows LEFT JOIN Reddit hourly features -> table `merged_hourly_panel`.

Base = `market_hourly_features` (valid price bars only, one row per ticker x hour), so the row count of every
(scope, variant) block equals the number of market rows.  Key used for the join (proposal 7.4): hour + ticker.

    scope    'ticker'  Reddit side = texts that mention THIS ticker      (panel_Ticker*  family)
             'global'  Reddit side = market-wide texts (ticker 'ALL'), joined to every ticker's price row
                                                                          (panel_global*  family)
    variant  all / strong / quality  (which texts entered the Reddit hour, see etl.reddit_hourly)

Columns: scope, variant, ticker, big_group (DimTicker.AssetClass), hour_utc (epoch s of the floored hour),
         market columns (close ... volume_zscore_24 renamed market_volume_zscore_24),
         every Reddit feature of reddit_hourly_features, and has_reddit_data (1 if a Reddit row exists).
Missing Reddit hour: reddit_volume = 0 (no texts is a real count), every sentiment column stays NULL
(0 would mean "neutral", which is a different statement).  Rebuilt on every run.

Usage:  python -m etl.merge_panel [--db output/reddit.sqlite3]
"""

import argparse
import sys

from etl.common import DEFAULT_DB, connect

REDDIT_COLUMNS = ("sentiment_mean", "sentiment_abs_mean", "pos_ratio", "neg_ratio", "neu_ratio",
                  "majority_vader_status", "majority_finbert_status", "majority_final_status",
                  "voter_agreement_ratio", "reddit_volume_zscore_24", "reddit_volume_lag_1h",
                  "sentiment_lag_1h", "sentiment_lag_2h", "sentiment_lag_3h", "sentiment_lag_6h",
                  "sentiment_lag_12h", "sentiment_momentum_1h")
MARKET_COLUMNS = ("close", "volume", "log_return", "future_return_1h", "future_return_2h", "future_return_3h",
                  "future_return_6h", "future_return_12h", "rsi", "atr", "normalized_atr")

SQL = """
CREATE TABLE merged_hourly_panel AS
SELECT s.scope, s.variant, m.ticker, d.AssetClass AS big_group,
       CAST(strftime('%s', m.hour_bucket) AS INTEGER) AS hour_utc,
       {market},
       m.volume_zscore_24 AS market_volume_zscore_24,
       COALESCE(r.reddit_volume, 0) AS reddit_volume,
       {reddit},
       CASE WHEN r.hour_utc IS NULL THEN 0 ELSE 1 END AS has_reddit_data
FROM market_hourly_features m
JOIN DimTicker d ON d.TickerSymbol = m.ticker
CROSS JOIN (SELECT 'ticker' AS scope, 'all' AS variant UNION ALL SELECT 'ticker', 'strong'
            UNION ALL SELECT 'ticker', 'quality' UNION ALL SELECT 'global', 'all'
            UNION ALL SELECT 'global', 'strong' UNION ALL SELECT 'global', 'quality') s
LEFT JOIN reddit_hourly_features r
       ON r.variant = s.variant
      AND r.ticker = CASE s.scope WHEN 'ticker' THEN m.ticker ELSE 'ALL' END
      AND r.hour_utc = CAST(strftime('%s', m.hour_bucket) AS INTEGER)
"""


def build(db_path=DEFAULT_DB):
    db = connect(db_path)
    try:
        dup = db.execute("SELECT COUNT(*) FROM (SELECT ticker, hour_bucket FROM market_hourly_features "
                         "GROUP BY 1, 2 HAVING COUNT(*) > 1)").fetchone()[0]
        if dup:
            raise SystemExit("market_hourly_features has %d duplicated (ticker, hour_bucket) keys" % dup)
        db.execute("DROP TABLE IF EXISTS merged_hourly_panel")
        db.execute(SQL.format(market=", ".join("m." + c for c in MARKET_COLUMNS),
                              reddit=", ".join("r." + c for c in REDDIT_COLUMNS)))
        db.execute("CREATE INDEX merged_hourly_panel_key ON merged_hourly_panel(scope, variant, ticker, hour_utc)")
        db.commit()
        base = db.execute("SELECT COUNT(*) FROM market_hourly_features").fetchone()[0]
        summary = db.execute("SELECT scope, variant, COUNT(*), SUM(has_reddit_data) FROM merged_hourly_panel "
                             "GROUP BY 1, 2 ORDER BY 1, 2").fetchall()
        print("market rows: %d" % base)
        for scope, variant, n, with_reddit in summary:
            print("%-7s %-8s rows=%d  with_reddit=%d  (%.1f%%)" % (scope, variant, n, with_reddit, 100 * with_reddit / n))
        return base, summary
    finally:
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    build(parser.parse_args(argv).db)
    return 0


if __name__ == "__main__":
    sys.exit(main())
