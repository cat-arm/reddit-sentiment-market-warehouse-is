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
  t10_rule_validation_sample the stratified sample of the rule validation (7.3 step 5) with the label counts, no Reddit texts
  t11_rule_validation_examples one example row per rule group (scores and label, no text)

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
MODEL_TH = {"vader": "VADER", "finbert": "FinBERT", "final": "ผลสุดท้าย"}
LABEL_TH = {"positive": "เชิงบวก", "neutral": "เป็นกลาง", "negative": "เชิงลบ"}
METHOD_TH = {"same_direction": "ทั้งสองตัวเห็นตรงกัน คะแนนต่างกันไม่เกิน 0.50 ใช้ค่าเฉลี่ย",
             "same_direction_far": "ทั้งสองตัวเห็นตรงกัน แต่คะแนนต่างกันเกิน 0.50 ใช้ค่าที่ใกล้ศูนย์กว่า",
             "both_neutral": "ทั้งสองตัวเป็นกลาง ใช้ค่าเฉลี่ย",
             "small_conflict_rule_agrees": "ตัวหนึ่งเป็นกลาง อีกตัวมีทิศทาง คำสำคัญตรงกับทิศทางนั้น ใช้คะแนนของตัวที่มีทิศทาง",
             "small_conflict_rule_clash": "ตัวหนึ่งเป็นกลาง อีกตัวมีทิศทาง คำสำคัญขัดแย้งหรือผสม กำหนดเป็น 0",
             "small_conflict_no_rule": "ตัวหนึ่งเป็นกลาง อีกตัวมีทิศทาง ไม่มีคำสำคัญ ใช้คะแนนของตัวที่มีทิศทาง",
             "hard_conflict_rule": "ทิศตรงข้ามกัน มีคำสำคัญ ใช้คะแนนของตัวที่ตรงกับคำสำคัญ",
             "hard_conflict_no_rule": "ทิศตรงข้ามกัน ไม่มีคำสำคัญ กำหนดเป็น 0",
             "hard_conflict_mixed_zero": "ทิศตรงข้ามกัน คำสำคัญเป็นสัญญาณผสม กำหนดเป็น 0"}


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


VALIDATION = ROOT / "output" / "reports" / "rule_validation"
STRATA_ORDER = ["same_direction", "same_direction_far", "both_neutral", "small_conflict_keyword", "small_conflict_no_keyword",
                "hard_conflict_keyword", "hard_conflict_no_keyword"]
SPLIT_TH = {"tune": "ชุดปรับกฎ", "test": "ชุดทดสอบ"}
SIGNAL_TH = {"positive": "เชิงบวก", "negative": "เชิงลบ", "mixed": "ผสม", "none": "ไม่พบ"}


def rule_validation_sample():
    """t10 / t11: the stratified sample of the rule validation (proposal 7.3 step 5) WITHOUT the Reddit texts.
    Reads the key and the labels the developer filled in; skipped when those files are not there."""
    key_path, sheet_path = VALIDATION / "sample_key.csv", VALIDATION / "labeling_sheet.csv"
    if not (key_path.exists() and sheet_path.exists()):
        print("skip   t10/t11: no sample in", VALIDATION)
        return
    key = pd.read_csv(key_path)
    labels = pd.read_csv(sheet_path, encoding="utf-8-sig", usecols=["sample_id", "human_label"])      # the texts are never read
    sample = key.merge(labels, on="sample_id")
    sample["label"] = sample.human_label.str.strip().str.lower().map(LABEL_TH)
    sample["stratum"] = pd.Categorical(sample.stratum, STRATA_ORDER, ordered=True)
    sizes = sample.groupby("stratum", observed=True).agg(population=("stratum_population", "first"), n=("sample_id", "size"),
                                                         tune=("split", lambda s: int((s == "tune").sum())), test=("split", lambda s: int((s == "test").sum())))
    counts = pd.crosstab(sample.stratum, sample.label).reindex(columns=list(LABEL_TH.values()), fill_value=0)
    t10 = sizes.join(counts).reset_index()
    t10.loc[len(t10)] = ["รวม", int(t10.population.sum()), int(t10.n.sum()), int(t10.tune.sum()), int(t10.test.sum()),
                         *[int(t10[c].sum()) for c in LABEL_TH.values()]]
    save("t10_rule_validation_sample", t10.rename(columns={
        "stratum": "กลุ่มกฎ", "population": "จำนวนข้อความทั้งหมดของกลุ่ม", "n": "จำนวนตัวอย่าง", "tune": "ชุดปรับกฎ", "test": "ชุดทดสอบ"}),
         "ตัวอย่างที่สุ่มเพื่อตรวจกฎรวมผล แยกตามกลุ่มกฎ พร้อมจำนวนป้ายความรู้สึกที่ผู้พัฒนาติด (ไม่มีข้อความ Reddit)",
         "output/reports/rule_validation/sample_key.csv + labeling_sheet.csv (อ่านเฉพาะป้าย)")
    first = sample.sort_values("sample_id").groupby("stratum", observed=True).head(1).sort_values("stratum")
    example = pd.DataFrame({"รหัสตัวอย่าง": first.sample_id, "ชุด": first.split.map(SPLIT_TH), "กลุ่มกฎ": first.stratum.astype(str),
                            "คะแนน VADER": first.vader_score.round(3), "คะแนน FinBERT": first.finbert_score.round(3),
                            "คำสำคัญ": first.rule_signal.map(SIGNAL_TH), "คะแนนสุดท้าย": first.final_sentiment.round(3),
                            "ป้ายผู้พัฒนา": first.label})
    save("t11_rule_validation_examples", example, "ตัวอย่างข้อมูลที่สุ่มได้กลุ่มละ 1 รายการ (คะแนนและป้าย ไม่มีข้อความ Reddit)",
         "output/reports/rule_validation/sample_key.csv + labeling_sheet.csv (อ่านเฉพาะป้าย)")


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
    save("t2_sentiment_distribution", dist.assign(model=dist.model.map(MODEL_TH), label=dist.label.map(LABEL_TH)).rename(columns={
        "model": "วิธี", "label": "ประเภทความรู้สึก", "n": "จำนวนข้อความ", "share_pct": "ร้อยละ"}),
         "จำนวนและสัดส่วนความรู้สึกเชิงบวก เป็นกลาง และเชิงลบ ของ VADER, FinBERT และผลสุดท้าย (เกณฑ์ ±0.05)")
    method = sql("SELECT final_method, COUNT(*) AS n, SUM(is_ambiguous) AS ambiguous FROM sentiment_item GROUP BY 1 ORDER BY 2 DESC")
    method["share_pct"] = (100.0 * method.n / method.n.sum()).round(2)
    method.insert(1, "คำอธิบายกฎ", method.final_method.map(METHOD_TH))
    save("t3_final_method", method.rename(columns={"final_method": "กฎที่ใช้ (final_method)", "n": "จำนวนข้อความ",
                                                   "ambiguous": "จำนวนที่ตัดสินไม่ได้ (is_ambiguous = 1)", "share_pct": "ร้อยละ"}),
         "จำนวนข้อความแยกตามกฎที่ใช้รวมผล VADER และ FinBERT (final_method) และจำนวนที่ระบบตัดสินไม่ได้")

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

    rule_validation_sample()

    # ---------------- figures
    def f_dist(plt):
        fig, ax = plt.subplots(figsize=(8, 3.8))
        piv = dist.pivot(index="model", columns="label", values="share_pct").reindex(["vader", "finbert", "final"])[["positive", "neutral", "negative"]]
        piv = piv.rename(index=MODEL_TH, columns=LABEL_TH)
        piv.plot.barh(stacked=True, ax=ax, color=["#1a9850", "#bdbdbd", "#b2182b"])
        for bar_group in ax.containers:                                  # the share in % on every part of a bar
            ax.bar_label(bar_group, fmt="%.1f%%", label_type="center", fontsize=9, color="black")
        ax.set_xlabel("ร้อยละของข้อความ (เกณฑ์ความรู้สึกเป็นกลาง ±0.05)")
        ax.set_ylabel("")
        ax.set_xlim(0, 100)
        ax.invert_yaxis()                                                 # VADER on top, the final result at the bottom
        ax.set_title("สัดส่วนประเภทความรู้สึกของแต่ละวิธี (22 ล้านข้อความ)")
        ax.legend(title="ประเภทความรู้สึก", loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=3, frameon=False)
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
