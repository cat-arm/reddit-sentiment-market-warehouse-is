"""Numbers of the Thai defence deck (docs/presentation/build_deck_th.js).

Reads the database read-only plus the reports of the earlier steps and writes one JSON with every number the slides print.  The deck draws its
charts itself as native shapes, so no picture is made here.
Sources: output/tables/t1..t4, output/reports/rule_validation/, output/reports/hot_events_forward_check.csv, tables of output/reddit.sqlite3
(market_bars, reddit_volume_hourly, analysis_results, panels) and analysis/hot_events.py (the six KPIs and the level cuts).

Usage:   python scripts/deck_th_numbers.py [--db output/reddit.sqlite3]
Output:  output/reports/deck_th_numbers.json
Run first: python steps/34_hot_events_forward_check.py  (and the steps of the rule validation, 26 and 29)
"""
import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis import hot_events as he  # noqa: E402
from etl.common import DEFAULT_DB, load_yaml  # noqa: E402

TABLES, REPORTS = ROOT / "output" / "tables", ROOT / "output" / "reports"
OUT_JSON = REPORTS / "deck_th_numbers.json"


def rows(path, skip="#"):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(line for line in f if not line.startswith(skip)))


def reddit_numbers(db):
    t1 = {(r["step"], r["status"]): int(r["n"]) for r in rows(TABLES / "t1_data_funnel.csv")}
    removed = sum(n for (s, st), n in t1.items() if s.startswith("1 ") and st != "available")
    raw6 = sum(n for (s, _), n in t1.items() if s.startswith("1 "))
    cut = {st: n for (s, st), n in t1.items() if s.startswith("3 ")}
    clean = t1[("4 ผ่านตัวกรองคุณภาพ (filtered_text)", "passed")]
    processed = t1[("2 ล้างข้อความแล้ว (processed_text)", "written")]
    raw_all = db.execute("SELECT COUNT(*) FROM reddit_content").fetchone()[0]
    per = db.execute("""SELECT d.Subreddit, SUM(v.texts) FROM reddit_volume_hourly v JOIN DimSource d ON d.SourceID = v.SourceID
                        GROUP BY 1 ORDER BY 2 DESC""").fetchall()
    communities = [{"name": s, "texts": int(n), "share": 100.0 * n / clean} for s, n in per]
    mentions = rows(TABLES / "t4_ticker_mentions.csv")
    return {"raw_all": raw_all, "raw6": raw6, "removed": removed, "processed": processed, "empty_after_clean": raw6 - removed - processed,
            "bot": cut["bot_or_moderation_text"], "short": cut["too_short"], "non_english": cut["non_english"], "clean": clean,
            "kept_pct": 100.0 * clean / raw6, "communities": communities,
            "texts_with_ticker": db.execute("SELECT COUNT(DISTINCT src_rowid) FROM ticker_mentions").fetchone()[0],
            "top_mentions": [{"ticker": r["ticker"], "mentions": int(r["mentions"])} for r in mentions[:5]]}


def market_numbers(db):
    cfg = load_yaml("tickers.yaml")["tickers"]
    per = db.execute("SELECT ticker, COUNT(*), SUM(close IS NOT NULL) FROM market_bars GROUP BY ticker ORDER BY ticker").fetchall()
    assets = [{"ticker": t, "group": cfg[t]["asset_class"], "sub": cfg[t].get("instrument", ""), "raw": int(n), "clean": int(c)} for t, n, c in per]
    groups = {}
    for a in assets:
        g = groups.setdefault(a["group"], {"n": 0, "raw": 0, "clean": 0})
        g["n"] += 1
        g["raw"] += a["raw"]
        g["clean"] += a["clean"]
    coverage = {}
    for g, h1, h6, h12 in db.execute("""SELECT d.AssetClass, AVG(f.future_return_1h IS NOT NULL), AVG(f.future_return_6h IS NOT NULL),
                                               AVG(f.future_return_12h IS NOT NULL)
                                        FROM market_hourly_features f JOIN DimTicker d ON d.TickerSymbol = f.ticker GROUP BY 1""").fetchall():
        coverage[g] = {"h1": 100 * h1, "h6": 100 * h6, "h12": 100 * h12}
    return {"assets": assets, "groups": groups, "coverage": coverage, "raw": sum(a["raw"] for a in assets), "clean": sum(a["clean"] for a in assets)}


def sentiment_numbers():
    dist = {}
    for r in rows(TABLES / "t2_sentiment_distribution.csv"):
        dist.setdefault(r["model"], {})[r["label"]] = float(r["share_pct"])
    methods = {r["final_method"]: float(r["share_pct"]) for r in rows(TABLES / "t3_final_method.csv")}
    groups = {"same_direction": methods["same_direction"] + methods["same_direction_far"], "both_neutral": methods["both_neutral"],
              "small_conflict": methods["small_conflict_no_rule"] + methods["small_conflict_rule_agrees"] + methods["small_conflict_rule_clash"],
              "hard_conflict": methods["hard_conflict_no_rule"] + methods["hard_conflict_rule"] + methods["hard_conflict_mixed_zero"]}
    acc_rows = rows(REPORTS / "rule_validation" / "band_and_confusion.csv")
    accuracy = {}
    for r in acc_rows:
        accuracy.setdefault(r["split"], {})[r["method"]] = 100 * float(r["accuracy_band_0.05"])
    strata = {}
    for r in rows(REPORTS / "rule_validation" / "rule_validation.csv"):
        s = strata.setdefault(r["stratum"], {"n": 0, "vader": 0, "finbert": 0, "final": 0})
        s["n"] += int(r["n"])
        for m in ("vader", "finbert", "final"):
            s[m] += int(r[m + "_correct"])
    labels = {}
    for r in rows(REPORTS / "rule_validation" / "labeling_sheet.csv"):
        labels[r["human_label"]] = labels.get(r["human_label"], 0) + 1
    hard = strata["hard_conflict_keyword"]
    return {"distribution": dist, "conflict": groups, "accuracy": accuracy, "labels": labels, "n_labelled": sum(labels.values()),
            "hard_keyword": {m: 100.0 * hard[m] / hard["n"] for m in ("vader", "finbert", "final")}}


def analysis_numbers(db):
    q = db.execute
    auc = {(p, h): v for p, h, v in q("""SELECT panel_name, horizon, metric_value FROM analysis_results WHERE analysis = 'logistic' AND level = 'all'
                                         AND metric_name = 'auc' AND panel_name IN ('panel_global', 'panel_baseline')""")}
    win = {(p, h): (v, pv) for p, h, v, pv in q("""SELECT panel_name, horizon, metric_value, p_value FROM analysis_results WHERE analysis = 'winrate'
                                                   AND level = 'all' AND metric_name = 'winrate' AND panel_name IN ('panel_global', 'panel_baseline')
                                                   AND predictor IN ('sign(sentiment_mean)', 'random_direction')""")}
    spearman = {h: v for h, v in q("""SELECT horizon, metric_value FROM analysis_results WHERE analysis = 'correlation' AND level = 'all'
                                      AND metric_name = 'spearman' AND panel_name = 'panel_global' AND predictor = 'sentiment_mean'""")}
    panels = dict(q("SELECT panel_name, COUNT(*) FROM panels GROUP BY 1"))
    horizons = ["log_return", "1h", "2h", "3h", "6h", "12h"]
    return {"horizons": horizons, "auc_global": [auc[("panel_global", h)] for h in horizons], "auc_baseline": [auc[("panel_baseline", h)] for h in horizons],
            "win_global": [100 * win[("panel_global", h)][0] for h in horizons], "win_baseline": [100 * win[("panel_baseline", h)][0] for h in horizons],
            "spearman": [spearman[h] for h in horizons], "panels": panels}


def hot_numbers(db_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    import hot_events_forward_check as fc
    import pandas as pd
    frame = fc.load(db_path)
    points = he.score_pct(frame, he.DEFAULT_RULES, he.DEFAULT_WEIGHTS)
    share = {c: 100.0 * float((points >= c).mean()) for c in set(he.DEFAULT_CUTS_PCT.values())}
    lines = [ln for ln in open(REPORTS / "hot_events_forward_check.csv", encoding="utf-8") if not ln.startswith("#")]
    split = [i for i, ln in enumerate(lines) if ln.startswith("horizon")][1]
    aucs = list(csv.DictReader(lines[:split]))
    levels = list(csv.DictReader(lines[split:]))
    pick = lambda score: next(r for r in aucs if r["horizon"] == "1h" and r["period"] == "all" and r["score"] == score)
    hold = next(r for r in aucs if r["horizon"] == "1h" and r["period"] == "holdout" and r["score"] == "all KPIs")
    ladder = [{"level": r["level"], "n": int(r["n"]), "move": float(r["move"]), "big": 100 * float(r["big"]), "hit": 100 * float(r["hit"])}
              for r in levels if r["horizon"] == "1h" and r["period"] == "all"]
    return {"kpis": [{"key": k, "label": label, "threshold": t} for k, label, t, _ in he.METRICS], "cuts": he.DEFAULT_CUTS_PCT, "ladder": ladder,
            "auc_all": float(pick("all KPIs")["auc"]), "auc_reddit": float(pick("Reddit KPIs only")["auc"]), "auc_price": float(pick("price KPIs only")["auc"]),
            "auc_holdout": float(hold["auc"]), "n": int(pick("all KPIs")["n"]), "top_share": he.TOP_SHARE,
            "rows": len(frame), "share_reaching": share}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default=str(DEFAULT_DB))
    args = ap.parse_args()
    db = sqlite3.connect("file:%s?mode=ro" % Path(args.db).resolve(), uri=True)
    try:
        r, m, s, a = reddit_numbers(db), market_numbers(db), sentiment_numbers(), analysis_numbers(db)
    finally:
        db.close()
    h = hot_numbers(args.db)
    OUT_JSON.write_text(json.dumps({"reddit": r, "market": m, "sentiment": s, "analysis": a, "hot": h}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", OUT_JSON)


if __name__ == "__main__":
    main()
