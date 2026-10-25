"""Shared helpers for the ETL stages: project paths, YAML configs, SQLite connections."""

import sqlite3
from datetime import datetime
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


def file_header(what, script, rerun, sources="", comment=False):
    """Opening lines of every generated report/CSV: what the file is, when it was made, by which script.
    `comment=True` prefixes each line with '# ' for CSV files (pandas: read_csv(..., comment='#'))."""
    made = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = ["ไฟล์นี้คืออะไร: " + what, "สร้างเมื่อ: %s (เวลาเครื่อง) โดยสคริปต์ %s" % (made, script)]
    if sources:
        lines.append("ข้อมูลที่ใช้: " + sources)
    lines.append("สร้างใหม่ด้วยคำสั่ง: " + rerun)
    return ["# " + line for line in lines] if comment else ["> " + line + "  " for line in lines]


# Proposal 7.3 / 8 + VADER's own convention (Hutto & Gilbert 2014 / vaderSentiment README):
# positive s >= 0.05, negative s <= -0.05, neutral = the open band -0.05 < s < 0.05 (edges are directional).
NEUTRAL_BAND = 0.05


def status_of(score, band=NEUTRAL_BAND):
    """'positive' / 'negative' / 'neutral' for one VADER or FinBERT score (band edges are directional).
    `band` is only changed by the sensitivity test (scripts/neutral_band_sensitivity.py); the pipeline uses 0.05."""
    if score >= band:
        return "positive"
    if score <= -band:
        return "negative"
    return "neutral"
