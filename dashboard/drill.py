"""Drill-down along the dimensions of the proposal (figure 2-4 hierarchies, "from the largest to the smallest"):

    DimTime    Year > Month > Week > Day > Hour
    DimSource  Platform > Community > Content type (Post / Comment)
    DimTicker  Asset class > Ticker symbol

A drill-down shows ONE level at a time as a bar chart.  The user goes one level down by picking a bar in the box under
the chart, and back up with the breadcrumb buttons (`ทั้งหมด > 2025 > มี.ค.`).  The path is kept in session state, so it
survives the reruns Streamlit does; a path that no longer exists after the filters change is cut back automatically.
The pure helpers (`time_frame`, `level_totals`, `default_label`) have no Streamlit dependency and are unit tested.
"""

import datetime as dt

import altair as alt
import pandas as pd
import streamlit as st

TIME_LEVELS = [("year", "ปี"), ("month", "เดือน"), ("week", "สัปดาห์"), ("day", "วัน"), ("hour", "ชั่วโมง")]
SOURCE_LEVELS = [("platform", "แพลตฟอร์ม"), ("subreddit", "ชุมชน"), ("content_type", "ประเภทเนื้อหา")]
TICKER_LEVELS = [("big_group", "กลุ่มสินทรัพย์"), ("ticker", "สัญลักษณ์หลักทรัพย์")]
MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
WEEKDAYS = ["จ.", "อ.", "พ.", "พฤ.", "ศ.", "ส.", "อา."]
CONTENT_LABELS = {"Post": "โพสต์", "Comment": "ความคิดเห็น"}


def time_frame(df):
    """Add the DimTime levels to rows that carry `hour_utc`.  The week is the ISO week (DimTime.Week), the month the
    calendar month of the hour, so a week that spans two months appears under both with its own days only."""
    stamp = pd.to_datetime(df["hour_utc"], unit="s", utc=True)
    out = df.copy()
    out["year"] = stamp.dt.year
    out["month"] = stamp.dt.month
    out["week"] = stamp.dt.isocalendar().week.astype(int)
    out["day"] = stamp.dt.strftime("%Y-%m-%d")
    out["hour"] = stamp.dt.hour
    return out


def subset(frame, levels, path):
    """Rows under `path` (one value per level, from the top)."""
    rows = frame
    for (column, _), value in zip(levels, path):
        rows = rows[rows[column] == value]
    return rows


def level_totals(frame, levels, path, value="value"):
    """Sum of `value` per member of the level just below `path` -> DataFrame(<level column>, value)."""
    column = levels[len(path)][0]
    return subset(frame, levels, path).groupby(column, sort=True)[value].sum().reset_index()


def _short_day(day):
    date = dt.date.fromisoformat(day)
    return "%d %s" % (date.day, MONTHS[date.month - 1])


def default_label(column, value, rows):
    """Thai label of one member of a level; `rows` are the rows of that member's parent (week labels show its days)."""
    if column == "month":
        return MONTHS[int(value) - 1]
    if column == "week":
        days = rows.loc[rows["week"] == value, "day"]
        return "สัปดาห์ที่ %d (%s–%s)" % (value, _short_day(days.min()), _short_day(days.max()))
    if column == "day":
        return "%s (%s)" % (_short_day(value), WEEKDAYS[dt.date.fromisoformat(value).weekday()])
    if column == "hour":
        return "%02d:00" % int(value)
    if column == "content_type":
        return CONTENT_LABELS.get(value, str(value))
    return str(value)


def _go_up(state, depth):
    st.session_state[state] = list(st.session_state.get(state, []))[:depth]


def _go_down(state, pick):
    value = st.session_state.get(pick)
    if value is not None:
        st.session_state[state] = list(st.session_state.get(state, [])) + [value]
        st.session_state[pick] = None                       # the box is empty again for the next level


def drill(key, frame, levels, color, value_title, label_of=default_label, horizontal=False, by_value=False):
    """Draw one drill-down.  `frame` holds one row per finest member with the level columns and `value` (summed)."""
    if frame.empty:
        st.info("ไม่มีข้อมูลในช่วงและตัวกรองที่เลือก")
        return
    state = key + "_path"
    path, rows, crumbs = [], frame, ["ทั้งหมด"]
    for (column, _), value in zip(levels[:-1], st.session_state.get(state, [])):   # cut a stale path
        below = rows[rows[column] == value]
        if below.empty:
            break
        crumbs.append(label_of(column, value, rows))
        path.append(value)
        rows = below
    st.session_state[state] = path

    spacer = max(1, 7 - len(crumbs))
    cells = st.columns([1] * len(crumbs) + [spacer])
    for depth, (cell, text) in enumerate(zip(cells, crumbs)):
        if depth == len(crumbs) - 1:
            cell.markdown("**%s**" % text)
        else:
            cell.button(text + " ›", key="%s_crumb_%d" % (key, depth), on_click=_go_up, args=(state, depth))

    column, name = levels[len(path)]
    agg = level_totals(frame, levels, path)
    agg["label"] = [label_of(column, v, rows) for v in agg[column]]
    agg["share"] = 100.0 * agg["value"] / agg["value"].sum() if agg["value"].sum() else 0.0
    if by_value:
        agg = agg.sort_values("value", ascending=False)
    order = list(agg["label"])
    tip = [alt.Tooltip("label:N", title=name), alt.Tooltip("value:Q", title=value_title, format=",.0f"),
           alt.Tooltip("share:Q", title="% ของระดับนี้", format=".1f")]
    if horizontal:
        chart = alt.Chart(agg).mark_bar(color=color).encode(
            y=alt.Y("label:N", sort=order, title=None, axis=alt.Axis(labelOverlap=False)),
            x=alt.X("value:Q", title=value_title), tooltip=tip).properties(height=max(120, 26 * len(agg)))
    else:
        chart = alt.Chart(agg).mark_bar(color=color).encode(
            x=alt.X("label:N", sort=order, title=name, axis=alt.Axis(labelAngle=-35, labelOverlap=False)),
            y=alt.Y("value:Q", title=value_title), tooltip=tip).properties(height=260)
    st.altair_chart(chart, width="stretch")

    if len(path) < len(levels) - 1:
        pick = "%s_pick_%d" % (key, len(path))
        labels = dict(zip(agg[column].tolist(), agg["label"]))
        st.selectbox("เลือก%sเพื่อลงไปดู%s" % (name, levels[len(path) + 1][1]), agg[column].tolist(), index=None,
                     placeholder="เลือกจากรายการเพื่อลงต่อ", format_func=lambda v: labels[v], key=pick,
                     on_change=_go_down, args=(state, pick))
    else:
        st.caption("ถึงระดับล่างสุดแล้ว (%s) กดปุ่มข้างบนเพื่อย้อนกลับ" % name)
