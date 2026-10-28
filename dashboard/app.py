"""Home page of the dashboard.  Start with:   streamlit run dashboard/app.py

Six content pages live in dashboard/pages/ (the sidebar menu lists them):
  1 Reddit Volume          proposal 7.1-1   all posts + comments per hour and its Z-score (source + multi-ticker filters)
  2 Ticker Mentions        proposal 7.1-2   how often each asset is mentioned, mention rate (source + multi-ticker filters)
  3 Price and Return       proposal 7.2-1   close, volume, future returns, volatility
  4 Market and Sentiment   proposal 7.5-1   price next to Reddit sentiment, ratios, majority status
  5 Ranking and Signals    proposal 7.5-2   win-rate ranking + adjustable signal thresholds (7.6)
  6 Hot Events             EXTENSION        busy + clearly directional hours and what the price did next (not a signal)
"""

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # streamlit only adds dashboard/ to the path

import streamlit as st  # noqa: E402

from dashboard import common  # noqa: E402
from dashboard.common import q

common.setup("Reddit Sentiment × Securities Price", "🏠")
_, start, end, groups = common.sidebar(need_ticker=False)

info = q("data_range")
by_group = q("overview_filtered", start, end, tuple(groups))          # follows the date range and the asset classes
texts = q("texts_in_range", start, end)                               # market-wide, follows the date range only
day = lambda e: dt.datetime.fromtimestamp(e, dt.timezone.utc).date()

price_hours = int(by_group.price_hours.sum()) if not by_group.empty else 0
talked = int(by_group.talked_hours.sum()) if not by_group.empty else 0
common.kpi_cards([
    ("ข้อความที่วิเคราะห์ความรู้สึกแล้ว", "{:,}".format(int(texts)),
     "ข้อความทั้งหมดของ 6 ชุมชนในช่วงเวลาที่เลือก (ไม่แยกตามกลุ่มสินทรัพย์ เพราะข้อความหนึ่งไม่ได้เป็นของสินทรัพย์กลุ่มใดกลุ่มหนึ่ง)"),
    ("สินทรัพย์ที่เลือก", str(int(by_group.tickers.sum()) if not by_group.empty else 0), None),
    ("จำนวนชั่วโมงที่มีราคา (รวมทุกสินทรัพย์)", "{:,}".format(price_hours),
     "นับชั่วโมงที่มีราคาของแต่ละสินทรัพย์แล้วบวกกัน ไม่นับช่วงที่ตลาดปิด"),
    ("ชั่วโมงที่มีคนพูดถึงสินทรัพย์นั้น", "{:,}".format(talked),
     "นับจากชั่วโมงที่มีราคา: ชั่วโมงนั้นมีโพสต์หรือความคิดเห็นอย่างน้อย 1 ข้อความที่พูดถึงสินทรัพย์ตัวนั้น",
     "%.0f%% ของชั่วโมงที่มีราคา" % (100.0 * talked / price_hours) if price_hours else None)])
st.subheader("ภาพรวมตามตัวกรอง")
st.caption("ช่วง %s ถึง %s (UTC)  \nกลุ่ม: %s" % (day(start), day(end), ", ".join(common.group_name(g) for g in groups)))
if not by_group.empty:
    table = by_group.assign(กลุ่ม=by_group.big_group.map(common.group_name))
    order = {common.GROUP_LABELS[k]: i for i, k in enumerate(common.GROUP_LABELS)}
    table = table.sort_values("กลุ่ม", key=lambda s: s.map(order))
    common.table(table[["กลุ่ม", "tickers", "price_hours", "talked_hours"]].rename(columns={
        "tickers": "สินทรัพย์", "price_hours": "ชั่วโมงที่มีราคา", "talked_hours": "ชั่วโมงที่มีคนพูดถึง"}),
        hide_index=True, width="stretch")
st.caption("ช่วงข้อมูลทั้งหมด (ไม่ขึ้นกับตัวกรอง): Reddit %s ถึง %s  \nราคา %s ถึง %s (UTC)"
           % (day(info["reddit_lo"]), day(info["reddit_hi"]), day(info["market_lo"]), day(info["market_hi"])))

st.subheader("วิธีใช้")
st.markdown("""
- ทุกหน้าเปิดด้วย**การ์ดตัวเลขสรุป**ด้านบนสุด ตามด้วยกราฟที่เรียงลงมาทีละอัน (ไม่แบ่งครึ่งหน้า) กราฟแต่ละอันมีปุ่มสลับ **เส้น / แท่ง** ของตัวเอง
- ตัวกรองที่แถบด้านซ้ายหน้าตาเหมือนกันทั้งหมด (หัวข้อมิติ › ชื่อระดับ › ช่องติ๊กหรือรายการเลือก) เรียงตามมิติ: **เวลา** (ช่วงวันที่ ค่าเริ่มต้นย้อนหลัง 1 ปี และระดับเวลาของกราฟ) › **แหล่งข้อมูล** (ชุมชนและโพสต์/ความคิดเห็น ติ๊กไว้ทั้งหมดตอนแรก เฉพาะหน้า Reddit Volume และ Ticker Mentions) › **หลักทรัพย์** (กลุ่มสินทรัพย์ › สัญลักษณ์; ติ๊กกลุ่มแล้วติ๊กทั้งกลุ่ม; หน้า Reddit Volume, Ticker Mentions และ Price and Return ติ๊กได้หลายตัว ติ๊กไว้ทั้งหมดตอนแรก หน้า Market and Sentiment เลือกตัวเดียว)
- หน้า Price and Return มีสองมิติตาม proposal 7.2 คือ เวลา และหลักทรัพย์
- **Reddit Volume**: ปริมาณโพสต์และความคิดเห็นทั้งหมด (ถ้าเลือกหลักทรัพย์บางตัว จะแสดงจำนวนครั้งที่ตัวเหล่านั้นถูกพูดถึงแทน) และ Z-score เทียบกับ 24 ชั่วโมงก่อนหน้า (ไม่รวมชั่วโมงปัจจุบัน)
- **Ticker Mentions**: อันดับสินทรัพย์ที่ถูกพูดถึง แนวโน้มของสินทรัพย์ที่เลือก และสัดส่วนการพูดถึง
- **Price and Return**: ราคาปิด ปริมาณซื้อขาย ผลตอบแทนล่วงหน้า 1/2/3/6/12 ชั่วโมง และความผันผวน
- **Market and Sentiment**: ราคาเทียบกับค่าความรู้สึกเฉลี่ย สัดส่วนบวก/ลบ/กลาง และประเภทความรู้สึกส่วนใหญ่
- **Ranking and Signals**: จัดอันดับด้วย Historical Win Rate และปรับเกณฑ์สัญญาณ (Z-score / Sentiment / Horizon) ได้ทันที
""")
st.info("ชั่วโมงไหนที่ไม่มีใครพูดถึงสินทรัพย์ตัวนั้น จะไม่มีค่าความรู้สึก กราฟจึงขาดเป็นช่วง ๆ "
        "(ไม่นับเป็น 0 เพราะ 0 หมายถึงเป็นกลาง) ส่วนหุ้น/ETF ไม่มีผลตอบแทนล่วงหน้า 12 ชั่วโมง เพราะตลาดปิดกลางคืน")
