"""M1: price features per bar -> table `market_hourly_features` and `FactMarketPrice` (proposal figure 3).

Input is `market_bars` (hourly bars from yfinance). Rules, all from the proposal unless marked EXTENSION:

  * Rows with close IS NULL are placeholders for closed-market hours (19,177 rows), not prices: dropped first.
  * A bar's timestamp is the START of the bar (stocks xx:30, crypto/futures xx:00). hour_bucket = timestamp
    rounded down to the full hour, so a stock bar 13:30 belongs to hour 13:00. Reddit is aggregated in the same
    [H:00, H+1:00) hours, so both sides join on hour_bucket. close_t is the price at the END of the bar.
  * future_return_nh = (close_{t+n} - close_t) / close_t * 100   (percent). close_{t+n} must be the bar
    that starts exactly n hours after bar t; if that bar does not exist (weekend, holiday, overnight,
    missing data) the value is NULL. NULL therefore means "not valid", which is the proposal's
    "use only periods with enough data". Stocks trade ~7 bars/day, so 6h/12h are mostly NULL for them.
  * log_return = ln(close_t / close_{t-1}) * 100, only when bar t-1 starts exactly 1 hour earlier.
    NOTE: log_return = current_return (the proposal's "Current Return (%)", table 8). Only the name changed;
    the column keeps the name log_return so no migration is needed.
  * volume_zscore_24 = (volume_t - mean) / std of the PRIOR 24 clock hours, current hour excluded
    (needs >= MIN_WINDOW bars, std > 0, else NULL).
  * ATR = mean true range over the last 24 clock hours including this bar (needs >= MIN_WINDOW bars);
    normalized_atr = ATR / close * 100.   True range = max(high-low, |high-prev_close|, |low-prev_close|),
    prev_close only if the previous bar starts exactly 1h earlier, otherwise high-low.
  * RSI = Wilder RSI with period 14 (open question O6) on the sequence of valid bars of the ticker
    (EXTENSION: bars across a closed market are treated as consecutive); NULL for the first 14 bars.
future_return_* are TARGETS only. Never use them as model input (leakage).

Usage:
    python -m etl.market_features [--db output/reddit.sqlite3]
Always rebuilds both tables (about a minute).
"""

import argparse
import bisect
import math
import statistics
import sys
from datetime import datetime, timezone

from etl.common import DEFAULT_DB, connect
from etl.seed_dims import seed

HOUR = 3600
HORIZONS = (1, 2, 3, 6, 12)
RSI_PERIOD = 14
WINDOW_HOURS = 24
MIN_WINDOW = 5            # fewer bars than this in a 24 h window -> z-score / ATR are NULL

FEATURE_COLUMNS = ("ticker", "bar_ts", "hour_bucket", "close", "volume", "log_return",
                   "future_return_1h", "future_return_2h", "future_return_3h", "future_return_6h",
                   "future_return_12h", "rsi", "atr", "normalized_atr", "volume_zscore_24")

_SCHEMA = """CREATE TABLE market_hourly_features (
    ticker TEXT NOT NULL,
    bar_ts TEXT NOT NULL,                   -- start of the bar, same text as market_bars.timestamp_utc
    hour_bucket TEXT NOT NULL,              -- bar_ts rounded down to the hour = DimTime.ts_utc
    close REAL NOT NULL, volume REAL,
    log_return REAL,                        -- percent; = proposal's current_return (Current Return)
    future_return_1h REAL, future_return_2h REAL, future_return_3h REAL,
    future_return_6h REAL, future_return_12h REAL,    -- percent; NULL = no bar exactly n hours later
    rsi REAL, atr REAL, normalized_atr REAL, volume_zscore_24 REAL,
    PRIMARY KEY (ticker, bar_ts)) WITHOUT ROWID"""


def _epoch(text):
    return int(datetime.fromisoformat(text).timestamp())


def _text(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def ticker_features(bars):
    """bars: [(epoch, high, low, close, volume)] of ONE ticker, close not NULL, sorted. Returns feature rows."""
    stamps = [bar[0] for bar in bars]
    close_at = {bar[0]: bar[3] for bar in bars}

    true_range = []
    for ts, high, low, _, _ in bars:
        prev = close_at.get(ts - HOUR)
        true_range.append(max(high - low, abs(high - prev), abs(low - prev)) if prev is not None else high - low)

    rows, avg_gain, avg_loss = [], None, None
    gains, losses = [], []
    for i, (ts, high, low, close, volume) in enumerate(bars):
        prev = close_at.get(ts - HOUR)
        log_return = math.log(close / prev) * 100 if prev and close > 0 else None
        future = []
        for n in HORIZONS:
            later = close_at.get(ts + n * HOUR)
            future.append((later - close) / close * 100 if later is not None and close else None)

        # RSI: Wilder smoothing over consecutive valid bars
        rsi = None
        if i > 0:
            change = close - bars[i - 1][3]
            gain, loss = max(change, 0.0), max(-change, 0.0)
            if avg_gain is None:
                gains.append(gain)
                losses.append(loss)
                if len(gains) == RSI_PERIOD:
                    avg_gain, avg_loss = sum(gains) / RSI_PERIOD, sum(losses) / RSI_PERIOD
            else:
                avg_gain = (avg_gain * (RSI_PERIOD - 1) + gain) / RSI_PERIOD
                avg_loss = (avg_loss * (RSI_PERIOD - 1) + loss) / RSI_PERIOD
            if avg_gain is not None:
                rsi = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)

        # prior 24 clock hours, current excluded -> volume z-score (no look-ahead, no self-inclusion)
        lo = bisect.bisect_left(stamps, ts - WINDOW_HOURS * HOUR)
        prior = [b[4] for b in bars[lo:i] if b[4] is not None]
        zscore = None
        if volume is not None and len(prior) >= MIN_WINDOW:
            spread = statistics.pstdev(prior)
            zscore = (volume - statistics.fmean(prior)) / spread if spread > 0 else None

        # last 24 clock hours including this bar -> ATR
        lo_atr = bisect.bisect_left(stamps, ts - (WINDOW_HOURS - 1) * HOUR)
        window = true_range[lo_atr:i + 1]
        atr = statistics.fmean(window) if len(window) >= MIN_WINDOW else None
        normalized_atr = atr / close * 100 if atr is not None and close else None

        rows.append((_text(ts), _text(ts - ts % HOUR), close, volume, log_return, *future, rsi, atr,
                     normalized_atr, zscore))
    return rows


def build(db):
    db.execute("DROP TABLE IF EXISTS market_hourly_features")
    db.execute(_SCHEMA)
    by_ticker = {}
    for ticker, stamp, high, low, close, volume in db.execute(
            "SELECT ticker, timestamp_utc, high, low, close, volume FROM market_bars "
            "WHERE close IS NOT NULL ORDER BY ticker, timestamp_utc"):
        by_ticker.setdefault(ticker, []).append((_epoch(stamp), high, low, close, volume))
    for ticker, bars in by_ticker.items():
        out = [(ticker,) + row for row in ticker_features(bars)]
        db.executemany("INSERT INTO market_hourly_features VALUES (%s)" % ",".join("?" * 15), out)
    db.commit()


def load_fact(db):
    """FactMarketPrice = the figure-3 columns of market_hourly_features, keyed by (hour bucket, ticker)."""
    seed(db)
    db.execute("DELETE FROM FactMarketPrice")
    db.execute("""INSERT INTO FactMarketPrice (TimeID, TickerID, close, volume, future_return_1h, future_return_2h,
            future_return_3h, future_return_6h, future_return_12h, RSI, ATR)
        SELECT t.TimeID, k.TickerID, f.close, f.volume, f.future_return_1h, f.future_return_2h,
               f.future_return_3h, f.future_return_6h, f.future_return_12h, f.rsi, f.atr
        FROM market_hourly_features f
        JOIN DimTime t ON t.ts_utc = f.hour_bucket
        JOIN DimTicker k ON k.TickerSymbol = f.ticker""")
    db.commit()
    rows = db.execute("SELECT COUNT(*) FROM market_hourly_features").fetchone()[0]
    loaded = db.execute("SELECT COUNT(*) FROM FactMarketPrice").fetchone()[0]
    if rows != loaded:
        raise SystemExit("FactMarketPrice has %d rows but market_hourly_features has %d" % (loaded, rows))
    return {"features": rows, "fact_rows": loaded}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args(argv)
    db = connect(args.db)
    try:
        build(db)
        print(load_fact(db))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
