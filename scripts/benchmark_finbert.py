"""S0: measure FinBERT throughput on real Reddit text from the 6 in-scope subreddits.

Samples texts deterministically (rowid % 2000 == 7), runs ProsusAI/finbert in fp16 with
length-sorted batches for several (max_len, batch) settings, and reports texts/second and the
projected hours for the full corpus. Also reports how many FinBERT scores
(P(positive) - P(negative)) fall inside the neutral band.

Usage:
    python scripts/benchmark_finbert.py [--db output/reddit.sqlite3] [--out output/benchmark_finbert.json]
"""
import argparse
import json
import sqlite3
import time
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

# TODO: move to configs/subreddits.yaml once the config layer exists (one place for the 6 communities).
SUBREDDITS = ("wallstreetbets", "stocks", "investing", "StockMarket", "options", "CryptoCurrency")
NEUTRAL_BAND = 0.05
SETTINGS = ((128, 128), (256, 128), (256, 256), (512, 128))   # (max_len, batch_size)
REFERENCE = (256, 128)                                       # setting used for the score distribution


def load_texts(db_path, n):
    db = sqlite3.connect("file:" + Path(db_path).resolve().as_posix() + "?mode=ro", uri=True)
    rows = db.execute(
        "SELECT content_type, body, title, selftext FROM reddit_content "
        "WHERE text_status='available' AND subreddit IN (%s) AND rowid %% 2000 = 7 LIMIT ?"
        % ",".join("?" * len(SUBREDDITS)), SUBREDDITS + (n,)).fetchall()
    texts, comments = [], 0
    for content_type, body, title, selftext in rows:
        text = body if content_type == "comment" else ((title or "") + " " + (selftext or "")).strip()
        if text and text.strip():
            texts.append(text)
            comments += content_type == "comment"
    return texts, comments


def run(texts, tokenizer, model, pos, neg, max_len, batch_size, total_texts):
    start = time.perf_counter()
    encoded = tokenizer(texts, truncation=True, max_length=max_len)["input_ids"]
    tokenize_s = time.perf_counter() - start
    order = sorted(range(len(encoded)), key=lambda i: len(encoded[i]))
    scores = [0.0] * len(encoded)
    torch.cuda.reset_peak_memory_stats()

    def batches():
        for first in range(0, len(order), batch_size):
            index = order[first:first + batch_size]
            width = max(len(encoded[i]) for i in index)
            ids = torch.zeros((len(index), width), dtype=torch.long)
            mask = torch.zeros((len(index), width), dtype=torch.long)
            for row, i in enumerate(index):
                ids[row, :len(encoded[i])] = torch.tensor(encoded[i])
                mask[row, :len(encoded[i])] = 1
            yield index, ids.cuda(non_blocking=True), mask.cuda(non_blocking=True)

    with torch.inference_mode():
        for n, (_, ids, mask) in enumerate(batches()):      # warm-up on the first 3 batches
            if n == 3:
                break
            model(input_ids=ids, attention_mask=mask)
        torch.cuda.synchronize()
        start = time.perf_counter()
        for index, ids, mask in batches():
            probs = torch.softmax(model(input_ids=ids, attention_mask=mask).logits.float(), dim=-1)
            for i, value in zip(index, (probs[:, pos] - probs[:, neg]).cpu().tolist()):
                scores[i] = value
        torch.cuda.synchronize()
        gpu_s = time.perf_counter() - start
    per_s_total = len(texts) / (tokenize_s + gpu_s)
    return {
        "max_len": max_len, "batch": batch_size,
        "tokenize_s": round(tokenize_s, 2), "gpu_s": round(gpu_s, 2),
        "texts_per_s_gpu": round(len(texts) / gpu_s), "texts_per_s_total": round(per_s_total),
        "est_hours_all": round(total_texts / per_s_total / 3600, 2),
        "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2),
        "mean_tokens": round(sum(len(e) for e in encoded) / len(encoded), 1),
        "truncated_pct": round(100 * sum(len(e) >= max_len for e in encoded) / len(encoded), 2),
    }, scores


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default="output/reddit.sqlite3")
    parser.add_argument("--out", default="output/benchmark_finbert.json")
    parser.add_argument("--n", type=int, default=10_000, help="number of sample texts")
    parser.add_argument("--total", type=int, default=22_840_886,
                        help="texts to project to (in-scope, text_status='available')")
    args = parser.parse_args()

    texts, comments = load_texts(args.db, args.n)
    print("texts: %d (comments %d)" % (len(texts), comments), flush=True)
    assert torch.cuda.is_available(), "CUDA is not available"
    gpu = torch.cuda.get_device_name(0)
    print("GPU:", gpu, "| torch", torch.__version__, "| cuda", torch.version.cuda, flush=True)

    tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
    model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert").half().cuda().eval()
    labels = {int(k): v.lower() for k, v in model.config.id2label.items()}
    pos = next(k for k, v in labels.items() if v == "positive")
    neg = next(k for k, v in labels.items() if v == "negative")

    results, reference_scores = [], None
    for max_len, batch_size in SETTINGS:
        result, scores = run(texts, tokenizer, model, pos, neg, max_len, batch_size, args.total)
        print(json.dumps(result), flush=True)
        results.append(result)
        if (max_len, batch_size) == REFERENCE:
            reference_scores = scores

    n = len(reference_scores)
    summary = {
        "gpu": gpu, "torch": torch.__version__, "n": len(texts), "comments": comments,
        "projected_texts": args.total, "reference_setting": {"max_len": REFERENCE[0], "batch": REFERENCE[1]},
        "score": "P(positive) - P(negative)", "neutral_band": NEUTRAL_BAND,
        "finbert_neutral_band_share": round(sum(abs(s) <= NEUTRAL_BAND for s in reference_scores) / n, 3),
        "positive_share": round(sum(s > NEUTRAL_BAND for s in reference_scores) / n, 3),
        "negative_share": round(sum(s < -NEUTRAL_BAND for s in reference_scores) / n, 3),
    }
    print(json.dumps(summary), flush=True)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({"summary": summary, "results": results}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
