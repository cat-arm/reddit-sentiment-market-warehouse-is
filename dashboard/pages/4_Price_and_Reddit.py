"""Dashboard 4  Price and Reddit  (EXTENSION, not in the proposal): the page Price and Return with the Reddit volume added to it.

The price of the chosen assets (one asset: its close; several: an index accumulated from their mean Current Return); the trading volume, the RSI and the Normalized ATR are drawn against a Reddit measure of the reader's choice (Reddit Volume or Ticker Mention Count); the Z-scores are only in the cards is drawn on the same time axis as the
Reddit volume of the market (all the posts and comments of the chosen sources) and its Z-score, and the trading volume next to the Reddit volume, so
one can see by eye what the price does when the Reddit volume rises.  Same filters as the page Price and Return plus the Reddit sources.
Data: market_hourly_features (prices) and reddit_volume_hourly (Reddit volume).  A look at two series that move together, never a cause.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard import common  # noqa: E402
from dashboard.common import q  # noqa: E402

CARDS = ["Reddit Volume รวม", "Reddit Volume Z-score สูงสุด", "Current Return รวมทั้งช่วง (%)", "Volume Z-score สูงสุด (ปริมาณซื้อขาย)"]

common.setup("Price and Reddit (ส่วนขยาย: ราคาเทียบปริมาณ Reddit)", "🔗")
_, start, end, _ = common.sidebar(sources=True, multi=True)
how = common.granularity(start, end, "g_price_reddit")
tickers = common.selected_tickers()
src_ids = common.selected_sources()
if not tickers or not src_ids:
    common.nothing_selected(CARDS, "ไม่ได้เลือกหลักทรัพย์หรือแหล่งข้อมูล จึงไม่มีข้อมูลแสดง")
one = len(tickers) == 1
st.caption("**ส่วนขยายนอก proposal:** หน้า Price and Return ที่เพิ่มปริมาณ Reddit (โพสต์และความคิดเห็นทั้งหมดของตลาดในแหล่งข้อมูลที่เลือก) ลงบนแกนเวลาเดียวกัน  \n"
           + ("แสดงราคาปิดของสินทรัพย์ที่เลือก" if one else "เลือกหลายตัวจึงแสดงดัชนีที่สะสมจากผลตอบแทนเฉลี่ยของทุกตัว (ชั่วโมงแรก = 100) เพราะแต่ละตัวซื้อขายไม่พร้อมกัน") + "  ดูด้วยตาว่าตอนปริมาณ Reddit สูงขึ้น ราคาเป็นอย่างไร เป็นแค่การเทียบ ไม่ใช่เหตุและผล")

hourly = q("price_series_for", tickers, start, end)
reddit = q("total_volume_series", start, end, src_ids)
mentions = q("mention_series", tickers, start, end, src_ids)                    # Ticker_mention_count of the chosen assets (the sources of the page)
if hourly.empty:
    st.info("ไม่มีข้อมูลราคาของหลักทรัพย์ที่เลือกในช่วงนี้ (ตลาดอาจปิด)")
    st.stop()

# ---- cards: the Current Return and the trading volume of the assets, the Reddit volume of the market
returns = hourly.groupby("ticker").log_return.sum()
trading_z = hourly.groupby("ticker").volume_zscore_24.max()
suffix = "" if one else " (เฉลี่ยของ %d ตัว)" % hourly.ticker.nunique()
common.kpi_cards([
    (CARDS[0], "{:,}".format(int(reddit.texts.sum())) if not reddit.empty else "0", "โพสต์และความคิดเห็นทั้งหมดของตลาดในแหล่งข้อมูลที่เลือก (ไม่แยกตามสินทรัพย์)"),
    (CARDS[1], common.money(reddit.zscore.max()) if not reddit.empty else "n/a", "Z-score ของปริมาณ Reddit ทั้งตลาดสูงสุดในช่วง เทียบ 24 ชั่วโมงก่อนหน้า ไม่รวมชั่วโมงปัจจุบัน" + common.REDDIT_Z_NOTE),
    (CARDS[2], common.money(returns.mean()), "ln(close_t ÷ close_t−1) × 100 รวมทุกชั่วโมงในช่วงที่เลือก (ผลรวมของ Current Return ส่วนขยาย)" + suffix),
    (CARDS[3], common.money(trading_z.max()), "Z-score ของปริมาณซื้อขายของราคา (ตารางที่ 8 ข้อ 2) สูงสุดในช่วง ไม่ใช่ปริมาณ Reddit" + ("" if one else " (สูงสุดของทุกตัวที่เลือก)") + common.TRADING_Z_NOTE)])

# ---- the price and the trading volume at the chosen level of time.  One asset: its close and its volume.  Several: the assets are not all traded in the same
# hours (stocks sleep at night and on weekends), so an average of their LEVELS would jump whenever the set of traded assets changes; instead the mean Current
# Return of the assets traded in the hour is accumulated into an index (first hour = 100) and the trading volume is the median Volume Z-score.
hourly = hourly.assign(hour_utc=hourly.hour_utc.astype(int))
if one:
    market = common.resample(hourly.copy(), {"close": "last", "volume": "sum", "rsi": "last", "normalized_atr": "mean"}, how)
    price_col, price_title = "close", "ราคาปิด (USD)"
    volume_raw_title, rsi_title, natr_title = "ปริมาณซื้อขาย (หน่วย)", "RSI", "Normalized ATR (%)"
    volume_raw_col = "volume"
else:
    mean_volume = hourly.groupby("ticker").volume.transform("mean")
    hourly = hourly.assign(volume_index=100.0 * hourly.volume / mean_volume.where(mean_volume > 0))                  # the volume of each asset against its own mean (= 100)
    by_hour = hourly.groupby("hour_utc").agg(volume_index=("volume_index", "median"), log_return=("log_return", "mean"), rsi=("rsi", "median"), natr=("normalized_atr", "median"), time=("time", "first")).sort_index()
    by_hour["price_index"] = 100.0 * (by_hour.log_return.fillna(0).cumsum() / 100.0).apply(lambda v: __import__("math").exp(v))
    market = common.resample(by_hour.reset_index(), {"price_index": "last", "volume_index": "mean", "rsi": "last", "natr": "mean"}, how).rename(columns={"natr": "normalized_atr"})
    price_col, price_title = "price_index", "ราคาปิด (เฉลี่ยของที่เลือก)"
    volume_raw_title, rsi_title, natr_title = "ปริมาณซื้อขาย (มัธยฐานของที่เลือก)", "RSI (มัธยฐานของที่เลือก)", "Normalized ATR (มัธยฐานของที่เลือก)"
    volume_raw_col = "volume_index"
reddit_shown = common.resample(reddit.drop(columns=["hour_utc"], errors="ignore"), {"texts": "sum", "zscore": "max"}, how) if not reddit.empty else pd.DataFrame(columns=["time", "texts", "zscore"])
mention_shown = common.resample(mentions[["time", "mentions"]], {"mentions": "sum"}, how) if not mentions.empty else pd.DataFrame(columns=["time", "mentions"])
merged = market.merge(reddit_shown[["time", "texts", "zscore"]], on="time", how="left").merge(mention_shown, on="time", how="left")
merged["texts"] = merged.texts.fillna(0)
merged["mentions"] = merged.mentions.fillna(0)                                   # nobody mentioned the assets = a real 0

# ---- which Reddit measure is drawn against the price measures: the three of the Reddit pages, each in its own colour
MEASURES = {"Reddit Volume": ("texts", "Reddit Volume (ครั้ง)", common.C_REDDIT, ",.4g"),
            "Ticker Mention Count": ("mentions", "Ticker Mention Count (ครั้ง)", common.C_REDDIT, ",.4g")}
picked = st.radio("เทียบกับ", list(MEASURES), horizontal=True, key="pr_reddit_measure")
r_col, r_title, r_color, r_fmt = MEASURES[picked]
st.caption("เลือกว่าจะเทียบกับ Reddit Volume (โพสต์และความคิดเห็นทั้งหมดของตลาด) หรือ Ticker Mention Count (จำนวนครั้งที่สินทรัพย์ที่เลือกถูกพูดถึง) ทุกกราฟด้านล่างเปลี่ยนตาม สีเส้นเหมือนหน้า Reddit Volume และ Ticker Mentions  \nZ-score ดูในการ์ดด้านบน")

st.subheader("ราคาเทียบ %s" % picked)
common.dual_chart(merged, "time", price_col, r_col, price_title, r_title, "pr_price", "ราคาปิด", picked, right_color=r_color, right_fmt=r_fmt, left_fmt=",.4g")
st.caption("สีน้ำเงินคือราคา อีกเส้นคือ Reddit ที่เลือก ดูว่าช่วงที่เส้น Reddit พุ่ง ราคาเป็นอย่างไร")

st.subheader("ปริมาณซื้อขายเทียบ %s" % picked)
common.dual_chart(merged, "time", volume_raw_col, r_col, volume_raw_title, r_title, "pr_volume", "ปริมาณซื้อขาย", picked,
                  left_color=common.C_VOLUME, right_color=r_color, left_fmt=",.4g", right_fmt=r_fmt)
st.caption("สีเขียวคือปริมาณซื้อขายของราคา" + ("" if one else " (เลือกหลายตัว: ปริมาณของแต่ละตัวเทียบกับค่าเฉลี่ยของตัวเอง = 100 แล้วเอามัธยฐานของที่เลือก เพราะแต่ละตัวมีหน่วยและขนาดต่างกัน)") + " ดูว่าปริมาณซื้อขายพุ่งพร้อมกับ Reddit ไหม ส่วน Z-score ของทั้งสองปริมาณดูในการ์ดด้านบน")

st.subheader("RSI เทียบ %s" % picked)
common.dual_chart(merged, "time", "rsi", r_col, rsi_title, r_title, "pr_rsi", "RSI", picked, left_color=common.C_RATE, right_color=r_color, left_fmt=".1f", right_fmt=r_fmt)
st.caption("สีม่วงคือ RSI (ดัชนีความแข็งแกร่งสัมพัทธ์ 0 ถึง 100 เกิน 70 มักอ่านว่าซื้อมากเกินไป ต่ำกว่า 30 ขายมากเกินไป)")

st.subheader("Normalized ATR เทียบ %s" % picked)
common.dual_chart(merged, "time", "normalized_atr", r_col, natr_title, r_title, "pr_natr", "Normalized ATR", picked, left_color=common.C_NATR, right_color=r_color, left_fmt=".3f", right_fmt=r_fmt)
st.caption("สีชมพูคือ Normalized ATR (ความผันผวนสัมพัทธ์ = ATR 24 ชั่วโมง ÷ ราคาปิด × 100) ดูว่าตอน Reddit คึกคัก ความผันผวนสูงขึ้นไหม")
st.warning("**ดูภาพรวมย้อนหลัง ไม่ใช่สัญญาณซื้อขาย**  \n"
           "เหตุการณ์ใหญ่ทำให้ทั้ง Reddit และราคาขยับพร้อมกัน จึงเห็นเส้นขึ้นลงไปด้วยกันได้โดยไม่ได้แปลว่าอย่างหนึ่งทำให้อีกอย่างขยับ")
