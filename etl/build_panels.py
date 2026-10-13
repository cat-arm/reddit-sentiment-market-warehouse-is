"""P4: the 9 analysis panels of proposal table 12 -> one table `panels` (column `panel_name`).

Every panel is a filter over `merged_hourly_panel` and keeps ONLY rows that have real Reddit sentiment
(proposal 7.4 "keep only rows with real sentiment, to reduce sparsity"):  has_reddit_data = 1 AND sentiment_mean IS NOT NULL.

    panel_name              merged_hourly_panel block                       extra condition
    panel_global            scope=global,  variant=all
    panel_global_strong     scope=global,  variant=strong   (|text score| >= 0.05, filtered per TEXT before averaging)
    panel_global_quality    scope=global,  variant=quality  (|text score| >= 0.30, per text)
    panel_global_spike      scope=global,  variant=all      reddit_volume_zscore_24 > 1.5   (per HOUR, market-wide)
    panel_Ticker            scope=ticker,  variant=all
    panel_Ticker_strong     scope=ticker,  variant=strong
    panel_Ticker_quality    scope=ticker,  variant=quality
    panel_Ticker_spike      scope=ticker,  variant=all      reddit_volume_zscore_24 > 1.5   (that ticker's own volume)
    panel_baseline          = exactly the rows of panel_global, plus a RANDOM direction (+1/-1, fixed seed) in
                            column random_direction.  It never looks at sentiment, so it is the "no signal" yardstick
                            for win rate / AUC (proposal table 12, option "random direction").
`random_direction` is NULL for every other panel.  Rebuilt on every run.
Columns are copied as they are, so `log_return` (= the proposal's current_return / Current Return) keeps its DB name here.

Usage:  python -m etl.build_panels [--db output/reddit.sqlite3] [--seed 42]
"""

import argparse
import sys

import numpy as np

from etl.common import DEFAULT_DB, connect

SPIKE_Z = 1.5
SEED = 42
HAS_SENTIMENT = "has_reddit_data = 1 AND sentiment_mean IS NOT NULL"
# (panel_name, scope, variant, extra WHERE)
PANELS = (
    ("panel_global", "global", "all", ""),
    ("panel_global_strong", "global", "strong", ""),
    ("panel_global_quality", "global", "quality", ""),
    ("panel_global_spike", "global", "all", "AND reddit_volume_zscore_24 > %s" % SPIKE_Z),
    ("panel_Ticker", "ticker", "all", ""),
    ("panel_Ticker_strong", "ticker", "strong", ""),
    ("panel_Ticker_quality", "ticker", "quality", ""),
    ("panel_Ticker_spike", "ticker", "all", "AND reddit_volume_zscore_24 > %s" % SPIKE_Z),
)


def build(db_path=DEFAULT_DB, seed=SEED):
    db = connect(db_path)
    try:
        db.execute("DROP TABLE IF EXISTS panels")
        db.execute("CREATE TABLE panels AS SELECT 'x' AS panel_name, * FROM merged_hourly_panel WHERE 0")
        db.execute("ALTER TABLE panels ADD COLUMN random_direction INTEGER")
        for name, scope, variant, extra in PANELS:
            db.execute("INSERT INTO panels (panel_name, %s) SELECT '%s', %s FROM merged_hourly_panel "
                       "WHERE scope = '%s' AND variant = '%s' AND %s %s"
                       % (_columns(db), name, _columns(db), scope, variant, HAS_SENTIMENT, extra))
        # baseline = same rows as panel_global + random direction (deterministic order -> reproducible)
        db.execute("INSERT INTO panels (panel_name, %s) SELECT 'panel_baseline', %s FROM panels "
                   "WHERE panel_name = 'panel_global'" % (_columns(db), _columns(db)))
        ids = [r[0] for r in db.execute("SELECT rowid FROM panels WHERE panel_name = 'panel_baseline' "
                                        "ORDER BY ticker, hour_utc")]
        signs = np.random.default_rng(seed).choice([-1, 1], size=len(ids))
        db.executemany("UPDATE panels SET random_direction = ? WHERE rowid = ?",
                       [(int(s), i) for s, i in zip(signs, ids)])
        db.execute("CREATE INDEX panels_key ON panels(panel_name, ticker, hour_utc)")
        db.commit()
        counts = db.execute("SELECT panel_name, COUNT(*), COUNT(DISTINCT ticker) FROM panels "
                            "GROUP BY 1 ORDER BY 2 DESC").fetchall()
        for name, n, tickers in counts:
            print("%-22s rows=%-8d tickers=%d" % (name, n, tickers))
        return counts
    finally:
        db.close()


def _columns(db):
    return ", ".join(r[1] for r in db.execute("PRAGMA table_info(merged_hourly_panel)"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args(argv)
    build(args.db, args.seed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
