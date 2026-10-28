"""S2: FinBERT sentiment for every text that passed T1 + T2 -> table `sentiment_finbert` (needs a CUDA GPU).

    sentiment_finbert(src_rowid, finbert_score, finbert_status)
      finbert_score  = P(positive) - P(negative) from ProsusAI/finbert, in [-1, 1]
                       (the proposal only says the score lies in [-1, 1]; this is our chosen conversion)
      finbert_status positive / negative / neutral with the +-0.05 neutral band (same band as VADER)

Settings come from the S0 benchmark (docs/benchmark_finbert.md): texts are cut at MAX_LEN = 256 tokens
(0.9 % of texts are longer), batches of 128, sorted by length inside each window to waste little padding.
Precision is fp16 unless --dtype fp32 (scripts/compare_finbert_precision.py checks that both agree).
Every row of filtered_text gets one score. Each window is written in ONE transaction, so killing the process
loses at most one window; rerunning continues after the highest src_rowid written.

Usage:
    python -m etl.sentiment_finbert [--db output/reddit.sqlite3] [--window N] [--limit-rows N]
                                    [--dtype fp16|fp32] [--rebuild]
"""

import argparse
import sys
import time

from etl.common import DEFAULT_DB, connect, status_of
from ingest.pipeline_logs import append_event, run_id

MODEL_NAME = "ProsusAI/finbert"
MAX_LEN = 256
BATCH_SIZE = 128

SCHEMA = """CREATE TABLE IF NOT EXISTS sentiment_finbert (
    src_rowid INTEGER PRIMARY KEY,
    finbert_score REAL NOT NULL,
    finbert_status TEXT NOT NULL)"""


class FinBert:
    """Thin wrapper: score(list of texts) -> list of P(positive) - P(negative)."""

    def __init__(self, dtype="fp16", max_len=MAX_LEN, batch_size=BATCH_SIZE):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        if not torch.cuda.is_available():
            raise SystemExit("CUDA GPU not available; FinBERT on 22 M texts needs the GPU")
        self.torch, self.max_len, self.batch_size = torch, max_len, batch_size
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
        self.model = (model.half() if dtype == "fp16" else model).cuda().eval()
        labels = {int(k): v.lower() for k, v in self.model.config.id2label.items()}
        self.pos = next(k for k, v in labels.items() if v == "positive")
        self.neg = next(k for k, v in labels.items() if v == "negative")

    def score(self, texts):
        torch = self.torch
        encoded = self.tokenizer(texts, truncation=True, max_length=self.max_len)["input_ids"]
        order = sorted(range(len(encoded)), key=lambda i: len(encoded[i]))     # similar lengths together
        scores = [0.0] * len(encoded)
        with torch.inference_mode():
            for first in range(0, len(order), self.batch_size):
                index = order[first:first + self.batch_size]
                width = max(len(encoded[i]) for i in index)
                ids = torch.zeros((len(index), width), dtype=torch.long)       # 0 = [PAD] for this tokenizer
                mask = torch.zeros((len(index), width), dtype=torch.long)
                for row, i in enumerate(index):
                    ids[row, :len(encoded[i])] = torch.tensor(encoded[i])
                    mask[row, :len(encoded[i])] = 1
                logits = self.model(input_ids=ids.cuda(), attention_mask=mask.cuda()).logits
                probs = torch.softmax(logits.float(), dim=-1)
                for i, value in zip(index, (probs[:, self.pos] - probs[:, self.neg]).cpu().tolist()):
                    scores[i] = value
        return scores


def process(db_path=DEFAULT_DB, window=50_000, limit_rows=None, dtype="fp16", rebuild=False, scorer=None):
    """`scorer` can be any object with .score(list_of_texts) (used by tests so no GPU is needed)."""
    db = connect(db_path)
    try:
        return _process(db, window, limit_rows, dtype, rebuild, scorer)
    finally:
        db.close()


def _process(db, window, limit_rows, dtype, rebuild, scorer):
    if rebuild:
        db.execute("DROP TABLE IF EXISTS sentiment_finbert")
    db.execute(SCHEMA)
    db.commit()
    done = db.execute("SELECT COALESCE(MAX(src_rowid), 0) FROM sentiment_finbert").fetchone()[0]
    last = db.execute("SELECT MAX(src_rowid) FROM processed_text").fetchone()[0] or 0
    if limit_rows:
        last = min(last, done + limit_rows)
    scorer = scorer or FinBert(dtype)
    this_run = run_id()
    append_event(db, "sentiment_finbert_start", run_id=this_run, model=MODEL_NAME, dtype=dtype, max_len=MAX_LEN,
                 resume_from=done)
    scored, started = 0, time.time()
    while done < last:
        upper = min(done + window, last)
        rows = db.execute("SELECT src_rowid, final_text FROM filtered_text WHERE src_rowid > ? AND src_rowid <= ?",
                          (done, upper)).fetchall()
        scores = scorer.score([text for _, text in rows]) if rows else []
        db.executemany("INSERT OR IGNORE INTO sentiment_finbert VALUES (?,?,?)",
                       [(rowid, score, status_of(score)) for (rowid, _), score in zip(rows, scores)])
        db.commit()
        done = upper
        scored += len(rows)
        print("rowid %d/%d  scored %d  (%.0f texts/s)"
              % (done, last, scored, scored / max(time.time() - started, 1e-9)), flush=True)
    append_event(db, "sentiment_finbert_done", run_id=this_run, model=MODEL_NAME, dtype=dtype, scored=scored)
    return {"scored": scored}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--window", type=int, default=50_000, help="processed_text rowids per batch")
    parser.add_argument("--limit-rows", type=int, help="score only this many rowids (trials)")
    parser.add_argument("--dtype", choices=("fp16", "fp32"), default="fp16")
    parser.add_argument("--rebuild", action="store_true", help="drop sentiment_finbert and start over")
    args = parser.parse_args(argv)
    print("done:", process(args.db, args.window, args.limit_rows, args.dtype, args.rebuild))
    return 0


if __name__ == "__main__":
    sys.exit(main())
