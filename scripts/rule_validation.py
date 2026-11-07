"""S5 (proposal 7.3 step 5): validate the conflict-resolution rules AND the text given to the models, against comments
the developer labels by hand.  Answers the advisor's point (4) and the developer's three-way question
(comment only / post title + comment / post title + post body + comment).

Three sub-commands:

  sample    draw a stratified random sample of COMMENTS (one stratum per resolution rule, see STRATA), split every
            stratum 50/50 into a tuning set and a test set, and write
              labeling_sheet.csv  sample_id, comment, post_title, post_body, thai_comment, thai_title, thai_body, human_label
                                  (EMPTY human_label - fill in; the sheet shows no model score and no rule)
              sample_key.csv      sample_id, split, stratum, model scores, final ... (do NOT open before labelling)
            The human label is the stance of the COMMENT AUTHOR, read with the post as context, so it does not
            favour any of the three text variants (see README.md written next to the sheet).
  score     run VADER + FinBERT + the conflict-resolution rules on the three text variants of every sampled comment
            -> variant_scores.csv   A = comment only (own_text)
                                    B = post title + comment (final_text, what the pipeline uses; stored scores)
                                    C = post title + first 500 characters of the post body + comment
            Needs nltk (vader_lexicon), torch and transformers (ProsusAI/finbert).  Cheap: ~1.5 variants per comment.
  evaluate  read the filled sheet and compare, per stratum and split: VADER alone, FinBERT alone, the combined
            final sentiment and an "always neutral" baseline; then the three variants and the cascade
            (A, if neutral then B, if neutral then C).  -> rule_validation.md and .csv

Choices not fixed by the proposal (also in docs/METHOD_DECISIONS_NOT_IN_PROPOSAL.md): strata are the final_method
values grouped as in the proposal (agree / one neutral + keyword / one neutral, no keyword / opposite + keyword /
opposite, no keyword); only comments are sampled (a submission is title + body in every variant); the tuning and
test sets are a random 50/50 split inside every stratum; hard_conflict_mixed_zero (0.01%) is skipped; a text the
labeller cannot judge is labelled `unclear` and left out of every accuracy figure (its count is reported).
Read-only on the database.  The sheet holds real Reddit text: keep it out of git (output/ is ignored).

Usage:
    python scripts/rule_validation.py sample   [--db output/reddit.sqlite3] [--per-stratum 50] [--boost small_conflict_no_keyword=100]
                                               [--exclude-dir DIR] [--seed 20261104] [--force]
    python scripts/rule_validation.py score    [--db output/reddit.sqlite3] [--device auto|cpu|mps|cuda]
    python scripts/rule_validation.py evaluate [--out-dir output/reports/rule_validation]
"""
import argparse
import csv
import random
import sys
from array import array
from math import comb, sqrt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from etl.clean_text import _PLACEHOLDERS, clean_text                     # noqa: E402
from etl.common import DEFAULT_DB, connect, file_header, status_of       # noqa: E402
from etl.resolve_sentiment import is_ambiguous, resolve                  # noqa: E402

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
UNCLEAR = "unclear"
LABEL_ALIASES = {"pos": "positive", "+": "positive", "neg": "negative", "-": "negative", "neu": "neutral",
                 "0": "neutral", "?": UNCLEAR,
                 "neural": "neutral", "noclear": UNCLEAR, "not clear": UNCLEAR}       # typos seen in the real sheet
POST_BODY_CHARS = 500                    # variant C: how much of the post body goes in front of the comment
VARIANTS = ("A", "B", "C")
KEY_COLUMNS = ("sample_id", "split", "stratum", "stratum_population", "src_rowid", "final_method", "vader_score",
               "vader_status", "finbert_score", "finbert_status", "rule_signal", "final_sentiment", "final_status",
               "is_ambiguous", "post_known", "post_has_body")
SHEET_COLUMNS = ("sample_id", "comment", "post_title", "post_body", "thai_comment", "thai_title", "thai_body",
                 "human_label")
SCORE_COLUMNS = ("sample_id", "variant", "same_text_as_B", "vader_score", "finbert_score", "rule_signal",
                 "final_sentiment", "final_status", "final_method", "is_ambiguous")


# ----------------------------------------------------------------------------------------------- sampling

def draw(db, per_stratum, seed, only=None, exclude=frozenset(), boost=None):
    """[(stratum, population, [src_rowid, ...])] - a random sample of COMMENTS for every stratum.

    boost: {stratum: n} overrides per_stratum for that stratum (the weak rule gets a larger sample).
    only: restrict to these stratum names.  exclude: src_rowid values never to draw (already labelled earlier)."""
    rng = random.Random(seed)
    boost = boost or {}
    drawn = []
    for stratum, methods in STRATA.items():
        if only and stratum not in only:
            continue
        marks = ",".join("?" * len(methods))
        ids = array("q", (row[0] for row in db.execute(
            "SELECT s.src_rowid FROM sentiment_item s JOIN filtered_text t ON t.src_rowid = s.src_rowid "
            "WHERE s.final_method IN (%s) AND t.content_type = 'comment' ORDER BY s.src_rowid" % marks, methods)
            if row[0] not in exclude))
        wanted = boost.get(stratum, per_stratum)
        picked = sorted(ids[i] for i in rng.sample(range(len(ids)), min(wanted, len(ids))))
        drawn.append((stratum, len(ids), picked))
    return drawn


def split_sets(rowids, rng):
    """Random 50/50 tuning/test split of one stratum's sample."""
    shuffled = list(rowids)
    rng.shuffle(shuffled)
    half = len(shuffled) // 2
    return {rowid: ("tune" if k < half else "test") for k, rowid in enumerate(shuffled)}


def post_context(db, rowid):
    """(cleaned title, cleaned body) of the post a comment answers; ("", "") when the post is not in the database."""
    link = db.execute("SELECT link_id FROM reddit_content WHERE rowid = ?", (rowid,)).fetchone()
    parent = db.execute("SELECT title, selftext FROM reddit_content WHERE id = ? AND content_type = 'submission'",
                        (link[0],)).fetchone() if link and link[0] else None
    if not parent:
        return "", ""
    selftext = "" if (parent[1] or "").strip().lower() in _PLACEHOLDERS else parent[1]
    return clean_text(parent[0] or ""), clean_text(selftext or "")


def cut_words(text, limit=POST_BODY_CHARS):
    """First `limit` characters of text, cut at a word boundary."""
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0]


def variant_texts(own_text, final_text, title, body):
    """{variant: text the models read}: A comment only, B pipeline text, C title + body start + comment."""
    return {"A": own_text, "B": final_text,
            "C": " ".join(part for part in (title, cut_words(body), own_text) if part)}


def write_readme(out, records, seed):
    (out / "README.md").write_text("\n".join([
        "# โฟลเดอร์ rule_validation", "",
        *file_header("ชุดตัวอย่างสำหรับตรวจกฎรวมผลความรู้สึกและรูปแบบข้อความ (proposal 7.3 ขั้นตอนที่ 5): "
                     "%d คอมเมนต์สุ่มจาก %d กลุ่มกฎ" % (len(records), len({r[0] for r in records})),
                     "scripts/rule_validation.py sample", "python steps/26_rule_validation.py sample --force",
                     "sentiment_item + filtered_text + reddit_content ใน output/reddit.sqlite3 อ่านอย่างเดียว (seed %d)"
                     % seed), "",
        "| ไฟล์ | คืออะไร |", "|---|---|",
        "| `labeling_sheet.csv` | **ไฟล์ที่ต้องกรอก** — คอลัมน์ `human_label` (เห็นเฉพาะข้อความ ไม่เห็นคะแนนโมเดล) |",
        "| `sample_key.csv` | เฉลยฝั่งโมเดล: คะแนน VADER/FinBERT, กฎที่ใช้, ชุด tune/test — **อย่าเปิดดูก่อนติดป้ายเสร็จ** |",
        "| `variant_scores.csv` | คะแนนของข้อความ 3 แบบ A/B/C (เกิดหลังรัน `score`) |",
        "| `rule_validation.md` / `.csv` | ผลเทียบความแม่น (เกิดหลังรัน `evaluate`) |", "",
        "## วิธีติดป้าย (ใช้เหมือนกันทุกข้อความ)", "",
        "ติดป้ายตาม **ท่าทีของคนเขียนคอมเมนต์ (คอลัมน์ `comment`) ต่อหุ้น/คริปโต/ตลาดที่กำลังคุยกัน** "
        "โดยอ่านหัวข้อโพสต์ (`post_title`) และเนื้อโพสต์ (`post_body`) เป็นบริบท; ถ้าประชด ให้ติดตามความหมายจริง",
        "",
        "| ป้าย | ใช้เมื่อ |", "|---|---|",
        "| `positive` | มองบวก คาดว่าขึ้น ดีใจที่กำไร ชอบ/แนะนำให้ซื้อถือ |",
        "| `negative` | มองลบ คาดว่าลง เสียใจที่ขาดทุน เตือน/แนะนำให้ขาย |",
        "| `neutral` | ไม่มีท่าที เช่น ถามข้อมูล เล่าข้อเท็จจริง คุยเรื่องอื่น |",
        "| `unclear` | อ่านแล้วตัดสินไม่ได้จริง ๆ แม้ดูบริบทแล้ว (ไม่นับในความแม่น แต่รายงานจำนวน) |", "",
        "ห้ามเปิด `sample_key.csv` / `variant_scores.csv` ก่อนติดป้ายครบ. คอลัมน์ `thai_comment` / `thai_title` / `thai_body` เป็นคำแปลช่วยอ่าน (เว้นว่างได้; ติดป้ายครั้งเดียวต่อคอมเมนต์ ไม่ต้องติดป้ายแยกตามรูปแบบ A/B/C). "
        "ถ้ามีผู้ติดป้ายคนที่สอง ให้ใส่ป้ายในคอลัมน์ `human_label_2` (เพิ่มเอง) — `evaluate` จะคำนวณ Cohen's kappa ให้", "",
        "ข้อความในไฟล์เป็นข้อความ Reddit จริง ห้ามนำขึ้น git หรือแนบกับเล่ม (โฟลเดอร์ output/ ถูก ignore อยู่แล้ว)", ""]),
        encoding="utf-8")


def sample(args):
    out = Path(args.out_dir)
    sheet_path, key_path = out / "labeling_sheet.csv", out / "sample_key.csv"
    if sheet_path.exists() and not args.force:
        raise SystemExit("%s already exists (it may hold your labels); pass --force to overwrite" % sheet_path)
    for name in args.stratum or ():
        if name not in STRATA:
            raise SystemExit("unknown stratum %s; choose from %s" % (name, ", ".join(STRATA)))
    boost = {}
    for item in args.boost or ():
        name, _, count = item.partition("=")
        if name not in STRATA or not count.isdigit():
            raise SystemExit("--boost needs STRATUM=N with STRATUM one of %s" % ", ".join(STRATA))
        boost[name] = int(count)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    exclude = set()
    for folder in args.exclude_dir or ():
        with (Path(folder) / "sample_key.csv").open(newline="", encoding="utf-8") as handle:
            exclude.update(int(row["src_rowid"]) for row in csv.DictReader(handle))
    db = connect(args.db, readonly=True)
    try:
        records = []
        for stratum, population, rowids in draw(db, args.per_stratum, args.seed, args.stratum, exclude, boost):
            splits = split_sets(rowids, rng)
            for rowid in rowids:
                row = db.execute(
                    "SELECT s.vader_score, s.vader_status, s.finbert_score, s.finbert_status, s.rule_signal, "
                    "s.final_sentiment, s.final_status, s.final_method, s.is_ambiguous, t.own_text "
                    "FROM sentiment_item s JOIN filtered_text t ON t.src_rowid = s.src_rowid "
                    "WHERE s.src_rowid = ?", (rowid,)).fetchone()
                title, body = post_context(db, rowid)
                records.append((stratum, population, rowid, splits[rowid], row, title, body))
    finally:
        db.close()
    rng.shuffle(records)
    write_readme(out, records, args.seed)
    with sheet_path.open("w", newline="", encoding="utf-8-sig") as sheet, \
            key_path.open("w", newline="", encoding="utf-8") as key:
        sheet_writer, key_writer = csv.writer(sheet), csv.writer(key)
        sheet_writer.writerow(SHEET_COLUMNS)
        key_writer.writerow(KEY_COLUMNS)
        for number, (stratum, population, rowid, split, row, title, body) in enumerate(records, 1):
            sample_id = "S%04d" % number
            vader, vader_status, finbert, finbert_status, rule, final, final_status, method, ambiguous, own = row
            sheet_writer.writerow((sample_id, own, title, cut_words(body), "", "", "", ""))
            key_writer.writerow((sample_id, split, stratum, population, rowid, method, vader, vader_status, finbert,
                                 finbert_status, rule, final, final_status, ambiguous, int(bool(title)),
                                 int(bool(body))))
    print("wrote %d comments -> %s (fill human_label: positive / negative / neutral / unclear)"
          % (len(records), sheet_path))
    return 0


# ----------------------------------------------------------------------------------------------- scoring

class ModelScorers:
    """VADER (NLTK) and FinBERT (P(pos) - P(neg), same conversion as etl/sentiment_finbert.py) on any device.
    fp32 here; the stored scores were made in fp16 on a GPU, so variant B is also recomputed as a consistency check."""

    def __init__(self, device="auto"):
        import torch
        from nltk.sentiment.vader import SentimentIntensityAnalyzer
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        from etl.sentiment_finbert import MAX_LEN, MODEL_NAME
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
        self.torch, self.device, self.max_len = torch, device, MAX_LEN
        self.vader = SentimentIntensityAnalyzer()
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        self.model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME).to(device).eval()
        labels = {int(k): v.lower() for k, v in self.model.config.id2label.items()}
        self.pos = next(k for k, v in labels.items() if v == "positive")
        self.neg = next(k for k, v in labels.items() if v == "negative")

    def vader_scores(self, texts):
        return [self.vader.polarity_scores(text)["compound"] for text in texts]

    def finbert_scores(self, texts, batch_size=32):
        scores = []
        with self.torch.inference_mode():
            for first in range(0, len(texts), batch_size):
                batch = self.tokenizer(texts[first:first + batch_size], truncation=True, max_length=self.max_len,
                                       padding=True, return_tensors="pt").to(self.device)
                probs = self.torch.softmax(self.model(**batch).logits.float(), dim=-1)
                scores += (probs[:, self.pos] - probs[:, self.neg]).cpu().tolist()
        return scores


def score_variants(rows, scorers):
    """rows: [(sample_id, rule_signal, {variant: text}, stored B row dict)] -> list of SCORE_COLUMNS tuples.

    A variant whose text equals B's reuses B's stored scores (no model run); the rest is scored by `scorers`
    (any object with vader_scores / finbert_scores).  Also returns "B_recomputed" rows as a consistency check."""
    todo = []                                              # (sample_id, variant, text)
    for sample_id, _, texts, _ in rows:
        for variant in VARIANTS:
            if variant != "B" and texts[variant] != texts["B"]:
                todo.append((sample_id, variant, texts[variant]))
        todo.append((sample_id, "B_recomputed", texts["B"]))
    texts = [item[2] for item in todo]
    fresh = dict(zip(((i[0], i[1]) for i in todo), zip(scorers.vader_scores(texts), scorers.finbert_scores(texts))))
    out = []
    for sample_id, rule, texts, stored in rows:
        for variant in VARIANTS + ("B_recomputed",):
            reused = variant in VARIANTS and (variant == "B" or (sample_id, variant) not in fresh)
            if reused:
                vader, finbert = float(stored["vader_score"]), float(stored["finbert_score"])
            else:
                vader, finbert = fresh[(sample_id, variant)]
            final, method = resolve(vader, finbert, rule)
            out.append((sample_id, variant, int(reused), vader, finbert, rule, final, status_of(final), method,
                        is_ambiguous(method)))
    return out


def score(args, scorers=None):
    out = Path(args.out_dir)
    with (out / "sample_key.csv").open(newline="", encoding="utf-8") as handle:
        key = list(csv.DictReader(handle))
    db = connect(args.db, readonly=True)
    try:
        rows = []
        for item in key:
            rowid = int(item["src_rowid"])
            own, final_text = db.execute("SELECT own_text, final_text FROM filtered_text WHERE src_rowid = ?",
                                         (rowid,)).fetchone()
            title, body = post_context(db, rowid)
            rows.append((item["sample_id"], item["rule_signal"], variant_texts(own, final_text, title, body), item))
    finally:
        db.close()
    scorers = scorers or ModelScorers(args.device)
    result = score_variants(rows, scorers)
    path = out / "variant_scores.csv"
    with path.open("w", newline="", encoding="utf-8") as sink:
        sink.write("\n".join(file_header(
            "คะแนน VADER/FinBERT และผลกฎรวมของข้อความ 3 แบบ (A คอมเมนต์อย่างเดียว, B หัวข้อโพสต์+คอมเมนต์, "
            "C หัวข้อ+เนื้อโพสต์ %d ตัวอักษรแรก+คอมเมนต์) ของคอมเมนต์ที่สุ่มไว้; B_recomputed = คำนวณ B ใหม่เพื่อตรวจว่าตรงกับค่าที่เก็บไว้"
            % POST_BODY_CHARS, "scripts/rule_validation.py score", "python steps/26_rule_validation.py score",
            "sample_key.csv + filtered_text + reddit_content", comment=True)) + "\n")
        writer = csv.writer(sink)
        writer.writerow(SCORE_COLUMNS)
        writer.writerows(result)
    same = [r for r in result if r[1] == "B_recomputed"]
    stored = {item["sample_id"]: item["final_status"] for item in key}
    agree = sum(r[7] == stored[r[0]] for r in same)
    print("wrote %d rows -> %s; B recomputed vs stored final_status agree on %d/%d" % (len(result), path, agree, len(same)))
    return 0


# ----------------------------------------------------------------------------------------------- evaluation

def normalise(label):
    label = (label or "").strip().lower()
    label = LABEL_ALIASES.get(label, label)
    return label if label in LABELS or label == UNCLEAR else None


def read_sheet(out):
    """(labelled [(key row, label)], unlabelled count, unclear count, {sample_id: second label}) for one folder."""
    with (out / "sample_key.csv").open(newline="", encoding="utf-8") as handle:
        key = {row["sample_id"]: row for row in csv.DictReader(handle)}
    labelled, unlabelled, unclear, second = [], 0, 0, {}
    with (out / "labeling_sheet.csv").open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            label = normalise(row["human_label"])
            other = normalise(row.get("human_label_2", ""))
            if other in LABELS:
                second[row["sample_id"]] = other
            if label is None:
                unlabelled += 1
            elif label == UNCLEAR:
                unclear += 1
            else:
                labelled.append((key[row["sample_id"]], label))
    return labelled, unlabelled, unclear, second


def read_labelled(out):
    """[(key row dict, human label)] for every sheet row that has a usable label, and how many rows were skipped."""
    labelled, unlabelled, unclear, _ = read_sheet(out)
    return labelled, unlabelled + unclear


def read_variants(out):
    """{variant: {sample_id: {"vader", "finbert", "final", "final_status"}}} with B from the stored scores, plus the
    cascade; {} when `score` has not been run."""
    path = out / "variant_scores.csv"
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        lines = (line for line in handle if not line.startswith("#"))
        found = {}
        for row in csv.DictReader(lines):
            found.setdefault(row["variant"], {})[row["sample_id"]] = {
                "vader": status_of(float(row["vader_score"])), "finbert": status_of(float(row["finbert_score"])),
                "final": row["final_status"]}
    variants = {name: found[name] for name in VARIANTS if name in found}
    if len(variants) == len(VARIANTS):
        variants["cascade"] = {}
        for sample_id in variants["A"]:
            for name in VARIANTS:
                if variants[name][sample_id]["final"] != "neutral" or name == "C":
                    variants["cascade"][sample_id] = {"final": variants[name][sample_id]["final"]}
                    break
    return variants


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


def weighted_accuracy(rows, correct):
    """Accuracy of `correct(key row, label) -> bool` over `rows`, every stratum weighted by its population."""
    per = {}
    for row, label in rows:
        cell = per.setdefault(row["stratum"], [int(row["stratum_population"]), 0, 0])
        cell[1] += 1
        cell[2] += bool(correct(row, label))
    total = sum(cell[0] for cell in per.values())
    return sum(pop * hit / n for pop, n, hit in per.values()) / total if total else None


def weighted_overall(labelled, split):
    """Accuracy of each method on `split`, every stratum weighted by its population in the filtered texts."""
    rows = [(r, lab) for r, lab in labelled if r["split"] == split]
    if not rows:
        return None
    return {method: weighted_accuracy(rows, lambda r, lab, m=method: r[m + "_status"] == lab)
            for method in ("vader", "finbert", "final")}


def paired_p(a, b):
    """Exact two-sided binomial (sign) test p-value for a vs b discordant pairs; 1.0 when there are none."""
    n = a + b
    if not n:
        return 1.0
    tail = sum(comb(n, k) for k in range(min(a, b) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def holm(pvalues):
    """Holm-Bonferroni adjusted p-values, in the input order."""
    order = sorted(range(len(pvalues)), key=lambda i: pvalues[i])
    adjusted, running = [1.0] * len(pvalues), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(pvalues) - rank) * pvalues[i]))
        adjusted[i] = running
    return adjusted


def wilson(hits, n, z=1.96):
    """95% Wilson interval (low, high) for hits/n."""
    if not n:
        return 0.0, 0.0
    p = hits / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def kappa(pairs):
    """Cohen's kappa of [(label 1, label 2)]; None with fewer than 2 pairs or no disagreement possible."""
    n = len(pairs)
    if n < 2:
        return None
    observed = sum(a == b for a, b in pairs) / n
    expected = sum((sum(a == c for a, _ in pairs) / n) * (sum(b == c for _, b in pairs) / n) for c in LABELS)
    return None if expected == 1 else (observed - expected) / (1 - expected)


COMPARATORS = (("VADER", lambda r, lab: r["vader_status"] == lab), ("FinBERT", lambda r, lab: r["finbert_status"] == lab),
               ("เป็นกลางทุกข้อ", lambda r, lab: lab == "neutral"))


def rule_rows(labelled):
    """[(stratum, comparator name, n, final hits, other hits, only final, only other, p)] for one set of rows."""
    result = []
    for stratum in STRATA:
        rows = [(r, lab) for r, lab in labelled if r["stratum"] == stratum]
        if not rows:
            continue
        for name, other in COMPARATORS:
            only_final = sum(r["final_status"] == lab and not other(r, lab) for r, lab in rows)
            only_other = sum(other(r, lab) and r["final_status"] != lab for r, lab in rows)
            hits_final = sum(r["final_status"] == lab for r, lab in rows)
            hits_other = sum(other(r, lab) for r, lab in rows)
            result.append((stratum, name, len(rows), hits_final, hits_other, only_final, only_other,
                           paired_p(only_final, only_other)))
    return result


def rule_table(title, rows, with_holm):
    lines = ["### " + title, "",
             "| กลุ่ม | เทียบกับ | n | final (ช่วงเชื่อมั่น 95%) | วิธีเทียบ | ถูกเฉพาะ final | ถูกเฉพาะวิธีเทียบ | p | p (Holm) |",
             "|---|---|---|---|---|---|---|---|---|"]
    adjusted = holm([r[7] for r in rows]) if with_holm else [None] * len(rows)
    for (stratum, name, n, hit_f, hit_o, only_f, only_o, p), adj in zip(rows, adjusted):
        low, high = wilson(hit_f, n)
        lines.append("| %s | %s | %d | %.1f%% (%.0f–%.0f) | %.1f%% | %d | %d | %.3f | %s |" % (
            stratum, name, n, 100.0 * hit_f / n, 100 * low, 100 * high, 100.0 * hit_o / n, only_f, only_o, p,
            "%.3f" % adj if adj is not None else "–"))
    return lines + [""]


def variant_section(labelled, variants):
    """Markdown lines comparing text variants A/B/C and the cascade."""
    lines = ["## รูปแบบข้อความ: A คอมเมนต์อย่างเดียว / B หัวข้อโพสต์+คอมเมนต์ / C หัวข้อ+เนื้อโพสต์+คอมเมนต์ / cascade", "",
             "cascade = ใช้ A; ถ้าได้ neutral ใช้ B; ถ้ายัง neutral ใช้ C. ป้ายคนเป็นท่าทีของผู้เขียนคอมเมนต์ที่อ่านพร้อมบริบทโพสต์ "
             "จึงไม่เอนเอียงไปทางรูปแบบใดรูปแบบหนึ่ง. ความแม่นถ่วงน้ำหนักตามจำนวนข้อความของแต่ละกลุ่ม (กลุ่มถูกกำหนดจากกฎของ B)", "",
             "| รูปแบบ | ชุด | n | VADER | FinBERT | final |", "|---|---|---|---|---|---|"]
    for name in ("A", "B", "C", "cascade"):
        if name not in variants:
            continue
        for split in ("tune", "test", None):
            rows = [(r, lab) for r, lab in labelled if (split is None or r["split"] == split)]
            if not rows:
                continue
            cells = []
            for method in ("vader", "finbert", "final"):
                if method not in variants[name].get(rows[0][0]["sample_id"], {}):
                    cells.append("–")
                    continue
                value = weighted_accuracy(rows, lambda r, lab, m=method, v=name: variants[v][r["sample_id"]][m] == lab)
                cells.append("%.1f%%" % (100 * value))
            lines.append("| %s | %s | %d | %s |" % (name, split or "รวม", len(rows), " | ".join(cells)))
    lines += ["", "### เทียบเป็นคู่กับ B (final ของแต่ละรูปแบบ)", "",
              "ถูกเฉพาะรูปแบบนั้น = รูปแบบนั้นถูกแต่ B ผิด. C เทียบเฉพาะคอมเมนต์ที่โพสต์มีเนื้อหา (ที่เหลือ C = B); "
              "A เทียบเฉพาะคอมเมนต์ที่รู้หัวข้อโพสต์ (ที่เหลือ A = B)", "",
              "| รูปแบบ | ชุด | n | ถูกเฉพาะรูปแบบนั้น | ถูกเฉพาะ B | p |", "|---|---|---|---|---|---|"]
    for name in ("A", "C", "cascade"):
        if name not in variants:
            continue
        for split in ("tune", "test", None):
            rows = [(r, lab) for r, lab in labelled if (split is None or r["split"] == split)]
            if name == "C":
                rows = [(r, lab) for r, lab in rows if r["post_has_body"] == "1"]
            if name == "A":
                rows = [(r, lab) for r, lab in rows if r["post_known"] == "1"]
            only_v = sum(variants[name][r["sample_id"]]["final"] == lab and r["final_status"] != lab for r, lab in rows)
            only_b = sum(r["final_status"] == lab and variants[name][r["sample_id"]]["final"] != lab for r, lab in rows)
            lines.append("| %s | %s | %d | %d | %d | %.3f |" % (name, split or "รวม", len(rows), only_v, only_b,
                                                                 paired_p(only_v, only_b)))
    return lines + [""]


def distribution_section(labelled):
    lines = ["## ป้ายของคนในแต่ละกลุ่มกฎ (ตอบ \"ข้อความกลุ่มนี้เป็นบวก/ลบ/กลางจริงกี่ข้อความ\")", "",
             "| กลุ่ม | n | positive | negative | neutral |", "|---|---|---|---|---|"]
    groups = [(stratum, [(r, lab) for r, lab in labelled if r["stratum"] == stratum]) for stratum in STRATA]
    groups.append(("(เฉพาะแถวที่ระบบตั้งสถานะกำกวม is_ambiguous=1)", [(r, lab) for r, lab in labelled
                                                                       if r["is_ambiguous"] == "1"]))
    for name, rows in groups:
        if rows:
            counts = [sum(lab == label for _, lab in rows) for label in LABELS]
            lines.append("| %s | %d | %s |" % (name, len(rows), " | ".join(
                "%d (%.0f%%)" % (c, 100.0 * c / len(rows)) for c in counts)))
    return lines + [""]


def evaluate(args):
    out = Path(args.out_dir)
    labelled, unlabelled, unclear, second = read_sheet(out)
    if not labelled:
        raise SystemExit("no labelled rows in %s - fill human_label first" % (out / "labeling_sheet.csv"))
    table = accuracy_table(labelled)
    variants = read_variants(out)
    lines = ["# Rule validation (proposal 7.3 step 5)", "",
             *file_header("ความแม่นของ VADER เดี่ยว, FinBERT เดี่ยว, วิธีรวมผล และรูปแบบข้อความ 3 แบบ เมื่อเทียบกับป้ายที่ผู้พัฒนาติดเอง "
                          "(%d คอมเมนต์ที่ใช้ได้, ยังไม่มีป้าย %d, ติด unclear %d)" % (len(labelled), unlabelled, unclear),
                          "scripts/rule_validation.py evaluate", "python steps/26_rule_validation.py evaluate",
                          "labeling_sheet.csv (ป้าย) + sample_key.csv + variant_scores.csv ในโฟลเดอร์เดียวกัน"), "",
             "ความแม่น = สัดส่วนที่ประเภทความรู้สึก (positive/negative/neutral) ตรงกับป้ายที่ผู้พัฒนาติดเอง; "
             "ชุด tune ใช้ปรับกฎ, ชุด test ใช้ยืนยัน/รายงานผล", "",
             "**เกณฑ์ตัดสินที่ตั้งไว้ก่อนดูผล:** จะเปลี่ยนกฎ (หรือรูปแบบข้อความ) ก็ต่อเมื่อทางเลือกชนะ final อย่างน้อย 5 จุดในชุด tune "
             "**และ** ชุด test ให้ทิศทางเดียวกันด้วย sign test p < 0.05 (แบบดิบ) — ถ้าไม่ถึง ถือว่า \"แยกไม่ออก\" และคงกฎเดิม. "
             "ตารางเทียบกฎมี 21 การทดสอบ จึงแสดง p ที่ปรับด้วย Holm ควบคู่ด้วย", ""]
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
    lines += distribution_section(labelled)
    lines += ["## เทียบกฎรวมผล (final) กับทางเลือกง่าย ๆ ทีละกลุ่ม", "",
              "ทางเลือก: ใช้ VADER เดี่ยว, FinBERT เดี่ยว, หรือตอบ neutral ทุกข้อ (= \"คง neutral\" ตามข้อสังเกตของอาจารย์). "
              "p = exact binomial สองทางของสองคอลัมน์ \"ถูกเฉพาะ\" (p สูง = แยกไม่ออกว่าวิธีไหนดีกว่า)", ""]
    for title, split in (("ชุด test (ใช้ยืนยัน)", "test"), ("ชุด tune (ใช้ปรับ)", "tune"), ("รวมทั้งหมด (เพิ่มกำลังทดสอบ)", None)):
        rows = [(r, lab) for r, lab in labelled if split is None or r["split"] == split]
        lines += rule_table(title, rule_rows(rows), with_holm=split == "test")
    if variants:
        lines += variant_section(labelled, variants)
    else:
        lines += ["## รูปแบบข้อความ A/B/C", "", "ยังไม่มี variant_scores.csv — รัน `score` ก่อน", ""]
    pairs = [(lab, second[r["sample_id"]]) for r, lab in labelled if r["sample_id"] in second]
    if pairs:
        value = kappa(pairs)
        lines += ["## ความสอดคล้องระหว่างผู้ติดป้าย", "",
                  "ผู้ติดป้ายสองคนตรงกัน %d/%d ข้อความ, Cohen's kappa = %s" % (
                      sum(a == b for a, b in pairs), len(pairs), "–" if value is None else "%.2f" % value), ""]
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
    drawer = sub.add_parser("sample", help="draw the stratified sample of comments and write the labeling sheet")
    drawer.add_argument("--db", default=str(DEFAULT_DB))
    drawer.add_argument("--per-stratum", type=int, default=50)
    drawer.add_argument("--boost", action="append", metavar="STRATUM=N",
                        help="larger sample for one stratum, e.g. small_conflict_no_keyword=100 (repeatable)")
    drawer.add_argument("--seed", type=int, default=20261104)
    drawer.add_argument("--force", action="store_true", help="overwrite an existing labeling sheet")
    drawer.add_argument("--out-dir", default=str(OUT_DIR))
    drawer.add_argument("--stratum", action="append", help="draw only this stratum (repeatable)")
    drawer.add_argument("--exclude-dir", action="append",
                        help="never re-draw texts listed in <dir>/sample_key.csv (repeatable)")
    scorer = sub.add_parser("score", help="score the three text variants of every sampled comment")
    scorer.add_argument("--db", default=str(DEFAULT_DB))
    scorer.add_argument("--out-dir", default=str(OUT_DIR))
    scorer.add_argument("--device", default="auto", choices=("auto", "cpu", "mps", "cuda"))
    checker = sub.add_parser("evaluate", help="compare VADER / FinBERT / final / text variants against the human labels")
    checker.add_argument("--out-dir", default=str(OUT_DIR))
    args = parser.parse_args(argv)
    return {"sample": sample, "score": score, "evaluate": evaluate}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
