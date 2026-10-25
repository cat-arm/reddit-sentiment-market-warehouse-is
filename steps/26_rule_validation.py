"""Step 26: ตรวจกฎรวมผลด้วยตัวอย่างสุ่มที่ติดป้ายเอง (S5)
sample   -> สุ่มข้อความ + สร้างไฟล์ติดป้าย output/reports/rule_validation/labeling_sheet.csv
evaluate -> เทียบความแม่น VADER / FinBERT / รวมผล จากป้ายที่กรอกแล้ว

Run:  python steps/26_rule_validation.py sample
      (กรอกคอลัมน์ human_label = positive / negative / neutral)
      python steps/26_rule_validation.py evaluate
"""

from _run import script

script("scripts/rule_validation.py")
