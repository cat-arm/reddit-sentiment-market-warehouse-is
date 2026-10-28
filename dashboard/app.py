"""Home page of the dashboard.  Start with:   streamlit run dashboard/app.py

Six content pages live in dashboard/pages/ (the sidebar menu lists them):
  1 Reddit Volume          proposal 7.1-1   all posts + comments per hour (or only what mentions a ticker), Z-score, drill-down
  2 Ticker Mentions        proposal 7.1-2   how often each asset is mentioned, mention rate, drill-down on time / source / ticker
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

st.subheader("ภาพรวมตามตัวกรอง")
st.caption("ช่วง %s ถึง %s (UTC)  \nกลุ่ม: %s" % (day(start), day(end), ", ".join(common.group_name(g) for g in groups)))
price_hours = int(by_group.price_hours.sum()) if not by_group.empty else 0
talked = int(by_group.talked_hours.sum()) if not by_group.empty else 0
c1, c2, c3, c4 = st.columns(4)
c1.metric("ข้อความที่วิเคราะห์ความรู้สึกแล้ว", "{:,}".format(int(texts)),
          help="ข้อความทั้งหมดของ 6 ชุมชนในช่วงเวลาที่เลือก (ไม่แยกตามกลุ่มสินทรัพย์ เพราะข้อความหนึ่งไม่ได้เป็นของสินทรัพย์กลุ่มใดกลุ่มหนึ่ง)")
c2.metric("สินทรัพย์ที่เลือก", int(by_group.tickers.sum()) if not by_group.empty else 0)
c3.metric("จำนวนชั่วโมงที่มีราคา (รวมทุกสินทรัพย์)", "{:,}".format(price_hours),
          help="นับชั่วโมงที่มีราคาของแต่ละสินทรัพย์แล้วบวกกัน ไม่นับช่วงที่ตลาดปิด")
c4.metric("ชั่วโมงที่มีคนพูดถึงสินทรัพย์นั้น", "{:,}".format(talked),
          delta="%.0f%% ของชั่วโมงที่มีราคา" % (100.0 * talked / price_hours) if price_hours else None, delta_color="off",
          help="นับจากชั่วโมงที่มีราคา: ชั่วโมงนั้นมีโพสต์หรือความคิดเห็นอย่างน้อย 1 ข้อความที่พูดถึงสินทรัพย์ตัวนั้น")
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
- เลือก **กลุ่มสินทรัพย์ / Ticker / ช่วงเวลา (ค่าเริ่มต้นย้อนหลัง 1 ปี) / ความละเอียด (ชั่วโมง วัน สัปดาห์ เดือน ปี)** ที่แถบด้านซ้าย ตัวกรองนี้ใช้ร่วมกันทุกหน้า
- หน้า Reddit Volume และ Ticker Mentions มีตัวกรอง **แหล่งข้อมูล** เพิ่ม (ชุมชน และโพสต์/ความคิดเห็น) และมีส่วน **เจาะลึกตามมิติ (Drill-down)** ลงทีละระดับ: เวลา ปี › เดือน › สัปดาห์ › วัน › ชั่วโมง, แหล่งข้อมูล แพลตฟอร์ม › ชุมชน › ประเภท, หลักทรัพย์ กลุ่ม › สัญลักษณ์
- **Reddit Volume**: ปริมาณโพสต์และความคิดเห็นทั้งหมด (หรือเฉพาะที่พูดถึงสินทรัพย์ที่เลือก) และ Z-score เทียบกับ 24 ชั่วโมงก่อนหน้า (ไม่รวมชั่วโมงปัจจุบัน)
- **Ticker Mentions**: อันดับสินทรัพย์ที่ถูกพูดถึง แนวโน้มของสินทรัพย์ที่เลือก และสัดส่วนการพูดถึง
- **Price and Return**: ราคาปิด ปริมาณซื้อขาย ผลตอบแทนล่วงหน้า 1/2/3/6/12 ชั่วโมง และความผันผวน
- **Market and Sentiment**: ราคาเทียบกับค่าความรู้สึกเฉลี่ย สัดส่วนบวก/ลบ/กลาง และประเภทความรู้สึกส่วนใหญ่
- **Ranking and Signals**: จัดอันดับด้วย Historical Win Rate และปรับเกณฑ์สัญญาณ (Z-score / Sentiment / Horizon) ได้ทันที
""")
st.info("ชั่วโมงไหนที่ไม่มีใครพูดถึงสินทรัพย์ตัวนั้น จะไม่มีค่าความรู้สึก กราฟจึงขาดเป็นช่วง ๆ "
        "(ไม่นับเป็น 0 เพราะ 0 หมายถึงเป็นกลาง) ส่วนหุ้น/ETF ไม่มีผลตอบแทนล่วงหน้า 12 ชั่วโมง เพราะตลาดปิดกลางคืน")
