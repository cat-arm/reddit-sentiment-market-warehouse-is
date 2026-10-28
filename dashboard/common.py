"""Shared pieces of the dashboard pages (TASKS D0): path setup, cached queries, the central sidebar filter, charts.

Run:   streamlit run dashboard/app.py          (from the project root)
Pages: dashboard/pages/*.py  (Streamlit builds the menu from the file names)

Central filter (identical on every page: same widgets, same order, same fixed keys, so a choice made on one page
holds on all of them):
  The sidebar follows the three dimensions of the proposal, each one a hierarchy, time first:
    time      DimTime    year > month > week > day (each level appears after the one above), date range, chart level
    source    DimSource  platform (Reddit) > communities > Post / Comment      (pages 1-2 only)
    asset     DimTicker  asset class (Big_Group) > ticker                      (every page except Reddit Volume)
  Choosing a level of the time hierarchy sets the date range of the WHOLE page (a drill-down by filter) and a finer chart
  level; editing the date range by hand clears the hierarchy.  The default range is the LAST YEAR of the data.  Times are
  UTC.  Rule: a central widget that a page does not draw is kept in a shadow key, because Streamlit forgets it otherwise.
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
DEFAULT_TICKER = "SPY"
SOURCE_KEYS = ["f_comm", "f_type_Post", "f_type_Comment"]
TIME_KEYS = ["f_year", "f_month", "f_week", "f_day"]            # the time hierarchy, top to bottom
DEFAULT_RANGE_DAYS = 365
MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
WEEKDAYS = ["จ.", "อ.", "พ.", "พฤ.", "ศ.", "ส.", "อา."]


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
    """Bring back values that a page without those widgets had dropped (see `_keep`)."""
    for key in keys:
        if key not in st.session_state and ("_keep_" + key) in st.session_state:
            st.session_state[key] = st.session_state["_keep_" + key]


def _keep(keys):
    for key in keys:
        if key in st.session_state:
            st.session_state["_keep_" + key] = st.session_state[key]


def selected_sources():
    """DimSource ids kept by the sidebar source filter (communities x Post / Comment); nothing ticked = everything."""
    src = q("sources")
    communities = st.session_state.get("f_comm") or list(dict.fromkeys(src.subreddit))
    types = [kind for kind in ("Post", "Comment") if st.session_state.get("f_type_" + kind, True)] or ["Post", "Comment"]
    keep = src[src.subreddit.isin(communities) & src.content_type.isin(types)]
    return tuple(int(i) for i in keep.source_id)


def source_summary():
    """One line for the page: which sources are shown."""
    src = q("sources")
    ids = selected_sources()
    if len(ids) == len(src):
        return "แหล่งข้อมูล: ทุกชุมชน ทั้งโพสต์และความคิดเห็น"
    keep = src[src.source_id.isin(ids)]
    return "แหล่งข้อมูล: %s (%s)" % (", ".join(dict.fromkeys(keep.subreddit)),
                                    " + ".join(CONTENT_NAMES[k] for k in dict.fromkeys(keep.content_type)))


CONTENT_NAMES = {"Post": "โพสต์", "Comment": "ความคิดเห็น"}


def _source_filter():
    """The DimSource part of the sidebar: platform (fixed: Reddit) > communities > content type."""
    src = q("sources")
    communities = list(dict.fromkeys(src.subreddit))
    st.sidebar.write("แหล่งข้อมูล (DimSource)")
    st.sidebar.caption("แพลตฟอร์ม: Reddit")
    st.session_state.setdefault("f_comm", communities)
    st.session_state.setdefault("f_type_Post", True)
    st.session_state.setdefault("f_type_Comment", True)
    st.sidebar.multiselect("ชุมชน", communities, key="f_comm", help="เลือกได้หลายชุมชน ไม่เลือกเลย = ทุกชุมชน")
    st.sidebar.checkbox("โพสต์ (Post)", key="f_type_Post")
    st.sidebar.checkbox("ความคิดเห็น (Comment)", key="f_type_Comment")
    if not st.session_state["f_comm"] or not (st.session_state["f_type_Post"] or st.session_state["f_type_Comment"]):
        st.sidebar.caption("ไม่ได้เลือกชุมชนหรือประเภท จึงแสดงทั้งหมด")


# ------------------------------------------------------------------------------------------------ time hierarchy
def _data_dates():
    info = q("data_range")
    lo = dt.datetime.fromtimestamp(info["market_lo"], dt.timezone.utc).date()
    hi = dt.datetime.fromtimestamp(info["reddit_hi"], dt.timezone.utc).date()
    return info, lo, hi


def days_of_month(year, month, lo, hi):
    """Dates of the month that lie inside the data (lo..hi)."""
    first = dt.date(year, month, 1)
    last = (first.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
    a, b = max(first, lo), min(last, hi)
    return [a + dt.timedelta(days=i) for i in range((b - a).days + 1)] if a <= b else []


def week_days(year, month, week, lo, hi):
    """Days of ISO week `week` that belong to the month (a week spanning two months is split, like DimTime.Month)."""
    return [d for d in days_of_month(year, month, lo, hi) if d.isocalendar()[1] == week]


def cascade_range(year, month, week, day, lo, hi):
    """(first, last) date chosen by the Year > Month > Week > Day filters, clipped to the data; None = nothing chosen."""
    if year is None:
        return None
    if month is None:
        first, last = dt.date(year, 1, 1), dt.date(year, 12, 31)
    else:
        days = days_of_month(year, month, lo, hi) if week is None else week_days(year, month, week, lo, hi)
        if not days:
            return None
        first, last = days[0], days[-1]
        if day is not None:
            first = last = dt.date.fromisoformat(day)
    return max(first, lo), min(last, hi)


def _week_label(days):
    first, last = days[0], days[-1]
    return "สัปดาห์ที่ %d (%d %s–%d %s)" % (first.isocalendar()[1], first.day, MONTHS[first.month - 1], last.day, MONTHS[last.month - 1])


LEVEL_GRANULARITY = {0: "รายเดือน", 1: "รายวัน", 2: "รายวัน", 3: "รายชั่วโมง"}      # the chart level that suits each depth


def _time_changed(level):
    """Callback of the Year / Month / Week / Day boxes: clear the levels below, set the date range of the page and a
    chart level that suits the depth."""
    state = st.session_state
    depth = TIME_KEYS.index(level)
    for key in TIME_KEYS[depth + 1:]:
        state[key] = None
    _, lo, hi = _data_dates()
    chosen = cascade_range(*(state.get(k) for k in TIME_KEYS), lo, hi)
    deepest = max((i for i, k in enumerate(TIME_KEYS) if state.get(k) is not None), default=None)
    state["f_range"] = chosen if chosen else (max(lo, hi - dt.timedelta(days=DEFAULT_RANGE_DAYS)), hi)
    state["f_gran"] = LEVEL_GRANULARITY[deepest] if deepest is not None else DEFAULT_LEVEL


def _range_edited():
    """Callback of the manual date range: the hierarchy no longer describes it, so clear it."""
    for key in TIME_KEYS:
        st.session_state[key] = None


def _time_filter(info):
    """DimTime part of the sidebar: Year > Month > Week > Day, then a free date range and the chart level.
    Returns the chosen (start_day, end_day)."""
    _, lo, hi = _data_dates()
    state = st.session_state
    st.sidebar.write("เวลา (DimTime)")
    for key in TIME_KEYS:
        state.setdefault(key, None)
    all_label = lambda v, name=None: "ทั้งหมด" if v is None else (name(v) if name else str(v))      # noqa: E731
    st.sidebar.selectbox("ปี", [None] + list(range(lo.year, hi.year + 1)), key="f_year", format_func=all_label,
                         on_change=_time_changed, args=("f_year",),
                         help="เลือกปี แล้วจะเลือกเดือน สัปดาห์ วัน ต่อลงไปได้ ทั้งหน้าจะแสดงเฉพาะช่วงที่เลือก")
    year = state["f_year"]
    if year is not None:
        months = [None] + [m for m in range(1, 13) if days_of_month(year, m, lo, hi)]
        st.sidebar.selectbox("เดือน", months, key="f_month", on_change=_time_changed, args=("f_month",),
                             format_func=lambda v: all_label(v, lambda m: MONTHS[m - 1]))
        month = state["f_month"]
        if month is not None:
            weeks = list(dict.fromkeys(d.isocalendar()[1] for d in days_of_month(year, month, lo, hi)))
            st.sidebar.selectbox("สัปดาห์", [None] + weeks, key="f_week", on_change=_time_changed, args=("f_week",),
                                 format_func=lambda v: all_label(v, lambda w: _week_label(week_days(year, month, w, lo, hi))))
            week = state["f_week"]
            if week is not None:
                days = [d.isoformat() for d in week_days(year, month, week, lo, hi)]
                st.sidebar.selectbox("วัน", [None] + days, key="f_day", on_change=_time_changed, args=("f_day",),
                                     format_func=lambda v: all_label(v, lambda d: "%d %s (%s)" % (
                                         dt.date.fromisoformat(d).day, MONTHS[dt.date.fromisoformat(d).month - 1],
                                         WEEKDAYS[dt.date.fromisoformat(d).weekday()])))
    state.setdefault("f_range", (max(lo, hi - dt.timedelta(days=DEFAULT_RANGE_DAYS)), hi))     # no `value=`: the key carries it
    state.setdefault("f_gran", DEFAULT_LEVEL)
    stored = state["f_range"]                                       # a stale range outside the data would make the box fail
    given = list(stored) if isinstance(stored, (tuple, list)) else [stored]
    clipped = tuple(min(max(d, lo), hi) for d in given)
    if tuple(given) != clipped:
        state["f_range"] = clipped
    picked = st.sidebar.date_input("กำหนดช่วงเอง (UTC)", min_value=lo, max_value=hi, key="f_range",
                                   format="YYYY/MM/DD", on_change=_range_edited,
                                   help="พิมพ์วันที่ในช่องได้โดยตรง (ปี/เดือน/วัน) หรือคลิกจากปฏิทิน การแก้ช่วงเองจะล้างตัวเลือกปี/เดือน/สัปดาห์/วัน")
    # While the user is still choosing, Streamlit returns only ONE date (a tuple of length 1): treat it as that single
    # day until the second date is clicked, so the page never breaks halfway through a selection.
    days = list(picked) if isinstance(picked, (tuple, list)) else [picked]
    start_day, end_day = (days[0], days[1]) if len(days) >= 2 else (days[0], days[0])
    if len(days) < 2:
        st.sidebar.caption("เลือกวันเดียวอยู่: ดูเฉพาะวันนี้ จนกว่าจะคลิกวันสุดท้ายของช่วง")
    st.sidebar.caption("ข้อมูล Reddit: %s → %s" % (dt.datetime.fromtimestamp(info["reddit_lo"], dt.timezone.utc).date(), hi))
    st.sidebar.selectbox("ความละเอียดของกราฟ", list(GRANULARITY), key="f_gran",
                         help="ระดับเวลาของ DimTime: ชั่วโมง วัน สัปดาห์ เดือน ปี (รายชั่วโมงในช่วงยาวมากอาจโหลดช้า) "
                              "เมื่อเลือกปี/เดือน/วัน ระบบเปลี่ยนให้เหมาะกับระดับนั้น แก้เองได้")
    return start_day, end_day


def sidebar(need_ticker=True, assets=True, sources=False):
    """Draw the central filter (time first, then source, then asset); returns (ticker or None, start_epoch, end_epoch,
    groups).  assets=False: the asset-class boxes and the ticker box are NOT drawn and all classes are used.
    sources=True: the source filter is drawn too (read it with `selected_sources()`).
    Streamlit would forget the values of widgets a page does not draw, so they are kept in shadow keys and restored on
    the next page that draws them."""
    info = q("data_range")
    universe = q("tickers")
    st.sidebar.header("ตัวกรองกลาง")
    asset_keys = ["f_ticker"] + ["f_group_" + k for k in GROUP_LABELS]
    _restore(asset_keys + SOURCE_KEYS)
    if not sources:
        _keep(SOURCE_KEYS)
    if not assets:
        _keep(asset_keys)
    start_day, end_day = _time_filter(info)
    st.sidebar.divider()
    if sources:
        _source_filter()
        st.sidebar.divider()
    ticker, groups = None, list(GROUP_LABELS)
    if assets:
        # One tick box per asset class (instead of a multiselect whose chips are all the same colour): the coloured dot
        # is the colour this class has in every chart.
        st.sidebar.write("หลักทรัพย์ (DimTicker)")
        groups = [key for key in GROUP_LABELS
                  if st.sidebar.checkbox(GROUP_DOTS[key] + " " + GROUP_LABELS[key], value=True, key="f_group_" + key)]
        if not groups:                                      # nothing ticked would empty every page: use all
            st.sidebar.caption("ไม่ได้เลือกกลุ่มใดเลย จึงแสดงทุกกลุ่ม")
            groups = list(GROUP_LABELS)
        pool = universe[universe.big_group.isin(groups)]
        # The ticker box is drawn on EVERY page that draws the asset filter, even where the page does not use it (home,
        # ranking): a widget that is not drawn on a page loses its value in Streamlit.
        options = list(pool.ticker)                         # already ordered stocks/ETF, futures, crypto
        default = DEFAULT_TICKER if DEFAULT_TICKER in options else options[0]
        if st.session_state.get("f_ticker") not in options:   # the old choice may have left the chosen groups
            st.session_state["f_ticker"] = default
        kind_of = dict(zip(universe.ticker, universe.big_group))
        name = dict(zip(universe.ticker, universe.name))
        ticker = st.sidebar.selectbox("สินทรัพย์ (Ticker)", options, key="f_ticker",
                                      format_func=lambda t: "%s %s · %s  (%s)" % (GROUP_DOTS[kind_of[t]], t, name[t], GROUP_LABELS[kind_of[t]]))
        if not need_ticker:
            st.sidebar.caption("หน้านี้แสดงทุกสินทรัพย์ จึงไม่ใช้ช่อง Ticker (ค่ายังถูกจำไว้สำหรับหน้าอื่น)")
        st.sidebar.divider()
    else:
        st.sidebar.caption("หน้านี้นับข้อความทั้งหมด ไม่เกี่ยวกับสินทรัพย์ จึงไม่มีตัวกรองสินทรัพย์")
    if not sources:
        st.sidebar.caption("ตัวกรองชุมชนและประเภท (โพสต์/ความคิดเห็น) ใช้เฉพาะหน้า Reddit Volume และ Ticker Mentions")
    return ticker, epoch(start_day), epoch(end_day, end_of_day=True), groups


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


def series_chart(df, x, y, title, color, height, tooltip=None, fmt=None, peak=None, dots=False, y_zero=False, bar=False):
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
    if bar:
        size = {"size": 6} if how == "Weekly" else {}
        enc_x = alt.X(x + ":T", title=None, timeUnit=TIME_UNIT[how], axis=axis)
        layers = [alt.Chart(df).mark_bar(color=color, opacity=0.85, **size).encode(
            x=enc_x, y=alt.Y(y + ":Q", title=title, axis=axis_y, scale=alt.Scale(zero=y_zero) if y_zero else alt.Undefined), tooltip=tooltip)]
        if peak:
            mark = df.assign(_peak_lo=df[peak] - 0.012 * float(df[peak].max() or 1))     # a thin dark cap at the peak
            layers.append(alt.Chart(mark).mark_bar(color="#222222", **size).encode(
                x=enc_x, y=alt.Y(peak + ":Q"), y2="_peak_lo:Q", tooltip=tooltip))
    else:
        enc_x = alt.X(x + ":T", title=None, axis=axis)
        enc_y = alt.Y(y + ":Q", title=title, axis=axis_y, scale=alt.Scale(zero=y_zero) if y_zero else alt.Undefined)
        layers = [alt.Chart(df).mark_line(color=color).encode(x=enc_x, y=enc_y, tooltip=tooltip)]
        if dots:                                           # dots carry the tooltip with the peak
            hover = alt.selection_point(nearest=True, on="mouseover", empty=False, clear="mouseout", fields=[x])
            layers.append(alt.Chart(df).mark_circle(color=color).encode(
                x=enc_x, y=enc_y, tooltip=tooltip,
                size=alt.condition(hover, alt.value(150), alt.value(22)),            # the hovered point swells
                stroke=alt.condition(hover, alt.value("white"), alt.value(None)),
                strokeWidth=alt.value(2)).add_params(hover))
    return alt.layer(*layers).properties(height=height).interactive()


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


def line(df, x, y, title, color="#1f77b4", height=260, fmt=None, y_zero=False, dots=False, label=None, bar=False):
    """One series as a line or bars (`bar`, chosen with `kind`) at the chosen time level.  `fmt` overrides the x label format."""
    tip = None
    if label:                                               # Thai tooltip: the period, then the value
        tip = [alt.Tooltip(x + ":T", title=PERIOD_LABEL[granularity()], format=DATE_TIP[granularity()]),
               alt.Tooltip(y + ":Q", title=label, format=",.2f")]
    return series_chart(df, x, y, title, color, height, tooltip=tip, fmt=fmt, y_zero=y_zero, dots=dots, bar=bar)


def dual_axis(df, x, left, right, left_title, right_title, height=300):
    """Two series with independent y axes (e.g. close price vs sentiment_mean)."""
    base = alt.Chart(df).encode(x=alt.X(x + ":T", title=None))
    a = base.mark_line(color="#1f77b4").encode(
        y=alt.Y(left + ":Q", title=left_title, scale=alt.Scale(zero=False)),
        tooltip=[alt.Tooltip(x + ":T"), alt.Tooltip(left + ":Q", format=",.4g")])
    b = base.mark_line(color="#d62728", opacity=0.8).encode(
        y=alt.Y(right + ":Q", title=right_title), tooltip=[alt.Tooltip(right + ":Q", format=",.3f")])
    return alt.layer(a, b).resolve_scale(y="independent").properties(height=height).interactive()


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
