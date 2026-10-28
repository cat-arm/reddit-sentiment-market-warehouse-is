"""Report per-month progress: archive downloaded, imported to SQLite, market data fetched."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # so `python ingest/<file>.py` finds the ingest package

import argparse
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

from ingest.market_fetch import TICKERS, date_arg, next_month, utc

MONTH_RE = re.compile(r"\d{4}-\d{2}")
TORRENT_COMMENT_RE = re.compile(rb"from (\d{4}-\d{2})")


def torrent_months(data_dir):
    """Months whose archive is described by a local .torrent file's comment field."""
    months = set()
    for path in sorted(Path(data_dir).glob("*.torrent")):
        match = TORRENT_COMMENT_RE.search(path.read_bytes())
        if match:
            months.add(match.group(1).decode())
    return months


def downloaded_months(data_dir):
    """Months with an RS_ and/or RC_ archive already present on disk, wherever nested."""
    months = defaultdict(lambda: {"submissions": False, "comments": False})
    for path in Path(data_dir).glob("**/RS_*.zst"):
        match = MONTH_RE.search(path.name)
        if match:
            months[match.group()]["submissions"] = True
    for path in Path(data_dir).glob("**/RC_*.zst"):
        match = MONTH_RE.search(path.name)
        if match:
            months[match.group()]["comments"] = True
    return months


def archive_status(month, downloaded):
    have = downloaded.get(month, {"submissions": False, "comments": False})
    if have["submissions"] and have["comments"]:
        return "downloaded"
    if have["submissions"] or have["comments"]:
        return "partial"
    return "missing"


def table_exists(connection, name):
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def reddit_import_status(connection, month):
    if connection is None or not table_exists(connection, "reddit_content"):
        return "not imported", 0, 0
    counts = dict(connection.execute(
        "SELECT content_type, COUNT(*) FROM reddit_content WHERE source_archive LIKE ? "
        "GROUP BY content_type", ("%_{}.zst".format(month),)
    ).fetchall())
    submissions, comments = counts.get("submission", 0), counts.get("comment", 0)
    status = "imported" if submissions or comments else "not imported"
    return status, submissions, comments


def market_status(connection, month, tickers=TICKERS):
    if connection is None or not table_exists(connection, "market_bars"):
        return "not fetched", 0, 0, 0
    start, end = date_arg(month + "-01"), next_month(date_arg(month + "-01"))
    covered = connection.execute(
        "SELECT COUNT(DISTINCT ticker) FROM market_bars WHERE timestamp_utc >= ? AND timestamp_utc < ?",
        (utc(start), utc(end))
    ).fetchone()[0]
    gaps = connection.execute(
        "SELECT COUNT(*) FROM market_gaps WHERE timestamp_utc >= ? AND timestamp_utc < ?",
        (utc(start), utc(end))
    ).fetchone()[0] if table_exists(connection, "market_gaps") else 0
    unresolved = connection.execute(
        "SELECT COUNT(DISTINCT ticker) FROM market_windows WHERE status IN ('needs_review', 'unavailable') "
        "AND start_utc < ? AND end_utc > ?", (utc(end), utc(start))
    ).fetchone()[0] if table_exists(connection, "market_windows") else 0
    if covered == 0:
        status = "not fetched"
    elif covered < len(tickers) or unresolved:
        status = "partial"
    else:
        status = "fetched"
    return status, covered, gaps, unresolved


def all_months(data_dir, connection):
    months = set(torrent_months(data_dir)) | set(downloaded_months(data_dir))
    if connection is not None and table_exists(connection, "reddit_content"):
        for (archive,) in connection.execute(
                "SELECT DISTINCT source_archive FROM reddit_content"):
            match = MONTH_RE.search(archive or "")
            if match:
                months.add(match.group())
    if connection is not None and table_exists(connection, "market_bars"):
        for (timestamp,) in connection.execute(
                "SELECT DISTINCT substr(timestamp_utc, 1, 7) FROM market_bars"):
            if MONTH_RE.fullmatch(timestamp or ""):
                months.add(timestamp)
    return sorted(months)


def report(data_dir, db_path):
    connection = sqlite3.connect(str(db_path)) if Path(db_path).is_file() else None
    downloaded = downloaded_months(data_dir)
    try:
        months = all_months(data_dir, connection)
        if not months:
            print("No archives, imports, or market data found yet.")
            return []
        rows = []
        current_year = None
        for month in months:
            year = month[:4]
            if year != current_year:
                print("\n{}".format(year))
                current_year = year
            archive = archive_status(month, downloaded)
            import_state, submissions, comments = reddit_import_status(connection, month)
            market_state, covered, gaps, unresolved = market_status(connection, month)
            print("  {}  archive={:<10} reddit={:<12}(posts={} comments={})  "
                  "market={:<10}(tickers={}/{} gaps={} unresolved={})".format(
                      month, archive, import_state, submissions, comments,
                      market_state, covered, len(TICKERS), gaps, unresolved))
            rows.append((month, archive, import_state, market_state))
        return rows
    finally:
        if connection is not None:
            connection.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data"),
                        help="directory holding .torrent files and downloaded archives")
    parser.add_argument("--db", type=Path, default=Path("output/reddit.sqlite3"))
    args = parser.parse_args(argv)
    report(args.data, args.db)
    return 0


if __name__ == "__main__":
    sys.exit(main())
