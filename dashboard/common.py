"""Shared pieces of the dashboard pages (TASKS D0): path setup, cached queries, the central sidebar filter, charts.

Run:   streamlit run dashboard/app.py          (from the project root)
Pages: dashboard/pages/*.py  (Streamlit builds the menu from the file names)

Central filter (identical on every page: same widgets, same order, same fixed keys, so a choice made on one page
holds on all of them):
  The sidebar follows the three dimensions of the proposal, time first:
    time      DimTime    date range (default: the last year of the data) and the chart level (hour .. year)
    source    DimSource  platform (Reddit) > communities > Post / Comment: one tick box each, all ticked at first
                                                                           (pages 1-2 only)
    asset     DimTicker  asset class (Big_Group) boxes > tickers; pages 1-2 take SEVERAL tickers (one tick box each,
                         all ticked at first), the other pages one ticker
  Times are UTC.  Rule: a central widget that a page does not draw is kept in a shadow key, because Streamlit
  forgets it otherwise.
"""

import datetime as dt
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:                       # `streamlit run dashboard/app.py` puts dashboard/ first, not the root
    sys.path.insert(0, str(ROOT))

import altair as alt                                # noqa: E402
import pandas as pd                                 # noqa: E402
import streamlit as st                              # noqa: E402

from dashboard import data                          # noqa: E402

DB_PATH = os.environ.get("REDDIT_DB", str(data.DEFAULT_DB))
DISCLAIMER = ("ข้อมูลย้อนหลังจาก Academic Torrents และ yfinance เพื่อสนับสนุนการวิเคราะห์เท่านั้น  \n"
              "ไม่ใช่ข้อมูล real-time, ไม่ใช่คำแนะนำการลงทุน และไม่ใช่การทำนายราคา")
# Asset classes always appear in this order (stocks/ETF, futures, crypto) and with the same colour in every chart.
GROUP_LABELS = {"stock_etf": "หุ้น/ETF", "futures": "ฟิวเจอร์ส", "crypto": "คริปโต"}
GROUP_COLORS = {"stock_etf": "#1f77b4", "futures": "#ff7f0e", "crypto": "#2ca02c"}   # blue, orange, green
GROUP_DOTS = {"stock_etf": "🔵", "futures": "🟠", "crypto": "🟢"}   # same colours inside the sidebar list
TYPE_KEYS = ["f_type_Post", "f_type_Comment"]
STATUSES = ("positive", "negative", "neutral")                  # DimMajoritySentiment
MAJORITY_KEYS = ["f_maj_" + s for s in STATUSES]
SIGNAL_KEYS = ["s_z", "s_s", "s_h"]                             # DimDetectionConfig on the Ranking and Signals page
EVENT_KEYS = ["h_z", "h_s"]                                     # the same idea on the Hot Events page
OVERVIEW_KEYS = ["d_z", "d_s"]                                  # Market and Sentiment: thresholds FILTER the whole page (0 = no filter)
SENTIMENT_MODELS = ("VADER+FinBERT", "VADER", "FinBERT")         # DimSentimentSource.ModelUsed; the first is the proposal's
DEFAULT_RANGE_DAYS = 365
TIME_KEYS = ["f_range", "f_gran"]                              # DimTime: the date range and the chart level

# ---- one chart design for every dashboard: one height, one colour per measure, one grid / axis style, one tooltip behaviour
CHART_HEIGHT = 280
C_PRICE = "#1f77b4"            # close price, Current Return          (blue)
C_VOLUME = "#2ca02c"           # market trading volume                (green)
C_REDDIT = "#ff7f0e"           # Reddit volume, comments, mentions    (orange)
C_REDDIT_LIGHT = "#ffbb78"     # posts (a small share of the Reddit texts)
C_Z = "#d62728"                # Reddit Volume Z-score                (red: unusual)
C_SENT = "#17becf"             # Sentiment Score                      (teal: a neutral colour, not a verdict)
C_RATE = "#9467bd"             # Ticker Mention Rate, RSI             (purple)
C_ATR = "#8c564b"              # ATR                                  (brown)
C_NATR = "#e377c2"             # Normalized ATR                       (pink)


def group_name(key):
    """Short Thai name of a Big_Group key (unknown keys are returned unchanged)."""
    return GROUP_LABELS.get(key, key)


def group_scale():
    """Altair colour scale: Thai group name -> the fixed colour (use with a column holding the Thai name)."""
    return alt.Scale(domain=[GROUP_LABELS[k] for k in GROUP_LABELS], range=[GROUP_COLORS[k] for k in GROUP_LABELS])


@st.cache_data(ttl=3600, show_spinner=False)
def _cached(name, code_version, *args):
    """The cache key contains `code_version`, so editing data.py can never serve results of the old query."""
    return getattr(data, name)(DB_PATH, *args)


def q(name, *args):
    """Cached call of dashboard.data.<name>(DB_PATH, *args).  Arguments must be hashable (str / int / tuple)."""
    return _cached(name, os.path.getmtime(data.__file__), *args)


def setup(title, icon="📊"):
    """Page config + title + the shared disclaimer; call first on every page."""
    st.set_page_config(page_title=title, page_icon=icon, layout="wide")
    st.title(title)
    st.caption(DISCLAIMER)


def epoch(day, end_of_day=False):
    """Date -> epoch seconds of 00:00 (or 23:00 = last hour) UTC of that day."""
    moment = dt.datetime(day.year, day.month, day.day, 23 if end_of_day else 0, tzinfo=dt.timezone.utc)
    return int(moment.timestamp())


def _restore(keys):
    """Bring back values that a page without those widgets had dropped (see `_keep`).  A value that is still there is
    assigned to itself: Streamlit then treats it as set by the app, so a widget that the new page draws anew (a different
    page = a new widget id) starts with that value instead of its default."""
    for key in keys:
        if key in st.session_state:
            st.session_state[key] = st.session_state[key]
        elif ("_keep_" + key) in st.session_state:
            st.session_state[key] = st.session_state["_keep_" + key]


def _keep(keys):
    for key in keys:
        if key in st.session_state:
            st.session_state["_keep_" + key] = st.session_state[key]


def _community_key(name):
    return "f_src_" + name


def source_keys():
    """Session keys of the source filter: one tick box per community, then Post and Comment."""
    return [_community_key(c) for c in dict.fromkeys(q("sources").subreddit)] + TYPE_KEYS


def selected_sources():
    """DimSource ids kept by the sidebar source filter (communities x Post / Comment); nothing ticked = nothing."""
    src = q("sources")
    all_communities = list(dict.fromkeys(src.subreddit))
    communities = [c for c in all_communities if st.session_state.get(_community_key(c), True)]
    types = [kind for kind in ("Post", "Comment") if st.session_state.get("f_type_" + kind, True)]
    keep = src[src.subreddit.isin(communities) & src.content_type.isin(types)]
    return tuple(int(i) for i in keep.source_id)


def _ticker_key(symbol):
    return "f_tk_" + symbol


def ticker_keys():
    """Session keys of the multi-ticker filter: one tick box per ticker."""
    return [_ticker_key(s) for s in q("tickers").ticker]


def selected_tickers():
    """Tickers kept by the asset filter of pages 1-3: the ticked tickers inside the ticked asset classes (no class ticked:
    the ticked tickers among all of them).  Everything is ticked at first; nothing ticked = nothing."""
    universe = q("tickers")
    groups = [g for g in GROUP_LABELS if st.session_state.get("f_group_" + g, True)]
    pool = list(universe[universe.big_group.isin(groups)].ticker) if groups else list(universe.ticker)
    return tuple(s for s in pool if st.session_state.get(_ticker_key(s), True))


def tickers_restricted():
    """True when the asset filter keeps fewer than all 34 tickers (then the numbers count mentions of those tickers
    instead of every text)."""
    return len(selected_tickers()) < len(q("tickers"))


def _sentiment_key(name):
    return "f_ss_" + name


def sentiment_source_keys():
    return [_sentiment_key(c) for c in dict.fromkeys(q("sources").subreddit)] + ["f_ss_model"]


def selected_content_types():
    """Content types kept by the DimSource filter of the pages with a sentiment source ('Post', 'Comment'); nothing ticked = nothing."""
    return tuple(kind for kind in ("Post", "Comment") if st.session_state.get("f_type_" + kind, True))


def selected_model():
    """The model chosen in the DimSentimentSource filter (one of SENTIMENT_MODELS)."""
    model = st.session_state.get("f_ss_model", SENTIMENT_MODELS[0])
    return model if model in SENTIMENT_MODELS else SENTIMENT_MODELS[0]


def selected_communities():
    """Communities kept by the DimSentimentSource filter ('r/wallstreetbets', ...); nothing ticked = nothing."""
    return tuple(c for c in dict.fromkeys(q("sources").subreddit) if st.session_state.get(_sentiment_key(c), True))


def selected_statuses():
    """Majority statuses kept by the DimMajoritySentiment filter; nothing ticked = nothing."""
    return tuple(s for s in STATUSES if st.session_state.get("f_maj_" + s, True))


def _sentiment_source_filter():
    """DimSentimentSource: platform (Reddit) > community > model (pick one: VADER+FinBERT, VADER or FinBERT)."""
    st.sidebar.markdown("**แหล่งข้อมูลความรู้สึก (DimSentimentSource)**")
    for key in sentiment_source_keys() + TYPE_KEYS:
        st.session_state.setdefault(key, True if key != "f_ss_model" else SENTIMENT_MODELS[0])
    st.sidebar.caption("แพลตฟอร์ม: Reddit › ชุมชน")
    for community in dict.fromkeys(q("sources").subreddit):
        st.sidebar.checkbox(community, key=_sentiment_key(community))
    st.sidebar.caption("ประเภทเนื้อหา (DimSource)")
    st.sidebar.checkbox("โพสต์ (Post)", key="f_type_Post")
    st.sidebar.checkbox("ความคิดเห็น (Comment)", key="f_type_Comment")
    st.sidebar.caption("แบบจำลองที่ใช้")
    st.sidebar.radio("แบบจำลองที่ใช้", SENTIMENT_MODELS, key="f_ss_model", label_visibility="collapsed")


def _majority_filter():
    """DimMajoritySentiment: the majority status of the hour (final result of 7.3), every box ticked at first."""
    st.sidebar.markdown("**ประเภทความรู้สึกส่วนใหญ่ (DimMajoritySentiment)**")
    for key in MAJORITY_KEYS:
        st.session_state.setdefault(key, True)
    for status in STATUSES:
        st.sidebar.checkbox(status, key="f_maj_" + status)


def _z_hint(key):
    """Under the Z-score slider: what that threshold means in texts per hour, so the user need not think in standard deviations.  An hour
    passes when its texts exceed the mean + Z x the standard deviation of the 24 hours before it; the line gives that number for the chosen
    tickers and range (the median, and where the middle half of the tickers lie)."""
    z = st.session_state.get(key, 0.0)
    span = st.session_state.get("f_range")
    days = sorted(span) if isinstance(span, (tuple, list)) and len(span) else []
    if not z or not days:
        return
    tickers = tuple(selected_tickers())
    need = data.texts_needed(q("volume_baseline", tickers, epoch(days[0]), epoch(days[-1], end_of_day=True)), z)
    if need is None:
        st.sidebar.caption("ไม่มีข้อมูลปริมาณของหลักทรัพย์และช่วงเวลาที่เลือก")
        return
    mid, low, high = need
    if len(tickers) == 1 or low == high:
        st.sidebar.caption("Z-score เกิน %.1f = ปริมาณ **มากกว่า %s ข้อความต่อชั่วโมง**" % (z, "{:,}".format(mid)))
    else:
        st.sidebar.caption("Z-score เกิน %.1f = ปริมาณ **มากกว่า %s ข้อความต่อชั่วโมง** (ค่ากลางของสินทรัพย์ที่เลือก; ส่วนใหญ่ %s–%s ตามความดังของแต่ละตัว)"
                           % (z, "{:,}".format(mid), "{:,}".format(low), "{:,}".format(high)))


def _detection_filter(kind):
    """DimDetectionConfig: Z-score Threshold, Sentiment Threshold and Horizon (kind 'signals' = Ranking and Signals, 'overview' =
    Market and Sentiment: two thresholds that filter the whole page, 0 = off; the Horizon is chosen inside the charts that need it), or the thresholds and the minimum number of
    texts of the Hot Events page (kind 'events')."""
    state = st.session_state
    st.sidebar.markdown("**เกณฑ์การตรวจจับสัญญาณ (DimDetectionConfig)**")
    if kind == "overview":                                  # filters the hours of the page; 0 = off, so by default nothing is removed
        state.setdefault("d_z", 0.0)
        state.setdefault("d_s", 0.0)
        st.sidebar.caption("Reddit Volume Z-score Threshold (ปริมาณต้องเกิน; 0 = ไม่กรอง)")
        st.sidebar.slider("Reddit Volume Z-score Threshold", 0.0, 4.0, step=0.1, key="d_z", label_visibility="collapsed")
        _z_hint("d_z")
        st.sidebar.caption("Sentiment Threshold (|ความรู้สึก| ตั้งแต่; 0 = ไม่กรอง)")
        st.sidebar.slider("Sentiment Threshold", 0.0, 1.0, step=0.05, key="d_s", label_visibility="collapsed")

    elif kind == "signals":
        state.setdefault("s_z", 1.5)
        state.setdefault("s_s", 0.30)
        state.setdefault("s_h", "1h")
        st.sidebar.caption("Reddit Volume Z-score Threshold (ปริมาณต้องเกิน)")
        st.sidebar.slider("Reddit Volume Z-score Threshold", 0.5, 4.0, step=0.1, key="s_z", label_visibility="collapsed")
        st.sidebar.caption("Sentiment Threshold (|ความรู้สึก| ตั้งแต่)")
        st.sidebar.slider("Sentiment Threshold", 0.0, 1.0, step=0.05, key="s_s", label_visibility="collapsed")
        st.sidebar.caption("Horizon (กรอบเวลาของสถิติย้อนหลัง)")
        st.sidebar.radio("Horizon", list(data.HORIZONS), key="s_h", horizontal=True, label_visibility="collapsed")
    else:
        state.setdefault("h_z", 2.0)
        state.setdefault("h_s", 0.50)
        st.sidebar.caption("Reddit Volume Z-score Threshold (ปริมาณต้องเกิน)")
        st.sidebar.slider("Reddit Volume Z-score Threshold", 1.5, 4.0, step=0.1, key="h_z", label_visibility="collapsed")
        _z_hint("h_z")
        st.sidebar.caption("Sentiment Threshold (|ความรู้สึก| ตั้งแต่)")
        st.sidebar.slider("Sentiment Threshold", 0.05, 0.90, step=0.05, key="h_s", label_visibility="collapsed")



def _source_filter():
    """The DimSource part of the sidebar: platform (fixed: Reddit) > communities > content type, every box ticked."""
    src = q("sources")
    st.sidebar.markdown("**แหล่งข้อมูล (DimSource)**")
    for key in source_keys():
        st.session_state.setdefault(key, True)
    st.sidebar.caption("แพลตฟอร์ม: Reddit › ชุมชน")
    for community in dict.fromkeys(src.subreddit):
        st.sidebar.checkbox(community, key=_community_key(community))
    st.sidebar.caption("ประเภทเนื้อหา")
    st.sidebar.checkbox("โพสต์ (Post)", key="f_type_Post")
    st.sidebar.checkbox("ความคิดเห็น (Comment)", key="f_type_Comment")


def _time_filter(info):
    """DimTime part of the sidebar: the date range and the chart level.  Returns (start_day, end_day)."""
    lo = dt.datetime.fromtimestamp(info["market_lo"], dt.timezone.utc).date()
    hi = dt.datetime.fromtimestamp(info["reddit_hi"], dt.timezone.utc).date()
    state = st.session_state
    st.sidebar.markdown("**เวลา (DimTime)**")
    state.setdefault("f_range", (max(lo, hi - dt.timedelta(days=DEFAULT_RANGE_DAYS)), hi))     # no `value=`: the key carries it
    state.setdefault("f_gran", DEFAULT_LEVEL)
    stored = state["f_range"]                                       # a stale range outside the data would make the box fail
    given = list(stored) if isinstance(stored, (tuple, list)) else [stored]
    clipped = tuple(min(max(d, lo), hi) for d in given)
    if tuple(given) != clipped:
        state["f_range"] = clipped
    st.sidebar.caption("ช่วงเวลา (UTC) ค่าเริ่มต้นย้อนหลัง 1 ปี")
    picked = st.sidebar.date_input("ช่วงเวลา (UTC)", min_value=lo, max_value=hi, key="f_range", format="YYYY/MM/DD",
                                   label_visibility="collapsed",
                                   help="พิมพ์วันที่ในช่องได้โดยตรง (ปี/เดือน/วัน) หรือคลิกจากปฏิทิน")
    # While the user is still choosing, Streamlit returns only ONE date (a tuple of length 1): treat it as that single
    # day until the second date is clicked, so the page never breaks halfway through a selection.
    days = list(picked) if isinstance(picked, (tuple, list)) else [picked]
    start_day, end_day = (days[0], days[1]) if len(days) >= 2 else (days[0], days[0])
    if len(days) < 2:
        st.sidebar.caption("เลือกวันเดียวอยู่: ดูเฉพาะวันนี้ จนกว่าจะคลิกวันสุดท้ายของช่วง")
    st.sidebar.caption("ข้อมูล Reddit: %s → %s" % (dt.datetime.fromtimestamp(info["reddit_lo"], dt.timezone.utc).date(), hi))
    st.sidebar.caption("ระดับเวลาของกราฟ (ชั่วโมง › วัน › สัปดาห์ › เดือน › ปี)")
    st.sidebar.radio("ระดับเวลาของกราฟ", list(GRANULARITY), key="f_gran", label_visibility="collapsed",
                     help="ระดับเวลาของ DimTime (รายชั่วโมงในช่วงยาวมากอาจโหลดช้า)")
    return start_day, end_day


def _group_toggled(group):
    """Callback of an asset-class box: ticking a class ticks the whole class, unticking it clears it."""
    universe = q("tickers")
    value = st.session_state["f_group_" + group]
    for symbol in universe[universe.big_group == group].ticker:
        st.session_state[_ticker_key(symbol)] = value


def _set_all(value):
    """Callback of the two small buttons: tick / untick every ticker AND every asset class (nothing ticked = everything
    is shown, so "clear" is the start of a new choice)."""
    for key in ticker_keys() + ["f_group_" + g for g in GROUP_LABELS]:
        st.session_state[key] = value


def _ticker_boxes(options, label):
    """One tick box per ticker of the ticked classes, drawn like the other tick boxes of the sidebar, all ticked at
    first, with two small buttons to tick / untick the whole list."""
    for key in ticker_keys():
        st.session_state.setdefault(key, True)
    st.sidebar.caption("สัญลักษณ์หลักทรัพย์")
    left, right = st.sidebar.columns(2)
    left.button("เลือกทั้งหมด", key="f_tk_all", on_click=_set_all, args=(True,), width="content")
    right.button("ล้าง", key="f_tk_none", on_click=_set_all, args=(False,), width="content")
    for symbol in options:
        st.sidebar.checkbox(label(symbol), key=_ticker_key(symbol))


def _asset_filter(universe, multi):
    """The DimTicker part of the sidebar: asset class > ticker.  Returns (None, groups).
    multi=True: one tick box per ticker (every page of the dashboards); otherwise only the asset classes (home page)."""
    st.sidebar.markdown("**หลักทรัพย์ (DimTicker)**")
    st.sidebar.caption("กลุ่มสินทรัพย์")
    # One tick box per asset class (instead of a multiselect whose chips are all the same colour): the coloured dot is
    # the colour this class has in every chart.
    for key in GROUP_LABELS:
        st.session_state.setdefault("f_group_" + key, True)
    groups = [key for key in GROUP_LABELS
              if st.sidebar.checkbox(GROUP_DOTS[key] + " " + GROUP_LABELS[key], key="f_group_" + key,
                                     on_change=_group_toggled, args=(key,))]
    # nothing ticked = nothing shown; the ticker list then offers every ticker, so a choice can be built one by one
    pool = universe[universe.big_group.isin(groups)] if groups else universe
    options = list(pool.ticker)                             # already ordered stocks/ETF, futures, crypto
    kind_of = dict(zip(universe.ticker, universe.big_group))
    name = dict(zip(universe.ticker, universe.name))
    label = lambda t: "%s %s · %s" % (GROUP_DOTS[kind_of[t]], t, name[t])                     # noqa: E731
    if multi:
        _ticker_boxes(options, label)
        return None, groups
    return None, groups                                      # the home page: asset classes only


def sidebar(assets=True, sources=False, multi=False, sentiment=False, detection=None, majority=False):
    """Draw the central filter (time first, then source, then asset); returns (ticker or None, start_epoch, end_epoch,
    groups).  assets=False: the asset filter is NOT drawn and all classes are used.  sources=True: the source filter
    is drawn too (read it with `selected_sources()`).  multi=True: several tickers can be chosen (read them with
    `selected_tickers()`; the returned ticker is None).
    System 7.5 pages add: sentiment=True (DimSentimentSource, `selected_communities()`), detection='signals' / 'events'
    (DimDetectionConfig, values in session state s_z / s_s / s_h or h_z / h_s) and majority=True
    (DimMajoritySentiment, `selected_statuses()`).
    Streamlit would forget the values of widgets a page does not draw, so they are kept in shadow keys and restored on
    the next page that draws them."""
    info = q("data_range")
    universe = q("tickers")
    st.sidebar.header("ตัวกรองกลาง")
    s_keys = source_keys()
    group_keys = ["f_group_" + k for k in GROUP_LABELS]
    t_keys = ticker_keys()
    ss_keys = sentiment_source_keys()
    central = TIME_KEYS + t_keys + group_keys + s_keys + ss_keys + MAJORITY_KEYS + SIGNAL_KEYS + EVENT_KEYS + OVERVIEW_KEYS
    _restore(central)
    if not sources:                                          # the sentiment-source block draws the Post / Comment boxes itself
        _keep([k for k in s_keys if not (sentiment and k in TYPE_KEYS)])
    if not sentiment:
        _keep(ss_keys)
    if not majority:
        _keep(MAJORITY_KEYS)
    if detection != "signals":
        _keep(SIGNAL_KEYS)
    if detection != "events":
        _keep(EVENT_KEYS)
    if detection != "overview":
        _keep(OVERVIEW_KEYS)
    if not assets:
        _keep(t_keys + group_keys)
    elif not multi:
        _keep(t_keys)
    start_day, end_day = _time_filter(info)
    if sources:
        st.sidebar.divider()
        _source_filter()
    ticker, groups = None, list(GROUP_LABELS)
    if assets:
        st.sidebar.divider()
        ticker, groups = _asset_filter(universe, multi)
    if sentiment:
        st.sidebar.divider()
        _sentiment_source_filter()
    if detection:
        st.sidebar.divider()
        _detection_filter(detection)
    if majority:
        st.sidebar.divider()
        _majority_filter()
    _keep(central)          # back up every central value after drawing: a page change can drop even the widgets the next page draws too
    return ticker, epoch(start_day), epoch(end_day, end_of_day=True), groups


def nothing_selected(labels, message="ไม่ได้เลือกแหล่งข้อมูลหรือหลักทรัพย์ จึงไม่มีข้อมูลแสดง"):
    """Cards at 0 and a short note, then stop the page: used when a filter has nothing ticked."""
    kpi_cards([(label, "0", None) for label in labels])
    st.info(message)
    st.stop()


def kpi_cards(items):
    """The KPI cards every page opens with, directly under the title: one bordered card per
    (label, value, help) or (label, value, help, delta)."""
    for cell, item in zip(st.columns(len(items)), items):
        label, value, help_text = item[:3]
        cell.metric(label, value, help=help_text, delta=item[3] if len(item) > 3 else None, delta_color="off", border=True)


# Time levels follow DimTime (Hour, Day, Week, Month, Year).  Each has the pandas rule that rolls hourly rows up to it.
GRANULARITY = {"รายชั่วโมง": "Hourly", "รายวัน": "Daily", "รายสัปดาห์": "Weekly", "รายเดือน": "Monthly",
               "รายปี": "Yearly"}
DEFAULT_LEVEL = "รายวัน"
CHART_KINDS = ["เส้น", "แท่ง"]
RESAMPLE = {"Daily": dict(rule="1D"), "Weekly": dict(rule="W-MON", label="left", closed="left"),   # ISO week starts Monday
            "Monthly": dict(rule="MS"), "Yearly": dict(rule="YS")}
PERIOD_LABEL = {"Hourly": "ชั่วโมง", "Daily": "วัน", "Weekly": "สัปดาห์", "Monthly": "เดือน", "Yearly": "ปี"}
DATE_TIP = {"Hourly": "%Y-%m-%d %H:00", "Daily": "%Y-%m-%d", "Weekly": "%Y-%m-%d", "Monthly": "%b %Y", "Yearly": "%Y"}
DATE_FORMAT = {"Hourly": "%d %b %H:%M", "Daily": "%d %b", "Weekly": "%d %b %y", "Monthly": "%b %Y", "Yearly": "%Y"}


def resample(df, rules, how="Daily"):
    """Roll hourly rows up to `how` (Daily/Weekly/Monthly/Yearly).  `rules` maps column -> 'sum' | 'max' | 'last' |
    'mean'.  NaN stays NaN."""
    if how == "Hourly" or df.empty:
        return df
    return df.set_index("time").resample(**RESAMPLE[how]).agg(rules).reset_index()


def granularity(start=None, end=None, key=None):
    """Time level chosen in the sidebar ('Hourly' ... 'Yearly').  The range never changes it (start/end/key are kept
    only for old callers): one rule, so every chart of every page looks the same."""
    return GRANULARITY.get(st.session_state.get("f_gran", DEFAULT_LEVEL), "Daily")


def kind(container, key):
    """Line / bar switch of ONE chart, drawn above it in `container` (st or a column); True = bars."""
    return container.radio("รูปแบบกราฟ", CHART_KINDS, horizontal=True, key="ck_" + key, label_visibility="collapsed") == "แท่ง"


def period_summary(daily, col, how):
    """One row per period (Weekly/Monthly/Yearly) from a DAILY frame (time, col; NaN = day without data, not a real 0):
    avg = mean per day over the days that have data (so periods of different length / partly covered ones compare),
    peak = the busiest day, peak_day, days = days with data.  Periods without any data are absent."""
    d = daily.set_index("time")[col].dropna()
    if d.empty:
        return pd.DataFrame(columns=["period", "avg", "peak", "peak_day", "days"])
    rule = dict(RESAMPLE[how])
    grp = d.groupby(pd.Grouper(freq=rule["rule"], **{k: v for k, v in rule.items() if k != "rule"}))
    out = pd.DataFrame({"avg": grp.mean(), "peak": grp.max(), "days": grp.count()})
    out["peak_day"] = grp.apply(lambda x: x.idxmax() if len(x) else pd.NaT)
    return out.dropna(subset=["avg"]).reset_index().rename(columns={"time": "period"})


TICK_STEP = {"Weekly": "week", "Monthly": "month", "Yearly": "year"}   # one x label per period, never repeated
TIME_UNIT = {"Hourly": "utcyearmonthdatehours", "Daily": "utcyearmonthdate", "Weekly": "utcyearmonthdate",
             "Monthly": "utcyearmonth", "Yearly": "utcyear"}     # gives every bar its own full-width slot (UTC)


def style(chart):
    """The look shared by every chart of the dashboards: light grid, grey axes, no frame, legend on top, one default height."""
    if getattr(chart, "height", alt.Undefined) is alt.Undefined:
        chart = chart.properties(height=CHART_HEIGHT)
    chart = chart.configure_axis(grid=True, gridColor="#e8e8e8", domainColor="#bbbbbb", tickColor="#bbbbbb", labelColor="#555555",
                                 titleColor="#555555", labelFontSize=11, titleFontSize=12, titleFontWeight="normal")
    chart = chart.configure_view(stroke=None)
    return chart.configure_legend(orient="top", labelFontSize=11, titleFontSize=11, symbolType="square")


def show(chart, **kwargs):
    """Draw a chart with the shared design (`style`), full width."""
    kwargs.setdefault("width", "stretch")
    return st.altair_chart(style(chart), **kwargs)


def zero_rule():
    """The solid grey line at 0 shared by the charts of returns, correlations and Z-scores."""
    return alt.Chart(alt.Data(values=[{"y": 0}])).mark_rule(color="#555555").encode(y="y:Q")


def zero_rule_x():
    """The solid grey vertical line at 0 (the same rule as `zero_rule`, for bars that go left and right)."""
    return alt.Chart(alt.Data(values=[{"x": 0}])).mark_rule(color="#555555").encode(x=alt.X("x:Q", scale=alt.Scale(nice=False)))


def ref_rule(*levels):
    """Dashed grey reference lines at the given levels (a threshold such as Z = 1.5, RSI 30 / 70, AUC 0.5)."""
    return alt.Chart(alt.Data(values=[{"y": v} for v in levels])).mark_rule(strokeDash=[4, 4], color="gray").encode(y="y:Q")


def series_chart(df, x, y, title, color, height, tooltip=None, fmt=None, peak=None, dots=False, y_zero=False, bar=False,
                 y_domain=None):
    """One time series as a line or as bars (`bar`, chosen with `kind`), x axis labelled for the chosen time level.
    `peak` = optional column holding a value that is on the SAME scale as `y` and higher (the busiest day of a month,
    next to the daily average): bars get a dark cap at that height.  `dots` = lines get dots that carry the tooltip
    (use it whenever the tooltip has a peak, also one that is not on the y scale, like the busiest hour of a day)."""
    how = granularity()
    fmt = fmt or DATE_FORMAT[how]
    tooltip = tooltip or [alt.Tooltip(x + ":T"), alt.Tooltip(y + ":Q", format=",.4g")]
    ticks = {"tickCount": TICK_STEP[how]} if how in TICK_STEP else {}
    axis = alt.Axis(format=fmt, labelOverlap=True, **ticks)
    axis_y = alt.Axis(minExtent=55)                     # same left margin on every chart, so stacked charts line up
    y_scale = alt.Scale(domain=y_domain) if y_domain else alt.Scale(zero=True) if y_zero else alt.Undefined
    if bar:
        size = {"size": 6} if how == "Weekly" else {}
        enc_x = alt.X(x + ":T", title=None, timeUnit=TIME_UNIT[how], axis=axis)
        layers = [alt.Chart(df).mark_bar(color=color, opacity=0.85, **size).encode(
            x=enc_x, y=alt.Y(y + ":Q", title=title, axis=axis_y, scale=y_scale), tooltip=tooltip)]
        if peak:
            mark = df.assign(_peak_lo=df[peak] - 0.012 * float(df[peak].max() or 1))     # a thin dark cap at the peak
            layers.append(alt.Chart(mark).mark_bar(color="#222222", **size).encode(
                x=enc_x, y=alt.Y(peak + ":Q"), y2="_peak_lo:Q", tooltip=tooltip))
    else:
        enc_x = alt.X(x + ":T", title=None, axis=axis)
        enc_y = alt.Y(y + ":Q", title=title, axis=axis_y, scale=y_scale)
        layers = [alt.Chart(df).mark_line(color=color).encode(x=enc_x, y=enc_y)]
        # the tooltip hangs on an invisible, larger circle over every point: point at any spot of the line and the values appear
        layers.append(alt.Chart(df).mark_circle(color=color, size=150, opacity=0).encode(x=enc_x, y=enc_y, tooltip=tooltip))
    return alt.layer(*layers).properties(height=CHART_HEIGHT)          # `height` is kept for old callers: every chart has one height


def daily_peak(hourly, col):
    """Busiest hour of every day: DataFrame(time = day, peak, peak_time)."""
    g = hourly.set_index("time")[col].groupby(pd.Grouper(freq="1D"))
    return pd.DataFrame({"peak": g.max(), "peak_time": g.apply(lambda s: s.idxmax() if s.notna().any() else pd.NaT)}
                        ).reset_index()


def count_chart(daily, hourly, col, title, color, how, height=210, bar=False):
    """A count over time at the chosen level, with the peak inside each point in the tooltip:
    * Hourly: the count per hour (no peak)
    * Daily: the count per day; peak = the busiest hour of the day
    * Weekly / Monthly / Yearly: the AVERAGE per day of the period (so partly covered periods and periods of different
      length compare); peak = the busiest day.
    `daily` has NaN on days without data (a gap, not 0)."""
    if how == "Hourly":
        return series_chart(hourly, "time", col, title, color, height, fmt=DATE_FORMAT["Hourly"], bar=bar)
    if how == "Daily":
        d = daily[["time", col]].merge(daily_peak(hourly, col), on="time", how="left")
        d[["peak", "peak_time"]] = d[["peak", "peak_time"]].where(d[col].notna())
        tip = [alt.Tooltip("time:T", title="วันที่", format="%Y-%m-%d"),
               alt.Tooltip(col + ":Q", title="จำนวนทั้งวัน", format=",.0f"),
               alt.Tooltip("peak:Q", title="ชั่วโมงที่สูงสุด", format=",.0f"),
               alt.Tooltip("peak_time:T", title="เวลา (UTC)", format="%H:%M")]
        return series_chart(d, "time", col, title, color, height, tooltip=tip, dots=True, bar=bar)
    m = period_summary(daily, col, how).rename(columns={"period": "time"})
    tip = [alt.Tooltip("time:T", title="เริ่มต้น" + PERIOD_LABEL[how], format="%Y-%m-%d"),
           alt.Tooltip("avg:Q", title="เฉลี่ยต่อวัน", format=",.0f"),
           alt.Tooltip("peak:Q", title="วันที่สูงสุด", format=",.0f"),
           alt.Tooltip("peak_day:T", title="วันที่", format="%Y-%m-%d"),
           alt.Tooltip("days:Q", title="จำนวนวันที่มีข้อมูล")]
    return series_chart(m, "time", "avg", title + " (เฉลี่ยต่อวัน)", color, height, tooltip=tip,
                        peak="peak", dots=True, bar=bar)


def count_caption(how):
    """What one point / bar of `count_chart` means (one fact per line, no separators)."""
    if how == "Hourly":
        return "ค่าที่แสดง = จำนวนต่อชั่วโมง"
    if how == "Daily":
        return "ค่าที่แสดง = จำนวนทั้งวัน  \nชี้เมาส์เพื่อดูชั่วโมงที่สูงสุดของวันนั้นและเวลา"
    unit = PERIOD_LABEL[how]
    text = "ค่าที่แสดง = ค่าเฉลี่ยต่อวันของ%s" % unit
    text += "  \nถ้าแสดงเป็นแท่ง ขีดดำบนแท่ง = วันที่สูงสุดของ%s" % unit
    return text + "  \nชี้เมาส์เพื่อดูค่าและวันที่"


def line(df, x, y, title, color=C_PRICE, height=CHART_HEIGHT, fmt=None, y_zero=False, dots=False, label=None, bar=False, y_domain=None):
    """One series as a line or bars (`bar`, chosen with `kind`) at the chosen time level.  `fmt` overrides the x label format."""
    tip = None
    if label:                                               # Thai tooltip: the period, then the value
        tip = [alt.Tooltip(x + ":T", title=PERIOD_LABEL[granularity()], format=DATE_TIP[granularity()]),
               alt.Tooltip(y + ":Q", title=label, format=",.2f")]
    return series_chart(df, x, y, title, color, height, tooltip=tip, fmt=fmt, y_zero=y_zero, dots=dots, bar=bar, y_domain=y_domain)


def multi_series_chart(df, x, y, series, title, height=CHART_HEIGHT, bar=False, fmt=None, log=False, y_domain=None):
    """Several series (one per value of column `series`) over time: lines, or stacked bars when `bar`.  `log` = logarithmic
    y axis (series of very different size), `y_domain` = fixed y range."""
    how = granularity()
    ticks = {"tickCount": TICK_STEP[how]} if how in TICK_STEP else {}
    axis = alt.Axis(format=fmt or DATE_FORMAT[how], labelOverlap=True, **ticks)
    tip = [alt.Tooltip(x + ":T", title=PERIOD_LABEL[how], format=DATE_TIP[how]), alt.Tooltip(series + ":N", title="หลักทรัพย์"),
           alt.Tooltip(y + ":Q", title=title, format=",.2f")]
    color = alt.Color(series + ":N", title="หลักทรัพย์")
    y_scale = alt.Scale(domain=y_domain) if y_domain else alt.Scale(type="log") if log else alt.Undefined
    if bar:
        chart = alt.Chart(df).mark_bar(opacity=0.9).encode(
            x=alt.X(x + ":T", title=None, timeUnit=TIME_UNIT[how], axis=axis),
            y=alt.Y(y + ":Q", title=title, stack=True, axis=alt.Axis(minExtent=55)), color=color, tooltip=tip)
    else:
        enc = dict(x=alt.X(x + ":T", title=None, axis=axis), y=alt.Y(y + ":Q", title=title, axis=alt.Axis(minExtent=55), scale=y_scale),
                   color=color)
        chart = alt.layer(alt.Chart(df).mark_line().encode(**enc),
                          alt.Chart(df).mark_circle(size=150, opacity=0).encode(tooltip=tip, **enc))
    return chart.properties(height=CHART_HEIGHT)


COLOR_NAMES = {C_PRICE: "น้ำเงิน", C_VOLUME: "เขียว", C_REDDIT: "ส้ม", C_Z: "แดง", C_SENT: "เขียวอมฟ้า", C_RATE: "ม่วง"}


def dual_axis(df, x, left, right, left_title, right_title, height=CHART_HEIGHT, left_color=C_PRICE, right_color=C_SENT,
              left_fmt=",.4g", right_fmt="+.3f", show_left=True, show_right=True):
    """Two lines with independent y axes (e.g. close price vs sentiment_mean); each axis is coloured like its line.
    `show_left` / `show_right` = False hides that line (and its axis).  Pointing at any point of a line shows that period with
    the values of the lines that are visible.  (Two bar series on one chart are unreadable, so there is no bar mode.)"""
    how = granularity()
    ticks = {"tickCount": TICK_STEP[how]} if how in TICK_STEP else {}
    enc_x = alt.X(x + ":T", title=None, axis=alt.Axis(format=DATE_FORMAT[how], labelOverlap=True, **ticks))
    sides = [s for s, on in (((left, left_title, left_color, left_fmt), show_left), ((right, right_title, right_color, right_fmt), show_right)) if on]
    tip = [alt.Tooltip(x + ":T", title=PERIOD_LABEL[how], format=DATE_TIP[how])] + [
        alt.Tooltip(col + ":Q", title=title, format=fmt) for col, title, _, fmt in sides]
    scale = alt.Scale(zero=False)
    layers = []
    for col, title, color, _ in sides:
        axis = alt.Axis(title=title, titleColor=color, labelColor=color, minExtent=55)
        layers.append(alt.Chart(df).mark_line(color=color, opacity=0.85).encode(x=enc_x, y=alt.Y(col + ":Q", axis=axis, scale=scale)))
        # an invisible, larger circle on every point carries the tooltip: point at any spot of a line and its values appear
        layers.append(alt.Chart(df).mark_circle(color=color, size=150, opacity=0).encode(
            x=enc_x, y=alt.Y(col + ":Q", axis=None, scale=scale), tooltip=tip))
    return alt.layer(*layers).resolve_scale(y="independent").properties(height=CHART_HEIGHT)


def dual_chart(df, x, left, right, left_title, right_title, key, left_name, right_name, left_color=C_PRICE, right_color=C_SENT, **kwargs):
    """`dual_axis` with one tick box per line drawn above it (untick a line to hide it and read the other one alone).
    `key` makes the widget keys unique per chart."""
    first, second, _ = st.columns([1, 1, 2])
    show_left = first.checkbox("%s (%s)" % (left_name, COLOR_NAMES.get(left_color, "")), value=True, key="dl_" + key)
    show_right = second.checkbox("%s (%s)" % (right_name, COLOR_NAMES.get(right_color, "")), value=True, key="dr_" + key)
    if not (show_left or show_right):
        st.info("ติ๊กแสดงอย่างน้อย 1 เส้น")
        return
    show(dual_axis(df, x, left, right, left_title, right_title, left_color=left_color, right_color=right_color,
                   show_left=show_left, show_right=show_right, **kwargs))


def table(df, **kwargs):
    """st.dataframe with thousands separators: integer columns, and decimal columns whose values reach 1,000+,
    are shown as 1,234,567.  Small decimals (p-value, ratios) keep their own digits."""
    config = {}
    for col in df.columns:
        s = df[col]
        if pd.api.types.is_bool_dtype(s) or not pd.api.types.is_numeric_dtype(s):
            continue
        if pd.api.types.is_integer_dtype(s) or (s.abs().max() >= 1000):
            config[col] = st.column_config.NumberColumn(format="localized")
    return st.dataframe(df, column_config=config, **kwargs)


def money(x):
    return "n/a" if pd.isna(x) else "{:,.2f}".format(x)
