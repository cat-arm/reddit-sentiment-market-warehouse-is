"""P1b: hourly Reddit sentiment per ticker AND per community -> table `reddit_hourly_community` (DimSentimentSource).

    reddit_hourly_community(ticker, hour_utc, subreddit, texts, sentiment_sum, abs_sum, pos_n, neg_n, neu_n, model)
        PRIMARY KEY (model, ticker, hour_utc, subreddit)

`model` = DimSentimentSource.ModelUsed: 'VADER+FinBERT' (the final resolved sentiment of 7.3, the proposal's model),
'VADER' (vader_score / vader_status only) and 'FinBERT' (finbert_score / finbert_status only; EXTENSION: the dashboard lets
the user compare the two models).  Every model has the same texts, only the scores and statuses differ.

Why: the Market and Sentiment dashboard (proposal 7.5, dimensions DimTime, DimTicker, DimSentimentSource,
DimMajoritySentiment) lets the user choose the communities.  `reddit_hourly` holds only the pooled value, so this table
keeps the SUMS per community; any selection of communities is then recombined exactly:
    sentiment_mean = sum(sentiment_sum) / sum(texts)          (same formula as table 15 of the proposal)
    pos / neg / neu ratio = sum(pos_n) / sum(texts), ...      majority status = most frequent of pos_n / neg_n / neu_n
All variant = 'all' texts (every text that passed T1 + T2 and mentions the ticker).  `subreddit` is stored like
DimSentimentSource.Subreddit ('r/wallstreetbets').  Hours without a text have no row (NULL, never 0).  Rebuilt on every run.
`check` verifies that summing over the six communities gives exactly the pooled `reddit_hourly` rows (model 'VADER+FinBERT')
and that all three models have the same number of texts in every ticker-hour.

Usage:  python -m etl.reddit_hourly_community [--db output/reddit.sqlite3]
"""

import argparse
import sys

from etl.common import DEFAULT_DB, connect

MODELS = (("VADER+FinBERT", "final_sentiment", "final_status"), ("VADER", "vader_score", "vader_status"),
          ("FinBERT", "finbert_score", "finbert_status"))

SCHEMA = """CREATE TABLE reddit_hourly_community (
    ticker TEXT NOT NULL, hour_utc INTEGER NOT NULL, subreddit TEXT NOT NULL, texts INTEGER NOT NULL,
    sentiment_sum REAL NOT NULL, abs_sum REAL NOT NULL, pos_n INTEGER NOT NULL, neg_n INTEGER NOT NULL,
    neu_n INTEGER NOT NULL, model TEXT NOT NULL, PRIMARY KEY (model, ticker, hour_utc, subreddit)) WITHOUT ROWID"""

SELECT = """
    SELECT m.ticker, p.created_utc / 3600 * 3600 AS hour_utc, 'r/' || p.subreddit, COUNT(*), SUM(s.{score}),
           SUM(ABS(s.{score})), SUM(s.{status} = 'positive'), SUM(s.{status} = 'negative'),
           SUM(s.{status} = 'neutral'), '{model}'
    FROM sentiment_item s JOIN ticker_mentions m ON m.src_rowid = s.src_rowid
         JOIN processed_text p ON p.src_rowid = s.src_rowid
    GROUP BY 1, 2, 3"""


def aggregate(db, models=MODELS):
    """Rows of the table from the texts, one query per model (grouped by ticker, hour and community)."""
    for model, score, status in models:
        yield from db.execute(SELECT.format(model=model, score=score, status=status))


def build(db_path=DEFAULT_DB):
    db = connect(db_path)
    try:
        db.execute("DROP TABLE IF EXISTS reddit_hourly_community")
        db.execute(SCHEMA)
        total = 0
        for model, score, status in MODELS:
            rows = db.execute(SELECT.format(model=model, score=score, status=status)).fetchall()
            db.executemany("INSERT INTO reddit_hourly_community VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
            db.commit()
            total += len(rows)
            print("%s rows=%d" % (model, len(rows)), flush=True)
        return total
    finally:
        db.close()


def check(db_path=DEFAULT_DB):
    """(rows compared, rows that differ) between the community table summed over communities and `reddit_hourly`."""
    db = connect(db_path)
    try:
        bad = db.execute("""
            SELECT COUNT(*) FROM (
              SELECT c.ticker, c.hour_utc, SUM(c.texts) AS n, SUM(c.sentiment_sum) AS s, SUM(c.pos_n) AS p
              FROM reddit_hourly_community c WHERE c.model = 'VADER+FinBERT' GROUP BY 1, 2) a
            JOIN reddit_hourly h ON h.variant = 'all' AND h.ticker = a.ticker AND h.hour_utc = a.hour_utc
            WHERE h.reddit_volume != a.n OR ABS(h.sentiment_mean * h.reddit_volume - a.s) > 1e-6
               OR ABS(h.pos_ratio * h.reddit_volume - a.p) > 1e-6""").fetchone()[0]
        total = db.execute("SELECT COUNT(*) FROM reddit_hourly WHERE variant = 'all' AND ticker != 'ALL'").fetchone()[0]
        grouped = db.execute("SELECT COUNT(*) FROM (SELECT 1 FROM reddit_hourly_community WHERE model = 'VADER+FinBERT' "
                             "GROUP BY ticker, hour_utc)").fetchone()[0]
        # every model must have the same texts in every ticker-hour and community
        bad += db.execute("""SELECT COUNT(*) FROM reddit_hourly_community a JOIN reddit_hourly_community b
            ON b.ticker = a.ticker AND b.hour_utc = a.hour_utc AND b.subreddit = a.subreddit AND b.model != a.model
            WHERE a.model = 'VADER+FinBERT' AND a.texts != b.texts""").fetchone()[0]
        return total, grouped, bad
    finally:
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--check-only", action="store_true", help="only compare with reddit_hourly, do not rebuild")
    args = parser.parse_args(argv)
    if not args.check_only:
        build(args.db)
    total, grouped, bad = check(args.db)
    print("reddit_hourly rows %d, ticker-hours in the community table %d, rows that differ: %d" % (total, grouped, bad))
    return 0 if (total == grouped and bad == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
