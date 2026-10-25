"""Keep the text-only results before the post-title context rebuild (cleaner_version 2.0, 2026-10-24).

Renames, never copies or deletes rows:
    sentiment_vader, sentiment_finbert, sentiment_item, ticker_mentions, text_filter  ->  <name>_v1
so the rebuilt pipeline can start from empty tables and scripts/compare_context_effect.py can later measure how
much the post title changed the sentiment of the comments.  A table that is already archived (or missing) is skipped,
so the script is safe to run twice.

Usage:  python scripts/archive_sentiment_v1.py [--db output/reddit.sqlite3]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from etl.common import DEFAULT_DB, connect  # noqa: E402

TABLES = ("sentiment_vader", "sentiment_finbert", "sentiment_item", "ticker_mentions", "text_filter")


def archive(db_path=DEFAULT_DB):
    db = connect(db_path)
    try:
        existing = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        done = {}
        for name in TABLES:
            if name in existing and name + "_v1" not in existing:
                if name == "text_filter":
                    db.execute("DROP VIEW IF EXISTS filtered_text")      # the view reads text_filter
                db.execute('ALTER TABLE "%s" RENAME TO "%s_v1"' % (name, name))
                done[name] = "renamed"
            else:
                done[name] = "skipped (%s)" % ("already archived" if name + "_v1" in existing else "missing")
        db.commit()
        return done
    finally:
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    print(archive(parser.parse_args(argv).db))
    return 0


if __name__ == "__main__":
    sys.exit(main())
