"""Dashboard testing (proposal 8.4 part 3): every number the dashboard data layer returns is compared with an
independent SQL query on the database (a different table or a different way of counting where possible).

Checked for 2 time windows x 4 tickers (one per asset class + the most talked-about stock): Reddit volume,
Z-score, mention count and Ticker Mention Rate, price / Current Return, Normalized ATR, future return by group,
sentiment ranking, win rate / correlation ranking, signal counts, home-page headline numbers.
Read-only.  Exit code 1 if any check fails.

Usage:  python scripts/dashboard_kpi_check.py [--db output/reddit.sqlite3]
Output: output/reports/dashboard_kpi_check.md
"""
import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np                                                    # noqa: E402

from dashboard import data                                            # noqa: E402
from etl.common import DEFAULT_DB, file_header                        # noqa: E402

OUT = ROOT / "output" / "reports" / "dashboard_kpi_check.md"
TICKERS = ("BTC-USD", "TSLA", "GC=F", "SPY")
DAY = 86400


class Checker:
    def __init__(self, db_path):
        self.db_path = db_path
        self.db = sqlite3.connect("file:%s?mode=ro" % Path(db_path).resolve().as_posix(), uri=True)
        self.rows = []

    def q(self, sql, params=()):
        return self.db.execute(sql, params).fetchall()

    def check(self, page, what, shown, expected, tol=1e-9):
        shown = None if shown is None or (isinstance(shown, float) and np.isnan(shown)) else shown
        expected = None if expected is None or (isinstance(expected, float) and np.isnan(expected)) else expected
        if shown is None or expected is None:
            ok = shown is None and expected is None
        else:
            ok = abs(float(shown) - float(expected)) <= tol * max(1.0, abs(float(expected)))
        self.rows.append((page, what, shown, expected, ok))


def run(db_path):
    c = Checker(db_path)
    hi = c.q("SELECT MAX(hour_utc) FROM reddit_hourly WHERE variant='all' AND ticker='ALL'")[0][0]
    windows = {"30 วันล่าสุดของ Reddit": (hi - 30 * DAY, hi), "ช่วงกลาง (2025-03-01..2025-03-31)": (1740787200, 1743379200)}
    for wname, (start, end) in windows.items():
        # --- page 1: Reddit Volume (totals) ---
        tot = data.total_volume_series(db_path, start, end)
        n_raw = c.q("SELECT COUNT(*) FROM filtered_text WHERE created_utc >= ? AND created_utc < ?", (start, end + 3600))[0][0]
        c.check("1 Reddit Volume", "%s: รวมข้อความ (กราฟ) = นับตรงจาก filtered_text" % wname, int(tot.texts.sum()), n_raw)
        c.check("1 Reddit Volume", "%s: Post + Comment = รวม" % wname, int(tot.posts.sum() + tot.comments.sum()), int(tot.texts.sum()))
        by_src = data.total_volume_by_source(db_path, start, end)
        c.check("1 Reddit Volume", "%s: รวมต่อชุมชน = รวมทั้งหมด" % wname, int(by_src.texts.sum()), int(tot.texts.sum()))
        # --- page 2: ticker mentions ---
        rank = data.mention_ranking(db_path, start, end)
        for tk in TICKERS:
            row = rank[rank.ticker == tk].iloc[0]
            ment = c.q("SELECT COALESCE(SUM(m.mention_count), 0) FROM ticker_mentions m JOIN filtered_text p ON p.src_rowid = m.src_rowid "
                       "WHERE m.ticker = ? AND p.created_utc >= ? AND p.created_utc < ?", (tk, start, end + 3600))[0][0]
            c.check("2 Ticker Mentions", "%s %s: Ticker_mention_count" % (wname, tk), int(row.mentions), ment)
            c.check("2 Ticker Mentions", "%s %s: Ticker Mention Rate (%%)" % (wname, tk), row.mention_rate_pct, 100.0 * ment / n_raw)
    # --- per ticker pages ---
    for wname, (start, end) in windows.items():
        for tk in TICKERS:
            vol = data.volume_series(db_path, tk, start, end)
            exp = c.q("SELECT COALESCE(SUM(reddit_volume), 0) FROM reddit_hourly WHERE variant='all' AND ticker=? AND hour_utc BETWEEN ? AND ?", (tk, start, end))[0][0]
            c.check("1 Reddit Volume", "%s %s: ข้อความที่พูดถึง (กราฟ) = reddit_hourly ที่มีราคา" % (wname, tk), int(vol.reddit_volume.sum()), exp)
            px = data.price_series(db_path, tk, start, end)
            e = c.q("SELECT COUNT(*), AVG(close), AVG(log_return), AVG(normalized_atr), AVG(future_return_3h), AVG(rsi) FROM market_hourly_features "
                    "WHERE ticker = ? AND CAST(strftime('%s', hour_bucket) AS INTEGER) BETWEEN ? AND ?", (tk, start, end))[0]
            for label, shown, expected in (("จำนวนแท่ง", len(px), e[0]), ("close เฉลี่ย", px.close.mean(), e[1]),
                                           ("Current Return เฉลี่ย", px.log_return.mean(), e[2]),
                                           ("Normalized ATR เฉลี่ย", px.normalized_atr.mean(), e[3]),
                                           ("Future Return 3h เฉลี่ย", px.future_return_3h.mean(), e[4]), ("RSI เฉลี่ย", px.rsi.mean(), e[5])):
                c.check("3 Price and Return", "%s %s: %s" % (wname, tk, label), shown, expected, 1e-7)
            ov = data.overview_series(db_path, tk, start, end)
            e = c.q("SELECT AVG(r.sentiment_mean), COUNT(r.sentiment_mean), AVG(r.pos_ratio) FROM reddit_hourly r JOIN market_hourly_features m ON m.ticker = r.ticker AND CAST(strftime('%s', m.hour_bucket) AS INTEGER) = r.hour_utc WHERE r.variant='all' AND r.ticker=? AND r.hour_utc BETWEEN ? AND ?", (tk, start, end))[0]
            c.check("4 Market and Sentiment", "%s %s: Sentiment Score เฉลี่ย (กราฟ) = reddit_hourly ที่มีราคา" % (wname, tk), ov.sentiment_mean.mean(), e[0], 1e-7)
            c.check("4 Market and Sentiment", "%s %s: จำนวนชั่วโมงที่มีความรู้สึก" % (wname, tk), int(ov.sentiment_mean.notna().sum()), e[1])
    for wname, (start, end) in windows.items():
        # group level numbers recomputed with pandas from the raw feature table
        import pandas as pd
        feat = pd.read_sql_query("SELECT m.ticker, k.AssetClass AS g, m.normalized_atr, m.future_return_1h, m.future_return_6h FROM market_hourly_features m "
                                 "JOIN DimTicker k ON k.TickerSymbol = m.ticker WHERE CAST(strftime('%s', m.hour_bucket) AS INTEGER) BETWEEN ? AND ?",
                                 c.db, params=(start, end))
        risk = data.group_risk(db_path, start, end).set_index("big_group")
        for g, part in feat.groupby("g"):
            c.check("3 Price and Return", "%s %s: Normalized ATR เฉลี่ยของกลุ่ม" % (wname, g), risk.loc[g, "mean_normalized_atr_pct"], part.normalized_atr.mean(), 1e-7)
        fr = data.future_return_by_group(db_path, start, end)
        for g, part in feat.groupby("g"):
            for h, col in (("1h", "future_return_1h"), ("6h", "future_return_6h")):
                shown = fr[(fr.big_group == g) & (fr.horizon == h)].iloc[0]
                c.check("3 Price and Return", "%s %s: Future Return %s เฉลี่ย" % (wname, g, h), shown.mean_return_pct, part[col].mean(), 1e-7)
                up = part[col][part[col] != 0].dropna()
                c.check("3 Price and Return", "%s %s: สัดส่วนขึ้น %s" % (wname, g, h), shown.share_up, (up > 0).mean() if len(up) else None, 1e-7)
        sent = data.sentiment_by_ticker(db_path, start, end).set_index("ticker")
        for tk in TICKERS:
            e = c.q("SELECT AVG(r.sentiment_mean) FROM reddit_hourly r JOIN market_hourly_features m ON m.ticker = r.ticker AND CAST(strftime('%s', m.hour_bucket) AS INTEGER) = r.hour_utc WHERE r.variant='all' AND r.ticker=? AND r.hour_utc BETWEEN ? AND ?", (tk, start, end))[0][0]
            c.check("4 Market and Sentiment", "%s %s: อันดับความรู้สึก (เฉลี่ย)" % (wname, tk), sent.loc[tk, "mean_sentiment"] if tk in sent.index else None, e, 1e-7)
    # --- page 5: ranking, signals, home page ---
    rk = data.ranking_table(db_path)
    for tk in TICKERS:
        for h in ("1h", "6h"):
            e = c.q("SELECT metric_value * 100.0 FROM analysis_results WHERE analysis='winrate' AND panel_name='panel_Ticker' AND level='ticker' AND ticker=? "
                    "AND horizon=? AND predictor='sign(sentiment_mean)' AND metric_name='winrate'", (tk, h))
            shown = rk[(rk.ticker == tk) & (rk.horizon == h)].winrate
            c.check("5 Ranking and Signals", "%s %s: Historical Win Rate (%%)" % (tk, h), shown.iloc[0] if len(shown) else None, e[0][0] if e else None, 1e-9)
            e = c.q("SELECT metric_value FROM analysis_results WHERE analysis='correlation' AND panel_name='panel_Ticker' AND level='ticker' AND ticker=? "
                    "AND horizon=? AND predictor='sentiment_mean' AND metric_name='spearman'", (tk, h))
            shown = rk[(rk.ticker == tk) & (rk.horizon == h)].correlation
            c.check("5 Ranking and Signals", "%s %s: Spearman" % (tk, h), shown.iloc[0] if len(shown) else None, e[0][0] if e else None, 1e-9)
    sc = data.signal_counts(db_path)
    for z, s in ((1.5, 0.3), (2.0, 0.05), (2.5, 0.3)):
        e = c.q("SELECT COUNT(*) FROM signal_events WHERE z_threshold=? AND s_threshold=?", (z, s))[0][0]
        part = sc[(sc.z_threshold == z) & (sc.s_threshold == s)]
        c.check("5 Ranking and Signals", "จำนวนสัญญาณ z>%.1f, |s|>=%.2f" % (z, s), int(part.n_signals.sum()), e)
    # View v_signal_list (table 18) keeps one row per signal x horizon
    e = c.q("SELECT COUNT(*) FROM signal_events")[0][0]
    c.check("5 Ranking and Signals", "v_signal_list = signal_events x 5 horizon", c.q("SELECT COUNT(*) FROM v_signal_list")[0][0], e * 5)
    oc = data.overview_counts(db_path)
    c.check("หน้าแรก", "ข้อความที่มีคะแนน", int(oc.texts_scored), c.q("SELECT COUNT(*) FROM filtered_text")[0][0])
    c.check("หน้าแรก", "FactMarketSentiment แถว", int(oc.fact_rows), c.q("SELECT COUNT(*) FROM FactMarketSentiment")[0][0])
    c.check("หน้าแรก", "จำนวน ticker", int(oc.tickers), 34)
    c.db.close()
    return c.rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args(argv)
    rows = run(args.db)
    failed = [r for r in rows if not r[4]]
    lines = ["# ทดสอบ Dashboard: ตัวเลขบนหน้าจอเทียบ SQL ตรง (proposal 8.4 ส่วนที่ 3)", "",
             *file_header("เทียบตัวเลขที่ชั้นข้อมูลของ dashboard ส่งให้แต่ละหน้า กับ SQL อิสระบนฐานข้อมูล (4 สินทรัพย์ × 2 ช่วงเวลา)",
                          "scripts/dashboard_kpi_check.py", "python steps/30_dashboard_kpi_check.py", "output/reddit.sqlite3 อ่านอย่างเดียว"), "",
             "ผ่าน %d จาก %d ข้อ" % (len(rows) - len(failed), len(rows)), "",
             "| หน้า | ข้อตรวจ | ที่ dashboard แสดง | SQL ตรง | ผล |", "|---|---|---|---|---|"]
    for page, what, shown, expected, ok in rows:
        fmt = lambda v: "-" if v is None else ("%.6g" % v if isinstance(v, float) else "{:,}".format(v) if isinstance(v, int) else str(v))
        lines.append("| %s | %s | %s | %s | %s |" % (page, what, fmt(shown), fmt(expected), "ผ่าน" if ok else "**ไม่ผ่าน**"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("ผ่าน %d จาก %d ข้อ -> %s" % (len(rows) - len(failed), len(rows), OUT))
    for r in failed:
        print("FAIL", r)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
