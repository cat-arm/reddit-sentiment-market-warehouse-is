"""T4: find which of the 34 assets each cleaned text talks about and fill the `ticker_mentions` table.

Reads the view `filtered_text` (T1 cleaned + T2 quality-filtered) and uses TickerMatcher from T3
(rules live in configs/tickers.yaml). Writes ONE row per (text, ticker) that is mentioned at least once:

    ticker_mentions(content_id, ticker, mention_count, strong_count, src_rowid)
      mention_count = all mentions (strong + weak), the number used by FactRedditVolume (T5)
      strong_count  = clear mentions only (symbol / $cashtag / company or coin name); the difference is the
                      weak, generic-word part ("gold", "Russell 2000"). Use strong_count for sensitivity checks.

Texts with no mention write nothing (about 90 % of texts), so the table is small.
Resumable: restarts from the highest src_rowid already written; INSERT OR IGNORE prevents duplicates.

Usage:
    python -m etl.extract_tickers [--db output/reddit.sqlite3] [--window N] [--limit-rows N] [--rebuild]
"""

import argparse
import sys
import time

from etl.common import DEFAULT_DB, connect
from etl.ticker_dict import TickerMatcher
from pipeline_logs import append_event, run_id

EXTRACTOR_VERSION = "1.0"

SCHEMA = """CREATE TABLE IF NOT EXISTS ticker_mentions (
    content_id TEXT NOT NULL,               -- reddit_content.id
    ticker TEXT NOT NULL,                   -- one of the 34 symbols, e.g. TSLA, BTC-USD, GC=F
    mention_count INTEGER NOT NULL,         -- strong + weak mentions in this text
    strong_count INTEGER NOT NULL,          -- clear mentions only
    src_rowid INTEGER NOT NULL,             -- processed_text.src_rowid (used to resume)
    PRIMARY KEY (content_id, ticker)) WITHOUT ROWID"""


def process(db_path=DEFAULT_DB, window=200_000, limit_rows=None, rebuild=False):
    db = connect(db_path)
    try:
        return _process(db, window, limit_rows, rebuild)
    finally:
        db.close()


def _process(db, window, limit_rows, rebuild):
    matcher = TickerMatcher()
    if rebuild:
        db.execute("DROP TABLE IF EXISTS ticker_mentions")
        db.execute("DROP INDEX IF EXISTS ticker_mentions_by_ticker")
    db.execute(SCHEMA)
    db.commit()
    done = db.execute("SELECT COALESCE(MAX(src_rowid), 0) FROM ticker_mentions").fetchone()[0]
    last = db.execute("SELECT MAX(src_rowid) FROM processed_text").fetchone()[0] or 0
    if limit_rows:
        last = min(last, done + limit_rows)
    this_run = run_id()
    append_event(db, "extract_tickers_start", run_id=this_run, version=EXTRACTOR_VERSION, resume_from=done)
    totals = {"texts": 0, "texts_with_mention": 0, "mention_rows": 0}
    started = time.time()
    while done < last:
        upper = min(done + window, last)
        out = []
        # filtered_text = processed_text minus the rows T2 rejected (bots, too short, non-English)
        rows = db.execute("SELECT src_rowid, content_id, subreddit, final_text FROM filtered_text "
                          "WHERE src_rowid > ? AND src_rowid <= ?", (done, upper)).fetchall()
        for rowid, content_id, sub, text in rows:
            strong, weak = matcher.find_split(text, sub)
            if strong or weak:
                totals["texts_with_mention"] += 1
                for ticker in strong.keys() | weak.keys():
                    out.append((content_id, ticker, strong[ticker] + weak[ticker], strong[ticker], rowid))
        db.executemany("INSERT OR IGNORE INTO ticker_mentions VALUES (?,?,?,?,?)", out)
        db.commit()
        done = upper
        totals["texts"] += len(rows)
        totals["mention_rows"] += len(out)
        print("rowid %d/%d  texts %d  with mention %d  (%.0f texts/s)"
              % (done, last, totals["texts"], totals["texts_with_mention"],
                 totals["texts"] / max(time.time() - started, 1e-9)), flush=True)
    # Index for T5 (aggregate by ticker); built once at the end.
    db.execute("CREATE INDEX IF NOT EXISTS ticker_mentions_by_ticker ON ticker_mentions(ticker)")
    db.commit()
    append_event(db, "extract_tickers_done", run_id=this_run, version=EXTRACTOR_VERSION, **totals)
    return totals


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--window", type=int, default=200_000, help="processed_text rowids per batch")
    parser.add_argument("--limit-rows", type=int, help="stop after scanning this many rowids (trials)")
    parser.add_argument("--rebuild", action="store_true", help="drop ticker_mentions and start over")
    args = parser.parse_args(argv)
    print("done:", process(args.db, args.window, args.limit_rows, args.rebuild))
    return 0


if __name__ == "__main__":
    sys.exit(main())
