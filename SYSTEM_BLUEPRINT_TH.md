# System Blueprint (Thai)

เอกสารนี้ออกแบบจากข้อเสนอโครงการ (`data/Proposal_6782094726_Rithipong_Leanghirunkun.pdf` ฉบับปรับปรุงล่าสุด) เป็นหลัก โดยใช้โค้ดม๊อคอัพเป็นเพียงภาพประกอบแนวทางการพัฒนาเท่านั้น

> เอกสารคู่กัน: `TASKS.md` (รายการงานระดับลงมือทำ + สถานะข้อมูลจริง + ข้อสงสัยที่ต้องเคาะ)
> **ถ้าเอกสารนี้ขัดกับ proposal ให้ยึด proposal** — ส่วนที่เป็น "ส่วนขยาย" ต้องระบุว่าเป็นส่วนเพิ่มเองในรายงาน

## 0) สิ่งที่เปลี่ยนจากฉบับก่อน (ตาม proposal ที่ปรับแล้ว)

1. ฐานข้อมูลเป็น **SQLite อย่างเดียว** เป็น Single Source of Truth — **ตัด PostgreSQL ออกทั้งหมด** (ตารางที่ 1, §7.1, §7.2, §7.5, §7.6, รูปที่ 5)
2. ชุมชน Reddit เหลือ **6 ชุมชน**: wallstreetbets, stocks, investing, StockMarket, options, CryptoCurrency (เดิม 9)
3. dashboard มี **4 หน้า**: 7.1-1, 7.2-1, 7.5-1, 7.5-2 (รูปที่ 5) — ไม่มี dashboard คุณภาพข้อมูลแยก
4. dimension ฝั่ง Reddit/ราคาเหลือ DimTime, DimTicker, DimSource; ฝั่ง 7.5 มี DimSentimentSource, DimDetectionConfig และ **DimMajoritySentiment (ใหม่)**
5. เทคนิคสถิติ: Pearson, Spearman, Historical Win Rate + Binomial Test, Logistic Regression (TimeSeriesSplit) — **ไม่มี Granger**
6. ระบบ 7.6 ไม่ส่ง alert ภายนอก และไม่ใช่ real-time (§7.6 ภาพรวม) → ตัด Phase Operations แบบ schedule/alert ออก
7. เครื่องมือพัฒนาตาม proposal: VS Code / Cursor / **Google Colab + Google Drive**, Streamlit, Matplotlib + Seaborn, SciPy, scikit-learn

## 1) เป้าหมายระบบ

สร้างระบบวิจัยและวิเคราะห์เชิงปฏิบัติการที่รองรับงาน 6 ระบบตาม proposal

1. คลังข้อมูล Reddit (7.1)
2. คลังข้อมูลราคา 34 สินทรัพย์ (7.2)
3. วิเคราะห์ความรู้สึก VADER + FinBERT + conflict resolution (7.3)
4. วิเคราะห์ความสัมพันธ์กับผลตอบแทนในอนาคต (7.4)
5. วิเคราะห์การลงทุนเชิงสถิติและแสดงผล (7.5)
6. ตรวจจับสัญญาณเชิงข้อมูล (7.6)

ระบบต้องรันซ้ำได้ ตรวจสอบย้อนกลับได้ และป้องกัน look-ahead bias
ผลลัพธ์เป็น **เครื่องมือสนับสนุนการวิเคราะห์ (Analytical Decision Support)** ไม่ใช่คำแนะนำการลงทุน ไม่ใช่การทำนายราคา และไม่ส่งคำสั่งซื้อขาย

## 2) หลักการออกแบบระบบ

1. Source of truth แยกเป็นชั้น และ **อยู่ใน SQLite**
2. แยก Ingestion, Processing, Feature, Modeling, Serving ชัดเจน
3. ทุกขั้นตอนต้องมี data contract (schema, key, time semantics)
4. เวลาทุกชุด normalize เป็น UTC
5. แยกผลวิเคราะห์หลัก กับ sensitivity analysis ที่เสี่ยง leakage
6. เก็บ provenance ทุกแถวที่แปลงค่าแล้ว (version, run_id, created_at)
7. ข้อมูลดิบ **ห้ามสูญหาย**: ไฟล์ `.zst` ของเดือนที่ import แล้วถูกลบทิ้งตามดีไซน์ของ `fetch` ดังนั้น SQLite คือสำเนาเดียว → สำรองก่อนเขียนตารางใหม่ และกรองข้อมูลนอกขอบเขต (เช่น 3 ชุมชนส่วนเกิน) **ด้วย query ไม่ใช่ด้วยการลบแถว**
8. การกรองขอบเขต (6 ชุมชน, 34 ticker, ภาษาอังกฤษ) ต้องอยู่ใน config ที่เดียว ไม่ hard-code ซ้ำหลายไฟล์

## 3) ภาษาและเทคโนโลยี

ใช้ตามตารางที่ 1 ของ proposal

แกนหลัก

1. Python เป็นภาษา pipeline, NLP, modeling (ใช้ Python 3.11 ขึ้นไป — เครื่องพัฒนาปัจจุบันใช้ 3.14 ให้ทดสอบว่าไลบรารี NLP/torch รองรับก่อนเริ่ม S1/S2 หรือรันงานนั้นบน Colab)
2. SQL ใช้แปลงข้อมูลเชิงตารางและ aggregate
3. **SQLite** เป็นคลังข้อมูลกลาง (stdlib `sqlite3` เพียงพอ)

ไลบรารีหลัก (ตาม proposal)

1. pandas, NumPy
2. NLTK (VADER), Hugging Face Transformers + torch (`ProsusAI/finbert`)
3. SciPy (Pearson, Spearman, Binomial Test)
4. scikit-learn (Logistic Regression, StandardScaler, TimeSeriesSplit)
5. Matplotlib, Seaborn (heatmap และกราฟ)
6. Streamlit (dashboard)
7. `zstandard` (อ่าน `.zst`), yfinance (ราคา)

เครื่องมือเสริม (ไม่บังคับ — เพิ่มเมื่อจำเป็น)

1. pytest / unittest สำหรับ test (repo ปัจจุบันใช้ unittest)
2. ruff + black สำหรับคุณภาพโค้ด
3. pandera สำหรับ data quality contract (ถ้าต้องการ)

**ตัดออกจากฉบับก่อน** (ไม่อยู่ใน proposal และไม่จำเป็นกับ SQLite): PostgreSQL, sqlalchemy, dbt, Great Expectations, statsmodels (Granger), pydantic (ใช้เมื่อจำเป็นจริง), mypy/pre-commit/CI (ทำได้ภายหลัง ไม่ใช่เงื่อนไขของ proposal)

## 4) โครงสร้างโฟลเดอร์ที่ควรเป็น

**แนวทาง**: ค่อยเป็นค่อยไป (D3 ใน `TASKS.md`) — คงสคริปต์ที่ใช้งานจริงไว้ที่ root แล้วเพิ่ม package ใหม่ตามขั้น ค่อยย้ายเข้า `src/` เมื่อ pipeline นิ่ง

**โครงสร้างปัจจุบัน (จริง)**

```
reddit-sentiment-market-warehouse/
  README.md  TASKS.md  SYSTEM_BLUEPRINT_TH.md  requirements.txt
  ingest/reddit_extract.py   ingest/market_fetch.py   ingest/pipeline_status.py   ingest/pipeline_logs.py
  data/       # .torrent, ไฟล์ดาวน์โหลด, proposal PDF  (gitignore)
  output/     # reddit.sqlite3 (12.76 GB), logs/, csv สรุป  (gitignore)
  tests/
```

**โครงสร้างเป้าหมาย (เพิ่มตามขั้น)**

```
  configs/
    tickers.yaml         # 34 สินทรัพย์ + alias + AssetClass
    subreddits.yaml      # 6 ชุมชน
    sentiment.yaml       # neutral band 0.05, keyword list
    detection.yaml       # Z-score / Sentiment threshold / Horizon, สูตร signal_level
  db/
    schema.sql           # star schema ตามรูปที่ 2–4
    indexes.sql
  etl/                   # clean_text, quality_filter, ticker_dict, extract_tickers,
                         # sentiment_vader, sentiment_finbert, resolve_sentiment,
                         # market_features, reddit_hourly, build_panels, seed_dims, load_fact_*
  analysis/              # correlation.py, winrate.py, logistic.py, subgroup.py, signals.py
  dashboard/             # app.py + pages/ (4 หน้า)
  docs/                  # benchmark_finbert.md, คู่มือผู้ใช้ (§8.5)
  tests/                 # unit/ integration/ fixtures/
  notebooks/             # exploration เท่านั้น
```

หลักสำคัญ

1. Notebook ต้องอยู่แค่ exploration (หรือเป็นที่รันบน Colab ที่เรียกโค้ดจาก package)
2. Logic จริงต้องอยู่ในโมดูล `.py` เท่านั้น
3. pipeline แต่ละ stage ต้องเรียกจาก CLI ได้
4. **ไม่มี `serving/api.py`** — proposal ไม่มี API (ระบบแสดงผลผ่าน Streamlit อ่านจาก SQLite โดยตรง)

## 5) Data Architecture (จาก proposal -> ระบบจริง)

สอดคล้องรูปที่ 5 (Academic Torrents + yfinance → Clean / Transform / Align → SQLite → ระบบ 7.1–7.6 → Dashboard)

ชั้นข้อมูล (ทั้งหมดอยู่ใน SQLite)

1. **Raw layer** — มีอยู่แล้ว
   `reddit_content` (28.4M แถว: 6 ชุมชนในขอบเขต 24.5M + 3 ชุมชนส่วนเกิน 3.9M)
   `market_bars`, `market_windows`, `market_gaps` (ราคารายชั่วโมง 34 ticker)
2. **Staging layer**
   `processed_text` (final_text), `ticker_mentions`, `sentiment_item` (vader/finbert/rule/final)
3. **Feature layer**
   `reddit_hourly_features`, `market_hourly_features`, `merged_hourly_panel`
4. **Warehouse (star schema) layer** — ตามรูปที่ 2, 3, 4
   Dimensions: `DimTime`, `DimTicker`, `DimSource`, `DimSentimentSource`, `DimDetectionConfig`, `DimMajoritySentiment`
   Facts: `FactRedditVolume`, `FactMarketPrice`, `FactMarketSentiment`
5. **Research layer**
   `panel` (9 กลุ่ม, คอลัมน์ `panel_name`), `analysis_results`
6. **Serving layer**
   `signal_events` + view/ตารางสรุปสำหรับ Streamlit

ตารางหลักที่ต้องมี

1. reddit_content (มีแล้ว)
2. market_bars (มีแล้ว)
3. processed_text
4. ticker_mentions
5. sentiment_item
6. reddit_hourly_features
7. market_hourly_features
8. merged_hourly_panel
9. FactRedditVolume, FactMarketPrice, FactMarketSentiment + 6 Dim
10. analysis_results
11. signal_events
12. data_quality_audit (**QA ภายใน** — ไม่ใช่ deliverable ของ proposal ปัจจุบัน ใช้เขียนรายงานข้อจำกัด)

**star schema ตามรูปใน proposal (ชื่อคอลัมน์ต้องตรง)**

```
DimTime(TimeID, Year, Month, Week, Day, Hour)            -- + ts_utc ช่วย join (ส่วนขยาย)
DimTicker(TickerID, AssetClass, TickerSymbol, TickerName)
DimSource(SourceID, Platform, Subreddit, ContentType)
DimSentimentSource(SourceID, Platform, Subreddit, ModelUsed)
DimDetectionConfig(ConfigID, ZscoreThreshold, SentimentThreshold, Horizon)
DimMajoritySentiment(MajorityID, MajorityStatus)

FactRedditVolume(TimeID, TickerID, SourceID, reddit_volume, ticker_mention_count)
FactMarketPrice(TimeID, TickerID, close, volume, future_return_1h/2h/3h/6h/12h, RSI, ATR)
FactMarketSentiment(TimeID, TickerID, SentimentSourceID, DetectionConfigID, MajorityID,
                    close, volume, sentiment_mean, pos_ratio, neg_ratio, neu_ratio, reddit_volume,
                    future_return_1h..12h, winrate_1h..12h, winrate_p_value_1h..12h)
```

หมายเหตุ

- `future_return_*` ซ้ำใน `FactMarketPrice` และ `FactMarketSentiment` ตาม proposal โดยตั้งใจ
- KPI ที่คำนวณได้ (`log_return`, Volume Z-score, Normalized ATR, Sentiment Momentum, Reddit Volume Z-score, Ticker Mention Rate) ไม่อยู่ใน fact ตามรูป — เก็บในตาราง feature แล้วให้ dashboard อ่าน
- `reddit_volume` ใน `FactRedditVolume` ผูกกับ (ชั่วโมง, ticker, source) → **ห้าม SUM ข้าม ticker** (นิยามเต็มอยู่ที่ข้อสงสัย O1 ใน `TASKS.md`)

## 6) Time Alignment Rules ที่ต้องล็อก

1. ใช้ timestamp แบบ UTC hour bucket เสมอ
2. feature จาก Reddit เวลา t ต้อง map กับ market timestamp t ตามกติกาที่ประกาศชัด (key = timestamp + Ticker)
3. `future_return_1h/2h/3h/6h/12h` คำนวณจากข้อมูลอนาคตจริงเท่านั้น หน่วย **%**
4. `log_return = ln(close_t / close_{t-1}) × 100`
5. เก็บ `valid_for_target_xh` เป็นธงบอกว่าคู่นี้ใช้ได้ (proposal §4.2: ใช้เฉพาะช่วงที่มีข้อมูลเพียงพอ)
6. ไม่ใช้แถวที่ตลาดปิดหรือ gap โดยไม่มีการ mark
7. Z-score ทุกตัวใช้หน้าต่าง **24 ชั่วโมงย้อนหลัง ไม่รวมชั่วโมงปัจจุบัน**
8. `sentiment_mean = NULL` (ไม่มีข้อความ) ≠ `0` (neutral) — ห้าม fillna(0)
9. timestamp ของบาร์ราคาคือ **เวลาเริ่มบาร์**: หุ้น/ETF เป็น `xx:30` (≈7 บาร์/วัน), คริปโตและฟิวเจอร์สเป็น `xx:00` → ต้องกำหนด hour bucket (เช่น floor ถึงชั่วโมง) ก่อน merge กับ Reddit และบันทึกกติกานี้ไว้ในรายงาน
10. แถวราคาที่ `close IS NULL` (placeholder ตอนตลาดปิด) ไม่ใช่ข้อมูลราคา — ตัดก่อนคำนวณ return; horizon ยาว (6h/12h) ของหุ้น/ETF จะมีตัวอย่างน้อยมากเพราะตลาดเปิดวันละ ~7 ชั่วโมง ให้ mark `insufficient_data`

## 7) Leakage Control Policy

แยก 2 โหมด

1. Primary research mode
   ใช้เฉพาะข้อมูลที่รู้ได้ ณ เวลา t
2. Extended analysis mode
   อนุญาต metadata snapshot เช่น score, upvote_ratio แบบติดป้ายเสี่ยง leakage

กฎบังคับ

1. ห้ามใช้ num_comments, score, upvote_ratio ในโมเดลหลักถ้าไม่ freeze as-of-time
2. ทุก experiment ต้องบันทึก feature whitelist
3. ใช้ **TimeSeriesSplit (5 folds) เท่านั้น** ห้าม random split และห้าม StratifiedKFold (ตาม proposal §7.4)
4. `future_return_*` ใช้เป็น target เท่านั้น ห้ามเป็น feature

## 8) Code Structure Review จากม๊อคอัพ

สิ่งที่ดีอยู่แล้ว

1. แนวคิด panel หลายแบบสอดคล้อง proposal
2. มี valid target horizon และ lag features
3. มีสถิติหลายชนิด (corr, winrate)

จุดที่ต้อง refactor

1. ย้าย logic ออกจาก notebook ขนาดใหญ่ ไปเป็นโมดูลย่อย
2. ตัด hard-coded path และ parameter ออกไป config
3. ตัด hard-coded ticker alias ไปเป็น dictionary versioned (`configs/tickers.yaml`)
4. ทำ function ให้ pure และ testable
5. แยก compute กับ visualize
6. ทำ output format กลางเดียว
7. **แก้ให้ตรง proposal**: neutral band 0.10→0.05; spike z ≥2.0→>1.5; 8→9 panel; future return เป็น % ไม่ใช่ log; StratifiedKFold→TimeSeriesSplit; conflict resolution ตามกฎ 3 กรณีของ proposal (ไม่ใช้ค่า hard-code 0.70 / "โมเดลที่แรงกว่า"); ไม่พอร์ต Granger/PnL

## 9) Task Breakdown ระดับสถาปัตยกรรม

> รายละเอียดระดับลงมือทำ (input/output/DoD) อยู่ใน `TASKS.md` — ส่วนนี้ให้ภาพรวมของ phase

Phase A: Foundation and Governance

1. ตั้งค่า project standard ขั้นต่ำ: requirements, test runner (unittest/pytest), โครง `configs/`
2. นิยาม data contracts
   ผลลัพธ์: `db/schema.sql` (star schema ตามรูป), key constraints, enum definitions
3. run metadata
   ผลลัพธ์: run_id, pipeline_version, source_archive, created_at ในตารางสำคัญ
4. **สำรองไฟล์ SQLite ก่อนเขียนตารางใหม่** + ตั้ง PRAGMA (WAL, foreign_keys)

Definition of done

1. รัน test ผ่านอัตโนมัติ, `schema.sql` รันบน DB เปล่าได้ และมีไฟล์สำรองที่ผ่าน integrity_check

Phase B: Ingestion (ส่วนใหญ่เสร็จแล้ว)

1. Reddit ingestion — มีแล้ว (`ingest/reddit_extract.py fetch`): import 23 เดือน (2024-10 → 2026-08); 2024-09 และ 2026-09 ไม่มีข้อมูลต้นทาง (ข้ามได้)
2. Market ingestion — มีแล้วแต่ **ยัง partial 24 จาก 25 เดือน** → ต้องปิด gap (งาน M2 ใน `TASKS.md`) และ mark `unavailable` พร้อมเหตุผลสำหรับที่ดึงไม่ได้
3. ingestion audit — มี `ingest/pipeline_logs.py`; แก้ `ingest/pipeline_status.py` ให้เร็ว (Q0)
4. ขอบเขต: กรอง 6 ชุมชนในทุก query ปลายน้ำ

Definition of done

1. ทุกเดือนใน market เป็น `fetched` หรือมีเหตุผล gap ที่บันทึกไว้; รายงานสถานะรันจบเร็ว

Phase C: Text and Ticker Processing (ระบบ 7.1 ส่วน transform)

1. text normalization pipeline
   งาน: clean_title, clean_body, final_text (ถนอม `$`, `%`, `!`), แปลงเวลาเป็น UTC datetime/hour bucket
2. quality filter + กรองภาษาอังกฤษ
   งาน: deleted, removed, empty, missing, too_short, non_english, passed (เก็บเป็น QA ภายใน)
3. สร้าง ticker dictionary 34 สินทรัพย์ + alias rules + stop-word/conflict rules
4. extract mentions ระดับข้อความ → `ticker_mentions`
5. โหลด `FactRedditVolume`

Definition of done

1. `final_text` ไม่ว่าง; สกัดเฉพาะ 34 ticker; precision ของ ticker extraction ≥ 0.9 จากการสุ่มตรวจ 100 ข้อความ; KPI Ticker Mention Rate คำนวณได้

Phase D: Sentiment Engine (ระบบ 7.3)

1. VADER scoring module
2. FinBERT scoring module (ต้องวัดความเร็ว S0 ก่อน — ข้อความที่ต้องให้คะแนน 22.84M แถว ≈ 11–21 ชั่วโมงบน T4)
3. rule-based financial keywords → `rule_signal`
4. conflict resolver ตาม proposal 3 กรณี + `final_method` audit trail
5. sentiment QA report

Definition of done

1. ทุกข้อความ **ในชุดข้อมูลที่นิยามไว้** มี `final_sentiment` ∈ [−1,1], `final_status`, `final_method`; มีรายงาน distribution และสัดส่วน VADER/FinBERT ตรง–ขัดแย้ง

Phase E: Market & Hourly Feature Engineering (ระบบ 7.2 + ตัวเตรียม 7.4)

1. market features
   งาน: `log_return` (×100), `future_return_1h/2h/3h/6h/12h` (%) + validity flags, RSI, ATR (24h), Normalized ATR, Volume Z-score
2. reddit_hourly aggregation
   งาน: sentiment_mean, sentiment_abs_mean, pos/neg/neu_ratio, majority_vader/finbert/final_status, voter_agreement_ratio, Reddit_volume
3. zscore and lag
   งาน: Reddit_volume_zscore_24, Reddit_volume_lag_1h, sentiment_lag_1h/2h/3h/6h/12h, sentiment_momentum_1h
4. merge panel
   งาน: timestamp+Ticker merge พร้อม null policy ชัดเจน
5. สร้าง **9 panel** (aggregate ใหม่ต่อ panel เมื่อกรองระดับข้อความ)
6. โหลด `FactMarketPrice`

Definition of done

1. สร้าง panel ได้อัตโนมัติและตรวจซ้ำได้; `pos+neg+neu = 1`; ไม่มี future_return คำนวณข้ามช่องว่างโดยไม่ mark

Phase F: Research Analytics (ระบบ 7.4)

1. Correlation module
   งาน: Pearson, Spearman (sentiment_mean vs log_return/future_return), p-value, heatmap รายตัว Ticker, 9 panel
2. Historical win rate module
   งาน: sign(sentiment_mean) และ majority_final_status เทียบทิศจริง, Binomial Test เทียบ Random Baseline panel
3. Logistic regression module
   งาน: 6 กลุ่มตัวแปร, StandardScaler, TimeSeriesSplit(5), AUC-ROC เทียบ baseline, coefficients (ทำเมื่อข้อมูลเพียงพอ)
4. subgroup module
   งาน: stock_etf, crypto, futures
5. result evaluation
   งาน: convergence ของ 3 วิธี, เปรียบเทียบ 9 panel/3 กลุ่มสินทรัพย์/กลุ่มตัวแปร
6. โหลด `FactMarketSentiment` (winrate_*, winrate_p_value_*)

Definition of done

1. รายงานผล reproducible จาก run เดียว และตอบคำถามผู้บริหารข้อ 3 ของ §7.4 ได้ครบ

Phase G: Signal Detection System (ระบบ 7.6)

1. threshold configuration (`DimDetectionConfig`, `configs/detection.yaml`)
2. signal rule engine
   งาน: `volume_spike`, `positive_sentiment_spike`, `negative_sentiment_spike`, `combined_signal` + `signal_level` (low/medium/high)
3. historical statistic lookup
   งาน: แนบ `winrate` และ `correlation_value` จากระบบ 7.4 ด้วย key (Ticker, Big_Group, horizon)

Definition of done

1. ได้ตาราง `signal_events` ตามตารางที่ 18 ของ proposal; เปลี่ยนเกณฑ์แล้วจำนวนสัญญาณเปลี่ยนตาม; ไม่มีสัญญาณที่ไม่มี Reddit data

Phase H: Serving and Dashboard (ระบบ 7.5 + หน้า 7.1/7.2)

1. Dashboard 7.1-1 ปริมาณการกล่าวถึงรายชั่วโมง
2. Dashboard 7.2-1 ราคาและผลตอบแทนรายชั่วโมง
3. Dashboard 7.5-1 ภาพรวมตลาดและความรู้สึก
4. Dashboard 7.5-2 จัดอันดับและตั้งค่าเกณฑ์ตรวจจับสัญญาณ (มี control Z-score Threshold / Sentiment Threshold / Horizon)
5. (ส่วนขยาย) drill-down ย้อนกลับถึงข้อความต้นทางผ่าน `permalink`

Definition of done

1. ผู้ใช้ (ทีมนักวิเคราะห์ฯ) ตอบ management question ใน proposal ได้จาก 4 หน้านี้โดยไม่รัน notebook

Phase I: Testing & Documentation (§8.4, §8.5)

1. Unit & Logic / Integration / Dashboard test
2. คู่มือผู้ใช้: วิธีอ่าน KPI, วิธีปรับเกณฑ์, ข้อจำกัด

Definition of done

1. test ครบ 3 ส่วนตาม proposal ผ่าน และมีคู่มือที่ระบุข้อจำกัด (ข้อมูลย้อนหลัง ไม่ใช่ real-time ไม่ใช่คำแนะนำการลงทุน)

> **ตัดออกจากฉบับก่อน**: Phase "Operations" (schedule daily/hourly, monitoring/alerts, incident playbook) — proposal ระบุชัดว่าระบบทำงานกับข้อมูลย้อนหลัง ไม่ครอบคลุม real-time และไม่ส่งแจ้งเตือนภายนอก ให้คงไว้เฉพาะ "สำรองข้อมูล" ซึ่งอยู่ใน Phase A

## 10) Milestone Plan

อ้างอิงลำดับของ proposal ตารางที่ 19 (วิเคราะห์ → ออกแบบ → พัฒนา → production → ทดสอบ → คู่มือ) — ไทม์ไลน์เดือนจริงในตารางนั้น (มี.ค.–ก.ค. 2569) ให้ยืนยันกับอาจารย์ที่ปรึกษาอีกครั้งเพราะสถานะงานปัจจุบันยังไม่ถึงขั้น transform/sentiment

Milestone 1 — Foundation + Data readiness

1. Phase A–B: สำรอง DB, DDL star schema, ปิด gap ราคา (M2), แก้ `pipeline_status`, เคาะข้อสงสัย O1–O8 และ D1–D8

Milestone 2 — Text, Ticker, Sentiment

1. Phase C–D: clean/ticker/FactRedditVolume + VADER/FinBERT/resolver (ต้องมีผล S0 ก่อน)

Milestone 3 — Features, Analytics, Signals

1. Phase E–G: market features, hourly panel 9 กลุ่ม, correlation/win rate/logistic, signal detection

Milestone 4 — Dashboard, Test, Docs

1. Phase H–I: 4 dashboard, test 3 ส่วน, คู่มือผู้ใช้

## 11) Test Strategy

ตาม proposal §8.4 แบ่ง 3 ส่วน

Unit & Logic tests

1. text cleaner: `final_text` ไม่ว่าง
2. ticker extractor: สกัดเฉพาะ 34 ตัวเป้าหมาย และไม่ติด false positive (KO, COIN, SOL)
3. sentiment resolver: `final_sentiment` ∈ [−1,+1] และครบทุกกรณีย่อย (ใช้ตัวเลขตัวอย่างจาก proposal)
4. return calculator: `future_return` ถูกต้องตามกรอบเวลา, `valid_for_target` ทำงานกับ BTC-USD (24/7) และ AAPL (ตลาดปิด)
5. z-score: ไม่ใช้ข้อมูลชั่วโมงปัจจุบัน
6. ขอบเขต: ไม่มี subreddit นอก 6 ชุมชนหลุดเข้า pipeline

Integration tests

1. reddit_content → processed_text → sentiment_item → reddit_hourly (fixture เล็ก)
2. market_bars → market_hourly_features → merged_hourly_panel (เชื่อมด้วย timestamp + Ticker, ครบทุก horizon)
3. panel → analysis_results → signal_events

Dashboard tests

1. ตัวเลขบนกราฟ/ตาราง/ตัวกรองตรงกับ SQL ตรงจาก DB
2. ปรับ Z-score/Sentiment/Horizon บน 7.5-2 แล้ว signal จาก 7.6 เปลี่ยนตามและแสดงครบ

Data tests

1. uniqueness keys (PK ของ dim, key ของ fact)
2. null constraints
3. timestamp continuity checks
4. leakage guard checks (ไม่มี future column / score / upvote_ratio / num_comments ใน feature list)
5. จำนวนแถวก่อน–หลังการสร้างตาราง (เช่น `reddit_content` ต้องเท่าเดิม 28,392,470 แถวจนกว่าจะมีการ import ใหม่)

## 12) Risk Register

1. Data quality / ข้อมูลราคายัง partial
   แผนรับมือ: ปิด gap (M2), mark `unavailable` พร้อมเหตุผล, ตาราง QA ภายใน; ระวัง yfinance จำกัดข้อมูลรายชั่วโมงย้อนหลังราว 730 วัน (ตรวจยืนยัน) → สำรอง `market_bars`
2. Model / Sentiment-quality risk (VADER/FinBERT ตีความสแลงผิด)
   แผนรับมือ: conflict resolution + keyword, รายงาน agreement/conflict, sensitivity ของ neutral band ผ่าน config
3. Leakage risk
   แผนรับมือ: feature whitelist, TimeSeriesSplit เท่านั้น, leakage guard test, z-score ไม่รวมชั่วโมงปัจจุบัน
4. Runtime and storage pressure
   แผนรับมือ: FinBERT 22.84M แถว (11–21 ชม. บน T4) → วัด S0 ก่อน, checkpoint/resume, ลดขอบเขตเดือนหรือชุดข้อมูลถ้าจำเป็น (ต้องนิยามชุดข้อมูลให้ชัด); SQLite 12.76 GB → เตรียมดิสก์ ~50 GB, ทำงานหนักด้วย batch/transaction, สร้าง index หลังโหลด
5. Single copy of raw data (ไม่มีไฟล์ `.zst` สำรอง)
   แผนรับมือ: สำรอง `output/reddit.sqlite3` ก่อนเขียน, ห้ามลบ/VACUUM โดยไม่จำเป็น, กรองด้วย query
6. Colab + Google Drive กับ SQLite ไฟล์ใหญ่
   แผนรับมือ: อย่าเขียน SQLite ตรงบน Drive; ให้ Colab เขียนผลลง SQLite ไฟล์เล็กบนดิสก์ท้องถิ่นของ Colab แล้ว merge เข้า DB หลัก
7. Reproducibility gap
   แผนรับมือ: config freeze + run metadata + deterministic seeds (seed ของ `panel_baseline` และ TimeSeriesSplit)
8. Spec ambiguity ใน proposal (นิยาม `Reddit_volume`, `panel_baseline`, กรณีที่ conflict resolution ไม่ครอบคลุม, mapping กลุ่มตัวแปร Logistic)
   แผนรับมือ: ข้อสงสัย O1–O8 ใน `TASKS.md` — ให้เคาะ/ถามอาจารย์ก่อนลงมือสร้างตารางที่เกี่ยวข้อง และบันทึกการตีความไว้ในรายงาน

## 13) Immediate Next Actions (ทำได้ทันที)

1. สำรอง `output/reddit.sqlite3` และเคาะ D8 (ไฟล์เดียว/แยก) + ตั้ง PRAGMA
2. เคาะข้อสงสัย O1, O2, O4 ก่อนออกแบบ `FactRedditVolume`, `panel_baseline`, `resolve_sentiment`
3. ปิด gap ข้อมูลราคา (M2) — สำรอง `market_bars` ก่อน
4. สร้างไฟล์ config ชุดแรกในโฟลเดอร์ `configs/` (`subreddits.yaml` 6 ชุมชน, `tickers.yaml` 34 ตัว, `sentiment.yaml`)
5. เขียน `db/schema.sql` ตามรูปที่ 2–4 และ seed dims (`DimTicker` 34, `DimSource` 12)
6. รัน S0 (วัดความเร็ว FinBERT) เพื่อเคาะ D2
7. เริ่มโมดูล `etl/clean_text.py` + `etl/ticker_dict.py` พร้อม unit test

## 14) เกณฑ์ความสำเร็จของระบบจริง

1. รัน pipeline ทั้งเส้นจากข้อมูลดิบ (SQLite) ถึงรายงานสถิติและ dashboard ได้ด้วยคำสั่งชุดเดียวที่เอกสารระบุไว้
2. ได้ measure/KPI/dimension ที่ตรง proposal (ตารางที่ 3–18) และตอบ management question ครบ
3. ทุกผลลัพธ์ตรวจสอบย้อนหลังได้ถึงข้อมูลต้นทาง (run_id, config hash, cleaner_version, final_method)
4. ไม่มี look-ahead leakage ในโมเดลหลัก (TimeSeriesSplit + leakage guard)
5. มี test 3 ส่วน (Unit & Logic / Integration / Dashboard) และคู่มือผู้ใช้ที่ระบุข้อจำกัดอย่างชัดเจน (ข้อมูลย้อนหลัง ไม่ใช่ real-time ไม่ใช่คำแนะนำการลงทุน)
