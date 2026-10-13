-- Star schema of the thesis warehouse (proposal figures 2, 3, 4). Names must match the figures exactly
-- because the report quotes them. Safe to run repeatedly (IF NOT EXISTS). Run by etl/seed_dims.py.
--
--   Figure 2: FactRedditVolume    (Reddit volume per hour / ticker / source)
--   Figure 3: FactMarketPrice     (price, volume, future returns, RSI, ATR per hour / ticker)
--   Figure 4: FactMarketSentiment (sentiment + win rates per hour / ticker / sentiment source / config)
-- Raw tables (reddit_content, market_bars, market_windows, market_gaps) live in the same file and are not touched.

-- ---------- dimensions ----------
CREATE TABLE IF NOT EXISTS DimTime (
    TimeID INTEGER PRIMARY KEY,
    Year INTEGER NOT NULL, Month INTEGER NOT NULL, Week INTEGER NOT NULL,   -- Week = ISO week number
    Day INTEGER NOT NULL, Hour INTEGER NOT NULL,
    ts_utc TEXT NOT NULL UNIQUE          -- EXTENSION (not in figure 2): join key, same text format as market_bars
);                                       --   e.g. 2025-03-04T14:00:00+00:00

CREATE TABLE IF NOT EXISTS DimTicker (
    TickerID INTEGER PRIMARY KEY,
    AssetClass TEXT NOT NULL CHECK (AssetClass IN ('stock_etf', 'crypto', 'futures')),
    TickerSymbol TEXT NOT NULL UNIQUE,
    TickerName TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS DimSource (
    SourceID INTEGER PRIMARY KEY,
    Platform TEXT NOT NULL,              -- 'Reddit'
    Subreddit TEXT NOT NULL,             -- 'r/wallstreetbets'
    ContentType TEXT NOT NULL CHECK (ContentType IN ('Post', 'Comment')),
    UNIQUE (Subreddit, ContentType)
);

CREATE TABLE IF NOT EXISTS DimSentimentSource (
    SourceID INTEGER PRIMARY KEY,        -- figure 4 names this column SourceID too
    Platform TEXT NOT NULL,
    Subreddit TEXT NOT NULL,             -- one per community, plus 'ALL' = the pooled panel (EXTENSION)
    ModelUsed TEXT NOT NULL,             -- 'VADER+FinBERT'
    UNIQUE (Subreddit, ModelUsed)
);

CREATE TABLE IF NOT EXISTS DimDetectionConfig (
    ConfigID INTEGER PRIMARY KEY,
    ZscoreThreshold REAL NOT NULL,
    SentimentThreshold REAL NOT NULL,
    Horizon TEXT NOT NULL,               -- '1h' .. '12h'
    UNIQUE (ZscoreThreshold, SentimentThreshold, Horizon)
);

CREATE TABLE IF NOT EXISTS DimMajoritySentiment (
    MajorityID INTEGER PRIMARY KEY,
    MajorityStatus TEXT NOT NULL UNIQUE CHECK (MajorityStatus IN ('positive', 'negative', 'neutral'))
);

-- ---------- facts ----------
CREATE TABLE IF NOT EXISTS FactRedditVolume (
    TimeID INTEGER NOT NULL REFERENCES DimTime(TimeID),
    TickerID INTEGER NOT NULL REFERENCES DimTicker(TickerID),
    SourceID INTEGER NOT NULL REFERENCES DimSource(SourceID),
    reddit_volume INTEGER NOT NULL,      -- number of texts that mention the ticker in that hour/source.
                                         -- DO NOT SUM across tickers (one text can mention several); see TASKS O1
    ticker_mention_count INTEGER NOT NULL,   -- total mentions (a text saying TSLA 3 times counts 3)
    PRIMARY KEY (TimeID, TickerID, SourceID)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS FactMarketPrice (
    TimeID INTEGER NOT NULL REFERENCES DimTime(TimeID),
    TickerID INTEGER NOT NULL REFERENCES DimTicker(TickerID),
    close REAL, volume REAL,
    future_return_1h REAL, future_return_2h REAL, future_return_3h REAL,    -- percent, not a fraction
    future_return_6h REAL, future_return_12h REAL,
    RSI REAL, ATR REAL,
    PRIMARY KEY (TimeID, TickerID)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS FactMarketSentiment (
    TimeID INTEGER NOT NULL REFERENCES DimTime(TimeID),
    TickerID INTEGER NOT NULL REFERENCES DimTicker(TickerID),
    SentimentSourceID INTEGER NOT NULL REFERENCES DimSentimentSource(SourceID),
    DetectionConfigID INTEGER NOT NULL REFERENCES DimDetectionConfig(ConfigID),
    MajorityID INTEGER REFERENCES DimMajoritySentiment(MajorityID),
    close REAL, volume REAL,
    sentiment_mean REAL,                 -- NULL = no text that hour. NULL is NOT 0 (0 means neutral)
    pos_ratio REAL, neg_ratio REAL, neu_ratio REAL,
    reddit_volume INTEGER,
    future_return_1h REAL, future_return_2h REAL, future_return_3h REAL,
    future_return_6h REAL, future_return_12h REAL,
    winrate_1h REAL, winrate_2h REAL, winrate_3h REAL, winrate_6h REAL, winrate_12h REAL,
    winrate_p_value_1h REAL, winrate_p_value_2h REAL, winrate_p_value_3h REAL,
    winrate_p_value_6h REAL, winrate_p_value_12h REAL,
    PRIMARY KEY (TimeID, TickerID, SentimentSourceID, DetectionConfigID)
) WITHOUT ROWID;

-- The primary keys already cover (TimeID, TickerID, ...). Dashboards filter by ticker first, so add (TickerID, TimeID).
CREATE INDEX IF NOT EXISTS FactRedditVolume_by_ticker ON FactRedditVolume(TickerID, TimeID);
CREATE INDEX IF NOT EXISTS FactMarketPrice_by_ticker ON FactMarketPrice(TickerID, TimeID);
CREATE INDEX IF NOT EXISTS FactMarketSentiment_by_ticker ON FactMarketSentiment(TickerID, TimeID);
