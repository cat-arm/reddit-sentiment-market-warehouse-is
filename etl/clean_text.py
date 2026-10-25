"""T1: clean Reddit text into `final_text` and fill the `processed_text` table.

Ported from cell 5 of the old MVP notebook (old_code/reddit_6.ipynb) with deliberate changes,
because the new text feeds VADER and FinBERT:
  * case is preserved      (VADER boosts ALL-CAPS words; the MVP lower-cased everything)
  * apostrophes are kept   ("don't" must stay a negation; the MVP turned it into "dont")
  * emoji become plain words separated by spaces ("loudly crying face"); NLTK's VADER does not
    understand unicode emoji, and the MVP's ":rocket:" form is unreadable to it as well
  * finance symbols are kept: $CASHTAGS, %, !, ?, +, -, ., prices
No language filtering and no bot/quality filtering happen here (that is T2).

Context for comments (cleaner_version 2.0, decided with the user 2026-10-24): the old MVP notebook built
final_text = title + text for every row, and its comments carried the TITLE OF THE POST THEY ANSWER, so a bare
"hold" under "this stock is amazing" was read as positive.  The torrent dump has no title on comments, but every
comment has link_id = id of its post, so:
    submission  final_text = title + selftext
    comment     final_text = title of the post it answers + body of the comment   (body only if the post is unknown)
`own_text` keeps what the author of the row wrote (comment body / submission title+selftext).  T2 (bot, too short,
language) and the keyword rule of S3 judge `own_text`, so a title can neither hide a bot reply nor make a
one-word comment pass; VADER, FinBERT and ticker extraction read `final_text` (the context the models are given).
A comment whose own body is empty after cleaning is not written, whatever its post title says.

How to check this step later (thesis audit trail):
  * every rule is one named regex below, applied in the order listed in clean_text()
  * raw text is never modified: results go to the NEW table processed_text, reddit_content is only read
  * each output row records cleaner_version, so a rule change = bump CLEANER_VERSION + rerun with --rebuild
  * rows whose cleaned text is empty (deleted posts, image-only posts, pure links) are NOT written;
    the "empty" count printed at the end says how many

Usage:
    python -m etl.clean_text [--db output/reddit.sqlite3] [--limit-rows N] [--rebuild]
"""

import argparse
import html
import re
import sys
import time
from datetime import datetime, timezone

import emoji

from etl.common import DEFAULT_DB, connect, subreddits
from pipeline_logs import append_event, run_id

# Bump this whenever ANY rule below changes; process() refuses to mix versions in one table.
CLEANER_VERSION = "2.0"

# --- cleaning rules (each one is explained so the thesis can cite it) ---

# 1) Reddit escapes markdown characters with a backslash; remove the backslash only
_ESCAPED = re.compile(r"\\([\\`*_{}\[\]()#+\-.!$~>|])")             # Reddit markdown escapes: \$TSLA, \*
# 2) embedded images / emotes / gifs carry no sentiment text -> drop the whole thing
_MEDIA = re.compile(r"!\[[^\]]*\]\([^)]*\)")                         # ![img](emote|t5_2th52|4258), ![gif](giphy|..)
# 3) keep the visible link text, drop the hidden address
_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")                      # [text](url) -> text
# 4) bare links
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
# 5) u/name and r/sub are removed (this also keeps usernames out of the analysis, see CLAUDE.md privacy rule)
_MENTION = re.compile(r"(?<![\w/])/?[ur]/[\w-]+", re.IGNORECASE)     # u/name, r/sub: drops usernames too
# 6-8) markdown layout at the start of a line: "# title", "> quote", "-----" rules
_HEADING = re.compile(r"(?m)^[ \t]{0,3}#{1,6}[ \t]*")
_QUOTE = re.compile(r"(?m)^[ \t]*>+[ \t]?")
_RULE = re.compile(r"(?m)^[ \t]*(?:[-_*][ \t]*){3,}$")
# 9) inline markers **bold** *italic* ~~strike~~ `code` (the words inside are kept)
_MARKUP = re.compile(r"[*`~]+")                                      # bold/italic/strike/code markers
# 10) zero-width characters removed; curly quotes/nbsp -> plain ASCII (keeps "don't" a normal negation)
_INVISIBLE = re.compile("[​‌‍⁠﻿]")
# emoji skin-tone modifiers turn into words after demojize; they only add noise, so remove them
_SKIN_TONE = re.compile(r"\b(?:light|medium[- ]light|medium[- ]dark|medium|dark) skin tone\b")
_SPACES = re.compile(r"\s+")
_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "\xa0": " "})
# Reddit puts these strings in selftext when a post was removed; treat as empty, not as text
_PLACEHOLDERS = {"[removed]", "[deleted]", "[removed by reddit]", "[deleted by user]"}


def emoji_to_words(text):
    """Replace each emoji by its plain-English name: '😭' -> ' loudly crying face '."""
    text = emoji.demojize(text, delimiters=(" ", " ")).replace("_", " ")
    return _SKIN_TONE.sub(" ", text)


def clean_text(text):
    """Return the cleaned, single-line text (may be empty)."""
    if not isinstance(text, str) or not text:
        return ""
    # Order matters: unescape HTML first (&amp; -> &), strip links/media BEFORE markup markers,
    # and convert emoji LAST so the emoji words are not touched by the markup rules.
    text = html.unescape(text)
    text = _ESCAPED.sub(r"\1", text)
    text = _MEDIA.sub(" ", text)
    text = _MD_LINK.sub(r"\1", text)
    text = _URL.sub(" ", text)
    text = _MENTION.sub(" ", text)
    text = _HEADING.sub("", text)
    text = _QUOTE.sub("", text)
    text = _RULE.sub(" ", text)
    text = _MARKUP.sub("", text)
    text = _INVISIBLE.sub("", text).translate(_QUOTES)
    text = emoji_to_words(text)
    # collapse newlines/tabs/repeated spaces into one space: one line per item (VADER/FinBERT input)
    return _SPACES.sub(" ", text).strip()


def build_texts(content_type, title, selftext, body, parent_title=""):
    """(final_text, own_text) for one raw row; `parent_title` is the already-cleaned title of the post a comment
    answers.  Submissions: title + selftext (a link post has the title only).  Comments: own = body,
    final = parent title + body, and nothing at all when the body itself is empty."""
    if content_type == "comment":
        own = clean_text(body)
        return (" ".join(part for part in (parent_title, own) if part) if own else ""), own
    selftext = "" if (selftext or "").strip().lower() in _PLACEHOLDERS else selftext
    own = clean_text(" ".join(part for part in (title, selftext) if part))
    return own, own


def build_final_text(content_type, title, selftext, body, parent_title=""):
    return build_texts(content_type, title, selftext, body, parent_title)[0]


SCHEMA = """CREATE TABLE IF NOT EXISTS processed_text (
    src_rowid INTEGER PRIMARY KEY,          -- rowid of the row in reddit_content (used to resume)
    content_id TEXT NOT NULL,
    content_type TEXT NOT NULL,
    subreddit TEXT NOT NULL,
    created_utc INTEGER,
    final_text TEXT NOT NULL,               -- what VADER / FinBERT read (comments: post title + comment body)
    own_text TEXT NOT NULL,                 -- what the author of this row wrote (T2 and the S3 keywords use it)
    char_len INTEGER NOT NULL,
    token_len INTEGER NOT NULL,             -- whitespace-separated words, not model tokens
    cleaned_at TEXT NOT NULL,
    cleaner_version TEXT NOT NULL)"""


def post_titles(db, names):
    """{post id (as in comments' link_id): cleaned title} for the in-scope submissions."""
    marks = ",".join("?" * len(names))
    return {post_id: clean_text(title) for post_id, title in db.execute(
        "SELECT id, title FROM reddit_content WHERE content_type = 'submission' AND title IS NOT NULL "
        "AND subreddit IN (%s)" % marks, names)}


def process(db_path=DEFAULT_DB, window=100_000, limit_rows=None, rebuild=False):
    """Clean every in-scope, available text and append it to processed_text (resumable).

    Scope = the 6 communities in configs/subreddits.yaml AND text_status = 'available'
    (the other 3 communities stay in reddit_content but are filtered here, never deleted).
    """
    db = connect(db_path)
    try:
        return _process(db, window, limit_rows, rebuild)
    finally:
        db.close()


def _process(db, window, limit_rows, rebuild):
    names = subreddits()                      # the 6 communities, from config (not hard-coded)
    if rebuild:                               # the table layout changed in 2.0, so drop it instead of emptying it
        db.execute("DROP VIEW IF EXISTS filtered_text")
        db.execute("DROP TABLE IF EXISTS processed_text")
    db.execute(SCHEMA)
    # Safety: never mix rows made by different cleaner versions in the same table.
    other = db.execute("SELECT DISTINCT cleaner_version FROM processed_text WHERE cleaner_version != ?",
                       (CLEANER_VERSION,)).fetchall()
    if other:
        raise SystemExit("processed_text holds cleaner_version %s; rerun with --rebuild to redo it with %s"
                         % ([row[0] for row in other], CLEANER_VERSION))
    db.commit()

    # Resume point: highest source rowid already cleaned. Stop and re-run = continue from there.
    done = db.execute("SELECT COALESCE(MAX(src_rowid), 0) FROM processed_text").fetchone()[0]
    last = db.execute("SELECT MAX(rowid) FROM reddit_content").fetchone()[0] or 0
    if limit_rows:
        last = min(last, done + limit_rows)
    marks = ",".join("?" * len(names))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    this_run = run_id()
    append_event(db, "clean_text_start", run_id=this_run, version=CLEANER_VERSION, resume_from=done, last_rowid=last)
    totals = {"read": 0, "written": 0, "empty": 0, "comments_with_post_title": 0}
    titles = post_titles(db, names)           # post id -> cleaned title, for the comments' context
    started = time.time()
    # Work in windows of rowids (not OFFSET paging) so each batch is a fast index range read.
    while done < last:
        upper = min(done + window, last)
        rows = db.execute(
            "SELECT rowid, id, content_type, subreddit, created_utc, title, selftext, body, link_id FROM reddit_content "
            "WHERE rowid > ? AND rowid <= ? AND text_status = 'available' AND subreddit IN (%s)" % marks,
            (done, upper) + names).fetchall()
        out = []
        for rowid, content_id, ctype, sub, created, title, selftext, body, link_id in rows:
            parent = titles.get(link_id, "") if ctype == "comment" else ""
            text, own = build_texts(ctype, title, selftext, body, parent)
            if text:                           # skip rows that end up empty after cleaning
                totals["comments_with_post_title"] += bool(parent)
                out.append((rowid, content_id, ctype, sub, created, text, own, len(text), len(text.split()),
                            now, CLEANER_VERSION))
        # INSERT OR IGNORE: if a crash left a half-written batch, re-running it cannot create duplicates.
        db.executemany("INSERT OR IGNORE INTO processed_text VALUES (?,?,?,?,?,?,?,?,?,?,?)", out)
        db.commit()
        done = upper
        totals["read"] += len(rows)
        totals["written"] += len(out)
        totals["empty"] += len(rows) - len(out)
        speed = totals["read"] / max(time.time() - started, 1e-9)
        print("rowid %d/%d  read %d  written %d  empty %d  (%.0f rows/s)"
              % (done, last, totals["read"], totals["written"], totals["empty"], speed), flush=True)
    # Index built once at the end (faster than keeping it during the bulk insert); T2/T4 join on content_id.
    db.execute("CREATE INDEX IF NOT EXISTS processed_text_by_content ON processed_text(content_id)")
    db.commit()
    append_event(db, "clean_text_done", run_id=this_run, version=CLEANER_VERSION, **totals)
    return totals


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--window", type=int, default=100_000, help="reddit_content rowids per batch")
    parser.add_argument("--limit-rows", type=int, help="stop after scanning this many rowids (for trials)")
    parser.add_argument("--rebuild", action="store_true", help="empty processed_text and start over")
    args = parser.parse_args(argv)
    totals = process(args.db, args.window, args.limit_rows, args.rebuild)
    print("done:", totals)
    return 0


if __name__ == "__main__":
    sys.exit(main())
