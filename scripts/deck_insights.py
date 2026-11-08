"""Numbers behind the insight stories (docs/USER_STORY_INSIGHTS_TH.md): where does Reddit sentiment line up with prices?
Reads the final hourly panel (`merged_hourly_panel`, scope 'global' = market-wide sentiment) and `analysis_results`, read-only.

Usage:  python scripts/deck_insights.py [--db output/reddit.sqlite3]
Output: output/reports/insight_stories.md  and  output/reports/insight_stories.json
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np                                     # noqa: E402
import pandas as pd                                    # noqa: E402
from scipy import stats                                # noqa: E402

from dashboard import data                             # noqa: E402
from etl.common import DEFAULT_DB, file_header         # noqa: E402

OUT_MD = ROOT / "output" / "reports" / "insight_stories.md"
OUT_JSON = ROOT / "output" / "reports" / "insight_stories.json"
SPIKE_Z = 1.5
EVENT_HOUR = "2025-04-09 17:00"


def spearman(d, col):
    d = d[["sentiment_mean", col]].dropna()
    if len(d) < 30:
        return None
    rho, p = stats.spearmanr(d.sentiment_mean, d[col])
    return {"rho": round(float(rho), 4), "p": float(p), "n": int(len(d))}


def bh(pvals):
    p = np.asarray(pvals, float)
    order = np.argsort(p)
    adj = np.empty_like(p)
    running = 1.0
    for rank, i in zip(range(len(p), 0, -1), order[::-1]):
        running = min(running, p[i] * len(p) / rank)
        adj[i] = running
    return adj


def collect(db):
    con = sqlite3.connect("file:%s?mode=ro" % Path(db).resolve(), uri=True)
    panel = pd.read_sql("""SELECT ticker, big_group, hour_utc, log_return, future_return_1h, sentiment_mean, reddit_volume,
                           reddit_volume_zscore_24 AS z FROM merged_hourly_panel WHERE scope = 'global' AND variant = 'all'""", con)
    price = pd.read_sql("SELECT ticker, hour_utc, log_return FROM merged_hourly_panel WHERE scope = 'ticker' AND variant = 'all'", con)
    out = {"spike_z": SPIKE_Z, "event_hour": EVENT_HOUR}

    # story 1: same-hour correlation of market-wide sentiment with each asset's Current Return, all hours against busy hours
    rows = []
    for t, g in panel.groupby("ticker"):
        a, s = spearman(g, "log_return"), spearman(g[g.z > SPIKE_Z], "log_return")
        if a and s:
            rows.append({"ticker": t, "group": g.big_group.iloc[0], "all": a, "spike": s})
    adj = bh([r["spike"]["p"] for r in rows])
    for r, v in zip(rows, adj):
        r["spike"]["bh"] = float(v)
    out["story1"] = sorted(rows, key=lambda r: -r["spike"]["rho"])
    out["story1_positive_bh_count"] = int(sum(1 for r in rows if r["spike"]["bh"] < 0.05 and r["spike"]["rho"] > 0))
    out["story1_assets"] = len(rows)

    # story 2: who moves first in busy hours: correlation with the return k hours before / after the Reddit hour
    out["story2"] = {}
    for t in ("ES=F", "NQ=F", "BTC-USD"):
        g = panel[(panel.ticker == t) & (panel.z > SPIKE_Z)][["ticker", "hour_utc", "sentiment_mean"]].dropna()
        timing = g.merge(price[price.ticker == t][["ticker", "hour_utc", "log_return"]], on=["ticker", "hour_utc"], how="left")
        lags = data.lag_correlation(timing)
        out["story2"][t] = [{"lag": int(l.lag), "rho": round(float(l.rho), 3), "n": int(l.n)} for l in lags.itertuples()]
        d = panel[(panel.ticker == t) & (panel.z > SPIKE_Z)].dropna(subset=["sentiment_mean", "future_return_1h"])
        rho, p = stats.spearmanr(d.sentiment_mean, d.future_return_1h)
        out["story2"][t + "_next_hour"] = {"rho": round(float(rho), 4), "p": float(p), "n": int(len(d))}

    # story 3: the busiest hour of the whole data set and the hours around it
    ts = int(pd.Timestamp(EVENT_HOUR).timestamp())
    one = panel[panel.ticker == "BTC-USD"].set_index("hour_utc")
    window = []
    for h in range(ts - 3 * 3600, ts + 5 * 3600, 3600):
        row = {"hour": pd.to_datetime(h, unit="s").strftime("%Y-%m-%d %H:%M"), "texts": int(one.reddit_volume.get(h, 0)),
               "z": num(one.z.get(h)), "sentiment": num(one.sentiment_mean.get(h), 3)}
        for t in ("ES=F", "BTC-USD", "TSLA"):
            v = price[(price.ticker == t) & (price.hour_utc == h)].log_return
            row["ret_" + t] = num(v.iloc[0], 2) if len(v) else None
        window.append(row)
    out["story3_window"] = window
    top = one.dropna(subset=["reddit_volume"]).sort_values("reddit_volume", ascending=False).head(5)
    out["story3_top_hours"] = [{"hour": pd.to_datetime(h, unit="s").strftime("%Y-%m-%d %H:%M"), "texts": int(r.reddit_volume), "z": num(r.z), "sentiment": num(r.sentiment_mean, 3)}
                               for h, r in top.iterrows()]
    at = panel[panel.hour_utc == ts]
    out["story3_event_returns"] = {r.ticker: num(r.log_return, 2) for r in at.itertuples() if r.log_return == r.log_return}
    tick = data.sentiment_hourly(db, ("TSLA", "BTC-USD"), ts - 6 * 3600, ts + 6 * 3600, tuple(dict.fromkeys(data.sources(db).subreddit)), "VADER+FinBERT", "all", data.CONTENT_TYPES)
    frame = data.sentiment_frame(tick, ts - 6 * 3600, ts + 6 * 3600).dropna(subset=["sentiment_mean"])
    out["story3_ticker_sentiment"] = [{"hour": pd.to_datetime(r.hour_utc, unit="s").strftime("%Y-%m-%d %H:%M"), "ticker": r.series, "sentiment": round(float(r.sentiment_mean), 3), "texts": int(r.texts)}
                                      for r in frame.itertuples() if ts - 2 * 3600 <= r.hour_utc <= ts + 3 * 3600]

    # story 4: the statistically significant but tiny win rates (stored, panel_global, sign of sentiment)
    win = pd.read_sql("""SELECT ticker, horizon, metric_value * 100 AS win_rate, p_value, p_value_bh, n_samples FROM analysis_results
                         WHERE analysis = 'winrate' AND panel_name = 'panel_global' AND level = 'ticker' AND metric_name = 'winrate' AND predictor = 'sign(sentiment_mean)'
                           AND p_value_bh < 0.05 AND n_samples >= 300 ORDER BY p_value_bh""", con)
    out["story4"] = [{"ticker": r.ticker, "horizon": r.horizon, "win_rate": round(r.win_rate, 1), "bh": float(r.p_value_bh), "n": int(r.n_samples)} for r in win.itertuples()]
    con.close()
    return out


def num(v, digits=3):
    return None if v is None or v != v else round(float(v), digits)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    result = collect(parser.parse_args(argv).db)
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    OUT_MD.write_text("\n".join([*file_header("ตัวเลขของเรื่องเล่าเชิงข้อมูล: ที่ไหนความรู้สึกบน Reddit ขยับพร้อมราคา", "scripts/deck_insights.py",
                                            "python scripts/deck_insights.py", "output/reddit.sqlite3 อ่านอย่างเดียว (merged_hourly_panel, analysis_results)"),
                                 "", "```json", json.dumps(result, ensure_ascii=False, indent=1), "```"]), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("story1_positive_bh_count", "story1_assets", "story3_top_hours", "story4")}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
