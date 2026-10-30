"""Step 33: ความรู้สึกรายชั่วโมงต่อ Ticker และทั้งตลาด แยกตามชุมชน × แบบจำลอง × variant -> reddit_hourly_community, reddit_hourly_global (P1b, DimSentimentSource)

Run:  python steps/33_reddit_hourly_community.py          (สร้างตารางใหม่ แล้วตรวจว่ารวมชุมชนแล้วเท่ากับ reddit_hourly)
      python steps/33_reddit_hourly_community.py --check-only
"""

from _run import module

module("etl.reddit_hourly_community")
