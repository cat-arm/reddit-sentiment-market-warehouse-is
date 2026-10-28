"""Persist pipeline events and export all-month SQLite inventory summaries."""
import argparse
import csv
import json
import re
import sqlite3
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

GROUPS = ("wallstreetbets", "stocks", "investing", "stockmarket", "cryptocurrency",
          "bitcoin", "dogecoin", "daytrading", "options")


def append_event(db, event, **values):
    path = db.execute("PRAGMA database_list").fetchone()[2]
    if not path:
        return
    folder = Path(path).parent / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    record = dict(event=event, logged_at_utc=datetime.now(timezone.utc).isoformat(), **values)
    with (folder / "pipeline_events.jsonl").open("a", encoding="utf-8") as dest:
        dest.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")


def run_id():
    return uuid.uuid4().hex


def export_report(db_path, folder):
    db_path, folder = Path(db_path), Path(folder)
    db = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    months = defaultdict(lambda: {"reddit": [], "market": [], "market_windows": [], "suspected_market_gaps": []})
    try:
        db.execute("BEGIN")
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "reddit_content" in tables:
            for row in db.execute("""SELECT source_archive, content_type, lower(subreddit) subreddit,
                text_status, count(*) rows, min(created_utc) first_created_utc,
                max(created_utc) last_created_utc, sum(created_utc IS NULL) missing_timestamp
                FROM reddit_content GROUP BY 1,2,3,4"""):
                match = re.search(r"\d{4}-\d{2}", row["source_archive"] or "")
                if match:
                    months[match.group()]["reddit"].append(dict(row))
        if "market_bars" in tables:
            for row in db.execute("""SELECT substr(timestamp_utc,1,7) month, ticker,
                count(*) stored_rows, min(timestamp_utc) first_utc, max(timestamp_utc) last_utc,
                sum(open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL) null_price_rows,
                sum(volume IS NULL) null_volume_rows,
                sum(open IS NOT NULL AND high IS NOT NULL AND low IS NOT NULL
                    AND close IS NOT NULL AND volume IS NOT NULL) complete_ohlcv_rows,
                sum(volume=0) zero_volume_rows FROM market_bars GROUP BY 1,2 ORDER BY 1,2"""):
                months[row["month"]]["market"].append(dict(row))
        if "market_windows" in tables:
            for row in db.execute("SELECT * FROM market_windows ORDER BY ticker,start_utc"):
                start, end = datetime.fromisoformat(row["start_utc"]), datetime.fromisoformat(row["end_utc"])
                point = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                while point < end:
                    months[point.strftime("%Y-%m")]["market_windows"].append(dict(row))
                    point = point.replace(year=point.year + (point.month == 12), month=point.month % 12 + 1)
        if "market_gaps" in tables:
            for row in db.execute("SELECT * FROM market_gaps ORDER BY timestamp_utc,ticker"):
                months[row["timestamp_utc"][:7]]["suspected_market_gaps"].append(dict(row))
    finally:
        db.close()
    events = []
    for events_path in (db_path.parent / "logs").glob("*events.jsonl"):
        for line in events_path.read_text(encoding="utf-8").splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                continue
    summary = []
    for month, detail in sorted(months.items()):
        posts = sum(r["rows"] for r in detail["reddit"] if r["content_type"] == "submission")
        comments = sum(r["rows"] for r in detail["reddit"] if r["content_type"] == "comment")
        detail["reddit_by_subreddit"] = {
            group: {kind: sum(r["rows"] for r in detail["reddit"]
                             if r["subreddit"] == group and r["content_type"] == kind)
                    for kind in ("submission", "comment")} for group in GROUPS}
        detail["import_events"] = [e for e in events if month in e.get("source_archive", "")]
        completed = {e.get("kind") for e in detail["import_events"] if e["event"] == "reddit_import_completed"}
        summary.append(dict(month=month, reddit_posts=posts, reddit_comments=comments,
            reddit_total=posts + comments, reddit_completion="logged_complete" if
            completed == {"submissions", "comments"} else "not_verified" if posts + comments else "no_rows",
            market_tickers=len(detail["market"]), market_rows=sum(r["stored_rows"] for r in detail["market"]),
            market_null_price_rows=sum(r["null_price_rows"] for r in detail["market"]),
            market_null_volume_rows=sum(r["null_volume_rows"] for r in detail["market"]),
            suspected_market_gaps=len(detail["suspected_market_gaps"])))
    report = dict(generated_at_utc=datetime.now(timezone.utc).isoformat(),
        notes=["Reddit months use archive names; market months use UTC bar timestamps.",
               "Historical read/selected counts are unknown unless preserved in import events.",
               "Stored rows do not prove full imports; active imports may be partial.",
               "Market gaps are heuristic suspects. Holidays/early closes require calendars.",
               "Overlapping market windows must not be summed as unique bars.",
               "Author names and message text are excluded."], summary=summary, months=dict(sorted(months.items())))
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / "monthly_pipeline_report.json"
    temp = dest.with_suffix(".json.partial")
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(dest)
    with (folder / "monthly_pipeline_summary.csv").open("w", newline="", encoding="utf-8-sig") as dest:
        writer = csv.DictWriter(dest, fieldnames=list(summary[0]) if summary else ["month"])
        writer.writeheader()
        writer.writerows(summary)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("output/reddit.sqlite3"))
    parser.add_argument("--output", type=Path, default=Path("output/logs"))
    args = parser.parse_args()
    report = export_report(args.db, args.output)
    for row in report["summary"]:
        print("{month}: Reddit={reddit_total:,} Market={market_rows:,} tickers={market_tickers}".format(**row))
    print("Saved reports to", args.output)


if __name__ == "__main__":
    main()