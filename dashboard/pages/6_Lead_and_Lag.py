"""Dashboard extension 7  Lead and Lag  (who moves first: the sentiment or the price?).

Same filters as Market and Sentiment (table 17).  Everything is computed from the ticker-hours that pass them (the texts of the
chosen communities and model, the hours in the range, the two thresholds, the majority status):
  * Spearman correlation between the Sentiment Score of an hour and the return k hours before / after it (k = -6 .. +6),
  * the average Sentiment Score after a fall or a rise of the price (1 / 2 / 3 / 6 / 12 hours before).
The p-values and win rates per asset are on dashboard 5 (Statistical Analysis).
Descriptive only: hourly data are autocorrelated, so intervals are narrower than they should be; no investment advice.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import altair as alt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard import common, data  # noqa: E402
from dashboard.common import GROUP_LABELS, q  # noqa: E402

common.setup("Lead and Lag (ความรู้สึกหรือราคาเปลี่ยนก่อนกัน)", "🔀")
_, start, end, _ = common.sidebar(multi=True, sentiment=True, detection="overview", majority=True)
tickers = common.selected_tickers()
communities = common.selected_communities()
statuses = common.selected_statuses()
content_types = common.selected_content_types()
CARDS = ["ค่าสหสัมพันธ์ ชั่วโมงเดียวกัน", "ค่าสหสัมพันธ์ เมื่อราคาเปลี่ยนก่อน (−6 ถึง −1 ชม.)", "ค่าสหสัมพันธ์ เมื่อราคาเปลี่ยนหลัง (+1 ถึง +6 ชม.)"]
if not tickers or not communities or not statuses or not content_types:
    common.nothing_selected(CARDS, "ไม่ได้เลือกหลักทรัพย์ ชุมชน หรือประเภทความรู้สึกส่วนใหญ่ จึงไม่มีข้อมูลแสดง")
z_th = st.session_state.get("d_z", 0.0)                 # DimDetectionConfig: filters the hours (0 = no filter)
s_th = st.session_state.get("d_s", 0.0)
names = dict(zip(q("tickers").ticker, q("tickers").name))

prices = q("price_series_for", tickers, start, end)
sent = q("sentiment_hourly", tickers, start, end, communities, common.selected_model(), "all", content_types)
if prices.empty:
    common.kpi_cards([(c, "n/a", None) for c in CARDS])
    st.info("ไม่มีข้อมูลราคาของหลักทรัพย์ที่เลือกในช่วงนี้ (ตลาดอาจปิด)")
    st.stop()
per_ticker = data.sentiment_frame(sent, start, end)
per_ticker_kept = per_ticker.assign(majority=per_ticker.majority.where(data.threshold_mask(per_ticker, z_th, s_th)))

# ---- who moves first?  the same ticker-hours as above, now looking back as well as forward
timing = per_ticker_kept.rename(columns={"series": "ticker"})[["ticker", "hour_utc", "sentiment_mean", "majority"]]
timing = timing[timing.majority.isin(statuses)].merge(prices[["ticker", "hour_utc", "log_return"]], on=["ticker", "hour_utc"], how="left")
lags = data.lag_correlation(timing)

def _mean(rows):
    return "n/a" if rows.empty or rows.rho.notna().sum() == 0 else "{:+.3f}".format(rows.rho.mean())


common.kpi_cards([
    (CARDS[0], _mean(lags[lags.lag == 0]), "ค่าสหสัมพันธ์ Spearman ระหว่าง Sentiment Score ของชั่วโมงที่มีข้อความกับ Current Return ของชั่วโมงเดียวกัน"),
    (CARDS[1], _mean(lags[lags.lag < 0]), "ค่าเฉลี่ยของค่าสหสัมพันธ์เมื่อเทียบกับผลตอบแทนของ 1 ถึง 6 ชั่วโมงก่อนชั่วโมงที่มีข้อความ (ราคาเปลี่ยนก่อน)"),
    (CARDS[2], _mean(lags[lags.lag > 0]), "ค่าเฉลี่ยของค่าสหสัมพันธ์เมื่อเทียบกับผลตอบแทนของ 1 ถึง 6 ชั่วโมงหลังชั่วโมงที่มีข้อความ (ความรู้สึกเปลี่ยนก่อน)")])
st.subheader("ความรู้สึกหรือราคาเปลี่ยนก่อนกัน")
if lags.rho.notna().sum() == 0:
    st.info("ตัวอย่างน้อยเกินไปสำหรับวัดความสัมพันธ์ข้ามเวลา")
else:
    lags["ช่วงเวลา"] = lags.lag.map(lambda k: "ชั่วโมงเดียวกัน" if k == 0 else ("ราคาก่อน %d ชม." % -k if k < 0 else "ราคาหลัง %d ชม." % k))
    lags["ฝั่ง"] = lags.lag.map(lambda k: "ราคาเปลี่ยนก่อนข้อความ" if k < 0 else ("ชั่วโมงเดียวกัน" if k == 0 else "ราคาเปลี่ยนหลังข้อความ"))
    base = alt.Chart(lags).encode(x=alt.X("lag:O", title="ผลตอบแทนของชั่วโมงที่ห่างจากชั่วโมงที่มีข้อความกี่ชั่วโมง (ค่าลบคือก่อนมีข้อความ ค่าบวกคือหลังมีข้อความ)",
                                          axis=alt.Axis(labelAngle=0)))
    bars = base.mark_bar().encode(
        y=alt.Y("rho:Q", title="ค่าสหสัมพันธ์ Spearman (ความรู้สึก vs ผลตอบแทน)"),
        color=alt.Color("ฝั่ง:N", scale=alt.Scale(domain=["ราคาเปลี่ยนก่อนข้อความ", "ชั่วโมงเดียวกัน", "ราคาเปลี่ยนหลังข้อความ"],
                                                  range=["#d62728", "#7f7f7f", "#1f77b4"]), legend=alt.Legend(orient="top", title=None)),
        tooltip=["ช่วงเวลา", alt.Tooltip("rho:Q", title="ค่าสหสัมพันธ์ Spearman", format="+.3f"), alt.Tooltip("n:Q", title="จำนวนตัวอย่าง", format=","),
                 alt.Tooltip("ci_lo:Q", title="ช่วงเชื่อมั่น 95% ล่าง", format="+.3f"), alt.Tooltip("ci_hi:Q", title="ช่วงเชื่อมั่น 95% บน", format="+.3f")])
    errors = base.mark_rule(color="#222222", strokeWidth=2).encode(y="ci_lo:Q", y2="ci_hi:Q")
    zero = common.zero_rule()
    common.show(bars + errors + zero, width="stretch")
    st.caption("**วิธีอ่าน**  \n"
               "แต่ละแท่งคือความสัมพันธ์ระหว่าง Sentiment Score ของชั่วโมงที่มีข้อความ กับผลตอบแทนรายชั่วโมงที่ห่างออกไปตามจำนวนชั่วโมงที่ระบุ  \n"
               "หากราคาเปลี่ยนก่อนแล้วจึงมีการโพสต์ แท่งสีแดง (ฝั่งซ้าย) จะสูงกว่าแท่งสีน้ำเงิน  \n"
               "หากความรู้สึกนำราคา แท่งสีน้ำเงิน (ฝั่งขวา) จะสูงกว่า  \n"
               "เส้นสีดำคือช่วงเชื่อมั่น 95% หากเส้นคร่อมศูนย์ แสดงว่าแยกจากกรณีไม่มีความสัมพันธ์ไม่ได้")

st.subheader("ความรู้สึกหลังราคาขึ้นหรือลง")
CURRENT = "Current Return (ชั่วโมงเดียวกัน)"
PAST = {CURRENT: 0, **{"%d ชั่วโมงก่อนหน้า" % h: h for h in (1, 2, 3, 6, 12)}}              # the horizons of the proposal (1 / 2 / 3 / 6 / 12 hours)
st.session_state.setdefault("s_past_hours", "3 ชั่วโมงก่อนหน้า")
past_pick = st.radio("ดูผลตอบแทน", list(PAST), horizontal=True, key="s_past_hours", label_visibility="collapsed")
timing = timing.assign(past=data.past_return(timing, PAST[past_pick]))
rb = data.return_buckets(timing, "past")
if rb.empty:
    st.info("ตัวอย่างน้อยเกินไปสำหรับแบ่งกลุ่มตามผลตอบแทนก่อนหน้า (ต้องมีอย่างน้อย 50 ticker-hourที่มีทั้งข้อความและราคาก่อนหน้า)")
else:
    price_levels = ["ลดลงมาก", "ลดลงเล็กน้อย", "ทรงตัว", "เพิ่มขึ้นเล็กน้อย", "เพิ่มขึ้นมาก"]
    rb["ระดับราคา"] = [price_levels[int(b)] if len(rb) == 5 else "กลุ่ม %d" % (int(b) + 1) for b in rb.bucket]
    rb["ป้าย"] = rb.apply(lambda r: "%s (%+.2f%% ถึง %+.2f%%)" % (r["ระดับราคา"], r.lo, r.hi), axis=1)
    base = alt.Chart(rb).encode(x=alt.X("ป้าย:N", sort=list(rb["ป้าย"]), axis=alt.Axis(labelAngle=0, labelLimit=200),
                                        title="ผลตอบแทนก่อนชั่วโมงที่มีข้อความ (แบ่งเป็น 5 กลุ่มเท่ากัน จากลดลงมากไปเพิ่มขึ้นมาก)"))
    bars = base.mark_bar(color=common.C_SENT).encode(
        y=alt.Y("mean:Q", title="Sentiment Score เฉลี่ย"),
        tooltip=["ระดับราคา", alt.Tooltip("mean_return:Q", title="ผลตอบแทนก่อนหน้าเฉลี่ย (%)", format="+.3f"),
                 alt.Tooltip("n:Q", title="จำนวนตัวอย่าง", format=","), alt.Tooltip("mean:Q", title="Sentiment Score เฉลี่ย", format="+.4f"),
                 alt.Tooltip("ci_lo:Q", title="ช่วงเชื่อมั่น 95% ล่าง", format="+.4f"), alt.Tooltip("ci_hi:Q", title="ช่วงเชื่อมั่น 95% บน", format="+.4f")])
    errors = base.mark_rule(color="#222222", strokeWidth=2).encode(y="ci_lo:Q", y2="ci_hi:Q")
    zero = common.zero_rule()
    common.show(bars + errors + zero, width="stretch")
    st.caption("**วิธีอ่าน**  \n"
               "แบ่ง ticker-hour ที่มีข้อความเป็น 5 กลุ่มเท่ากันตามผลตอบแทนของราคาก่อนชั่วโมงนั้น แล้วดู Sentiment Score เฉลี่ยของแต่ละกลุ่ม  \n"
               "หากราคาที่ลดลงทำให้ความรู้สึกแย่ลง แท่งซ้าย (ลดลงมาก) ควรต่ำกว่าแท่งขวา (เพิ่มขึ้นมาก)  \n"
               "เส้นสีดำคือช่วงเชื่อมั่น 95%")
