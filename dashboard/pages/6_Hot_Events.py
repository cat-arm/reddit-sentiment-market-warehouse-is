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
_, start, end, groups = common.sidebar(need_ticker=False)

# the three thresholds are read from their keys, so the KPI cards can come first
z_min = st.session_state.get("h_z", 2.0)
s_min = st.session_state.get("h_s", 0.50)
min_texts = st.session_state.get("h_n", 3)
events = q("hot_events", start, end, float(z_min), float(s_min), int(min_texts))
events = events[events.big_group.isin(groups)].copy()

common.kpi_cards([("จำนวนเหตุการณ์ (ชั่วโมง × สินทรัพย์)", "{:,}".format(len(events)), None),
                  ("จำนวนสินทรัพย์ที่เกิดเหตุการณ์", str(events.ticker.nunique()), None),
                  ("จำนวนชั่วโมงที่ต่างกัน", "{:,}".format(events.hour_utc.nunique()), "หลายสินทรัพย์เกิดในชั่วโมงเดียวกันได้")])
st.warning("**ส่วนขยายนอก proposal — ดูเหตุการณ์ย้อนหลัง ไม่ใช่สัญญาณซื้อขาย**  \n"
           "ผลทดสอบทั้งโครงการพบว่าความรู้สึกบน Reddit ทำนายทิศทางราคาได้ไม่ดีกว่าการสุ่ม (win rate ≈ 50%) "
           "ค่าที่ดูสูงในบางช่องมักเป็นความบังเอิญ โดยเฉพาะเมื่อจำนวนเหตุการณ์น้อย (ดูช่วงความเชื่อมั่นประกอบเสมอ)")
c1, c2, c3 = st.columns(3)
c1.slider("Volume Z-score ต้องเกิน", 1.5, 4.0, 2.0, 0.1, key="h_z")
c2.slider("|Sentiment| ตั้งแต่", 0.05, 0.90, 0.50, 0.05, key="h_s")
c3.slider("ข้อความขั้นต่ำในชั่วโมงนั้น", 1, 20, 3, key="h_n")
if events.empty:
    st.info("ไม่พบเหตุการณ์ตามเกณฑ์นี้ในช่วงที่เลือก ลองลดเกณฑ์หรือขยายช่วงเวลา")
    st.stop()


def wilson(wins, n, z=1.96):
    p = wins / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


rows = []
for h in HORIZONS:
    ret = events["future_return_" + h]
    moved = events[ret.notna() & (ret != 0)]
    n = len(moved)
    row = {"Horizon": h, "เหตุการณ์ที่มีผลตอบแทน (n)": n}
    if n < MIN_N:
        row.update({"Win Rate (%)": None, "ช่วงเชื่อมั่น 95% (%)": "ข้อมูลไม่เพียงพอ (n < %d)" % MIN_N, "Future Return เฉลี่ย (%)": None})
    else:
        wins = int((np.sign(moved.sentiment_mean) == np.sign(moved["future_return_" + h])).sum())
        lo, hi = wilson(wins, n)
        row.update({"Win Rate (%)": round(100 * wins / n, 1), "ช่วงเชื่อมั่น 95% (%)": "%.1f – %.1f" % (100 * lo, 100 * hi),
                    "Future Return เฉลี่ย (%)": round(float(moved["future_return_" + h].mean()), 4)})
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
common.table(view[["timestamp", "ticker", "big_group", "sentiment_mean", "reddit_volume", "zscore", "future_return_1h",
                   "future_return_3h", "future_return_6h"]].round(3), hide_index=True, width="stretch", height=380)
st.caption("ผลตอบแทนว่าง = ไม่มีแท่งราคาที่ห่างพอดีตามกรอบเวลา (เช่น หุ้นช่วงตลาดปิด) ไม่ใช่ 0")
