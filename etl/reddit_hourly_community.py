"""P1b: hourly Reddit sentiment per ticker (and per market) AND per community -> tables `reddit_hourly_community` and
`reddit_hourly_global` (DimSentimentSource).

    reddit_hourly_community(ticker, hour_utc, subreddit, texts, sentiment_sum, abs_sum, pos_n, neg_n, neu_n, model, variant, content_type)
        PRIMARY KEY (model, variant, ticker, hour_utc, subreddit, content_type)   the texts that MENTION the ticker
    reddit_hourly_global(hour_utc, subreddit, texts, sentiment_sum, abs_sum, pos_n, neg_n, neu_n, model, variant, content_type)
        PRIMARY KEY (model, variant, hour_utc, subreddit, content_type)           EVERY text of the market (proposal: scope global)

Why: the dashboards (proposal 7.5, dimensions DimTime, DimTicker, DimSentimentSource, DimMajoritySentiment) let the user choose the
communities, and the statistics of dashboard 2 are computed live on the chosen hours.  `reddit_hourly` holds only the pooled value, so
these tables keep the SUMS per community; any selection of communities is then recombined exactly:
    sentiment_mean = sum(sentiment_sum) / sum(texts)          (same formula as table 15 of the proposal)
    pos / neg / neu ratio = sum(pos_n) / sum(texts), ...      majority status = most frequent of pos_n / neg_n / neu_n
`model` = DimSentimentSource.ModelUsed: 'VADER+FinBERT' (the final resolved sentiment of 7.3, the proposal's model), 'VADER'
(vader_score / vader_status only) and 'FinBERT' (finbert_score / finbert_status only; EXTENSION).  `variant` = which texts enter
the hour, as in `reddit_hourly` (table 12 of the proposal; the filter is applied per TEXT before summing, on the score of the model
of the row): 'all' = every text, 'strong' = |score| >= 0.05, 'quality' = |score| >= 0.30.
`content_type` = 'Post' (processed_text 'submission') or 'Comment' (DimSource.ContentType): the filter of the dashboards sums the rows of the types that are ticked.
`subreddit` is stored like DimSentimentSource.Subreddit ('r/wallstreetbets').  Hours without a text have no row (NULL, never 0).
Rebuilt on every run.  `check` verifies that summing over the six communities gives exactly the pooled `reddit_hourly` rows
(model 'VADER+FinBERT', every variant, every ticker and the market 'ALL') and that all models keep the same texts in 'all'.

Usage:  python -m etl.reddit_hourly_community [--db output/reddit.sqlite3]
"""

import argparse
import sys

from etl.common import DEFAULT_DB, connect

MODELS = (("VADER+FinBERT", "final_sentiment", "final_status"), ("VADER", "vader_score", "vader_status"),
          ("FinBERT", "finbert_score", "finbert_status"))
VARIANTS = (("all", 0.0), ("strong", 0.05), ("quality", 0.30))

SCHEMA = """CREATE TABLE reddit_hourly_community (
    ticker TEXT NOT NULL, hour_utc INTEGER NOT NULL, subreddit TEXT NOT NULL, texts INTEGER NOT NULL,
    sentiment_sum REAL NOT NULL, abs_sum REAL NOT NULL, pos_n INTEGER NOT NULL, neg_n INTEGER NOT NULL,
    neu_n INTEGER NOT NULL, model TEXT NOT NULL, variant TEXT NOT NULL, content_type TEXT NOT NULL,
    PRIMARY KEY (model, variant, ticker, hour_utc, subreddit, content_type)) WITHOUT ROWID"""

SCHEMA_GLOBAL = """CREATE TABLE reddit_hourly_global (
    hour_utc INTEGER NOT NULL, subreddit TEXT NOT NULL, texts INTEGER NOT NULL,
    sentiment_sum REAL NOT NULL, abs_sum REAL NOT NULL, pos_n INTEGER NOT NULL, neg_n INTEGER NOT NULL,
    neu_n INTEGER NOT NULL, model TEXT NOT NULL, variant TEXT NOT NULL, content_type TEXT NOT NULL,
    PRIMARY KEY (model, variant, hour_utc, subreddit, content_type)) WITHOUT ROWID"""

SELECT = """
    SELECT m.ticker, p.created_utc / 3600 * 3600 AS hour_utc, 'r/' || p.subreddit, COUNT(*), SUM(s.{score}),
           SUM(ABS(s.{score})), SUM(s.{status} = 'positive'), SUM(s.{status} = 'negative'),
           SUM(s.{status} = 'neutral'), '{model}', '{variant}', CASE p.content_type WHEN 'submission' THEN 'Post' ELSE 'Comment' END
    FROM sentiment_item s JOIN ticker_mentions m ON m.src_rowid = s.src_rowid
         JOIN processed_text p ON p.src_rowid = s.src_rowid
    WHERE ABS(s.{score}) >= {floor}
    GROUP BY 1, 2, 3, 12"""

SELECT_GLOBAL = """
    SELECT p.created_utc / 3600 * 3600 AS hour_utc, 'r/' || p.subreddit, COUNT(*), SUM(s.{score}),
           SUM(ABS(s.{score})), SUM(s.{status} = 'positive'), SUM(s.{status} = 'negative'),
           SUM(s.{status} = 'neutral'), '{model}', '{variant}', CASE p.content_type WHEN 'submission' THEN 'Post' ELSE 'Comment' END
    FROM sentiment_item s JOIN processed_text p ON p.src_rowid = s.src_rowid
    WHERE ABS(s.{score}) >= {floor}
    GROUP BY 1, 2, 11"""


def aggregate(db, models=MODELS, variants=VARIANTS):
    """Rows of `reddit_hourly_community` from the texts, one query per model and variant (grouped by ticker, hour, community)."""
    for model, score, status in models:
        for variant, floor in variants:
            yield from db.execute(SELECT.format(model=model, score=score, status=status, variant=variant, floor=floor))


def aggregate_global(db, models=MODELS, variants=VARIANTS):
    """Rows of `reddit_hourly_global` from the texts of the whole market (grouped by hour and community)."""
    for model, score, status in models:
        for variant, floor in variants:
            yield from db.execute(SELECT_GLOBAL.format(model=model, score=score, status=status, variant=variant, floor=floor))


def build(db_path=DEFAULT_DB):
    db = connect(db_path)
    try:
        total = 0
        for table, schema, select, marks in (("reddit_hourly_community", SCHEMA, SELECT, 12), ("reddit_hourly_global", SCHEMA_GLOBAL, SELECT_GLOBAL, 11)):
            db.execute("DROP TABLE IF EXISTS " + table)
            db.execute(schema)
            for model, score, status in MODELS:
                for variant, floor in VARIANTS:
                    rows = db.execute(select.format(model=model, score=score, status=status, variant=variant, floor=floor)).fetchall()
                    db.executemany("INSERT INTO %s VALUES (%s)" % (table, ",".join("?" * marks)), rows)
                    db.commit()
                    total += len(rows)
                    print("%s %s %s rows=%d" % (table, model, variant, len(rows)), flush=True)
        return total
    finally:
        db.close()


def check(db_path=DEFAULT_DB):
    """(pooled rows compared, rows that differ) between the tables summed over communities and `reddit_hourly`, for the final model
    and every variant, per ticker and for the market ('ALL'); plus the rows where the models disagree on the number of texts ('all')."""
    db = connect(db_path)
    try:
        compared = bad = 0
        for table, key in (("reddit_hourly_community", "ticker"), ("reddit_hourly_global", "'ALL'")):
            group = "ticker, hour_utc" if key == "ticker" else "hour_utc"
            join = "h.ticker = a.ticker AND " if key == "ticker" else "h.ticker = 'ALL' AND "
            select_key = "ticker" if key == "ticker" else "'ALL' AS ticker"
            for variant, _ in VARIANTS:
                sql = """
                    SELECT COUNT(*), SUM(h.reddit_volume != a.n OR ABS(h.sentiment_mean * h.reddit_volume - a.s) > 1e-6
                                         OR ABS(h.pos_ratio * h.reddit_volume - a.p) > 1e-6)
                    FROM (SELECT %s, hour_utc, SUM(texts) AS n, SUM(sentiment_sum) AS s, SUM(pos_n) AS p
                          FROM %s WHERE model = 'VADER+FinBERT' AND variant = ? GROUP BY %s) a
                    JOIN reddit_hourly h ON %sh.variant = ? AND h.hour_utc = a.hour_utc""" % (select_key, table, group, join)
                n, wrong = db.execute(sql, (variant, variant)).fetchone()
                compared += n
                bad += wrong or 0
                rows = db.execute("SELECT COUNT(*) FROM reddit_hourly WHERE variant = ? AND %s" % ("ticker != 'ALL'" if key == "ticker" else "ticker = 'ALL'"),
                                  (variant,)).fetchone()[0]
                grouped = db.execute("SELECT COUNT(*) FROM (SELECT 1 FROM %s WHERE model = 'VADER+FinBERT' AND variant = ? GROUP BY %s)" % (table, group),
                                     (variant,)).fetchone()[0]
                if rows != grouped:
                    bad += abs(rows - grouped)
            # every model keeps the same texts in 'all'
            other = "ticker, " if key == "ticker" else ""
            bad += db.execute("""SELECT COUNT(*) FROM %s a JOIN %s b ON b.hour_utc = a.hour_utc AND b.subreddit = a.subreddit AND b.content_type = a.content_type %s
                                 AND b.variant = 'all' AND b.model != a.model WHERE a.model = 'VADER+FinBERT' AND a.variant = 'all' AND a.texts != b.texts"""
                              % (table, table, "AND b.ticker = a.ticker" if other else "")).fetchone()[0]
        return compared, bad
    finally:
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--check-only", action="store_true", help="only compare with reddit_hourly, do not rebuild")
    args = parser.parse_args(argv)
    if not args.check_only:
        build(args.db)
    compared, bad = check(args.db)
    print("pooled hours compared with reddit_hourly: %d, differences: %d" % (compared, bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
