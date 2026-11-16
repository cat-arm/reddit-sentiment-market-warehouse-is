"""Dashboard 7.2  Price and Return  (proposal 7.2: close, volume, future_return 1/2/3/6/12h, RSI, ATR) with the Reddit volume drawn next to it.

One page since 2026-11-15 (it was two: Price and Return, page 3, and Price and Reddit, page 4, an extension).  The price of the chosen assets (one asset: its
close; several: an index accumulated from their mean Current Return), the trading volume, the RSI and the Normalized ATR are each drawn against a Reddit
measure of the reader's choice (the message volume or the mentions of the ticked assets) on the same time axis, one tick box per line; then the measures
of every ticked asset, the future returns and the volatility by asset class.  Every chart and table has a title and one line saying what it is used for.
The sidebar has the dimensions of 7.2 (time, asset) and the Reddit sources.  A look at two series that move together, never a cause.
Data: market_hourly_features (valid price bars only), reddit_volume_hourly (message volume), reddit_hourly_community (mentions).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard import common  # noqa: E402
from dashboard.common import GROUP_LABELS, q  # noqa: E402

block = common.block
CARDS = ["ปริมาณข้อความรวม", "Reddit Volume Z-score สูงสุด", "Current Return รวมทั้งช่วง (%)", "Volume Z-score สูงสุด (ปริมาณซื้อขาย)", "Normalized Average True Range (%)"]

common.setup("ราคาและผลตอบแทน (Price and Return)", "📈")
_, start, end, _ = common.sidebar(sources=True, multi=True)
how = common.granularity(start, end, "g_price")
tickers = common.selected_tickers()
src_ids = common.selected_sources()
universe = q("tickers")
names = dict(zip(universe.ticker, universe.name))
if not tickers or not src_ids:
    common.nothing_selected(CARDS, "ยังไม่ได้เลือกหลักทรัพย์หรือแหล่งข้อมูล จึงไม่มีข้อมูลแสดง")
one = len(tickers) == 1

hourly = q("price_series_for", tickers, start, end)
reddit = q("total_volume_series", start, end, src_ids)
mentions = q("ticker_texts_series", tickers, start, end, src_ids).rename(columns={"texts": "mentions"})       # texts that mention the chosen assets (once per asset)
if hourly.empty:
    st.info("ไม่มีข้อมูลราคาของหลักทรัพย์ที่เลือกในช่วงนี้ (ตลาดอาจปิด)")
    st.stop()

# ---- cards: the Reddit volume of the market, the Current Return, the trading volume and the volatility of the assets
returns = hourly.groupby("ticker").log_return.sum()
trading_z = hourly.groupby("ticker").volume_zscore_24.max()
natr = hourly.groupby("ticker").normalized_atr.mean()
suffix = "" if one else " (เฉลี่ยของ %d ตัว)" % hourly.ticker.nunique()
common.kpi_cards([
    (CARDS[0], "{:,}".format(int(reddit.texts.sum())) if not reddit.empty else "0",
     common.explain("จำนวนข้อความ Reddit ทั้งตลาดในช่วงเวลาที่เลือก", "นับทุกข้อความของชุมชนที่เลือก ไม่แยกตามสินทรัพย์")),
    (CARDS[1], common.money(reddit.zscore.max()) if not reddit.empty else "n/a",
     common.explain("ชั่วโมงที่ปริมาณข้อความทั้งตลาดผิดปกติที่สุดในช่วงนี้ ผิดปกติแค่ไหน", common.Z_SCORE_HOW + " แล้วเลือกค่าสูงสุดของช่วง", common.REDDIT_Z_NOTE)),
    (CARDS[2], common.money(returns.mean()),
     common.explain("ราคาขึ้นหรือลงรวมทั้งช่วงเวลากี่ % (+ = ขึ้น, − = ลง)",
                    "บวกผลตอบแทนรายชั่วโมง ln(ราคาปิดชั่วโมงนี้ ÷ ราคาปิดชั่วโมงก่อน) × 100 ทุกชั่วโมงในช่วงที่เลือก "
                    "นับเฉพาะชั่วโมงที่มีราคาชั่วโมงก่อนหน้าต่อเนื่อง การเปลี่ยนข้ามช่วงตลาดปิด (เช่น ข้ามคืนของหุ้น) ไม่นับ" + ("" if one else " เลือกหลายตัวคือค่าเฉลี่ยของแต่ละตัว"))),
    (CARDS[3], common.money(trading_z.max()),
     common.explain("ชั่วโมงที่ปริมาณซื้อขายพุ่งผิดปกติที่สุด พุ่งแค่ไหน (เป็นปริมาณซื้อขายของราคา ไม่ใช่ปริมาณ Reddit)",
                    "ปริมาณซื้อขายชั่วโมงนั้น เทียบ 24 ชั่วโมงก่อนหน้า ไม่รวมชั่วโมงปัจจุบัน (สูตรเดียวกับ Z-score ของ Reddit) แล้วเลือกค่าสูงสุดของช่วง"
                    + ("" if one else " เลือกหลายตัวคือค่าสูงสุดของทุกตัว"), common.TRADING_Z_NOTE)),
    (CARDS[4], common.money(natr.mean()),
     common.explain("ราคาแกว่งแรงแค่ไหนต่อชั่วโมง คิดเป็น % ของราคา (ใช้เทียบข้ามสินทรัพย์ได้)",
                    "ATR (ระยะที่ราคาแกว่งเฉลี่ยใน 24 ชั่วโมงล่าสุด) ÷ ราคาปิด × 100 แล้วเฉลี่ยทั้งช่วงที่เลือก" + ("" if one else " เลือกหลายตัวคือค่าเฉลี่ยของแต่ละตัว")))])

# ---- the price and the trading volume at the chosen level of time.  One asset: its close and its volume.  Several: the assets are not all traded in the same
# hours (stocks sleep at night and on weekends), so an average of their LEVELS would jump whenever the set of traded assets changes; instead the mean Current
# Return of the assets traded in the hour is drawn (the Current Return chart: a % needs no index, since 2026-11-15) and the trading volume, the RSI and the Normalized ATR are the mean of the assets traded in the hour, as on Price and Return.
hourly = hourly.assign(hour_utc=hourly.hour_utc.astype(int), abs_return=hourly.log_return.abs())      # the size of the move of each asset in the hour, before any average
if one:
    market = common.resample(hourly.copy(), {"close": "last", "volume": "sum", "abs_return": "mean", "rsi": "last", "atr": "last", "normalized_atr": "mean"}, how)
    price_col, price_title = "close", "ราคาปิด (USD)"
    volume_raw_title, rsi_title, natr_title = "ปริมาณซื้อขาย (หน่วย)", "RSI", "Normalized ATR (%)"
    volume_raw_col = "volume"
else:
    mean_volume = hourly.groupby("ticker").volume.transform("mean")
    hourly = hourly.assign(volume_index=100.0 * hourly.volume / mean_volume.where(mean_volume > 0))                  # the volume of each asset against its own mean (= 100)
    by_hour = hourly.groupby("hour_utc").agg(volume_index=("volume_index", "mean"), abs_return=("abs_return", "mean"), rsi=("rsi", "mean"), natr=("normalized_atr", "mean"), time=("time", "first")).sort_index()
    market = common.resample(by_hour.reset_index(), {"abs_return": "mean", "volume_index": "mean", "rsi": "last", "natr": "mean"}, how).rename(columns={"natr": "normalized_atr"})
    price_col, price_title = None, None                                                              # several assets: no price level (see the Current Return chart)
    volume_raw_title, rsi_title, natr_title = "ปริมาณซื้อขาย (เฉลี่ยของที่เลือก)", "RSI (เฉลี่ยของที่เลือก)", "Normalized ATR (เฉลี่ยของที่เลือก)"      # the same names as on Price and Return
    volume_raw_col = "volume_index"
reddit_shown = common.resample(reddit.drop(columns=["hour_utc"], errors="ignore"), {"texts": "sum", "zscore": "max"}, how) if not reddit.empty else pd.DataFrame(columns=["time", "texts", "zscore"])
mention_shown = common.resample(mentions[["time", "mentions"]], {"mentions": "sum"}, how) if not mentions.empty else pd.DataFrame(columns=["time", "mentions"])
merged = market.merge(reddit_shown[["time", "texts", "zscore"]], on="time", how="left").merge(mention_shown, on="time", how="left")
merged["texts"] = merged.texts.fillna(0)
merged["mentions"] = merged.mentions.fillna(0)                                   # nobody mentioned the assets = a real 0

# ---- every chart: one price measure against the message volume (red) and the mentions of the ticked assets (teal); a tick box per line hides it
REDDIT_LINES = [("texts", "ปริมาณข้อความ", common.C_REDDIT, ",.0f"), ("mentions", "ปริมาณการกล่าวถึงสินทรัพย์", common.C_RATE, ",.0f")]

block("|Current Return| (%) เทียบกับปริมาณ Reddit", "ใช้ตรวจสอบว่าราคาขยับแรงแค่ไหน (ไม่สนว่าขึ้นหรือลง) แล้วตรงกับช่วงที่ Reddit Volume ขึ้นหรือลงหรือเปล่า",
      how="ขนาดของ ln(ราคาปิดชั่วโมงนี้ ÷ ราคาปิดชั่วโมงก่อน) × 100")
common.overlay_chart(merged, "time", "abs_return", "|Current Return| (%)", common.C_PRICE, REDDIT_LINES, "pr_return", "|Current Return|", left_fmt=".3f", left_zero=True)

if one:
    block("ราคาปิด เทียบกับปริมาณ Reddit", "ใช้ตรวจสอบว่าราคาเคลื่อนไหวไปพร้อมกับช่วงที่ Reddit Volume ขึ้นหรือลงหรือเปล่า (แสดงเมื่อเลือกสินทรัพย์ตัวเดียว)",
          how="ราคาปิดของสินทรัพย์ที่เลือก")
    common.overlay_chart(merged, "time", price_col, price_title, common.C_PRICE, REDDIT_LINES, "pr_price", "ราคาปิด")

block("ปริมาณซื้อขาย เทียบกับปริมาณ Reddit", "ใช้ตรวจสอบว่าช่วงที่ซื้อขายคึกคัก ตรงกับช่วงที่ Reddit Volume ขึ้นหรือลงหรือเปล่า",
      how=("จำนวนหุ้นหรือเหรียญที่ซื้อขายกันในชั่วโมงนั้น"))
common.overlay_chart(merged, "time", volume_raw_col, volume_raw_title, common.C_VOLUME, REDDIT_LINES, "pr_volume", "ปริมาณซื้อขาย")

block("RSI เทียบกับปริมาณ Reddit", "ใช้ตรวจสอบว่าราคาขึ้นหรือลงต่อเนื่องแค่ไหน ตรงกับช่วงที่ Reddit Volume ขึ้นหรือลงหรือเปล่า (0–100: เกิน 70 = ขึ้นต่อเนื่องมาก เรียกว่า ซื้อมากเกินไป, ต่ำกว่า 30 = ลงต่อเนื่องมาก เรียกว่า ขายมากเกินไป)",
      how="ดูราคาปิด 14 ชั่วโมงล่าสุด แยกชั่วโมงที่ขึ้นกับชั่วโมงที่ลง หาค่าเฉลี่ยของการขึ้นและการลง แล้ว RSI = 100 − 100 ÷ (1 + เฉลี่ยขึ้น ÷ เฉลี่ยลง)")
common.overlay_chart(merged, "time", "rsi", rsi_title, common.C_RSI, REDDIT_LINES, "pr_rsi", "RSI", left_fmt=".1f")

block("Normalized ATR เทียบกับปริมาณ Reddit", "ใช้ตรวจสอบว่าช่วงที่ราคาแกว่งแรง (เป็น % ของราคา) ตรงกับช่วงที่ Reddit Volume ขึ้นหรือลงหรือเปล่า",
      how="ATR (ระยะที่ราคาแกว่งเฉลี่ยต่อชั่วโมงใน 24 ชั่วโมงล่าสุด) ÷ ราคาปิด × 100 ใช้เทียบข้ามสินทรัพย์ได้")
common.overlay_chart(merged, "time", "normalized_atr", natr_title, common.C_NATR, REDDIT_LINES, "pr_natr", "Normalized ATR", left_fmt=".3f")

if one:
    block("ATR (USD)", "ใช้ตรวจสอบระยะที่ราคาแกว่งเฉลี่ยเป็นดอลลาร์ต่อชั่วโมง (แสดงเมื่อเลือกสินทรัพย์ตัวเดียว เนื่องจากหน่วยเป็นดอลลาร์ จึงเฉลี่ยข้ามสินทรัพย์ไม่ได้)",
          how="แต่ละชั่วโมงดูระยะแกว่ง = ราคาสูงสุด − ราคาต่ำสุด (รวมช่องว่างจากราคาปิดชั่วโมงก่อนถ้าห่างกว่า) แล้วเฉลี่ย 24 ชั่วโมงล่าสุด")
    common.show(common.line(market, "time", "atr", "ATR (USD)", common.C_ATR, y_zero=True), width="stretch")

# ---- the measures of every ticked ticker
block("รายละเอียดข้อมูล รายสินทรัพย์", "ใช้ตรวจสอบข้อมูลของแต่ละสินทรัพย์ที่เลือก (คลิกหัวคอลัมน์เพื่อเรียงลำดับ)")
snap = q("ticker_snapshot", start, end, tickers)
snap["สินทรัพย์"] = snap.ticker.map(lambda s: "%s (%s)" % (s, names.get(s, "")))
snap["กลุ่ม"] = snap.big_group.map(GROUP_LABELS)
snap["rows"] = snap.ticker.map(hourly.groupby("ticker").size())                      # the hourly price rows of the asset in the range (the rows its numbers are made of)
rsi_zones = hourly.dropna(subset=["rsi"]).groupby("ticker").rsi.agg(over70=lambda s: (s > 70).mean(), under30=lambda s: (s < 30).mean())
snap = snap.merge(rsi_zones, left_on="ticker", right_index=True, how="left")
measures = snap[["สินทรัพย์", "กลุ่ม", "rows", "last_close", "last_rsi", "over70", "under30", "mean_normalized_atr_pct",
                 "fr_now", "fr_1h", "fr_2h", "fr_3h", "fr_6h", "fr_12h"]].rename(columns={
    "rows": "จำนวนแถวข้อมูล (ชั่วโมง)", "last_close": "ราคาปิดล่าสุด (USD)", "last_rsi": "RSI ล่าสุด", "over70": "สัดส่วน RSI > 70", "under30": "สัดส่วน RSI < 30",
    "mean_normalized_atr_pct": "Normalized ATR เฉลี่ย (%)",
    "fr_now": "ผลตอบแทน Current (%)", "fr_1h": "1h (%)", "fr_2h": "2h (%)", "fr_3h": "3h (%)", "fr_6h": "6h (%)", "fr_12h": "12h (%)"})
formats = {c: "{:.4f}" for c in measures.columns if c not in ("สินทรัพย์", "กลุ่ม")}
formats["ราคาปิดล่าสุด (USD)"] = "{:,.2f}"
formats["จำนวนแถวข้อมูล (ชั่วโมง)"] = "{:,.0f}"
st.dataframe(measures.style.format(formats, na_rep="-"), hide_index=True, width="stretch", height=min(420, 60 + 36 * len(snap)))      # a missing value shows "-", never None
