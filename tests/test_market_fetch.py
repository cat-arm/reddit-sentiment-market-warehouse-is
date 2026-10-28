from contextlib import closing
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ingest.market_fetch import database, date_arg, expected_closed, find_gaps, run_window, save, utc


class MarketFetchTest(unittest.TestCase):
    def test_retry_empty_and_idempotent_save(self):
        start = date_arg("2024-10-01")
        end = start + timedelta(days=1)
        calls = []

        def provider(ticker, left, right):
            calls.append((left, right))
            if len(calls) == 1:
                return []
            return [(ticker, utc(start), 1., 2., 1., 1.5, 42., utc(start))]

        with tempfile.TemporaryDirectory() as directory:
            with closing(database(Path(directory) / "test.sqlite3")) as db:
                result = run_window(db, "AAPL", start, end, retries=3, pause=0, provider=provider)
                self.assertEqual(result[:3], ("complete", 1, 0))
                self.assertEqual(len(calls), 2)
                run_window(db, "AAPL", start, end, retries=1, pause=0, provider=provider)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM market_bars").fetchone()[0], 1)

    def test_repair_missing_crypto_hour_and_audit_unresolved(self):
        start = date_arg("2024-10-01")
        end = start + timedelta(hours=3)

        def bar(hour):
            return ("BTC-USD", utc(start + timedelta(hours=hour)), 1., 1., 1., 1., 0., utc(start))

        calls = []

        def provider(ticker, left, right):
            calls.append(left)
            if left == start + timedelta(hours=1):
                return [bar(1)]
            return [bar(0), bar(2)]

        with tempfile.TemporaryDirectory() as directory:
            with closing(database(Path(directory) / "test.sqlite3")) as db:
                result = run_window(db, "BTC-USD", start, end, retries=2, pause=0, provider=provider)
                self.assertEqual(result[:3], ("complete", 3, 0))
                self.assertIn(start + timedelta(hours=1), calls)

                failed = run_window(db, "DOGE-USD", start, end, retries=2, pause=0,
                                    provider=lambda *args: [])
                self.assertEqual(failed[0], "needs_review")
                self.assertEqual(db.execute("SELECT status FROM market_windows WHERE ticker='DOGE-USD'")
                                 .fetchone()[0], "needs_review")

    def test_market_closure_is_not_a_hole(self):
        friday = date_arg("2024-10-04") + timedelta(hours=19)
        monday = friday + timedelta(days=3)
        rows = [("AAPL", utc(dt), 1., 1., 1., 1., 1.) for dt in (friday, monday)]
        self.assertEqual(find_gaps(rows, "AAPL"), [])

    def test_partial_saved_data_not_complete_after_error(self):
        start = date_arg("2024-10-01")
        end = start + timedelta(days=1)
        with tempfile.TemporaryDirectory() as directory:
            with closing(database(Path(directory) / "test.sqlite3")) as db:
                db.execute("INSERT INTO market_bars VALUES (?,?,?,?,?,?,?,?)",
                           ("AAPL", utc(start), 1., 1., 1., 1., 1., utc(start)))
                def failed(*args):
                    raise ConnectionError("offline")
                result = run_window(db, "AAPL", start, end, retries=2,
                                    pause=0, provider=failed)
                self.assertEqual(result[0], "needs_review")

    def test_null_volume_is_flagged(self):
        start = date_arg("2024-10-01")
        bar = ("AAPL", utc(start), 1., 1., 1., 1., None, utc(start))
        self.assertEqual(find_gaps([bar], "AAPL"), [start])

    def test_crypto_window_boundary_gap(self):
        start = date_arg("2024-10-01")
        end = start + timedelta(hours=3)
        bar = ("BTC-USD", utc(start + timedelta(hours=1)), 1., 1., 1., 1., 1., utc(start))
        self.assertEqual(find_gaps([bar], "BTC-USD", start, end),
                         [start, start + timedelta(hours=2)])

    def test_futures_maintenance_hour_is_retained_not_retried(self):
        closed = date_arg("2024-10-01") + timedelta(hours=21)
        bar = ("ES=F", utc(closed), None, None, None, None, 0., utc(closed))
        self.assertEqual(find_gaps([bar], "ES=F"), [])

    def test_expected_weekend_closure(self):
        saturday = date_arg("2024-09-28")
        sunday = saturday + timedelta(days=1)
        self.assertTrue(expected_closed("AAPL", saturday, sunday))
        self.assertTrue(expected_closed("ES=F", saturday, sunday))
        self.assertFalse(expected_closed("BTC-USD", saturday, sunday))
        self.assertTrue(expected_closed("AAPL", sunday, sunday + timedelta(days=1)))
        self.assertFalse(expected_closed("ES=F", sunday, sunday + timedelta(days=1)))

    def test_futures_weekend_placeholders_are_not_gaps(self):
        weekend = date_arg("2024-10-05")
        active = date_arg("2024-10-07")
        placeholder = ("ES=F", utc(weekend), None, None, None, None, 0., utc(weekend))
        self.assertEqual(find_gaps([placeholder], "ES=F"), [])
        missing_trade = ("ES=F", utc(active), None, None, None, None, 0., utc(active))
        self.assertEqual(find_gaps([missing_trade], "ES=F"), [active])

    def test_null_retry_does_not_overwrite_valid_prices(self):
        day = date_arg("2024-10-01")
        with tempfile.TemporaryDirectory() as directory:
            with closing(database(Path(directory) / "test.sqlite3")) as db:
                save(db, [("ES=F", utc(day), 1., 2., 1., 1.5, 5., utc(day))])
                save(db, [("ES=F", utc(day), None, None, None, None, 0., utc(day))])
                self.assertEqual(db.execute("SELECT close FROM market_bars").fetchone()[0], 1.5)

    def test_expired_hourly_history_is_recorded(self):
        day = date_arg("2024-09-28")
        def expired(*args):
            raise ValueError("The requested range must be within the last 730 days.")
        with tempfile.TemporaryDirectory() as directory:
            with closing(database(Path(directory) / "test.sqlite3")) as db:
                result = run_window(db, "BTC-USD", day, day + timedelta(days=1),
                                    retries=2, pause=0, provider=expired)
                self.assertEqual(result[0], "unavailable")


if __name__ == "__main__":
    unittest.main()