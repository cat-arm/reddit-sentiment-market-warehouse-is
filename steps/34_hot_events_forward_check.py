"""Step 34: (ส่วนขยาย) ระบบ 7.6 ในฐานะ Predictive: คะแนน Hot Events บอกล่วงหน้าได้ไหมว่าราคาจะขยับแรงกว่าปกติ / บอกทิศได้ไหม
-> output/reports/hot_events_forward_check.md

Run:  python steps/34_hot_events_forward_check.py [--boot 200]
"""

from _run import script

script("scripts/hot_events_forward_check.py")
