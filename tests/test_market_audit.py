from contextlib import closing
import unittest
import sqlite3
import tempfile
from pathlib import Path

from ingest.market_fetch import audit, database, date_arg, expected_hours, month_arg, next_month, utc


class MarketAuditTest(unittest.TestCase):
    def test_inclusive_month_range(self):
        self.assertEqual(month_arg("nov24"), date_arg("2024-11-01"))
        self.assertEqual(next_month(month_arg("jan25")), date_arg("2025-02-01"))
        self.assertEqual(next_month(month_arg("dec24")), date_arg("2025-01-01"))
        with self.assertRaises(Exception):
            month_arg("november24")

    def test_expected_slots_for_september_weekend_and_monday(self):
        saturday = date_arg("2024-09-28")
        sunday = date_arg("2024-09-29")
        monday = date_arg("2024-09-30")
        self.assertEqual(len(expected_hours("ES=F", saturday)), 0)
        self.assertEqual(len(expected_hours("ES=F", sunday)), 2)
        self.assertEqual(len(expected_hours("ES=F", monday)), 23)
        self.assertEqual(len(expected_hours("AAPL", monday)), 7)
        self.assertEqual(len(expected_hours("BTC-USD", saturday)), 24)

    def test_two_day_window_covers_one_day(self):
        day = date_arg("2024-10-01")
        with tempfile.TemporaryDirectory() as directory:
            with closing(database(Path(directory) / "test.sqlite3")) as db:
                db.execute("INSERT INTO market_windows VALUES (?,?,?,?,?,?,?,?,?)",
                           ("BTC-USD", utc(day), utc(day.replace(day=3)),
                            "complete", 48, 0, 1, None, utc(day)))
                for hour in expected_hours("BTC-USD", day):
                    db.execute("INSERT INTO market_bars VALUES (?,?,?,?,?,?,?,?)",
                               ("BTC-USD", utc(hour), 1., 2., 1., 1.5, 1., utc(day)))
                self.assertEqual(audit(db, "BTC-USD", day)[:3], ("OK", 24, 24))


if __name__ == "__main__":
    unittest.main()