"""Step 38: (ส่วนขยาย ระบบ 7.4) ตรวจสมมติฐานของ Spearman (monotonic, ค่าซ้ำ, autocorrelation + Ljung-Box, ADF/KPSS) และตอบ "sentiment ขึ้น ราคาขึ้นไหม / ลง ราคาลงไหม"
(10 กลุ่มความรู้สึก, ครึ่งสูง/ต่ำ, การเปลี่ยนแปลง, lead-lag, ความเสถียรรายเดือน)
-> output/reports/spearman_assumptions_check.md/.csv, output/figures/spearman_deciles.png, spearman_leadlag.png

Run:  python steps/38_spearman_assumptions_check.py [--boot 300]
"""

from _run import script

script("scripts/spearman_assumptions_check.py")
