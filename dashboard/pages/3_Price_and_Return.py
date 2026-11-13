"""Dashboard 7.2-1  Price and Return  (proposal 7.2: close, volume, future_return 1/2/3/6/12h, RSI, ATR).

Questions answered: how did price and volume move, how do future returns differ between asset classes, and which
asset class is the most volatile (Normalized ATR, KPI 3 of table 8).
The sidebar has the two dimensions of 7.2 (time, asset): ticking an asset class ticks all its tickers, tickers can be
ticked one by one, and everything on the page follows the ticked tickers.  One ticker: its own series.  Up to
MAX_LINES tickers: one line each (price and volume as an index, because the prices have very different sizes).  More:
the average of the ticked tickers.
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

MAX_LINES = 8                       # up to this many tickers: one line per ticker, otherwise their average

common.setup("Price and Return (ราคาและผลตอบแทนรายชั่วโมง)", "📈")
_, start, end, _ = common.sidebar(multi=True)
how = common.granularity(start, end, "g_price")
tickers = common.selected_tickers()
universe = q("tickers")
names = dict(zip(universe.ticker, universe.name))
if not tickers:
    common.nothing_selected(["Current Return รวมทั้งช่วง (%)", "Volume Z-score สูงสุด", "Normalized Average True Range (%)"],
                            "ไม่ได้เลือกหลักทรัพย์ จึงไม่มีข้อมูลแสดง")
one = len(tickers) == 1
per_ticker = 1 < len(tickers) <= MAX_LINES

hourly = q("price_series_for", tickers, start, end)
if hourly.empty:
    st.info("ไม่มีข้อมูลราคาของหลักทรัพย์ที่เลือกในช่วงนี้ (ตลาดอาจปิด)")
    st.stop()

# ---- KPI cards first: the three KPIs of table 8 (close, volume, RSI and ATR are measures, shown below)
# log_return (DB column) = Current Return (proposal name) - same formula.  Several tickers: the average over them.
by = hourly.groupby("ticker")
returns = by.log_return.sum()
natr = by.normalized_atr.mean()
vz = by.volume_zscore_24.max()                                             # the highest of the range, like the Z-score cards of the other pages
suffix = "" if one else " (เฉลี่ยของ %d ตัว)" % len(by)
common.kpi_cards([
    ("Current Return รวมทั้งช่วง (%)", common.money(returns.mean()),
     "ผลตอบแทนช่วงเวลาปัจจุบัน = ln(close_t / close_t−1) × 100 รวมทุกชั่วโมงในช่วงที่เลือก" + suffix),
    ("Volume Z-score สูงสุด", common.money(vz.max()),
     "ค่าสูงสุดในช่วงที่เลือก (ปริมาณซื้อขายของราคา ไม่ใช่ปริมาณ Reddit) = (volume_t − μ24h) ÷ σ24h เทียบ 24 ชั่วโมงก่อนหน้า ไม่รวมชั่วโมงปัจจุบัน" + ("" if one else " (สูงสุดของทุกตัวที่เลือก)") + common.TRADING_Z_NOTE),
    ("Normalized Average True Range (%)", common.money(natr.mean()),
     "อัตราความผันผวนสัมพัทธ์ = (ATR 24 ชั่วโมง ÷ close) × 100 เฉลี่ยในช่วงที่เลือก" + suffix)])

# ---- one table per level of detail: every chart is built from the same long frame (ticker, time, measures)
pieces = []
for symbol, part in hourly.groupby("ticker"):
    part = part.copy()
    first = part.close.dropna().iloc[0] if part.close.notna().any() else float("nan")
    part["price_index"] = 100.0 * part.close / first                          # price rebased: the first close = 100
    mean_volume = part.volume.mean()
    part["volume_index"] = 100.0 * part.volume / mean_volume if mean_volume else float("nan")   # volume: the mean = 100
    shown_part = common.resample(part, {"close": "last", "volume": "sum", "rsi": "last", "atr": "last", "normalized_atr": "mean",
                                        "log_return": "sum", "volume_zscore_24": "max", "price_index": "last",
                                        "volume_index": "mean"}, how)
    shown_part["ticker"] = symbol
    pieces.append(shown_part)
long = pd.concat(pieces, ignore_index=True)
if len(tickers) > MAX_LINES:                                                  # the average of the ticked tickers
    mean_frame = long.groupby("time", as_index=False).mean(numeric_only=True)
    shown = mean_frame
else:
    shown = long


def trend(col, title, color, key, height=common.CHART_HEIGHT, log=False, **kw):
    """One trend chart: the single series, one line per ticker, or the average of many."""
    if one or len(tickers) > MAX_LINES:
        label = title + ("" if one else " (เฉลี่ยของที่เลือก)")
        return common.line(shown, "time", col, label, color, height, bar=common.kind(st, key), **kw)
    return common.multi_series_chart(long, "time", col, "ticker", title, height, log=log, y_domain=kw.get("y_domain"))


price_title = "ราคาปิด (USD)" if one else ("ราคาปิด (ค่าแรก = 100)" if per_ticker else "ราคาปิด")      # several lines: each rebased; the average: "(เฉลี่ยของที่เลือก)" is added by `trend`
common.show(trend("close" if one else "price_index", price_title, common.C_PRICE, "p_close"), width="stretch")
if not one:
    st.caption("เลือกหลายตัวจึงปรับราคาแต่ละตัวให้ค่าแรกของช่วง = 100 เพื่อเทียบกันได้ (ราคาจริงต่างขนาดกันมาก เช่น SPY หลักร้อย BTC หลักแสน)")
common.show(trend("volume" if one else "volume_index", "ปริมาณซื้อขาย (หน่วย)" if one else ("ปริมาณซื้อขาย (ค่าเฉลี่ย = 100)" if per_ticker else "ปริมาณซื้อขาย"),
                      common.C_VOLUME, "p_volume"), width="stretch")
common.show(trend("rsi", "RSI", common.C_RATE, "p_rsi", y_domain=[0, 100])
                + alt.Chart(alt.Data(values=[{"y": 30}, {"y": 70}])).mark_rule(strokeDash=[4, 4], color="gray")
                .encode(y="y:Q"), width="stretch")
st.caption("RSI (Relative Strength Index) คือดัชนีความแข็งแกร่งสัมพัทธ์ในช่วง 0 ถึง 100 (Wilder 14 แท่ง) วัดความเร็วและขนาดการเปลี่ยนแปลงของราคา  \n"
           "เส้นประที่ 30 และ 70 เป็นระดับที่นิยมใช้อ่านภาวะขายมากเกินไปและซื้อมากเกินไป")
if len(tickers) <= MAX_LINES:
    common.show(trend("atr", "ATR (USD)" if one else "ATR (USD) แกนลอการิทึม", common.C_ATR, "p_atr", log=True, y_zero=one)
                    if not one else common.line(shown, "time", "atr", "ATR (USD)", common.C_ATR, 220, y_zero=True,
                                                bar=common.kind(st, "p_atr")), width="stretch")
    st.caption("ATR (Average True Range) คือค่าเฉลี่ยของ True Range 24 ชั่วโมง วัดระดับความผันผวนของราคาโดยไม่พิจารณาทิศทาง  \n"
               "ค่าเป็นดอลลาร์สหรัฐ จึงเทียบข้ามสินทรัพย์ไม่ได้ ให้ดู Normalized ATR แทน")
common.show(trend("normalized_atr", "Normalized ATR (%)" if one else "Normalized ATR", common.C_NATR, "p_natr", y_zero=True), width="stretch")
if not one:
    st.caption("Normalized ATR หน่วยเป็น % ของราคาปิด (ATR 24 ชั่วโมง ÷ ราคาปิด × 100)")

# ---- the measures of every ticked ticker
st.subheader("รายละเอียดค่าวัดของหลักทรัพย์ที่เลือก")
snap = q("ticker_snapshot", start, end, tickers)
snap["สินทรัพย์"] = snap.ticker.map(lambda s: "%s (%s)" % (s, names.get(s, "")))
snap["กลุ่ม"] = snap.big_group.map(GROUP_LABELS)
rsi_zones = hourly.dropna(subset=["rsi"]).groupby("ticker").rsi.agg(over70=lambda s: (s > 70).mean(), under30=lambda s: (s < 30).mean())
snap = snap.merge(rsi_zones, left_on="ticker", right_index=True, how="left")
measures = snap[["สินทรัพย์", "กลุ่ม", "last_close", "last_rsi", "over70", "under30", "mean_normalized_atr_pct",
                 "fr_now", "fr_1h", "fr_2h", "fr_3h", "fr_6h", "fr_12h"]].rename(columns={
    "last_close": "ราคาปิดล่าสุด (USD)", "last_rsi": "RSI ล่าสุด", "over70": "สัดส่วน RSI > 70", "under30": "สัดส่วน RSI < 30",
    "mean_normalized_atr_pct": "Normalized ATR เฉลี่ย (%)",
    "fr_now": "ผลตอบแทน Current (%)", "fr_1h": "1h (%)", "fr_2h": "2h (%)", "fr_3h": "3h (%)", "fr_6h": "6h (%)", "fr_12h": "12h (%)"})
formats = {c: "{:.4f}" for c in measures.columns if c not in ("สินทรัพย์", "กลุ่ม")}
formats["ราคาปิดล่าสุด (USD)"] = "{:,.2f}"
st.dataframe(measures.style.format(formats, na_rep="-"), hide_index=True, width="stretch", height=min(420, 60 + 36 * len(snap)))      # a missing value shows "-", never None
st.caption("**RSI:** RSI ล่าสุด = ค่า RSI ของชั่วโมงสุดท้ายในช่วงที่เลือก  สัดส่วน RSI > 70 = สัดส่วนของชั่วโมงที่ RSI เกิน 70 (ซื้อมากเกินไป)  สัดส่วน RSI < 30 = สัดส่วนของชั่วโมงที่ต่ำกว่า 30 (ขายมากเกินไป)  \n"
           "**ผลตอบแทน:** ผลตอบแทน Current คือค่าเฉลี่ยต่อชั่วโมงของ Current Return (ผลตอบแทนของชั่วโมงเดียวกัน ส่วนขยาย) ส่วน 1h ถึง 12h คือผลตอบแทนล่วงหน้าเฉลี่ย ทุกคอลัมน์เป็นค่าเฉลี่ยในช่วงที่เลือก (ผลรวมของ Current Return ทั้งช่วงอยู่ในการ์ดด้านบน) ช่องที่ว่างหมายถึงไม่มีแท่งราคาครบตามกรอบเวลา (หุ้นและ ETF ที่ 12h ไม่มีเลย เพราะตลาดปิดกลางคืน)")

# ---- below, as before: asset classes (computed over the ticked tickers)
st.subheader("ผลตอบแทนล่วงหน้าแยกตามกลุ่มสินทรัพย์")
fr = q("future_return_by_group", start, end, tickers)
if fr.empty or fr.n.sum() == 0:
    st.info("ไม่มีข้อมูลผลตอบแทนล่วงหน้าในช่วงนี้")
else:
    fr["กลุ่ม"] = fr.big_group.map(GROUP_LABELS)
    fr["กรอบเวลา"] = fr.horizon
    fr["ราคาขึ้นกี่ % ของแท่ง"] = (100.0 * fr.share_up).round(1)
    chart = (alt.Chart(fr).mark_bar().encode(
        x=alt.X("กรอบเวลา:N", sort=["Current Return", "1h", "2h", "3h", "6h", "12h"], title="กรอบเวลา"),
        y=alt.Y("mean_return_pct:Q", title="ผลตอบแทนเฉลี่ย (%)"), xOffset="กลุ่ม:N",
        color=alt.Color("กลุ่ม:N", scale=common.group_scale()),
        tooltip=["กลุ่ม", "กรอบเวลา", alt.Tooltip("mean_return_pct:Q", format=".4f"),
                 alt.Tooltip("ราคาขึ้นกี่ % ของแท่ง:Q", format=".1f"), alt.Tooltip("n:Q", format=",")]).properties(height=common.CHART_HEIGHT))
    common.show(chart, width="stretch")
    common.table(fr[["กลุ่ม", "กรอบเวลา", "n", "mean_return_pct", "ราคาขึ้นกี่ % ของแท่ง"]].rename(columns={
        "n": "จำนวนตัวอย่าง", "mean_return_pct": "ผลตอบแทนเฉลี่ย (%)"}),
        hide_index=True, width="stretch")
    st.caption("**ราคาขึ้นกี่ % ของแท่ง** คือสัดส่วนของแท่งราคาที่ผลตอบแทนเป็นบวก (ราคาขึ้น) จากแท่งที่ราคาขยับ (ไม่นับแท่งที่ผลตอบแทนเท่ากับ 0 พอดี) 50 = ขึ้นกับลงพอ ๆ กัน เหมือนโยนเหรียญ  \n"
               "จำนวนตัวอย่างของหุ้นและ ETF ที่ 6h มีน้อย และที่ 12h เป็น 0 เพราะตลาดปิดกลางคืนจึงมีแท่งราคารายชั่วโมงไม่ครบ ไม่ได้แปลว่าผลตอบแทนเป็น 0")

st.subheader("กลุ่มสินทรัพย์ใดผันผวนสูงที่สุด")
st.caption("ผันผวน = ราคาขยับแรงแค่ไหนโดยไม่สนทิศขึ้นหรือลง  เรียงจากกลุ่มที่ผันผวนสูงสุด **กดที่แถวของกลุ่มเพื่อดูรายตัวของกลุ่มนั้น**  \n"
           "**Normalized ATR** = ความผันผวนสัมพัทธ์ (ATR 24 ชั่วโมง ÷ ราคาปิด × 100) เป็น KPI ของ proposal  \n"
           "**|Current Return| เฉลี่ย** ใช้ค่าสัมบูรณ์เพราะถ้าเฉลี่ยผลตอบแทนตรง ๆ ชั่วโมงที่ขึ้นกับลงจะหักล้างกันจนใกล้ 0 ทั้งที่ราคาขยับแรง (ส่วนขยาย)  \n"
           "**จำนวนแท่งราคา** = จำนวนแท่งราคารายชั่วโมงที่ใช้คำนวณ")
tr = q("ticker_risk", start, end, tickers)
tr["สินทรัพย์"] = tr.ticker.map(lambda t: "%s (%s)" % (t, names.get(t, "")))
# the stock_etf group is shown split into stocks, index ETFs and bitcoin ETFs (EXTENSION: their volatility differs a lot); the other groups as they are
tr["ชนิด"] = [("หุ้น/ETF · " + common.INSTRUMENT_LABELS.get(common.instrument_of(t), "")) if g == "stock_etf" else GROUP_LABELS.get(g, g) for t, g in zip(tr.ticker, tr.big_group)]
tr["atr_x_bars"] = tr.mean_normalized_atr_pct * tr.bars
tr["abs_x_bars"] = tr.mean_abs_log_return_pct * tr.bars
kinds = tr.groupby("ชนิด").agg(ตัว=("ticker", "nunique"), แท่ง=("bars", "sum"), atr=("atr_x_bars", "sum"), absr=("abs_x_bars", "sum")).reset_index()
kinds["atr"], kinds["absr"] = kinds.atr / kinds.แท่ง, kinds.absr / kinds.แท่ง              # the mean over all the bars of the kind, as the group table was
for row in kinds.sort_values("atr", ascending=False).itertuples():                       # one drawer per kind: its row (the numbers) is the header, the assets are inside
    part = tr[tr.ชนิด == row.ชนิด]
    with st.expander("**%s** · %d ตัว · แท่งราคา %s · Normalized ATR %.4f%% · |Current Return| %.4f%%" % (row.ชนิด, row.ตัว, "{:,}".format(int(row.แท่ง)), row.atr, row.absr)):
        common.table(part[["สินทรัพย์", "bars", "mean_normalized_atr_pct", "mean_abs_log_return_pct"]].rename(columns={
            "bars": "จำนวนแท่งราคา", "mean_normalized_atr_pct": "Normalized ATR เฉลี่ย (%)", "mean_abs_log_return_pct": "|Current Return| เฉลี่ย (%)"}).round(4),
            hide_index=True, width="stretch")
