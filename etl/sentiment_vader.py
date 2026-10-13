"""S1: VADER sentiment for every text that passed T1 + T2 -> table `sentiment_vader`.

    sentiment_vader(src_rowid, vader_score, vader_status)
      src_rowid    same key as processed_text / filtered_text
      vader_score  compound score in [-1, 1]  (NLTK SentimentIntensityAnalyzer, polarity_scores()["compound"])
      vader_status positive / negative / neutral with the +-0.05 neutral band (etl.common.status_of)

Every row of filtered_text gets exactly one score (no NULLs). Resumable: restarts after the highest src_rowid
already written. VADER reads the CASE of words ("GREAT" is stronger than "great") and negations like "don't",
which is why T1 keeps case and apostrophes. The lexicon is NLTK's `vader_lexicon`
(python -c "import nltk; nltk.download('vader_lexicon')" once).

Usage:
    python -m etl.sentiment_vader [--db output/reddit.sqlite3] [--window N] [--limit-rows N] [--rebuild]
"""

import argparse
import sys
import time

from nltk.sentiment.vader import SentimentIntensityAnalyzer

from etl.common import DEFAULT_DB, connect, status_of
from pipeline_logs import append_event, run_id

SCORER_VERSION = "nltk-vader-1.0"

SCHEMA = """CREATE TABLE IF NOT EXISTS sentiment_vader (
    src_rowid INTEGER PRIMARY KEY,
    vader_score REAL NOT NULL,
    vader_status TEXT NOT NULL)"""


def process(db_path=DEFAULT_DB, window=200_000, limit_rows=None, rebuild=False):
    db = connect(db_path)
    try:
        return _process(db, window, limit_rows, rebuild)
    finally:
        db.close()


def _process(db, window, limit_rows, rebuild):
    analyzer = SentimentIntensityAnalyzer()
    if rebuild:
        db.execute("DROP TABLE IF EXISTS sentiment_vader")
    db.execute(SCHEMA)
    db.commit()
    done = db.execute("SELECT COALESCE(MAX(src_rowid), 0) FROM sentiment_vader").fetchone()[0]
    last = db.execute("SELECT MAX(src_rowid) FROM processed_text").fetchone()[0] or 0
    if limit_rows:
        last = min(last, done + limit_rows)
    this_run = run_id()
    append_event(db, "sentiment_vader_start", run_id=this_run, version=SCORER_VERSION, resume_from=done)
    scored, started = 0, time.time()
    while done < last:
        upper = min(done + window, last)
        rows = db.execute("SELECT src_rowid, final_text FROM filtered_text WHERE src_rowid > ? AND src_rowid <= ?",
                          (done, upper)).fetchall()
        out = []
        for rowid, text in rows:
            score = analyzer.polarity_scores(text)["compound"]
            out.append((rowid, score, status_of(score)))
        db.executemany("INSERT OR IGNORE INTO sentiment_vader VALUES (?,?,?)", out)
        db.commit()
        done = upper
        scored += len(out)
        print("rowid %d/%d  scored %d  (%.0f texts/s)"
              % (done, last, scored, scored / max(time.time() - started, 1e-9)), flush=True)
    append_event(db, "sentiment_vader_done", run_id=this_run, version=SCORER_VERSION, scored=scored)
    return {"scored": scored}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--window", type=int, default=200_000, help="processed_text rowids per batch")
    parser.add_argument("--limit-rows", type=int, help="score only this many rowids (trials)")
    parser.add_argument("--rebuild", action="store_true", help="drop sentiment_vader and start over")
    args = parser.parse_args(argv)
    print("done:", process(args.db, args.window, args.limit_rows, args.rebuild))
    return 0


if __name__ == "__main__":
    sys.exit(main())
