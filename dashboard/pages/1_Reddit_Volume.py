"""Dashboard 7.1-1  Reddit Volume  (proposal 7.1: Reddit_volume, Volume Z-score).

Reddit_volume = ALL posts and comments of the 6 communities per hour.  No asset is involved, so this page has NO asset
filter; how often each asset is mentioned (Ticker_mention_count) is on the next page.  The sidebar holds the time
hierarchy (year > month > week > day) and the source filter (communities, Post / Comment).
Data: reddit_volume_hourly (totals), reddit_hourly_features (stored Z-score of the all-source total).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard import common  # noqa: E402
from dashboard.common import q  # noqa: E402

common.setup("Reddit Volume: ปริมาณโพสต์และความคิดเห็น", "💬")
_, start, end, _ = common.sidebar(assets=False, sources=True)
how = common.granularity(start, end)
src_ids = common.selected_sources()
st.caption(common.source_summary())

total = q("total_volume_series", start, end, src_ids)
if total.empty:
    st.warning("ไม่มีข้อมูล Reddit ในช่วงนี้")
    st.stop()
# a missing hour means "no texts", which is a real 0 for a count (unlike sentiment, where it is unknown)
full = pd.DataFrame({"time": pd.date_range(total.time.min(), total.time.max(), freq="h")})
total = full.merge(total, on="time", how="left").fillna({"posts": 0, "comments": 0, "texts": 0})
shown = common.resample(total, {"posts": "sum", "comments": "sum", "texts": "sum", "zscore": "max"}, how)

# KPIs of proposal 7.1: Reddit_volume (total, per hour, busiest hour) and Volume Z-score (peak, spike hours)
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Reddit Volume รวม", "{:,}".format(int(total.texts.sum())), help="โพสต์ + ความคิดเห็น")
k2.metric("เฉลี่ยต่อชั่วโมง", "{:,.0f}".format(total.texts.mean()))
k3.metric("ชั่วโมงที่คึกคักสุด", "{:,}".format(int(total.texts.max())),
          help=str(total.loc[total.texts.idxmax(), "time"])[:16] + " UTC")
k4.metric("Reddit Volume Z-score สูงสุด", common.money(total.zscore.max()),
          help="Z-score ของชั่วโมงที่คึกคักผิดปกติที่สุดในช่วงที่เลือก: สูงกว่าค่าเฉลี่ยของ 24 ชั่วโมงก่อนหน้ากี่เท่าของส่วนเบี่ยงเบนมาตรฐาน")
k5.metric("ชั่วโมงที่ Z-score > 1.5", "{:,}".format(int((total.zscore > 1.5).sum())),
          help="spike = ชั่วโมงที่ปริมาณสูงกว่าค่าเฉลี่ยของ 24 ชั่วโมงก่อนหน้า เกิน 1.5 เท่าของส่วนเบี่ยงเบนมาตรฐาน (เกณฑ์ 1.5 ตาม proposal)")

# Comments and posts are two charts one above the other (no dual axis: posts are only ~1 % of the texts, so a shared
# axis hides them and two axes make the lines cross meaninglessly).  A day without any text in the six communities is
# a data gap and is drawn as a gap, not as 0.
daily = common.resample(total, {"posts": "sum", "comments": "sum", "texts": "sum"}, "Daily")
daily[["posts", "comments"]] = daily[["posts", "comments"]].where(daily.texts > 0)
hourly = total
st.altair_chart(common.count_chart(daily, hourly, "comments", "ความคิดเห็น", "#1f77b4", how, bar=common.kind(st, "v_comments")), width="stretch")
st.altair_chart(common.count_chart(daily, hourly, "posts", "โพสต์", "#ff7f0e", how, 160, bar=common.kind(st, "v_posts")), width="stretch")
st.caption(common.count_caption(how))

# Z-score of the hourly volume; for day / week / month / year each point is the HIGHEST hourly Z-score of that period
z = common.line(shown, "time", "zscore", "Volume Z-score" + ("" if how == "Hourly" else " (สูงสุดของ%s)" % common.PERIOD_LABEL[how]),
                "#d62728", 200, dots=how != "Hourly", label="Z-score สูงสุด", bar=common.kind(st, "v_z"))
zero = alt.Chart(alt.Data(values=[{"y": 0}])).mark_rule(color="#555555").encode(y="y:Q")       # Z = 0: normal volume
rule = alt.Chart(alt.Data(values=[{"y": 1.5}])).mark_rule(strokeDash=[4, 4], color="gray").encode(y="y:Q")
st.altair_chart(z + zero + rule, width="stretch")
st.caption("เส้นแดง = Z-score ของปริมาณ เทียบกับ 24 ชั่วโมงก่อนหน้า" + ("" if how == "Hourly" else "  \nค่าของแต่ละจุด = ชั่วโมงที่สูงที่สุดในช่วงนั้น") + "  \n"
           "เส้นทึบเทา = ระดับ 0 (ปริมาณปกติ)  \n"
           "เส้นประ = ระดับ 1.5 ถ้าเส้นแดงอยู่เหนือเส้นนี้ ถือว่าคึกคักผิดปกติ (spike)")

by_source = q("total_volume_by_source", start, end, src_ids)
pivot = by_source.pivot_table(index="subreddit", columns="content_type", values="texts", aggfunc="sum").fillna(0)
pivot["รวม"] = pivot.sum(axis=1)
st.subheader("แยกตามชุมชน")
common.table(pivot.sort_values("รวม", ascending=False).astype(int).rename(
    columns={"Comment": "ความคิดเห็น", "Post": "โพสต์"}), width="stretch")
