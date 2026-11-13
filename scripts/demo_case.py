"""Numbers of the live-demo case (docs/DEMO_CASE_TH.md): the volatile week 7-11 April 2025, page by page.

It runs the REAL dashboard pages (Streamlit AppTest) with the filters written in the demo guide and records the numbers on the cards,
so every number the presenter will see on screen is checked here.  Win rates of page 7 use the same function as the page (dashboard.data).
Read-only; needs the real database.

Usage:  python scripts/demo_case.py [--db output/reddit.sqlite3]
Output: output/reports/demo_case.md  and  output/reports/demo_case.json
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np                                     # noqa: E402
import pandas as pd                                    # noqa: E402

from analysis import signals                           # noqa: E402
from dashboard import data                             # noqa: E402
from etl.common import DEFAULT_DB, file_header         # noqa: E402

OUT_MD = ROOT / "output" / "reports" / "demo_case.md"
OUT_JSON = ROOT / "output" / "reports" / "demo_case.json"
INSIGHTS = ROOT / "output" / "reports" / "insight_stories.json"
WEEK = (dt.date(2025, 4, 7), dt.date(2025, 4, 11))
FULL = (dt.date(2024, 10, 1), dt.date(2026, 8, 31))
HOURLY, DAILY = "รายชั่วโมง", "รายวัน"
TICKERS = ["AAPL", "AMC", "AMD", "BITO", "BRK-B", "COIN", "GME", "HOOD", "IBIT", "IWM", "JNJ", "JPM", "KO", "MARA", "MSFT", "MSTR", "NVDA", "PLTR",
           "QQQ", "SPY", "TSLA", "XOM", "CL=F", "ES=F", "GC=F", "NG=F", "NQ=F", "RTY=F", "BTC-USD", "DOGE-USD", "ETH-USD", "SHIB-USD", "SOL-USD", "XRP-USD"]
ONE = {"ES=F"}                                  # the asset of pages 3 to 6 (the sidebar keeps the choice from page to page); page 7 takes every asset
WIN_MIN, WIN_N, WIN_H = 57, 30, "Current Return"          # the win-rate filter of the signal list on page 7: asset win rate at 6 hours of at least 55% on at least 100 signals
HORIZONS = [("log_return", "Current Return"), ("future_return_1h", "1h"), ("future_return_2h", "2h"), ("future_return_3h", "3h"),
            ("future_return_6h", "6h"), ("future_return_12h", "12h")]


def run_page(page, rng, level, keep=None, full=False, **state):
    """Open one dashboard page with the given sidebar state and return its cards (label -> value) and tables (and the AppTest with `full`)."""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "dashboard" / "pages" / page), default_timeout=300)
    at.session_state["f_range"], at.session_state["f_gran"] = rng, level
    for symbol in TICKERS:
        at.session_state["f_tk_" + symbol] = keep is None or symbol in keep
    for key, value in state.items():
        at.session_state[key] = value
    at.run()
    if at.exception:
        raise RuntimeError("%s failed: %s" % (page, at.exception[0].value))
    cards, tables = {m.label: m.value for m in at.metric}, [d.value for d in at.dataframe]
    return (cards, tables, at) if full else (cards, tables)


def chart_frames(at):
    """The data behind every chart of a page (Altair charts are sent to the browser with their data): list of (mark, DataFrame)."""
    import io
    import pyarrow as pa
    out = []
    for chart in at.get("vega_lite_chart"):
        spec = json.loads(chart.proto.spec)
        frames = [pa.ipc.open_stream(io.BytesIO(d.data.data)).read_all().to_pandas() for d in chart.proto.datasets]
        mark = spec.get("mark", (spec.get("layer") or [{}])[0].get("mark"))
        out.append((mark.get("type") if isinstance(mark, dict) else mark, frames[0] if frames else None))
    return out


def heat_row(frame, ticker):
    """One ticker of a page-5 heat map: per target the correlation, its adjusted p, n and the win rate (what the page shows)."""
    rows = frame[frame.ticker == ticker]
    return {r.target: {"spearman": round(float(r.spearman_rho), 4), "bh": float(r.spearman_bh), "n": int(r.n),
                       "win_rate": None if pd.isna(r.winrate) else round(float(r.winrate), 1), "win_n": None if pd.isna(r.win_n) else int(r.win_n),
                       "win_bh": None if pd.isna(r.win_bh) else float(r.win_bh)} for r in rows.itertuples()}

def epoch(day, end=False):
    return int(dt.datetime(day.year, day.month, day.day, 23 if end else 0, tzinfo=dt.timezone.utc).timestamp())


def win_rates(events):
    """The page-7 chart: how often the price went the same way as the sentiment, per horizon (same rule as the page)."""
    directional = events[events.sentiment_mean.notna() & (events.sentiment_mean != 0)]
    rows = []
    for column, name in HORIZONS:
        moved = directional[directional[column].notna() & (directional[column] != 0)]
        n = len(moved)
        wins = int((np.sign(moved.sentiment_mean) == np.sign(moved[column])).sum()) if n else 0
        rows.append({"horizon": name, "n": n, "win_rate": round(100.0 * wins / n, 1) if n >= 30 else None})
    return rows


def collect(db):
    out = {"week": [str(WEEK[0]), str(WEEK[1])], "full": [str(FULL[0]), str(FULL[1])]}
    lo, hi = epoch(WEEK[0]), epoch(WEEK[1], end=True)

    out["p1"], _ = run_page("1_Reddit_Volume.py", WEEK, HOURLY)
    out["p1_full"], _ = run_page("1_Reddit_Volume.py", FULL, DAILY)
    out["p2"], tables = run_page("2_Ticker_Mentions.py", WEEK, HOURLY)
    rank = data.mention_ranking(db, lo, hi).reset_index(drop=True)
    out["p2_top"] = [{"ticker": r.ticker, "mentions": int(r.mentions), "texts_about": int(r.texts_about), "rate_pct": round(float(r.mention_rate_pct), 3)}
                     for r in rank.head(6).itertuples()]
    out["p3"], _ = run_page("3_Price_and_Return.py", WEEK, HOURLY, ONE)
    out["p3b_price_reddit"], _ = run_page("4_Price_and_Reddit.py", WEEK, HOURLY, ONE)          # extension: Price and Return with the Reddit volume
    out["p4"], _ = run_page("5_Market_and_Sentiment.py", WEEK, HOURLY, ONE)
    ts = epoch(dt.date(2025, 4, 9)) + 17 * 3600                            # the busiest hour of the whole data set
    names = tuple(dict.fromkeys(data.sources(db).subreddit))
    hourly = data.sentiment_frame(data.sentiment_hourly(db, ("ES=F",), ts - 6 * 3600, ts + 6 * 3600, names, "VADER+FinBERT", "all", data.CONTENT_TYPES), ts - 6 * 3600, ts + 6 * 3600)
    out["p4_event_hours"] = [{"hour": pd.to_datetime(r.hour_utc, unit="s").strftime("%Y-%m-%d %H:%M"), "sentiment": None if pd.isna(r.sentiment_mean) else round(float(r.sentiment_mean), 3),
                              "texts": int(r.texts)} for r in hourly.itertuples() if ts - 2 * 3600 <= r.hour_utc <= ts + 3 * 3600]

    # page 5: the heat map is read from the page itself (one view, no tabs); the slider Z-score threshold moves it (1.5 = the volume-spike panel)
    out["p5"] = {}
    for z in (0.0, 1.5):
        cards, _, at = run_page("6_Statistical_Analysis.py", FULL, DAILY, ONE, full=True, d_z=z, d_s=0.0)
        heat = [f for _, f in chart_frames(at) if f is not None and {"ticker", "spearman_rho", "winrate"} <= set(f.columns)]      # the heat map of the page (one view)
        out["p5"]["z=%.1f" % z] = {"cards": cards, "all_texts_tab": heat_row(heat[0], "ES=F")}
    out["p5_cards_all34"], _ = run_page("6_Statistical_Analysis.py", FULL, DAILY, None, d_z=0.0, d_s=0.0)
    insights = json.loads(INSIGHTS.read_text(encoding="utf-8")) if INSIGHTS.exists() else {}      # scripts/deck_insights.py
    out["p5_bh_positive"] = [insights.get("story1_positive_bh_count"), insights.get("story1_assets")]
    logistic = data.logistic_results(db)
    futures = logistic[(logistic.status == "ok") & (logistic.panel == "panel_global") & (logistic.metric == "auc") & (logistic.level == "big_group") & (logistic.big_group == "futures")]
    out["p5_logistic_futures_auc"] = {r.horizon: round(float(r.value), 4) for r in futures.itertuples()}

    out["p7"], tables = run_page("8_Hot_Events.py", WEEK, HOURLY, None, d_z=1.5, d_s=0.05)
    out["p7_by_type"] = tables[0].to_dict("records")
    found = data.market_signals(db, epoch(FULL[0]), epoch(FULL[1], end=True), tuple(data.tickers(db).ticker), ("positive", "negative", "neutral"), 1.5, 0.05)   # the page's own function
    week_events = found[(found.hour_utc >= lo) & (found.hour_utc <= hi)]
    if len(week_events) != int(out["p7"]["จำนวนสัญญาณ (ชั่วโมง × สินทรัพย์)"].replace(",", "")):
        raise RuntimeError("signal count differs from the page: %d" % len(week_events))
    out["p7_week_win"] = win_rates(week_events)
    full_events = found[(found.hour_utc >= epoch(FULL[0])) & (found.hour_utc <= epoch(FULL[1], end=True))]
    out["p7_full_signals"] = int(len(full_events))
    out["p7_full_win"] = win_rates(full_events)

    # the win-rate filter of the signal list on page 7: the stored Win Rate of each asset and horizon (BH over every tested pair)
    from dashboard import common                         # the lookup of the page: the numbers of system 7.4 (the Statistical Analysis page) with the same thresholds
    stat74 = common.panel_stat("global", "all", tuple(data.tickers(db).ticker), epoch(FULL[0]), epoch(FULL[1], end=True), tuple(dict.fromkeys(data.sources(db).subreddit)),
                               "VADER+FinBERT", ("positive", "negative", "neutral"), 1.5, 0.05, ("Post", "Comment"), "sentiment_mean")
    names = {"log_return": "Current Return", "1h": "1h", "2h": "2h", "3h": "3h", "6h": "6h", "12h": "12h"}
    table = pd.DataFrame({"ticker": stat74.ticker, "horizon": stat74.target.map(names), "n": stat74.win_n, "win_rate": stat74.winrate,
                                            "rho": stat74.spearman_rho, "p": stat74.win_p, "p_bh": stat74.win_bh})
    at_h = table[table.horizon == WIN_H]
    kept = at_h[at_h.win_rate >= WIN_MIN].sort_values("win_rate", ascending=False)
    win_col = dict((name, col) for col, name in HORIZONS)[WIN_H]
    listed = int((full_events.ticker.isin(kept.ticker) & full_events[win_col].notna() & (full_events[win_col] != 0) & full_events.sentiment_mean.notna() & (full_events.sentiment_mean != 0)).sum())        # the list shows only the signals that can be judged
    top_raw = table.sort_values("p").head(5)
    bh_pairs = table[table.p_bh < 0.05].sort_values("p_bh")
    out["p7_win_filter"] = {"bh_pairs": [{"ticker": r.ticker, "horizon": r.horizon, "n": int(r.n), "win_rate": round(r.win_rate, 1), "rho": round(float(r.rho), 3), "p_bh": round(float(r.p_bh), 4)} for r in bh_pairs.itertuples()],
                            "raw_p_below_05": int((table.p < 0.05).sum()), "lowest_raw": [{"ticker": r.ticker, "horizon": r.horizon, "n": int(r.n), "win_rate": round(r.win_rate, 1), "rho": round(float(r.rho), 3), "p": round(float(r.p), 4), "p_bh": round(float(r.p_bh), 3)} for r in top_raw.itertuples()],
                            "tested": int(table.p.notna().sum()), "expected_by_chance": round(0.05 * int(table.p.notna().sum()), 1), "pass_bh": int((table.p_bh < 0.05).sum()),
                            "filter": [WIN_MIN, WIN_N, WIN_H], "kept": int(len(kept)), "kept_pass_bh": int((kept.p_bh < 0.05).sum()), "events_listed": listed,
                            "best_p_bh": None if kept.empty else round(float(kept.p_bh.min()), 3),
                            "top": [{"ticker": r.ticker, "horizon": r.horizon, "n": int(r.n), "win_rate": round(r.win_rate, 1), "p_bh": round(float(r.p_bh), 3)} for r in kept.head(5).itertuples()]}
    _, tables = run_page("8_Hot_Events.py", FULL, DAILY, None, d_z=1.5, d_s=0.05, h_wh=WIN_H)
    score_tab = [t for t in tables if "ความรู้สึก (ทั้งตลาด)" in t.columns]          # the tab of the score (the other tab reads the majority)
    shown = len(score_tab[0]) if score_tab else 0
    if shown != min(300, listed):
        raise RuntimeError("signal list differs from the page: %d against %d" % (shown, min(300, listed)))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    result = collect(parser.parse_args(argv).db)
    text = json.dumps(result, ensure_ascii=False, indent=1, default=str)
    OUT_JSON.write_text(text, encoding="utf-8")
    OUT_MD.write_text("\n".join([*file_header("ตัวเลขของเคส demo สัปดาห์ผันผวน 7-11 เม.ย. 2025 ทีละหน้า dashboard", "scripts/demo_case.py",
                                            "python scripts/demo_case.py", "output/reddit.sqlite3 อ่านอย่างเดียว; รันหน้า dashboard จริงด้วย Streamlit AppTest"),
                                 "", "```json", text, "```"]), encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
