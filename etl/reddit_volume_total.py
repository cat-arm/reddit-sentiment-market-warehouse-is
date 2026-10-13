"""T5b: TOTAL Reddit volume per hour and source -> table `reddit_volume_hourly`.

Proposal 7.1 measure 1: Reddit_volume = "number of posts and comments" (table 3).  It is the size of the whole
conversation in that hour, NOT the number of texts about one ticker.  The proof is KPI 2 of table 4:
    Ticker Mention Rate (%) = Ticker_mention_count / Reddit_volume x 100
where Reddit_volume must be the denominator (all texts) and Ticker_mention_count the part about one ticker.

    reddit_volume_hourly(TimeID, SourceID, texts)
      TimeID    DimTime row of the hour (UTC)
      SourceID  DimSource row = community x {Post, Comment}
      texts     texts of the 6 communities in that hour/source that passed the cleaning and quality filters
                (the same 22.03 M texts that get a sentiment score; filtered_text view)
Hours/sources without any text have no row (the dashboard fills them with 0: no texts is a real count).
FactRedditVolume.reddit_volume copies these numbers (see etl/load_fact_reddit_volume.py).
Rebuilt on every run (a few minutes: one pass over filtered_text).

Usage:  python -m etl.reddit_volume_total [--db output/reddit.sqlite3]
"""

import argparse
import sys

from etl.common import DEFAULT_DB, connect
from etl.seed_dims import seed

SCHEMA = """CREATE TABLE reddit_volume_hourly (
    TimeID INTEGER NOT NULL REFERENCES DimTime(TimeID),
    SourceID INTEGER NOT NULL REFERENCES DimSource(SourceID),
    texts INTEGER NOT NULL,
    PRIMARY KEY (TimeID, SourceID)) WITHOUT ROWID"""

# Group the big view first (hour x community x type), then join the small result to the dimensions.
_LOAD = """
INSERT INTO reddit_volume_hourly (TimeID, SourceID, texts)
SELECT t.TimeID, s.SourceID, g.n
FROM (SELECT created_utc / 3600 * 3600 AS hour_start, subreddit, content_type, COUNT(*) AS n
      FROM filtered_text GROUP BY 1, 2, 3) g
JOIN DimTime t ON t.ts_utc = strftime('%Y-%m-%dT%H:00:00+00:00', g.hour_start, 'unixepoch')
JOIN DimSource s ON s.Subreddit = 'r/' || g.subreddit
              AND s.ContentType = CASE g.content_type WHEN 'comment' THEN 'Comment' ELSE 'Post' END
"""


def build(db):
    seed(db)                                           # schema + dimensions must exist
    db.execute("DROP TABLE IF EXISTS reddit_volume_hourly")
    db.execute(SCHEMA)
    db.execute(_LOAD)
    db.commit()
    total, expected = (db.execute("SELECT SUM(texts) FROM reddit_volume_hourly").fetchone()[0],
                       db.execute("SELECT COUNT(*) FROM filtered_text").fetchone()[0])
    if total != expected:                              # a lost row means a broken hour / community join
        raise SystemExit("reddit_volume_hourly sums to %s but filtered_text has %s rows" % (total, expected))
    return {"rows": db.execute("SELECT COUNT(*) FROM reddit_volume_hourly").fetchone()[0], "texts": total}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args(argv)
    db = connect(args.db)
    try:
        print(build(db))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
