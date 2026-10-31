"""Home page of the dashboard (the first tab of dashboard/app.py, which holds the navigation).  Start with:   streamlit run dashboard/app.py

Seven content pages live in dashboard/pages/ (the tabs at the top list them):
  1 Reddit Volume          proposal 7.1-1   all posts + comments per hour and its Z-score (source + multi-ticker filters)
  2 Ticker Mentions        proposal 7.1-2   how often each asset is mentioned, mention rate (source + multi-ticker filters)
  3 Price and Return       proposal 7.2-1   close, volume, future returns, volatility
  4 Market and Sentiment   proposal 7.5-1   price next to Reddit sentiment, ratios, majority status
  5 Statistical Analysis   proposal 7.5-2   p-values, win rate, logistic regression
  6 Lead and Lag           EXTENSION        whether sentiment or price changes first
  7 Hot Events             EXTENSION        detected signal list (proposal 7.6): thresholds from the sidebar, returns after each signal (not a trading signal)
"""

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # streamlit only adds dashboard/ to the path

import streamlit as st  # noqa: E402

from dashboard import common  # noqa: E402
from dashboard.common import q

common.setup("Reddit Sentiment × Securities Price", "🏠")
_, start, end, groups = common.sidebar()

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
    ("ชั่วโมงที่มีการกล่าวถึงสินทรัพย์", "{:,}".format(talked),
     "นับจากชั่วโมงที่มีราคา โดยชั่วโมงนั้นต้องมีโพสต์หรือความคิดเห็นอย่างน้อย 1 ข้อความที่กล่าวถึงสินทรัพย์ตัวนั้น",
     "%.0f%% ของชั่วโมงที่มีราคา" % (100.0 * talked / price_hours) if price_hours else None)])
st.subheader("ภาพรวมตามตัวกรอง")
st.caption("ช่วงเวลา %s ถึง %s (UTC)  \nกลุ่มสินทรัพย์ %s" % (day(start), day(end), ", ".join(common.group_name(g) for g in groups)))
if not by_group.empty:
    table = by_group.assign(กลุ่ม=by_group.big_group.map(common.group_name))
    order = {common.GROUP_LABELS[k]: i for i, k in enumerate(common.GROUP_LABELS)}
    table = table.sort_values("กลุ่ม", key=lambda s: s.map(order))
    common.table(table[["กลุ่ม", "tickers", "price_hours", "talked_hours"]].rename(columns={
        "tickers": "สินทรัพย์", "price_hours": "ชั่วโมงที่มีราคา", "talked_hours": "ชั่วโมงที่มีคนพูดถึง"}),
        hide_index=True, width="stretch")
st.caption("ช่วงข้อมูลทั้งหมด (ไม่ขึ้นกับตัวกรอง)  \nReddit %s ถึง %s  \nราคา %s ถึง %s (UTC)"
           % (day(info["reddit_lo"]), day(info["reddit_hi"]), day(info["market_lo"]), day(info["market_hi"])))

st.subheader("วิธีใช้")
st.markdown("""
ทุกหน้าเปิดด้วยการ์ดตัวเลขสรุป ตามด้วยกราฟที่เรียงลงมาทีละอัน กราฟแต่ละอันมีปุ่มสลับระหว่างเส้นและแท่งของตัวเอง

ตัวกรองที่แถบด้านซ้ายเรียงตามมิติ ได้แก่ เวลา (ช่วงวันที่ ค่าเริ่มต้นย้อนหลัง 1 ปี และระดับเวลาของกราฟ) แหล่งข้อมูล (ชุมชนและประเภทเนื้อหา เฉพาะบางหน้า) และหลักทรัพย์ (กลุ่มสินทรัพย์และสัญลักษณ์) ตอนเริ่มต้นทุกช่องถูกติ๊กไว้ทั้งหมด ค่าที่เลือกจะคงอยู่เมื่อเปลี่ยนหน้า

**Reddit Volume**
ปริมาณโพสต์และความคิดเห็นทั้งหมด หากเลือกหลักทรัพย์บางตัวจะแสดงจำนวนครั้งที่ตัวเหล่านั้นถูกกล่าวถึงแทน พร้อม Z-score เทียบกับ 24 ชั่วโมงก่อนหน้า (ไม่รวมชั่วโมงปัจจุบัน)

**Ticker Mentions**
อันดับสินทรัพย์ที่ถูกกล่าวถึง แนวโน้มของสินทรัพย์ที่เลือก และสัดส่วนการกล่าวถึง

**Price and Return**
ราคาปิด ปริมาณซื้อขาย ผลตอบแทนล่วงหน้า 1, 2, 3, 6 และ 12 ชั่วโมง และความผันผวน

**Market and Sentiment**
ราคาเทียบกับค่าความรู้สึกเฉลี่ย สัดส่วนบวก ลบ และเป็นกลาง และประเภทความรู้สึกส่วนใหญ่

**Statistical Analysis**
ความสัมพันธ์ระหว่างความรู้สึกกับผลตอบแทน (Win Rate, Spearman, Pearson) และ Logistic Regression

**Lead and Lag**
ตรวจว่าความรู้สึกหรือราคาเปลี่ยนก่อนกัน

**Hot Events**
รายการสัญญาณที่ตรวจพบตามเกณฑ์ Z-score, Sentiment และจำนวนข้อความขั้นต่ำ พร้อมผลตอบแทนหลังเกิดสัญญาณ
""")
st.info("ชั่วโมงที่ไม่มีการกล่าวถึงสินทรัพย์ตัวนั้นจะไม่มีค่าความรู้สึก กราฟจึงขาดเป็นช่วง ๆ "
        "(ไม่นับเป็น 0 เพราะ 0 หมายถึงความรู้สึกเป็นกลาง)  \nหุ้นและ ETF ไม่มีผลตอบแทนล่วงหน้า 12 ชั่วโมง เพราะตลาดปิดกลางคืน")
