"""The central sidebar filter must be the same on every page and must keep its value between pages (TASKS D0).

Streamlit forgets a widget that a page does not draw, so the rule is: every central widget is drawn on every page.
The test runs each page and compares the sidebar widgets (labels, order, values).  It needs the real database.
"""

import datetime as dt
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "output" / "reddit.sqlite3"
SOURCE_PAGES = {"pages/1_Reddit_Volume.py", "pages/2_Ticker_Mentions.py"}   # system 7.1: DimSource filter
SENTIMENT_PAGE = "pages/4_Market_and_Sentiment.py"                            # 7.5-1: DimSentimentSource, DimMajoritySentiment
ANALYSIS_PAGE = "pages/7_Statistical_Analysis.py"                              # 7.5-3: deeper analysis (extension)
DETECTION_PAGES = {"pages/5_Ranking_and_Signals.py": ["s_z", "s_s", "s_h"], "pages/6_Hot_Events.py": ["h_z", "h_s", "h_n"],
                   SENTIMENT_PAGE: ["s_z", "s_s", "s_h"]}
MAJORITY_PAGES = {SENTIMENT_PAGE, ANALYSIS_PAGE, *DETECTION_PAGES}
SENTIMENT_PAGES = {SENTIMENT_PAGE, ANALYSIS_PAGE}
COUNT_PAGES = SOURCE_PAGES | {"pages/3_Price_and_Return.py"}                  # first card = a count that follows the ticks
TIME_KEYS = ["f_range", "f_gran"]
COMMUNITIES = ["r/wallstreetbets", "r/stocks", "r/investing", "r/StockMarket", "r/options", "r/CryptoCurrency"]
SOURCE_KEYS = ["f_src_" + c for c in COMMUNITIES] + ["f_type_Post", "f_type_Comment"]
SENTIMENT_KEYS = ["f_ss_" + c for c in COMMUNITIES] + ["f_ss_model"]
MAJORITY_KEYS = ["f_maj_positive", "f_maj_negative", "f_maj_neutral"]
GROUP_KEYS = ["f_group_stock_etf", "f_group_futures", "f_group_crypto"]
TICKERS = ["AAPL", "AMC", "AMD", "BITO", "BRK-B", "COIN", "GME", "HOOD", "IBIT", "IWM", "JNJ", "JPM", "KO", "MARA", "MSFT",
           "MSTR", "NVDA", "PLTR", "QQQ", "SPY", "TSLA", "XOM", "CL=F", "ES=F", "GC=F", "NG=F", "NQ=F", "RTY=F",
           "BTC-USD", "DOGE-USD", "ETH-USD", "SHIB-USD", "SOL-USD", "XRP-USD"]
PAGES = ["app.py", "pages/1_Reddit_Volume.py", "pages/2_Ticker_Mentions.py", "pages/3_Price_and_Return.py",
         "pages/4_Market_and_Sentiment.py", "pages/5_Ranking_and_Signals.py", "pages/6_Hot_Events.py",
         ANALYSIS_PAGE]
MULTI_PAGES = set(PAGES[1:])                                                  # every dashboard takes several tickers


def tick_only(at, keep):
    """Tick exactly the tickers in `keep` (every other box is unticked), then rerun."""
    for symbol in TICKERS:
        try:
            at.sidebar.checkbox(key="f_tk_" + symbol).set_value(symbol in keep)
        except KeyError:
            pass                                                     # its class is unticked: the box is not drawn
    return at.run()


def expected_keys(page):
    """Sidebar order: time, [source 7.1], asset, [sentiment source], [detection config], [majority status]."""
    keys = list(TIME_KEYS)
    if page in SOURCE_PAGES:
        keys += SOURCE_KEYS
    keys += GROUP_KEYS + (["f_tk_" + s for s in TICKERS] if page in MULTI_PAGES else [])
    if page in SENTIMENT_PAGES:
        keys += SENTIMENT_KEYS
    keys += DETECTION_PAGES.get(page, [])
    if page in MAJORITY_PAGES:
        keys += MAJORITY_KEYS
    return keys


def sidebar_order(at):
    """Keys of the sidebar widgets in the order they are drawn."""
    return [b.key for b in at.sidebar.children.values() if getattr(b, "key", None)
            and b.key not in ("f_tk_all", "f_tk_none")]


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
        chosen = dict(f_group_crypto=False, f_range=(dt.date(2026, 8, 3), dt.date(2026, 8, 9)), f_gran="รายเดือน")
        for page in PAGES:
            at = self.run_page(page, **chosen)
            self.assertEqual(len(at.exception), 0, "%s raised %s" % (page, [e.value for e in at.exception]))
            self.assertFalse(at.sidebar.checkbox(key="f_group_crypto").value, page)
            self.assertTrue(at.sidebar.checkbox(key="f_group_stock_etf").value, page)
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
        for page in COUNT_PAGES:
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

    def test_select_all_and_clear_also_set_the_asset_classes(self):
        """The two buttons tick / untick every ticker and every asset class together."""
        for page in MULTI_PAGES:
            at = self.run_page(page)
            at.button(key="f_tk_none").click().run()
            self.assertFalse(any(at.sidebar.checkbox(key=k).value for k in GROUP_KEYS), page)
            self.assertFalse(any(at.sidebar.checkbox(key="f_tk_" + s).value for s in TICKERS), page)
            self.assertEqual(len(at.exception), 0, page)
            self.assertTrue(at.metric and all(m.value == "0" for m in at.metric), "%s shows 0 when nothing is ticked" % page)
            at.button(key="f_tk_all").click().run()
            self.assertTrue(all(at.sidebar.checkbox(key=k).value for k in GROUP_KEYS), page)
            self.assertTrue(all(at.sidebar.checkbox(key="f_tk_" + s).value for s in TICKERS), page)
            self.assertEqual(len(at.exception), 0, page)

    def test_source_filter_cleared_shows_nothing(self):
        for page in SOURCE_PAGES:
            at = self.run_page(page)
            for key in SOURCE_KEYS:
                at.sidebar.checkbox(key=key).set_value(False)
            at = at.run()
            self.assertEqual(len(at.exception), 0, page)
            self.assertTrue(at.metric and all(m.value == "0" for m in at.metric), page)

    def test_no_asset_class_ticked_never_breaks_a_page(self):
        """Clearing the classes on every page: pages with a ticker list show 0, the others an empty result, none fails."""
        for page in PAGES:
            at = self.run_page(page)
            for key in GROUP_KEYS:
                at.sidebar.checkbox(key=key).set_value(False)
            at = at.run()
            self.assertEqual(len(at.exception), 0, "%s: %s" % (page, [e.value for e in at.exception]))

    def test_statistical_analysis_page(self):
        """Stored analyses (A1-A3) follow the ticker filter; the live part follows every filter; nothing ticked = cards 0."""
        at = self.run_page(ANALYSIS_PAGE)
        self.assertEqual([m.label for m in at.metric], ["Spearman ที่ p < 0.05", "ผ่านการปรับ Benjamini-Hochberg", "Win Rate ที่ p < 0.05",
                                                         "Logistic AUC เฉลี่ย"])
        full = [m.value for m in at.metric]
        self.assertRegex(full[0], r"^\d+ / \d+$")
        for key, values in (("a_method", ["Pearson (เชิงเส้น)"]), ("a_horizon", ["Current Return", "12h"]), ("a_win_horizon", ["1h", "12h"]),
                            ("a_log_horizon", ["1h", "12h"]), ("s_past_hours", ["2 ชั่วโมงก่อนหน้า", "12 ชั่วโมงก่อนหน้า"])):
            for value in values:
                at.radio(key=key).set_value(value).run()
                self.assertEqual(len(at.exception), 0, "%s=%s: %s" % (key, value, [e.value for e in at.exception]))
        at = tick_only(at, ["SPY"])
        self.assertEqual(len(at.exception), 0)
        self.assertNotEqual([m.value for m in at.metric], full)                 # the cards follow the tickers
        for key in TICKERS:
            at.sidebar.checkbox(key="f_tk_" + key).set_value(False)
        at = at.run()
        self.assertEqual([m.value for m in at.metric], ["0"] * 4)

    def test_system_75_dimension_filters_change_the_numbers(self):
        """DimSentimentSource, DimMajoritySentiment and DimDetectionConfig are real filters, not decoration."""
        at = self.run_page(SENTIMENT_PAGE)
        full = [m.value for m in at.metric]
        at.sidebar.checkbox(key="f_ss_r/wallstreetbets").set_value(False).run()
        no_wsb = [m.value for m in at.metric]
        self.assertNotEqual(no_wsb[0], full[0], "Sentiment Score follows the communities")
        at.sidebar.checkbox(key="f_ss_r/wallstreetbets").set_value(True)
        for model in ("VADER", "FinBERT"):                                  # the model is a choice of ONE: each gives its own numbers
            at.sidebar.radio(key="f_ss_model").set_value(model).run()
            self.assertEqual(len(at.exception), 0, model)
            self.assertNotEqual(at.metric[0].value, full[0], "Sentiment Score of %s differs from VADER+FinBERT" % model)
        at.sidebar.radio(key="f_ss_model").set_value("VADER+FinBERT")
        at.sidebar.checkbox(key="f_maj_neutral").set_value(False).run()
        self.assertNotEqual(at.metric[0].value, full[0], "hours with a neutral majority lose their sentiment")
        self.assertEqual([m.label for m in at.metric], ["Sentiment Score", "Sentiment Momentum", "Reddit Volume Z-score สูงสุด"])
        at.sidebar.checkbox(key="f_maj_neutral").set_value(True)
        for z in (3.0, 0.5):                                                        # DimDetectionConfig: the signal hours follow the thresholds
            at.sidebar.slider(key="s_z").set_value(z).run()
            self.assertEqual(len(at.exception), 0, z)
        at.sidebar.radio(key="s_h").set_value("12h").run()
        self.assertEqual(len(at.exception), 0)
        at.sidebar.slider(key="s_z").set_value(1.5)
        at.sidebar.radio(key="s_h").set_value("1h")
        for key in ("s_price_sent", "s_z_sent", "s_price_z"):                      # the dual charts: hide one line, then both
            at.checkbox(key="dl_" + key).set_value(False).run()
            self.assertEqual(len(at.exception), 0, key)
            at.checkbox(key="dr_" + key).set_value(False).run()                    # both hidden: a note instead of a chart
            self.assertEqual(len(at.exception), 0, key)
            at.checkbox(key="dl_" + key).set_value(True)
            at.checkbox(key="dr_" + key).set_value(True).run()
        for measure in ("Current Return (ชั่วโมงเดียวกัน)", "ผลตอบแทนล่วงหน้า 12h"):                       # sentiment vs return bars
            at.radio(key="s_bar_measure").set_value(measure).run()
            self.assertEqual(len(at.exception), 0, measure)
        at.radio(key="s_ratio_mode").set_value("ผลโหวตส่วนใหญ่ (สัดส่วนชั่วโมง)")      # the ratio chart can count the majority votes
        at.sidebar.checkbox(key="f_maj_positive").set_value(False).run()
        self.assertEqual(len(at.exception), 0)
        at.sidebar.checkbox(key="f_maj_positive").set_value(True)
        for key in ("f_ss_" + c for c in COMMUNITIES):
            at.sidebar.checkbox(key=key).set_value(False)
        at = at.run()
        self.assertTrue(all(m.value == "0" for m in at.metric), "no community ticked = nothing")
        # ranking and signals: thresholds and majority statuses change the detected signals
        page = "pages/5_Ranking_and_Signals.py"
        at = self.run_page(page)
        base = at.metric[0].value
        at.sidebar.slider(key="s_z").set_value(3.0).run()
        self.assertNotEqual(at.metric[0].value, base, "Z-score Threshold changes the signals")
        at.sidebar.slider(key="s_z").set_value(1.5)
        at.sidebar.checkbox(key="f_maj_positive").set_value(False).run()
        self.assertNotEqual(at.metric[0].value, base, "majority status changes the signals")
        for key in MAJORITY_KEYS:
            at.sidebar.checkbox(key=key).set_value(False)
        self.assertTrue(all(m.value == "0" for m in at.run().metric))
        page = "pages/6_Hot_Events.py"
        at = self.run_page(page)
        base = at.metric[0].value
        at.sidebar.slider(key="h_z").set_value(3.5).run()
        self.assertNotEqual(at.metric[0].value, base, "Z-score Threshold changes the events")
        self.assertEqual(len(at.exception), 0)

    def test_majority_vote_chart_follows_every_filter(self):
        """The vote mode of the ratio chart changes with the majority status, the community, the time range and the tickers."""
        import pyarrow as pa
        from streamlit.testing.v1 import AppTest

        def shares(at):
            for el in at.main:
                if type(el).__name__ == "UnknownElement":
                    for d in el.proto.datasets:
                        tbl = pa.ipc.open_stream(d.data.data).read_all().to_pandas()
                        if "ประเภท" in tbl.columns and "hours" in tbl.columns:
                            hours = tbl.groupby("ประเภท").hours.sum()
                            return {k: round(float(v) / float(hours.sum()), 3) for k, v in hours.items()}
            return None

        at = AppTest.from_file(str(ROOT / "dashboard" / SENTIMENT_PAGE), default_timeout=180).run()
        at.radio(key="s_ratio_mode").set_value("ผลโหวตส่วนใหญ่ (สัดส่วนชั่วโมง)").run()
        base = shares(at)
        self.assertEqual(set(base), {"บวก", "ลบ", "เป็นกลาง"})
        at.sidebar.checkbox(key="f_maj_positive").set_value(False).run()
        self.assertNotIn("บวก", shares(at))                                              # an unticked status has no votes
        at.sidebar.checkbox(key="f_maj_positive").set_value(True)
        at.sidebar.checkbox(key="f_ss_r/wallstreetbets").set_value(False).run()
        self.assertNotEqual(shares(at), base)                                            # community
        at.sidebar.checkbox(key="f_ss_r/wallstreetbets").set_value(True)
        at.sidebar.date_input(key="f_range").set_value((dt.date(2026, 3, 1), dt.date(2026, 3, 31))).run()
        march = shares(at)
        self.assertNotEqual(march, base)                                                 # time range
        at = tick_only(at, ["SPY"])
        self.assertNotEqual(shares(at), march)                                           # tickers
        self.assertEqual(len(at.exception), 0)

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
        for page in PAGES[1:4]:
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
        other = AppTest.from_file(str(ROOT / "dashboard" / "app.py"), default_timeout=90)
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
