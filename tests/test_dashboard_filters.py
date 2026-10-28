"""The central sidebar filter must be the same on every page and must keep its value between pages (TASKS D0).

Streamlit forgets a widget that a page does not draw, so the rule is: every central widget is drawn on every page.
The test runs each page and compares the sidebar widgets (labels, order, values).  It needs the real database.
"""

import datetime as dt
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "output" / "reddit.sqlite3"
SOURCE_PAGES = {"pages/1_Reddit_Volume.py", "pages/2_Ticker_Mentions.py"}   # only these tables are split by source
MULTI_PAGES = SOURCE_PAGES | {"pages/3_Price_and_Return.py"}                   # these take several tickers
SINGLE_PAGES = {"pages/4_Market_and_Sentiment.py"}                            # one ticker; the others draw no ticker list
TIME_KEYS = ["f_range", "f_gran"]
COMMUNITIES = ["r/wallstreetbets", "r/stocks", "r/investing", "r/StockMarket", "r/options", "r/CryptoCurrency"]
SOURCE_KEYS = ["f_src_" + c for c in COMMUNITIES] + ["f_type_Post", "f_type_Comment"]
GROUP_KEYS = ["f_group_stock_etf", "f_group_futures", "f_group_crypto"]
TICKERS = ["AAPL", "AMC", "AMD", "BITO", "BRK-B", "COIN", "GME", "HOOD", "IBIT", "IWM", "JNJ", "JPM", "KO", "MARA", "MSFT",
           "MSTR", "NVDA", "PLTR", "QQQ", "SPY", "TSLA", "XOM", "CL=F", "ES=F", "GC=F", "NG=F", "NQ=F", "RTY=F",
           "BTC-USD", "DOGE-USD", "ETH-USD", "SHIB-USD", "SOL-USD", "XRP-USD"]


def tick_only(at, keep):
    """Tick exactly the tickers in `keep` on pages 1-2 (every other box is unticked), then rerun."""
    for symbol in TICKERS:
        try:
            at.sidebar.checkbox(key="f_tk_" + symbol).set_value(symbol in keep)
        except KeyError:
            pass                                                     # its class is unticked: the box is not drawn
    return at.run()
PAGES = ["app.py", "pages/1_Reddit_Volume.py", "pages/2_Ticker_Mentions.py", "pages/3_Price_and_Return.py",
         "pages/4_Market_and_Sentiment.py", "pages/5_Ranking_and_Signals.py", "pages/6_Hot_Events.py"]


def expected_keys(page):
    """Sidebar order: time (DimTime) first, then source (DimSource), then asset (DimTicker)."""
    asset = GROUP_KEYS + (["f_tk_" + s for s in TICKERS] if page in MULTI_PAGES else ["f_ticker"] if page in SINGLE_PAGES else [])
    return TIME_KEYS + (SOURCE_KEYS if page in SOURCE_PAGES else []) + asset


def sidebar_order(at):
    """Keys of the sidebar widgets in the order they are drawn."""
    return [b.key for b in at.sidebar.children.values() if getattr(b, "key", None)]


def sidebar_signature(at):
    """(kind, label, key) of every widget in the sidebar, in order."""
    out = []
    for kind in ("checkbox", "selectbox", "multiselect", "date_input", "radio"):
        for w in getattr(at.sidebar, kind):
            out.append((w.key, kind, w.label))
    return sorted(out)


@unittest.skipUnless(DB.exists(), "real database not available")
class FilterTests(unittest.TestCase):
    def run_page(self, page, **state):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(ROOT / "dashboard" / page), default_timeout=90)
        for key, value in state.items():
            at.session_state[key] = value
        return at.run()

    def test_sidebar_has_the_dimensions_in_order_on_every_page(self):
        for page in PAGES:
            order = sidebar_order(self.run_page(page))
            self.assertEqual(order, expected_keys(page), "%s sidebar order" % page)

    def test_a_choice_holds_on_every_page(self):
        chosen = dict(f_group_crypto=False, f_ticker="QQQ", f_range=(dt.date(2026, 8, 3), dt.date(2026, 8, 9)),
                      f_gran="รายเดือน")
        for page in PAGES:
            at = self.run_page(page, **chosen)
            self.assertEqual(len(at.exception), 0, "%s raised %s" % (page, [e.value for e in at.exception]))
            self.assertFalse(at.sidebar.checkbox(key="f_group_crypto").value, page)
            self.assertTrue(at.sidebar.checkbox(key="f_group_stock_etf").value, page)
            if page in SINGLE_PAGES:
                self.assertEqual(at.sidebar.radio(key="f_ticker").value, "QQQ", page)
            self.assertEqual(at.sidebar.radio(key="f_gran").value, "รายเดือน", page)
            self.assertEqual(tuple(at.sidebar.date_input(key="f_range").value),
                             (dt.date(2026, 8, 3), dt.date(2026, 8, 9)), page)

    def test_every_source_box_starts_ticked_and_changes_the_numbers(self):
        for page in SOURCE_PAGES:
            at = self.run_page(page)
            for key in SOURCE_KEYS:
                self.assertTrue(at.sidebar.checkbox(key=key).value, "%s %s" % (page, key))
            full = at.metric[0].value
            at.sidebar.checkbox(key="f_src_r/wallstreetbets").set_value(False).run()
            self.assertNotEqual(at.metric[0].value, full, page + " (community off)")
            smaller = at.metric[0].value
            at.sidebar.checkbox(key="f_type_Post").set_value(False).run()
            self.assertNotEqual(at.metric[0].value, smaller, page + " (posts off)")
            self.assertEqual(len(at.exception), 0, page)

    def test_every_ticker_box_starts_ticked(self):
        for page in MULTI_PAGES:
            at = self.run_page(page)
            for symbol in TICKERS:
                self.assertTrue(at.sidebar.checkbox(key="f_tk_" + symbol).value, "%s %s" % (page, symbol))

    def test_several_tickers_and_classes_change_the_numbers(self):
        """Pages 1-2: everything ticked = every ticker; ticking fewer narrows the numbers; unticking a class drops its tickers."""
        for page in MULTI_PAGES:
            at = self.run_page(page)
            full = at.metric[0].value
            at = tick_only(at, ["TSLA", "NVDA"])
            two = at.metric[0].value
            self.assertNotEqual(two, full, page)
            at = tick_only(at, ["TSLA", "NVDA", "BTC-USD"])
            self.assertNotEqual(at.metric[0].value, two, page)
            at.sidebar.checkbox(key="f_group_crypto").set_value(False).run()          # BTC-USD leaves with its class
            self.assertEqual(at.metric[0].value, two, page)
            self.assertEqual(len(at.exception), 0, page)

    def test_ticking_a_class_ticks_all_its_tickers(self):
        """Pages 1-3: unticking a class clears its tickers, ticking it again ticks the whole class (even a ticker unticked before)."""
        crypto = ["BTC-USD", "DOGE-USD", "ETH-USD", "SHIB-USD", "SOL-USD", "XRP-USD"]
        for page in MULTI_PAGES:
            at = self.run_page(page)
            at.sidebar.checkbox(key="f_tk_BTC-USD").set_value(False).run()           # one crypto ticker out
            at.sidebar.checkbox(key="f_group_crypto").set_value(False).run()
            for symbol in crypto:
                self.assertNotIn("f_tk_" + symbol, [c.key for c in at.sidebar.checkbox], "%s %s" % (page, symbol))
            at.sidebar.checkbox(key="f_group_crypto").set_value(True).run()
            for symbol in crypto:
                self.assertTrue(at.sidebar.checkbox(key="f_tk_" + symbol).value, "%s %s" % (page, symbol))
            self.assertEqual(len(at.exception), 0, page)

    def test_price_page_follows_the_ticked_tickers(self):
        """One ticker, a few (one line each) and many (their average) all render, and the numbers follow the ticks."""
        page = "pages/3_Price_and_Return.py"
        at = self.run_page(page)
        many = at.metric[0].value
        at = tick_only(at, ["SPY"])
        self.assertEqual(len(at.exception), 0)
        one = at.metric[0].value
        at = tick_only(at, ["SPY", "TSLA", "BTC-USD"])
        self.assertEqual(len(at.exception), 0)
        self.assertNotEqual(at.metric[0].value, one)
        self.assertNotEqual(one, many)
        for key in ("ck_p_close",):
            self.assertNotIn(key, [r.key for r in at.radio])                          # a few tickers: lines only, no bar switch

    def test_total_volume_page_shows_all_texts_unless_tickers_are_unticked(self):
        at = self.run_page("pages/1_Reddit_Volume.py")
        self.assertEqual(at.metric[0].label, "Reddit Volume รวม")
        self.assertEqual(len(at.info), 0)
        at = tick_only(at, ["SPY"])
        self.assertEqual(at.metric[0].label, "Ticker Mention Count รวม")
        self.assertEqual(len(at.info), 1)                            # the page says what it now counts

    def test_every_chart_can_switch_to_bars(self):
        """The line / bar switch sits on each chart (not in the sidebar) and every chart survives being a bar chart."""
        for page in PAGES[1:5]:
            at = self.run_page(page)
            switches = [r for r in at.radio if r.key and r.key.startswith("ck_")]
            self.assertGreaterEqual(len(switches), 1, page)
            for switch in switches:
                at.radio(key=switch.key).set_value("แท่ง")
            at = at.run()
            self.assertEqual(len(at.exception), 0, "%s raised %s" % (page, [e.value for e in at.exception]))
        sidebar_radios = [r.key for r in self.run_page("pages/1_Reddit_Volume.py").sidebar.radio]
        self.assertEqual(sidebar_radios, ["f_gran"])                    # the chart level only: no line / bar switch there

    def test_several_tickers_chart_survives_lines_and_bars(self):
        at = self.run_page("pages/2_Ticker_Mentions.py")
        at = tick_only(at, ["TSLA", "NVDA", "SPY"])
        self.assertEqual(len(at.exception), 0)
        at.radio(key="ck_m_count").set_value("แท่ง").run()             # stacked bars, one colour per ticker
        self.assertEqual(len(at.exception), 0)
        at = tick_only(at, ["TSLA", "NVDA", "SPY", "QQQ", "AAPL", "AMD", "AMC", "GME", "MSFT"])
        self.assertEqual(len(at.exception), 0)                       # more than 8 tickers: one summed line

    def test_default_range_is_the_last_year_of_the_data(self):
        at = self.run_page("app.py")
        lo, hi = at.sidebar.date_input(key="f_range").value
        self.assertEqual(hi, dt.date(2026, 8, 31))                 # last day of Reddit data
        self.assertEqual((hi - lo).days, 365)

    def test_source_and_ticker_choices_hold_across_pages_that_do_not_draw_them(self):
        """The source filter and the ticker tick boxes are drawn on pages 1-2 only; a choice made there must come back."""
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(ROOT / "dashboard" / "pages/1_Reddit_Volume.py"), default_timeout=90).run()
        at.sidebar.checkbox(key="f_src_r/options").set_value(False)
        at.sidebar.checkbox(key="f_type_Post").set_value(False)
        at = tick_only(at, ["TSLA"])
        self.assertEqual(len(at.exception), 0)
        state = {"f_src_r/options": False, "f_type_Post": False, "f_tk_TSLA": True, "f_tk_SPY": False}
        other = AppTest.from_file(str(ROOT / "dashboard" / "pages/4_Market_and_Sentiment.py"), default_timeout=90)
        for key, value in state.items():
            other.session_state[key] = value
        other = other.run()                                         # page without the widgets: the values go to shadow keys
        self.assertFalse(other.session_state["_keep_f_src_r/options"])
        self.assertFalse(other.session_state["_keep_f_type_Post"])
        self.assertTrue(other.session_state["_keep_f_tk_TSLA"])
        self.assertFalse(other.session_state["_keep_f_tk_SPY"])

    def test_every_time_level_works_on_every_page(self):
        """Hour / day / week / month / year (DimTime levels) on a short, a medium and the full range."""
        from dashboard import common
        for level in common.GRANULARITY:
            for page in PAGES[1:]:
                for rng in [(dt.date(2026, 9, 20), dt.date(2026, 9, 25)), (dt.date(2024, 10, 1), dt.date(2026, 10, 1))]:
                    if level == "รายชั่วโมง" and rng[0].year == 2024:
                        continue                          # 2 years of hourly points: slow, and the user can still ask
                    at = self.run_page(page, f_gran=level, f_range=rng)
                    self.assertEqual(len(at.exception), 0, "%s / %s / %s raised %s" % (
                        page, level, rng, [e.value for e in at.exception]))

    def test_ticker_outside_chosen_groups_falls_back_to_a_valid_one(self):
        at = self.run_page("pages/4_Market_and_Sentiment.py", f_group_stock_etf=False, f_group_futures=False, f_ticker="SPY")
        self.assertEqual(len(at.exception), 0)
        self.assertIn(at.sidebar.radio(key="f_ticker").value, ["BTC-USD", "DOGE-USD", "ETH-USD", "SHIB-USD",
                                                                    "SOL-USD", "XRP-USD"])


class DesignTests(unittest.TestCase):
    """Every page opens the same way: title, KPI cards, then the rest; charts one under the other."""

    def test_every_page_opens_with_kpi_cards_and_has_no_split_charts(self):
        from streamlit.testing.v1 import AppTest
        for page in PAGES:
            at = AppTest.from_file(str(ROOT / "dashboard" / page), default_timeout=120).run()
            self.assertEqual(len(at.exception), 0, page)
            kinds = [type(e).__name__ for e in at.main]
            first_metric = kinds.index("Metric")
            before = [k for k in kinds[:first_metric] if k in ("Subheader", "Header", "Dataframe", "UnknownElement", "Radio")]
            self.assertEqual(before, [], "%s has content before the KPI cards" % page)
            for column in at.columns:                                # no chart or table inside a column
                inner = [type(c).__name__ for c in column.children.values()]
                self.assertNotIn("UnknownElement", inner, "%s has a chart inside a column" % page)
                self.assertNotIn("Dataframe", inner, "%s has a table inside a column" % page)


if __name__ == "__main__":
    unittest.main()
