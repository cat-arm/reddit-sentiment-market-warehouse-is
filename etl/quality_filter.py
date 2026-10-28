"""T2: decide which cleaned texts are NOT real investor opinion, and write an audit of everything dropped.

Reads `processed_text` (made by T1) and writes two NEW tables (raw `reddit_content` is never changed):
  * text_filter(src_rowid, reason)  - only the REJECTED rows. A row in processed_text with no row here "passed".
  * data_quality_audit(ts_hour, subreddit, content_type, remove_reason, row_count) - every raw row of the
    6 communities falls into exactly one reason, so  sum(row_count) = raw rows  (the T2 definition of done).
and a view `filtered_text` = processed_text without the rejected rows. Later steps (T4, S1, S2) read that view.

Reasons (single enum, checked in this order):
  bot_or_moderation_text  AutoModerator / bot replies / removal notices / "!banbet" (old notebook's rule
                          "moderator" was far too broad and is NOT ported: it would delete real opinions)
  too_short               fewer than 2 letters (e.g. "!!!", "+10%", "420"); short words like "Yes"/"lol" are KEPT
  non_english             proposal 4.1 limitation. Cheap heuristic, no model, see _is_non_english()
  (from text_status)      removed / deleted / empty   -> text was already gone in the raw data
  empty_after_cleaning    text existed but T1 cleaning left nothing (image-only post, only a link)
  passed

Usage:
    python -m etl.quality_filter [--db output/reddit.sqlite3] [--window N] [--limit-rows N]
Always rebuilds both tables (fast, ~10 min), so reruns after a rule change are safe.
"""

import argparse
import re
import sys
import time
from collections import Counter

from etl.common import DEFAULT_DB, connect, subreddits
from ingest.pipeline_logs import append_event, run_id

FILTER_VERSION = "1.1"      # 1.1: judges processed_text.own_text (what the author wrote), not the title-prefixed final_text

# --- 1) bot / moderation text -------------------------------------------------------------------
# Phrases copied from the most frequent duplicated texts found in processed_text (checked 2026-10-09:
# "I am a bot, and this action was performed automatically", "Your submission was removed because...",
# "!banbet", "[ Removed by moderator ]", WSB gain/loss-porn rules, CryptoCurrency image rule, ...).
# All phrases are specific on purpose; a generic word such as "moderator" would hit normal opinions.
_BOT_PHRASES = (
    r"i am a bot", r"i am an? llm[- ]powered bot", r"this action was performed automatically",
    r"performed automatically", r"contact the moderators", r"message the mods",
    r"automoderator", r"visualmod",
    r"^!banbet", r"^\[ ?removed by (?:moderator|reddit) ?\]", r"^\[ ?deleted by user ?\]",
    r"^(?:sorry,? )?your (?:text )?(?:post|submission|comment)(?: in)?(?:/comment)? (?:was|has been|have been)"
    r"(?: automatically)? removed",
    r"your submission in .{0,20}was automatically removed",
    r"has been automatically removed", r"was automatically removed",
    r"your (?:reddit )?account is either less than",
    r"insufficient karma",
    r"direct links to images are require",
    r"this looks like a basic question",
    r"thanks for your submission! to keep things interesting",
    r"does not allow link-only or screenshot posts",
    r"most mentions on r/", r"most mentions on ",
    r"^user reports?\b", r"\btotal submissions\b", r"\bfirst seen in\b",
    r"please reply to this comment with your position",
)
_BOT = re.compile("|".join("(?:%s)" % p for p in _BOT_PHRASES), re.IGNORECASE)

# --- 2) too short -------------------------------------------------------------------------------
_PLACEHOLDER_TEXT = {"n/a", "na", "test", "nan", "none", "null", "deleted", "removed"}

# --- 3) non-English (cheap heuristic, no per-row language model: 22.8 M rows) -------------------
# (a) text written mostly in a non-Latin script (Chinese, Russian, Arabic, Thai...) -> reject
# (b) Latin-script foreign text (Spanish, German, French, Portuguese...) -> reject only if the text has
#     several unmistakable foreign function words AND very few English ones. Needing BOTH conditions keeps
#     jargon-heavy English such as "TSLA 450c 3/21 calls printing" safe.
_TOKEN = re.compile(r"[a-zà-ÿ']+", re.IGNORECASE)
_ENGLISH_WORDS = frozenset(
    "the a an and or but of to in on at for with from by is are was were be been it this that these those "
    "i you he she we they me my your his her our their not no do does did have has had will would can could "
    "should just so if as what when how why who which there here all some more very up out about than then "
    "too also its im dont thats cant it's i'm don't that's".split())
_FOREIGN_WORDS = frozenset(
    # Spanish / Portuguese / Italian / French / German function words that are not English words
    "el los las del que por con para pero muy más como esto esta este sus una uno también porque cuando "
    "está están hay todo todos nada tengo tiene vamos bien jaja "
    "não você mais isso são foi sua seu pelo pela então tem já aqui "
    "il che di non sono della questo anche perché più "
    "les des est une pas qui dans pour sur avec ce sont mais nous vous elle être fait aussi très "
    "der das und ist nicht ein eine mit auf für den von dem ich sie auch sich aber wie wir noch nur "
    "bei oder wenn aus dass mehr kann schon".split())


def _is_non_english(text):
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return False
    # (a) share of letters outside Latin (code point above U+024F = beyond Latin Extended-B)
    non_latin = sum(1 for ch in letters if ord(ch) > 0x24F)
    if non_latin / len(letters) > 0.3:
        return True
    # (b) foreign vs English function words; very short texts are never judged (too little evidence)
    words = [w.lower() for w in _TOKEN.findall(text)]
    if len(words) < 6:
        return False
    foreign = sum(1 for w in words if w in _FOREIGN_WORDS)
    english = sum(1 for w in words if w in _ENGLISH_WORDS)
    return foreign >= 2 and foreign / len(words) >= 0.2 and english / len(words) < 0.15


def classify(text):
    """Return the rejection reason for one cleaned text, or None if it passes."""
    if _BOT.search(text):
        return "bot_or_moderation_text"
    # any alphabet counts as a letter, so Chinese/Russian text is labelled non_english, not too_short
    if sum(1 for ch in text if ch.isalpha()) < 2 or text.strip().lower() in _PLACEHOLDER_TEXT:
        return "too_short"
    if _is_non_english(text):
        return "non_english"
    return None


# --- tables -------------------------------------------------------------------------------------
_FILTER_SCHEMA = """CREATE TABLE text_filter (
    src_rowid INTEGER PRIMARY KEY,          -- same key as processed_text.src_rowid
    reason TEXT NOT NULL)"""
_AUDIT_SCHEMA = """CREATE TABLE data_quality_audit (
    ts_hour INTEGER NOT NULL,               -- created_utc rounded down to the hour (unix seconds)
    subreddit TEXT NOT NULL,
    content_type TEXT NOT NULL,
    remove_reason TEXT NOT NULL,            -- passed / removed / deleted / empty / empty_after_cleaning / <T2 reasons>
    row_count INTEGER NOT NULL,
    PRIMARY KEY (ts_hour, subreddit, content_type, remove_reason))"""
_VIEW = """CREATE VIEW filtered_text AS
    SELECT p.* FROM processed_text p LEFT JOIN text_filter f ON f.src_rowid = p.src_rowid
    WHERE f.src_rowid IS NULL"""


def process(db_path=DEFAULT_DB, window=500_000, limit_rows=None):
    db = connect(db_path)
    try:
        return _process(db, window, limit_rows)
    finally:
        db.close()


def _process(db, window, limit_rows):
    for statement in ("DROP VIEW IF EXISTS filtered_text", "DROP TABLE IF EXISTS text_filter",
                      "DROP TABLE IF EXISTS data_quality_audit", _FILTER_SCHEMA, _AUDIT_SCHEMA):
        db.execute(statement)
    this_run = run_id()
    append_event(db, "quality_filter_start", run_id=this_run, version=FILTER_VERSION)
    last = db.execute("SELECT MAX(src_rowid) FROM processed_text").fetchone()[0] or 0
    if limit_rows:
        last = min(last, limit_rows)

    # Step 1: classify every cleaned text; store only the rejected ones.
    reasons, done, started = Counter(), 0, time.time()
    while done < last:
        upper = min(done + window, last)
        rejected = []
        for rowid, text in db.execute(
                "SELECT src_rowid, own_text FROM processed_text WHERE src_rowid > ? AND src_rowid <= ?",
                (done, upper)).fetchall():
            reason = classify(text)
            if reason:
                rejected.append((rowid, reason))
                reasons[reason] += 1
        db.executemany("INSERT INTO text_filter VALUES (?,?)", rejected)
        db.commit()
        done = upper
        print("rowid %d/%d  rejected so far %d  (%.0f rows/s)"
              % (done, last, sum(reasons.values()), done / max(time.time() - started, 1e-9)), flush=True)
    db.execute(_VIEW)

    # Step 2: audit. Every raw row of the 6 communities lands in exactly one reason.
    names = subreddits()
    marks = ",".join("?" * len(names))
    audit = Counter()
    # 2a) text already gone in the raw data (text_status removed / deleted / empty)
    for hour, sub, ctype, status, n in db.execute(
            "SELECT created_utc/3600*3600, subreddit, content_type, text_status, COUNT(*) FROM reddit_content "
            "WHERE text_status != 'available' AND subreddit IN (%s) GROUP BY 1,2,3,4" % marks, names):
        audit[(hour, sub, ctype, status)] += n
    # 2b) available text: how many survived T1, how many T2 rejected
    #     (empty_after_cleaning = available - processed; passed = processed - rejected)
    available = Counter()
    for hour, sub, ctype, n in db.execute(
            "SELECT created_utc/3600*3600, subreddit, content_type, COUNT(*) FROM reddit_content "
            "WHERE text_status = 'available' AND subreddit IN (%s) GROUP BY 1,2,3" % marks, names):
        available[(hour, sub, ctype)] = n
    processed = Counter()
    for hour, sub, ctype, n in db.execute(
            "SELECT created_utc/3600*3600, subreddit, content_type, COUNT(*) FROM processed_text GROUP BY 1,2,3"):
        processed[(hour, sub, ctype)] = n
    rejected = Counter()
    for hour, sub, ctype, reason, n in db.execute(
            "SELECT p.created_utc/3600*3600, p.subreddit, p.content_type, f.reason, COUNT(*) "
            "FROM text_filter f JOIN processed_text p ON p.src_rowid = f.src_rowid GROUP BY 1,2,3,4"):
        audit[(hour, sub, ctype, reason)] += n
        rejected[(hour, sub, ctype)] += n
    for key, n in available.items():
        if n - processed[key]:
            audit[key + ("empty_after_cleaning",)] += n - processed[key]
    for key, n in processed.items():
        if n - rejected[key]:
            audit[key + ("passed",)] += n - rejected[key]
    db.executemany("INSERT INTO data_quality_audit VALUES (?,?,?,?,?)",
                   [key + (n,) for key, n in audit.items()])
    db.commit()
    totals = dict(reasons)
    totals["audit_rows"] = len(audit)
    append_event(db, "quality_filter_done", run_id=this_run, version=FILTER_VERSION, **totals)
    return totals


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--window", type=int, default=500_000, help="processed_text rowids per batch")
    parser.add_argument("--limit-rows", type=int, help="only classify rowids up to this value (trials)")
    args = parser.parse_args(argv)
    print("done:", process(args.db, args.window, args.limit_rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
