"""Dashboard 7.1-2  Ticker Mentions  (proposal 7.1: Ticker_mention_count, Mention Rate, Volume Z-score of an asset).

How often each asset is mentioned: ranking, trend of the chosen ticker, and
Ticker Mention Rate (%) = Ticker_mention_count / Reddit_volume x 100.  Uses the asset filters of the sidebar.
Data: FactRedditVolume (mentions), reddit_volume_hourly (totals), reddit_hourly_features (z-scores).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard import common, drill  # noqa: E402
from dashboard.common import q  # noqa: E402

common.setup("Ticker Mentions: สินทรัพย์ที่ถูกกล่าวถึงบน Reddit", "🗣️")
ticker, start, end, groups = common.sidebar(sources=True)
how = common.granularity(start, end)
src_ids = common.selected_sources()
st.caption(common.source_summary())
total = q("total_volume_series", start, end, src_ids)       # Reddit_volume per hour of the chosen sources: the denominator of the mention rate

# ================================================================================================ part 2: mentions
st.header("สินทรัพย์ที่ถูกพูดถึงมากที่สุด")
rank = q("mention_ranking", start, end, src_ids)
rank = rank[rank.big_group.isin(groups)].reset_index(drop=True)
if rank.empty:
    st.warning("ไม่มีข้อมูลการกล่าวถึงในช่วงนี้")
else:
    rank["กลุ่ม"] = rank.big_group.map(common.group_name)
    top = rank.head(15)
    chart = (alt.Chart(top).mark_bar().encode(
        x=alt.X("mentions:Q", title="Ticker Mention Count (ครั้งที่ถูกพูดถึง)"),
        y=alt.Y("ticker:N", sort="-x", title=None, axis=alt.Axis(labelOverlap=False)),   # label every ticker
        color=alt.Color("กลุ่ม:N", title="กลุ่ม", scale=common.group_scale()),
        tooltip=["ticker", "กลุ่ม", alt.Tooltip("mentions:Q", format=","), alt.Tooltip("mention_rate_pct:Q", format=".3f")])
        .properties(height=380))
    left, right = st.columns([3, 2])
    left.altair_chart(chart, width="stretch")
    with right:
        common.table(rank[["ticker", "กลุ่ม", "mentions", "mention_rate_pct", "texts_about", "peak_hour_texts"]].rename(columns={
        "mentions": "Ticker Mention Count", "mention_rate_pct": "Ticker Mention Rate (%)",
        "texts_about": "ข้อความที่พูดถึง", "peak_hour_texts": "สูงสุดใน 1 ชั่วโมง"}).round(3),
        hide_index=True, width="stretch", height=360)
    st.caption("Ticker Mention Rate (%) = Ticker Mention Count ÷ ปริมาณโพสต์และความคิดเห็นทั้งหมดในช่วงเดียวกัน × 100  \n"
               "ข้อความเดียวที่พูดถึงหลายตัวนับให้ทุกตัว จึงห้ามรวมคอลัมน์ข้าม ticker" + (
                   "" if rank.texts_about.notna().any() else
                   "  \nช่อง \"ข้อความที่พูดถึง\" ว่างเมื่อเลือกแหล่งข้อมูลบางส่วน เพราะไม่ได้เก็บจำนวนข้อความต่อแหล่งข้อมูล"))

    st.subheader("แนวโน้มการถูกพูดถึงของ %s" % ticker)
    mentions = q("mention_series", ticker, start, end, src_ids)
    volume = q("ticker_zscore", ticker, start, end, src_ids)
    if mentions.empty:
        st.info("ไม่มีใครพูดถึง %s ในช่วงนี้" % ticker)
    else:
        lo, hi = (total.time.min(), total.time.max()) if not total.empty else (mentions.time.min(), mentions.time.max())
        full = pd.DataFrame({"time": pd.date_range(lo, hi, freq="h")})
        merged = full.merge(mentions[["time", "mentions"]], on="time", how="left")
        merged = merged.merge(volume[["time", "zscore"]], on="time", how="left")
        merged = merged.merge(total[["time", "texts"]] if not total.empty else full.assign(texts=float("nan")),
                              on="time", how="left")
        merged["mentions"] = merged["mentions"].fillna(0)          # nobody mentioned it = a real 0
        shown = common.resample(merged, {"mentions": "sum", "texts": "sum", "zscore": "max"}, how)
        shown["rate"] = 100.0 * shown["mentions"] / shown["texts"].where(shown["texts"] > 0)
        st.altair_chart(common.line(shown, "time", "mentions", "Ticker Mention Count", "#2ca02c", fmt=common.DATE_FORMAT[how]), width="stretch")
        a, b = st.columns(2)
        a.altair_chart(common.line(shown, "time", "rate", "Ticker Mention Rate (%)", "#9467bd", 220, fmt=common.DATE_FORMAT[how]), width="stretch")
        b.altair_chart(common.line(shown, "time", "zscore", "Volume Z-score ของ %s" % ticker, "#d62728", 220,
                              fmt=common.DATE_FORMAT[how]), width="stretch")
        # KPIs of proposal 7.1: Ticker Mention Count (measure), Ticker Mention Rate (%) and Reddit Volume Z-score
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Ticker Mention Count รวม (ครั้ง)", "{:,}".format(int(mentions.mentions.sum())))
        all_texts = float(merged.texts.sum())
        m2.metric("Ticker Mention Rate (%)", "n/a" if not all_texts else "{:.3f}".format(100.0 * mentions.mentions.sum() / all_texts),
                  help="Ticker Mention Count ÷ ปริมาณโพสต์และความคิดเห็นทั้งหมดในช่วงเดียวกัน × 100")
        m3.metric("Reddit Volume Z-score สูงสุด", common.money(volume.zscore.max()),
                  help="Z-score ของจำนวนข้อความที่พูดถึงสินทรัพย์นี้ เทียบกับ 24 ชั่วโมงก่อนหน้าของตัวเอง")
        m4.metric("ชั่วโมงที่ Z-score > 1.5", "{:,}".format(int((volume.zscore > 1.5).sum())),
                  help="spike ตามเกณฑ์ 1.5 ของ proposal")
        if volume.empty or volume.basis.iloc[0] == "texts":
            st.caption("Volume Z-score ของสินทรัพย์ = เทียบจำนวนข้อความที่พูดถึงตัวนี้กับ 24 ชั่วโมงก่อนหน้าของตัวเอง "
                       "(ใช้ในชุดข้อมูล panel_Ticker_spike)")
        else:
            st.caption("Volume Z-score ของสินทรัพย์ (เมื่อเลือกแหล่งข้อมูลบางส่วน) = เทียบจำนวนครั้งที่ถูกพูดถึงในแหล่งข้อมูลที่เลือกกับ 24 ชั่วโมงก่อนหน้า "
                       "กฎเดียวกับปกติ แต่นับจาก Ticker Mention Count เพราะไม่ได้เก็บจำนวนข้อความต่อแหล่งข้อมูล")

        st.write("พูดถึงที่ไหน (ชุมชน × ประเภทเนื้อหา)")
        source = q("volume_by_source", ticker, start, end, src_ids)
        common.table(source.rename(columns={"mentions": "ครั้งที่ถูกพูดถึง"}), hide_index=True, width="stretch")

# ---- drill-down along the three dimensions (proposal figures 2-4: hierarchies from the largest to the smallest) ----
st.header("เจาะลึกตามมิติ (Drill-down)")
st.caption("ดูทีละระดับของมิติ: เลือกในกล่องใต้กราฟเพื่อลงไประดับถัดไป กดปุ่มด้านบนกราฟเพื่อย้อนกลับ  \n"
           "ใช้ช่วงเวลาและแหล่งข้อมูลตามตัวกรองกลาง; แท็บเวลาและแหล่งข้อมูลดูการพูดถึง %s ส่วนแท็บหลักทรัพย์ดูทุกสินทรัพย์ในกลุ่มที่เลือก" % ticker)
sources_table = q("sources")
universe = q("tickers")
names = dict(zip(universe.ticker, universe.name))


def ticker_label(column, value, rows):
    if column == "big_group":
        return common.group_name(value)
    return "%s · %s" % (value, names.get(value, ""))


tab_time, tab_source, tab_ticker = st.tabs(["เวลา (DimTime): ปี › เดือน › สัปดาห์ › วัน › ชั่วโมง",
                                            "แหล่งข้อมูล (DimSource): แพลตฟอร์ม › ชุมชน › ประเภท",
                                            "หลักทรัพย์ (DimTicker): กลุ่มสินทรัพย์ › สัญลักษณ์"])
raw = q("mention_hour_source", ticker, start, end, src_ids).merge(sources_table, on="source_id")
with tab_time:
    st.caption("จำนวนครั้งที่ %s ถูกพูดถึง" % ticker)
    drill.drill("m_time", drill.time_frame(raw), drill.TIME_LEVELS, "#2ca02c", "ครั้งที่ถูกพูดถึง")
with tab_source:
    st.caption("จำนวนครั้งที่ %s ถูกพูดถึง" % ticker)
    drill.drill("m_source", raw, drill.SOURCE_LEVELS, "#2ca02c", "ครั้งที่ถูกพูดถึง", horizontal=True, by_value=True)
with tab_ticker:
    st.caption("จำนวนครั้งที่แต่ละสินทรัพย์ถูกพูดถึง (ข้อความเดียวที่พูดถึงหลายตัวนับให้ทุกตัว)")
    frame = rank.rename(columns={"mentions": "value"})[["big_group", "ticker", "value"]] if not rank.empty else rank
    drill.drill("m_ticker", frame, drill.TICKER_LEVELS, "#9467bd", "ครั้งที่ถูกพูดถึง", label_of=ticker_label,
                horizontal=True, by_value=True)
