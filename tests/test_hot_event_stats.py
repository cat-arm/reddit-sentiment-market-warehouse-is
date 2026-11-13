"""System 7.6 (Hot Events) looks its Win Rate up from system 7.4 (Statistical Analysis), proposal 7.6 step 3: with the same filters the two pages
show the same numbers.  Needs the real database output/reddit.sqlite3 (read-only); skipped when it is absent."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pyarrow as pa                                   # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "output" / "reddit.sqlite3"


def heat_values(at):
    """{(ticker, horizon label): Win Rate} read from the data behind the heat map of the Statistical Analysis page."""
    chart = at.get("vega_lite_chart")[0]
    for dataset in chart.proto.datasets:
        frame = pa.ipc.open_stream(dataset.data.data).read_all().to_pandas()
        if {"asset", "value", "bh"} <= set(frame.columns):
            return {(r.asset.split(" ")[0], r.ช่วง): (r.value, r.n_used) for r in frame.itertuples() if r.value == r.value}
    raise AssertionError("heat map data not found")


@unittest.skipUnless(DB.exists(), "real database not available")
class HotEventsLookupTests(unittest.TestCase):
    def test_hot_events_win_rate_is_the_number_of_the_statistical_analysis_page(self):
        from streamlit.testing.v1 import AppTest
        five = AppTest.from_file(str(ROOT / "dashboard" / "pages" / "6_Statistical_Analysis.py"), default_timeout=180).run()
        five.sidebar.slider(key="d_z").set_value(1.5)
        five.sidebar.slider(key="d_s").set_value(0.05)
        five.radio(key="p5_measure_all").set_value("Win Rate").run()
        win = heat_values(five)
        seven = AppTest.from_file(str(ROOT / "dashboard" / "pages" / "8_Hot_Events.py"), default_timeout=180)
        seven.session_state["d_z"], seven.session_state["d_s"] = 1.5, 0.05
        seven.session_state["f_range"] = five.session_state["f_range"]
        seven.run()
        self.assertEqual(len(seven.exception), 0)
        table = [t.value for t in seven.dataframe if "ความรู้สึก (ทั้งตลาด)" in t.value.columns][0]      # the tab of the score
        self.assertIn("Win Rate ของสินทรัพย์ (%)", table.columns)
        checked = 0
        for row in table.itertuples(index=False):
            ticker, rate = row[1], row[table.columns.get_loc("Win Rate ของสินทรัพย์ (%)")]
            key = (ticker, "Current Return")
            if key in win and rate == rate:
                self.assertAlmostEqual(float(rate), win[key][0], places=0, msg=ticker)
                checked += 1
        self.assertGreater(checked, 0)


if __name__ == "__main__":
    unittest.main()
