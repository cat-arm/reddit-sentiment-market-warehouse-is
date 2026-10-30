"""Dashboard 7  Detected Signal List (proposal 7.6, table 18) with what the price did after each signal.

One list of signals (volume spike / sentiment spike / combined) of ticker-hours, linked to DimDetectionConfig: the Z-score and Sentiment
thresholds of the sidebar (0 = no threshold, the user sets them) and the least texts per hour of the slider under the cards.  Everything on the page
follows the same three values: the count table, the list with the returns after each signal, and the win-rate chart.  Only texts that
MENTION the asset are counted (ticker-level panel).  A look at history, NOT a trading signal: win rates near 50% are what a random direction
gives (see output/reports/final/2_tests_and_hypotheses.md).
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
TARGETS = [("log_return", "Current Return"), *[("future_return_" + h, h) for h in HORIZONS]]
NAMES = {"log_return": "ราคาชั่วโมงเดียวกัน (Current Return %)", **{"future_return_" + h: "ราคาหลัง %s ชั่วโมง (%%)" % h[:-1] for h in HORIZONS}}
CARDS = ["จำนวนสัญญาณ (ชั่วโมง × สินทรัพย์)", "จำนวนสินทรัพย์ที่เกิดสัญญาณ", "จำนวนชั่วโมงที่ต่างกัน"]

common.setup("รายการสัญญาณ (Hot Events)", "🔥")
_, start, end, _ = common.sidebar(multi=True, detection="events", majority=True)         # DimTime, DimTicker, DimDetectionConfig, DimMajoritySentiment
tickers = common.selected_tickers()
statuses = common.selected_statuses()
if not tickers or not statuses:
    common.nothing_selected(CARDS, "ไม่ได้เลือกหลักทรัพย์หรือประเภทความรู้สึกส่วนใหญ่ จึงไม่มีข้อมูลแสดง")

z_min = float(st.session_state.get("h_z", 0.0))
s_min = float(st.session_state.get("h_s", 0.0))
st.session_state.setdefault("h_n", 1)
LEVELS = ("low", "medium", "high")
for level in LEVELS:
    st.session_state.setdefault("h_lv_" + level, True)           # every level ticked: nothing is removed
levels = [level for level in LEVELS if st.session_state["h_lv_" + level]]
n_min = int(st.session_state["h_n"])         # the least texts of an hour (the slider sits under the cards, so the first run reads the state)

rules = {**signals.RULES, "min_texts_for_sentiment": n_min}
found = signals.detect(q("signal_panel"), z_min, s_min, rules)
found = found[(found.hour_utc >= start) & (found.hour_utc <= end) & found.ticker.isin(tickers) & found.majority_final_status.isin(statuses)
              & (found.reddit_volume >= n_min) & found.signal_level.isin(levels)].sort_values("hour_utc", ascending=False)

common.kpi_cards([(CARDS[0], "{:,}".format(len(found)), None),
                  (CARDS[1], str(found.ticker.nunique()), None),
                  (CARDS[2], "{:,}".format(found.hour_utc.nunique()), "หลายสินทรัพย์เกิดในชั่วโมงเดียวกันได้")])

st.subheader("รายการสัญญาณ (Detected Signal List)")
st.caption("ทุกตัวเลขในหน้านี้นับเฉพาะข้อความที่กล่าวถึงสินทรัพย์นั้น (ไม่ใช่ข้อความทั้งหมดบน Reddit)  \n"
           "เกณฑ์ปัจจุบันคือ Z-score มากกว่า %.1f, |Sentiment Score| ตั้งแต่ %.2f และข้อความอย่างน้อย %d ต่อชั่วโมง (ค่า 0 คือไม่กรอง ปรับ Z-score และ Sentiment ได้ที่แถบด้านซ้าย)  \n"
           "**ชนิดของสัญญาณ**  \n"
           "volume_spike คือปริมาณพุ่งอย่างเดียว  \n"
           "positive_sentiment_spike และ negative_sentiment_spike คือความรู้สึกชัดเจนอย่างเดียว  \n"
           "combined_signal คือปริมาณพุ่งและความรู้สึกชัดเจนพร้อมกัน  \n"
           "**ระดับของสัญญาณ**  \n"
           "low, medium และ high ยิ่งเกินเกณฑ์มากยิ่งสูง ไม่ได้บอกว่าแม่นยำกว่า  \n"
           "รายการนี้ใช้ประกอบการวิเคราะห์ ไม่ใช่คำแนะนำการลงทุน" % (z_min, s_min, n_min))
st.slider("ข้อความขั้นต่ำต่อชั่วโมง (เฉพาะที่กล่าวถึงสินทรัพย์นั้น)", 1, 30, key="h_n",
          help="ชั่วโมงที่มีข้อความน้อยกว่าค่านี้จะไม่นับเป็นสัญญาณ ค่านี้มีผลกับทั้งหน้า")
st.write("ระดับของสัญญาณ (high คือเกินเกณฑ์มาก ไม่ได้หมายความว่าดีหรือแม่นยำกว่า)")
for cell, level in zip(st.columns(len(LEVELS)), LEVELS):
    cell.checkbox(level, key="h_lv_" + level)
if found.empty:
    st.info("ไม่พบสัญญาณตามเกณฑ์นี้ในช่วงที่เลือก ลองลดเกณฑ์หรือขยายช่วงเวลา")
    st.stop()

# ---- 1. how many ----------------------------------------------------------------------------------------------------------------
st.write("จำนวนสัญญาณ แยกตามกลุ่มสินทรัพย์และประเภทสัญญาณ")
summary = pd.crosstab(found.big_group.map(GROUP_LABELS).rename("กลุ่ม"), found.signal_type, margins=True, margins_name="รวม").reset_index()
common.table(summary, hide_index=True, width="stretch")

# ---- 2. the list, with what the price did after each signal -----------------------------------------------------------------------
st.subheader("รายการสัญญาณที่ตรวจพบ (ล่าสุด 300 รายการ)")
view = found.head(300).copy()
view["timestamp"] = pd.to_datetime(view.hour_utc, unit="s", utc=True).dt.strftime("%Y-%m-%d %H:%M")
view["big_group"] = view.big_group.map(GROUP_LABELS)
common.table(view[["timestamp", "ticker", "big_group", "signal_type", "signal_level", "reddit_volume", "sentiment_mean", "reddit_volume_zscore_24", *NAMES]].rename(columns={
    "timestamp": "เวลา (UTC)", "ticker": "สินทรัพย์", "big_group": "กลุ่ม", "signal_type": "ชนิด", "signal_level": "ระดับ", "reddit_volume": "จำนวนข้อความ",
    "sentiment_mean": "ความรู้สึก (-1 ถึง +1)", "reddit_volume_zscore_24": "Z-score ปริมาณ", **NAMES}).round(3), hide_index=True, width="stretch", height=380)
st.caption("ช่องราคาที่ว่างหมายถึงไม่มีข้อมูลราคาให้คำนวณ (เช่น ตลาดปิด หรือไม่มีแท่งราคาที่ห่างพอดี) ไม่ใช่ค่า 0  \nราคาหลัง n ชั่วโมงคือผลตอบแทน (%) ที่เกิดหลังชั่วโมงนั้น")


# ---- 3. did the price follow the sentiment? -----------------------------------------------------------------------------------------
def wilson(wins, n, z=1.96):
    p = wins / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


rows = []
directional = found[found.sentiment_mean.notna() & (found.sentiment_mean != 0)]          # no direction, no win or loss
for column, name in TARGETS:
    ret = directional[column]
    moved = directional[ret.notna() & (ret != 0)]
    n = len(moved)
    row = {"Horizon": name, "n": n}
    if n < MIN_N:
        row.update({"win": None, "lo": None, "hi": None, "avg": None})
    else:
        wins = int((np.sign(moved.sentiment_mean) == np.sign(moved[column])).sum())
        lo, hi = wilson(wins, n)
        row.update({"win": 100.0 * wins / n, "lo": 100 * lo, "hi": 100 * hi, "avg": float(moved[column].mean())})
    rows.append(row)
ok = pd.DataFrame(rows).dropna(subset=["win"])
st.subheader("หลังสัญญาณ ราคาไปทางเดียวกับความรู้สึกบ่อยแค่ไหน")
if ok.empty:
    st.info("สัญญาณที่มีผลตอบแทนและความรู้สึกมีทิศน้อยกว่า %d รายการ จึงยังสรุปไม่ได้" % MIN_N)
else:
    base = alt.Chart(ok).encode(x=alt.X("Horizon:N", sort=[n for _, n in TARGETS], title=None, axis=alt.Axis(labelAngle=0)))
    bars = base.mark_bar(color=common.C_SENT).encode(
        y=alt.Y("win:Q", scale=alt.Scale(domain=[0, 100]), title="ราคาไปทางเดียวกับความรู้สึก (%)"),
        tooltip=["Horizon", alt.Tooltip("n:Q", title="จำนวนสัญญาณ"), alt.Tooltip("win:Q", format=".1f", title="%"),
                 alt.Tooltip("lo:Q", format=".1f", title="ช่วงเชื่อมั่น 95% ล่าง"), alt.Tooltip("hi:Q", format=".1f", title="ช่วงเชื่อมั่น 95% บน"),
                 alt.Tooltip("avg:Q", format="+.3f", title="ผลตอบแทนเฉลี่ย (%)")])
    errors = base.mark_rule(color="#222222", strokeWidth=2).encode(y="lo:Q", y2="hi:Q")
    common.show(bars + errors + common.ref_rule(50), width="stretch")
    st.caption("เส้นประคือ 50% (เท่ากับการสุ่ม)  \n"
               "เส้นสีดำคือช่วงเชื่อมั่น 95% ชี้ที่แท่งเพื่อดูจำนวนสัญญาณและผลตอบแทนเฉลี่ย  \n"
               "หากเส้นสีดำคร่อม 50% แสดงว่าแยกจากการสุ่มไม่ได้  \n"
               "ไม่นับสัญญาณที่ความรู้สึกหรือผลตอบแทนเป็น 0  \n"
               "สัญญาณที่เกิดใกล้กันมีข้อมูลซ้อนทับ ช่วงเชื่อมั่นจริงจึงกว้างกว่าที่แสดง")

st.warning("**ดูเหตุการณ์ย้อนหลัง ไม่ใช่สัญญาณซื้อขาย**  \n"
           "ผลทดสอบทั้งโครงการพบว่าความรู้สึกบน Reddit ทำนายทิศทางราคาได้ไม่ดีกว่าการสุ่ม (ราว 50%)  ค่าที่ดูสูงในบางช่องมักเป็นความบังเอิญ โดยเฉพาะเมื่อจำนวนสัญญาณน้อย")
