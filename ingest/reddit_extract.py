"""Stream monthly Reddit archives into SQLite; fetch and export via CLI."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # so `python ingest/<file>.py` finds the ingest package

import argparse
import io
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import zstandard as zstd
from ingest.pipeline_logs import append_event, run_id

SUBREDDITS = frozenset(x.casefold() for x in (
	"wallstreetbets", "stocks", "investing", "StockMarket", "CryptoCurrency",
	"Bitcoin", "dogecoin", "Daytrading", "options"))
BATCH_SIZE = 1000
FIELDS = {
	"id": "TEXT PRIMARY KEY", "content_type": "TEXT NOT NULL",
	"subreddit": "TEXT NOT NULL", "created_utc": "INTEGER",
	"title": "TEXT", "selftext": "TEXT", "body": "TEXT", "link_id": "TEXT",
	"parent_id": "TEXT", "is_self": "INTEGER", "url": "TEXT", "domain": "TEXT",
	"removed_by_category": "TEXT", "text_status": "TEXT NOT NULL",
	"source_archive": "TEXT NOT NULL", "score": "INTEGER", "upvote_ratio": "REAL",
	"num_comments": "INTEGER", "author": "TEXT", "retrieved_on": "INTEGER",
	"permalink": "TEXT", "stickied": "INTEGER", "distinguished": "TEXT",
	"locked": "INTEGER", "over_18": "INTEGER", "is_submitter": "INTEGER",
	"edited": "INTEGER",
}


def database(path):
	Path(path).parent.mkdir(parents=True, exist_ok=True)
	db = sqlite3.connect(str(path), timeout=60)
	db.execute("CREATE TABLE IF NOT EXISTS reddit_content ({})".format(
		", ".join(k + " " + v for k, v in FIELDS.items())))
	db.execute("CREATE INDEX IF NOT EXISTS reddit_comments_by_post ON "
			   "reddit_content(link_id, created_utc, id) WHERE content_type='comment'")
	db.execute("CREATE INDEX IF NOT EXISTS reddit_by_hour ON "
			   "reddit_content(created_utc, subreddit, content_type)")
	db.commit()
	return db


def timestamp(value):
	try:
		return int(value)
	except (ValueError, TypeError, OverflowError):
		return None


def fullname(value, prefix):
	if not isinstance(value, str) or not value:
		return None
	if value.startswith(prefix):
		return value
	return None if "_" in value else prefix + value


def text_status(value):
	if value is None:
		return "missing"
	if value in ("[removed]", "[deleted]"):
		return value[1:-1]
	return "available" if value.strip() else "empty"


def rows_from_zst(path, stats):
	with open(path, "rb") as raw:
		with zstd.ZstdDecompressor(max_window_size=2**31).stream_reader(raw) as reader:
			with io.TextIOWrapper(reader, encoding="utf-8", errors="replace") as lines:
				for line in lines:
					stats["read"] += 1
					try:
						item = json.loads(line)
					except (ValueError, UnicodeError):
						stats["invalid"] += 1
						continue
					if isinstance(item, dict):
						yield item
					else:
						stats["invalid"] += 1


def import_file(connection, path, kind):
	stats = dict(read=0, invalid=0, selected=0, inserted=0)
	metadata = dict(run_id=run_id(), source_archive=Path(path).name, kind=kind)
	append_event(connection, "reddit_import_started", **metadata)
	try:
		result = _import_file(connection, path, kind, stats)
	except Exception as exc:
		append_event(connection, "reddit_import_failed", **metadata, stats=stats,
					 error="{}: {}".format(type(exc).__name__, exc), complete=False)
		raise
	append_event(connection, "reddit_import_completed", **metadata, stats=result,
				 complete=True, skipped_existing=result["selected"] - result["inserted"])
	return result


def _import_file(connection, path, kind, stats):
	if kind not in ("submissions", "comments"):
		raise ValueError("kind must be submissions or comments")
	is_post = kind == "submissions"
	columns = list(FIELDS)
	statement = "INSERT OR IGNORE INTO reddit_content ({}) VALUES ({})".format(
		",".join(columns), ",".join("?" for _ in columns))
	batch = []

	def flush():
		with connection:
			before = connection.total_changes
			connection.executemany(statement, batch)
		stats["inserted"] += connection.total_changes - before
		batch.clear()

	for item in rows_from_zst(path, stats):
		sub = item.get("subreddit")
		if not isinstance(sub, str) or sub.casefold() not in SUBREDDITS:
			continue
		ident = fullname(item.get("id"), "t3_" if is_post else "t1_")
		link = fullname(item.get("link_id"), "t3_") if not is_post else None
		parent = item.get("parent_id") if not is_post else None
		if not ident or (not is_post and (not link or not isinstance(parent, str))):
			stats["invalid"] += 1
			continue
		row = dict.fromkeys(columns)
		row.update(id=ident, content_type="submission" if is_post else "comment",
				   subreddit=sub, source_archive=Path(path).name,
				   link_id=link, parent_id=parent)
		common = ("author", "permalink", "distinguished")
		strings = common + (("title", "selftext", "url", "domain", "removed_by_category")
							if is_post else ("body",))
		for key in strings:
			row[key] = item.get(key) if isinstance(item.get(key), str) else None
		for key in ("created_utc", "retrieved_on", "edited"):
			row[key] = timestamp(item.get(key))
		for key in (("score", "num_comments") if is_post else ("score",)):
			row[key] = item.get(key) if type(item.get(key)) is int else None
		for key in (("stickied", "locked", "is_self", "over_18") if is_post
					else ("stickied", "locked", "is_submitter")):
			row[key] = int(item[key]) if type(item.get(key)) is bool else None
		if is_post and type(item.get("upvote_ratio")) in (float, int):
			row["upvote_ratio"] = float(item["upvote_ratio"])
		value = (row["selftext"] or row["title"]) if is_post else row["body"]
		row["text_status"] = text_status(value)
		batch.append(tuple(row[k] for k in columns))
		stats["selected"] += 1
		if len(batch) >= BATCH_SIZE:
			flush()
			if stats["selected"] % 100000 == 0:
				print("Progress: {}".format(stats), flush=True)
	if batch:
		flush()
	return stats


def find_torrent(data_dir, month):
	for path in sorted(Path(data_dir).glob("*.torrent")):
		if re.search(rb"from " + month.encode(), path.read_bytes()):
			return path
	return None


def find_archive(data_dir, month, prefix):
	return next(iter(sorted(Path(data_dir).glob("**/{}_{}.zst".format(prefix, month)))), None)


def archive_ready(data_dir, month):
	rs, rc = (find_archive(data_dir, month, p) for p in ("RS", "RC"))
	controls = list(Path(data_dir).glob("reddit-{}/**/*.aria2".format(month)))
	return bool(rs and rc and not controls), rs, rc


def fetch_month(connection, data_dir, month, keep_archive=False, run=subprocess.run):
	ready, rs, rc = archive_ready(data_dir, month)
	if not ready:
		torrent = find_torrent(data_dir, month)
		if torrent is None:
			raise OSError("No .torrent for {} under {}".format(month, data_dir))
		target = Path(data_dir) / ("reddit-" + month)
		print("Downloading {} -> {}".format(torrent, target), flush=True)
		result = run(["aria2c", "--seed-time=0", "--dir=" + str(target), str(torrent)])
		if result.returncode:
			raise OSError("aria2c failed (exit {})".format(result.returncode))
		ready, rs, rc = archive_ready(data_dir, month)
		if not ready:
			raise OSError("Archive incomplete for " + month)
	for path, kind in ((rs, "submissions"), (rc, "comments")):
		print("Importing {}: {}".format(kind, path), flush=True)
		print(import_file(connection, path, kind), flush=True)
	if not keep_archive:
		rs.unlink()
		rc.unlink()
		print("Deleted imported archives", flush=True)


def export_json(connection, output):
	output = Path(output)
	output.parent.mkdir(parents=True, exist_ok=True)
	temporary = output.with_name(output.name + ".partial")
	post_count = comment_count = 0
	try:
		with temporary.open("w", encoding="utf-8") as dest:
			dest.write("[\n")
			for row in connection.execute("SELECT id,subreddit,title,selftext,created_utc "
										  "FROM reddit_content WHERE content_type='submission' ORDER BY id"):
				post = dict(zip(("id", "subreddit", "title", "selftext", "created_utc"), row))
				if post_count:
					dest.write(",\n")
				dest.write(json.dumps(post, ensure_ascii=False)[:-1] + ', "comments": [')
				local = 0
				for reply in connection.execute("SELECT id,parent_id,link_id,body,created_utc "
					"FROM reddit_content WHERE content_type='comment' AND link_id=? "
					"ORDER BY created_utc,id", (row[0],)):
					if local:
						dest.write(", ")
					dest.write(json.dumps(dict(zip(("id", "parent_id", "link_id", "body", "created_utc"), reply)), ensure_ascii=False))
					local += 1
					comment_count += 1
				dest.write("]}")
				post_count += 1
			dest.write("\n]\n")
		temporary.replace(output)
	finally:
		temporary.unlink(missing_ok=True)
	return post_count, comment_count


def main(argv=None):
	parser = argparse.ArgumentParser(description=__doc__)
	commands = parser.add_subparsers(dest="command", required=True)
	importer = commands.add_parser("import")
	importer.add_argument("--db", required=True, type=Path)
	importer.add_argument("--submissions", action="append", type=Path, default=[])
	importer.add_argument("--comments", action="append", type=Path, default=[])
	fetcher = commands.add_parser("fetch")
	fetcher.add_argument("month")
	fetcher.add_argument("--db", required=True, type=Path)
	fetcher.add_argument("--data", type=Path, default=Path("data"))
	fetcher.add_argument("--keep-archive", action="store_true")
	exporter = commands.add_parser("export")
	exporter.add_argument("--db", required=True, type=Path)
	exporter.add_argument("--output", required=True, type=Path)
	args = parser.parse_args(argv)
	if args.command == "fetch" and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", args.month):
		parser.error("expected YYYY-MM")
	if args.command == "import" and not (args.submissions or args.comments):
		parser.error("provide --submissions and/or --comments")
	if args.command == "export" and not args.db.is_file():
		parser.error("database does not exist")
	try:
		connection = database(args.db)
		try:
			if args.command == "fetch":
				fetch_month(connection, args.data, args.month, args.keep_archive)
			elif args.command == "import":
				for kind in ("submissions", "comments"):
					for path in getattr(args, kind):
						print("Importing {}: {}".format(kind, path), flush=True)
						print(import_file(connection, path, kind), flush=True)
			else:
				print("Exported posts/comments: {}".format(export_json(connection, args.output)))
		finally:
			connection.close()
	except (OSError, sqlite3.Error, zstd.ZstdError) as exc:
		print("Error: {}".format(exc), file=sys.stderr)
		return 1
	return 0


if __name__ == "__main__":
	sys.exit(main())
