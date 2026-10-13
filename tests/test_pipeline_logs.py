import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import zstandard as zstd
from pipeline_logs import export_report
from reddit_extract import database, import_file


class PipelineLogTest(unittest.TestCase):
    def test_completed_repeat_failed_and_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "RS_2025-09.zst"
            records = [dict(id="a", subreddit="stocks", title="Hello"),
                       dict(id="b", subreddit="unrelated", title="Ignore")]
            path.write_bytes(zstd.ZstdCompressor().compress(
                ("\n".join(json.dumps(r) for r in records) + "\n").encode()))
            db_path = root / "test.sqlite3"
            with database(db_path) as db:
                self.assertEqual(import_file(db, path, "submissions")["inserted"], 1)
                self.assertEqual(import_file(db, path, "submissions")["inserted"], 0)
                with self.assertRaises(FileNotFoundError):
                    import_file(db, root / "RC_2025-09.zst", "comments")
                db.execute("CREATE TABLE market_bars (ticker,timestamp_utc,open,high,low,close,volume)")
                db.execute("INSERT INTO market_bars VALUES ('AAPL','2025-09-01T14:30:00+00:00',1,2,1,NULL,0)")
            events = [json.loads(line) for line in (root / "logs/pipeline_events.jsonl").read_text().splitlines()]
            self.assertEqual(events[1]["stats"]["read"], 2)
            self.assertEqual(events[3]["skipped_existing"], 1)
            self.assertEqual(events[-1]["event"], "reddit_import_failed")
            report = export_report(db_path, root / "reports")
            row = report["summary"][0]
            self.assertEqual(row["reddit_total"], 1)
            self.assertEqual(row["reddit_completion"], "not_verified")
            self.assertEqual(row["market_null_price_rows"], 1)
            self.assertEqual(report["months"]["2025-09"]["reddit_by_subreddit"]["bitcoin"]["comment"], 0)
            self.assertTrue((root / "reports/monthly_pipeline_summary.csv").exists())


if __name__ == "__main__":
    unittest.main()