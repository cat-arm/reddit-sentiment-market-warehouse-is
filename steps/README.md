# ลำดับรัน (เริ่มที่ 01 แล้วไล่ตามเลข)

รันจากโฟลเดอร์โปรเจกต์: `python steps/<ชื่อไฟล์>.py [ตัวเลือก]` (เปิด venv ก่อน: `.\venv\Scripts\Activate.ps1`)

ไฟล์ในโฟลเดอร์นี้เป็นตัวเรียก (launcher) ของโค้ดจริงใน `etl/`, `analysis/`, `scripts/` และสคริปต์ที่ root ตัวเลือกบรรทัดคำสั่งส่งต่อให้โค้ดจริงทุกตัว เช่น `python steps/04_clean_text.py --help`

| เลข | ไฟล์ | ทำอะไร | โค้ดจริง |
|---|---|---|---|
| 00 | `00_pipeline_status.py` | ดูสถานะข้อมูลรายเดือน (Reddit import / ราคา) | `pipeline_status.py` |
| 01 | `01_extract_reddit.py` | ดึง/นำเข้าข้อมูล Reddit ดิบ -> reddit_content | `reddit_extract.py` |
| 02 | `02_fetch_market.py` | ดึงราคารายชั่วโมง 34 สินทรัพย์ (yfinance) -> market_bars | `market_fetch.py` |
| 03 | `03_create_schema_and_dims.py` | สร้างตาราง star schema (db/schema.sql) และเติม Dim ทั้ง 6 | `etl/seed_dims.py` |
| 04 | `04_clean_text.py` | ล้างข้อความ -> processed_text (T1) | `etl/clean_text.py` |
| 05 | `05_quality_filter.py` | กรองคุณภาพ/ภาษา -> text_filter, filtered_text (T2) | `etl/quality_filter.py` |
| 06 | `06_extract_tickers.py` | สกัด Ticker จากข้อความ -> ticker_mentions (T4) | `etl/extract_tickers.py` |
| 07 | `07_sentiment_vader.py` | ความรู้สึกด้วย VADER -> sentiment_vader (S1) | `etl/sentiment_vader.py` |
| 08 | `08_sentiment_finbert.py` | ความรู้สึกด้วย FinBERT (ใช้ GPU) -> sentiment_finbert (S2) | `etl/sentiment_finbert.py` |
| 09 | `09_resolve_sentiment.py` | รวม VADER+FinBERT+keyword และแก้ conflict -> sentiment_item (S3, S4) | `etl/resolve_sentiment.py` |
| 10 | `10_sentiment_qa.py` | ตรวจคุณภาพความรู้สึก -> sentiment_qa (S5) | `etl/sentiment_qa.py` |
| 11 | `11_market_features.py` | feature ราคา (return, RSI, ATR, Z-score) -> market_hourly_features, FactMarketPrice (M1) | `etl/market_features.py` |
| 12 | `12_reddit_hourly.py` | สรุป Reddit รายชั่วโมงต่อ Ticker -> reddit_hourly (P1) | `etl/reddit_hourly.py` |
| 13 | `13_reddit_features.py` | lag / momentum / Z-score -> reddit_hourly_features (P2) | `etl/reddit_features.py` |
| 14 | `14_merge_panel.py` | รวมราคา+Reddit -> merged_hourly_panel (P3) | `etl/merge_panel.py` |
| 15 | `15_build_panels.py` | สร้าง 9 panel -> panels (P4) | `etl/build_panels.py` |
| 16 | `16_correlation.py` | Pearson/Spearman -> analysis_results (A1) | `analysis/correlation.py` |
| 17 | `17_winrate.py` | Historical Win Rate + binomial test -> analysis_results (A2) | `analysis/winrate.py` |
| 18 | `18_logistic.py` | Logistic regression (time split) -> analysis_results (A3) | `analysis/logistic.py` |
| 19 | `19_evaluate.py` | สรุปผล 3 วิธี/กลุ่มสินทรัพย์ -> evaluation_*, output/reports (A4, A5) | `analysis/evaluate.py` |
| 20 | `20_load_fact_reddit_volume.py` | โหลด FactRedditVolume (ปริมาณรวม + ticker_mention_count) (T5) | `etl/load_fact_reddit_volume.py` |
| 21 | `21_load_fact_market_sentiment.py` | โหลด FactMarketSentiment (ต้องรันหลัง 17) (F1) | `etl/load_fact_market_sentiment.py` |
| 22 | `22_detect_signals.py` | ตรวจจับสัญญาณ -> signal_events, signal_summary, v_signal_list (G) | `analysis/signals.py` |
| 23 | `23_run_dashboard.py` | เปิด Streamlit dashboard | `dashboard/app.py` |
| 24 | `24_check_proposal_coverage.py` | ตรวจว่า DB + dashboard ตอบ proposal ครบ -> output/reports/proposal_coverage.md | `scripts/check_proposal_coverage.py` |

หมายเหตุ
- 21 ต้องรันหลัง 17 (ดึง win rate จาก analysis_results) และ 20 รันหลัง 06 (ใช้ ticker_mentions)
- 01 ใช้ `fetch <เดือน>` (ต้องมี aria2c) หรือ `import`; ดู `python steps/01_extract_reddit.py --help`
- 08 ใช้ GPU และนานหลายชั่วโมงกับข้อมูลทั้งหมด
- `24` อ่านฐานข้อมูลอย่างเดียว
