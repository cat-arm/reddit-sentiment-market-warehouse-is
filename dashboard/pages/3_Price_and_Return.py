"""Dashboard 7.2-1  Price and Return  (proposal 7.2: close, volume, future_return 1/2/3/6/12h, RSI, ATR).

Questions answered: how did price and volume move, how do future returns differ between asset classes, and which
asset class is the most volatile (Normalized ATR, KPI 3 of table 8).
Data: market_hourly_features (valid price bars only; closed-market placeholder rows are excluded upstream).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import altair as alt  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard import common  # noqa: E402
from dashboard.common import GROUP_LABELS, q  # noqa: E402

common.setup("Price and Return: ราคาและผลตอบแทนรายชั่วโมง", "📈")
ticker, start, end, groups = common.sidebar()

st.subheader("%s: ราคาปิดและปริมาณการซื้อขาย" % ticker)
how = common.granularity(start, end, "g_price")
price = q("price_series", ticker, start, end)
if price.empty:
    st.info("ไม่มีข้อมูลราคาของ %s ในช่วงนี้ (ตลาดอาจปิด)" % ticker)
else:
    # log_return (DB column) = Current Return (proposal name) - same formula
    shown = common.resample(price, {"close": "last", "volume": "sum", "rsi": "last", "atr": "last",
                                    "normalized_atr": "mean", "log_return": "sum", "volume_zscore_24": "max"}, how)
    st.altair_chart(common.line(shown, "time", "close", "ราคาปิด (USD)", bar=common.kind(st, "p_close")), width="stretch")
    c1, c2 = st.columns(2)
    c1.altair_chart(common.line(shown, "time", "volume", "ปริมาณซื้อขาย (หน่วย)", "#2ca02c", 220, bar=common.kind(c1, "p_volume")), width="stretch")
    c2.altair_chart(common.line(shown, "time", "rsi", "RSI (0–100)", "#9467bd", 220, bar=common.kind(c2, "p_rsi"))
                    + alt.Chart(alt.Data(values=[{"y": 30}, {"y": 70}])).mark_rule(strokeDash=[4, 4], color="gray")
                    .encode(y="y:Q"), width="stretch")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("ราคาปิดล่าสุด", common.money(price.close.iloc[-1]))
    k2.metric("Current Return รวม (%)", common.money(price.log_return.sum()))
    k3.metric("Normalized ATR เฉลี่ย (%)", common.money(price.normalized_atr.mean()))
    k4.metric("Volume Z-score ล่าสุด", common.money(price.volume_zscore_24.dropna().iloc[-1]
                                                    if price.volume_zscore_24.notna().any() else float("nan")))
    st.caption("Current Return = ln(close_t / close_t−1) × 100  \nNormalized ATR = ATR 24 ชั่วโมง ÷ close × 100  \n"
               "ผลตอบแทนล่วงหน้านับจากชั่วโมงที่เกิดข้อมูล เว้นว่างเมื่อไม่มีบาร์ราคาครบตามกรอบเวลา (เช่น ตลาดปิด)")

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
a, b = st.columns([2, 3])
a.dataframe(risk[["กลุ่ม", "bars", "mean_normalized_atr_pct", "mean_abs_log_return_pct"]].rename(columns={
    "bars": "จำนวนบาร์", "mean_normalized_atr_pct": "Normalized ATR เฉลี่ย (%)",
    "mean_abs_log_return_pct": "|Current Return| เฉลี่ย (%)"}).round(4), hide_index=True, width="stretch")
tr = q("ticker_risk", start, end)
b.dataframe(tr[tr.big_group.isin(groups)].round(4), hide_index=True, width="stretch", height=260)
