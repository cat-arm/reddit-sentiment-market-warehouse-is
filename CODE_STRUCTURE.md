# CODE_STRUCTURE.md — โครงสร้างโค้ด และแผนที่ proposal → โค้ด

ไฟล์นี้มีไว้กัน **"ลืมทำเป็นโค้ด"** — ตอนทำรูปเล่ม ทุกขั้นตอนต้องมีโค้ดที่รันซ้ำได้ และทุกตัวเลข/ตาราง/กราฟในเล่มต้องไล่ย้อนถึงสคริปต์ได้

## 1) กติกา 6 ข้อ

1. **ทุกขั้นตอนของ pipeline = สคริปต์ `.py` ที่สั่งรันจาก command line ได้** (มี `argparse`) — ไม่ทำใน notebook, ไม่รัน SQL มือแล้วจำผล, ไม่แก้ตารางด้วยมือ
2. **รันซ้ำได้และรันต่อได้** (idempotent/resumable): รันซ้ำแล้วไม่ได้แถวซ้ำ; งานยาว (FinBERT, ticker extraction) เก็บ checkpoint ได้
3. **ค่าตั้งอยู่ใน `configs/`** (6 ชุมชน, 34 ticker + alias, threshold, keyword) ไม่ hard-code ซ้ำหลายไฟล์
4. **ตัวเลข ตาราง กราฟที่ลงเล่ม ต้องมาจากสคริปต์** (`scripts/` และ `reports/`) ไม่ใช่ copy จาก query ที่รันมือ — รวมถึงตัวเลขที่เคยคำนวณมือระหว่างทำโปรเจกต์ (จำนวนแถวต่อชุมชน, สัดส่วน removed/deleted, gap ของราคา, `close IS NULL`, ความยาวข้อความ) ให้ย้ายเป็นสคริปต์ `scripts/data_profile.py`
5. **notebook ใช้สำรวจเท่านั้น** — ถ้าผลถูกนำไปใช้จริง ต้องย้ายเป็น `.py` (โค้ดเก่า `old_code/reddit_6.ipynb` ใช้เป็นตัวอย่างอ้างอิง ไม่ใช่ส่วนของระบบ)
6. **ทุกการรันบันทึก `run_id`, เวอร์ชันโค้ด, config, seed** (ใช้ `ingest/pipeline_logs.py` ที่มีอยู่) เพื่อให้ตรวจย้อนหลังได้

## 2) โครงโฟลเดอร์ (✅ มีแล้ว · ⬜ ยังไม่ทำ)

```
reddit-sentiment-market-warehouse/
  README.md  CLAUDE.md  TASKS.md  SYSTEM_BLUEPRINT_TH.md  CODE_STRUCTURE.md
  requirements.txt            ✅  (+ requirements-sentiment.txt ✅ torch CUDA/transformers/nltk, requirements-analysis.txt ✅ รวม pypdf)
  ingest/                     ✅  ขั้นนำเข้าข้อมูล (ย้ายจาก root 2026-10-28)
    reddit_extract.py         ✅  7.1 นำเข้า Reddit (.zst → SQLite)
    market_fetch.py           ✅  7.2 ดึงราคา yfinance
    pipeline_status.py        ✅  รายงานสถานะ (Q0 ยังต้องแก้ให้เร็ว)
    pipeline_logs.py          ✅  log การรัน
  configs/                    ✅  subreddits.yaml, tickers.yaml, sentiment.yaml, detection.yaml
  db/                         ✅  schema.sql (รูปที่ 2–4), indexes.sql
  etl/                        ✅  T1–T5, S1–S5, M1, P1–P4, Fact loaders (ดูตารางข้อ 3)
  analysis/                   ✅  correlation, winrate, logistic, evaluate, signals, results_store, figure_style (สี/คำอธิบายของ heatmap)
  dashboard/                  ✅  Streamlit หน้าแรก + 7 หน้า (หน้า 5 Statistical Analysis (แดชบอร์ดที่ 2 ตามตารางที่ 17), หน้า 6 Lead and Lag) (หน้า 7 Hot Events = ส่วนขยาย; data.py = ชั้น query อ่านอย่างเดียว)
  steps/                      ✅  ตัวเรียกที่มีเลขลำดับ 00–33 (เริ่มที่ 01) ดู steps/README.md
  scripts/                    ✅  ตรวจ/ทดสอบ/สรุปผล: system_tests, dashboard_kpi_check, rule_validation(+extras), neutral_band, super_signal, make_book_tables, build_final_reports ฯลฯ
  reports/                    —   (ใช้ scripts/make_book_tables.py แทน → output/tables, output/figures/book_*)
  docs/                       ✅  benchmark_finbert.md, METHOD_DECISIONS_NOT_IN_PROPOSAL.md, USER_MANUAL_TH.md (§8.5)
  tests/                      ✅  มี 4 ไฟล์ (เสีย 9/18 บน Windows) + 1 ไฟล์ว่าง
  old_code/                   —   MVP เก่า อ้างอิงเท่านั้น (gitignored)
  data/  output/              —   ข้อมูล/ผลลัพธ์ (gitignored)
```

สคริปต์ขั้นนำเข้าข้อมูล 4 ตัว (reddit_extract, market_fetch, pipeline_status, pipeline_logs) ย้ายเข้า `ingest/` เมื่อ 2026-10-28 ตามที่ผู้ใช้สั่ง (เดิมอยู่ root); import ใช้ `from ingest.pipeline_logs import ...`, รันได้ทั้ง `python steps/0X_*.py`, `python -m ingest.<module>` และ `python ingest/<file>.py`

## 3) แผนที่ proposal → โค้ด → ตารางผลลัพธ์

| ส่วนของ proposal | งาน (TASKS) | สคริปต์ | ผลลัพธ์ | สถานะ |
|---|---|---|---|---|
| 7.1 นำเข้า Reddit | — | `ingest/reddit_extract.py` | `reddit_content` | ✅ |
| 7.1 ล้างข้อความ | T1 | `etl/clean_text.py` (+ `etl/common.py`, `configs/subreddits.yaml`) | `processed_text` | ✅ เขียน+ทดสอบแล้ว · ⬜ ยังไม่ได้รันกับฐานข้อมูลหลัก |
| 7.1 กรองคุณภาพ/ภาษา | T2 | `etl/quality_filter.py` | `text_filter`, `data_quality_audit`, view `filtered_text` | ✅ รันแล้ว 2026-10-10 |
| 7.1 พจนานุกรม Ticker | T3 | `configs/tickers.yaml`, `etl/ticker_dict.py` | — | ✅ |
| 7.1 สกัด Ticker | T4 | `etl/extract_tickers.py` | `ticker_mentions` | ✅ รันแล้ว 2026-10-10 |
| 7.1 Fact + dashboard 7.1-1 | T5, D1 | `etl/load_fact_reddit_volume.py`, `dashboard/pages/1_Reddit_Volume.py` (ปริมาณรวมทั้ง Reddit; เลือกหลักทรัพย์บางตัวแล้วเปลี่ยนเป็นจำนวนครั้งที่ถูกพูดถึง), `dashboard/pages/2_Ticker_Mentions.py` (สินทรัพย์ที่ถูกพูดถึง หลาย Ticker); ตัวกรองกลางใน `dashboard/common.py` เรียงเวลา › แหล่งข้อมูล (ติ๊กชุมชน/ประเภท) › หลักทรัพย์ (กลุ่ม › ติ๊ก Ticker หลายตัว ติ๊กทั้งหมดตอนแรก) หน้าตาเหมือนกันทุกบล็อก; การ์ดตัวเลขบนสุดของทุกหน้าใช้ `common.kpi_cards` | `FactRedditVolume` | ✅ รันแล้ว 2026-10-11 |
| 7.2 ดึงราคา | M2 | `ingest/market_fetch.py` | `market_bars` | ✅ (gap ~0.5% รอปิด) |
| 7.2 feature ราคา | M1 | `etl/market_features.py` | `market_hourly_features`, `FactMarketPrice` | ✅ รันแล้ว 2026-10-10 |
| 7.2 dashboard 7.2-1 | D2 | `dashboard/pages/3_Price_and_Return.py` | — | ✅ รันแล้ว 2026-10-11 |
| schema / dimension | W2, W4 | `db/schema.sql`, `etl/seed_dims.py` | Dim\* ทั้ง 6, Fact ทั้ง 3 | ✅ สร้างแล้ว 2026-10-10 (Fact ของ price/sentiment ยังว่าง) |
| 7.3 วัดความเร็ว FinBERT | S0 | `scripts/benchmark_finbert.py` | `docs/benchmark_finbert.md`, `output/benchmark_finbert.json` | ✅ |
| 7.3 VADER / FinBERT | S1, S2 | `etl/sentiment_vader.py`, `etl/sentiment_finbert.py` | `sentiment_vader`, `sentiment_finbert` (S4 จะรวมเป็น `sentiment_item`) | ✅ รันแล้ว 2026-10-10 |
| 7.3 ย้อนดูผลของ title โพสต์แม่ (final_text 2.0) | — | `scripts/archive_sentiment_v1.py`, `scripts/compare_context_effect.py` | `*_v1`, `output/reports/context_effect.md` | ✅ 2026-10-24 |
| 7.1 พิสูจน์รูปแบบ final_text (2 แบบ) | — | `scripts/verify_final_text_forms.py` | `output/reports/final_text_forms.md` | ✅ 2026-10-25 |
| 8.4 ทดสอบระบบกับข้อมูลจริง (ตรรกะ + เชื่อมโยง) | Q | `scripts/system_tests.py` | `output/reports/system_tests.md` | ✅ 2026-10-25 |
| 8.4 ทดสอบ dashboard (ตัวเลขเทียบ SQL ตรง) | Q4 | `scripts/dashboard_kpi_check.py` (step 30), `tests/test_dashboard_smoke.py` | `output/reports/dashboard_kpi_check.md` | ✅ 2026-10-25 |
| ส่วนขยาย: หน้า Hot Events (ชั่วโมงคึกคัก + ช่วงความเชื่อมั่น) | D6 | `dashboard/pages/6_Hot_Events.py`, `dashboard.data.hot_events` | — | ✅ 2026-10-25 |
| 7.5 แดชบอร์ดที่ 2 Statistical Analysis (แดชบอร์ดที่ 2 ตามตารางที่ 17) (Win Rate, p-value Spearman/Pearson คำนวณสดตามตัวกรอง 9 panel; Logistic ผลเก็บไว้) | — | `dashboard/pages/5_Statistical_Analysis.py`, `dashboard/data.py` (`panel_samples`, `stat_table`, `bh_adjust`, `global_hourly`, `logistic_results`), `tests/test_dashboard_filters.py`, `tests/test_dashboard_sentiment.py` | คำนวณสดจาก `reddit_hourly_community`, `reddit_hourly_global` + `market_hourly_features`; อ่าน `analysis_results` (Logistic) | ✅ 2026-10-30 |
| ส่วนขยาย: หน้า 6 Lead and Lag (ใครขยับก่อน ความรู้สึกหรือราคา) | — | `dashboard/pages/7_Lead_and_Lag.py`, `dashboard/data.py` (`lag_correlation`, `past_return`, `return_buckets`) | คำนวณสดจากชั่วโมงที่ผ่านตัวกรอง | ✅ 2026-10-30 |
| 7.4 ส่วนขยาย: เกณฑ์ที่เข้มขึ้น super quality / super spike | — | `scripts/super_signal_sensitivity.py` (step 27) | `output/reports/super_signal_sensitivity.md/.csv` | ✅ 2026-10-25 |
| 7.6 ส่วนขยาย: ความแม่นของเกณฑ์ Z-score × ความรู้สึก (กริด) | — | `scripts/z_sentiment_grid.py` (step 32) | `output/reports/z_sentiment_grid.md/.csv` | ✅ 2026-10-25 |
| สรุปเล่ม: ส่วนที่ทำเกิน proposal / การทดสอบและสมมติฐาน / สรุปผลสุดท้าย | — | `scripts/build_final_reports.py` (step 28) | `output/reports/final/1_*.md, 2_*.md, 3_*.md` | ✅ 2026-10-25 |
| รูป A1/A2: สีแดง-เขียว + n ทุกช่อง + คำอธิบาย panel | A1, A2 | `analysis/figure_style.py` (ใช้โดย `analysis/correlation.py`, `analysis/winrate.py`) | `output/figures/a1_*.png`, `a2_*.png` | ✅ 2026-10-25 |
| 7.3 keyword + แก้ conflict | S3, S4 | `etl/resolve_sentiment.py`, `configs/sentiment.yaml` | `sentiment_item` (final_sentiment/status/method + `is_ambiguous`) | ✅ รันแล้ว 2026-10-10; ปรับตาม proposal ฉบับอนุมัติ 2026-10-24 (`same_direction_far`, `is_ambiguous`, `--migrate`) |
| 7.3 ตรวจเกณฑ์ neutral 0.05 เทียบ 0.10 | S5 | `scripts/neutral_band_sensitivity.py` (step 25), `scripts/rule_validation_extras.py` (step 29: ความแม่นเทียบป้าย + confusion matrix) | `output/reports/neutral_band_sensitivity.md/.csv`, `output/reports/rule_validation/band_and_confusion.md`, `output/figures/s5_confusion_matrices.png` | ✅ 2026-10-25 |
| 7.3 ตรวจกฎรวมผลด้วยตัวอย่างติดป้ายเอง | S5 | `scripts/rule_validation.py sample/evaluate` (step 26) | `output/reports/rule_validation/` | ✅ ผู้ใช้ติดป้ายแล้ว 2026-10-25 |
| 7.3 QA | S5 | `etl/sentiment_qa.py` | `sentiment_qa` | ✅ รันแล้ว 2026-10-10 |
| 7.3 ซ่อมป้าย neutral band | — | `scripts/recompute_status_band.py` | แก้ `vader_status` 771 แถว | ✅ 2026-10-10 |
| 7.4 สรุปรายชั่วโมง | P1, P2 | `etl/reddit_hourly.py`, `etl/reddit_features.py` | `reddit_hourly`, `reddit_hourly_features` | ✅ รันแล้ว 2026-10-10 |
| 7.5 ความรู้สึกแยกตามชุมชน (DimSentimentSource) | P1b | `etl/reddit_hourly_community.py` (step 33), `tests/test_reddit_hourly_community.py` | `reddit_hourly_community` (ต่อ Ticker) และ `reddit_hourly_global` (ทั้งตลาด) แยกตามชุมชน × แบบจำลอง (VADER+FinBERT, VADER, FinBERT) × variant (all, strong, quality); รวมชุมชนแล้วเท่ากับ `reddit_hourly` ทุกชั่วโมง (848,002 ชั่วโมง ต่าง 0) | ✅ 2026-10-30 |
| 7.4 merge + 9 panel | P3, P4 | `etl/merge_panel.py`, `etl/build_panels.py` | `merged_hourly_panel`, `panels` | ✅ รันแล้ว 2026-10-10 |
| 7.4 Correlation | A1 | `analysis/correlation.py`, `analysis/results_store.py` | `analysis_results` + `output/figures/a1_*.png` | ✅ รันแล้ว 2026-10-10 |
| 7.4 Win Rate | A2 | `analysis/winrate.py` | `analysis_results` + `output/figures/a2_*.png` (`winrate_*` ใน fact = W3 ยังไม่ทำ) | ✅ รันแล้ว 2026-10-10 |
| 7.4 Logistic | A3 | `analysis/logistic.py` | `analysis_results` (AUC, coef) + `output/figures/a3_auc.png` | ✅ รันแล้ว 2026-10-10 |
| 7.4 กลุ่มสินทรัพย์ + สรุปผล | A4, A5 | `analysis/evaluate.py` (รวม A4 ไว้ในไฟล์เดียว) | `evaluation_*` + `output/reports/a5_evaluation.md` | ✅ รันแล้ว 2026-10-10 |
| 7.5 โหลด Fact ของ 7.5 | F1 | `etl/load_fact_market_sentiment.py` | `FactMarketSentiment` (250,253 แถว) | ✅ รันแล้ว 2026-10-10 |
| 7.6 ตรวจจับสัญญาณ | G1–G3 | `analysis/signals.py`, `configs/detection.yaml` | `signal_events`, `signal_summary`, view `v_signal_list` (= ตาราง 18) | ✅ รันแล้ว 2026-10-11 |
| 7.5 dashboard | D0, D3, D4 | `dashboard/app.py` (เมนูแท็บ), `dashboard/home.py`, `dashboard/data.py`, `dashboard/common.py`, `dashboard/pages/4_*.py`, `5_*.py` | — | ✅ รันแล้ว 2026-10-11 (เปิดด้วย `streamlit run dashboard/app.py`) |
| ลำดับรัน + ตรวจ proposal | — | `steps/00_*.py` ถึง `26_*.py` (ตัวเรียกมีเลขลำดับ), `scripts/check_proposal_coverage.py` | `output/reports/proposal_coverage.md` | ✅ 2026-10-11 |
| ตัวเลข/กราฟลงเล่ม | — | `scripts/make_book_tables.py` (step 31) | `output/tables/t1..t11_*.csv` (t10, t11 = ตัวอย่างตรวจกฎรวมผล ไม่มีข้อความ Reddit), `output/figures/book_*.png` | ✅ ร่างแรก 2026-10-25 (ผู้ใช้ปรับรูปแบบต่อ) |
| ทดสอบ (§8.4) | Q1–Q4 | `tests/` | รายงานผลเทสต์ | บางส่วน |
| คู่มือผู้ใช้ (§8.5) | Q5 | `docs/USER_MANUAL_TH.md` | — | ✅ 2026-10-25 |

## 4) ลำดับรันที่ต้องมีในเล่ม (RUNBOOK)

เขียนลำดับนี้ลงใน README ให้คนที่ clone ไปรันตามได้ (ตอนนี้ยังไม่ครบ — เติมเมื่อแต่ละขั้นเสร็จ):

```
 1. สร้าง venv + ติดตั้ง requirements
 2. ingest/reddit_extract.py fetch <เดือน>      (หรือ import)    → reddit_content
 3. ingest/market_fetch.py                                          → market_bars
 4. db/schema.sql + etl/seed_dims.py                         → Dim/Fact ว่าง
 5. etl/clean_text.py → quality_filter.py → extract_tickers.py
 6. etl/sentiment_vader.py → sentiment_finbert.py → resolve_sentiment.py
 7. etl/market_features.py → reddit_hourly.py → build_panels.py
 8. analysis/correlation.py, winrate.py, logistic.py, subgroup.py, evaluate.py
 9. analysis/signals.py
10. streamlit run dashboard/app.py
11. reports/make_tables.py, make_figures.py                  → ตาราง/กราฟของเล่ม
```

ถ้ามีเวลาท้ายโปรเจกต์ ทำตัวเรียกรวม (`run_pipeline.py --from 5 --to 8`) แต่ไม่จำเป็น — ลำดับในเอกสารที่ตรงกับโค้ดจริงสำคัญกว่า

## 5) เช็กลิสต์ก่อนปิดเล่ม

- [ ] ทุกตัวเลขในเล่มระบุได้ว่ามาจากสคริปต์ไหน + `run_id` ไหน
- [ ] ทุกกราฟ/ตารางในเล่มสร้างจาก `reports/` (ลบแล้วรันใหม่ได้ผลเดิม)
- [ ] `requirements.txt` และ `requirements-sentiment.txt` ตรงกับที่ใช้จริง (มีเวอร์ชัน)
- [ ] README มี RUNBOOK ที่ตรงกับโค้ด และระบุว่าไม่เผยแพร่ข้อมูล Reddit
- [ ] ลองรันบน fixture เล็ก (1 เดือน) จากโฟลเดอร์ใหม่ได้จนจบ
- [ ] เทสต์ผ่านบน Windows (ตอนนี้ 9/18 error จากไฟล์ SQLite ที่ไม่ปิดก่อนลบ) และมี `test_reddit_extract.py` จริง
- [ ] ไม่มีข้อมูลดิบ/ชื่อผู้ใช้/โน้ตบุ๊กที่มีข้อความจริง ในส่วนที่แนบหรือใน git
- [ ] ส่วนขยายนอก proposal ทุกข้อ (ดู docs/METHOD_DECISIONS_NOT_IN_PROPOSAL.md) เขียนอธิบายไว้ในเล่ม

## 6) ไฟล์ที่มีอยู่แล้ว: เก็บ / แก้ / ลบ (ตรวจ 2026-10-09)

| ไฟล์ | การตัดสินใจ | หมายเหตุ |
|---|---|---|
| `ingest/reddit_extract.py`, `ingest/market_fetch.py`, `ingest/pipeline_status.py`, `ingest/pipeline_logs.py` | **เก็บ** | ส่วนหนึ่งของระบบ 7.1/7.2 |
| `tests/` 4 ไฟล์ที่มีเนื้อหา | **เก็บ + แก้** | proposal §8.4 บังคับให้มีการทดสอบ; แก้ให้ปิดไฟล์ SQLite ก่อนลบโฟลเดอร์ชั่วคราว |
| `tests/test_reddit_extract.py` (ว่าง 0 ไบต์) | **เติมเทสต์จริง** | ยังไม่ลบเพราะ importer เป็นของสำคัญ ควรมีเทสต์ |
| `README.md` | **แก้** | ยังบอก 9 ชุมชน; เพิ่ม RUNBOOK |
| `output/*.csv`, `*.txt`, `output/logs/` | **เก็บ** | รายงานตรวจคุณภาพราคาจากการรันก่อนหน้า (เล็ก) — สร้างใหม่ได้ด้วย `ingest/market_fetch.py` |
| `old_code/reddit_6.ipynb` | **เก็บไว้อ้างอิงก่อน** | ย้ายออกจากโปรเจกต์ได้เมื่อพอร์ต cell ที่ต้องใช้ครบ (T1–A4) |
| `.vscode/settings.json` | **แก้แล้ว** | เดิมชี้ `.venv` ที่ไม่มีอยู่ → ชี้ `venv\Scripts\python.exe` |
| `__pycache__/`, `output/.DS_Store` | **ลบแล้ว** | ไฟล์ขยะที่สร้างซ้ำได้ |
