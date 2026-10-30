"""Dashboard extension 6  Hot Events: ชั่วโมงที่ Reddit คึกคักมาก แล้วราคาเป็นอย่างไรต่อ (EXTENSION, not in the proposal).

Lists ticker-hours in which the Reddit Volume Z-score was above a threshold AND the sentiment was clearly directional,
with the win rate of the sentiment direction against the forward return, its 95% Wilson interval and the mean return.
It is a look at history, NOT a trading signal: win rates near 50% are what a random direction gives
(see output/reports/final/2_tests_and_hypotheses.md).
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

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
min_texts = st.session_state.get("h_n", 3)
events = q("hot_events", start, end, float(z_min), float(s_min), int(min_texts))
events = events[events.ticker.isin(tickers) & events.majority_final_status.isin(statuses)].copy()

common.kpi_cards([("จำนวนเหตุการณ์ (ชั่วโมง × สินทรัพย์)", "{:,}".format(len(events)), None),
                  ("จำนวนสินทรัพย์ที่เกิดเหตุการณ์", str(events.ticker.nunique()), None),
                  ("จำนวนชั่วโมงที่ต่างกัน", "{:,}".format(events.hour_utc.nunique()), "หลายสินทรัพย์เกิดในชั่วโมงเดียวกันได้")])
st.warning("**ส่วนขยายนอก proposal — ดูเหตุการณ์ย้อนหลัง ไม่ใช่สัญญาณซื้อขาย**  \n"
           "ผลทดสอบทั้งโครงการพบว่าความรู้สึกบน Reddit ทำนายทิศทางราคาได้ไม่ดีกว่าการสุ่ม (win rate ≈ 50%) "
           "ค่าที่ดูสูงในบางช่องมักเป็นความบังเอิญ โดยเฉพาะเมื่อจำนวนเหตุการณ์น้อย (ดูช่วงความเชื่อมั่นประกอบเสมอ)")
if events.empty:
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
