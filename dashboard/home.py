"""Home page of the dashboard (the first tab of dashboard/app.py, which holds the navigation).  Start with:   streamlit run dashboard/app.py

Seven content pages live in dashboard/pages/ (the tabs at the top list them):
  1 Reddit Volume and Ticker Mentions   proposal 7.1   all posts + comments per hour and its Z-score (never depends on the asset filter), then how often
                           the ticked assets are mentioned, mention rate (source + multi-ticker filters)
  3 Price and Return       proposal 7.2-1   close, volume, RSI, ATR next to the Reddit volume (Price and Reddit was merged into it 2026-11-15), future returns, volatility
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

common.setup("ความรู้สึกบน Reddit เทียบกับราคาหลักทรัพย์ (Reddit Sentiment × Securities Price)", "🏠")
_, start, end, groups = common.sidebar()

info = q("data_range")
by_group = q("overview_filtered", start, end, tuple(groups))          # follows the date range and the asset classes
texts = q("texts_in_range", start, end)                               # market-wide, follows the date range only
day = lambda e: dt.datetime.fromtimestamp(e, dt.timezone.utc).date()

price_hours = int(by_group.price_hours.sum()) if not by_group.empty else 0
talked = int(by_group.talked_hours.sum()) if not by_group.empty else 0
common.kpi_cards([
    ("ข้อความที่วิเคราะห์ความรู้สึกแล้ว", "{:,}".format(int(texts)),
     common.explain("จำนวนโพสต์และความคิดเห็นของ 6 ชุมชนที่ผ่านการคัดกรองและวัดความรู้สึกแล้ว ในช่วงเวลาที่เลือก",
                    "นับทุกข้อความในช่วงเวลาที่เลือก ไม่แยกตามกลุ่มสินทรัพย์ เพราะข้อความหนึ่งไม่ได้เป็นของสินทรัพย์กลุ่มใดกลุ่มหนึ่ง")),
    ("สินทรัพย์ที่เลือก", str(int(by_group.tickers.sum()) if not by_group.empty else 0),
     common.explain("จำนวนสินทรัพย์ในกลุ่มที่ติ๊กไว้ที่แถบด้านซ้าย", "นับสินทรัพย์ของกลุ่มที่เลือก จากทั้งหมด 34 ตัว")),
    ("จำนวนชั่วโมงที่มีราคา (รวมทุกสินทรัพย์)", "{:,}".format(price_hours),
     common.explain("จำนวนชั่วโมงที่มีการซื้อขายจริง (มีราคา) รวมทุกสินทรัพย์ที่เลือก",
                    "นับชั่วโมงที่มีราคาของแต่ละสินทรัพย์ แล้วบวกกัน ไม่นับช่วงตลาดปิด เช่น หุ้นช่วงกลางคืนและวันเสาร์อาทิตย์")),
    ("ชั่วโมงที่มีการกล่าวถึงสินทรัพย์", "{:,}".format(talked),
     common.explain("จำนวนชั่วโมงที่มีคนพูดถึงสินทรัพย์ใน Reddit",
                    "นับเฉพาะชั่วโมงที่มีราคา และมีข้อความอย่างน้อย 1 ข้อความพูดถึงสินทรัพย์ตัวนั้น"
                    + (" (คิดเป็น %.0f%% ของชั่วโมงที่มีราคา)" % (100.0 * talked / price_hours) if price_hours else "")))])
common.block("ภาพรวมตามตัวกรอง", "ใช้ตรวจสอบจำนวนสินทรัพย์ ชั่วโมงที่มีราคา และชั่วโมงที่มีการกล่าวถึง แยกตามกลุ่มสินทรัพย์",
             how="ชั่วโมงที่มีราคา = ชั่วโมงที่มีการซื้อขายจริง · ชั่วโมงที่มีคนพูดถึง = ชั่วโมงที่มีราคาและมีข้อความอย่างน้อย 1 ข้อความพูดถึงสินทรัพย์นั้น")
st.caption("ช่วงเวลา %s ถึง %s (UTC)  \nกลุ่มสินทรัพย์ %s" % (day(start), day(end), ", ".join(common.group_name(g) for g in groups)))
if not by_group.empty:
    table = by_group.assign(กลุ่ม=by_group.big_group.map(common.group_name))
    order = {common.GROUP_LABELS[k]: i for i, k in enumerate(common.GROUP_LABELS)}
    table = table.sort_values("กลุ่ม", key=lambda s: s.map(order))
    common.table(table[["กลุ่ม", "tickers", "price_hours", "talked_hours"]].rename(columns={
        "tickers": "สินทรัพย์", "price_hours": "ชั่วโมงที่มีราคา", "talked_hours": "ชั่วโมงที่มีคนพูดถึง"}),
        hide_index=True, width="stretch")

st.subheader("วิธีใช้")
st.markdown("""
แถบด้านซ้ายคือตัวกรอง ส่วนบนคือการ์ดตัวเลขสรุป และส่วนล่างคือกราฟและตาราง

**ภาพรวมของแต่ละแดชบอร์ด**

**Reddit Volume and Ticker Mentions** ปริมาณข้อความรายชั่วโมงในชุมชน Reddit ทั้ง 6 แห่ง พร้อม Reddit Volume Z-score ซึ่งบอกว่าปริมาณในชั่วโมงนั้นผิดปกติเมื่อเทียบกับ 24 ชั่วโมงก่อนหน้าเพียงใด และความถี่ที่แต่ละสินทรัพย์ถูกกล่าวถึง (Ticker Mention Count) พร้อมสัดส่วนต่อปริมาณข้อความทั้งหมด (Ticker Mention Rate)

**Price and Return** ราคาปิด ปริมาณซื้อขาย และตัวชี้วัดความผันผวน (RSI, ATR) เทียบกับปริมาณ Reddit บนแกนเวลาเดียวกัน พร้อมผลตอบแทนของชั่วโมงเดียวกัน (Current Return) และผลตอบแทนล่วงหน้า 1, 2, 3, 6 และ 12 ชั่วโมง

**Market and Sentiment** ค่าความรู้สึกเฉลี่ยรายชั่วโมง สัดส่วนความรู้สึกเชิงบวก เชิงลบ และเป็นกลาง และประเภทความรู้สึกส่วนใหญ่ เทียบกับราคา

**Statistical Analysis** ความสัมพันธ์ระหว่างความรู้สึกกับผลตอบแทน (Win Rate, Spearman และ Pearson) คำนวณตามตัวกรองที่เลือก และเปรียบเทียบกลุ่มข้อมูลตามตารางที่ 12 ของข้อเสนอโครงการได้

**Logistic Regression** แบบจำลองที่ทำนายทิศทางผลตอบแทนจากตัวแปรความรู้สึก แบ่งเป็น 2 ส่วนแยกกัน คือ (1) แต่ละ panel ดีกว่าเดาสุ่มหรือไม่ ดูจาก AUC บนชุดทดสอบ และ (2) ตัวแปรใดช่วยเพิ่มการทำนาย (L1, เติมทีละตัว, ตัดทีละตัว)

**Hot Events** รายการชั่วโมงที่ผิดปกติ จัดระดับ low / medium / high ด้วยคะแนนจาก KPI ที่ผู้ใช้กำหนดเกณฑ์ได้ พร้อมสถิติย้อนหลังของสินทรัพย์ ใช้ข้อมูลทั้งหมดโดยไม่มีตัวกรองด้านซ้าย
""")
