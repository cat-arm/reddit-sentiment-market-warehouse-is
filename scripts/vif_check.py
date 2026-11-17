"""Multicollinearity check of the Logistic Regression variables (advisor's remark in the meeting 2026-11-17: the variables that correlate make the reading of the model misleading).

For the panel Global (every text of the market, hourly), on the TRAIN part of the time split (the first 75% of the hours: no test row is looked at) it reports, for the 19
variables and for the variables KEPT after the validation (read from `logistic_cut_test.csv`, the Current Return row):
  VIF   Variance Inflation Factor = 1 / (1 - R^2) of a variable regressed on all the others (1 = not redundant, above 5 = redundant, above 10 = very redundant)
  pairs the pairs of variables with |Pearson r| >= 0.7
The VIF depends on the variables only (not on the target), so one table serves every horizon.  Read-only: nothing is written to the database.

Usage:  python scripts/vif_check.py [--db output/reddit.sqlite3]
Output: output/reports/vif_check.md and .csv
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis import logistic_eval as le                                        # noqa: E402
from analysis.logistic import GROUPS, prepare                                    # noqa: E402
from etl.common import DEFAULT_DB, connect, file_header                          # noqa: E402

OUT_DIR = ROOT / "output" / "reports"
PAIR_LIMIT = 0.7


def kept_from_report():
    path = OUT_DIR / "logistic_cut_test.csv"
    if not path.exists():
        return None
    cuts = pd.read_csv(path, comment="#")
    row = cuts[(cuts.panel == "panel_global") & (cuts.horizon == "log_return")]
    return [c.strip() for c in row.iloc[0].kept.split(",")] if len(row) else None


def run(db_path=DEFAULT_DB):
    db = connect(db_path, readonly=True)
    try:
        part = prepare(le.load_panel(db, "panel_global", None, ["log_return"]))
    finally:
        db.close()
    columns = [c for cols in GROUPS.values() for c in cols]
    hours, x, _ = le.design(part, "log_return", columns)
    train, _ = le.time_split(hours)
    xt = x[train]
    group_of = {c: g for g, cols in GROUPS.items() for c in cols}
    kept = kept_from_report()
    table = pd.DataFrame({"variable": columns, "group": [group_of[c] for c in columns], "vif_all_19": le.vif_values(xt)})
    if kept:
        idx = [columns.index(c) for c in kept]
        table["vif_kept"] = np.nan
        table.loc[idx, "vif_kept"] = le.vif_values(xt[:, idx])
    corr = np.corrcoef(xt, rowvar=False)
    pairs = [(columns[i], columns[j], corr[i, j]) for i in range(len(columns)) for j in range(i + 1, len(columns)) if abs(corr[i, j]) >= PAIR_LIMIT]
    pairs.sort(key=lambda t: -abs(t[2]))
    return table, pairs, len(train), kept


def report(table, pairs, n_train, kept):
    lines = ["# Multicollinearity ของตัวแปร Logistic Regression (VIF): panel Global", "",
             *file_header("ตรวจว่าตัวแปรของโมเดล Logistic ซ้ำซ้อนกันเองแค่ไหน (VIF และคู่ตัวแปรที่สัมพันธ์กันสูง) ตามข้อสังเกตของอาจารย์ในประชุม 2026-11-17",
                          "scripts/vif_check.py", "python scripts/vif_check.py", "ตาราง panels (panel_global) ใน output/reddit.sqlite3 อ่านอย่างเดียว"), "",
             "ใช้ชุดฝึก (75%% แรกของเวลา, %s แถว) ไม่แตะชุดทดสอบ · VIF = 1 ÷ (1 − R²) ของตัวแปรนั้นเมื่อทายด้วยตัวแปรอื่นทั้งหมด: 1 = ไม่ซ้ำ, เกิน 5 = ซ้ำ, เกิน 10 = ซ้ำมาก · "
             "VIF ไม่ขึ้นกับตัวทาย (Current Return หรือล่วงหน้า) จึงใช้ตารางเดียวกับทุกช่วงเวลา" % "{:,}".format(n_train), "",
             "| ตัวแปร | กลุ่ม | VIF (ครบ 19 ตัว) | VIF (เฉพาะ %d ตัวที่เก็บไว้) |" % (len(kept) if kept else 0), "|---|---|---|---|"]
    for r in table.sort_values("vif_all_19", ascending=False).itertuples():
        kept_v = "-" if not kept or pd.isna(getattr(r, "vif_kept", np.nan)) else "%.1f" % r.vif_kept
        lines.append("| %s | %s | %s | %s |" % (r.variable, r.group, "-" if pd.isna(r.vif_all_19) else ("เป็นผลรวมของตัวอื่น" if np.isinf(r.vif_all_19) else "%.1f" % r.vif_all_19), kept_v))
    over10 = int((table.vif_all_19 > 10).sum())
    over5 = int((table.vif_all_19 > 5).sum())
    exact = [c for c, v in zip(table.variable, table.vif_all_19) if np.isinf(v)]
    lines += ["", "ตัวแปรที่ VIF เกิน 5: %d ตัว, เกิน 10: %d ตัว (จาก 19 ตัว) ในนี้เป็นผลรวมของตัวอื่น (คำนวณได้จากตัวแปรอื่นตรง ๆ): %s" % (over5, over10, ", ".join(exact) or "ไม่มี")]
    if kept and "vif_kept" in table:
        lines.append("หลังเลือก (%d ตัวแปร) VIF สูงสุด = %.1f" % (len(kept), table.vif_kept.max()))
    else:
        lines.append("(ยังไม่มีไฟล์ logistic_cut_test.csv จึงไม่มีคอลัมน์ชุดที่เก็บไว้: รัน python -m analysis.logistic_eval ก่อน)")
    lines += ["", "คู่ตัวแปรที่ |r| ≥ %.1f (Pearson ระหว่างตัวแปรเอง บนชุดฝึก):" % PAIR_LIMIT, ""]
    lines += ["| ตัวแปร A | ตัวแปร B | r |", "|---|---|---|"] + ["| %s | %s | %+.2f |" % p for p in pairs] if pairs else ["ไม่มีคู่ใดถึงเกณฑ์"]
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args(argv)
    table, pairs, n_train, kept = run(args.db)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "vif_check.md").write_text("\n".join(report(table, pairs, n_train, kept)) + "\n", encoding="utf-8")
    with (OUT_DIR / "vif_check.csv").open("w", newline="", encoding="utf-8") as sink:
        sink.write("\n".join(file_header("VIF ของตัวแปร Logistic (panel Global, ชุดฝึก)", "scripts/vif_check.py", "python scripts/vif_check.py", "ตาราง panels", comment=True)) + "\n")
        table.to_csv(sink, index=False)
    print(table.sort_values("vif_all_19", ascending=False).round(2).to_string(index=False))
    print("\npairs |r| >= %.1f:" % PAIR_LIMIT)
    for a, b, r in pairs:
        print("  %-28s %-28s %+.2f" % (a, b, r))


if __name__ == "__main__":
    main()
