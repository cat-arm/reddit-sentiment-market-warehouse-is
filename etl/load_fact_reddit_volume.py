"""T5: fill FactRedditVolume (proposal figure 2) from ticker_mentions.

One row per (hour, ticker, source) where source = community x {Post, Comment}, only where the ticker was mentioned:
    reddit_volume        = ALL posts/comments of that hour and source (proposal table 3; the denominator of the
                           Ticker Mention Rate, table 4).  Copied from reddit_volume_hourly, so the SAME number repeats
                           on every ticker row of one hour/source: never sum it across tickers.
    ticker_mention_count = total mentions of the ticker in the texts of that hour/source (3 times in one text = 3)
Mentions use the all-mentions count (mention_count, decision "option A" in TASKS T4: weak words such as "gold"
included). strong_count stays in ticker_mentions for the sensitivity check.
(Until 2026-10-11 reddit_volume held the number of texts that mention the ticker; that was a misreading of the
proposal. The ticker-level text counts still exist, as `reddit_hourly`, and feed the analysis panels.)

Hour = created_utc rounded down to the full hour (UTC). Hours with no mention have no row; consumers
that need zeros (T6 panel) must LEFT JOIN and fill reddit_volume with 0 (volume 0 is real; NULL is not).
Always rebuilds the table (a few minutes), so it is safe to rerun after T2/T4 change.

Usage:
    python -m etl.load_fact_reddit_volume [--db output/reddit.sqlite3]
"""

import argparse
import sys

from etl import reddit_volume_total
from etl.common import DEFAULT_DB, connect
from etl.seed_dims import seed

# processed_text gives the hour/community/type of each text, ticker_mentions gives the ticker.
_LOAD = """
INSERT INTO FactRedditVolume (TimeID, TickerID, SourceID, reddit_volume, ticker_mention_count)
SELECT t.TimeID, k.TickerID, s.SourceID, COUNT(*), SUM(m.mention_count)
FROM ticker_mentions m
JOIN processed_text p ON p.src_rowid = m.src_rowid
JOIN DimTime t ON t.ts_utc = strftime('%Y-%m-%dT%H:00:00+00:00', p.created_utc, 'unixepoch')
JOIN DimTicker k ON k.TickerSymbol = m.ticker
JOIN DimSource s ON s.Subreddit = 'r/' || p.subreddit
              AND s.ContentType = CASE p.content_type WHEN 'comment' THEN 'Comment' ELSE 'Post' END
GROUP BY t.TimeID, k.TickerID, s.SourceID
"""


def load(db):
    seed(db)                                   # make sure schema + dimensions exist
    reddit_volume_total.build(db)              # total texts per hour x source (the real Reddit_volume)
    db.execute("DELETE FROM FactRedditVolume")
    db.execute(_LOAD)
    # Proposal table 3: Reddit_volume = ALL posts and comments of that hour and source (it is the denominator of the
    # Ticker Mention Rate, table 4).  The insert above counted only the texts that mention the ticker, so replace it
    # with the total.  The same number therefore repeats on every ticker row of one hour/source - do NOT sum
    # reddit_volume across tickers.  Ticker_mention_count stays the number of mentions of this ticker.
    db.execute("""UPDATE FactRedditVolume SET reddit_volume = (
                      SELECT v.texts FROM reddit_volume_hourly v
                      WHERE v.TimeID = FactRedditVolume.TimeID AND v.SourceID = FactRedditVolume.SourceID)""")
    db.commit()
    return check_totals(db)


def check_totals(db):
    """Definition of done: mentions agree with ticker_mentions and every row carries a real total volume."""
    fact_mentions = db.execute("SELECT SUM(ticker_mention_count) FROM FactRedditVolume").fetchone()[0]
    src_mentions = db.execute("SELECT SUM(mention_count) FROM ticker_mentions").fetchone()[0]
    missing = db.execute("SELECT COUNT(*) FROM FactRedditVolume WHERE reddit_volume IS NULL OR reddit_volume <= 0").fetchone()[0]
    result = {"fact_rows": db.execute("SELECT COUNT(*) FROM FactRedditVolume").fetchone()[0],
              "mention_count_total": fact_mentions, "mention_count_expected": src_mentions,
              "rows_without_total_volume": missing}
    if fact_mentions != src_mentions or missing:
        raise SystemExit("FactRedditVolume does not match ticker_mentions / totals: %s" % result)
    return result


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
