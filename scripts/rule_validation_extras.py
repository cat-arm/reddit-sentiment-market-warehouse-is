"""S5 extras (proposal 7.3 step 5): (1) accuracy against the hand labels when the neutral band is +-0.10 instead of +-0.05,
(2) confusion matrices (model prediction vs the developer's label) for VADER, FinBERT and the combined final sentiment.

Reads the 210 hand labels of scripts/rule_validation.py (labeling_sheet.csv + sample_key.csv) and re-applies the
conflict-resolution rules to the STORED model scores with the other band (no model is run, the database is not touched).
Accuracy is weighted by stratum population exactly like rule_validation.md.  With ~15 texts per stratum and split the
numbers are indications, not significance tests.

Usage:  python scripts/rule_validation_extras.py [--out-dir output/reports/rule_validation]
Output: <out-dir>/band_and_confusion.md, band_and_confusion.csv and output/figures/s5_confusion_matrices.png
"""
import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis import figure_style                                            # noqa: E402
from etl.common import file_header, status_of                                # noqa: E402
from etl.resolve_sentiment import resolve                                    # noqa: E402
from scripts.rule_validation import LABELS, OUT_DIR, read_labelled           # noqa: E402

BANDS = (0.05, 0.10)
ORDER = ("positive", "neutral", "negative")
FIGURES = ROOT / "output" / "figures"


def predictions(row, band):
    """{method: status} for one sample row at one neutral band (stored scores, rules re-applied)."""
    vader, finbert = float(row["vader_score"]), float(row["finbert_score"])
    score, _ = resolve(vader, finbert, row["rule_signal"], None, band)
    return {"vader": status_of(vader, band), "finbert": status_of(finbert, band), "final": status_of(score, band)}


def weighted(labelled, split, band):
    """Accuracy per method on `split` (None = all), strata weighted by population."""
    per = {}
    for row, label in labelled:
        if split and row["split"] != split:
            continue
        cell = per.setdefault(row["stratum"], {"pop": int(row["stratum_population"]), "n": 0, "vader": 0, "finbert": 0, "final": 0})
        cell["n"] += 1
        for method, status in predictions(row, band).items():
            cell[method] += status == label
    total = sum(c["pop"] for c in per.values())
    return {m: sum(c["pop"] * c[m] / c["n"] for c in per.values()) / total for m in ("vader", "finbert", "final")}


def plain(labelled, split, band):
    """Unweighted accuracy and the number of texts."""
    hits, n = Counter(), 0
    for row, label in labelled:
        if split and row["split"] != split:
            continue
        n += 1
        for method, status in predictions(row, band).items():
            hits[method] += status == label
    return n, {m: hits[m] / n for m in ("vader", "finbert", "final")}


def confusion(labelled, band):
    """{method: Counter((label, predicted))} over all labelled texts."""
    out = {m: Counter() for m in ("vader", "finbert", "final")}
    for row, label in labelled:
        for method, status in predictions(row, band).items():
            out[method][(label, status)] += 1
    return out


def draw(matrices, path, count):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    figure_style.use_thai_font()
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.2))
    for ax, (method, title) in zip(axes, (("vader", "VADER เดี่ยว"), ("finbert", "FinBERT เดี่ยว"), ("final", "วิธีรวมผล (final)"))):
        grid = np.array([[matrices[method][(lab, pred)] for pred in ORDER] for lab in ORDER], dtype=float)
        share = grid / grid.sum(axis=1, keepdims=True).clip(min=1)
        ax.imshow(share, cmap="Blues", vmin=0, vmax=1)
        for i in range(3):
            for j in range(3):
                ax.text(j, i, "%d\n(%.0f%%)" % (grid[i, j], 100 * share[i, j]), ha="center", va="center", fontsize=9,
                        color="white" if share[i, j] > 0.6 else "black")
        ax.set_xticks(range(3), ORDER)
        ax.set_yticks(range(3), ORDER)
        ax.set_xlabel("โมเดลทาย")
        ax.set_ylabel("ป้ายของผู้พัฒนา")
        ax.set_title("%s  (ถูก %.1f%%)" % (title, 100 * grid.trace() / grid.sum()), fontsize=10)
    fig.suptitle("Confusion matrix เทียบป้ายที่ติดเอง %d ข้อความ (เกณฑ์ neutral ±0.05; สี = สัดส่วนต่อแถวของป้าย; ตัวเลข = จำนวนข้อความ)"
                 % count, fontsize=10)
    fig.tight_layout()
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", default=str(OUT_DIR))
    args = parser.parse_args(argv)
    out = Path(args.out_dir)
    labelled, skipped = read_labelled(out)
    if not labelled:
        raise SystemExit("no labelled rows - fill human_label first")
    names = {"vader": "VADER", "finbert": "FinBERT", "final": "รวมผล (final)"}
    lines = ["# เกณฑ์ neutral ±0.10 เทียบป้าย + confusion matrix (proposal 7.3 ขั้นตอนที่ 5)", "",
             *file_header("ความแม่นเมื่อเทียบป้ายที่ผู้พัฒนาติดเอง ที่เกณฑ์ neutral ±0.05 เทียบ ±0.10 และ confusion matrix (%d ข้อความ, ข้าม %d ที่ไม่มีป้าย)"
                          % (len(labelled), skipped), "scripts/rule_validation_extras.py",
                          "python steps/29_rule_validation_extras.py",
                          "labeling_sheet.csv + sample_key.csv (คะแนนที่เก็บไว้ เอากฎมาคำนวณใหม่ ไม่รันโมเดล ไม่แตะฐานข้อมูล)"), "",
             "ตัวเลขรวมถ่วงน้ำหนักตามจำนวนข้อความจริงของแต่ละกลุ่มกฎ เหมือน rule_validation.md; ตัวอย่างน้อย (ชุดละ 105 ข้อความ) ผลเป็นแนวโน้ม ไม่ใช่การทดสอบนัยสำคัญ", ""]
    rows = []
    lines += ["## ความแม่น: ±0.05 เทียบ ±0.10", "", "| ชุด | วิธี | ±0.05 | ±0.10 | ต่าง (จุด) |", "|---|---|---|---|---|"]
    for split, label in (("tune", "tune"), ("test", "test"), (None, "ทั้ง 210")):
        a, b = weighted(labelled, split, BANDS[0]), weighted(labelled, split, BANDS[1])
        for method in ("vader", "finbert", "final"):
            lines.append("| %s | %s | %.1f%% | %.1f%% | %+.1f |" % (label, names[method], 100 * a[method], 100 * b[method], 100 * (b[method] - a[method])))
            rows.append((label, method, "%.4f" % a[method], "%.4f" % b[method]))
    n_all, plain05 = plain(labelled, None, BANDS[0])
    _, plain10 = plain(labelled, None, BANDS[1])
    lines += ["", "ไม่ถ่วงน้ำหนัก (ทั้ง %d ข้อความ): " % n_all + " · ".join(
        "%s %.1f%% → %.1f%%" % (names[m], 100 * plain05[m], 100 * plain10[m]) for m in ("vader", "finbert", "final")), ""]
    matrices = confusion(labelled, BANDS[0])
    for band in BANDS:
        matrices_b = matrices if band == BANDS[0] else confusion(labelled, band)
        lines += ["## Confusion matrix ที่เกณฑ์ ±%.2f (แถว = ป้ายผู้พัฒนา, คอลัมน์ = โมเดลทาย)" % band, ""]
        for method in ("vader", "finbert", "final"):
            lines += ["**%s**" % names[method], "", "| ป้าย \\ ทาย | positive | neutral | negative | รวม |", "|---|---|---|---|---|"]
            for lab in ORDER:
                cells = [matrices_b[method][(lab, pred)] for pred in ORDER]
                lines.append("| %s | %s | %d |" % (lab, " | ".join(str(c) for c in cells), sum(cells)))
            lines.append("")
    label_count = Counter(label for _, label in labelled)
    lines += ["ป้ายของผู้พัฒนา: " + ", ".join("%s %d" % (k, label_count[k]) for k in ORDER) +
              " (ตัวอย่างสุ่มแบบแบ่งกลุ่มตามกฎ ไม่ใช่สัดส่วนจริงของข้อความทั้งหมด)", "",
              "รูป: `output/figures/s5_confusion_matrices.png` (เกณฑ์ ±0.05)", ""]
    (out / "band_and_confusion.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (out / "band_and_confusion.csv").open("w", newline="", encoding="utf-8") as sink:
        sink.write("\n".join(file_header("ความแม่นถ่วงน้ำหนักที่เกณฑ์ ±0.05 และ ±0.10 (ข้อมูลชุดเดียวกับ band_and_confusion.md)",
                                         "scripts/rule_validation_extras.py", "python steps/29_rule_validation_extras.py",
                                         "labeling_sheet.csv + sample_key.csv", comment=True)) + "\n")
        writer = csv.writer(sink)
        writer.writerow(("split", "method", "accuracy_band_0.05", "accuracy_band_0.10"))
        writer.writerows(rows)
    draw(matrices, FIGURES / "s5_confusion_matrices.png", len(labelled))
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
