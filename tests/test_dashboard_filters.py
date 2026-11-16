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
SPIKE_PAGE = "pages/3_Price_and_Return.py"                                     # Price and Return with the Reddit volume next to it (Price and Reddit was merged into it, 2026-11-15)
SOURCE_PAGES = {"pages/1_Reddit_Volume.py", SPIKE_PAGE}   # system 7.1: DimSource filter
SENTIMENT_PAGE = "pages/5_Market_and_Sentiment.py"                            # 7.5-1: DimSentimentSource, DimMajoritySentiment
RANKING_PAGE = "pages/6_Statistical_Analysis.py"                              # 7.5-2: p-values, win rate, regression
DETECTION_PAGES = {SENTIMENT_PAGE: ["d_z", "d_mode", "d_s"], RANKING_PAGE: ["d_z", "d_mode", "d_s"]}
MAJORITY_PAGES = {SENTIMENT_PAGE, *DETECTION_PAGES}
SENTIMENT_PAGES = {SENTIMENT_PAGE, RANKING_PAGE}
COUNT_PAGES = SOURCE_PAGES - {SPIKE_PAGE}                                             # the count that follows the ticks (page 1: the mention count)
TIME_KEYS = ["f_range", "f_gran"]
COMMUNITIES = ["r/wallstreetbets", "r/stocks", "r/investing", "r/StockMarket", "r/options", "r/CryptoCurrency"]
SOURCE_KEYS = ["f_src_" + c for c in COMMUNITIES]                              # the content type (Post / Comment) is no longer a filter (2026-11-15)
SENTIMENT_KEYS = ["f_ss_" + c for c in COMMUNITIES] + ["f_ss_model"]
MAJORITY_KEYS = ["f_maj_positive", "f_maj_negative", "f_maj_neutral"]
GROUP_KEYS = ["f_group_stock_etf", "f_group_futures", "f_group_crypto"]
TICKERS = ["AAPL", "AMC", "AMD", "BITO", "BRK-B", "COIN", "GME", "HOOD", "IBIT", "IWM", "JNJ", "JPM", "KO", "MARA", "MSFT",
           "MSTR", "NVDA", "PLTR", "QQQ", "SPY", "TSLA", "XOM", "CL=F", "ES=F", "GC=F", "NG=F", "NQ=F", "RTY=F",
           "BTC-USD", "DOGE-USD", "ETH-USD", "SHIB-USD", "SOL-USD", "XRP-USD"]
PAGES = ["app.py", "pages/1_Reddit_Volume.py", SPIKE_PAGE,
         "pages/5_Market_and_Sentiment.py", RANKING_PAGE]                         # Hot Events has no central filter (it works on all the data): see HotEventsTests
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
        for page in ("pages/1_Reddit_Volume.py", "pages/5_Market_and_Sentiment.py", "pages/6_Statistical_Analysis.py"):
            fresh = self.run_page(page)
            default = (tuple(fresh.sidebar.date_input(key="f_range").value), fresh.sidebar.checkbox(key="f_group_crypto").value)
            at = self.run_page(page, f_group_crypto=False, f_range=(dt.date(2026, 8, 3), dt.date(2026, 8, 9)), f_gran="รายเดือน")
            if page != "pages/1_Reddit_Volume.py":
                at.sidebar.slider(key="d_z").set_value(1.5).run()
            at.sidebar.button(key="f_reset_button").click().run()
            self.assertEqual(len(at.exception), 0, "%s: %s" % (page, [e.value for e in at.exception]))
            self.assertEqual((tuple(at.sidebar.date_input(key="f_range").value), at.sidebar.checkbox(key="f_group_crypto").value), default, page)
            if page != "pages/1_Reddit_Volume.py":
                self.assertEqual((at.sidebar.slider(key="d_z").value, at.sidebar.slider(key="d_s").value), (0, 0.0), page)

    def test_a_choice_survives_pages_that_do_not_have_that_filter(self):
        """Leave a page and come back: every filter is as it was, also those the pages in between do not draw (they work with
        everything ticked in the background, the saved choice returns with the page that has the filter)."""
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(ROOT / "dashboard" / "app.py"), default_timeout=180).run()
        at = at.switch_page(SENTIMENT_PAGE).run()
        at.sidebar.slider(key="d_z").set_value(1.5)
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
        self.assertEqual(at.sidebar.slider(key="d_z").value, 1.5)
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
            self.assertFalse([c for c in at.sidebar.checkbox if "f_type_" in (c.key or "")], page + " has no content type filter")
            self.assertEqual(len(at.exception), 0, page)

    def test_every_ticker_box_starts_ticked(self):
        for page in MULTI_PAGES:
            at = self.run_page(page)
            for symbol in TICKERS:
                self.assertTrue(at.sidebar.checkbox(key="f_tk_" + symbol).value, "%s %s" % (page, symbol))

    def test_several_tickers_and_classes_change_the_numbers(self):
        """Page 1 (Ticker Mentions part): everything ticked = every ticker; ticking fewer narrows the numbers; unticking a class drops its tickers."""
        for page in COUNT_PAGES:
            at = self.run_page(page)
            # page 1: the all-volume cards never follow the ticks, so the count that follows is the Ticker Mention Count card; the other pages: the first card
            mentions = lambda a: ([m.value for m in a.metric if m.label == "ปริมาณการกล่าวถึงสินทรัพย์รวม"] or [a.metric[0].value])[0]
            full = mentions(at)
            at = tick_only(at, ["TSLA", "NVDA"])
            two = mentions(at)
            self.assertNotEqual(two, full, page)
            at = tick_only(at, ["TSLA", "NVDA", "BTC-USD"])
            self.assertNotEqual(mentions(at), two, page)
            at.sidebar.checkbox(key="f_group_crypto").set_value(False).run()          # BTC-USD leaves with its class
            self.assertEqual(mentions(at), two, page)
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
            if page == "pages/1_Reddit_Volume.py":                                    # the all-volume cards stay; the mention count falls to 0 and the rate to n/a
                cards = {m.label: m.value for m in at.metric}
                self.assertNotEqual(cards["ปริมาณข้อความรวม"], "0", page)
                self.assertEqual(cards["ปริมาณการกล่าวถึงสินทรัพย์รวม"], "0", page)
                self.assertEqual(cards["Ticker Mention Rate (%)"], "n/a", page)
            else:
                if page == SENTIMENT_PAGE:                                            # the text side is the whole market: the cards stay, only the asset parts are gone
                    self.assertTrue(at.metric and any(m.value not in ("0", "n/a") for m in at.metric), page)
                    self.assertTrue(any("ยังไม่ได้เลือกสินทรัพย์" in i.value for i in at.info), page)
                else:
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

    def test_logistic_page_follows_the_filters(self):
        """The Logistic Regression is a page of its own: the precomputed overview of the nine panels, then the table of the variables (kept or cut, and why) of the panel
        Global at the Current Return, computed live on the filters of the sidebar."""
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(ROOT / "dashboard" / "pages" / "9_Logistic_Regression.py"), default_timeout=600)
        at.run()
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        self.assertFalse(at.sidebar.slider(key="d_z").disabled)                              # the panel "all" follows the two thresholds
        self.assertEqual(len(at.metric), 0, "no cards on the Logistic page")
        self.assertEqual(len(at.dataframe), 3)                                                # metrics of the nine panels, before / after the cut, and the table of the variables

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
        self.assertEqual([m.label for m in at.metric], ["Historical Win Rate", "Spearman p-value"] * 2)      # two rows: Global, Ticker
        full = [m.value for m in at.metric]
        self.assertRegex(full[0], r"^\d+\.\d%$")
        for view in at.radio(key="p5_measure_all").options:                                 # the three measures (value and p-value in one cell)
            at.radio(key="p5_measure_all").set_value(view).run()
            self.assertEqual(len(at.exception), 0, "%s: %s" % (view, [e.value for e in at.exception]))
        self.assertEqual(at.radio(key="p5_measure_all").options, ["Spearman", "Win Rate"])            # Pearson is not shown: the data are not normal
        self.assertNotIn("ρ", "".join(at.radio(key="p5_measure_all").options))                 # the Greek rho looks like the p of p-value
        self.assertNotIn("p5_predictor", [r.key for r in at.radio])                          # the proposal measures only the mean Sentiment Score
        at.sidebar.slider(key="d_z").set_value(1.5).run()                                     # the Z-score narrows every panel and says what it means in texts
        self.assertEqual(len(at.exception), 0)
        self.assertNotEqual([m.value for m in at.metric][:3], full[:3])
        self.assertFalse(any("Z-score เกิน" in c.value for c in at.sidebar.caption), "no texts-per-hour hint under the Z-score slider (it misled: the Z-score is relative to each hour)")
        at.sidebar.slider(key="d_z").set_value(0.0)
        self.assertEqual(at.radio(key="p5_family_all").value, "global")                    # the default: the sentiment of the whole market
        self.assertEqual(len(at.radio(key="p5_family_all").options), 3)                    # Global, Ticker, compare (the random baseline is a kind of Global)
        for family in ("Ticker", "global"):                                                  # the picker of the kind of text is hidden (SHOW_PANEL_KIND = False): the panel "all" only
            at.radio(key="p5_family_all").set_value(family).run()
            self.assertNotIn("p5_panel", [r.key for r in at.radio], family)
            self.assertNotIn("p5_basis", [r.key for r in at.radio], family)                  # the picker "วัดความรู้สึกด้วย" is hidden too
            self.assertEqual(len(at.exception), 0, "%s: %s" % (family, [e.value for e in at.exception]))
            self.assertFalse(at.sidebar.slider(key="d_z").disabled, "the panel is always 'all': the two thresholds work")
        at.radio(key="p5_family_all").set_value("compare").run()                             # compare two panels: the difference B - A, the thresholds act on the sides "all" only
        for measure in ("Spearman", "Win Rate"):                                             # Global next to Ticker: the values themselves, no picker of panels
            at.radio(key="p5_cmp_measure").set_value(measure).run()
            self.assertEqual(len(at.exception), 0, "%s: %s" % (measure, [e.value for e in at.exception]))
            self.assertTrue(any(c.value.startswith("**สรุป:**") for c in at.caption), measure)
            self.assertNotIn("p5_cmp_a", [w.key for w in at.selectbox], measure)
        self.assertFalse(at.sidebar.slider(key="d_z").disabled, "the comparison is Global and Ticker 'all': the thresholds work")
        at.radio(key="p5_family_all").set_value("global").run()
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
        self.assertEqual([m.value for m in at.metric], ["0"] * 2)

    def test_model_choice_reaches_statistical_and_logistic_pages(self):
        """The model of DimSentimentSource (VADER+FinBERT / VADER / FinBERT) is a real filter on Statistical Analysis and on Logistic Regression too:
        a committee member who ticks only FinBERT must get FinBERT's numbers, not an error and not the combined ones."""
        import pyarrow as pa
        from streamlit.testing.v1 import AppTest
        stat = self.run_page(RANKING_PAGE)
        full = [m.value for m in stat.metric]
        for model in ("VADER", "FinBERT"):
            stat.sidebar.radio(key="f_ss_model").set_value(model).run()
            self.assertEqual(len(stat.exception), 0, model)
            self.assertNotEqual([m.value for m in stat.metric], full, "Statistical Analysis numbers follow the model: " + model)

        def test_auc(model):
            at = AppTest.from_file(str(ROOT / "dashboard" / "pages/9_Logistic_Regression.py"), default_timeout=600)
            at.run()
            at.sidebar.radio(key="f_ss_model").set_value(model).run()
            self.assertEqual(len(at.exception), 0, model)
            return list(at.dataframe[-1].value["เหตุผล"])                                          # the reasons carry the AUC gains of the model

        combined = test_auc("VADER+FinBERT")
        self.assertNotEqual(test_auc("FinBERT"), combined, "the AUC of the Logistic Regression follows the model")
        self.assertNotEqual(test_auc("VADER"), combined)

    @unittest.skip("the relation block of Market and Sentiment is hidden (SHOW_RELATION_BLOCK = False, user 2026-11-16); remove the skip when it is shown again")
    def test_relation_block_follows_the_model_and_the_thresholds(self):
        """(EXTENSION) the block "ผลตอบแทนเฉลี่ยตามระดับความรู้สึก" is computed live: the model of the sidebar, the Reddit Volume Threshold and the Sentiment Threshold all change its numbers."""
        at = self.run_page(SENTIMENT_PAGE)
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        full = [m.value for m in at.metric][3:]
        self.assertEqual(len(full), 3)
        self.assertTrue(full[0].endswith("%") and full[1][0] in "+-", full)
        for model in ("VADER", "FinBERT"):                                                   # a single model: its own sentiment, so its own numbers
            at.sidebar.radio(key="f_ss_model").set_value(model).run()
            self.assertEqual(len(at.exception), 0, model)
            self.assertNotEqual([m.value for m in at.metric][3:], full, "the relation block follows the model: " + model)
        at.sidebar.radio(key="f_ss_model").set_value("VADER+FinBERT")
        at.sidebar.slider(key="d_z").set_value(1.5).run()                                   # the Reddit Volume Z-score Threshold drops the hours below the Z-score
        self.assertEqual(len(at.exception), 0)
        self.assertNotEqual([m.value for m in at.metric][3:], full, "the relation block follows the Reddit Volume Z-score Threshold")
        at.sidebar.slider(key="d_z").set_value(0.0)
        at.sidebar.slider(key="d_s").set_value(0.30).run()                                   # the Sentiment Threshold keeps only the texts with |score| >= 0.30
        self.assertEqual(len(at.exception), 0)
        self.assertNotEqual([m.value for m in at.metric][3:], full, "the relation block follows the Sentiment Threshold")

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
        self.assertEqual([m.label for m in at.metric][:3], ["Sentiment Score", "Sentiment Momentum", "Reddit Volume Z-score สูงสุด"])
        self.assertEqual(len(at.metric), 3, "the relation block (deciles of the sentiment) is hidden: SHOW_RELATION_BLOCK = False")
        at.sidebar.checkbox(key="f_maj_neutral").set_value(True)
        # DimDetectionConfig is a FILTER on this page: 0 / 0 removes nothing, a threshold removes hours
        self.assertEqual((at.sidebar.slider(key="d_z").value, at.sidebar.slider(key="d_s").value), (0, 0.0))
        for z in (3.0, 1.5):
            at.sidebar.slider(key="d_z").set_value(z).run()
            self.assertEqual(len(at.exception), 0, z)
            self.assertNotEqual(at.metric[0].value, full[0], "Z-score Threshold %s removes hours, so the Sentiment Score changes" % z)
        at.sidebar.slider(key="d_z").set_value(0.0)
        at.run()
        at.sidebar.slider(key="d_z").set_value(1.5).run()
        self.assertFalse(any("Z-score เกิน" in c.value for c in at.sidebar.caption), "no hint under the Z-score slider")
        at.sidebar.slider(key="d_z").set_value(4.0).run()
        self.assertEqual(len(at.exception), 0)
        at.sidebar.slider(key="d_z").set_value(0.0)
        self.assertFalse([c for c in at.sidebar.checkbox if "f_type_" in (c.key or "")], "no content type filter")
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
        at.sidebar.checkbox(key="f_maj_positive").set_value(False).run()
        self.assertEqual(len(at.exception), 0)
        at.sidebar.checkbox(key="f_maj_positive").set_value(True)
        for key in ("f_ss_" + c for c in COMMUNITIES):
            at.sidebar.checkbox(key=key).set_value(False)
        at = at.run()
        self.assertTrue(all(m.value == "0" for m in at.metric), "no community ticked = nothing")

    def test_hot_events_has_no_filter_and_works_on_all_the_data(self):
        """No central filter on Hot Events: the whole period, every asset, the latest hour first (300 rows); the filters of the other pages are kept."""
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(ROOT / "dashboard" / "app.py"), default_timeout=300).run()
        at = at.switch_page(SENTIMENT_PAGE).run()
        at.sidebar.checkbox(key="f_tk_SPY").set_value(False).run()                  # a filter of another page
        at = at.switch_page("pages/8_Hot_Events.py").run()
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        self.assertEqual(len(at.sidebar.slider) + len(at.sidebar.checkbox) + len(at.sidebar.radio), 0, "no filter in the sidebar")
        self.assertEqual(at.multiselect(key="h_tickers").value, [], "every asset, whatever the other pages ticked")
        self.assertEqual(len(at.multiselect(key="h_tickers").options), 34)
        self.assertEqual(len(at.metric), 0, "no cards: the page counts the signals per level, the price after them is in the forward-check script")
        summary = [d.value for d in at.dataframe if "สัดส่วน (%)" in d.value.columns][0]
        self.assertEqual(list(summary["ระดับ"]), ["high", "medium", "low", "ไม่ถึง low", "รวม"])
        self.assertEqual(int(summary["จำนวน"].iloc[:4].sum()), int(summary["จำนวน"].iloc[4]))              # the levels add up to the total
        table = [d.value for d in at.dataframe if "ระดับ" in d.value.columns and "คะแนน (%)" in d.value.columns][0]
        self.assertEqual(len(table), 300)
        self.assertEqual(table["เวลา (UTC)"].iloc[0], max(table["เวลา (UTC)"]), "the latest hour first")
        self.assertIn("Current Return (%)", list(table.columns))                     # the default period is Current Return
        self.assertLess(list(table.columns).index("Current Return (%)"), list(table.columns).index("Trading Volume (ของสินทรัพย์)"))
        self.assertEqual(at.radio(key="h_levels").value, "all")                       # the default: every level
        at.radio(key="h_levels").set_value("high").run()                            # the level picker sits under the period picker; the list follows it (the summary shows every level)
        self.assertEqual(list([d.value for d in at.dataframe if "สัดส่วน (%)" in d.value.columns][0]["ระดับ"]), ["high", "medium", "low", "ไม่ถึง low", "รวม"])
        table = [d.value for d in at.dataframe if "ระดับ" in d.value.columns and "คะแนน (%)" in d.value.columns][0]
        self.assertEqual(set(table["ระดับ"]), {"high"})
        at = at.switch_page(SENTIMENT_PAGE).run()
        self.assertFalse(at.sidebar.checkbox(key="f_tk_SPY").value, "the filter of the other page is still there")

    def test_hot_events_score_and_levels_are_set_by_the_user_and_the_sidebar_still_filters(self):
        """Six measures, each with one threshold; the number a row passes decides low / medium / high.  Nothing changes until the button Apply is pressed;
        a stricter threshold or a higher cut lists fewer signals, cuts out of order stop the table, the reset button brings the defaults back, the sidebar
        still filters first."""
        at = self.run_page("pages/8_Hot_Events.py")
        def counts(page):
            return [d.value for d in page.dataframe if "สัดส่วน (%)" in d.value.columns][0]["จำนวน"].tolist()

        base = counts(at)
        self.assertNotIn("h_wh", [r.key for r in at.radio])                                 # no horizon of the Win Rate to pick: the statistics are those of the same hour
        self.assertEqual(at.number_input(key="hs_cut_high").value, 80.0)                    # the default of the level high (% score)
        at.number_input(key="hs_rz_t").set_value(3.5).run()                                 # typed, not applied yet: the numbers below do not move
        self.assertEqual(counts(at), base)
        at.number_input(key="hs_rz_t").set_value(3.5)
        at.button(key="h_apply").click().run()                                              # applied: a stricter threshold, fewer rows pass the volume KPI
        self.assertNotEqual(counts(at), base)
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        at.number_input(key="hs_cut_low").set_value(90.0)
        at.button(key="h_apply").click().run()                                              # low above medium: the cuts are out of order
        self.assertTrue(any("เรียงจากน้อยไปมาก" in i.value for i in at.info))
        at.button(key="h_level_reset").click().run()
        self.assertEqual(counts(at), base)                                          # the defaults are back
        self.assertEqual(round(sum(at.number_input(key="hs_%s_w" % m).value for m in ("rz", "mr", "ss", "tz", "na", "cr"))), 100)     # the weights total 100 %
        at.number_input(key="hs_rz_w").set_value(60.0)
        at.button(key="h_apply").click().run()                                              # the weights no longer total 100 %: an error, no table
        self.assertTrue(any("100" in e.value for e in at.error))
        at.button(key="h_level_reset").click().run()
        self.assertEqual(len(at.slider), 0, "no threshold of DimDetectionConfig on this page: the score decides what is a signal")
        keys = [n.key for n in at.number_input]
        for metric in ("rz", "mr", "ss", "tz", "na", "cr"):                                  # the six KPIs known in the hour have a threshold
            self.assertIn("hs_%s_t" % metric, keys)
        self.assertEqual([k for k in keys if k.endswith("_p")], [], "no weights")
        self.assertNotIn("hs_wr_p", keys)
        for row in at.dataframe:
            if "ระดับ" in row.value.columns and "คะแนน (%)" in row.value.columns:
                self.assertNotIn("ชนิด", row.value.columns)                                  # no signal type any more
                self.assertTrue(set(row.value["ระดับ"]) <= {"low", "medium", "high"})
                self.assertTrue((row.value["คะแนน (%)"] >= 30).all(), "a signal below the level low is dropped")
                for gone in ("Ticker Mention Rate (%)", "Reddit Volume Z-score (ทั้งตลาด)", "Trading Volume Z-score (ของสินทรัพย์)"):
                    self.assertNotIn(gone, row.value.columns)
                break
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])

    @unittest.skip("the vote mode of the ratio chart is hidden (SHOW_VOTE_MODE = False in 5_Market_and_Sentiment.py, user 2026-11-16); remove the skip when it is shown again")
    def test_majority_vote_chart_follows_every_filter(self):
        """The vote mode of the ratio chart changes with the majority status, the community and the time range; the tickers do not change it (every text of the market)."""
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
        self.assertEqual(shares(at), march, "the text side is the whole market: it does not follow the ticked assets")
        self.assertEqual(len(at.exception), 0)

    def test_price_page_follows_the_ticked_tickers(self):
        """One ticker, a few and many all render; the Current Return card follows the ticks, the Reddit volume card does not; every chart has a title and a line
        saying what it is for, and the Reddit measure can be switched."""
        page = "pages/3_Price_and_Return.py"
        at = self.run_page(page)
        card = lambda a, label: [m.value for m in a.metric if m.label == label][0]
        many, volume = card(at, "Current Return รวมทั้งช่วง (%)"), card(at, "ปริมาณข้อความรวม")
        at = tick_only(at, ["SPY"])
        self.assertEqual(len(at.exception), 0)
        one = card(at, "Current Return รวมทั้งช่วง (%)")
        at = tick_only(at, ["SPY", "TSLA", "BTC-USD"])
        self.assertEqual(len(at.exception), 0)
        self.assertNotEqual(card(at, "Current Return รวมทั้งช่วง (%)"), one)
        self.assertNotEqual(one, many)
        self.assertEqual(card(at, "ปริมาณข้อความรวม"), volume, "the Reddit volume of the market does not depend on the asset")
        self.assertEqual([r.key for r in at.radio if r.key and r.key.startswith("ck_")], [], "no line / bar switch")
        titles = [h.value.lstrip("# ") for h in at.markdown if h.value.startswith("###")]
        self.assertIn("|Current Return| (%) เทียบกับปริมาณ Reddit", titles)
        self.assertNotIn("ราคาปิด เทียบกับปริมาณ Reddit", titles, "several assets: no price chart (the price levels cannot be compared)")
        self.assertIn("ราคาปิด เทียบกับปริมาณ Reddit", [h.value.lstrip("# ") for h in tick_only(self.run_page(page), ["SPY"]).markdown], "one asset: its price")
        self.assertEqual([r.key for r in at.radio if r.key == "pr_reddit_measure"], [], "the Reddit measure is a tick box in each chart, not a button")
        for key in ("or_pr_return_texts", "or_pr_return_mentions", "ol_pr_return"):                   # a tick box per line, all ticked at first
            self.assertTrue(at.checkbox(key=key).value, key)
        at.checkbox(key="or_pr_return_mentions").set_value(False).run()                              # hide the mentions: the price and the volume stay
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        at.checkbox(key="ol_pr_return").set_value(False).run()
        at.checkbox(key="or_pr_return_texts").set_value(False).run()                                  # nothing ticked: a hint
        self.assertTrue(any("อย่างน้อย 1 เส้น" in i.value for i in at.info))
        self.assertGreaterEqual(len(at.caption), 8, "every chart and table has a line saying what it is for")

    def test_all_reddit_volume_stays_when_tickers_are_unticked(self):
        """Reddit Volume (all texts) never depends on the asset filter: unticking tickers changes only the Ticker Mentions part of the page."""
        at = self.run_page("pages/1_Reddit_Volume.py")
        self.assertEqual(at.metric[0].label, "ปริมาณข้อความรวม")
        all_total = at.metric[0].value
        self.assertEqual(len(at.info), 0)
        at = tick_only(at, ["SPY"])
        self.assertEqual(at.metric[0].label, "ปริมาณข้อความรวม")
        self.assertEqual(at.metric[0].value, all_total, "all texts, whatever tickers are ticked")
        def lines(a):                                                  # the titles of the y axes of the first chart (volume on the left, mentions on the right)
            found = []
            def walk(o):
                if isinstance(o, dict):
                    if isinstance(o.get("axis"), dict) and o["axis"].get("title"):
                        found.append(o["axis"]["title"])
                    for v in o.values():
                        walk(v)
                elif isinstance(o, list):
                    for v in o:
                        walk(v)
            walk(json.loads(a.get("vega_lite_chart")[0].proto.spec))
            return list(dict.fromkeys(found))
        self.assertEqual(lines(tick_only(at, ["SPY"])), ["ปริมาณข้อความทั้งหมด", "ปริมาณการกล่าวถึงสินทรัพย์"])    # the volume stays, the right axis is the ticked ticker
        nothing = tick_only(at, [])
        self.assertIn("ปริมาณข้อความทั้งหมด", json.dumps(json.loads(nothing.get("vega_lite_chart")[0].proto.spec), ensure_ascii=False))           # nothing ticked: the volume line alone
        at = tick_only(at, ["SPY"])
        labels = [m.label for m in at.metric]
        self.assertIn("ปริมาณการกล่าวถึงสินทรัพย์รวม", labels)        # the mentions part follows the ticked tickers
        self.assertIn("Ticker Mention Rate (%)", labels)

    def test_z_score_chart_sits_above_the_mentions_and_holds_both_z_scores(self):
        """The Z-score chart comes right under the comparison chart (above the mentions ranking) with the Z-score of the volume and, for the ticked tickers, the
        Z-score of the mentions; with no ticker ticked only the volume one."""
        def titles(a):
            return [h.value.lstrip("# ") for h in a.markdown if h.value.startswith("#")]
        def series(a, i):
            spec = json.loads(a.get("vega_lite_chart")[i].proto.spec)
            return spec["layer"][0]["encoding"]["color"]["scale"]["domain"]
        at = tick_only(self.run_page("pages/1_Reddit_Volume.py"), ["SPY"])
        order = titles(at)
        self.assertLess(order.index("Z-score ปริมาณข้อความ เทียบกับ Z-score ปริมาณการกล่าวถึงสินทรัพย์"), order.index("ปริมาณการกล่าวถึงสินทรัพย์"))
        self.assertEqual(series(at, 1), ["Z-score ปริมาณข้อความ", "Z-score ปริมาณการกล่าวถึงสินทรัพย์"])
        self.assertEqual(series(tick_only(at, []), 1), ["Z-score ปริมาณข้อความ"])
        at = tick_only(at, ["SPY"])
        at.checkbox(key="zl_mention_z").set_value(False).run()                      # a tick box per line: untick the mentions, the volume one stays
        self.assertEqual(series(at, 1), ["Z-score ปริมาณข้อความ"])
        at.checkbox(key="zl_zscore").set_value(False).run()                         # nothing ticked: a hint, and both lines come back
        self.assertEqual(len(at.exception), 0)
        self.assertTrue(any("อย่างน้อย 1 เส้น" in i.value for i in at.info))

    def test_one_table_by_community_holds_the_volume_and_the_mentions(self):
        """The volume by community and the mentions by community are ONE table (it was two); the mentions count a text once per ticker."""
        at = tick_only(self.run_page("pages/1_Reddit_Volume.py"), ["TSLA"])
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        tables = [d.value for d in at.dataframe if "ปริมาณข้อความ" in d.value.columns and "ปริมาณการกล่าวถึง" in d.value.columns]
        self.assertEqual(len(tables), 1)
        table = tables[0]
        self.assertIn("Mention Rate (%)", table.columns)
        self.assertFalse([c for c in table.columns if "โพสต์" in c or "ความคิดเห็น" in c], "no split into posts and comments")
        total = table.loc["รวมทุกชุมชน"]
        self.assertLessEqual(total["Mention Rate (%)"], 100.0)                      # one ticker: a share of the texts, never above 100 %
        self.assertEqual([m.value for m in at.metric if m.label == "ปริมาณการกล่าวถึงสินทรัพย์รวม"][0].replace(",", ""), str(int(total["ปริมาณการกล่าวถึง"])))    # the card is the same number
        self.assertNotIn("ปริมาณการกล่าวถึงสินทรัพย์ รายสินทรัพย์ (ชุมชน × ประเภทเนื้อหา)", [h.value.lstrip("# ") for h in at.markdown])

    def test_reddit_volume_and_ticker_mentions_page_has_no_line_bar_switch(self):
        """One page for 7.1, lines only: no line / bar switch, not for one ticker, several or many; a ticker set that is empty keeps the all-volume part."""
        for keep in (["SPY"], ["TSLA", "NVDA", "SPY"], ["TSLA", "NVDA", "SPY", "QQQ", "AAPL", "AMD", "AMC", "GME", "MSFT"]):
            at = tick_only(self.run_page("pages/1_Reddit_Volume.py"), keep)
            self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
            self.assertEqual([r.key for r in at.radio if r.key and r.key.startswith("ck_")], [], keep)
        at = tick_only(self.run_page("pages/1_Reddit_Volume.py"), [])
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        self.assertEqual(at.metric[0].label, "ปริมาณข้อความรวม")        # nothing ticked: the all-volume part is still there

    def test_the_pages_have_no_line_bar_switch_and_the_sidebar_has_the_chart_level_only(self):
        """The line / bar switch was removed (pages 1 and 3 draw lines only); the sidebar radio is the chart level."""
        for page in ("pages/1_Reddit_Volume.py", "pages/3_Price_and_Return.py"):
            at = self.run_page(page)
            self.assertEqual([r.key for r in at.radio if r.key and r.key.startswith("ck_")], [], page)
            self.assertEqual([r.key for r in at.sidebar.radio], ["f_gran"], page)

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
        at.sidebar.checkbox(key="f_src_r/stocks").set_value(False)
        at = tick_only(at, ["TSLA"])
        self.assertEqual(len(at.exception), 0)
        state = {"f_src_r/options": False, "f_src_r/stocks": False, "f_tk_TSLA": True, "f_tk_SPY": False}
        other = AppTest.from_file(str(ROOT / "dashboard" / "app.py"), default_timeout=90)
        for key, value in state.items():
            other.session_state[key] = value
        other = other.run()                                         # page without the widgets: the values go to shadow keys
        self.assertFalse(other.session_state["_keep_f_src_r/options"])
        self.assertFalse(other.session_state["_keep_f_src_r/stocks"])
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
            if page == "pages/8_Hot_Events.py":                       # the score and the levels are set first (before the cards), by design
                continue
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
