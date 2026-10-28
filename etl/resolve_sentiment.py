"""S3 + S4: keyword rule signal and conflict resolution -> table `sentiment_item`.

    sentiment_item(src_rowid, vader_score, vader_status, finbert_score, finbert_status,
                   rule_signal, final_sentiment, final_status, final_method, is_ambiguous)

S3 rule_signal  positive / negative / mixed / none  from the keyword lists in configs/sentiment.yaml, searched in
                own_text = what the author of the row wrote (a keyword in the post title is the poster's opinion, not the commenter's).
                A keyword with a negator in the 2 words before it ("not bullish") is ignored, not flipped.
S4 resolution   proposal 7.3 step 3 (three cases). Cases the proposal does not cover are EXTENSIONS and are
                tagged in final_method so they can be counted in the report:
    final_method                 case
    ---------------------------  ----------------------------------------------------------------------
    same_direction               both models positive (or both negative), scores differ <= 0.50 -> mean
    same_direction_far           same direction but scores differ > 0.50 -> the score closer to 0 (p30)
    small_conflict_rule_agrees   one neutral, one directional, keyword agrees with the directional -> its score
    small_conflict_rule_clash    ... keyword opposes it or is mixed                               -> 0.0
    small_conflict_no_rule       ... no keyword                                                   -> directional score
    hard_conflict_rule           opposite directions, keyword positive/negative -> score of the model that agrees
    hard_conflict_no_rule        opposite directions, no keyword                                  -> 0.0
    both_neutral                 (extension) both neutral                                         -> mean
    hard_conflict_mixed_zero     (extension) opposite directions, keyword mixed                   -> 0.0
    one_model                    (extension) only one model has a score                           -> that score
is_ambiguous = 1 when the final 0.0 comes from a conflict the system cannot decide (proposal Table 11):
hard_conflict_no_rule, hard_conflict_mixed_zero, small_conflict_rule_clash. final_sentiment stays 0.0 and
final_status neutral so downstream maths still works; analyses can drop or report the flag separately.
Status labels use etl.common.status_of (closed neutral band +-0.05). Resumable by src_rowid.
`--migrate` upgrades a sentiment_item built before same_direction_far / is_ambiguous existed, in place, from the
stored scores (no model re-run).

Usage:
    python -m etl.resolve_sentiment [--db output/reddit.sqlite3] [--window N] [--limit-rows N] [--rebuild | --migrate]
"""

import argparse
import re
import sys
import time

from etl.common import DEFAULT_DB, NEUTRAL_BAND, connect, load_yaml, status_of
from ingest.pipeline_logs import append_event, run_id

RESOLVER_VERSION = "1.1"

AMBIGUOUS_METHODS = ("hard_conflict_no_rule", "hard_conflict_mixed_zero", "small_conflict_rule_clash")
FLOAT_SLACK = 1e-9      # 0.9 - 0.4 must count as exactly 0.50, not 0.5000000000000001

SCHEMA = """CREATE TABLE IF NOT EXISTS sentiment_item (
    src_rowid INTEGER PRIMARY KEY,
    vader_score REAL, vader_status TEXT,
    finbert_score REAL, finbert_status TEXT,
    rule_signal TEXT NOT NULL,
    final_sentiment REAL NOT NULL,
    final_status TEXT NOT NULL,
    final_method TEXT NOT NULL,
    is_ambiguous INTEGER NOT NULL DEFAULT 0)"""


def same_direction_max_gap():
    """Largest VADER/FinBERT score gap still averaged (configs/sentiment.yaml, proposal 7.3 step 3)."""
    return float(load_yaml("sentiment.yaml")["same_direction_max_gap"])


def is_ambiguous(method):
    return int(method in AMBIGUOUS_METHODS)


class RuleMatcher:
    """Builds regexes from configs/sentiment.yaml; `signal(text)` returns positive/negative/mixed/none."""

    def __init__(self, config=None):
        config = config or load_yaml("sentiment.yaml")

        def alternation(words):
            return "|".join(sorted((re.escape(w).replace(r"\ ", r"\s+") for w in words), key=len, reverse=True))

        self._pos = re.compile(r"\b(?:%s)\b" % alternation(config["positive"]))
        self._neg = re.compile(r"\b(?:%s)\b" % alternation(config["negative"]))
        self._negators = set(config["negators"])
        self._word = re.compile(r"[a-z']+")

    def _hit(self, pattern, text):
        for match in pattern.finditer(text):
            before = self._word.findall(text[max(0, match.start() - 30):match.start()].replace("’", "'"))[-2:]
            if not any(w in self._negators for w in before):
                return True
        return False

    def signal(self, text):
        lowered = text.lower().replace("’", "'")
        pos, neg = self._hit(self._pos, lowered), self._hit(self._neg, lowered)
        return "mixed" if pos and neg else "positive" if pos else "negative" if neg else "none"


def resolve(vader, finbert, rule, max_gap=None, band=NEUTRAL_BAND):
    """(final_sentiment, final_method) from the two model scores (None = missing) and rule_signal."""
    max_gap = same_direction_max_gap() if max_gap is None else max_gap
    if vader is None or finbert is None:
        only = finbert if vader is None else vader
        return only, "one_model"
    vs, fs = status_of(vader, band), status_of(finbert, band)
    if vs == fs:
        if vs == "neutral":
            return (vader + finbert) / 2, "both_neutral"
        if abs(vader - finbert) > max_gap + FLOAT_SLACK:
            return min(vader, finbert, key=abs), "same_direction_far"
        return (vader + finbert) / 2, "same_direction"
    if "neutral" in (vs, fs):                                   # Small Conflict
        direction, score = (vs, vader) if fs == "neutral" else (fs, finbert)
        if rule == "none":
            return score, "small_conflict_no_rule"
        return (score, "small_conflict_rule_agrees") if rule == direction else (0.0, "small_conflict_rule_clash")
    # Hard Conflict: opposite directions
    if rule == "none":
        return 0.0, "hard_conflict_no_rule"
    if rule == "mixed":
        return 0.0, "hard_conflict_mixed_zero"
    return (vader if vs == rule else finbert), "hard_conflict_rule"


def process(db_path=DEFAULT_DB, window=200_000, limit_rows=None, rebuild=False):
    db = connect(db_path)
    try:
        return _process(db, window, limit_rows, rebuild)
    finally:
        db.close()


def _process(db, window, limit_rows, rebuild):
    matcher = RuleMatcher()
    max_gap = same_direction_max_gap()
    if rebuild:
        db.execute("DROP TABLE IF EXISTS sentiment_item")
    elif _has_table(db) and not _has_ambiguous_column(db):
        raise SystemExit("sentiment_item predates is_ambiguous / same_direction_far: run with --migrate first")
    db.execute(SCHEMA)
    db.commit()
    done = db.execute("SELECT COALESCE(MAX(src_rowid), 0) FROM sentiment_item").fetchone()[0]
    last = db.execute("SELECT MAX(src_rowid) FROM processed_text").fetchone()[0] or 0
    if limit_rows:
        last = min(last, done + limit_rows)
    this_run = run_id()
    append_event(db, "resolve_sentiment_start", run_id=this_run, version=RESOLVER_VERSION, resume_from=done)
    written, started = 0, time.time()
    while done < last:
        upper = min(done + window, last)
        rows = db.execute(
            "SELECT t.src_rowid, t.own_text, v.vader_score, f.finbert_score FROM filtered_text t "
            "LEFT JOIN sentiment_vader v ON v.src_rowid = t.src_rowid "
            "LEFT JOIN sentiment_finbert f ON f.src_rowid = t.src_rowid "
            "WHERE t.src_rowid > ? AND t.src_rowid <= ?", (done, upper)).fetchall()
        out = []
        for rowid, text, vs, fs in rows:
            rule = matcher.signal(text)
            score, method = resolve(vs, fs, rule, max_gap)
            out.append((rowid, vs, None if vs is None else status_of(vs), fs, None if fs is None else status_of(fs),
                        rule, score, status_of(score), method, is_ambiguous(method)))
        db.executemany("INSERT OR IGNORE INTO sentiment_item VALUES (?,?,?,?,?,?,?,?,?,?)", out)
        db.commit()
        done = upper
        written += len(out)
        print("rowid %d/%d  written %d  (%.0f texts/s)"
              % (done, last, written, written / max(time.time() - started, 1e-9)), flush=True)
    append_event(db, "resolve_sentiment_done", run_id=this_run, version=RESOLVER_VERSION, written=written)
    return {"written": written}


def _has_table(db):
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sentiment_item'").fetchone() is not None


def _has_ambiguous_column(db):
    return any(row[1] == "is_ambiguous" for row in db.execute("PRAGMA table_info(sentiment_item)"))


def migrate(db_path=DEFAULT_DB):
    """Add is_ambiguous and apply the 0.50 same-direction rule to an existing sentiment_item (idempotent)."""
    db = connect(db_path)
    try:
        max_gap = same_direction_max_gap() + FLOAT_SLACK
        if not _has_ambiguous_column(db):
            db.execute("ALTER TABLE sentiment_item ADD COLUMN is_ambiguous INTEGER NOT NULL DEFAULT 0")
        far = db.execute(
            "UPDATE sentiment_item SET final_sentiment = CASE WHEN ABS(vader_score) <= ABS(finbert_score) "
            "THEN vader_score ELSE finbert_score END, final_method = 'same_direction_far' "
            "WHERE final_method = 'same_direction' AND ABS(vader_score - finbert_score) > ?", (max_gap,)).rowcount
        flagged = db.execute(
            "UPDATE sentiment_item SET is_ambiguous = 1 WHERE final_method IN (%s) AND is_ambiguous = 0"
            % ",".join("?" * len(AMBIGUOUS_METHODS)), AMBIGUOUS_METHODS).rowcount
        db.commit()
        return {"same_direction_far": far, "flagged_ambiguous": flagged}
    finally:
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--window", type=int, default=200_000, help="processed_text rowids per batch")
    parser.add_argument("--limit-rows", type=int, help="resolve only this many rowids (trials)")
    parser.add_argument("--rebuild", action="store_true", help="drop sentiment_item and start over")
    parser.add_argument("--migrate", action="store_true",
                        help="add is_ambiguous + same_direction_far to an existing sentiment_item, in place")
    args = parser.parse_args(argv)
    if args.migrate:
        print("migrated:", migrate(args.db))
        return 0
    print("done:", process(args.db, args.window, args.limit_rows, args.rebuild))
    return 0


if __name__ == "__main__":
    sys.exit(main())
