"""Dashboard 7.2-1  Price and Return  (proposal 7.2: close, volume, future_return 1/2/3/6/12h, RSI, ATR).

Questions answered: how did price and volume move, how do future returns differ between asset classes, and which
asset class is the most volatile (Normalized ATR, KPI 3 of table 8).
Data: market_hourly_features (valid price bars only; closed-market placeholder rows are excluded upstream).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard import common  # noqa: E402
from dashboard.common import GROUP_LABELS, q  # noqa: E402

common.setup("Price and Return: ราคาและผลตอบแทนรายชั่วโมง", "📈")
ticker, start, end, groups = common.sidebar()
how = common.granularity(start, end, "g_price")
universe = q("tickers")
name = dict(zip(universe.ticker, universe.name))
st.caption("การ์ดและกราฟรายละเอียดด้านล่างเป็นของ **%s · %s** (เลือกที่แถบข้าง); ส่วน \"ภาพรวมตามกลุ่มสินทรัพย์\" เป็นของทุกกลุ่มที่ติ๊ก"
           % (ticker, name.get(ticker, "")))
price = q("price_series", ticker, start, end)

# ---- KPI cards first: exactly the three KPIs of table 8 (close, volume, RSI and ATR are measures, shown below)
if price.empty:
    st.info("ไม่มีข้อมูลราคาของ %s ในช่วงนี้ (ตลาดอาจปิด)" % ticker)
else:
    common.kpi_cards([
        ("Current Return (%)", common.money(price.log_return.sum()),
         "ผลตอบแทนช่วงเวลาปัจจุบัน = ln(close_t / close_t−1) × 100 รวมทุกชั่วโมงในช่วงที่เลือก"),
        ("Volume Z-score", common.money(price.volume_zscore_24.dropna().iloc[-1]
                                        if price.volume_zscore_24.notna().any() else float("nan")),
         "ค่าล่าสุดในช่วงที่เลือก = (volume_t − μ24h) ÷ σ24h เทียบ 24 ชั่วโมงก่อนหน้า ไม่รวมชั่วโมงปัจจุบัน"),
        ("Normalized Average True Range (%)", common.money(price.normalized_atr.mean()),
         "อัตราความผันผวนสัมพัทธ์ = (ATR 24 ชั่วโมง ÷ close) × 100 เฉลี่ยในช่วงที่เลือก")])

# ---- by asset class (proposal: "แยกตาม Ticker และกลุ่มสินทรัพย์"): follows the asset-class boxes of the sidebar
st.header("ภาพรวมตามกลุ่มสินทรัพย์ที่ติ๊ก")
snap = q("ticker_snapshot", start, end)
snap = snap[snap.big_group.isin(groups)].copy()
if snap.empty:
    st.info("ไม่มีข้อมูลราคาของกลุ่มที่ติ๊กในช่วงนี้")
else:
    snap["สินทรัพย์"] = snap.ticker.map(lambda s: "%s · %s" % (s, name.get(s, "")))
    snap["กลุ่ม"] = snap.big_group.map(GROUP_LABELS)
    st.subheader("รายสินทรัพย์ในกลุ่มที่ติ๊ก")
    common.table(snap[["สินทรัพย์", "กลุ่ม", "last_close", "current_return_pct", "mean_normalized_atr_pct", "last_rsi",
                       "fr_1h", "fr_2h", "fr_3h", "fr_6h", "fr_12h"]].rename(columns={
        "last_close": "ราคาปิดล่าสุด (USD)", "current_return_pct": "Current Return รวม (%)",
        "mean_normalized_atr_pct": "Normalized ATR เฉลี่ย (%)", "last_rsi": "RSI ล่าสุด",
        "fr_1h": "ผลตอบแทน 1h (%)", "fr_2h": "2h (%)", "fr_3h": "3h (%)", "fr_6h": "6h (%)", "fr_12h": "12h (%)"}).round(4),
        hide_index=True, width="stretch", height=420)
    st.caption("ผลตอบแทนล่วงหน้า = ค่าเฉลี่ยของแต่ละกรอบเวลาในช่วงที่เลือก ว่างเมื่อไม่มีแท่งราคาครบตามกรอบเวลา (หุ้น/ETF ที่ 12h ไม่มีเลย เพราะตลาดปิดกลางคืน)")

st.subheader("ผลตอบแทนล่วงหน้าแยกตามกลุ่มสินทรัพย์")
fr = q("future_return_by_group", start, end)
fr = fr[fr.big_group.isin(groups)].copy()
if fr.empty or fr.n.sum() == 0:
    st.info("ไม่มีข้อมูลผลตอบแทนล่วงหน้าในช่วงนี้")
else:
    fr["กลุ่ม"] = fr.big_group.map(GROUP_LABELS)
    chart = (alt.Chart(fr).mark_bar().encode(
        x=alt.X("horizon:N", sort=["1h", "2h", "3h", "6h", "12h"], title="กรอบเวลา"),
        y=alt.Y("mean_return_pct:Q", title="ผลตอบแทนเฉลี่ย (%)"), xOffset="กลุ่ม:N",
        color=alt.Color("กลุ่ม:N", scale=common.group_scale()),
        tooltip=["กลุ่ม", "horizon", alt.Tooltip("mean_return_pct:Q", format=".4f"),
                 alt.Tooltip("share_up:Q", format=".1%"), alt.Tooltip("n:Q", format=",")]).properties(height=280))
    st.altair_chart(chart, width="stretch")
    common.table(fr[["กลุ่ม", "horizon", "n", "mean_return_pct", "share_up"]].rename(columns={
        "n": "จำนวนตัวอย่าง", "mean_return_pct": "ผลตอบแทนเฉลี่ย (%)", "share_up": "สัดส่วนที่เป็นบวก"}),
        hide_index=True, width="stretch")
    st.caption("จำนวนตัวอย่างหุ้น/ETF ที่ 6h น้อยและที่ 12h เป็น 0 เพราะตลาดปิดกลางคืนจึงมีบาร์รายชั่วโมงไม่ครบ ไม่ได้แปลว่าผลตอบแทนเป็น 0")

st.subheader("กลุ่มสินทรัพย์ใดผันผวนสูงที่สุด")
risk = q("group_risk", start, end)
risk = risk[risk.big_group.isin(groups)].copy()
risk["กลุ่ม"] = risk.big_group.map(GROUP_LABELS)
common.table(risk[["กลุ่ม", "bars", "mean_normalized_atr_pct", "mean_abs_log_return_pct"]].rename(columns={
    "bars": "จำนวนบาร์", "mean_normalized_atr_pct": "Normalized ATR เฉลี่ย (%)",
    "mean_abs_log_return_pct": "|Current Return| เฉลี่ย (%)"}).round(4), hide_index=True, width="stretch")
st.caption("Normalized ATR = ATR 24 ชั่วโมง ÷ close × 100 ยิ่งสูงยิ่งผันผวน (เทียบข้ามสินทรัพย์ได้เพราะเป็นเปอร์เซ็นต์)")

# ---- the chosen ticker: trend charts of the measures (close, volume, RSI, ATR) and its own future returns
st.header("รายละเอียดของ %s" % ticker)
if price.empty:
    st.stop()
# log_return (DB column) = Current Return (proposal name) - same formula
shown = common.resample(price, {"close": "last", "volume": "sum", "rsi": "last", "atr": "last",
                                "normalized_atr": "mean", "log_return": "sum", "volume_zscore_24": "max"}, how)
st.altair_chart(common.line(shown, "time", "close", "ราคาปิด (USD)", bar=common.kind(st, "p_close")), width="stretch")
st.altair_chart(common.line(shown, "time", "volume", "ปริมาณซื้อขาย", "#2ca02c", 220, bar=common.kind(st, "p_volume")), width="stretch")
st.altair_chart(common.line(shown, "time", "rsi", "RSI", "#9467bd", 220, bar=common.kind(st, "p_rsi"), y_domain=[0, 100])
                + alt.Chart(alt.Data(values=[{"y": 30}, {"y": 70}])).mark_rule(strokeDash=[4, 4], color="gray")
                .encode(y="y:Q"), width="stretch")
st.caption("RSI = ดัชนีความแข็งแกร่งสัมพัทธ์ 0–100 (Wilder 14 แท่ง) วัดความเร็วและการเปลี่ยนแปลงของการเคลื่อนไหวของราคา "
           "เส้นประที่ 30 และ 70 คือระดับที่นิยมใช้อ่านว่าขายมากเกินไป / ซื้อมากเกินไป")
st.altair_chart(common.line(shown, "time", "atr", "ATR (USD)", "#8c564b", 220, y_zero=True, bar=common.kind(st, "p_atr")), width="stretch")
st.caption("ATR = ช่วงความผันผวนเฉลี่ยที่แท้จริง (ดอลลาร์สหรัฐ) เฉลี่ย True Range 24 ชั่วโมง วัดระดับความผันผวนของราคาโดยไม่พิจารณาทิศทาง "
           "ค่าเป็นดอลลาร์ จึงเทียบข้ามสินทรัพย์ไม่ได้ ให้ดู Normalized ATR")
st.altair_chart(common.line(shown, "time", "normalized_atr", "Normalized ATR (%)", "#e377c2", 220, y_zero=True,
                            bar=common.kind(st, "p_natr")), width="stretch")
st.caption("Normalized ATR = ATR 24 ชั่วโมง ÷ close × 100  \nCurrent Return = ln(close_t / close_t−1) × 100  \n"
           "ผลตอบแทนล่วงหน้านับจากชั่วโมงที่เกิดข้อมูล เว้นว่างเมื่อไม่มีบาร์ราคาครบตามกรอบเวลา (เช่น ตลาดปิด)")

st.subheader("รายละเอียดค่าวัดของ %s" % ticker)
detail = pd.DataFrame([{"ค่าวัด": label, "ล่าสุด": s.dropna().iloc[-1] if s.notna().any() else float("nan"),
                        "เฉลี่ย": s.mean(), "ต่ำสุด": s.min(), "สูงสุด": s.max(), "จำนวนชั่วโมงที่มีค่า": int(s.notna().sum())}
                       for label, s in (("close ราคาปิด (USD)", price.close), ("volume ปริมาณซื้อขาย (หน่วย)", price.volume),
                                        ("RSI (0–100)", price.rsi), ("ATR (USD)", price.atr),
                                        ("Normalized ATR (%)", price.normalized_atr), ("Current Return (%)", price.log_return))])
common.table(detail.round(4), hide_index=True, width="stretch")
rsi = price.rsi.dropna()
st.caption("RSI > 70 (ซื้อมากเกินไป) %s ของชั่วโมงที่มีค่า · RSI < 30 (ขายมากเกินไป) %s" % (
    "n/a" if rsi.empty else "{:.1%}".format((rsi > 70).mean()), "n/a" if rsi.empty else "{:.1%}".format((rsi < 30).mean())))

st.subheader("ผลตอบแทนล่วงหน้า 5 ช่วงเวลาของ %s" % ticker)
own = q("future_return_for_ticker", ticker, start, end)
if own.n.sum() == 0:
    st.info("ไม่มีผลตอบแทนล่วงหน้าของ %s ในช่วงนี้" % ticker)
else:
    own_chart = (alt.Chart(own).mark_bar(color="#1f77b4").encode(
        x=alt.X("horizon:N", sort=["1h", "2h", "3h", "6h", "12h"], title="กรอบเวลา"),
        y=alt.Y("mean_return_pct:Q", title="ผลตอบแทนเฉลี่ย (%)"),
        tooltip=["horizon", alt.Tooltip("mean_return_pct:Q", format=".4f"), alt.Tooltip("share_up:Q", format=".1%"),
                 alt.Tooltip("n:Q", format=",")]).properties(height=240))
    st.altair_chart(own_chart, width="stretch")
    common.table(own[["horizon", "n", "mean_return_pct", "share_up"]].rename(columns={
        "horizon": "กรอบเวลา", "n": "จำนวนตัวอย่าง", "mean_return_pct": "ผลตอบแทนเฉลี่ย (%)", "share_up": "สัดส่วนที่เป็นบวก"}),
        hide_index=True, width="stretch")
