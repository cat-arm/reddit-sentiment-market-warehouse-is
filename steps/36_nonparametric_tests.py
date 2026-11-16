"""Step 36: (ส่วนขยาย ระบบ 7.4) ทดสอบแบบ non-parametric: Spearman + ช่วงเชื่อมั่น block bootstrap + p จาก circular-shift, Mann-Whitney, Kruskal-Wallis รายสินทรัพย์ x ช่วงเวลา
-> output/reports/nonparametric_tests.md/.csv

Run:  python steps/36_nonparametric_tests.py [--boot 1000] [--shifts 2000]
"""

from _run import script

script("scripts/nonparametric_tests.py")
