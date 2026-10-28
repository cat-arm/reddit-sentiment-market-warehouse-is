"""Dashboard 7.1-2  Ticker Mentions  (proposal 7.1: Ticker_mention_count, Mention Rate, Volume Z-score of an asset).

How often each asset is mentioned: the KPIs on top, then the ranking and the trend of the chosen ticker(s) (three
charts one under the other), and Ticker Mention Rate (%) = Ticker_mention_count / Reddit_volume x 100.  The sidebar has
the three dimensions: time, source (communities, Post / Comment) and asset (classes, several tickers).
Data: FactRedditVolume (mentions), reddit_volume_hourly (totals), reddit_hourly_features (z-scores).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard import common  # noqa: E402
from dashboard.common import q  # noqa: E402

MAX_LINES = 8                       # up to this many tickers the trend shows one line per ticker, otherwise their sum

common.setup("Ticker Mentions: สินทรัพย์ที่ถูกกล่าวถึงบน Reddit", "🗣️")
_, start, end, groups = common.sidebar(sources=True, multi=True)
how = common.granularity(start, end)
src_ids = common.selected_sources()
tickers = common.selected_tickers()
many = len(tickers) > 1
label = tickers[0] if not many else "%d ตัวรวมกัน" % len(tickers)

total = q("total_volume_series", start, end, src_ids)       # Reddit_volume per hour of the chosen sources: the denominator of the mention rate
rank = q("mention_ranking", start, end, src_ids)
rank = rank[rank.ticker.isin(tickers)].reset_index(drop=True)
mentions = q("mention_series", tickers, start, end, src_ids)
volume = q("ticker_zscore", tickers, start, end, src_ids)
if rank.empty or mentions.empty:
    st.warning("ไม่มีข้อมูลการกล่าวถึงในช่วงและตัวกรองที่เลือก")
    st.stop()

lo, hi = (total.time.min(), total.time.max()) if not total.empty else (mentions.time.min(), mentions.time.max())
full = pd.DataFrame({"time": pd.date_range(lo, hi, freq="h")})
merged = full.merge(mentions[["time", "mentions"]], on="time", how="left")
merged = merged.merge(volume[["time", "zscore"]], on="time", how="left")
merged = merged.merge(total[["time", "texts"]] if not total.empty else full.assign(texts=float("nan")), on="time", how="left")
merged["mentions"] = merged["mentions"].fillna(0)          # nobody mentioned it = a real 0
shown = common.resample(merged, {"mentions": "sum", "texts": "sum", "zscore": "max"}, how)
shown["rate"] = 100.0 * shown["mentions"] / shown["texts"].where(shown["texts"] > 0)

# ================================================================================================ KPIs on top
# KPIs of proposal 7.1: Ticker Mention Count (measure), Ticker Mention Rate (%) and Reddit Volume Z-score
m1, m2, m3, m4 = st.columns(4)
m1.metric("Ticker Mention Count รวม (ครั้ง)", "{:,}".format(int(mentions.mentions.sum())))
all_texts = float(merged.texts.sum())
m2.metric("Ticker Mention Rate (%)", "n/a" if not all_texts else "{:.3f}".format(100.0 * mentions.mentions.sum() / all_texts),
          help="Ticker Mention Count ÷ ปริมาณโพสต์และความคิดเห็นทั้งหมดในช่วงเดียวกัน × 100")
m3.metric("Reddit Volume Z-score สูงสุด", common.money(volume.zscore.max()),
          help="Z-score ของจำนวนที่พูดถึงสินทรัพย์ที่เลือก เทียบกับ 24 ชั่วโมงก่อนหน้าของตัวเอง")
m4.metric("ชั่วโมงที่ Z-score > 1.5", "{:,}".format(int((volume.zscore > 1.5).sum())), help="spike ตามเกณฑ์ 1.5 ของ proposal")
if volume.empty or volume.basis.iloc[0] == "texts":
    st.caption("Volume Z-score ของสินทรัพย์ = เทียบจำนวนข้อความที่พูดถึงตัวนี้กับ 24 ชั่วโมงก่อนหน้าของตัวเอง "
               "(ใช้ในชุดข้อมูล panel_Ticker_spike)")
else:
    st.caption("Volume Z-score (เมื่อเลือกหลายตัวหรือแหล่งข้อมูลบางส่วน) = เทียบจำนวนครั้งที่ถูกพูดถึงรวมของที่เลือกกับ 24 ชั่วโมงก่อนหน้า "
               "กฎเดียวกับปกติ แต่นับจาก Ticker Mention Count เพราะไม่ได้เก็บจำนวนข้อความต่อแหล่งข้อมูล และข้อความเดียวอาจพูดถึงหลายตัว")

# ================================================================================================ ranking
st.header("สินทรัพย์ที่ถูกพูดถึงมากที่สุด")
rank["กลุ่ม"] = rank.big_group.map(common.group_name)
top = rank.head(15)
chart = (alt.Chart(top).mark_bar().encode(
    x=alt.X("mentions:Q", title="Ticker Mention Count (ครั้งที่ถูกพูดถึง)"),
    y=alt.Y("ticker:N", sort="-x", title=None, axis=alt.Axis(labelOverlap=False)),   # label every ticker
    color=alt.Color("กลุ่ม:N", title="กลุ่ม", scale=common.group_scale()),
    tooltip=["ticker", "กลุ่ม", alt.Tooltip("mentions:Q", format=","), alt.Tooltip("mention_rate_pct:Q", format=".3f")])
    .properties(height=380))
st.altair_chart(chart, width="stretch")
common.table(rank[["ticker", "กลุ่ม", "mentions", "mention_rate_pct", "texts_about", "peak_hour_texts"]].rename(columns={
    "mentions": "Ticker Mention Count", "mention_rate_pct": "Ticker Mention Rate (%)",
    "texts_about": "ข้อความที่พูดถึง", "peak_hour_texts": "สูงสุดใน 1 ชั่วโมง"}).round(3),
    hide_index=True, width="stretch", height=360)
st.caption("Ticker Mention Rate (%) = Ticker Mention Count ÷ ปริมาณโพสต์และความคิดเห็นทั้งหมดในช่วงเดียวกัน × 100  \n"
           "ข้อความเดียวที่พูดถึงหลายตัวนับให้ทุกตัว จึงห้ามรวมคอลัมน์ข้าม ticker" + (
               "" if rank.texts_about.notna().any() else
               "  \nช่อง \"ข้อความที่พูดถึง\" ว่างเมื่อเลือกแหล่งข้อมูลบางส่วน เพราะไม่ได้เก็บจำนวนข้อความต่อแหล่งข้อมูล"))

# ================================================================================================ trend: three charts, one under the other
st.subheader("แนวโน้มการถูกพูดถึง")
if many and len(tickers) <= MAX_LINES:                      # one line (or stack) per ticker
    per = q("mention_series_by_ticker", tickers, start, end, src_ids)
    wide = per.pivot_table(index="time", columns="ticker", values="mentions", aggfunc="sum").reindex(full.time).fillna(0)
    wide = common.resample(wide.rename_axis("time").reset_index(), {c: "sum" for c in wide.columns}, how)
    long = wide.melt(id_vars="time", var_name="ticker", value_name="mentions")
    st.altair_chart(common.multi_series_chart(long, "time", "mentions", "ticker", "Ticker Mention Count", bar=common.kind(st, "m_count")),
                    width="stretch")
else:
    st.altair_chart(common.line(shown, "time", "mentions", "Ticker Mention Count" + (" (รวม %d ตัว)" % len(tickers) if many else ""),
                                "#2ca02c", fmt=common.DATE_FORMAT[how], bar=common.kind(st, "m_count")), width="stretch")
st.altair_chart(common.line(shown, "time", "rate", "Ticker Mention Rate (%)", "#9467bd", 240, fmt=common.DATE_FORMAT[how],
                            bar=common.kind(st, "m_rate")), width="stretch")
st.altair_chart(common.line(shown, "time", "zscore", "Volume Z-score ของ %s" % label, "#d62728", 240,
                            fmt=common.DATE_FORMAT[how], bar=common.kind(st, "m_z")), width="stretch")

st.subheader("พูดถึงที่ไหน (ชุมชน × ประเภทเนื้อหา)")
source = q("volume_by_source", tickers, start, end, src_ids)
common.table(source.rename(columns={"mentions": "ครั้งที่ถูกพูดถึง"}), hide_index=True, width="stretch")
