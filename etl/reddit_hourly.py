"""P1: hourly Reddit sentiment features -> table `reddit_hourly` (proposal tables 13 and 15).

    reddit_hourly(variant, ticker, hour_utc, reddit_volume, sentiment_mean, sentiment_abs_mean,
                  pos_ratio, neg_ratio, neu_ratio, majority_vader_status, majority_finbert_status,
                  majority_final_status, voter_agreement_ratio)   PRIMARY KEY (variant, ticker, hour_utc)

variant  which TEXTS enter the hour (the filter is applied per text BEFORE averaging, for panels 4/5/7/8):
           all     every text that passed T1+T2
           strong  |final_sentiment| >= 0.05   (proposal table 12; same edge rule as status_of)
           quality |final_sentiment| >= 0.30
ticker   'ALL' = market-wide (every text); otherwise only texts that mention that ticker (ticker_mentions)
hour_utc epoch seconds of the start of the hour (post time floored to the hour; hour = [H:00, H+1:00) UTC)

Formulas (as written in the proposal):
  sentiment_mean      = sum(final_sentiment) / number of texts in the hour          (table 15)
  sentiment_abs_mean  = mean of |final_sentiment|
  pos/neg/neu_ratio   = share of texts whose final_status is positive/negative/neutral   (sum = 1)
  majority_*_status   = most frequent status of that model (vader / finbert / final) in the hour;
                        ties go to 'neutral' first, then 'positive', then 'negative' (conservative, deterministic)
  voter_agreement_ratio = texts in the most frequent FINAL status / all texts in the hour    (table 13)
Hours with no text have no row (NULL, not 0: 0 would mean "neutral"). Rebuilt on every run.

Usage:  python -m etl.reddit_hourly [--db output/reddit.sqlite3]
"""

import argparse
import sys

from etl.common import DEFAULT_DB, connect

VARIANTS = {"all": "1=1", "strong": "ABS(s.final_sentiment) >= 0.05", "quality": "ABS(s.final_sentiment) >= 0.30"}
STATUSES = ("neutral", "positive", "negative")          # tie-break order

SCHEMA = """CREATE TABLE reddit_hourly (
    variant TEXT NOT NULL, ticker TEXT NOT NULL, hour_utc INTEGER NOT NULL,
    reddit_volume INTEGER NOT NULL, sentiment_mean REAL NOT NULL, sentiment_abs_mean REAL NOT NULL,
    pos_ratio REAL NOT NULL, neg_ratio REAL NOT NULL, neu_ratio REAL NOT NULL,
    majority_vader_status TEXT, majority_finbert_status TEXT, majority_final_status TEXT NOT NULL,
    voter_agreement_ratio REAL NOT NULL,
    PRIMARY KEY (variant, ticker, hour_utc)) WITHOUT ROWID"""


def _counts(prefix):
    return ", ".join("SUM(s.%s_status = '%s')" % (prefix, st) for st in STATUSES)


def majority(neutral, positive, negative):
    """Most frequent status; ties resolved neutral > positive > negative."""
    counts = dict(zip(STATUSES, (neutral, positive, negative)))
    best = max(counts.values())
    return next(st for st in STATUSES if counts[st] == best), best


def aggregate(db, variant, where_sql, ticker=None):
    """Hourly rows for one variant. `where_sql` is the per-text filter (SQL on alias s = sentiment_item).
    ticker=None -> market-wide ('ALL'); ticker='__each__' -> one group per ticker from ticker_mentions."""
    if ticker == "__each__":
        source = ("sentiment_item s JOIN ticker_mentions m ON m.src_rowid = s.src_rowid "
                  "JOIN processed_text p ON p.src_rowid = s.src_rowid")
        key = "m.ticker"
    else:
        source = "sentiment_item s JOIN processed_text p ON p.src_rowid = s.src_rowid"
        key = "'ALL'"
    sql = ("SELECT %s, p.created_utc / 3600 * 3600 AS hour_utc, COUNT(*), SUM(s.final_sentiment), "
           "SUM(ABS(s.final_sentiment)), %s, %s, %s FROM %s WHERE %s GROUP BY 1, 2"
           % (key, _counts("vader"), _counts("finbert"), _counts("final"), source, where_sql))
    rows = []
    for (tk, hour, n, total, abs_total, vn, vp, vg, fn, fp, fg, gn, gp, gg) in db.execute(sql):
        final_major, final_best = majority(gn, gp, gg)
        rows.append((variant, tk, hour, n, total / n, abs_total / n, gp / n, gg / n, gn / n,
                     majority(vn, vp, vg)[0], majority(fn, fp, fg)[0], final_major, final_best / n))
    return rows


def build(db_path=DEFAULT_DB):
    db = connect(db_path)
    try:
        db.execute("DROP TABLE IF EXISTS reddit_hourly")
        db.execute(SCHEMA)
        for variant, where_sql in VARIANTS.items():
            for scope in (None, "__each__"):
                rows = aggregate(db, variant, where_sql, scope)
                db.executemany("INSERT INTO reddit_hourly VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
                db.commit()
                print("%-8s %-9s rows=%d" % (variant, "per-ticker" if scope else "market", len(rows)), flush=True)
        return db.execute("SELECT variant, COUNT(*) FROM reddit_hourly GROUP BY 1").fetchall()
    finally:
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    print(build(parser.parse_args(argv).db))
    return 0


if __name__ == "__main__":
    sys.exit(main())
