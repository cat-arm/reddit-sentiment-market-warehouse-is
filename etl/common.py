"""Shared helpers for the ETL stages: project paths, YAML configs, SQLite connections."""

import sqlite3
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIGS = ROOT / "configs"
DEFAULT_DB = ROOT / "output" / "reddit.sqlite3"


def load_yaml(name):
    """Load configs/<name> (e.g. 'tickers.yaml') and return the parsed document."""
    with (CONFIGS / name).open(encoding="utf-8") as source:
        return yaml.safe_load(source)


def subreddits():
    """The 6 in-scope communities, spelled as stored in reddit_content."""
    return tuple(load_yaml("subreddits.yaml")["subreddits"])


def connect(db_path=DEFAULT_DB, readonly=False):
    path = Path(db_path).resolve()
    if readonly:
        return sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=60)
    return sqlite3.connect(str(path), timeout=60)


# Proposal 7.3 / 8 + VADER's own convention (Hutto & Gilbert 2014 / vaderSentiment README):
# positive s >= 0.05, negative s <= -0.05, neutral = the open band -0.05 < s < 0.05 (edges are directional).
NEUTRAL_BAND = 0.05


def status_of(score):
    """'positive' / 'negative' / 'neutral' for one VADER or FinBERT score (band edges are directional)."""
    if score >= NEUTRAL_BAND:
        return "positive"
    if score <= -NEUTRAL_BAND:
        return "negative"
    return "neutral"
