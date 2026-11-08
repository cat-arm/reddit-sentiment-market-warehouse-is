"""Numbers of the BTC-USD user story in the defence deck: what each dashboard page shows for BTC-USD over the full range
(all communities, all content types, final model).  It calls the SAME functions as the pages (dashboard.data), read-only.

Usage:  python scripts/deck_story_btc.py [--db output/reddit.sqlite3]
Output: output/reports/deck_story_btc.md  and  output/reports/deck_story_btc.json  (read by docs/presentation/build_deck_en.js)
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np                                     # noqa: E402
import pandas as pd                                    # noqa: E402

import dashboard_answers as answers                    # noqa: E402
from dashboard import data                             # noqa: E402
from etl.common import DEFAULT_DB, file_header         # noqa: E402

TICKER = "BTC-USD"
OUT_MD = ROOT / "output" / "reports" / "deck_story_btc.md"
OUT_JSON = ROOT / "output" / "reports" / "deck_story_btc.json"


def num(v, digits=4):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else round(float(v), digits)


def collect(db):
    rng = data.data_range(db)
    lo, hi = rng["reddit_lo"], rng["reddit_hi"]
    out = {"ticker": TICKER, "range": [pd.to_datetime(lo, unit="s").strftime("%Y-%m-%d"), pd.to_datetime(hi, unit="s").strftime("%Y-%m-%d")]}

    # page 1 Reddit Volume: market-wide cards
    cards, _, _ = answers.volume(db, lo, hi)
    out["p1"] = {row["การ์ด"]: row["ค่า"] for _, row in cards.iterrows()}

    # page 2 Ticker Mentions
    rank = data.mention_ranking(db, lo, hi).reset_index(drop=True)
    pos = int(rank.index[rank.ticker == TICKER][0]) + 1
    row = rank[rank.ticker == TICKER].iloc[0]
    out["p2"] = {"rank": pos, "of": int(len(rank)), "mentions": int(row.mentions), "texts_about": int(row.texts_about),
                 "mention_rate_pct": num(row.mention_rate_pct), "second": rank.iloc[1].ticker, "second_mentions": int(rank.iloc[1].mentions)}

    # page 3 Price and Return
    price = data.price_series_for(db, (TICKER,), lo, hi)
    first, last = price.close.dropna().iloc[0], price.close.dropna().iloc[-1]
    snap = data.ticker_snapshot(db, lo, hi, (TICKER,)).iloc[0]
    fr = data.future_return_by_group(db, lo, hi)
    crypto = fr[(fr.big_group == "crypto") & (fr.horizon == "1h")].iloc[0]
    out["p3"] = {"first_close": num(first, 2), "last_close": num(last, 2), "change_pct": num(100 * (last / first - 1), 1),
                 "mean_norm_atr_pct": num(snap.mean_normalized_atr_pct), "last_rsi": num(snap.last_rsi, 1),
                 "crypto_1h_mean_pct": num(crypto.mean_return_pct, 5), "crypto_1h_share_up": num(crypto.share_up)}

    # page 4 Market and Sentiment (same rule as the ranking table)
    ranking = answers.sentiment_ranking(db, lo, hi)
    ranked = ranking[ranking.ranked].reset_index(drop=True)
    r = ranked[ranked.series == TICKER].iloc[0]
    out["p4"] = {"sentiment": num(r.sentiment), "pos_pct": num(r.pos, 1), "neg_pct": num(r.neg, 1), "texts": int(r.texts),
                 "rank_from_top": int(ranked.index[ranked.series == TICKER][0]) + 1, "ranked": int(len(ranked))}

    # page 5 Statistical Analysis (stored panel_Ticker)
    st = data.stored_stat_table(db, "panel_Ticker")
    st = st[st.ticker == TICKER]
    out["p5"] = [{"target": t.target, "spearman_rho": num(t.spearman_rho), "p": num(t.spearman_p), "bh": num(t.spearman_bh),
                  "n": None if np.isnan(t.n) else int(t.n), "winrate": num(t.winrate, 1), "win_p": num(t.win_p)} for t in st.itertuples()]

    # page 6 Lead and Lag
    names = list(dict.fromkeys(data.sources(db).subreddit))
    sent = data.sentiment_hourly(db, (TICKER,), lo, hi, tuple(names), "VADER+FinBERT", "all", data.CONTENT_TYPES)
    frame = data.sentiment_frame(sent, lo, hi).rename(columns={"series": "ticker"})[["ticker", "hour_utc", "sentiment_mean"]].dropna()
    timing = frame.merge(price[["ticker", "hour_utc", "log_return"]], on=["ticker", "hour_utc"], how="left")
    lags = data.lag_correlation(timing)
    out["p6"] = [{"lag": int(l.lag), "rho": num(l.rho), "n": int(l.n), "lo": num(l.ci_lo), "hi": num(l.ci_hi)} for l in lags.itertuples()]

    # page 7 Hot Events at the default thresholds (Z 1.5, sentiment 0.05)
    events = data.hot_events(db, lo, hi, 1.5, 0.05)
    btc = events[events.ticker == TICKER].dropna(subset=["future_return_1h"])
    same = ((btc.sentiment_mean > 0) & (btc.future_return_1h > 0)) | ((btc.sentiment_mean < 0) & (btc.future_return_1h < 0))
    counts = data.signal_counts(db)
    import sqlite3
    con = sqlite3.connect("file:%s?mode=ro" % Path(db).resolve(), uri=True)
    by_type = dict(con.execute("SELECT signal_type, COUNT(*) FROM signal_events WHERE ticker = ? AND z_threshold = 1.5 AND s_threshold = 0.05 "
                               "GROUP BY signal_type", (TICKER,)).fetchall())
    by_z = dict(con.execute("SELECT z_threshold, COUNT(*) FROM signal_events WHERE ticker = ? AND s_threshold = 0.05 GROUP BY z_threshold", (TICKER,)).fetchall())
    con.close()
    out["p7"] = {"by_type": by_type, "total_default": int(sum(by_type.values())), "by_z_at_s005": {str(k): int(v) for k, v in by_z.items()},
                 "hot_rows_with_1h_return": int(len(btc)), "share_same_direction_1h": num(100 * same.mean(), 1) if len(btc) else None,
                 "all_assets_signal_rows_default": int(counts[(counts.z_threshold == 1.5) & (counts.s_threshold == 0.05)].n_signals.sum())}
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    result = collect(parser.parse_args(argv).db)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    lines = ["# BTC-USD user story: numbers per dashboard page", "",
             *file_header("ตัวเลขที่แต่ละหน้าของ dashboard แสดงสำหรับ BTC-USD ช่วงเต็ม (ใช้ในสไลด์ user story)", "scripts/deck_story_btc.py",
                          "python scripts/deck_story_btc.py", "output/reddit.sqlite3 อ่านอย่างเดียว ผ่านฟังก์ชันของ dashboard/data.py"), "",
             "```json", json.dumps(result, ensure_ascii=False, indent=1, default=str), "```"]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
