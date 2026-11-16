"""Step 39: (ส่วนขยาย A3) ประเมิน Logistic บนชุดทดสอบสุดท้าย: แบ่งตามเวลา 75/25 เว้น 12 ชั่วโมง, ปรับ L1/L2 + C ด้วย TimeSeriesSplit ในชุดฝึก, AUC + ช่วงเชื่อมั่น + metrics อื่น,
เทียบโมเดลฐาน (สุ่ม / ราคาล้วน / Reddit ล้วน) และวัดว่าตัวแปรแต่ละตัวช่วยเพิ่มเท่าไร (L1 คัดตัวแปร, drop-one, add-one)
-> output/reports/logistic_evaluation.md, logistic_panels.csv, logistic_features.csv, output/figures/logistic_delta_auc.png

Run:  python steps/39_logistic_evaluation.py [--boot 300] [--panels panel_global] [--no-features]
"""

from _run import module

module("analysis.logistic_eval")
