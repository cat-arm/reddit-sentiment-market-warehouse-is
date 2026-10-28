"""Dashboard 7.1-1  Reddit Volume  (proposal 7.1: Reddit_volume, Volume Z-score).

Reddit_volume = ALL posts and comments of the 6 communities per hour (the default view).  The central filter has the
three dimensions of the proposal: time (range + level), source (communities, Post / Comment) and asset.  The asset
only matters in the second view "only what mentions <ticker>" (Ticker_mention_count of FactRedditVolume).
Below the charts a drill-down goes down the DimTime and DimSource hierarchies level by level.
Data: reddit_volume_hourly (totals), FactRedditVolume (per ticker), reddit_hourly_features (stored Z-score).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard import common, drill  # noqa: E402
from dashboard.common import q  # noqa: E402

common.setup("Reddit Volume: ปริมาณโพสต์และความคิดเห็น", "💬")
ticker, start, end, _ = common.sidebar(sources=True)
how = common.granularity(start, end)
src_ids = common.selected_sources()
st.caption(common.source_summary())

scope = st.radio("ดูปริมาณของ", ["total", "ticker"], horizontal=True, key="v_scope",
                 format_func=lambda s: "ทั้ง Reddit" if s == "total" else "เฉพาะข้อความที่พูดถึง %s" % ticker)
everything = q("total_volume_series", start, end, src_ids)      # all texts of the chosen sources (also the base of the rate)
if everything.empty:
    st.warning("ไม่มีข้อมูล Reddit ในช่วงนี้")
    st.stop()
if scope == "total":
    total = everything
    noun, count_name = "ข้อความ", "Reddit Volume"
else:
    # Ticker_mention_count split by Post / Comment; the Z-score follows the rule of `data.ticker_zscore`
    mentions = q("ticker_volume_series", ticker, start, end, src_ids).rename(columns={"mentions": "texts"})
    z = q("ticker_zscore", ticker, start, end, src_ids)[["hour_utc", "zscore", "basis"]]
    total = mentions.drop(columns="time").merge(z, on="hour_utc", how="outer").assign(
        time=lambda d: pd.to_datetime(d.hour_utc, unit="s", utc=True)).sort_values("time")
    noun, count_name = "การพูดถึง", "Ticker Mention Count"
    st.info("แสดงเฉพาะที่พูดถึง **%s**: นับ**จำนวนครั้งที่ถูกพูดถึง** (Ticker_mention_count) ข้อความเดียวที่พูดถึงหลายครั้งนับหลายครั้ง "
            "สัดส่วนเทียบกับข้อความทั้งหมดของแหล่งข้อมูลที่เลือกแสดงที่ตัวเลขด้านล่าง" % ticker)
# a missing hour means "no texts", which is a real 0 for a count (unlike sentiment, where it is unknown)
full = pd.DataFrame({"time": pd.date_range(everything.time.min(), everything.time.max(), freq="h")})
total = full.merge(total, on="time", how="left").fillna({"posts": 0, "comments": 0, "texts": 0})
shown = common.resample(total, {"posts": "sum", "comments": "sum", "texts": "sum", "zscore": "max"}, how)

# KPIs of proposal 7.1: Reddit_volume (total, per hour, busiest hour) and Volume Z-score (peak, spike hours)
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric(count_name + " รวม", "{:,}".format(int(total.texts.sum())),
          help="โพสต์ + ความคิดเห็น" if scope == "total" else "จำนวนครั้งที่ %s ถูกพูดถึงในแหล่งข้อมูลที่เลือก" % ticker)
k2.metric("เฉลี่ยต่อชั่วโมง", "{:,.0f}".format(total.texts.mean()))
k3.metric("ชั่วโมงที่คึกคักสุด", "{:,}".format(int(total.texts.max())),
          help=str(total.loc[total.texts.idxmax(), "time"])[:16] + " UTC")
k4.metric("Reddit Volume Z-score สูงสุด" if scope == "total" else "Volume Z-score ของ %s สูงสุด" % ticker, common.money(total.zscore.max()),
          help="Z-score ของชั่วโมงที่คึกคักผิดปกติที่สุดในช่วงที่เลือก: สูงกว่าค่าเฉลี่ยของ 24 ชั่วโมงก่อนหน้ากี่เท่าของส่วนเบี่ยงเบนมาตรฐาน")
k5.metric("ชั่วโมงที่ Z-score > 1.5", "{:,}".format(int((total.zscore > 1.5).sum())),
          help="spike = ชั่วโมงที่ปริมาณสูงกว่าค่าเฉลี่ยของ 24 ชั่วโมงก่อนหน้า เกิน 1.5 เท่าของส่วนเบี่ยงเบนมาตรฐาน (เกณฑ์ 1.5 ตาม proposal)")
if scope == "ticker":
    base = float(everything.texts.sum())
    st.metric("สัดส่วนเทียบข้อความทั้งหมดของแหล่งข้อมูลที่เลือก (Ticker Mention Rate %)",
              "n/a" if not base else "{:.3f}".format(100.0 * total.texts.sum() / base),
              help="Ticker Mention Count ÷ ปริมาณโพสต์และความคิดเห็นทั้งหมดของแหล่งข้อมูลเดียวกัน × 100")
    basis = total["basis"].dropna()
    st.caption("Z-score ของ %s คำนวณจาก%s" % (ticker, "จำนวนข้อความที่พูดถึงสินทรัพย์ (ค่าที่เก็บไว้ ใช้ใน panel_Ticker_spike)"
                                               if basis.empty or basis.iloc[0] == "texts" else
                                               "จำนวนครั้งที่ถูกพูดถึงในแหล่งข้อมูลที่เลือก (กฎเดียวกัน: เทียบ 24 ชั่วโมงก่อนหน้า) เพราะไม่ได้เก็บจำนวนข้อความต่อแหล่งข้อมูล"))

# Comments and posts are two charts one above the other (no dual axis: posts are only ~1 % of the texts, so a shared
# axis hides them and two axes make the lines cross meaninglessly).  A day without any text in the six communities is
# a data gap and is drawn as a gap, not as 0.
daily = common.resample(total, {"posts": "sum", "comments": "sum", "texts": "sum"}, "Daily")
daily[["posts", "comments"]] = daily[["posts", "comments"]].where(daily.texts > 0)
hourly = total
st.altair_chart(common.count_chart(daily, hourly, "comments", "ความคิดเห็น" if scope == "total" else "พูดถึงในความคิดเห็น", "#1f77b4", how), width="stretch")
st.altair_chart(common.count_chart(daily, hourly, "posts", "โพสต์" if scope == "total" else "พูดถึงในโพสต์", "#ff7f0e", how, 160), width="stretch")
st.caption(common.count_caption(how))

# Z-score of the hourly volume; for day / week / month / year each point is the HIGHEST hourly Z-score of that period
z = common.line(shown, "time", "zscore", ("Volume Z-score" if scope == "total" else "Volume Z-score ของ " + ticker) + ("" if how == "Hourly" else " (สูงสุดของ%s)" % common.PERIOD_LABEL[how]),
                "#d62728", 200, dots=how != "Hourly", label="Z-score สูงสุด")
zero = alt.Chart(alt.Data(values=[{"y": 0}])).mark_rule(color="#555555").encode(y="y:Q")       # Z = 0: normal volume
rule = alt.Chart(alt.Data(values=[{"y": 1.5}])).mark_rule(strokeDash=[4, 4], color="gray").encode(y="y:Q")
st.altair_chart(z + zero + rule, width="stretch")
st.caption("เส้นแดง = Z-score ของปริมาณ เทียบกับ 24 ชั่วโมงก่อนหน้า" + ("" if how == "Hourly" else "  \nค่าของแต่ละจุด = ชั่วโมงที่สูงที่สุดในช่วงนั้น") + "  \n"
           "เส้นทึบเทา = ระดับ 0 (ปริมาณปกติ)  \n"
           "เส้นประ = ระดับ 1.5 ถ้าเส้นแดงอยู่เหนือเส้นนี้ ถือว่าคึกคักผิดปกติ (spike)")

if scope == "total":
    by_source = q("total_volume_by_source", start, end, src_ids)
    subtitle = "แยกตามชุมชน"
else:
    by_source = q("volume_by_source", ticker, start, end, src_ids).rename(columns={"mentions": "texts"})
    subtitle = "แยกตามชุมชน (จำนวนครั้งที่ %s ถูกพูดถึง)" % ticker
pivot = by_source.pivot_table(index="subreddit", columns="content_type", values="texts", aggfunc="sum").fillna(0)
pivot["รวม"] = pivot.sum(axis=1)
st.subheader(subtitle)
common.table(pivot.sort_values("รวม", ascending=False).astype(int).rename(
    columns={"Comment": "ความคิดเห็น", "Post": "โพสต์"}), width="stretch")

# ---- drill-down along the dimensions (proposal figures 2-4: hierarchies from the largest to the smallest) ----
st.header("เจาะลึกตามมิติ (Drill-down)")
st.caption("ดูทีละระดับของมิติ: เลือกในกล่องใต้กราฟเพื่อลงไประดับถัดไป กดปุ่มด้านบนกราฟเพื่อย้อนกลับ  \n"
           "ใช้ช่วงเวลา แหล่งข้อมูล และมุมมอง (ทั้ง Reddit / เฉพาะ %s) ตามที่เลือกไว้" % ticker)
if scope == "total":
    raw = q("volume_hour_source", start, end, src_ids)
else:
    raw = q("mention_hour_source", ticker, start, end, src_ids)
base = raw.merge(q("sources"), on="source_id")
tab_time, tab_source = st.tabs(["เวลา (DimTime): ปี › เดือน › สัปดาห์ › วัน › ชั่วโมง",
                                "แหล่งข้อมูล (DimSource): แพลตฟอร์ม › ชุมชน › ประเภท"])
with tab_time:
    drill.drill("v_time", drill.time_frame(base), drill.TIME_LEVELS, "#1f77b4", noun)
with tab_source:
    drill.drill("v_source", base, drill.SOURCE_LEVELS, "#2ca02c", noun, horizontal=True, by_value=True)
