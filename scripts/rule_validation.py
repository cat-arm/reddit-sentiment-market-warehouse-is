"""S5 (proposal 7.3 step 5): validate the conflict-resolution rules against texts the developer labels by hand.

Two sub-commands:

  sample    draw a stratified random sample of texts (one stratum per resolution rule, see STRATA), split it into a
            tuning set and a test set, and write
              output/reports/rule_validation/labeling_sheet.csv   sample_id, final_text, human_label (EMPTY - fill in)
              output/reports/rule_validation/sample_key.csv       sample_id, split, stratum, model scores, final ...
            The sheet shows only the text, in shuffled order, so the labeller sees neither the model scores nor the
            rule that produced the final value.  human_label is one of: positive / negative / neutral.
  evaluate  read the filled sheet and compare the accuracy of VADER alone, FinBERT alone and the combined final
            sentiment, per stratum and split; the overall figure is weighted by stratum population.
            -> output/reports/rule_validation/rule_validation.md and .csv

Choices not fixed by the proposal (also in docs/METHOD_DECISIONS_NOT_IN_PROPOSAL.md): strata are the final_method
values grouped as in the proposal (agree / one neutral + keyword / one neutral, no keyword / opposite + keyword /
opposite, no keyword); every text length is eligible (the models scored all of them) unless --min-chars / --max-chars is given;
the tuning and test sets are a random 50/50 split inside every stratum; hard_conflict_mixed_zero (0.01%) is skipped.
Read-only on the database.  The sheet holds real Reddit text: keep it out of git (output/ is ignored).

Usage:
    python scripts/rule_validation.py sample   [--db output/reddit.sqlite3] [--per-stratum 30] [--min-chars N] [--max-chars N] [--seed 20261024] [--force]
    python scripts/rule_validation.py evaluate [--out-dir output/reports/rule_validation]
"""
import argparse
import csv
import random
import sys
from array import array
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from etl.common import DEFAULT_DB, connect, file_header                  # noqa: E402

OUT_DIR = ROOT / "output" / "reports" / "rule_validation"
# stratum -> final_method values it covers (proposal step 5: groups 1, 2 and 3; groups 2 and 3 split by keyword)
STRATA = {
    "same_direction": ("same_direction",),
    "same_direction_far": ("same_direction_far",),
    "both_neutral": ("both_neutral",),
    "small_conflict_keyword": ("small_conflict_rule_agrees", "small_conflict_rule_clash"),
    "small_conflict_no_keyword": ("small_conflict_no_rule",),
    "hard_conflict_keyword": ("hard_conflict_rule",),
    "hard_conflict_no_keyword": ("hard_conflict_no_rule",),
}
LABELS = ("positive", "negative", "neutral")
LABEL_ALIASES = {"pos": "positive", "+": "positive", "neg": "negative", "-": "negative", "neu": "neutral", "0": "neutral"}
KEY_COLUMNS = ("sample_id", "split", "stratum", "stratum_population", "src_rowid", "final_method", "vader_score",
               "vader_status", "finbert_score", "finbert_status", "rule_signal", "final_sentiment", "final_status",
               "is_ambiguous")


def draw(db, per_stratum, seed, min_chars=0, max_chars=None):
    """[(stratum, population, [src_rowid, ...])] - a random sample of `per_stratum` texts for every stratum."""
    rng = random.Random(seed)
    drawn = []
    for stratum, methods in STRATA.items():
        marks = ",".join("?" * len(methods))
        ids = array("q", (row[0] for row in db.execute(
            "SELECT s.src_rowid FROM sentiment_item s JOIN filtered_text t ON t.src_rowid = s.src_rowid "
            "WHERE s.final_method IN (%s) AND t.char_len >= ? AND t.char_len <= ? ORDER BY s.src_rowid" % marks,
            (*methods, min_chars, max_chars if max_chars is not None else 1 << 40))))
        picked = sorted(ids[i] for i in rng.sample(range(len(ids)), min(per_stratum, len(ids))))
        drawn.append((stratum, len(ids), picked))
    return drawn


def split_sets(rowids, rng):
    """Random 50/50 tuning/test split of one stratum's sample."""
    shuffled = list(rowids)
    rng.shuffle(shuffled)
    half = len(shuffled) // 2
    return {rowid: ("tune" if k < half else "test") for k, rowid in enumerate(shuffled)}


def sample(args):
    out = Path(args.out_dir)
    sheet_path, key_path = out / "labeling_sheet.csv", out / "sample_key.csv"
    if sheet_path.exists() and not args.force:
        raise SystemExit("%s already exists (it may hold your labels); pass --force to overwrite" % sheet_path)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    db = connect(args.db, readonly=True)
    try:
        records = []
        for stratum, population, rowids in draw(db, args.per_stratum, args.seed, args.min_chars, args.max_chars):
            splits = split_sets(rowids, rng)
            for rowid in rowids:
                row = db.execute(
                    "SELECT s.vader_score, s.vader_status, s.finbert_score, s.finbert_status, s.rule_signal, "
                    "s.final_sentiment, s.final_status, s.final_method, s.is_ambiguous, t.final_text "
                    "FROM sentiment_item s JOIN filtered_text t ON t.src_rowid = s.src_rowid "
                    "WHERE s.src_rowid = ?", (rowid,)).fetchone()
                records.append((stratum, population, rowid, splits[rowid], row))
    finally:
        db.close()
    rng.shuffle(records)
    (out / "README.md").write_text("\n".join([
        "# โฟลเดอร์ rule_validation", "",
        *file_header("ชุดตัวอย่างสำหรับตรวจกฎรวมผลความรู้สึก (proposal 7.3 ขั้นตอนที่ 5): %d ข้อความสุ่มจาก %d กลุ่มกฎ"
                     % (len(records), len(STRATA)), "scripts/rule_validation.py sample",
                     "python steps/26_rule_validation.py sample --force",
                     "sentiment_item + filtered_text ใน output/reddit.sqlite3 อ่านอย่างเดียว (seed %d)" % args.seed), "",
        "| ไฟล์ | คืออะไร |", "|---|---|",
        "| `labeling_sheet.csv` | **ไฟล์ที่ต้องกรอก** — คอลัมน์ `human_label` ใส่ positive / negative / neutral (เห็นเฉพาะข้อความ ไม่เห็นคะแนนโมเดล) |",
        "| `sample_key.csv` | เฉลยฝั่งโมเดล: คะแนน VADER/FinBERT, กฎที่ใช้, ชุด tune/test — **อย่าเปิดดูก่อนติดป้ายเสร็จ** เพื่อไม่ให้ลำเอียง |",
        "| `rule_validation.md` / `.csv` | ผลเทียบความแม่น (เกิดหลังรัน `evaluate`) |", "",
        "ข้อความในไฟล์เป็นข้อความ Reddit จริง ห้ามนำขึ้น git หรือแนบกับเล่ม (โฟลเดอร์ output/ ถูก ignore อยู่แล้ว)", ""]),
        encoding="utf-8")
    with sheet_path.open("w", newline="", encoding="utf-8-sig") as sheet, \
            key_path.open("w", newline="", encoding="utf-8") as key:
        sheet_writer, key_writer = csv.writer(sheet), csv.writer(key)
        sheet_writer.writerow(("sample_id", "final_text", "human_label"))
        key_writer.writerow(KEY_COLUMNS)
        for number, (stratum, population, rowid, split, row) in enumerate(records, 1):
            sample_id = "S%04d" % number
            vader, vader_status, finbert, finbert_status, rule, final, final_status, method, ambiguous, text = row
            sheet_writer.writerow((sample_id, text, ""))
            key_writer.writerow((sample_id, split, stratum, population, rowid, method, vader, vader_status, finbert,
                                 finbert_status, rule, final, final_status, ambiguous))
    print("wrote %d texts -> %s (fill human_label with positive / negative / neutral)" % (len(records), sheet_path))
    return 0


def normalise(label):
    label = (label or "").strip().lower()
    label = LABEL_ALIASES.get(label, label)
    return label if label in LABELS else None


def read_labelled(out):
    """[(key row dict, human label)] for every sheet row that has a valid label."""
    with (out / "sample_key.csv").open(newline="", encoding="utf-8") as handle:
        key = {row["sample_id"]: row for row in csv.DictReader(handle)}
    labelled, skipped = [], 0
    with (out / "labeling_sheet.csv").open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            label = normalise(row["human_label"])
            if label is None:
                skipped += 1
            else:
                labelled.append((key[row["sample_id"]], label))
    return labelled, skipped


def accuracy_table(labelled):
    """{(stratum, split): {n, vader, finbert, final}} with the number of texts each method got right."""
    table = {}
    for row, label in labelled:
        cell = table.setdefault((row["stratum"], row["split"]), {"n": 0, "vader": 0, "finbert": 0, "final": 0})
        cell["n"] += 1
        cell["vader"] += row["vader_status"] == label
        cell["finbert"] += row["finbert_status"] == label
        cell["final"] += row["final_status"] == label
    return table


def weighted_overall(labelled, split):
    """Accuracy of each method on `split`, every stratum weighted by its population in the filtered texts."""
    per = {}
    for row, label in labelled:
        if row["split"] != split:
            continue
        cell = per.setdefault(row["stratum"], {"population": int(row["stratum_population"]), "n": 0,
                                               "vader": 0, "finbert": 0, "final": 0})
        cell["n"] += 1
        for method in ("vader", "finbert", "final"):
            cell[method] += row[method + "_status"] == label
    total = sum(cell["population"] for cell in per.values())
    if not total:
        return None
    return {method: sum(c["population"] * c[method] / c["n"] for c in per.values()) / total
            for method in ("vader", "finbert", "final")}


def evaluate(args):
    out = Path(args.out_dir)
    labelled, skipped = read_labelled(out)
    if not labelled:
        raise SystemExit("no labelled rows in %s - fill human_label first" % (out / "labeling_sheet.csv"))
    table = accuracy_table(labelled)
    lines = ["# Rule validation (proposal 7.3 step 5)", "",
             *file_header("ความแม่นของ VADER เดี่ยว, FinBERT เดี่ยว และวิธีรวมผล เมื่อเทียบกับป้ายที่ผู้พัฒนาติดเอง (%d ข้อความ, ข้าม %d ที่ยังไม่มีป้าย)"
                          % (len(labelled), skipped), "scripts/rule_validation.py evaluate",
                          "python steps/26_rule_validation.py evaluate",
                          "labeling_sheet.csv (ป้าย) + sample_key.csv (คะแนนโมเดล) ในโฟลเดอร์เดียวกัน"), "",
             "ความแม่น = สัดส่วนที่ประเภทความรู้สึก (positive/negative/neutral) ตรงกับป้ายที่ผู้พัฒนาติดเอง; "
             "ชุด tune ใช้ปรับกฎ, ชุด test ใช้รายงานผล", ""]
    for split in ("tune", "test"):
        lines += ["## ชุด %s" % split, "", "| กลุ่ม | n | VADER | FinBERT | รวมผล (final) |", "|---|---|---|---|---|"]
        for stratum in STRATA:
            cell = table.get((stratum, split))
            if cell:
                lines.append("| %s | %d | %.1f%% | %.1f%% | %.1f%% |" % (
                    stratum, cell["n"], *(100.0 * cell[m] / cell["n"] for m in ("vader", "finbert", "final"))))
        overall = weighted_overall(labelled, split)
        if overall:
            lines.append("| **ถ่วงน้ำหนักตามจำนวนข้อความของกลุ่ม** | | %.1f%% | %.1f%% | %.1f%% |"
                         % (100 * overall["vader"], 100 * overall["finbert"], 100 * overall["final"]))
        lines.append("")
    (out / "rule_validation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (out / "rule_validation.csv").open("w", newline="", encoding="utf-8") as sink:
        sink.write("\n".join(file_header(
            "จำนวนข้อความที่แต่ละวิธีตอบถูก แยกตามกลุ่มกฎและชุด tune/test (ข้อมูลชุดเดียวกับ rule_validation.md)",
            "scripts/rule_validation.py evaluate", "python steps/26_rule_validation.py evaluate",
            "labeling_sheet.csv + sample_key.csv", comment=True)) + "\n")
        writer = csv.writer(sink)
        writer.writerow(("stratum", "split", "n", "vader_correct", "finbert_correct", "final_correct"))
        for (stratum, split), cell in sorted(table.items()):
            writer.writerow((stratum, split, cell["n"], cell["vader"], cell["finbert"], cell["final"]))
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(lines))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    drawer = sub.add_parser("sample", help="draw the stratified sample and write the labeling sheet")
    drawer.add_argument("--db", default=str(DEFAULT_DB))
    drawer.add_argument("--per-stratum", type=int, default=30)
    drawer.add_argument("--min-chars", type=int, default=0, help="optional: skip texts shorter than this")
    drawer.add_argument("--max-chars", type=int, help="optional: skip texts longer than this")
    drawer.add_argument("--seed", type=int, default=20261024)
    drawer.add_argument("--force", action="store_true", help="overwrite an existing labeling sheet")
    drawer.add_argument("--out-dir", default=str(OUT_DIR))
    checker = sub.add_parser("evaluate", help="compare VADER / FinBERT / final against the human labels")
    checker.add_argument("--out-dir", default=str(OUT_DIR))
    args = parser.parse_args(argv)
    return sample(args) if args.command == "sample" else evaluate(args)


if __name__ == "__main__":
    sys.exit(main())
