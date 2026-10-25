"""Tables and figures for the thesis book, all computed from the database (read-only) so every number can be rebuilt.

Tables  -> output/tables/*.csv   (each starts with a '#' header: what it is, when, script, rerun command)
Figures -> output/figures/book_*.png

  t1_data_funnel            raw rows -> readable -> cleaned -> passed quality filter, with the removed reasons
  t2_sentiment_distribution VADER / FinBERT / final positive-neutral-negative counts and shares
  t3_final_method           how the final sentiment was resolved (conflict-resolution cases)
  t4_ticker_mentions        texts and mentions per ticker
  t5_future_return_coverage share of price bars with a computable future return per asset class and horizon
  t6_panel_overview         rows, tickers and mean texts per row for the 9 panels
  t7_panel_results          per panel: cells with BH p < 0.05 (Spearman, win rate), mean win rate, mean AUC
  t8_asset_class_results    pooled win rate / Spearman / AUC per asset class and horizon (panel_Ticker)
  t9_signal_counts          detected signals per configuration and type

Usage:  python scripts/make_book_tables.py [--db output/reddit.sqlite3]
"""
import argparse
import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd                                                   # noqa: E402

from analysis import figure_style                                     # noqa: E402
from etl.common import DEFAULT_DB, file_header, subreddits            # noqa: E402

TABLES = ROOT / "output" / "tables"
FIGURES = ROOT / "output" / "figures"
RERUN = "python steps/31_make_book_tables.py"
HORIZONS = ("1h", "2h", "3h", "6h", "12h")


def save(name, frame, what, sources="output/reddit.sqlite3 อ่านอย่างเดียว"):
    TABLES.mkdir(parents=True, exist_ok=True)
    path = TABLES / (name + ".csv")
    with path.open("w", newline="", encoding="utf-8") as sink:
        sink.write("\n".join(file_header(what, "scripts/make_book_tables.py", RERUN, sources, comment=True)) + "\n")
        frame.to_csv(sink, index=False, lineterminator="\n")
    print("table  ", path.name, len(frame), "rows")


def figure(name, build):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figure_style.use_thai_font()
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig = build(plt)
    fig.tight_layout()
    fig.savefig(FIGURES / name, dpi=150)
    plt.close(fig)
    print("figure ", name)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args(argv)
    db = sqlite3.connect("file:%s?mode=ro" % Path(args.db).resolve().as_posix(), uri=True)
    sql = lambda text, params=(): pd.read_sql_query(text, db, params=params)

    marks = ",".join("?" * len(subreddits()))
    raw = sql("SELECT text_status AS status, COUNT(*) AS n FROM reddit_content WHERE subreddit IN (%s) GROUP BY 1 ORDER BY 2 DESC" % marks, tuple(subreddits()))
    reasons = sql("SELECT reason AS status, COUNT(*) AS n FROM text_filter GROUP BY 1 ORDER BY 2 DESC")
    funnel = pd.concat([raw.assign(step="1 ข้อมูลดิบ 6 ชุมชน (ตามสถานะ)"), pd.DataFrame([
        {"step": "2 ล้างข้อความแล้ว (processed_text)", "status": "written", "n": sql("SELECT COUNT(*) n FROM processed_text").n[0]},
        {"step": "4 ผ่านตัวกรองคุณภาพ (filtered_text)", "status": "passed", "n": sql("SELECT COUNT(*) n FROM filtered_text").n[0]}]),
        reasons.assign(step="3 ถูกตัดที่ตัวกรองคุณภาพ (ตามเหตุผล)")], ignore_index=True)
    save("t1_data_funnel", funnel[["step", "status", "n"]], "ข้อความ Reddit จากข้อมูลดิบถึงข้อความที่ใช้วิเคราะห์ พร้อมเหตุผลที่ถูกตัด")

    dist = []
    for model in ("vader", "finbert", "final"):
        frame = sql("SELECT %s_status AS label, COUNT(*) AS n FROM sentiment_item GROUP BY 1" % model)
        frame["model"] = model
        frame["share_pct"] = (100.0 * frame.n / frame.n.sum()).round(2)
        dist.append(frame)
    dist = pd.concat(dist)[["model", "label", "n", "share_pct"]]
    save("t2_sentiment_distribution", dist, "จำนวนและสัดส่วน positive/neutral/negative ของ VADER, FinBERT และผลสุดท้าย (เกณฑ์ ±0.05)")
    method = sql("SELECT final_method, COUNT(*) AS n, SUM(is_ambiguous) AS ambiguous FROM sentiment_item GROUP BY 1 ORDER BY 2 DESC")
    method["share_pct"] = (100.0 * method.n / method.n.sum()).round(2)
    save("t3_final_method", method, "จำนวนข้อความแยกตามกฎที่ใช้รวมผล VADER+FinBERT (final_method) และจำนวนที่กำกวม")

    mentions = sql("SELECT m.ticker, k.AssetClass AS big_group, COUNT(DISTINCT m.src_rowid) AS texts, SUM(m.mention_count) AS mentions "
                   "FROM ticker_mentions m JOIN DimTicker k ON k.TickerSymbol = m.ticker GROUP BY m.ticker ORDER BY texts DESC")
    save("t4_ticker_mentions", mentions, "จำนวนข้อความที่พูดถึงและจำนวนการกล่าวถึงของแต่ละสินทรัพย์ (34 ตัว)")

    cov = sql("SELECT k.AssetClass AS big_group, COUNT(*) AS bars, " + ", ".join(
        "ROUND(100.0 * COUNT(m.future_return_%s) / COUNT(*), 1) AS pct_%s" % (h, h) for h in HORIZONS) +
              " FROM market_hourly_features m JOIN DimTicker k ON k.TickerSymbol = m.ticker GROUP BY k.AssetClass")
    save("t5_future_return_coverage", cov, "ร้อยละของแท่งราคาที่คำนวณ Future Return ได้ แยกกลุ่มสินทรัพย์และกรอบเวลา (หุ้น/ETF 12 ชม. = 0)")

    over = sql("SELECT panel_name, COUNT(*) AS rows, COUNT(DISTINCT ticker) AS tickers, ROUND(AVG(reddit_volume), 1) AS mean_texts_per_row, "
               "ROUND(AVG(sentiment_mean), 4) AS mean_sentiment FROM panels GROUP BY 1 ORDER BY 1")
    save("t6_panel_overview", over, "จำนวนแถวและค่าเฉลี่ยของ 9 panel (ตารางที่ 12 ของ proposal)")

    res = sql("""
        SELECT panel_name,
               SUM(metric_name = 'spearman' AND p_value_bh < 0.05) AS spearman_sig_cells,
               SUM(metric_name = 'spearman' AND status = 'ok') AS spearman_cells,
               SUM(metric_name = 'winrate' AND p_value_bh < 0.05) AS winrate_sig_cells,
               SUM(metric_name = 'winrate' AND status = 'ok') AS winrate_cells,
               ROUND(100 * AVG(CASE WHEN metric_name = 'winrate' AND status = 'ok' THEN metric_value END), 2) AS mean_winrate_pct,
               ROUND(AVG(CASE WHEN metric_name = 'auc' AND status = 'ok' THEN metric_value END), 4) AS mean_auc
        FROM analysis_results
        WHERE (level = 'ticker' AND metric_name IN ('spearman', 'winrate') AND horizon != 'log_return'
               AND predictor IN ('sentiment_mean', 'sign(sentiment_mean)', 'random_direction'))
           OR metric_name = 'auc'
        GROUP BY panel_name ORDER BY panel_name""")
    save("t7_panel_results", res, "ผลหลักของทุก panel: จำนวนเซลล์ (สินทรัพย์ × กรอบเวลา) ที่มีนัยสำคัญหลังปรับ BH, win rate เฉลี่ย, AUC เฉลี่ย")

    asset = sql("""
        SELECT a.big_group, a.horizon, ROUND(100 * a.metric_value, 2) AS winrate_pct, a.n_samples AS winrate_n,
               ROUND(s.metric_value, 4) AS spearman, s.n_samples AS spearman_n, ROUND(u.metric_value, 4) AS auc
        FROM analysis_results a
        LEFT JOIN analysis_results s ON s.analysis = 'correlation' AND s.panel_name = a.panel_name AND s.level = 'big_group'
             AND s.big_group = a.big_group AND s.horizon = a.horizon AND s.predictor = 'sentiment_mean' AND s.metric_name = 'spearman'
        LEFT JOIN analysis_results u ON u.metric_name = 'auc' AND u.panel_name = a.panel_name AND u.big_group = a.big_group AND u.horizon = a.horizon
        WHERE a.analysis = 'winrate' AND a.panel_name = 'panel_Ticker' AND a.level = 'big_group' AND a.metric_name = 'winrate'
          AND a.predictor = 'sign(sentiment_mean)' AND a.status = 'ok'
        ORDER BY a.big_group, a.horizon""")
    save("t8_asset_class_results", asset, "ผล panel_Ticker รวมแต่ละกลุ่มสินทรัพย์: win rate, Spearman, AUC ตามกรอบเวลา (ช่องว่าง = ข้อมูลไม่พอ)")
    sig = sql("SELECT z_threshold, s_threshold, signal_type, SUM(n_signals) AS n_signals FROM signal_summary GROUP BY 1, 2, 3 ORDER BY 1, 2, 3")
    save("t9_signal_counts", sig, "จำนวนสัญญาณเชิงข้อมูลที่ตรวจพบ แยกชุดเกณฑ์และประเภทสัญญาณ")

    # ---------------- figures
    def f_dist(plt):
        fig, ax = plt.subplots(figsize=(7, 3.6))
        piv = dist.pivot(index="model", columns="label", values="share_pct").reindex(["vader", "finbert", "final"])[["positive", "neutral", "negative"]]
        piv.plot.barh(stacked=True, ax=ax, color=["#1a9850", "#bdbdbd", "#b2182b"])
        ax.set_xlabel("ร้อยละของข้อความ (เกณฑ์ neutral ±0.05)")
        ax.set_ylabel("")
        ax.set_title("สัดส่วนความรู้สึกของแต่ละวิธี (22 ล้านข้อความ)")
        return fig
    figure("book_sentiment_distribution.png", f_dist)

    month = sql("SELECT strftime('%Y-%m', created_utc, 'unixepoch') AS month, subreddit, COUNT(*) AS n FROM filtered_text GROUP BY 1, 2")

    def f_month(plt):
        fig, ax = plt.subplots(figsize=(10, 3.8))
        month.pivot(index="month", columns="subreddit", values="n").fillna(0).plot.bar(stacked=True, ax=ax, width=0.85)
        ax.set_ylabel("จำนวนข้อความ")
        ax.set_xlabel("")
        ax.set_title("ข้อความ Reddit ที่ใช้วิเคราะห์ต่อเดือน แยกชุมชน")
        return fig
    figure("book_texts_per_month.png", f_month)

    def f_cov(plt):
        fig, ax = plt.subplots(figsize=(7, 3.6))
        cov.set_index("big_group")[["pct_" + h for h in HORIZONS]].rename(columns=lambda c: c[4:]).plot.bar(ax=ax, rot=0)
        ax.set_ylabel("% ของแท่งราคาที่คำนวณได้")
        ax.set_xlabel("")
        ax.set_title("Future Return ที่คำนวณได้ ตามกลุ่มสินทรัพย์และกรอบเวลา")
        return fig
    figure("book_future_return_coverage.png", f_cov)

    def f_win(plt):
        fig, ax = plt.subplots(figsize=(8, 4))
        frame = res.set_index("panel_name").mean_winrate_pct
        colors = ["#7f7f7f" if p == "panel_baseline" else "#2b6cb0" for p in frame.index]
        ax.barh(frame.index, frame.values - 50, left=50, color=colors)
        ax.axvline(50, color="black", lw=1)
        ax.set_xlim(48, 52)
        ax.set_xlabel("win rate เฉลี่ย (%) — 50% = เดาทิศสุ่ม, แท่งเทา = baseline")
        ax.set_title("Win rate เฉลี่ยของทุก panel (ทุกสินทรัพย์ × ทุกกรอบเวลา)")
        return fig
    figure("book_panel_winrate.png", f_win)

    def f_ment(plt):
        fig, ax = plt.subplots(figsize=(8, 6))
        top = mentions.head(20).iloc[::-1]
        ax.barh(top.ticker, top.texts, color="#2b6cb0")
        ax.set_xlabel("จำนวนข้อความที่พูดถึง")
        ax.set_title("20 สินทรัพย์ที่ถูกพูดถึงมากที่สุด")
        return fig
    figure("book_top_mentions.png", f_ment)
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
