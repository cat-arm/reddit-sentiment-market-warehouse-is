"""Dashboard extension 7  Hot Events: ชั่วโมงที่ Reddit คึกคักมาก แล้วราคาเป็นอย่างไรต่อ (EXTENSION, not in the proposal).

Lists ticker-hours in which the Reddit Volume Z-score was above a threshold AND the sentiment was clearly directional,
with the win rate of the sentiment direction against the forward return, its 95% Wilson interval and the mean return.
It is a look at history, NOT a trading signal: win rates near 50% are what a random direction gives
(see output/reports/final/2_tests_and_hypotheses.md).
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import altair as alt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from analysis import signals  # noqa: E402
from dashboard import common  # noqa: E402
from dashboard.common import GROUP_LABELS, q  # noqa: E402

HORIZONS = ("1h", "2h", "3h", "6h", "12h")
MIN_N = 30                                  # same guard as the win-rate analysis (A2)

common.setup("Hot Events: ชั่วโมงที่ Reddit คึกคักมาก (ส่วนขยาย)", "🔥")
# the same dimensions as the Ranking and Signals dashboard: DimTime, DimTicker, DimDetectionConfig, DimMajoritySentiment
_, start, end, _ = common.sidebar(multi=True, detection="events", majority=True)
tickers = common.selected_tickers()
statuses = common.selected_statuses()
if not tickers or not statuses:
    common.nothing_selected(["จำนวนเหตุการณ์ (ชั่วโมง × สินทรัพย์)", "จำนวนสินทรัพย์ที่เกิดเหตุการณ์", "จำนวนชั่วโมงที่ต่างกัน"],
                            "ไม่ได้เลือกหลักทรัพย์หรือประเภทความรู้สึกส่วนใหญ่ จึงไม่มีข้อมูลแสดง")

z_min = st.session_state.get("h_z", 2.0)
s_min = st.session_state.get("h_s", 0.50)
events = q("hot_events", start, end, float(z_min), float(s_min))
events = events[events.ticker.isin(tickers) & events.majority_final_status.isin(statuses)].copy()

def signal_section():
    """The data-driven signals of system 7.6 (proposal tables 18 and 16): the detected signal list with the historical statistics of the
    asset, and the summary of how many signals of which type were found.  Uses the thresholds of the sidebar (Z-score, Sentiment); the
    signal engine has its own rule for the least texts of a sentiment spike (configs/detection.yaml)."""
    st.subheader("สัญญาณเชิงข้อมูลของระบบ 7.6 (Detected Signal List)")
    found = signals.detect(q("signal_panel"), float(z_min), float(s_min))
    found = found[(found.hour_utc >= start) & (found.hour_utc <= end) & found.ticker.isin(tickers) & found.majority_final_status.isin(statuses)]
    st.caption("ระบบตรวจจับสัญญาณใช้เกณฑ์ Reddit Volume Z-score > %.1f และ |Sentiment Score| ≥ %.2f จากแถบด้านซ้าย  ชนิดสัญญาณ: volume_spike (ปริมาณพุ่ง) "
               "positive/negative_sentiment_spike (ความรู้สึกชัด) combined_signal (ทั้งสองอย่าง)  ระดับ low / medium / high ตามความแรง  "
               "เป็นรายการประกอบการวิเคราะห์ ไม่ใช่คำแนะนำการลงทุน" % (z_min, s_min))
    if found.empty:
        st.info("ไม่พบสัญญาณตามเกณฑ์นี้ในช่วงที่เลือก ลองลดเกณฑ์หรือขยายช่วงเวลา")
        return
    by_type = found.groupby(["signal_type", "signal_level"]).size().reset_index(name="n")
    common.show(alt.Chart(by_type).mark_bar().encode(
        x=alt.X("n:Q", title="จำนวนสัญญาณ"), y=alt.Y("signal_type:N", title=None),
        color=alt.Color("signal_level:N", sort=["low", "medium", "high"], title="ระดับ",
                        scale=alt.Scale(domain=["low", "medium", "high"], range=["#9ecae1", "#fdae6b", "#d62728"])),
        tooltip=["signal_type", "signal_level", "n"]).properties(height=200))
    st.write("จำนวนสัญญาณ แยกตามกลุ่มสินทรัพย์และประเภทสัญญาณ")
    summary = pd.crosstab(found.big_group.map(GROUP_LABELS).rename("กลุ่ม"), found.signal_type, margins=True, margins_name="รวม").reset_index()
    common.table(summary, hide_index=True, width="stretch")
    st.write("จำนวนสัญญาณ แยกตามเดือน")
    months = pd.to_datetime(found.hour_utc, unit="s", utc=True).dt.strftime("%Y-%m").rename("เดือน")
    monthly = pd.crosstab(months, found.signal_type).reset_index()
    common.table(monthly, hide_index=True, width="stretch")
    st.write("รายการสัญญาณที่ตรวจพบ (ล่าสุด 300 รายการ) พร้อมสถิติย้อนหลังของสินทรัพย์นั้น")
    choices = {"Current Return": "log_return", **{h: h for h in HORIZONS}}
    st.session_state.setdefault("hs_h", HORIZONS[0])
    pick = st.radio("Horizon ของสถิติย้อนหลัง (Win Rate, ความสัมพันธ์)", list(choices), horizontal=True, key="hs_h")
    horizon = choices[pick]
    stats = q("ranking_table")
    stats = stats[stats.horizon == horizon][["ticker", "winrate", "correlation"]]
    listing = found.merge(stats, on="ticker", how="left").sort_values("hour_utc", ascending=False).head(300).copy()
    listing["timestamp"] = pd.to_datetime(listing.hour_utc, unit="s", utc=True).dt.strftime("%Y-%m-%d %H:%M")
    listing["horizon"] = pick
    common.table(listing[["timestamp", "ticker", "big_group", "signal_type", "signal_level", "sentiment_mean", "reddit_volume",
                          "reddit_volume_zscore_24", "horizon", "winrate", "correlation"]].rename(
        columns={"reddit_volume_zscore_24": "reddit_volume_zscore", "correlation": "correlation_value"}).round(3),
        hide_index=True, width="stretch", height=380)
    st.caption("winrate / correlation_value = สถิติย้อนหลังเต็มช่วงข้อมูลของสินทรัพย์นั้น ณ Horizon ที่เลือก (ค่าว่าง = ข้อมูลไม่พอ) "
               "ไม่ถือเป็นการยืนยันผลตอบแทนหรือคำแนะนำการลงทุน")


common.kpi_cards([("จำนวนเหตุการณ์ (ชั่วโมง × สินทรัพย์)", "{:,}".format(len(events)), None),
                  ("จำนวนสินทรัพย์ที่เกิดเหตุการณ์", str(events.ticker.nunique()), None),
                  ("จำนวนชั่วโมงที่ต่างกัน", "{:,}".format(events.hour_utc.nunique()), "หลายสินทรัพย์เกิดในชั่วโมงเดียวกันได้")])
st.warning("**ส่วนขยายนอก proposal — ดูเหตุการณ์ย้อนหลัง ไม่ใช่สัญญาณซื้อขาย**  \n"
           "ผลทดสอบทั้งโครงการพบว่าความรู้สึกบน Reddit ทำนายทิศทางราคาได้ไม่ดีกว่าการสุ่ม (win rate ≈ 50%) "
           "ค่าที่ดูสูงในบางช่องมักเป็นความบังเอิญ โดยเฉพาะเมื่อจำนวนเหตุการณ์น้อย (ดูช่วงความเชื่อมั่นประกอบเสมอ)")
if events.empty:
    signal_section()
    st.info("ไม่พบเหตุการณ์ตามเกณฑ์นี้ในช่วงที่เลือก ลองลดเกณฑ์หรือขยายช่วงเวลา")
    st.stop()


def wilson(wins, n, z=1.96):
    p = wins / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


TARGETS = [("log_return", "Current Return"), *[("future_return_" + h, h) for h in HORIZONS]]
rows = []
for column, name in TARGETS:
    ret = events[column]
    moved = events[ret.notna() & (ret != 0)]
    n = len(moved)
    row = {"Horizon": name, "เหตุการณ์ที่มีผลตอบแทน (n)": n}
    if n < MIN_N:
        row.update({"Win Rate (%)": None, "ช่วงเชื่อมั่น 95% (%)": "ข้อมูลไม่เพียงพอ (n < %d)" % MIN_N, "ผลตอบแทนเฉลี่ย (%)": None})
    else:
        wins = int((np.sign(moved.sentiment_mean) == np.sign(moved[column])).sum())
        lo, hi = wilson(wins, n)
        row.update({"Win Rate (%)": round(100 * wins / n, 1), "ช่วงเชื่อมั่น 95% (%)": "%.1f – %.1f" % (100 * lo, 100 * hi),
                    "ผลตอบแทนเฉลี่ย (%)": round(float(moved[column].mean()), 4)})
    rows.append(row)
st.subheader("หลังเหตุการณ์ ราคาไปทางเดียวกับความรู้สึกบ่อยแค่ไหน")
common.table(pd.DataFrame(rows), hide_index=True, width="stretch")
st.caption("Win Rate = สัดส่วนที่ทิศของความรู้สึกตรงกับทิศของผลตอบแทน (ไม่นับผลตอบแทนที่เป็น 0)  \n"
           "ถ้าช่วงเชื่อมั่นคลุม 50% แปลว่าแยกจากการสุ่มไม่ได้ · ช่วงเวลาของข้อมูลที่ซ้อนทับกันทำให้ช่วงจริงกว้างกว่าที่แสดง")

by_group = (events.assign(กลุ่ม=events.big_group.map(GROUP_LABELS)).groupby("กลุ่ม")
            .agg(เหตุการณ์=("ticker", "size"), สินทรัพย์=("ticker", "nunique")).reset_index())
st.subheader("แยกตามกลุ่มสินทรัพย์")
st.dataframe(by_group, hide_index=True, width="stretch")
top = events.groupby("ticker").size().sort_values(ascending=False).head(10).rename("เหตุการณ์").reset_index()
st.subheader("สินทรัพย์ที่เกิดบ่อยสุด")
st.dataframe(top, hide_index=True, width="stretch")

st.subheader("รายการเหตุการณ์ (ล่าสุด 300 รายการ)")
view = events.head(300).copy()
view["timestamp"] = pd.to_datetime(view.hour_utc, unit="s", utc=True).dt.strftime("%Y-%m-%d %H:%M")
common.table(view[["timestamp", "ticker", "big_group", "sentiment_mean", "reddit_volume", "zscore", "log_return", "future_return_1h",
                   "future_return_2h", "future_return_3h", "future_return_6h", "future_return_12h"]].rename(
    columns={"log_return": "Current Return (%)"}).round(3), hide_index=True, width="stretch", height=380)
st.caption("ผลตอบแทนว่าง = ไม่มีแท่งราคาที่ห่างพอดีตามกรอบเวลา (เช่น หุ้นช่วงตลาดปิด) ไม่ใช่ 0")

# ---- how complete the returns are, and why they are missing -------------------------------------------------------------------
st.subheader("ผลตอบแทนที่มีและที่ขาด (ร้อยละของเหตุการณ์ที่มีค่า)")
have = events.assign(กลุ่ม=events.big_group.map(GROUP_LABELS)).groupby("กลุ่ม").agg(
    เหตุการณ์=("ticker", "size"), **{name: (column, lambda s: round(100.0 * s.notna().mean(), 1)) for column, name in TARGETS}).reset_index()
common.table(have, hide_index=True, width="stretch")
st.caption("ทำไมบางช่องขาด (ไม่ใช่ข้อมูลหาย แต่ตามกติกาของ proposal)  \n"
           "• ผลตอบแทนล่วงหน้า n ชั่วโมง ต้องมีแท่งราคาที่ห่างพอดี n ชั่วโมง  หุ้น/ETF ซื้อขายเฉพาะเวลาตลาดสหรัฐ (ราว 13:30–20:00 UTC) "
           "จึงไม่มีแท่งราคาหลังจากนั้น 12 ชั่วโมง (ตลาดปิด) และ 6 ชั่วโมงก็ขาดสำหรับเหตุการณ์ช่วงบ่าย  ฟิวเจอร์สหยุดพักบางช่วงของวัน  คริปโตซื้อขายตลอด 24 ชั่วโมง จึงไม่ขาด  \n"
           "• Current Return ต้องมีแท่งราคาก่อนหน้า 1 ชั่วโมงพอดี  ชั่วโมงแรกของตลาดเปิดจึงไม่มีค่า  \n"
           "• ชั่วโมงท้ายสุดของข้อมูลยังไม่มีราคาล่วงหน้า")

signal_section()
