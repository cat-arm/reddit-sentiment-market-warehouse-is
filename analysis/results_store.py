"""Shared storage for the Stage A analyses (A1 correlation, A2 win rate, A3 logistic) -> table `analysis_results`.

One row = one number.  Columns:
    run_id, analysis ('correlation' | 'winrate' | 'logistic'), panel_name,
    level ('ticker' | 'big_group' | 'all'), ticker ('ALL' unless level='ticker'), big_group ('ALL' for level='all'),
    predictor, target, horizon ('log_return' | '1h' | '2h' | '3h' | '6h' | '12h'),
    metric_name (pearson / spearman / winrate / auc / coef ...), metric_value, p_value (raw, not adjusted for the number
    of tests), n_samples,
    status ('ok' | 'insufficient_data' | 'constant'), config_hash, created_at.
A row with status != 'ok' keeps n_samples but has NULL metric/p-value (never 0: 0 would read as "no relation").
Each analysis replaces its own previous rows (`replace`), so the table always holds the latest run per analysis.
"""

import datetime
import hashlib
import json

import numpy as np

SCHEMA = """CREATE TABLE IF NOT EXISTS analysis_results (
    run_id TEXT NOT NULL, analysis TEXT NOT NULL, panel_name TEXT NOT NULL,
    level TEXT NOT NULL, ticker TEXT NOT NULL, big_group TEXT NOT NULL,
    predictor TEXT NOT NULL, target TEXT NOT NULL, horizon TEXT NOT NULL,
    metric_name TEXT NOT NULL, metric_value REAL, p_value REAL,
    n_samples INTEGER NOT NULL, status TEXT NOT NULL, config_hash TEXT NOT NULL, created_at TEXT NOT NULL)"""
INDEX = ("CREATE INDEX IF NOT EXISTS analysis_results_key ON analysis_results"
         "(analysis, panel_name, level, ticker, predictor, horizon, metric_name)")
COLUMNS = ("run_id", "analysis", "panel_name", "level", "ticker", "big_group", "predictor", "target", "horizon",
           "metric_name", "metric_value", "p_value", "n_samples", "status", "config_hash", "created_at")
# "log_return" = the proposal's current_return (Current Return); stored under the old name in analysis_results
HORIZONS = {"log_return": "log_return", "future_return_1h": "1h", "future_return_2h": "2h",
            "future_return_3h": "3h", "future_return_6h": "6h", "future_return_12h": "12h"}


def config_hash(params):
    """Short stable hash of the analysis parameters (goes into every row for the audit trail)."""
    return hashlib.sha1(json.dumps(params, sort_keys=True, default=str).encode()).hexdigest()[:12]


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def replace(db, analysis, rows):
    """Delete the previous rows of `analysis` and store the new ones (one transaction)."""
    db.execute(SCHEMA)
    if "p_value_bh" in [r[1] for r in db.execute("PRAGMA table_info(analysis_results)")]:
        db.execute("ALTER TABLE analysis_results DROP COLUMN p_value_bh")     # the Benjamini-Hochberg column was removed (2026-11-01)
    db.execute(INDEX)
    db.execute("DELETE FROM analysis_results WHERE analysis = ?", (analysis,))
    db.executemany("INSERT INTO analysis_results (%s) VALUES (%s)" % (", ".join(COLUMNS), ", ".join("?" * len(COLUMNS))),
                   [tuple(_clean(r.get(c)) for c in COLUMNS) for r in rows])
    db.commit()


def _clean(value):
    if isinstance(value, (np.floating, float)):
        return None if np.isnan(value) else float(value)
    if isinstance(value, np.integer):
        return int(value)
    return value
