"""Home page of the dashboard (the first tab of dashboard/app.py, which holds the navigation).  Start with:   streamlit run dashboard/app.py

Seven content pages live in dashboard/pages/ (the tabs at the top list them):
  1 Reddit Volume          proposal 7.1-1   all posts + comments per hour and its Z-score (source + multi-ticker filters)
  2 Ticker Mentions        proposal 7.1-2   how often each asset is mentioned, mention rate (source + multi-ticker filters)
  3 Price and Return       proposal 7.2-1   close, volume, future returns, volatility
  4 Market and Sentiment   proposal 7.5-1   price next to Reddit sentiment, ratios, majority status
  5 Statistical Analysis   proposal 7.5-2   p-values, win rate (live); Logistic Regression is page 9 (trained live, EXTENSION placement)
  7 Hot Events             EXTENSION        detected signal list (proposal 7.6): thresholds from the sidebar, returns after each signal (not a trading signal)
"""

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # streamlit only adds dashboard/ to the path

import pandas as pd  # noqa: E402
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
     "ข้อความทั้งหมดของ 6 ชุมชนในช่วงเวลาที่เลือก (ไม่แยกตามกลุ่มสินทรัพย์ เนื่องจากข้อความหนึ่งมิได้เป็นของสินทรัพย์กลุ่มใดกลุ่มหนึ่ง)"),
    ("สินทรัพย์ที่เลือก", str(int(by_group.tickers.sum()) if not by_group.empty else 0), None),
    ("จำนวนชั่วโมงที่มีราคา (รวมทุกสินทรัพย์)", "{:,}".format(price_hours),
     "นับชั่วโมงที่มีราคาของแต่ละสินทรัพย์แล้วบวกกัน ไม่นับช่วงที่ตลาดปิด"),
    ("ชั่วโมงที่มีการกล่าวถึงสินทรัพย์", "{:,}".format(talked),
     "นับจากชั่วโมงที่มีราคา โดยชั่วโมงนั้นต้องมีโพสต์หรือความคิดเห็นอย่างน้อย 1 ข้อความที่กล่าวถึงสินทรัพย์ตัวนั้น"
     + (" (%.0f%% ของชั่วโมงที่มีราคา)" % (100.0 * talked / price_hours) if price_hours else ""))])
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
แถบด้านซ้ายคือตัวกรอง (เวลา แหล่งข้อมูล และสินทรัพย์) ส่วนบนของหน้าคือการ์ดตัวเลขสรุป และส่วนล่างคือกราฟและตาราง ค่าที่เลือกในตัวกรองจะคงอยู่เมื่อเปลี่ยนหน้า (ยกเว้นหน้า Hot Events ซึ่งไม่มีตัวกรองและใช้ข้อมูลทั้งหมด)

**ภาพรวมของแต่ละแดชบอร์ด**

**Reddit Volume** ปริมาณโพสต์และความคิดเห็นรายชั่วโมงในชุมชน Reddit ทั้ง 6 แห่ง พร้อม Reddit Volume Z-score ซึ่งบอกว่าปริมาณในชั่วโมงนั้นผิดปกติเมื่อเทียบกับ 24 ชั่วโมงก่อนหน้าเพียงใด

**Ticker Mentions** ความถี่ที่แต่ละสินทรัพย์ถูกกล่าวถึง (Ticker Mention Count) และสัดส่วนของการกล่าวถึงต่อปริมาณข้อความทั้งหมด (Ticker Mention Rate)

**Price and Return** ราคาปิด ปริมาณซื้อขาย ผลตอบแทนของชั่วโมงเดียวกัน (Current Return) ผลตอบแทนล่วงหน้า 1, 2, 3, 6 และ 12 ชั่วโมง และตัวชี้วัดความผันผวน (RSI, ATR)

**Price and Reddit** (ส่วนขยาย) ราคา ปริมาณซื้อขาย และตัวชี้วัดความผันผวน เทียบกับปริมาณ Reddit บนแกนเวลาเดียวกัน

**Market and Sentiment** ค่าความรู้สึกเฉลี่ยรายชั่วโมง สัดส่วนความรู้สึกเชิงบวก เชิงลบ และเป็นกลาง และประเภทความรู้สึกส่วนใหญ่ เทียบกับราคา

**Statistical Analysis** ความสัมพันธ์ระหว่างความรู้สึกกับผลตอบแทน (Win Rate, Spearman และ Pearson) คำนวณตามตัวกรองที่เลือก และเปรียบเทียบกลุ่มข้อมูลตามตารางที่ 12 ของข้อเสนอโครงการได้

**Logistic Regression** (ส่วนขยาย) แบบจำลองที่ทำนายทิศทางผลตอบแทนจากตัวแปรความรู้สึก แสดง AUC และสัมประสิทธิ์ของตัวแปร

**Hot Events** (ส่วนขยาย) รายการชั่วโมงที่ผิดปกติ จัดระดับ low / medium / high ด้วยคะแนนจาก KPI ที่ผู้ใช้กำหนดเกณฑ์ได้ พร้อมสถิติย้อนหลังของสินทรัพย์ ใช้ข้อมูลทั้งหมดโดยไม่มีตัวกรองด้านซ้าย
""")
st.info("ชั่วโมงที่ไม่มีการกล่าวถึงสินทรัพย์ใดจะไม่มีค่าความรู้สึก กราฟจึงขาดเป็นช่วง ๆ "
        "(ไม่นับเป็น 0 เนื่องจาก 0 หมายถึงความรู้สึกเป็นกลาง)  \nหุ้นและ ETF ไม่มีผลตอบแทนล่วงหน้า 12 ชั่วโมง เนื่องจากตลาดปิดในช่วงกลางคืน")
