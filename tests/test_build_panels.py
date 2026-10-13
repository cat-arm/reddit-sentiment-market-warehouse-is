import os
import sqlite3
import tempfile
import unittest

from etl import build_panels


def make_db(path):
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE merged_hourly_panel (scope TEXT, variant TEXT, ticker TEXT, hour_utc INTEGER, "
               "sentiment_mean REAL, reddit_volume_zscore_24 REAL, has_reddit_data INTEGER, future_return_1h REAL)")
    ins = "INSERT INTO merged_hourly_panel VALUES (?,?,?,?,?,?,?,?)"
    for variant in ("all", "strong", "quality"):
        for scope in ("global", "ticker"):
            db.execute(ins, (scope, variant, "AAA", 1, 0.3, 2.0, 1, 0.5))       # has sentiment, spike
            db.execute(ins, (scope, variant, "AAA", 2, 0.1, 0.2, 1, -0.5))      # has sentiment, no spike
            db.execute(ins, (scope, variant, "AAA", 3, None, None, 0, 0.1))     # no Reddit data
            db.execute(ins, (scope, variant, "BBB", 1, -0.2, None, 1, 0.2))     # sentiment but z NULL
    db.commit()
    db.close()


class PanelTests(unittest.TestCase):
    def test_nine_panels_and_filters(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "t.sqlite3")
            make_db(path)
            build_panels.build(path)
            db = sqlite3.connect(path)
            try:
                n = dict(db.execute("SELECT panel_name, COUNT(*) FROM panels GROUP BY 1").fetchall())
                self.assertEqual(len(n), 9)
                self.assertEqual(n["panel_global"], 3)                 # AAA h1, AAA h2, BBB h1 (row without sentiment dropped)
                self.assertEqual(n["panel_global_strong"], 3)
                self.assertEqual(n["panel_global_spike"], 1)           # only AAA h1 has z > 1.5 (NULL z never qualifies)
                self.assertEqual(n["panel_Ticker_spike"], 1)
                self.assertEqual(n["panel_baseline"], n["panel_global"])
                self.assertGreaterEqual(n["panel_global"], n["panel_global_spike"])
                dirs = db.execute("SELECT random_direction FROM panels WHERE panel_name='panel_baseline'").fetchall()
                self.assertTrue(all(d[0] in (-1, 1) for d in dirs))
                other = db.execute("SELECT COUNT(*) FROM panels WHERE panel_name != 'panel_baseline' "
                                   "AND random_direction IS NOT NULL").fetchone()[0]
                self.assertEqual(other, 0)
            finally:
                db.close()

    def test_baseline_is_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "t.sqlite3")
            make_db(path)
            q = "SELECT ticker, hour_utc, random_direction FROM panels WHERE panel_name='panel_baseline' ORDER BY 1, 2"
            runs = []
            for _ in range(2):
                build_panels.build(path, seed=7)
                db = sqlite3.connect(path)
                runs.append(db.execute(q).fetchall())
                db.close()
            self.assertEqual(runs[0], runs[1])


if __name__ == "__main__":
    unittest.main()
