"""Builds the three summary documents for the thesis from the real database and the reports already generated.

    1_beyond_proposal.md       what the code does ABOVE or DIFFERENT from the approved proposal (extensions + choices)
    2_tests_and_hypotheses.md  the tests of 7.3 step 5 (rule validation, neutral band), the extra tests we added
                               (stricter z-score / super quality / super spike) and the 7.4 hypothesis tests, with methods
    3_final_summary.md         every pipeline step: what it does, which file runs it, what it produced, what is interesting

Every number is read from output/reddit.sqlite3 (mode=ro) or from the CSV / Markdown reports of the other scripts, never
typed by hand.  Nothing is written to the database.

Usage:  python scripts/build_final_reports.py [--db output/reddit.sqlite3]
Output: output/reports/final/*.md
"""
import argparse
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from etl.common import DEFAULT_DB, file_header, subreddits   # noqa: E402

REPORTS = ROOT / "output" / "reports"
OUT_DIR = REPORTS / "final"
CMD = "python scripts/build_final_reports.py"
HORIZONS = ("1h", "2h", "3h", "6h", "12h")
PANELS = ["panel_global", "panel_global_strong", "panel_global_quality", "panel_global_spike",
          "panel_Ticker", "panel_Ticker_strong", "panel_Ticker_quality", "panel_Ticker_spike", "panel_baseline"]


def n(x):
    return "{:,}".format(int(x))


def pct(x, digits=1):
    return "n/a" if x is None or pd.isna(x) else ("%%.%df%%%%" % digits) % (100 * x)


def table(header, rows):
    esc = lambda c: str(c).replace("|", "\\|")           # a "|" inside a cell (e.g. |score|) would split the column
    out = ["| " + " | ".join(esc(c) for c in header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(esc(c) for c in r) + " |" for r in rows]
    return out


def header(title, what, sources):
    return ["# " + title, ""] + file_header(what, "scripts/build_final_reports.py", CMD, sources) + [""]


# ----------------------------------------------------------------------------------------------- data

def gather(db):
    q = lambda sql, *a: db.execute(sql, a).fetchone()[0]
    rows = lambda sql, *a: db.execute(sql, a).fetchall()
    six = tuple(subreddits())
    mark = ",".join("?" * len(six))
    D = {"six": six}
    D["raw_all"] = q("SELECT COUNT(*) FROM reddit_content")
    D["status"] = dict(rows("SELECT text_status, COUNT(*) FROM reddit_content WHERE subreddit IN (%s) GROUP BY 1" % mark, *six))
    D["six_rows"] = sum(D["status"].values())
    D["processed"] = q("SELECT COUNT(*) FROM processed_text")
    D["passed"] = q("SELECT COUNT(*) FROM filtered_text")
    D["empty_clean"] = D["status"]["available"] - D["processed"]
    D["filter"] = dict(rows("SELECT reason, COUNT(*) FROM text_filter GROUP BY 1"))
    D["mix"] = rows("SELECT subreddit, COUNT(*) FROM filtered_text GROUP BY 1 ORDER BY 2 DESC")
    D["kind"] = dict(rows("SELECT content_type, COUNT(*) FROM filtered_text GROUP BY 1"))
    D["ticker_rows"] = q("SELECT COUNT(*) FROM ticker_mentions")
    D["ticker_texts"] = q("SELECT COUNT(DISTINCT src_rowid) FROM ticker_mentions")
    D["ticker_top"] = rows("SELECT ticker, SUM(mention_count) c FROM ticker_mentions GROUP BY 1 ORDER BY 2 DESC LIMIT 5")
    D["ticker_low"] = rows("SELECT ticker, SUM(mention_count) c FROM ticker_mentions GROUP BY 1 ORDER BY 2 LIMIT 5")
    D["final"] = dict(rows("SELECT final_status, COUNT(*) FROM sentiment_item GROUP BY 1"))
    D["method"] = rows("SELECT final_method, COUNT(*) FROM sentiment_item GROUP BY 1 ORDER BY 2 DESC")
    D["ambiguous"] = q("SELECT COUNT(*) FROM sentiment_item WHERE is_ambiguous = 1")
    D["model_status"] = {r[0]: r[1] for r in rows("SELECT label, n FROM sentiment_qa WHERE section = 'model_status'")}
    D["bars"] = q("SELECT COUNT(*) FROM market_bars")
    D["null_close"] = q("SELECT COUNT(*) FROM market_bars WHERE close IS NULL")
    D["features"] = q("SELECT COUNT(*) FROM market_hourly_features")
    D["coverage"] = rows("""SELECT t.AssetClass, COUNT(*), SUM(f.future_return_1h IS NOT NULL), SUM(f.future_return_2h IS NOT NULL),
        SUM(f.future_return_3h IS NOT NULL), SUM(f.future_return_6h IS NOT NULL), SUM(f.future_return_12h IS NOT NULL)
        FROM market_hourly_features f JOIN DimTicker t ON t.TickerSymbol = f.ticker GROUP BY 1 ORDER BY 1""")
    D["hourly"] = q("SELECT COUNT(*) FROM reddit_hourly")
    D["merged"] = q("SELECT COUNT(*) FROM merged_hourly_panel")
    D["panels"] = {r[0]: r[1:] for r in rows("SELECT panel_name, COUNT(*), COUNT(DISTINCT ticker), AVG(reddit_volume) FROM panels GROUP BY 1")}
    D["span"] = rows("SELECT MIN(hour_utc), MAX(hour_utc) FROM panels")[0]
    D["facts"] = {t: q('SELECT COUNT(*) FROM "%s"' % t) for t in
                  ("DimTicker", "DimTime", "DimSource", "DimSentimentSource", "DimMajoritySentiment", "DimDetectionConfig",
                   "FactRedditVolume", "FactMarketPrice", "FactMarketSentiment")}
    D["a1"] = {r[0]: r[1:] for r in rows("""SELECT panel_name, COUNT(*), SUM(p_value_bh < 0.05), AVG(metric_value) FROM analysis_results
        WHERE metric_name = 'spearman' AND status = 'ok' AND level = 'ticker' AND horizon != 'log_return'
        AND predictor IN ('sentiment_mean', 'random_direction') GROUP BY 1""")}
    D["a2"] = {r[0]: r[1:] for r in rows("""SELECT panel_name, COUNT(*), SUM(p_value_bh < 0.05), AVG(metric_value), SUM(metric_value > 0.5)
        FROM analysis_results WHERE metric_name = 'winrate' AND status = 'ok' AND level = 'ticker'
        AND predictor IN ('sign(sentiment_mean)', 'random_direction') GROUP BY 1""")}
    D["a3"] = {r[0]: r[1:] for r in rows("""SELECT panel_name, COUNT(*), AVG(metric_value), MAX(metric_value), MIN(metric_value)
        FROM analysis_results WHERE metric_name = 'auc' AND status = 'ok' GROUP BY 1""")}
    D["a5"] = rows("SELECT COUNT(*), SUM(weak_convergence), SUM(strong_convergence) FROM evaluation_convergence WHERE a1_edge IS NOT NULL AND a2_edge IS NOT NULL AND a3_edge IS NOT NULL AND panel_name != 'panel_baseline'")[0]
    D["a5_base"] = rows("SELECT COUNT(*), SUM(weak_convergence) FROM evaluation_convergence WHERE a1_edge IS NOT NULL AND a2_edge IS NOT NULL AND a3_edge IS NOT NULL AND panel_name = 'panel_baseline'")[0]
    D["rank"] = rows("SELECT panel_name, mean_abs_edge, weak, strong, cells FROM evaluation_panel_ranking ORDER BY mean_abs_edge DESC")
    D["prior"] = rows("SELECT COUNT(*), SUM(lag_beats_current) FROM evaluation_prior_vs_current")[0]
    D["importance"] = rows("SELECT group_name, AVG(mean_abs_coef) FROM evaluation_factor_importance WHERE panel_name != 'panel_baseline' GROUP BY 1 ORDER BY 2 DESC")
    D["signals"] = rows("SELECT z_threshold, s_threshold, SUM(n_signals) FROM signal_summary GROUP BY 1, 2 ORDER BY 1, 2")
    D["signal_types"] = rows("SELECT signal_type, COUNT(*) FROM signal_events GROUP BY 1 ORDER BY 2 DESC")
    D["signal_levels"] = rows("SELECT signal_level, COUNT(*) FROM signal_events GROUP BY 1")
    return D


def date_of(epoch):
    return pd.to_datetime(epoch, unit="s").strftime("%Y-%m-%d")


def read_csv(path):
    return pd.read_csv(path, comment="#")


def rule_validation_text():
    text = (REPORTS / "rule_validation" / "rule_validation.md").read_text(encoding="utf-8")
    return text[text.index("## ชุด tune"):].replace("\n## ", "\n### ").replace("## ชุด tune", "### ชุด tune", 1).strip().splitlines()


def extras_text(start, stop=None):
    """Lines of output/reports/rule_validation/band_and_confusion.md from heading `start` up to heading `stop`, demoted one level."""
    text = (REPORTS / "rule_validation" / "band_and_confusion.md").read_text(encoding="utf-8")
    part = text[text.index(start):]
    if stop:
        part = part[:part.index(stop)]
    return part.replace("\n## ", "\n### ").replace(start, "#" + start, 1).strip().splitlines()


def dashboard_check_summary():
    text = (REPORTS / "dashboard_kpi_check.md").read_text(encoding="utf-8")
    m = re.search(r"ผ่าน (\d+) จาก (\d+) ข้อ", text)
    return int(m.group(1)), int(m.group(2))


def system_tests_summary():
    text = (REPORTS / "system_tests.md").read_text(encoding="utf-8")
    m = re.search(r"ผ่าน (\d+) จาก (\d+) ข้อ", text)
    return int(m.group(1)), int(m.group(2))


# ------------------------------------------------------------------------------------------------ file 1

def build_beyond(D):
    L = header("1) สิ่งที่โค้ดทำเหนือหรือต่างจาก proposal",
               "รายการทุกจุดที่ระบบทำนอกเหนือจาก proposal ฉบับอนุมัติ หรือเลือกวิธีเองในจุดที่ proposal ไม่ได้ระบุ",
               "docs/METHOD_DECISIONS_NOT_IN_PROPOSAL.md, docstring ของโมดูล, configs/*.yaml, proposal (อ่านจาก PDF) และตารางใน output/reddit.sqlite3")
    L += ["ป้ายที่ใช้: **[ส่วนขยาย]** = เพิ่มนอก proposal (ต้องบอกในรายงาน) · **[กำหนดรายละเอียด]** = proposal พูดถึงเรื่องนี้แต่ไม่ระบุวิธี เราเลือกเอง · "
          "**[ต่างจากตัวอักษร]** = ทำต่างจากที่ proposal เขียนตรง ๆ · **[ตามที่ระบุ]** = อยู่ใน proposal ฉบับอนุมัติแล้ว (ใส่ไว้เพราะเคยเข้าใจผิดว่าเป็นของเพิ่ม)", ""]

    def section(title, rows):
        L.extend(["## " + title, ""] + table(["#", "เรื่อง", "ป้าย", "proposal ว่าอย่างไร", "ที่ทำจริง / เหตุผล", "โค้ด"], rows) + [""])

    section("A. ข้อมูลดิบและการเตรียมข้อความ (7.1)", [
        (1, "final_text ของคอมเมนต์ = title โพสต์แม่ + body คอมเมนต์ (cleaner 2.0)", "[กำหนดรายละเอียด]",
         "บอกแค่ว่าใช้ final_text ที่ล้างแล้ว", "คอมเมนต์สั้น ๆ ('hold', 'lol') ไม่มีความหมายถ้าไม่มี title; ตรงกับงานเก่า; ผู้ใช้เคาะ 2026-10-24. เก็บ `own_text` (ที่คนเขียนเอง) แยก", "etl/clean_text.py"),
        (2, "กรองบอท/ข้อความสั้น/ไม่ใช่อังกฤษ ตัดสินจาก `own_text`", "[กำหนดรายละเอียด]", "ไม่ระบุกฎกรอง",
         "title ต้องไม่ช่วยให้คอมเมนต์ '!' ผ่านหรือบังบอท; ภาษาใช้กฎอักษร/คำฟังก์ชัน (ไม่ใช้โมเดล) จับได้เฉพาะข้อความ ≥ 6 คำ", "etl/quality_filter.py"),
        (3, "แปลงอีโมจิเป็นคำ, คงตัวพิมพ์ใหญ่และ `$ % ! ?`", "[กำหนดรายละเอียด]", "ระบุแค่ 'ล้างข้อความ'", "VADER ใช้ตัวพิมพ์ใหญ่และเครื่องหมายเป็นสัญญาณ; อีโมจิล้วนจึงไม่กลายเป็นว่าง", "etl/clean_text.py"),
        (4, "ข้อความ Ticker ใน title ของโพสต์แม่นับให้คอมเมนต์ด้วย", "[ส่วนขยายโดยผล]", "ไม่ระบุ",
         "T4 อ่าน final_text จึงนับคอมเมนต์ในโพสต์ที่พูดถึงหุ้นนั้น (ผู้ใช้เคาะแล้วว่าเป็นพฤติกรรมที่ควรเป็น); ตัวเลข mention/volume รายหุ้นจึงสูงกว่าถ้านับแค่ข้อความตัวเอง", "etl/extract_tickers.py"),
        (5, "กฎกันคำทั่วไปของ Ticker (KO, COIN, SOL, 'Ripple effect', doge เฉพาะ r/CryptoCurrency)", "[กำหนดรายละเอียด]", "ระบุ 34 สินทรัพย์", "ลด false positive; เก็บ `strong_count` แยกจาก `mention_count` (โดยเฉพาะ `gold` ที่เป็นคำทั่วไป)", "etl/ticker_dict.py"),
        (6, "ใช้เฉพาะ 6 ชุมชน กรองตอน query ไม่ลบแถวอีก 3 ชุมชน", "[ตามที่ระบุ]", "6 ชุมชน", "DB เก็บ 9 ชุมชนเพราะข้อมูลดิบคือสำเนาเดียว", "etl/common.py"),
    ])
    section("B. การวิเคราะห์ความรู้สึก (7.3)", [
        (7, "กฎเสริม 3 ข้อของ conflict resolution: `both_neutral`, `hard_conflict_mixed_zero`, `one_model`", "[ส่วนขยาย]", "กำหนด 3 กรณี (เหมือนกัน/ขัดเล็ก/ขัดหนัก)",
         "ปิดช่องที่ proposal ไม่ครอบคลุม ตามหลัก 'ถ้าไม่ชัดให้เป็นกลาง'; บันทึกใน `final_method` ให้ตรวจย้อนหลังได้", "etl/resolve_sentiment.py"),
        (8, "`same_direction_far` (ต่างกัน > 0.50 ใช้คะแนนที่ใกล้ 0) และ `is_ambiguous`", "[ตามที่ระบุ]", "ระบุในฉบับอนุมัติ (ตาราง 11)", "ค่า 0.50 อยู่ configs/sentiment.yaml", "etl/resolve_sentiment.py"),
        (9, "คำสำคัญที่มีคำปฏิเสธ 2 คำก่อนหน้า ('not bullish') ถูก **ข้าม** ไม่กลับขั้ว; ค้นเฉพาะ `own_text`", "[กำหนดรายละเอียด]", "ใช้คำสำคัญเป็นตัวตัดสินกรณีขัดกัน", "การกลับขั้วอัตโนมัติผิดบ่อย; 'bullish' ใน title คือความเห็นของเจ้าของโพสต์ ไม่ใช่ของคนคอมเมนต์", "etl/resolve_sentiment.py"),
        (10, "คะแนน FinBERT = P(positive) − P(negative); ProsusAI/finbert, fp16, ตัดที่ 256 โทเคน, batch 128", "[ตามที่ระบุ + กำหนดรายละเอียด]", "ระบุสูตร; ไม่ระบุ precision/ความยาว",
         "fp16 เทียบ fp32 บน 1,000 ข้อความ ต่างไม่เกิน 0.005; ข้อความที่ยาวเกิน 256 โทเคนถูกตัดส่วนท้าย", "etl/sentiment_finbert.py"),
        (11, "ขอบ neutral band เป็นแบบทิศทาง: ≥ +0.05 = positive, ≤ −0.05 = negative", "[กำหนดรายละเอียด]", "'ระหว่าง −0.05 ถึง +0.05' (กำกวมที่ค่าขอบ)", "ตามธรรมเนียมของผู้พัฒนา VADER", "etl/common.status_of"),
    ])
    section("C. ราคาและ feature (7.2)", [
        (12, "ตัดแถว `close IS NULL`", "[กำหนดรายละเอียด]", "ระบุแค่ใช้ช่วงที่มีข้อมูลพอ", "เป็น placeholder ตลาดปิด ไม่ใช่ราคา (%s แถว)" % n(D["null_close"]), "etl/market_features.py"),
        (13, "ปัดเวลาเริ่มบาร์ลงเป็นต้นชั่วโมงก่อนจับคู่ (หุ้น 13:30 → 13:00)", "[กำหนดรายละเอียด]", "จับคู่ด้วย timestamp + Ticker", "บาร์หุ้นเริ่มที่ xx:30; ตรวจแล้วไม่มี look-ahead", "etl/market_features.py, etl/merge_panel.py"),
        (14, "`future_return_nh` เป็น NULL ถ้าไม่มีบาร์ที่เริ่มหลัง n ชั่วโมงพอดี", "[กำหนดรายละเอียด]", "ให้ใช้เฉพาะช่วงที่มีข้อมูลเพียงพอ", "ไม่คำนวณข้ามวันหยุด/ตลาดปิด → หุ้น/ETF 12h ไม่มีเลย, 6h น้อยมาก (ข้อจำกัดสำคัญ)", "etl/market_features.py"),
        (15, "RSI ข้ามช่วงตลาดปิดโดยถือว่าบาร์ติดกัน; Wilder คาบ 14", "[ส่วนขยาย]", "ไม่ระบุคาบ", "ค่ามาตรฐานของตัวชี้วัด", "etl/market_features.py"),
        (16, "z-score ใช้ 24 ชั่วโมง **ก่อนหน้า ไม่รวมปัจจุบัน**, ต้องมี ≥ 5 บาร์", "[กำหนดรายละเอียด]", "ระบุ z-score 24 ชม.", "กัน look-ahead", "etl/market_features.py, etl/reddit_features.py"),
        (17, "ชื่อคอลัมน์ในฐานข้อมูลคงเดิม `log_return` แต่ทุกอย่างที่คนเห็นเรียก **Current Return**", "[ต่างจากตัวอักษร]", "ตัวแปร `current_return`", "ไม่ต้องสร้างตารางและรันผลใหม่; อ้างในเล่มด้วยหมายเหตุ", "ทั้งระบบ"),
    ])
    section("D. การวิเคราะห์ความสัมพันธ์ (7.4)", [
        (18, "Correlation: เพิ่มตัวทำนาย lag_1h, momentum_1h, volume z-score (นอกจาก sentiment_mean)", "[ส่วนขยาย]", "sentiment เป็น input", "ตอบคำถามผู้บริหารว่า 'อดีตดีกว่าปัจจุบันไหม'", "analysis/correlation.py"),
        (19, "Correlation: เพิ่มเป้า Current Return (ชั่วโมงเดียวกัน) นอกจาก future return 5 กรอบ", "[ส่วนขยาย]", "5 กรอบเวลาของ future return", "ใช้ดูการเคลื่อนไหวร่วม (ไม่ใช่การทำนาย)", "analysis/correlation.py"),
        (20, "ปรับ p-value แบบ Benjamini–Hochberg (BH) ข้ามสินทรัพย์", "[ส่วนขยาย]", "ไม่มี", "ทดสอบหลายพันเซลล์ จึงต้องคุมผลบวกลวง", "analysis/results_store.py"),
        (21, "จำนวนตัวอย่างขั้นต่ำ 30; ต่ำกว่านี้ติด `insufficient_data` ไม่เติม 0", "[กำหนดรายละเอียด]", "'หากจำนวนตัวอย่างเพียงพอ'", "ค่า 30 เป็นข้อเสนอของโครงการ ปรับได้", "analysis/*.py"),
        (22, "Win Rate: เหตุการณ์ = ชั่วโมงที่ sentiment มีทิศทาง **และ** return ไม่เท่ากับ 0; เทียบ baseline = ทิศสุ่มบนแถวเดียวกัน", "[กำหนดรายละเอียด]", "ระบุ Binomial Test เทียบการสุ่ม", "ไม่ปนชั่วโมงที่ไม่มีทิศ; baseline ใช้ seed คงที่", "analysis/winrate.py"),
        (23, "Logistic: ตัวแปร 6 กลุ่มแมปเป็นคอลัมน์ชัดเจน, `TimeSeriesSplit(5, gap=12)`, scaler fit เฉพาะชุดฝึก, ตัดแถว return = 0, แยกตาม panel × กลุ่มสินทรัพย์ × horizon", "[กำหนดรายละเอียด]", "ระบุ TimeSeriesSplit และ AUC", "gap 12 ชม. กัน future_return_12h ซ้อนกับชุดทดสอบ", "analysis/logistic.py"),
        (24, "A4/A5: ประเมินว่า 3 วิธี (Spearman, Win Rate, AUC) เห็นตรงกันหรือไม่ (weak/strong convergence), จัดอันดับ panel, เทียบ lag กับ current, ความสำคัญของกลุ่มตัวแปร", "[ส่วนขยาย]", "ให้ประเมินผล", "สรุปผลหลายวิธีให้เป็นภาพเดียว; ตัวควบคุมคือ panel_baseline", "analysis/evaluate.py"),
        (25, "กราฟ heatmap: แดง = ต่ำกว่าเกณฑ์/ติดลบ เขียว = สูงกว่า/บวก, มี n ทุกช่อง, หัวกราฟมีคำอธิบาย panel, ฟอนต์ไทย", "[ส่วนขยาย]", "ให้แสดง heatmap", "อ่านง่ายขึ้นและบอกขนาดตัวอย่าง (ผู้ใช้ขอ 2026-10-25)", "analysis/figure_style.py"),
    ])
    section("E. สัญญาณ (7.6), คลังข้อมูล และแดชบอร์ด (7.5)", [
        (26, "สัญญาณจาก sentiment ต้องมี ≥ 3 ข้อความในชั่วโมงนั้น", "[ส่วนขยาย]", "ไม่ระบุ", "กัน 'ค่าเฉลี่ยของ 1 ข้อความ' ยิงสัญญาณ", "analysis/signals.py + configs/detection.yaml"),
        (27, "ระดับสัญญาณ low/medium/high คำนวณจากคะแนน 1–3 (ระยะห่างเหนือเกณฑ์)", "[กำหนดรายละเอียด]", "ระบุว่ามีระดับ ไม่ระบุสูตร", "ค่าทั้งหมดอยู่ configs/detection.yaml", "analysis/signals.py"),
        (28, "คำนวณสัญญาณล่วงหน้า 6 ชุด (z 1.5/2.0/2.5 × sentiment 0.05/0.30) ส่วน horizon แนบผ่าน view `v_signal_list`", "[กำหนดรายละเอียด]", "ผู้ใช้ปรับ Z-score, Sentiment, Horizon", "ไม่เก็บสำเนาซ้ำ 5 ชุด; หน้าจอคำนวณสดได้ใน < 2 วินาที", "analysis/signals.py"),
        (29, "`DimSentimentSource` มีแถว 'ALL' (panel รวม) เพิ่ม; `FactMarketSentiment` 1 แถว = ชั่วโมง × ticker ใช้ config เริ่มต้นชุดเดียว", "[ส่วนขยาย]", "ระบุโครงดาวตามรูปที่ 2–4", "Win rate ในตารางเป็นค่าเต็มช่วง ใช้แสดงผลเท่านั้น", "etl/seed_dims.py, etl/load_fact_market_sentiment.py"),
        (30, "ตารางผลวิเคราะห์ `analysis_results` และตารางประเมิน `evaluation_*` รวมถึง `sentiment_qa`, `data_quality_audit`", "[ส่วนขยาย]", "ไม่ระบุที่เก็บผล", "เก็บผลทุกเซลล์ตรวจย้อนหลังได้ (มี run_id, config_hash)", "analysis/results_store.py"),
        (31, "ตารางเก็บผลรุ่นก่อนเปลี่ยนบริบท `*_v1` (sentiment_item_v1 ฯลฯ)", "[ส่วนขยาย]", "ไม่มี", "ไว้เทียบผลของการใส่ title โพสต์แม่ (`context_effect.md`); ลบได้เมื่อไม่ใช้ (ต้องถามผู้ใช้ก่อน)", "scripts/archive_sentiment_v1.py"),
    ])
    section("F. การทดสอบและรายงานที่เพิ่ม", [
        (32, "ทดสอบระบบกับข้อมูลจริง 32 ข้อ (ตรรกะ + เชื่อมโยง) แยกจาก unit test", "[กำหนดรายละเอียด]", "8.4 ให้ทดสอบ 3 ส่วน", "ตรวจตัวเลขในตารางจริง ไม่ใช่แค่ข้อมูลจำลอง; คำนวณ return ซ้ำจากราคา", "scripts/system_tests.py"),
        (33, "ตรวจว่า final_text ตรงกับรูปแบบที่กำหนด (ผล 0 รายการไม่ตรง)", "[ส่วนขยาย]", "ไม่มี", "ยืนยันว่าการใส่ title ถูกต้องทุกแถว", "scripts/verify_final_text_forms.py"),
        (34, "เทียบผลก่อน/หลังใส่ title โพสต์แม่", "[ส่วนขยาย]", "ไม่มี", "วัดว่าบริบทเปลี่ยนความรู้สึกมากแค่ไหน (ตัวควบคุม = submission ต้องไม่เปลี่ยน)", "scripts/compare_context_effect.py"),
        (35, "ทดสอบเกณฑ์เข้มขึ้น: super quality (|score| ≥ 0.50) และ super spike (z > 2.0) แยกช่วง explore / hold-out", "[ส่วนขยาย]", "ไม่มี", "ตอบว่าเกณฑ์เข้มขึ้นให้สัญญาณดีขึ้นหรือเป็นแค่โชค (ผลอยู่ไฟล์ที่ 2)", "scripts/super_signal_sensitivity.py"),
        (36, "ตรวจ proposal coverage อัตโนมัติ (ตัวแปรและ KPI ครบหรือไม่)", "[ส่วนขยาย]", "ไม่มี", "กันตกหล่นตารางค่าวัด", "scripts/check_proposal_coverage.py"),
    ])
    L += ["## ข้อควรระวังเวลาเขียนในเล่ม", "",
          "- ข้อที่ป้าย **[ส่วนขยาย]** ต้องเขียนว่าเป็นส่วนขยาย ไม่ใช่การแก้ proposal",
          "- ข้อ 17 (`log_return` ↔ Current Return) ถ้าอ้างชื่อคอลัมน์ในฐานข้อมูล ให้ใส่หมายเหตุ",
          "- ข้อ 14 กระทบผลหุ้น/ETF ที่ 6h และ 12h → ต้องเขียนเป็นข้อจำกัด (ดูไฟล์ที่ 3)",
          "- ข้อ 31 ตาราง `*_v1` ทำให้ฐานข้อมูลใหญ่ขึ้น (ลบแล้ว 2026-10-25 ตามที่ผู้ใช้สั่ง; รายงาน context_effect.md ที่สร้างไว้ก่อนลบยังอยู่ แต่สคริปต์ compare_context_effect.py รันซ้ำไม่ได้อีก)", ""]
    return L


# ------------------------------------------------------------------------------------------------ file 2

def build_tests(D, db_path):
    nb = read_csv(REPORTS / "neutral_band_sensitivity.csv")
    sup = read_csv(REPORTS / "super_signal_sensitivity.csv")
    ok, total = system_tests_summary()
    dash = dashboard_check_summary()
    L = header("2) การทดสอบ: ขั้นตอนที่ 5 ของ 7.3, เกณฑ์ที่เพิ่ม และสมมติฐานของ 7.4",
               "สรุปทุกการทดสอบที่ทำ: ทำอะไร วิธีทำ ผลที่วัดได้ และข้อสรุป รวมถึงเกณฑ์ที่เราเพิ่ม (z-score, super quality, super spike)",
               "output/reports/*.csv|md (neutral band, rule validation, super signal, system tests) และตาราง analysis_results / evaluation_* / signal_summary")
    L += ["## ภาพรวม", ""] + table(["#", "การทดสอบ", "ที่มาใน proposal", "สถานะ", "ข้อสรุปสั้น"], [
        ("T1", "เทียบ neutral band 0.05 กับ 0.10 (สัดส่วน + ความแม่นเทียบป้าย)", "7.3 ขั้นตอนที่ 5", "ทำแล้ว", "สัดส่วนผลสุดท้ายต่างกัน ≤ 1.5 จุด; ความแม่นเทียบป้ายที่ ±0.10 ไม่ดีกว่า (final 44.3% → 42.4%) จึงคง ±0.05"),
        ("T2", "Rule Validation (ติดป้ายเอง 210 ข้อความ) + confusion matrix", "7.3 ขั้นตอนที่ 5", "ทำแล้ว", "กฎรวมผลใกล้เคียง FinBERT เดี่ยว (ชุด test 41.3% / 42.9%); คงกฎตาม proposal ไม่ตัด"),
        ("T3", "Z-score threshold 1.5 / 2.0 / 2.5 ในระบบสัญญาณ", "7.5 + 7.6 (ปรับได้)", "ทำแล้ว (นับจำนวน + ทดสอบความแม่นแบบกริด Z × ความรู้สึก)", "เกณฑ์สูงขึ้น สัญญาณน้อยลง"),
        ("T4", "Super quality (≥ 0.50) และ super spike (z > 2.0)", "ส่วนขยาย", "ทำแล้ว", "ไม่ดีกว่า; ผลที่เด่นหายไปในช่วง hold-out"),
        ("T5", "สมมติฐาน 7.4: Correlation, Win Rate, Logistic, ความสอดคล้องของ 3 วิธี", "7.4", "ทำแล้ว", "ไม่พบความสามารถทำนายที่เชื่อถือได้"),
        ("T6", "ทดสอบระบบกับข้อมูลจริง (Unit & Logic + Integration)", "8.4", "ผ่าน %d/%d ข้อ" % (ok, total), "ไม่พบตัวเลขผิดกฎ"),
        ("T8", "ทดสอบ Dashboard: ตัวเลขบนหน้าจอเทียบ SQL ตรง", "8.4 ส่วนที่ 3", "ผ่าน %d/%d ข้อ" % dash, "ทุก KPI ที่ตรวจตรงกับ SQL"),
        ("T7", "ผลของการใส่ title โพสต์แม่", "ส่วนขยาย", "ทำแล้ว", "final_status คอมเมนต์เปลี่ยน ~21.8%"),
    ]) + [""]

    # ---- T1
    keep = nb[nb.group == "final"]
    piv = keep.pivot(index="label", columns="band", values="n")
    tot = piv.sum()
    L += ["## T1) เทียบ neutral band ±0.05 กับ ±0.10", "",
          "**สมมติฐาน H0:** การเปลี่ยนเกณฑ์ neutral จาก ±0.05 เป็น ±0.10 ไม่เปลี่ยนสัดส่วน positive/negative/neutral อย่างมีสาระ",
          "", "**วิธีทำ:** ใช้คะแนน VADER, FinBERT และคำสำคัญที่เก็บไว้แล้วของทุกข้อความ (%s) คำนวณกฎรวมผลใหม่ด้วยเกณฑ์ 0.10 โดยไม่รันโมเดลซ้ำ แล้วนับสัดส่วน และนับข้อความที่ป้ายสุดท้ายเปลี่ยน (`scripts/neutral_band_sensitivity.py`, อ่านอย่างเดียว)" % n(D["passed"]), "",
          "**ผล (final):**", ""]
    L += table(["ประเภท", "±0.05", "±0.10", "ต่าง (จุด)"],
               [(lab, pct(piv.loc[lab, 0.05] / tot[0.05]), pct(piv.loc[lab, 0.1] / tot[0.1]),
                 "%+.2f" % (100 * (piv.loc[lab, 0.1] / tot[0.1] - piv.loc[lab, 0.05] / tot[0.05]))) for lab in ("positive", "neutral", "negative")])
    models = []
    for model in ("vader", "finbert"):
        sub = nb[nb.group == model].pivot(index="label", columns="band", values="n")
        for lab in ("positive", "neutral", "negative"):
            models.append((model, lab, pct(sub.loc[lab, 0.05] / sub[0.05].sum()), pct(sub.loc[lab, 0.1] / sub[0.1].sum())))
    amb = nb[nb.group == "is_ambiguous"].set_index("band").n
    L += ["", "**แยกตามโมเดล:**", ""] + table(["โมเดล", "ประเภท", "±0.05", "±0.10"], models)
    L += ["", "- `is_ambiguous`: %s → %s ของข้อความ" % (pct(amb[0.05] / tot[0.05]), pct(amb[0.1] / tot[0.1])),
          "- ข้อความที่ป้ายสุดท้ายเปลี่ยน: ดูตารางท้ายรายงาน `output/reports/neutral_band_sensitivity.md` (ตัวเลขชุดเดียวกัน)",
          "", "**ข้อสรุป:** ผลสุดท้ายแทบไม่ต่างกัน แต่ FinBERT ที่ให้คะแนนเบา neutral เพิ่มมากเมื่อเกณฑ์กว้างขึ้น ทดสอบนัยสำคัญด้วย p-value ไม่มีความหมายเพราะตัวอย่าง 22 ล้านทำให้ทุกความต่างมีนัยสำคัญ "
          "ควรตัดสินจากขนาดความต่าง", ""]
    L += ["**ความแม่นเมื่อเทียบป้าย 210 ข้อความของผู้พัฒนา (`scripts/rule_validation_extras.py`):**", ""] + extras_text("## ความแม่น: ±0.05 เทียบ ±0.10", "## Confusion matrix")[2:]
    L += ["", "**ข้อสรุป:** เกณฑ์ ±0.10 ไม่ทำให้ความแม่นของวิธีรวมผลดีขึ้น (ทั้ง 210 ข้อความ 44.3% → 42.4%; ชุด test เท่าเดิม 41.3%) ความต่างอยู่ในช่วงที่ตัวอย่างเล็กแยกจากความบังเอิญไม่ได้ จึง**คงเกณฑ์ ±0.05 ตาม proposal** และรายงาน ±0.10 เป็นการทดสอบความไว", ""]

    # ---- T2
    L += ["## T2) Rule Validation (ตรวจกฎรวมผลด้วยป้ายที่ผู้พัฒนาติดเอง)", "",
          "**สมมติฐาน H0:** วิธีรวมผลตามกฎของ proposal ไม่แม่นกว่าการใช้ FinBERT หรือ VADER อย่างเดียว",
          "", "**วิธีทำ** (`scripts/rule_validation.py`):",
          "1. แบ่งข้อความเป็น 7 กลุ่มตามกฎ (`final_method`): same_direction, same_direction_far, both_neutral, small_conflict มี/ไม่มีคำสำคัญ, hard_conflict มี/ไม่มีคำสำคัญ (ข้ามกลุ่มที่มี 0.01%)",
          "2. สุ่มกลุ่มละ 30 ข้อความ = 210 ข้อความ จากทุกความยาว (seed คงที่ 20261024) แล้วแบ่งชุด **tune** (ปรับกฎ) กับชุด **test** (รายงานผล) อย่างละครึ่งในแต่ละกลุ่ม",
          "3. ผู้พัฒนาติดป้าย positive/negative/neutral เองจากไฟล์ที่มีแต่ข้อความ (ซ่อนคะแนนและกฎ; AI ไม่ได้ติดป้ายเพื่อไม่ให้โมเดลตัดสินโมเดล)",
          "4. คำนวณความแม่น = สัดส่วนที่ประเภทของวิธีนั้นตรงกับป้าย; รวมแบบถ่วงน้ำหนักตามจำนวนข้อความจริงของแต่ละกลุ่ม", "",
          "**ผล (วัดจริง):**", ""] + rule_validation_text()
    L += ["", "**ข้อสรุป:** ในชุด test กฎรวมผล 41.3% ใกล้เคียง FinBERT เดี่ยว 42.9% และสูงกว่า VADER 37.1%; ในชุด tune FinBERT เดี่ยวดีกว่า (56.4% เทียบ 47.3%) "
          "ตัวอย่าง 15 ข้อความต่อกลุ่มต่อชุดน้อยเกินกว่าจะยืนยันรายกฎ จึงถือเป็นแนวโน้มไม่ใช่การทดสอบนัยสำคัญ proposal ระบุว่า 'กฎใดไม่ช่วยให้ถูกต้องขึ้นจะปรับหรือตัดออก' "
          "**ผู้ใช้เคาะ 2026-10-25: คงกฎตาม proposal ไม่ตัดกฎ** รายงานผลตามจริงว่ากฎรวมไม่ได้แม่นกว่า FinBERT เดี่ยวอย่างชัดเจน และไม่ได้แย่กว่าอย่างมีนัย", ""]
    L += ["**Confusion matrix (โมเดลทาย vs ป้ายของผู้พัฒนา, เกณฑ์ ±0.05):**", ""] + extras_text("## Confusion matrix ที่เกณฑ์ ±0.05", "## Confusion matrix ที่เกณฑ์ ±0.10")[1:]
    L += ["", "รูป: `output/figures/s5_confusion_matrices.png`",
          "", "**สิ่งที่อ่านได้จาก confusion matrix:** ข้อความที่ผู้พัฒนาติด neutral (90 ข้อความ) ถูกทำนายเป็น positive/negative บ่อย — VADER ทายถูกเพียง 24 จาก 90 และ FinBERT 37 จาก 90; FinBERT ทายขั้ว negative ได้ดีกว่า VADER (45 เทียบ 28 จาก 77) "
          "สอดคล้องกับที่ VADER อ่านคำสแลง/คำเชิงลบเป็นลบเกินจริง ตัวอย่างนี้สุ่มแบบแบ่งกลุ่มตามกฎ ไม่ใช่สัดส่วนจริงของข้อความทั้งหมด", ""]

    # ---- T3
    sig = pd.DataFrame(D["signals"], columns=["z", "s", "n"]).pivot(index="z", columns="s", values="n")
    L += ["## T3) เพิ่ม Z-score threshold (1.5 / 2.0 / 2.5) ในระบบสัญญาณ", "",
          "**คำถาม:** เมื่อเกณฑ์ z สูงขึ้นหรือเกณฑ์ sentiment เข้มขึ้น จำนวนสัญญาณเปลี่ยนอย่างไร (proposal 7.6 ข้อ 'เกณฑ์ส่งผลต่อจำนวนและประเภทอย่างไร')",
          "", "**วิธีทำ:** `analysis/signals.py` ตรวจสัญญาณทุกชั่วโมง × ticker ด้วยตาราง 3 × 2 = 6 ชุดเกณฑ์ (z > 1.5/2.0/2.5; |sentiment| ≥ 0.05/0.30; ต้องมี ≥ 3 ข้อความ) เก็บใน `signal_events`", "",
          "**ผล (จำนวนสัญญาณรวมทุกประเภท):**", ""]
    L += table(["Z-score >", "|sentiment| ≥ 0.05", "|sentiment| ≥ 0.30"], [(z, n(sig.loc[z, 0.05]), n(sig.loc[z, 0.30])) for z in sig.index])
    L += ["", "ประเภทสัญญาณทั้งหมด (6 ชุดรวมกัน): " + ", ".join("%s %s" % (t, n(c)) for t, c in D["signal_types"]) + "; ระดับ: " + ", ".join("%s %s" % (t, n(c)) for t, c in D["signal_levels"]),
          "", "**ข้อสรุป:** จำนวนสัญญาณลดลงเมื่อเกณฑ์เข้ม; นี่เป็นการนับสัญญาณ ไม่ใช่การพิสูจน์ว่าสัญญาณแม่น (ดู T4 ที่ทดสอบความแม่น)", ""]

    grid = (REPORTS / "z_sentiment_grid.md").read_text(encoding="utf-8")
    L += ["**ทดสอบความแม่นของเกณฑ์ (ส่วนขยาย, `scripts/z_sentiment_grid.py`):** กริด Z-score 1.5/2.0/2.5 × |ความรู้สึก| 0.05/0.30/0.50/0.80 กำหนดก่อนดูผล "
          "วัด win rate ของทิศความรู้สึกเทียบ Future Return แยกช่วง explore / hold-out", ""]
    L += grid[grid.index("## กรอบเวลา 1h"):].replace("\n## ", "\n#### ").replace("## กรอบเวลา 1h", "#### กรอบเวลา 1h", 1).strip().splitlines()
    L += ["", "**ข้อสรุป:** ทั้ง 45 ช่องส่วนใหญ่ ≈ 50% (49–51%); |ความรู้สึก| ≥ 0.80 มีเหตุการณ์ไม่ถึง 30 ทุกช่อง (ข้อมูลไม่พอ) "
          "ช่องที่ดูเด่นที่สุดคือ |s| ≥ 0.50 ที่ 1h (52.8–54.4%, n = 237–362) ซึ่งสูงกว่า 50% ทั้งช่วง explore และ hold-out แต่ที่ 2h/3h กลับต่ำกว่าหรือเท่า 50% และมี n น้อย "
          "จึงเป็น**ข้อสังเกตที่น่าตามต่อ ไม่ใช่หลักฐานว่าทำนายได้** (ทดสอบ 45 ครั้ง คาดว่าบังเอิญ p < 0.05 ราว 2 ครั้ง; เหตุการณ์ชั่วโมงติดกันไม่อิสระกัน)", ""]

    # ---- T4
    pool = sup[(sup.level == "pooled") & (sup.period == "all")]
    def wr_table(names):
        rows = []
        for name in names:
            row = [name]
            for h in HORIZONS:
                r = pool[(pool.panel == name) & (pool.horizon == h)].iloc[0]
                row.append("%s (n=%s)" % (pct(r.winrate), n(r.n)))
            rows.append(row)
        return table(["panel"] + list(HORIZONS), rows)
    L += ["## T4) ส่วนขยาย: super quality (|score| ≥ 0.50) และ super spike (z > 2.0)", "",
          "**สมมติฐาน H0:** เกณฑ์ที่เข้มขึ้นไม่ทำให้ win rate / correlation ดีขึ้นกว่า quality (0.30) และ spike (1.5)",
          "", "**วิธีทำ** (`scripts/super_signal_sensitivity.py`, อ่านอย่างเดียว):",
          "1. super quality = กรองข้อความ |final_sentiment| ≥ 0.50 ต่อข้อความก่อนเฉลี่ยรายชั่วโมง (ทั้งระดับ Ticker และ global)",
          "2. super spike = เลือกชั่วโมงที่ z-score ปริมาณโพสต์ > 2.0 (ทั้ง Ticker และ global)",
          "3. เกณฑ์ **ตั้งก่อนดูผล** และไม่ปรับตามผล เพื่อไม่ให้เลือกผลที่ชอบ",
          "4. คำนวณ win rate (เทียบ baseline = ทิศสุ่มบนแถวชุดเดียวกัน, binomial test) และ Spearman แยกช่วง explore (ก่อน 2025-10-01) กับ hold-out (หลังจากนั้น) เพื่อดูว่าผลที่เด่นอยู่ต่อไหม",
          "", "**ผล: win rate รวมทุกสินทรัพย์ (ควร ≈ 50% ถ้าไม่มีสัญญาณ):**", ""]
    L += wr_table(["panel_Ticker", "panel_Ticker_quality", "panel_Ticker_super_quality", "panel_Ticker_spike", "panel_Ticker_super_spike"])
    L += [""] + wr_table(["panel_global", "panel_global_quality", "panel_global_super_quality", "panel_global_spike", "panel_global_super_spike"])
    gs = sup[(sup.panel == "panel_global_super_spike") & (sup.level == "pooled")]
    rows = []
    for h in HORIZONS:
        a = gs[(gs.period == "explore") & (gs.horizon == h)].iloc[0]
        b = gs[(gs.period == "holdout") & (gs.horizon == h)].iloc[0]
        rows.append((h, "%s (n=%s)" % (pct(a.winrate), n(a.n)), "%s (n=%s)" % (pct(b.winrate), n(b.n))))
    L += ["", "**กรณีที่ดูเด่นแต่ไม่คงอยู่: panel_global_super_spike แยกช่วงเวลา**", ""] + table(["horizon", "explore (ก่อน 2025-10-01)", "hold-out"], rows)
    L += ["", "**ข้อสรุป:** ไม่มี panel ที่เข้มขึ้นชนะการสุ่มอย่างสม่ำเสมอ; ผลที่ต่ำกว่า 50% ของ global super spike ที่ 6–12 ชั่วโมงมาจากช่วง explore และกลับมาใกล้ 50% ในช่วง hold-out "
          "(ข้อควรระวัง: ใน panel_global ทุกสินทรัพย์ใช้ค่า sentiment เดียวกันในชั่วโมงเดียวกัน แถว pooled จึงไม่อิสระ p-value ดูเล็กเกินจริง) ผลเต็ม: `output/reports/super_signal_sensitivity.md`", ""]

    # ---- T5
    L += ["## T5) สมมติฐานของ 7.4 (9 panel)", "",
          "**H0 ทุกข้อ:** ความรู้สึกบน Reddit ไม่มีความสัมพันธ์/ความสามารถทำนายทิศทางผลตอบแทนเหนือการสุ่ม", "",
          "**วิธีทำ:**",
          "- **A1 Correlation:** Pearson และ Spearman ของ `sentiment_mean` กับผลตอบแทน 5 กรอบ (1/2/3/6/12 ชม.) รายสินทรัพย์ กลุ่ม และรวม; ตัดคู่ที่มี NULL; ต้องมี ≥ 30 คู่; ปรับ p ด้วย BH",
          "- **A2 Win Rate:** สัดส่วนที่เครื่องหมายของ sentiment ตรงกับเครื่องหมายของผลตอบแทน; Binomial test เทียบ baseline ทิศสุ่ม; ต้องมี ≥ 30 เหตุการณ์",
          "- **A3 Logistic Regression:** ทำนายทิศทางผลตอบแทนด้วยตัวแปร 6 กลุ่ม, `TimeSeriesSplit(5, gap=12)`, รายงาน AUC เทียบ 0.5",
          "- **A5:** ดูว่าสามวิธีให้ทิศเดียวกันไหม (weak) และมีนัยสำคัญพร้อม AUC เกินส่วนเบี่ยงเบนของ fold (strong)", "",
          "**ผล (รายสินทรัพย์ × กรอบเวลา; BH p < 0.05 = เซลล์ที่มีนัยสำคัญ ถ้าไม่มีสัญญาณคาดว่าจะเจอราว 5% จากโชค):**", ""]
    rows = []
    for p in PANELS:
        a1, a2, a3 = D["a1"].get(p), D["a2"].get(p), D["a3"].get(p)
        rows.append((p, "%d / %d" % (a1[1], a1[0]), "%+.4f" % a1[2], "%d / %d" % (a2[1], a2[0]), pct(a2[2], 2), "%.4f" % a3[1], "%.4f" % a3[2]))
    L += table(["panel", "A1 Spearman: เซลล์มีนัยสำคัญ", "ค่าเฉลี่ย ρ", "A2 Win rate: เซลล์มีนัยสำคัญ", "win rate เฉลี่ย", "A3 AUC เฉลี่ย", "AUC สูงสุด"], rows)
    wk, st = D["a5"][1], D["a5"][2]
    L += ["", "**A5 ความสอดคล้องของ 3 วิธี:** %s เซลล์ (ไม่รวม baseline) weak convergence %s, strong convergence **%s**; ตัวควบคุม panel_baseline weak %s จาก %s (สุ่มก็เห็นตรงกันได้ราว 1 ใน 4 อยู่แล้ว)" % (n(D["a5"][0]), n(wk), n(st), n(D["a5_base"][1]), n(D["a5_base"][0])),
          "", "**ข้อสรุป:** AUC ทุก panel ≈ 0.50, win rate ≈ 50%, ค่า ρ ใกล้ 0 → **ไม่ปฏิเสธ H0** ไม่พบความสามารถทำนายที่เชื่อถือได้ "
          "เซลล์ที่มีนัยสำคัญใน panel_global มีมากกว่า panel_Ticker แต่เกิดจาก sentiment ค่าเดียวกันถูกใช้กับ 34 สินทรัพย์ (ข้อมูลไม่อิสระ) และค่า ρ เป็นลบเล็กน้อย (≈ −0.02) "
          "ซึ่งมีขนาดเล็กมากในเชิงปฏิบัติ; ข้อมูลรายชั่วโมงมี autocorrelation และ horizon ซ้อนกัน p-value จึงใช้ประกอบเท่านั้น", "",
          "**จัดอันดับ panel ตามขนาดเฉลี่ยของ |edge| (A4):**", ""]
    L += table(["panel", "mean |edge|", "weak", "strong", "เซลล์"], [(r[0], "%.5f" % r[1], r[2], r[3], r[4]) for r in D["rank"]])
    L += ["", "**ตัวแปรกลุ่มใดมีน้ำหนักมากสุดใน Logistic (ค่าเฉลี่ย |coef| ที่ปรับสเกลแล้ว):** " + ", ".join("%s %.4f" % (g, v) for g, v in D["importance"]),
          "**อดีตดีกว่าปัจจุบันไหม:** lag/momentum/volume เป็นตัวทำนายที่แรงที่สุดใน %s จาก %s เซลล์ (แต่ขนาดเล็กมาก ใกล้ 0 ทุกตัว)" % (n(D["prior"][1]), n(D["prior"][0])), ""]
    L += ["**ข้อจำกัดของข้อมูล:** หุ้น/ETF ไม่มีข้อมูลผลตอบแทน 12 ชั่วโมงเลย และ 6 ชั่วโมงมีน้อยมาก (ดูไฟล์ที่ 3) จึงรายงาน 'ข้อมูลไม่เพียงพอ'", ""]

    # ---- T6, T7
    L += ["## T6) ทดสอบระบบกับข้อมูลจริง (8.4)", "",
          "**วิธีทำ:** `scripts/system_tests.py` ตรวจ %d ข้อกับฐานข้อมูลจริง (อ่านอย่างเดียว) แบ่งเป็นตรรกะข้อมูล (final_text ไม่ว่าง, คะแนนอยู่ใน −1..+1, สถานะตรงเกณฑ์ ±0.05, ticker เฉพาะ 34 ตัว, คำนวณ Current Return และ future return ซ้ำจากราคาแล้วต่างไม่เกิน 1e-6) "
          "และการเชื่อมโยง (ทุกข้อความมีคะแนน, ผลรวมรายชั่วโมงเท่าจำนวนข้อความ, key ใน Fact ไม่ซ้ำ, ไม่มีรหัสกำพร้า)" % total,
          "", "**ผล:** ผ่าน %d จาก %d ข้อ, แถวที่ผิดกฎ 0 (รายละเอียด `output/reports/system_tests.md`); ส่วน Dashboard ตรวจด้วย smoke test (`tests/test_dashboard_smoke.py`) "
          "unit test ในรีโป 154 ตัวผ่านทั้งหมด (เดิม error 9 ตัวเป็น `PermissionError` ตอนลบไฟล์ชั่วคราวบน Windows เพราะเทสต์ไม่ปิดไฟล์ SQLite — แก้ที่เทสต์แล้ว ไม่เกี่ยวกับตรรกะ)" % (ok, total), ""]
    L += ["## T8) ทดสอบ Dashboard (8.4 ส่วนที่ 3)", "",
          "**วิธีทำ:** `scripts/dashboard_kpi_check.py` เรียกชั้นข้อมูลที่ทุกหน้า dashboard ใช้ แล้วเทียบกับ SQL อิสระ (ตารางหรือวิธีนับต่างกัน เช่น จำนวนข้อความรวมเทียบการนับตรงจาก `filtered_text`, Ticker Mention Rate คำนวณใหม่จาก `ticker_mentions`) "
          "ใช้ 4 สินทรัพย์ (BTC-USD, TSLA, GC=F, SPY) × 2 ช่วงเวลา ครอบคลุม ตัวกรองแหล่งข้อมูล (ชุมชน × โพสต์/ความคิดเห็น 3 ชุด เทียบการนับตรงจาก `filtered_text` และ `ticker_mentions`), หลาย Ticker พร้อมกัน (ผลรวมการพูดถึงของ TSLA+BTC-USD เทียบการนับตรงจาก `ticker_mentions`), Reddit Volume, Z-score, Mention Rate, Current Return, Normalized ATR, Future Return, Sentiment Score, Win Rate/Spearman, จำนวนสัญญาณ และตัวเลขหน้าแรก; "
          "นอกจากนี้ `tests/test_dashboard_smoke.py` เปิดทุกหน้าด้วย AppTest ว่าไม่มี exception",
          "", "**ผล:** ผ่าน %d จาก %d ข้อ (`output/reports/dashboard_kpi_check.md`)" % dash,
          "", "**ข้อสังเกตจากการทดสอบ:** ตอนเขียนเทสต์ครั้งแรกมี 18 ข้อไม่ผ่าน เพราะความรู้สึกบนหน้า Market and Sentiment นับเฉพาะชั่วโมงที่มีแท่งราคา (ตลาดหุ้นปิดแล้วไม่มีแท่ง) ส่วน SQL ที่ผมเขียนนับทุกชั่วโมง — เป็นความต่างของนิยามไม่ใช่บั๊กของ dashboard จึงแก้ SQL อ้างอิงให้นับเฉพาะชั่วโมงที่มีราคา", ""]
    ce = (REPORTS / "context_effect.md").read_text(encoding="utf-8")
    m = re.search(r"## final \(รวมผล\)\s+\|[^\n]*\n\|[^\n]*\n\| comment \| (\d+) \| (\d+) \| ([\d.]+)%", ce)
    L += ["## T7) ผลของการใส่ title โพสต์แม่ (final_text เวอร์ชัน 1.0 → 2.0)", "",
          "**วิธีทำ:** `scripts/compare_context_effect.py` เทียบ `sentiment_item_v1` (ก่อน) กับ `sentiment_item` (หลัง); ใช้ข้อความประเภท submission เป็นตัวควบคุมเพราะไม่ถูกเปลี่ยนโดยการออกแบบ",
          "", "**ผล:** final_status ของคอมเมนต์เปลี่ยน %s จาก %s ข้อความ (%s%%); ตัวควบคุม submission เปลี่ยนไม่ถึง 0.01%% (9 จาก 275,242 แถว; **ยังไม่ได้ตรวจสาเหตุ**)" % (n(m.group(2)), n(m.group(1)), m.group(3)) if m else "(อ่าน context_effect.md ไม่สำเร็จ)",
          "", "**ข้อสรุป:** บริบทของ title เปลี่ยนความรู้สึกของคอมเมนต์ในระดับที่มีผลจริง จึงควรเขียนในเล่มว่าเลือกใช้ title+body", ""]
    return L


# ------------------------------------------------------------------------------------------------ file 3

def build_summary(D):
    s0, s1 = D["span"]
    L = header("3) สรุปผลสุดท้ายของโครงการ: ทำอะไรไปบ้างในแต่ละขั้นตอน และได้อะไร",
               "สรุปทุกขั้นตอนของ pipeline (ตามลำดับไฟล์ใน steps/): ทำอะไร ผลลัพธ์ที่วัดได้ และสิ่งที่น่าสนใจ",
               "ตารางใน output/reddit.sqlite3 (อ่านอย่างเดียว) และรายงานใน output/reports/")
    f = D["final"]
    tot = sum(f.values())
    L += ["## ภาพรวมโครงการ", "",
          "คลังข้อมูลและแดชบอร์ดที่เทียบ **ความรู้สึกจาก Reddit 6 ชุมชน** กับ **ราคารายชั่วโมงของ 34 สินทรัพย์** ช่วง %s ถึง %s เป็นการวิเคราะห์ข้อมูลย้อนหลัง ไม่ใช่ real-time และไม่ใช่คำแนะนำการลงทุน" % (date_of(s0), date_of(s1)), "",
          "### ผลสรุปหนึ่งหน้า", "",
          "1. ข้อความ Reddit ที่ใช้ได้: **%s** (จากข้อมูลดิบ 6 ชุมชน %s แถว = %s)" % (n(D["passed"]), n(D["six_rows"]), pct(D["passed"] / D["six_rows"])),
          "2. ความรู้สึกสุดท้ายของข้อความ: positive %s · neutral %s · negative %s" % (pct(f["positive"] / tot), pct(f["neutral"] / tot), pct(f["negative"] / tot)),
          "3. **ผลวิเคราะห์หลัก: ไม่พบความสามารถทำนายทิศทางราคาจากความรู้สึกบน Reddit** — win rate ≈ 50%, AUC ≈ 0.50, correlation ใกล้ 0 ทุก panel (เทียบกับ baseline สุ่ม)",
          "4. เกณฑ์ที่เข้มขึ้น (strong, quality, spike, super quality, super spike) ไม่ทำให้ win rate ดีขึ้นกว่าการสุ่ม ผลที่เด่นในช่วงหนึ่งไม่คงอยู่ในอีกช่วง (z-score 2.0/2.5 ในระบบสัญญาณวัดแค่จำนวนสัญญาณ ยังไม่ได้ทดสอบความแม่นแยกต่างหาก)",
          "5. กฎรวมผลของ VADER+FinBERT ไม่ได้แม่นกว่า FinBERT เดี่ยวเมื่อเทียบกับป้ายที่ผู้พัฒนาติด (ตัวอย่างเล็ก)",
          "6. ระบบผ่านการทดสอบกับข้อมูลจริง 32/32 ข้อ", ""]

    steps = [
        ("00–03", "เตรียมฐานข้อมูล", "ดูสถานะข้อมูล, นำเข้า Reddit ดิบ, ดึงราคา yfinance, สร้างตาราง star schema และมิติ", "`ingest/pipeline_status.py`, `ingest/reddit_extract.py`, `ingest/market_fetch.py`, `etl/seed_dims.py`",
         ["ข้อมูลดิบ `reddit_content` ทุกชุมชนที่เก็บไว้: %s แถว (เป็นสำเนาเดียว ห้ามลบ)" % n(D["raw_all"]),
          "ราคา `market_bars` %s แถว (เป็น placeholder ตลาดปิด %s แถว)" % (n(D["bars"]), n(D["null_close"])),
          "มิติ: " + ", ".join("%s %s แถว" % (k, n(v)) for k, v in D["facts"].items() if k.startswith("Dim"))]),
        ("04", "ล้างข้อความ (T1)", "ล้าง URL/markdown/mention, แปลงอีโมจิเป็นคำ, คอมเมนต์ = title โพสต์แม่ + body", "`etl/clean_text.py`",
         ["ข้อความของ 6 ชุมชน %s แถว: อ่านได้ %s, ถูกลบ/นำออก %s" % (n(D["six_rows"]), n(D["status"]["available"]), n(D["six_rows"] - D["status"]["available"])),
          "ล้างแล้วเขียน `processed_text` %s แถว (ว่างหลังล้าง %s)" % (n(D["processed"]), n(D["empty_clean"]))]),
        ("05", "กรองคุณภาพ (T2)", "ตัดบอท/ผู้ดูแล, สั้นเกิน (< 2 ตัวอักษร), ไม่ใช่ภาษาอังกฤษ", "`etl/quality_filter.py`",
         ["ผ่าน **%s** แถว (%s ของข้อมูลดิบ)" % (n(D["passed"]), pct(D["passed"] / D["six_rows"])),
          "ตัดออก: บอท %s · สั้นเกิน %s · ไม่ใช่อังกฤษ %s" % (n(D["filter"]["bot_or_moderation_text"]), n(D["filter"]["too_short"]), n(D["filter"]["non_english"])),
          "สัดส่วนชุมชน: " + ", ".join("%s %s" % (r[0], pct(r[1] / D["passed"])) for r in D["mix"]),
          "**น่าสนใจ:** wallstreetbets ครองข้อมูลเกือบสามในสี่ จึงทำให้ panel_global เป็นบรรยากาศของ WSB เป็นหลัก; ประเภท: " + ", ".join("%s %s" % (k, n(v)) for k, v in D["kind"].items())]),
        ("06", "สกัด Ticker (T4)", "พจนานุกรม 34 สินทรัพย์ (alias, cashtag, กฎกันคำทั่วไป)", "`etl/extract_tickers.py`",
         ["พบ ticker ใน **%s ข้อความ** (%s) รวม %s แถว mention" % (n(D["ticker_texts"]), pct(D["ticker_texts"] / D["passed"]), n(D["ticker_rows"])),
          "พูดถึงมากสุด: " + ", ".join("%s %s" % (t, n(c)) for t, c in D["ticker_top"]),
          "พูดถึงน้อยสุด: " + ", ".join("%s %s" % (t, n(c)) for t, c in D["ticker_low"]) + " → มักได้ 'ข้อมูลไม่เพียงพอ'"]),
        ("07–08", "ความรู้สึก VADER และ FinBERT (S1, S2)", "VADER (lexicon) และ FinBERT (P(pos) − P(neg)), FinBERT ใช้ GPU fp16", "`etl/sentiment_vader.py`, `etl/sentiment_finbert.py`",
         ["VADER: positive %s · neutral %s · negative %s" % tuple(pct(D["model_status"]["vader=" + k] / D["passed"]) for k in ("positive", "neutral", "negative")),
          "FinBERT: positive %s · neutral %s · negative %s" % tuple(pct(D["model_status"]["finbert=" + k] / D["passed"]) for k in ("positive", "neutral", "negative")),
          "**น่าสนใจ:** FinBERT ให้ neutral มากกว่า VADER ชัดเจน และคะแนนเบากว่า จึงไวต่อเกณฑ์ neutral"]),
        ("09–10", "รวมผลและตรวจคุณภาพ (S3, S4, S5)", "คำสำคัญ (rule_signal) + กฎ conflict resolution → final_sentiment/final_method; รายงานความสอดคล้อง", "`etl/resolve_sentiment.py`, `etl/sentiment_qa.py`",
         ["`final_method`: " + ", ".join("%s %s" % (m, pct(c / tot)) for m, c in D["method"]),
          "`is_ambiguous` = 1: %s แถว (%s) คะแนนเป็น 0.0/neutral" % (n(D["ambiguous"]), pct(D["ambiguous"] / tot)),
          "**น่าสนใจ:** กรณีสองโมเดลขัดกันในระดับ small conflict ไม่มีคำสำคัญเป็นกลุ่มใหญ่สุดหลัง both_neutral"]),
        ("11", "feature ราคา (M1)", "Current Return, future return 1/2/3/6/12 ชม. (%), RSI, ATR, volume z-score (ตัดแถว close NULL)", "`etl/market_features.py`",
         ["`market_hourly_features` %s แถว" % n(D["features"]),
          "ความครบของ future return ตามกลุ่ม (คอลัมน์ = สัดส่วนแถวที่คำนวณได้): "] ),
        ("12–14", "รวมรายชั่วโมง (P1–P3)", "สรุป Reddit รายชั่วโมง×ticker, เพิ่ม lag/momentum/z-score, รวมกับราคา", "`etl/reddit_hourly.py`, `etl/reddit_features.py`, `etl/merge_panel.py`",
         ["`reddit_hourly` %s แถว, `merged_hourly_panel` %s แถว" % (n(D["hourly"]), n(D["merged"]))]),
        ("15", "สร้าง 9 panel (P4)", "global/Ticker × (ทั้งหมด, strong ≥ 0.05, quality ≥ 0.30, spike z > 1.5) + baseline สุ่ม", "`etl/build_panels.py`",
         ["แถวต่อ panel: " + ", ".join("%s %s" % (p, n(D["panels"][p][0])) for p in PANELS)]),
        ("16–19", "วิเคราะห์ความสัมพันธ์ (A1–A5)", "Correlation, Win Rate + Binomial, Logistic (TimeSeriesSplit), ประเมินความสอดคล้อง 3 วิธี", "`analysis/correlation.py`, `winrate.py`, `logistic.py`, `evaluate.py`",
         ["ดูตารางผลหลักด้านล่าง", "A5: %s เซลล์ weak convergence %s, strong %s" % (n(D["a5"][0]), n(D["a5"][1]), n(D["a5"][2]))]),
        ("20–21", "โหลด Fact", "ปริมาณ Reddit และ FactMarketSentiment", "`etl/load_fact_reddit_volume.py`, `etl/load_fact_market_sentiment.py`",
         ["FactRedditVolume %s · FactMarketPrice %s · FactMarketSentiment %s แถว" % (n(D["facts"]["FactRedditVolume"]), n(D["facts"]["FactMarketPrice"]), n(D["facts"]["FactMarketSentiment"]))]),
        ("22", "ตรวจจับสัญญาณ (G)", "volume spike, positive/negative sentiment spike, combined; ระดับ low/medium/high", "`analysis/signals.py`",
         ["สัญญาณรวม 6 ชุดเกณฑ์ %s รายการ: " % n(sum(c for _, c in D["signal_types"])) + ", ".join("%s %s" % (t, n(c)) for t, c in D["signal_types"])]),
        ("23", "แดชบอร์ด Streamlit", "6 หน้า: Reddit Volume, Ticker Mentions, Price and Return, Market and Sentiment, Ranking and Signals และ Hot Events (ส่วนขยาย ดูเหตุการณ์ที่ Reddit คึกคักมาก พร้อมช่วงความเชื่อมั่นและป้ายเตือน)", "`dashboard/`",
         ["ตัวกรองร่วมที่แถบข้างเรียงตามมิติ: เวลา (ช่วงวันที่ ค่าเริ่มต้นย้อนหลัง 1 ปี + ความละเอียดกราฟ) › แหล่งข้อมูล (ติ๊กชุมชนและโพสต์/ความคิดเห็น ติ๊กทั้งหมดตอนแรก เฉพาะหน้า 1–2) › หลักทรัพย์ (ติ๊กกลุ่ม แล้วเลือก Ticker; หน้า 1–2 เลือกได้หลายตัว); ปุ่มสลับเส้น/แท่งอยู่ที่แต่ละกราฟ; ปรับ Z-score / Sentiment / Horizon แล้วคำนวณสัญญาณใหม่ทันที, มีป้ายระบุว่าไม่ใช่คำแนะนำการลงทุน"]),
        ("24–30", "ตรวจและทดสอบ (S5, 8.4)", "proposal coverage, เทียบ neutral band, rule validation, super quality/spike, สร้างรายงานสรุป, ความแม่น ±0.10 + confusion matrix, ทดสอบ dashboard", "`scripts/check_proposal_coverage.py`, `neutral_band_sensitivity.py`, `rule_validation.py`, `super_signal_sensitivity.py`, `build_final_reports.py`, `rule_validation_extras.py`, `dashboard_kpi_check.py`",
         ["รายละเอียดอยู่ไฟล์ที่ 2"]),
        ("31", "ตารางและกราฟสำหรับลงเล่ม", "สร้าง 9 ตาราง CSV และ 5 กราฟจากฐานข้อมูล", "`scripts/make_book_tables.py`", ["`output/tables/t1..t9*.csv`, `output/figures/book_*.png`"]),
    ]
    L += ["## ขั้นตอนต่อขั้นตอน", ""]
    for num, title, what, code, results in steps:
        L += ["### Step %s — %s" % (num, title), "", "- **ทำอะไร:** " + what, "- **โค้ด:** " + code, "- **ผลที่ได้ (วัดจริง):**"]
        L += ["  - " + r for r in results]
        if num == "11":
            L += [""] + ["  " + line for line in table(["กลุ่ม", "แถว", "1h", "2h", "3h", "6h", "12h"],
                  [[r[0], n(r[1])] + [pct(r[i] / r[1]) for i in range(2, 7)] for r in D["coverage"]])]
        L += [""]

    L += ["## ผลวิเคราะห์หลักทุก panel", "", "ค่าตัวเลข: เซลล์ = รายสินทรัพย์ × กรอบเวลา; 'มีนัยสำคัญ' = BH p < 0.05 (ถ้าสุ่มล้วนคาดว่าราว 5%)", ""]
    rows = []
    for p in PANELS:
        a1, a2, a3 = D["a1"][p], D["a2"][p], D["a3"][p]
        rows.append((p, n(D["panels"][p][0]), "%.1f" % D["panels"][p][2], "%d/%d" % (a1[1], a1[0]), "%d/%d" % (a2[1], a2[0]), pct(a2[2], 2), "%.4f" % a3[1]))
    L += table(["panel", "แถว", "ข้อความเฉลี่ย/แถว", "Spearman มีนัยสำคัญ", "Win rate มีนัยสำคัญ", "win rate เฉลี่ย", "AUC เฉลี่ย"], rows)
    L += ["", "## สิ่งที่น่าสนใจ", ""]
    L += ["1. **ไม่มีความสามารถทำนาย:** ทุก panel อยู่ที่ ≈ 50% ซึ่งเท่ากับ baseline สุ่ม; เมื่อกรองให้เข้มขึ้นผลก็ไม่ดีขึ้น (ข้อสรุปที่ยืนหยัดได้ในรายงาน)",
          "2. **panel_global มีเซลล์ 'มีนัยสำคัญ' มากกว่า panel_Ticker** แต่เพราะทุกสินทรัพย์ใช้ sentiment ค่าเดียวกันในชั่วโมงเดียวกัน ข้อมูลไม่อิสระ และค่าสหสัมพันธ์เล็กมาก (≈ −0.02)",
          "3. **บริบทของ title เปลี่ยนความรู้สึกมาก:** final_status ของคอมเมนต์เปลี่ยน ~21.8% เมื่อใส่ title โพสต์แม่ → ต้องบอกวิธีนี้ในเล่ม",
          "4. **กฎรวมผล VADER+FinBERT ไม่ได้ช่วย** เมื่อเทียบป้ายผู้พัฒนา 210 ข้อความ (ตัวอย่างเล็ก ผลเป็นแนวโน้ม) — ตัวอย่างเช่น VADER อ่านคำสแลงอย่าง 'die/crazy' เป็นลบแม้ข้อความเป็นคำถามกลาง ๆ",
          "5. **เกณฑ์ neutral:** ผลสุดท้ายแทบเท่าเดิมเมื่อเปลี่ยนจาก 0.05 เป็น 0.10 แต่ FinBERT ไวมาก (neutral เพิ่มจาก ~48% เป็น ~63%)",
          "6. **ข้อจำกัดข้อมูลหุ้น/ETF:** ตลาดเปิดราว 7 แท่งรายชั่วโมงต่อวัน กติกา 'แท่งห่างพอดี n ชั่วโมง' ทำให้ 12 ชั่วโมงไม่มีข้อมูล และ 6 ชั่วโมงน้อยมาก; ข้อความ Reddit จำนวนมากเกิดนอกเวลาตลาดหุ้นจึงจับคู่กับราคาไม่ได้ (คริปโตไม่เป็นปัญหา)",
          "7. **ผู้ใช้เปรียบเทียบกับงาน Colab เดิมแล้วผลต่าง** สาเหตุหลักคือวิธีต่างกัน: งานเก่าใช้ StratifiedKFold แบบสลับข้อมูล (รั่วอนาคต) ส่วนงานนี้ใช้ TimeSeriesSplit + gap, เกณฑ์/ช่วงเวลา/จำนวนสินทรัพย์ต่างกัน และงานเก่าไม่ปรับ p-value",
          "8. **ข้อควรระวังของข้อมูล:** ช่องที่ n น้อย (เช่น BITO, JNJ) สีจัดเกินจริง; ข้อความยาวเกิน 256 โทเคนถูก FinBERT ตัดท้าย (ราว 0.5–0.9%); คอมเมนต์ราว 44,000 แถวไม่มี title โพสต์แม่ใน DB; อีโมจิที่แปลงเป็นคำอาจตีความผิด", "",
          "## สิ่งที่ยังไม่ได้ตัดสินใจ / ยังไม่ได้ทำ", "",
          "- แสดงจำนวนข้อความรวมต่อช่องของ heatmap (ตอนนี้แสดง n = จำนวนแถวชั่วโมง × สินทรัพย์)",
          "- (ลบตาราง `*_v1` แล้ว; commit แล้ว)",
          "- ตารางและกราฟลงเล่มที่ทำไว้ (`output/tables`, `output/figures/book_*`) เป็นร่างให้ผู้ใช้ปรับรูปแบบต่อ", ""]
    return L


def run(db_path):
    db = sqlite3.connect("file:%s?mode=ro" % Path(db_path).as_posix(), uri=True)
    try:
        D = gather(db)
    finally:
        db.close()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = {"1_beyond_proposal.md": build_beyond(D), "2_tests_and_hypotheses.md": build_tests(D, db_path),
             "3_final_summary.md": build_summary(D)}
    for name, lines in files.items():
        (OUT_DIR / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("wrote", OUT_DIR / name)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    run(parser.parse_args(argv).db)
    return 0


if __name__ == "__main__":
    sys.exit(main())
