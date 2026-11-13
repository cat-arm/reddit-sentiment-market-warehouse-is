"""The central sidebar filter must be the same on every page and must keep its value between pages (TASKS D0).

Streamlit forgets a widget that a page does not draw, so the rule is: every central widget is drawn on every page.
The test runs each page and compares the sidebar widgets (labels, order, values).  It needs the real database.
"""

import datetime as dt
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "output" / "reddit.sqlite3"
SPIKE_PAGE = "pages/4_Price_and_Reddit.py"                                     # extension: Price and Return with the Reddit volume added
SOURCE_PAGES = {"pages/1_Reddit_Volume.py", "pages/2_Ticker_Mentions.py", SPIKE_PAGE}   # system 7.1: DimSource filter
SENTIMENT_PAGE = "pages/5_Market_and_Sentiment.py"                            # 7.5-1: DimSentimentSource, DimMajoritySentiment
RANKING_PAGE = "pages/6_Statistical_Analysis.py"                              # 7.5-2: p-values, win rate, regression
DETECTION_PAGES = {"pages/8_Hot_Events.py": ["d_v", "d_mode", "d_s"], SENTIMENT_PAGE: ["d_v", "d_mode", "d_s"], RANKING_PAGE: ["d_v", "d_mode", "d_s"]}
MAJORITY_PAGES = {SENTIMENT_PAGE, *DETECTION_PAGES}
SENTIMENT_PAGES = {SENTIMENT_PAGE, RANKING_PAGE, "pages/8_Hot_Events.py"}
COUNT_PAGES = (SOURCE_PAGES - {SPIKE_PAGE}) | {"pages/3_Price_and_Return.py"}                  # first card = a count that follows the ticks
TIME_KEYS = ["f_range", "f_gran"]
COMMUNITIES = ["r/wallstreetbets", "r/stocks", "r/investing", "r/StockMarket", "r/options", "r/CryptoCurrency"]
SOURCE_KEYS = ["f_src_" + c for c in COMMUNITIES] + ["f_type_Post", "f_type_Comment"]
SENTIMENT_KEYS = ["f_ss_" + c for c in COMMUNITIES] + ["f_type_Post", "f_type_Comment", "f_ss_model"]
MAJORITY_KEYS = ["f_maj_positive", "f_maj_negative", "f_maj_neutral"]
GROUP_KEYS = ["f_group_stock_etf", "f_group_futures", "f_group_crypto"]
TICKERS = ["AAPL", "AMC", "AMD", "BITO", "BRK-B", "COIN", "GME", "HOOD", "IBIT", "IWM", "JNJ", "JPM", "KO", "MARA", "MSFT",
           "MSTR", "NVDA", "PLTR", "QQQ", "SPY", "TSLA", "XOM", "CL=F", "ES=F", "GC=F", "NG=F", "NQ=F", "RTY=F",
           "BTC-USD", "DOGE-USD", "ETH-USD", "SHIB-USD", "SOL-USD", "XRP-USD"]
PAGES = ["app.py", "pages/1_Reddit_Volume.py", "pages/2_Ticker_Mentions.py", "pages/3_Price_and_Return.py", SPIKE_PAGE,
         "pages/5_Market_and_Sentiment.py", RANKING_PAGE,
         "pages/8_Hot_Events.py"]
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
            and b.key not in ("f_tk_all", "f_tk_none", "f_reset_button")]


def sidebar_signature(at):
    """(kind, label, key) of every widget in the sidebar, in order."""
    out = []
    for kind in ("checkbox", "selectbox", "multiselect", "date_input", "radio"):
        for w in getattr(at.sidebar, kind):
            out.append((w.key, kind, w.label))
    return sorted(out)


@unittest.skipUnless(DB.exists(), "real database not available")
def live_n_global_all(common, data, tickers, info, communities, statuses):
    """Rows of the panel Global with no filter (the biggest n of its models)."""
    full = common.logistic_live("global", "all", "ALL", tickers, info["reddit_lo"], info["reddit_hi"], communities, "VADER+FinBERT", statuses, 0.0, 0.0,
                                ("Post", "Comment"), 0)
    return full[full.metric == "auc"].n.max()


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

    def test_the_reset_button_restores_every_default(self):
        """The button above the central filter sets every filter back to its default, on every page that has the filters."""
        for page in ("pages/1_Reddit_Volume.py", "pages/5_Market_and_Sentiment.py", "pages/6_Statistical_Analysis.py", "pages/8_Hot_Events.py"):
            fresh = self.run_page(page)
            default = (tuple(fresh.sidebar.date_input(key="f_range").value), fresh.sidebar.checkbox(key="f_group_crypto").value)
            at = self.run_page(page, f_group_crypto=False, f_range=(dt.date(2026, 8, 3), dt.date(2026, 8, 9)), f_gran="รายเดือน")
            if page != "pages/1_Reddit_Volume.py":
                at.sidebar.slider(key="d_v").set_value(1500).run()
            at.sidebar.button(key="f_reset_button").click().run()
            self.assertEqual(len(at.exception), 0, "%s: %s" % (page, [e.value for e in at.exception]))
            self.assertEqual((tuple(at.sidebar.date_input(key="f_range").value), at.sidebar.checkbox(key="f_group_crypto").value), default, page)
            if page != "pages/1_Reddit_Volume.py":
                self.assertEqual((at.sidebar.slider(key="d_v").value, at.sidebar.slider(key="d_s").value), (0, 0.0), page)

    def test_a_choice_survives_pages_that_do_not_have_that_filter(self):
        """Leave a page and come back: every filter is as it was, also those the pages in between do not draw (they work with
        everything ticked in the background, the saved choice returns with the page that has the filter)."""
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(ROOT / "dashboard" / "app.py"), default_timeout=180).run()
        at = at.switch_page(SENTIMENT_PAGE).run()
        at.sidebar.slider(key="d_v").set_value(1500)
        at.sidebar.checkbox(key="f_ss_r/wallstreetbets").set_value(False)
        at.sidebar.checkbox(key="f_maj_positive").set_value(False)
        at.sidebar.radio(key="f_ss_model").set_value("VADER")
        at.sidebar.checkbox(key="f_tk_SPY").set_value(False)
        at.sidebar.radio(key="f_gran").set_value("รายเดือน").run()
        for other in ("pages/3_Price_and_Return.py", RANKING_PAGE, "pages/1_Reddit_Volume.py"):
            at = at.switch_page(other).run()
            self.assertEqual(len(at.exception), 0, "%s raised %s" % (other, [e.value for e in at.exception]))
            self.assertFalse(at.sidebar.checkbox(key="f_tk_SPY").value, other)           # a filter shared by the pages stays
            self.assertEqual(at.sidebar.radio(key="f_gran").value, "รายเดือน", other)    # also a radio, also when the next page draws it too
        at = at.switch_page(SENTIMENT_PAGE).run()
        self.assertEqual(at.sidebar.slider(key="d_v").value, 1500)
        self.assertFalse(at.sidebar.checkbox(key="f_ss_r/wallstreetbets").value)
        self.assertFalse(at.sidebar.checkbox(key="f_maj_positive").value)
        self.assertEqual(at.sidebar.radio(key="f_ss_model").value, "VADER")
        self.assertFalse(at.sidebar.checkbox(key="f_tk_SPY").value)
        self.assertEqual(at.sidebar.radio(key="f_gran").value, "รายเดือน")
        at = at.switch_page(RANKING_PAGE).run()                                          # two pages that both draw the model radio
        self.assertEqual(at.sidebar.radio(key="f_ss_model").value, "VADER")

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

    def test_price_and_reddit_cards_follow_the_ticks_and_the_sources(self):
        """Price and Reddit: the Reddit cards follow the sources, the Current Return and the trading volume cards follow the ticked assets."""
        at = self.run_page(SPIKE_PAGE)
        full = [m.value for m in at.metric]
        at = tick_only(at, ["BTC-USD"])
        one = [m.value for m in at.metric]
        self.assertEqual(one[:2], full[:2], "the Reddit volume of the market does not depend on the asset")
        self.assertNotEqual(one[2:], full[2:], "the Current Return and the trading volume follow the ticked asset")
        self.assertEqual(len(at.exception), 0)

    def test_every_chart_field_is_a_column_of_its_data(self):
        """A chart whose encoded field is not a column of its data draws nothing (it happened when a Thai field name with sara am was made by a Python
        keyword argument, which normalises it to two characters): every field of every chart of these pages must exist in the data the chart carries."""
        import io
        import json
        import pyarrow as pa

        def collect(spec):
            fields, inline = set(), set()

            def walk(x):
                if isinstance(x, dict):
                    if isinstance(x.get("field"), str):
                        fields.add(x["field"])
                    if isinstance(x.get("values"), list):
                        for row in x["values"]:
                            if isinstance(row, dict):
                                inline.update(row)
                    for v in x.values():
                        walk(v)
                elif isinstance(x, list):
                    for v in x:
                        walk(v)
            walk(spec)
            return fields, inline

        for page in (SPIKE_PAGE, SENTIMENT_PAGE, "pages/3_Price_and_Return.py"):
            at = self.run_page(page)
            for i, chart in enumerate(at.get("vega_lite_chart")):
                columns = set()
                for d in chart.proto.datasets:
                    columns |= set(pa.ipc.open_stream(io.BytesIO(d.data.data)).read_all().to_pandas().columns)
                fields, inline = collect(json.loads(chart.proto.spec))
                self.assertEqual({f for f in fields - columns - inline if not f.startswith("_")}, set(), "%s chart %d" % (page, i))

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

    def test_logistic_page_follows_the_filters_and_every_panel_opens(self):
        """The Logistic Regression is a page of its own, trained live on the filters of the sidebar: every scope, panel and comparison opens, the two thresholds
        grey out on the fixed panels."""
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(ROOT / "dashboard" / "pages" / "9_Logistic_Regression.py"), default_timeout=300).run()
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        self.assertFalse(at.sidebar.slider(key="d_v").disabled)                              # the panel "all" follows the two thresholds
        for family, kinds in (("global", ("all", "strong", "quality", "spike", "baseline")), ("Ticker", ("all", "strong", "quality", "spike"))):       # the coefficients of every one of the nine panels
            at.radio(key="l9_family").set_value(family).run()
            for kind in kinds:
                at.radio(key="l9_kind").set_value(kind).run()
                self.assertEqual(len(at.exception), 0, (family, kind, [e.value for e in at.exception]))
                self.assertEqual(at.sidebar.slider(key="d_v").disabled, kind != "all", (family, kind))
        at.radio(key="l9_family").set_value("compare").run()                              # the coefficients of two panels: the difference B - A
        for left, right in (("global:all", "global:strong"), ("global:all", "Ticker:all"), ("Ticker:spike", "global:quality")):
            at.selectbox(key="l9_cmp_a").set_value(left)
            at.selectbox(key="l9_cmp_b").set_value(right).run()
            self.assertEqual(len(at.exception), 0, (left, right, [e.value for e in at.exception]))
        
    def test_live_logistic_equals_the_stored_result_when_nothing_is_filtered(self):
        """The live model is the model of `analysis.logistic` on the same rows: with every filter open its AUC is the stored one (the first and last
        hours of the range differ by a few rows, hence the tolerance), and a threshold changes it."""
        from dashboard import common, data
        info = common.q("data_range")
        src = common.q("sources")
        communities = tuple(dict.fromkeys(src.subreddit))
        tickers = tuple(common.q("tickers").ticker)
        statuses = ("positive", "negative", "neutral")
        for family, kind in (("global", "all"), ("global", "strong"), ("Ticker", "all"), ("Ticker", "quality")):
            live = common.logistic_live(family, kind, "ALL", tickers, info["reddit_lo"], info["reddit_hi"], communities, "VADER+FinBERT", statuses, 0.0, 0.0,
                                        ("Post", "Comment"), 0)
            stored = data.logistic_results(str(DB))
            stored = stored[(stored.panel == data.panel_name(kind, family)) & (stored.level == "all") & (stored.metric == "auc")].set_index("horizon").value
            auc = live[live.metric == "auc"].set_index("horizon").value
            for horizon, value in auc.items():
                self.assertAlmostEqual(value, stored[horizon], delta=0.003, msg=(family, kind, horizon))
        narrow = common.logistic_live("global", "all", "ALL", tickers, info["reddit_lo"], info["reddit_hi"], communities, "VADER+FinBERT", statuses, 0.0, 0.30,
                                      ("Post", "Comment"), 0)
        self.assertLess(narrow[narrow.metric == "auc"].n.max(), live_n_global_all(common, data, tickers, info, communities, statuses))

    def test_ranking_and_statistics_page(self):
        """Same filters as Market and Sentiment and every one changes the numbers: the time range changes the p-values, two tickers = two
        tickers, nothing ticked = cards 0; every kind of text and both families open."""
        at = self.run_page(RANKING_PAGE)
        self.assertEqual([m.label for m in at.metric], ["Historical Win Rate", "Spearman p-value", "Pearson p-value"] * 2)      # two rows: Global, Ticker
        full = [m.value for m in at.metric]
        self.assertRegex(full[0], r"^\d+\.\d%$")
        for view in at.radio(key="p5_measure_all").options:                                 # the three measures (value and p-value in one cell)
            at.radio(key="p5_measure_all").set_value(view).run()
            self.assertEqual(len(at.exception), 0, "%s: %s" % (view, [e.value for e in at.exception]))
        self.assertEqual(at.radio(key="p5_measure_all").options, ["Spearman", "Pearson", "Win Rate"])
        self.assertNotIn("ρ", "".join(at.radio(key="p5_measure_all").options))                 # the Greek rho looks like the p of p-value
        self.assertNotIn("p5_predictor", [r.key for r in at.radio])                          # the proposal measures only the mean Sentiment Score
        at.sidebar.slider(key="d_v").set_value(1500).run()                                     # the Z-score narrows every panel and says what it means in texts
        self.assertEqual(len(at.exception), 0)
        self.assertNotEqual([m.value for m in at.metric][:3], full[:3])
        self.assertFalse(any("Z-score เกิน" in c.value for c in at.sidebar.caption), "no texts-per-hour hint under the Z-score slider (it misled: the Z-score is relative to each hour)")
        at.sidebar.slider(key="d_v").set_value(0)
        self.assertEqual(at.radio(key="p5_family_all").value, "global")                    # the default: the sentiment of the whole market
        self.assertEqual(len(at.radio(key="p5_family_all").options), 3)                    # Global, Ticker, compare (the random baseline is a kind of Global)
        for family in ("Ticker", "global"):                                                  # every kind of text of both families opens; a fixed panel does not move the sidebar
            at.radio(key="p5_family_all").set_value(family).run()
            self.assertEqual(len(at.radio(key="p5_panel").options), 5 if family == "global" else 4, family)     # the random baseline is a kind of Global only
            for panel in ("all", "strong", "quality", "spike"):
                at.radio(key="p5_panel").set_value(panel).run()
                self.assertEqual(len(at.exception), 0, "%s %s: %s" % (family, panel, [e.value for e in at.exception]))
                self.assertEqual((at.sidebar.slider(key="d_v").value, at.sidebar.slider(key="d_s").value), (0, 0.0), (family, panel))
                self.assertEqual(at.sidebar.slider(key="d_v").disabled, panel != "all", "the two thresholds are greyed out on a fixed panel")
                self.assertEqual(at.sidebar.slider(key="d_s").disabled, panel != "all")
        at.radio(key="p5_family_all").set_value("global").run()
        at.radio(key="p5_panel").set_value("baseline").run()
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        self.assertTrue(at.sidebar.slider(key="d_v").disabled)
        at.radio(key="p5_family_all").set_value("Ticker").run()                              # Ticker has no baseline: back to the panel "all"
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        self.assertEqual(at.radio(key="p5_panel").value, "all")
        at.radio(key="p5_family_all").set_value("compare").run()                             # compare two panels: the difference B - A, the thresholds act on the sides "all" only
        for left, right, locked in (("global:all", "global:baseline", False), ("global:all", "Ticker:quality", False), ("global:strong", "Ticker:spike", True)):
            at.selectbox(key="p5_cmp_a").set_value(left)
            at.selectbox(key="p5_cmp_b").set_value(right).run()
            for measure in ("Spearman", "Pearson", "Win Rate"):
                at.radio(key="p5_cmp_measure").set_value(measure).run()
                self.assertEqual(len(at.exception), 0, "%s vs %s %s: %s" % (left, right, measure, [e.value for e in at.exception]))
                self.assertTrue(any(c.value.startswith("**สรุป:**") for c in at.caption), (left, right, measure))
            self.assertEqual(at.sidebar.slider(key="d_v").disabled, locked, (left, right))
        at.radio(key="p5_family_all").set_value("global").run()
        at.radio(key="p5_panel").set_value("all").run()
        # the time range is a filter of the p-values
        at.sidebar.date_input(key="f_range").set_value((dt.date(2026, 3, 1), dt.date(2026, 3, 31))).run()
        self.assertEqual(len(at.exception), 0)
        self.assertNotEqual([m.value for m in at.metric][:3], full[:3], "a shorter time range changes the win rate and the p-values")
        at.sidebar.date_input(key="f_range").set_value(at.sidebar.date_input(key="f_range").value)
        # the other filters of the page
        at.sidebar.checkbox(key="f_ss_r/wallstreetbets").set_value(False).run()
        self.assertEqual(len(at.exception), 0)
        at.sidebar.checkbox(key="f_ss_r/wallstreetbets").set_value(True)
        at.sidebar.slider(key="d_s").set_value(0.5).run()
        self.assertEqual(len(at.exception), 0)
        at.sidebar.slider(key="d_s").set_value(0.0)
        at = tick_only(at, ["SPY", "QQQ"])
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(len([d for d in at.dataframe if "p ต่ำสุด" in list(d.value.columns)]), 0)       # no separate table of p-values any more
        for key in TICKERS:
            at.sidebar.checkbox(key="f_tk_" + key).set_value(False)
        at = at.run()
        self.assertEqual([m.value for m in at.metric], ["0"] * 3)

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
        # DimDetectionConfig is a FILTER on this page: 0 / 0 removes nothing, a threshold removes hours
        self.assertEqual((at.sidebar.slider(key="d_v").value, at.sidebar.slider(key="d_s").value), (0, 0.0))
        for z in (3000, 1500):
            at.sidebar.slider(key="d_v").set_value(z).run()
            self.assertEqual(len(at.exception), 0, z)
            self.assertNotEqual(at.metric[0].value, full[0], "Z-score Threshold %s removes hours, so the Sentiment Score changes" % z)
        at.sidebar.slider(key="d_v").set_value(0)
        at.run()
        at.sidebar.slider(key="d_v").set_value(1500).run()
        self.assertFalse(any("Z-score เกิน" in c.value for c in at.sidebar.caption), "no hint under the Z-score slider")
        at.sidebar.slider(key="d_v").set_value(4000).run()
        self.assertEqual(len(at.exception), 0)
        at.sidebar.slider(key="d_v").set_value(0)
        at.sidebar.checkbox(key="f_type_Comment").set_value(False).run()           # only the posts of the community are counted
        self.assertEqual(len(at.exception), 0)
        self.assertNotEqual([m.value for m in at.metric], full, "the content type is a filter")
        at.sidebar.checkbox(key="f_type_Post").set_value(False).run()               # no content type ticked = nothing
        self.assertEqual([m.value for m in at.metric], ["0"] * 3)
        at.sidebar.checkbox(key="f_type_Comment").set_value(True)
        at.sidebar.checkbox(key="f_type_Post").set_value(True)
        at.sidebar.slider(key="d_s").set_value(0.5).run()
        self.assertNotEqual(at.metric[0].value, full[0], "Sentiment Threshold changes the Sentiment Score")
        at.sidebar.slider(key="d_s").set_value(0.0)
        # the normal (signed) mode: a negative cut keeps only the negative texts, a positive one only the positive texts
        at.sidebar.radio(key="d_mode").set_value("normal").run()
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        self.assertEqual(at.sidebar.slider(key="d_ss").value, 0.0)
        at.sidebar.slider(key="d_ss").set_value(-0.30).run()
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        negative = at.metric[0].value
        self.assertTrue(negative.startswith("-") or negative.startswith("−"), "only the texts with score <= -0.30: the mean is negative, got %s" % negative)
        at.sidebar.slider(key="d_ss").set_value(0.30).run()
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        self.assertTrue(at.metric[0].value.startswith("+"), "only the texts with score >= +0.30: the mean is positive, got %s" % at.metric[0].value)
        at.sidebar.slider(key="d_ss").set_value(0.0)
        at.sidebar.radio(key="d_mode").set_value("absolute")
        at.run()
        at.run()
        self.assertEqual([m.value for m in at.metric], full, "back to 0 / 0: nothing is filtered, the numbers are the default ones")
        for key in ("s_price_sent", "s_z_sent"):                      # the dual charts: hide one line, then both
            at.checkbox(key="dl_" + key).set_value(False).run()
            self.assertEqual(len(at.exception), 0, key)
            at.checkbox(key="dr_" + key).set_value(False).run()                    # both hidden: a note instead of a chart
            self.assertEqual(len(at.exception), 0, key)
            at.checkbox(key="dl_" + key).set_value(True)
            at.checkbox(key="dr_" + key).set_value(True).run()
        for measure in ("Current Return (ชั่วโมงเดียวกัน ส่วนขยาย)", "ผลตอบแทนล่วงหน้า 2h", "ผลตอบแทนล่วงหน้า 12h"):      # sentiment vs return bars
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
        page = "pages/8_Hot_Events.py"
        at = self.run_page(page)
        base = at.metric[0].value
        at.sidebar.slider(key="d_v").set_value(4000).run()                          # both thresholds start at 0: every hour with texts is a signal
        at.sidebar.slider(key="d_s").set_value(0.5).run()
        self.assertNotEqual(at.metric[0].value, base, "the thresholds change the signals")
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
        self.assertEqual(at.metric[0].label, "Reddit Volume ของสินทรัพย์ที่เลือก รวม")
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


@unittest.skipUnless(DB.exists(), "needs output/reddit.sqlite3")
class StoredStatTests(unittest.TestCase):
    def test_every_panel_has_the_shape_of_the_live_table(self):
        from dashboard import data
        for panel in data.STORED_PANELS:
            out = data.stored_stat_table(str(DB), panel)
            self.assertEqual(list(out.columns), data.STAT_COLUMNS, panel)
            if panel == "panel_global_quality":                                   # the rows with |hourly mean| >= 0.30 of the whole market: 215 rows, a few assets only
                self.assertTrue(0 < out.ticker.nunique() <= 34, panel)
            else:
                self.assertEqual(out.ticker.nunique(), 34, panel)
            self.assertEqual(set(out.target), set(data.STAT_TARGETS), panel)

    def test_the_stored_numbers_match_the_stored_figures(self):
        from dashboard import data
        row = data.stored_stat_table(str(DB), "panel_Ticker").set_index(["ticker", "target"])
        self.assertAlmostEqual(row.loc[("SPY", "log_return"), "spearman_rho"], 0.064, places=3)     # the heat map of A1: SPY, Current Return
        self.assertAlmostEqual(row.loc[("BITO", "3h"), "winrate"], 54.8, places=1)                    # the heat map of A2: BITO, 3h


if __name__ == "__main__":
    unittest.main()
