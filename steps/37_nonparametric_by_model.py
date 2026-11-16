"""Step 37: (ส่วนขยาย ระบบ 7.4) ผล non-parametric แยกตามแบบจำลองความรู้สึก (VADER+FinBERT / VADER / FinBERT): สินทรัพย์เดียว (--ticker ES=F) หรือทุกสินทรัพย์ (--all)
-> output/reports/nonparametric_by_model_<ticker>.md/.csv หรือ nonparametric_by_model_all.md/.csv

Run:  python steps/37_nonparametric_by_model.py --ticker "ES=F"      หรือ      python steps/37_nonparametric_by_model.py --all
"""

from _run import script

script("scripts/nonparametric_by_model.py")
