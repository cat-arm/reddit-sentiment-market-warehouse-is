"""Store hourly yfinance bars with bounded retries and an audit trail."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # so `python ingest/<file>.py` finds the ingest package

import argparse
import math
import re
import sqlite3
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf
from ingest.pipeline_logs import append_event

TICKERS = ("AAPL", "AMC", "AMD", "BITO", "BRK-B", "BTC-USD", "CL=F", "COIN",
           "DOGE-USD", "ES=F", "ETH-USD", "GC=F", "GME", "HOOD", "IBIT", "IWM",
           "JNJ", "JPM", "KO", "MARA", "MSFT", "MSTR", "NG=F", "NQ=F", "NVDA",
           "PLTR", "QQQ", "RTY=F", "SHIB-USD", "SOL-USD", "SPY", "TSLA", "XOM",
           "XRP-USD")
UTC = timezone.utc
NY = ZoneInfo("America/New_York")


def utc(dt):
    return dt.astimezone(UTC).isoformat(timespec="seconds")


def date_arg(value):
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)


def month_arg(value):
    """Parse nov24/nov2024 as the first day of the month (UTC)."""
    match = re.fullmatch(r"([a-zA-Z]{3})(\d{2}|\d{4})", value)
    if match is None:
        raise argparse.ArgumentTypeError("expected month such as nov24 or jan2025")
    try:
        month = datetime.strptime(match.group(1).title(), "%b").month
    except ValueError as exc:
        raise argparse.ArgumentTypeError("invalid month: {}".format(value)) from exc
    year = int(match.group(2))
    return datetime(year + (2000 if year < 100 else 0), month, 1, tzinfo=UTC)


def next_month(value):
    return value.replace(year=value.year + (value.month == 12),
                         month=value.month % 12 + 1)


def database(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path))
    db.execute("""CREATE TABLE IF NOT EXISTS market_bars (
        ticker TEXT NOT NULL, timestamp_utc TEXT NOT NULL,
        open REAL, high REAL, low REAL, close REAL, volume REAL,
        fetched_at_utc TEXT NOT NULL,
        PRIMARY KEY (ticker, timestamp_utc))""")
    db.execute("""CREATE TABLE IF NOT EXISTS market_windows (
        ticker TEXT NOT NULL, start_utc TEXT NOT NULL, end_utc TEXT NOT NULL,
        status TEXT NOT NULL, rows INTEGER NOT NULL, missing INTEGER NOT NULL,
        attempts INTEGER NOT NULL, error TEXT, checked_at_utc TEXT NOT NULL,
        PRIMARY KEY (ticker, start_utc, end_utc))""")
    db.execute("""CREATE TABLE IF NOT EXISTS market_gaps (
        ticker TEXT NOT NULL, timestamp_utc TEXT NOT NULL, reason TEXT NOT NULL,
        PRIMARY KEY (ticker, timestamp_utc))""")
    db.execute("""UPDATE market_windows SET status='unavailable'
        WHERE status='needs_review' AND rows=0 AND error LIKE '%last 730 days%'""")
    old = db.execute("""SELECT ticker, start_utc, end_utc FROM market_windows
        WHERE status='needs_review' AND rows>0""").fetchall()
    for ticker, start, end in old:
        remaining = find_gaps(stored_bars(db, ticker,
                                          datetime.fromisoformat(start),
                                          datetime.fromisoformat(end)), ticker)
        db.execute("DELETE FROM market_gaps WHERE ticker=? AND timestamp_utc>=? AND timestamp_utc<?",
                   (ticker, start, end))
        db.executemany("INSERT OR REPLACE INTO market_gaps VALUES (?,?,?)",
                       [(ticker, utc(dt), "suspected_missing_or_null") for dt in remaining])
        if not remaining:
            db.execute("""UPDATE market_windows SET status='complete', missing=0, error=NULL
                WHERE ticker=? AND start_utc=? AND end_utc=?""", (ticker, start, end))
        else:
            db.execute("""UPDATE market_windows SET missing=?
                WHERE ticker=? AND start_utc=? AND end_utc=?""",
                (len(remaining), ticker, start, end))
    db.commit()
    return db


def fetch(ticker, start, end):
    frame = yf.Ticker(ticker).history(
        start=start, end=end, interval="60m", actions=False,
        auto_adjust=False, keepna=True, raise_errors=True, timeout=30)
    if frame.empty:
        return []
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is None:
        raise ValueError("Yahoo returned timestamps without a timezone")
    fields = ("Open", "High", "Low", "Close", "Volume")
    if any(field not in frame.columns for field in fields):
        raise ValueError("Yahoo returned incomplete OHLCV columns")
    result = []
    for index, row in frame.iterrows():
        values = []
        for field in fields:
            value = row[field]
            values.append(None if pd.isna(value) or not math.isfinite(float(value))
                          else float(value))
        result.append((ticker, utc(index.to_pydatetime()), *values, utc(datetime.now(UTC))))
    return result


def save(db, bars):
    with db:
        db.executemany("""INSERT INTO market_bars VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(ticker, timestamp_utc) DO UPDATE SET
            open=COALESCE(excluded.open,market_bars.open),
            high=COALESCE(excluded.high,market_bars.high),
            low=COALESCE(excluded.low,market_bars.low),
            close=COALESCE(excluded.close,market_bars.close),
            volume=COALESCE(excluded.volume,market_bars.volume),
            fetched_at_utc=excluded.fetched_at_utc""", bars)


def futures_open(dt):
    """Typical Sunday evening–Friday afternoon session in New York time."""
    local = dt.astimezone(NY)
    weekday, hour = local.weekday(), local.hour
    return ((weekday == 6 and hour >= 18) or
            (weekday in (0, 1, 2, 3) and hour != 17) or
            (weekday == 4 and hour < 17))


def expected_hours(ticker, day):
    """Typical hourly bars; holidays and instrument-specific hours need review."""
    hours = []
    for offset in range(24):
        hour = day + timedelta(hours=offset)
        local = hour.astimezone(NY)
        if ticker.endswith("-USD") or (ticker.endswith("=F") and futures_open(hour)):
            hours.append(hour)
        elif not ticker.endswith(("-USD", "=F")) and local.weekday() < 5 and 9 <= local.hour < 16:
            hours.append(hour.replace(minute=30))
    return hours


def audit(db, ticker, day):
    """Check all expected trading slots, not only total returned row counts."""
    end = day + timedelta(days=1)
    rows = db.execute("""SELECT timestamp_utc, open, high, low, close, volume
        FROM market_bars WHERE ticker=? AND timestamp_utc>=? AND timestamp_utc<?""",
        (ticker, utc(day), utc(end))).fetchall()
    by_time = {datetime.fromisoformat(row[0]): row[1:] for row in rows}
    expected = expected_hours(ticker, day)
    missing = [dt for dt in expected if dt not in by_time or
               any(value is None for value in by_time[dt])]
    window = db.execute("""SELECT status FROM market_windows
        WHERE ticker=? AND start_utc<=? AND end_utc>=?
        ORDER BY (start_utc=? AND end_utc=?) DESC, checked_at_utc DESC LIMIT 1""",
        (ticker, utc(day), utc(end), utc(day), utc(end))).fetchone()
    if window is None:
        status = "NOT_CHECKED"
    elif missing:
        status = "UNAVAILABLE" if window[0] == "unavailable" else "MISSING"
    elif window[0] == "closed" or (not expected and not rows):
        status = "CLOSED"
    else:
        status = "OK" if window[0] in ("complete", "needs_review") else "REVIEW"
    return status, len(expected), len(rows), missing


def audit_range(db, start, end, tickers=TICKERS):
    """Report exceptional ticker-days and summarize normal ones."""
    totals = Counter()
    day = start
    while day < end:
        for ticker in tickers:
            status, expected, stored, missing = audit(db, ticker, day)
            totals[status] += 1
            if status not in ("OK", "CLOSED"):
                append_event(db, "market_audit_exception", ticker=ticker,
                             date_utc=day.date().isoformat(), status=status,
                             stored_rows=stored, expected_slots_estimate=expected,
                             suspected_missing_utc=[utc(dt) for dt in missing],
                             calendar_verified=False)
            if status not in ("OK", "CLOSED"):
                print("AUDIT {} {} {} stored={} expected={} missing_utc={}".format(
                    day.date(), ticker, status, stored, expected,
                    ",".join(dt.strftime("%H:%M") for dt in missing) or "-"))
        day += timedelta(days=1)
    print("AUDIT SUMMARY: {}".format(dict(totals)))
    print("Schedules are estimates; verify exchange holidays and futures rolls.")
    return totals


def find_gaps(bars, ticker, start=None, end=None):
    """Find null OHLCV bars and hourly holes; do not infer futures sessions."""
    if not bars:
        return []
    ordered = sorted((datetime.fromisoformat(row[1]), row[2:7]) for row in bars)
    missing = {dt for dt, prices in ordered if any(value is None for value in prices)
               and not (ticker.endswith("=F") and not futures_open(dt))}
    if ticker.endswith("-USD") and start is not None and end is not None:
        observed = {dt for dt, _ in ordered}
        point = start
        while point < end:
            if point not in observed:
                missing.add(point)
            point += timedelta(hours=1)
        return sorted(missing)
    if ticker.endswith("=F"):
        return sorted(missing)
    for (left, _), (right, _) in zip(ordered, ordered[1:]):
        point = left + timedelta(hours=1)
        while point < right:
            if ticker.endswith("-USD") or left.astimezone(NY).date() == right.astimezone(NY).date():
                missing.add(point)
            point += timedelta(hours=1)
    return sorted(missing)


def stored_bars(db, ticker, start, end):
    return [(ticker, ts, op, high, low, close, volume)
            for ts, op, high, low, close, volume in db.execute(
        "SELECT timestamp_utc, open, high, low, close, volume FROM market_bars WHERE ticker=? AND timestamp_utc>=? "
        "AND timestamp_utc<? ORDER BY timestamp_utc", (ticker, utc(start), utc(end)))]


def expected_closed(ticker, start, end):
    """Entire UTC day with no expected trades (Sunday futures may reopen)."""
    if end - start != timedelta(days=1) or start.hour != 0 or ticker.endswith("-USD"):
        return False
    return start.weekday() == 5 if ticker.endswith("=F") else start.weekday() >= 5


def run_window(db, ticker, start, end, retries=3, pause=2, provider=fetch):
    last_error = None
    attempts = 0
    succeeded = False
    for attempt in range(1, retries + 1):
        attempts = attempt
        try:
            rows = provider(ticker, start, end)
            if rows:
                save(db, rows)
            gaps = find_gaps(stored_bars(db, ticker, start, end), ticker, start, end)
            if rows and not gaps:
                last_error = None
                succeeded = True
                break
            if gaps and len(gaps) <= 24 and attempt < retries:
                for gap in gaps:
                    try:
                        save(db, provider(ticker, gap, min(gap + timedelta(hours=2), end)))
                    except Exception as exc:
                        last_error = str(exc)
                if not find_gaps(stored_bars(db, ticker, start, end), ticker, start, end):
                    last_error = None
                    succeeded = True
                    break
            last_error = "empty response" if not rows else "suspected missing/null bars"
        except Exception as exc:
            last_error = "{}: {}".format(type(exc).__name__, exc)
        if attempt < retries:
            time.sleep(pause * 2 ** (attempt - 1))
    saved = stored_bars(db, ticker, start, end)
    gaps = find_gaps(saved, ticker, start, end)
    if succeeded and saved and not gaps:
        status = "complete"
    elif last_error and "last 730 days" in last_error:
        status = "unavailable"
    else:
        status = "needs_review"
    with db:
        db.execute("DELETE FROM market_gaps WHERE ticker=? AND timestamp_utc>=? AND timestamp_utc<?",
                   (ticker, utc(start), utc(end)))
        db.executemany("INSERT OR REPLACE INTO market_gaps VALUES (?,?,?)",
                       [(ticker, utc(gap), "suspected_missing_or_null") for gap in gaps])
        db.execute("""INSERT INTO market_windows VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(ticker, start_utc, end_utc) DO UPDATE SET
            status=excluded.status, rows=excluded.rows, missing=excluded.missing,
            attempts=excluded.attempts, error=excluded.error,
            checked_at_utc=excluded.checked_at_utc""",
                   (ticker, utc(start), utc(end), status, len(saved), len(gaps),
                    attempts, last_error, utc(datetime.now(UTC))))
    append_event(db, "market_window_completed", ticker=ticker,
                 start_utc=utc(start), end_utc=utc(end), status=status,
                 stored_rows=len(saved), suspected_gaps=len(gaps), attempts=attempts,
                 error=last_error)
    return status, len(saved), len(gaps), last_error


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("months", nargs="*", type=month_arg,
                        help="nov24 for one month, nov24 jan25 for an inclusive range")
    parser.add_argument("--db", type=Path, default=Path("output/reddit.sqlite3"))
    parser.add_argument("--start", type=date_arg, help="UTC YYYY-MM-DD (advanced)")
    parser.add_argument("--end", type=date_arg, help="exclusive end date in UTC")
    parser.add_argument("--ticker", action="append", choices=TICKERS)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--pause", type=float, default=2)
    parser.add_argument("--audit-only", action="store_true", help="check saved prices without downloading")
    args = parser.parse_args(argv)
    if len(args.months) > 2 or (args.months and (args.start or args.end)):
        parser.error("use one/two months OR --start/--end, not both")
    start = args.months[0] if args.months else args.start or date_arg("2024-10-01")
    end = (next_month(args.months[-1]) if args.months else
           args.end or datetime.now(UTC).replace(minute=0, second=0, microsecond=0))
    if start >= end or args.days < 1 or not 1 <= args.retries <= 10 or args.pause < 0:
        parser.error("require start < end, days > 0, retries 1..10, pause >= 0")
    failed = 0
    with database(args.db) as db:
        if args.audit_only:
            audit_range(db, start, end, args.ticker or TICKERS)
            return 0
        for ticker in args.ticker or TICKERS:
            point = start
            while point < end:
                stop = min(point + timedelta(days=args.days), end)
                existing = db.execute("SELECT status FROM market_windows WHERE ticker=? "
                                      "AND start_utc=? AND end_utc=?",
                                      (ticker, utc(point), utc(stop))).fetchone()
                if existing and existing[0] in ("complete", "closed", "unavailable"):
                    point = stop
                    continue
                if expected_closed(ticker, point, stop):
                    with db:
                        db.execute("""INSERT INTO market_windows VALUES (?,?,?,?,?,?,?,?,?)
                            ON CONFLICT(ticker, start_utc, end_utc) DO UPDATE SET
                            status=excluded.status, rows=0, missing=0, attempts=0,
                            error=NULL, checked_at_utc=excluded.checked_at_utc""",
                            (ticker, utc(point), utc(stop), "closed", 0, 0, 0, None,
                             utc(datetime.now(UTC))))
                    print("{} {}: expected closure".format(ticker, point.date()))
                else:
                    print("{} {} → {}".format(ticker, utc(point), utc(stop)), flush=True)
                    status, rows, gaps, error = run_window(
                        db, ticker, point, stop, args.retries, args.pause)
                    print("  {} rows={} suspected_gaps={} {}".format(
                        status, rows, gaps, error or ""), flush=True)
                    failed += status != "complete"
                    time.sleep(args.pause)
                point = stop
        totals = audit_range(db, start, end, args.ticker or TICKERS)
    if failed:
        print("{} windows need review; rerun to retry them".format(failed), file=sys.stderr)
    return 1 if failed or totals["MISSING"] or totals["UNAVAILABLE"] else 0


if __name__ == "__main__":
    sys.exit(main())