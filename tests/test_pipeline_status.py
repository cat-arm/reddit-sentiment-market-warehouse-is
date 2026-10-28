from contextlib import contextmanager
import sqlite3
import tempfile
import unittest
from pathlib import Path

from ingest.pipeline_status import (archive_status, downloaded_months, market_status,
                              reddit_import_status, torrent_months)


@contextmanager
def committing(connection):
    """Commit and then CLOSE the connection (sqlite3's own `with` only commits; an open file cannot be deleted on Windows)."""
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


class PipelineStatusTest(unittest.TestCase):
    def test_torrent_and_downloaded_months(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "reddit-abc.torrent").write_bytes(
                b"d7:comment44:Reddit comments and submissions from 2024-10e")
            submissions = root / "reddit-2024-10" / "reddit" / "submissions"
            submissions.mkdir(parents=True)
            (submissions / "RS_2024-10.zst").write_bytes(b"")

            self.assertEqual(torrent_months(root), {"2024-10"})
            downloaded = downloaded_months(root)
            self.assertEqual(archive_status("2024-10", downloaded), "partial")
            self.assertEqual(archive_status("2024-11", downloaded), "missing")

            comments = root / "reddit-2024-10" / "reddit" / "comments"
            comments.mkdir(parents=True)
            (comments / "RC_2024-10.zst").write_bytes(b"")
            self.assertEqual(archive_status("2024-10", downloaded_months(root)), "downloaded")

    def test_reddit_import_status_reads_source_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "test.sqlite3"
            with committing(sqlite3.connect(db_path)) as connection:
                connection.execute("""CREATE TABLE reddit_content (
                    content_type TEXT, source_archive TEXT)""")
                connection.executemany(
                    "INSERT INTO reddit_content VALUES (?, ?)",
                    [("submission", "RS_2024-10.zst"), ("comment", "RC_2024-10.zst"),
                     ("comment", "RC_2024-10.zst")])
            with committing(sqlite3.connect(db_path)) as connection:
                self.assertEqual(reddit_import_status(connection, "2024-10"),
                                 ("imported", 1, 2))
                self.assertEqual(reddit_import_status(connection, "2024-11"),
                                 ("not imported", 0, 0))
            self.assertEqual(reddit_import_status(None, "2024-10"), ("not imported", 0, 0))

    def test_market_status_partial_when_ticker_or_review_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "test.sqlite3"
            with committing(sqlite3.connect(db_path)) as connection:
                connection.execute("""CREATE TABLE market_bars (
                    ticker TEXT, timestamp_utc TEXT)""")
                connection.execute("""CREATE TABLE market_gaps (
                    ticker TEXT, timestamp_utc TEXT, reason TEXT)""")
                connection.execute("""CREATE TABLE market_windows (
                    ticker TEXT, start_utc TEXT, end_utc TEXT, status TEXT)""")
                connection.execute(
                    "INSERT INTO market_bars VALUES ('AAPL', '2024-10-01T00:00:00+00:00')")
                connection.execute(
                    "INSERT INTO market_windows VALUES ('AAPL', '2024-10-01T00:00:00+00:00', "
                    "'2024-10-15T00:00:00+00:00', 'needs_review')")
            with committing(sqlite3.connect(db_path)) as connection:
                status, covered, gaps, unresolved = market_status(
                    connection, "2024-10", tickers=("AAPL", "MSFT"))
                self.assertEqual(status, "partial")
                self.assertEqual((covered, unresolved), (1, 1))
            self.assertEqual(market_status(None, "2024-10")[0], "not fetched")


if __name__ == "__main__":
    unittest.main()
