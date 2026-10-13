# Reddit Pushshift research extractor

Extract submissions and comments from monthly Pushshift `.zst` dumps for exactly
these nine subreddits (matching case-insensitively): `wallstreetbets`, `stocks`,
`investing`, `StockMarket`, `CryptoCurrency`, `Bitcoin`, `dogecoin`, `Daytrading`,
and `options`.

**Research inputs are private/local:** The `data/` directory (including the
proposal PDF and `.torrent` files), downloaded archives, SQLite databases, and
exports are ignored by Git. Review `git status` before pushing. This project
does not download torrents and does not redistribute Reddit content.

## Setup

Python 3.9+ is required. On Windows, replace `python3` with `py -3` and use
`.venv\Scripts\activate` rather than `source .venv/bin/activate`.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

First download the monthly archives separately using a method permitted on
your network. Do **not** decompress the `.zst` files. For a one-month pilot,
obtain `RS_2024-10.zst` (submissions) and `RC_2024-10.zst` (comments); the
October torrent contains both files. Use their actual local paths below. Or,
if the matching `.torrent` is already under `data/` and `aria2c` is installed,
`python reddit_extract.py fetch 2024-10 --db output/reddit.sqlite3` downloads,
imports, and deletes the archive in one step (see "Pipeline commands" below).

```sh
python reddit_extract.py import --db output/reddit.sqlite3 \
  --submissions data/reddit-2024-10/reddit/submissions/RS_2024-10.zst \
  --comments data/reddit-2024-10/reddit/comments/RC_2024-10.zst
python reddit_extract.py export --db output/reddit.sqlite3 \
  --output output/reddit_2024-10.json
```

In PowerShell, run each command on a single line rather than using `\` to
continue a line. Paths with spaces must be quoted.

Each output item is a submission with `id`, `subreddit`, `title`, `selftext`,
`created_utc`, and a nested `comments` array. Each comment has `id`,
`parent_id`, `link_id`, `body`, and `created_utc`. `created_utc` is a Unix
timestamp in seconds. The output is a single JSON array and may itself become
very large; it is written incrementally.

The SQLite database stores **both posts and comments in one `reddit_content`
table**; `content_type` is `submission` or `comment`, and unused fields for a
given type are NULL. Research fields include the source text, subreddit, UTC
time, parent/post IDs, source archive, and `text_status` (`available`, `empty`,
`missing`, `removed`, `deleted`). A link post with an empty `selftext` but a
title is `available`. Additional source metadata kept for future analysis
includes `score`, post `upvote_ratio` and `num_comments`, `author`, `retrieved_on`,
`permalink`, and a few post/comment status flags. Missing source fields remain
NULL rather than being converted to zero. No full Reddit JSON or voter
identities are stored; `ups` and `downs` are deliberately excluded. These
engagement values are archive snapshots, **not** observations known at the
post's publication time; do not use them as contemporaneous predictive
features without addressing look-ahead bias. Keep author names private.
The JSON export remains the compact post-with-comments view described above;
it does not export all optional SQLite fields.

## Hourly market data (yfinance)

Market prices can be collected without waiting for Reddit downloads. The
research universe is the 34 tickers from the proposal. The single market
script downloads and audits the requested month(s). The second month is
**inclusive** (November, December, and January in the second example):

```sh
python3 market_fetch.py nov24
python3 market_fetch.py nov24 jan25
```

To check prices already in the database without requesting Yahoo again:

```sh
python3 market_fetch.py oct24 --audit-only
```

Python requires a script name after `python3`; `python3 nov24` by itself
cannot call the downloader. You can still use `--ticker AAPL` for a pilot,
or `--start 2024-10-01 --end 2024-11-01` (exclusive end) for exact dates.
Without month/date arguments, fetching begins October 1, 2024 and ends at
the beginning of the current UTC hour. Each ticker is requested in 14-day
windows and stored in the same SQLite database as the Reddit data.

The command retries empty responses, errors, null closing prices, and suspected
missing hours (including a focused fetch around each suspected gap). It records
every Yahoo-returned bar, including rows with missing fields, rather than
silently dropping them. Successful windows are skipped when you rerun the same
command; failed/incomplete windows are retried. Requests are sequential with a
pause to limit load. Check `market_windows` for `needs_review` and `market_gaps`
for suspected missing hours. **A successful response is not proof Yahoo has
every historical bar.** Markets close on weekends/holidays; futures have
instrument-specific sessions. The gap heuristic flags within-day stock gaps
and 24/7 crypto gaps, but cannot certify futures or boundary hours. Review the
asset's trading calendar before treating a gap as missing data. Yahoo's
futures data can include an all-null price placeholder during the 17:00 New
York daily maintenance hour; it is retained but not treated as a missing trade.
Other futures gaps still require calendar review. Intraday Yahoo history
has a rolling limit (approximately 730 days), so older intervals may
be irrecoverable from yfinance; no number of retries can restore unavailable
history. Such explicitly rejected windows are marked `unavailable` after the
configured retries, rather than repeatedly requesting them on future runs.
Save and back up the database promptly.

The automatic audit prints only exceptional ticker-days with missing UTC times
and summarizes normal/closed days; `--audit-only` runs it again without fetching.
It uses regular US equity hours, a typical US futures schedule, and
24/7 crypto hours. Exchange holidays and instrument-specific hours still need
independent verification. `Stored` includes null-price closed-session placeholders.
Daily rows are **not** expected to match across weekends, and equal row counts
do not prove that OHLCV values are present. Check `needs_review` windows and
the listed missing timestamps; Yahoo can return null prices during otherwise
open futures hours even after repeated requests.

The old Colab notebook under `old_code/` is an experiment, not the archive
pipeline; its tickers and scope may differ from the 34 in the proposal.

## Pipeline commands

One command per month handles the whole Reddit side — download the matching
`.torrent` with `aria2c` (skipped if already downloaded), import both archives
into SQLite, then delete the `.zst` files to free disk space (a month's pair
is ~45-50GB; keep more than a couple around and you will run out of space):

```sh
python reddit_extract.py fetch 2024-11 --db output/reddit.sqlite3
```

Requires the `aria2c` binary (`brew install aria2` on macOS) and the matching
`.torrent` file already present under `data/` (the proposal's torrents are
tracked there; see "Research inputs are private/local" above — this project
still does not fetch or create `.torrent` files itself, only downloads the
content of one you already have). Add `--keep-archive` to skip the delete
step, or `--data <dir>` if archives/torrents live somewhere other than `data/`.
Re-running the same month is safe: an already-downloaded, already-imported
month is detected and skipped/short-circuited rather than redone.

Finance data is a separate command, independent of the Reddit downloads:

```sh
python3 market_fetch.py nov24
```

And a status command reports progress across both, for every month:

```sh
python3 pipeline_status.py
```

It groups months by year and prints, per month: whether the archive is
downloaded (`missing`/`partial`/`downloaded`, matched against
`RS_YYYY-MM.zst`/`RC_YYYY-MM.zst` under `--data`, default `data/`), whether it
is imported into SQLite (post/comment row counts, matched by `source_archive`),
and whether market data is fetched (`not fetched`/`partial`/`fetched`, ticker
coverage, suspected gaps, and windows still `needs_review`/`unavailable`). It
reads `--db` (default `output/reddit.sqlite3`) without modifying it, so it is
safe to run anytime, including before either database table exists. The month
list comes from local `.torrent` file comments, files already on disk, and
whatever months are already present in the database, so a month only shows up
once something references it.

## Additional months

Run `import` again with other monthly file paths, reusing the same database.
Post IDs and comment IDs are unique SQLite keys: importing a file twice will
not duplicate records. A comment from a later month is linked to an older post
by `link_id` during export, even when the post and comment were imported on
different days. Orphan comments remain in SQLite until their posts are imported;
they are not exported alone. For the most complete result, import all desired
months before exporting. Re-export after importing a new month to include its
comments. Earlier exports are snapshots and do not update automatically.

The importer streams decompressed lines and commits in batches, but **disk**
space is still needed for the compressed archives, SQLite database (including
indexes), and output. Monitor free space before and during large imports. A
damaged/truncated archive may leave previously committed batches in SQLite;
after repairing the archive, rerun the import (IDs prevent duplication).

## Tests

## Persistent logs and all-month reports

Reddit imports now append start/completion/failure events with `read`, `invalid`,
`selected`, `inserted`, and skipped-existing counts to `output/logs/pipeline_events.jsonl`.
Market fetches log window results and audit exceptions in the same file. Existing
running processes must be restarted on their next run to pick up this logging.
These structured logs do not capture the full aria2 console transcript.

Run `python pipeline_logs.py` to refresh `output/logs/monthly_pipeline_report.json`
and `output/logs/monthly_pipeline_summary.csv` from a read-only SQLite snapshot.
The JSON has every archived Reddit month broken down by nine subreddits and text
status, market bars by ticker/month, overlapping fetch-window status/error details,
and suspected gap timestamps. Historical source totals cannot be reconstructed
from retained DB rows alone; unknown totals stay unknown. Supplied terminal
evidence is preserved separately in `historical_events.jsonl`. Row presence alone
is not proof of a completed import. Market gaps are estimates; the current audit
does not fully model exchange holidays/early closes or product-specific futures
calendars. Logs/reports stay under the Git-ignored output directory.

```sh
python -m unittest discover -s tests -v
```

## Publishing

The project can be committed locally and then pushed to a GitHub repository
you create. Do not add `data/` or `output/` to the repository. Before the first
push, verify `git status` and `git ls-files` do not include research material.
