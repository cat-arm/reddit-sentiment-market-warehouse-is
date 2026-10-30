# Task Breakdown — Reddit Sentiment × Securities Price Data Warehouse

เอกสารนี้คือ **รายการงานระดับลงมือทำ** สำหรับผู้พัฒนาที่รับงานต่อ
ใช้คู่กับ 2 เอกสารนี้ (อย่าขัดกัน):

- `data/Proposal_6782094726_Rithipong_Leanghirunkun.pdf` — เป็น **source of truth** ของ requirement (ระบบ 7.1–7.6, measures, KPIs, dimensions, dashboard) **ฉบับปรับปรุงล่าสุด (ไฟล์ปรับเมื่อ 2026-10-09)**
- `SYSTEM_BLUEPRINT_TH.md` — สถาปัตยกรรม/หลักการ (layer, leakage policy, folder convention)

เอกสารนี้ต่างจากทั้งสองตรงที่: ระบุ **ไฟล์ที่ต้องสร้าง, schema ที่ต้องได้, เกณฑ์ว่างานเสร็จ, และกับดักที่เจอจริงจากสถานะข้อมูลปัจจุบัน**

> **ถ้าเอกสารนี้ขัดกับ proposal ให้ยึด proposal** — ยกเว้นข้อที่ระบุว่าเป็น "ส่วนขยาย (extension)" ซึ่งต้องบันทึกในรายงานว่าเป็นส่วนที่เพิ่มเอง

---

## 00) สิ่งที่เปลี่ยนจาก proposal ฉบับก่อน → ฉบับปัจจุบัน

proposal ที่ปรับแล้วทำให้แผนฉบับก่อนล้าสมัยหลายจุด ตารางนี้สรุปว่าอะไรเปลี่ยน และกระทบงานข้อไหน

| หัวข้อ | แผนฉบับก่อน | proposal ปัจจุบัน | ผลต่อแผน |
|---|---|---|---|
| ฐานข้อมูลปลายทาง | PostgreSQL (warehouse) + SQLite (raw) | **SQLite อย่างเดียว** เป็น Single Source of Truth (ตารางที่ 1, §7.1, §7.2, รูปที่ 5) | **ยกเลิก** W1 (Docker/Postgres) และ W3 (ETL SQLite→Postgres) |
| ชุมชน Reddit | 9 ชุมชน | **6 ชุมชน**: wallstreetbets, stocks, investing, StockMarket, options, CryptoCurrency | ต้องกรองข้อมูลใน SQLite เหลือ 6 (ดู D6) |
| dimension ฝั่ง Reddit | DimTime, DimTicker, DimSource, **DimDataQuality** | DimTime, DimTicker, DimSource เท่านั้น (รูปที่ 2) | ตัด DimDataQuality, DimMarketQuality |
| measures/KPIs ฝั่ง Reddit | + raw/removed/passed_count, Removal Rate, Data Completeness | `Reddit_volume`, `Ticker_mention_count` · KPI: Reddit Volume Z-score, Ticker Mention Rate (ตารางที่ 3–4) | ตัด dashboard คุณภาพข้อมูลทั้ง Reddit และราคา |
| dashboard | 6 หน้า + drill-down | **4 หน้า**: 7.1-1, 7.2-1, 7.5-1, 7.5-2 (รูปที่ 5) | D2, D4, D7 เดิมไม่ใช่ deliverable |
| KPI ฝั่งราคา | Log return (ไม่คูณ 100), ATR 14 | `ln(close_t/close_{t-1}) × 100`, Volume Z-score 24h, **Normalized ATR = ATR(24h) ÷ close × 100** (ตารางที่ 8) | แก้ M1 |
| dimension ฝั่ง 7.5 | DimDetectionConfig, DimSentimentSource | + **DimMajoritySentiment** ใหม่ (รูปที่ 4) | เพิ่มใน DDL |
| fact `FactMarketSentiment` | มี imbalance, voter_agreement_ratio, majority_final_status ฯลฯ | มี FK `MajorityID` แทน; **ไม่มี** imbalance / voter_agreement_ratio ในตาราง fact (รูปที่ 4) | ปรับ DDL; ตัวแปรเหล่านั้นอยู่ที่ตารางรายชั่วโมง (ตารางที่ 13) |
| เครื่องมือวิเคราะห์ | (blueprint มี Granger, statsmodels, dbt, sqlalchemy) | Pearson, Spearman, Win Rate + Binomial, Logistic Regression (TimeSeriesSplit) — **ไม่มี Granger** | ตัด Granger ออก |
| Conflict resolution | 4 กรณี (มี "One Sentiment") | **3 กรณี**: Same Direction / Small Conflict / Hard Conflict (§7.3) | "One Sentiment" เป็นส่วนขยาย (ดู S4) |
| panel filter | อ่านว่ากรองระดับแถวรายชั่วโมง | กรอง **"ข้อความ"** ที่ `abs ≥ 0.05 / 0.30` (ตารางที่ 12) | ต้อง aggregate ใหม่ต่อ panel (ดู P4) |
| สภาพแวดล้อม | — | Colab + Google Drive เป็นสภาพแวดล้อมพัฒนา (§7.3, §7.4, §7.6) | มีผลกับการรัน FinBERT และ SQLite ขนาด 12.7 GB (ดู §13) |

---

## 0) สถานะปัจจุบัน (ตรวจจริงเมื่อ 2026-10-09)

> **ตัวเลขใน §0 เป็นของ 2026-10-09 และบางส่วนล้าสมัย** (เช่น ข้อความ 22,840,886 ก่อนใส่ title โพสต์แม่) ตัวเลขปัจจุบันที่สร้างจากสคริปต์ดู `output/reports/final/3_final_summary.md`

### มีอยู่แล้วและใช้งานได้

| ไฟล์ | หน้าที่ | สถานะ |
|---|---|---|
| `ingest/reddit_extract.py` | stream `.zst` → SQLite `reddit_content` + subcommand `fetch` (torrent→import→ลบไฟล์) | ใช้งานจริงแล้ว 23 เดือน (2024-10 → 2026-08) |
| `ingest/market_fetch.py` | yfinance รายชั่วโมง 34 ticker → `market_bars`, `market_windows`, `market_gaps` | ดึงแล้ว 2024-09-30 → 2026-09-30 แต่ **ยัง partial** เกือบทุกเดือน (ดูข้างล่าง) |
| `ingest/pipeline_status.py` | รายงานสถานะรายเดือน (archive / import / market) | รันจบได้ (ตรวจแล้วรอบนี้) แต่ query ยังเป็น `LIKE` บน `source_archive` (บรรทัด 59) — Q0 ยังไม่ได้แก้ |
| `ingest/pipeline_logs.py` | log สรุปรายเดือน → `output/logs/` | ใช้งานได้ |
| `tests/` | unittest | ยังไม่ได้รันซ้ำในรอบตรวจนี้ |

### ข้อมูลใน `output/reddit.sqlite3` (12.76 GB — **ไม่ใช่ 9.1 GB ตามฉบับก่อน**)

```
reddit_content : 28,392,470 แถว  (comment 27,515,792 / submission 876,678)
                 created_utc: 2024-10-01 → 2026-08-31 (23 เดือนติดกัน)
                 ไม่มีข้อมูล 2024-09 และ 2026-09 (ยืนยันแล้วว่าต้นทางไม่มี → ข้ามได้)
                 text_status รวม: available 26,366,890 / removed 1,926,213 / deleted 99,269 / empty 98

   แยกตามชุมชน (9 ชุมชนที่ importer ดึงมา):
     ใน proposal (6)                          นอก proposal (3)
     wallstreetbets   17,847,724              Bitcoin     2,197,074
     stocks            2,110,555              Daytrading  1,136,708
     CryptoCurrency    1,900,473              dogecoin      539,509
     StockMarket       1,128,371              รวมนอกขอบเขต 3,873,291 แถว
     investing         1,121,680
     options             410,376
     รวมในขอบเขต 24,519,179 แถว

   ในขอบเขต 6 ชุมชน แยก text_status:
     comment    available 22,558,317 / removed 1,278,629 / deleted 86,766 / empty 41
     submission available    282,569 / removed   311,296 / deleted  1,535 / empty 26
     → ข้อความที่ต้องให้คะแนน (available) = 22,840,886 แถว

market_bars    : 269,430 แถว, 34 ticker, 2024-09-30 → 2026-09-30
                 คอลัมน์: ticker, timestamp_utc, open, high, low, close, volume, fetched_at_utc
                 สถานะรายเดือน (pipeline_status): fetched แค่ 2026-07; อีก 24 เดือนเป็น partial
                 (ticker ครบ 34/34 ทุกเดือน แต่มี gaps/unresolved เช่น 2025-11 gaps=142 unresolved=28,
                  2026-02 gaps=202 unresolved=28, 2024-12 unresolved=34)
archive (.zst) : archive=missing ทุกเดือน = ถูกลบหลัง import (ตามดีไซน์ของ `fetch`)
                 → SQLite คือสำเนาเดียวของข้อมูลดิบ
```

### ยังไม่มีเลย (= ขอบเขตงานทั้งหมดของเอกสารนี้)

ระบบ 7.1 ส่วน transform (clean, ticker extraction), 7.2 ส่วน feature (future return, RSI, ATR), 7.3 ทั้งระบบ, 7.4 ทั้งระบบ, 7.5 ทั้งระบบ, 7.6 ทั้งระบบ
star schema, dashboard Streamlit, การวิเคราะห์สถิติทุกชนิด

### โค้ด MVP เก่า (`old_code/reddit_6.ipynb`, 40 cells, ~28 MB เพราะมี output ฝังอยู่)

> ตรวจ 2026-10-09: เลข cell ในตารางข้างล่าง (นับจาก 0) ตรวจกับไฟล์จริงแล้วว่าตรงทุกตัว

ใช้เป็น **ตัวอย่าง logic** เท่านั้น ห้าม copy ทั้งก้อน (hard-coded path Google Drive, อ่าน/เขียน CSV, ข้อมูลคนละชุด — Kaggle r/wallstreetbets ไม่ใช่ Academic Torrents)
cell ที่มีค่าในการพอร์ต:

| cell | เนื้อหา | พอร์ตไปที่ task |
|---|---|---|
| 5 | `clean_noise()` — ทำความสะอาดข้อความ ถนอมสัญลักษณ์การเงิน | T1 |
| 8 | กรองแถวผิดปกติ + บันทึกเหตุผลที่ตัดออก | T2 |
| 16 | VADER scoring | S1 |
| 19 | FinBERT scoring (`ProsusAI/finbert`) | S2 |
| 22 | rule-based keyword → `rule_signal` + flag conflict | S3 |
| 23 | conflict resolution → `final_sentiment/status/method` | S4 |
| 24 | ticker extraction (alias regex) | T3, T4 |
| 28 | สร้าง panel + aggregate + lag/zscore | P1–P4 |
| 31, 35, 39 | correlation / winrate / logistic regression | A1, A2, A3 |
| 32, 33, 34, 36, 37 | lag heatmap, Granger, subgroup, PnL, combined signal | **A4 เฉพาะ subgroup (cell 34)**; Granger/PnL ไม่อยู่ใน proposal ปัจจุบัน — ไม่ต้องพอร์ต; combined signal → G2 |

---

## 1) การตัดสินใจที่ต้องเคาะก่อนลงมือ

### D1 — ฐานข้อมูล: ✅ เคาะแล้ว = SQLite อย่างเดียว

proposal ปัจจุบันระบุ SQLite ทุกจุด (ตารางที่ 1, §7.1 "คลังข้อมูล SQLite", §7.2, §7.5 "ฐานข้อมูล SQLite", §7.6, รูปที่ 5 "SQLite = Single Source of Truth") **ไม่มี PostgreSQL แล้ว**

ผลที่ตามมา:
- ไม่มี Docker, psycopg, `COPY`, partition — **ยกเลิก W1/W3 เดิม**
- raw layer (`reddit_content`, `market_bars`) อยู่ใน SQLite อยู่แล้ว → ไม่ต้อง ETL ย้ายข้อมูล
- dimension / fact / panel / analysis_results / signal_events สร้างเป็นตารางใน SQLite เดียวกัน (ดู D8 เรื่องไฟล์เดียวหรือแยก)
- **ข้อจำกัดที่ยังอยู่**: ไฟล์ `.zst` ถูกลบหมดแล้ว SQLite คือสำเนาเดียวของข้อมูลดิบ → **สำรอง `output/reddit.sqlite3` (12.76 GB) ก่อนเขียนตารางใหม่ใด ๆ** และห้ามวางแผนแบบ re-import

### D2 — ขอบเขตการรัน FinBERT (สำคัญที่สุด เสี่ยงพังแผนมากที่สุด)

ข้อความที่ต้องให้คะแนน = **22,840,886 แถว** (6 ชุมชน, `text_status='available'`) — ลดจาก 26.4M เมื่อกรอง 6 ชุมชน แต่ยังมาก
FinBERT บน GPU T4 ได้ราว 300–600 ข้อความ/วินาที → **ประมาณ 11–21 ชั่วโมงต่อเนื่อง** (Colab free ตัดการเชื่อมต่อก่อนแน่นอน) บน CPU: เป็นสัปดาห์ ทำไม่ได้

ทางเลือก (ต้องเลือกอย่างน้อยหนึ่ง):
1. ลดขอบเขตเดือน เช่น 3–6 เดือน (proposal ไม่ได้ล็อกจำนวนเดือน แต่ล็อก 34 ticker + 6 ชุมชน)
2. ให้คะแนนเฉพาะข้อความที่พบ ticker แล้ว panel_global ใช้ชุดย่อย/สุ่ม — **ขัดกับ §7.3 ผลการวิเคราะห์ข้อ 1** ("ทุกรายการในชุดข้อมูลมี final_sentiment") ถ้าไม่ได้นิยามชุดข้อมูลที่ลดแล้วให้ชัด → ต้องเขียนเป็นข้อจำกัดในรายงาน
3. ซื้อ Colab Pro / รันบนเครื่อง GPU แล้ว checkpoint ทุก batch

**ต้องทำ S0 (วัดความเร็วจริง) ก่อนตัดสินใจ** อย่าเดา
**ข้อควรระวัง**: ถ้าเลือกข้อ 1 หรือ 2 ต้อง "นิยามชุดข้อมูลวิเคราะห์" ให้ชัดเจนก่อน แล้วค่อยบอกว่า "ทุกรายการในชุดนั้นมี final_sentiment" จึงจะตรง proposal

### D3 — โครงสร้าง repo

`SYSTEM_BLUEPRINT_TH.md` §4 เสนอ restructure เป็น `src/` เต็มรูปแบบ
**แนะนำ**: ทำแบบค่อยเป็นค่อยไป — คงสคริปต์ที่ใช้งานจริงไว้ที่ root (`ingest/reddit_extract.py`, `ingest/market_fetch.py`) แล้วเพิ่ม package ใหม่ตามขั้น (`etl/`, `analysis/`, `dashboard/`)
เหตุผล: สคริปต์ 2 ตัวนั้นผ่านการใช้งานจริงกับข้อมูล 28M แถวแล้ว การย้ายไฟล์ตอนนี้ได้ความเสี่ยงมากกว่าประโยชน์ ค่อยย้ายทีหลังเมื่อ pipeline นิ่ง

### D4 — Neutral band และ threshold: ✅ proposal ยืนยันซ้ำแล้ว

proposal §7.3 ระบุ **±0.05** (อ้าง Hutto & Gilbert 2014) ใช้ค่านี้ทั้ง VADER และ FinBERT, ทำเป็นค่า config (`configs/sentiment.yaml`) เพื่อทำ sensitivity analysis ได้

| พารามิเตอร์ | MVP เก่า | proposal | ใช้ |
|---|---|---|---|
| neutral band | 0.10 | ±0.05 (ขอบเขต 0.05 ถือเป็น neutral ตามตัวอย่าง "+0.05 (neutral)") | 0.05 |
| strong filter | abs ≥ 0.1 | abs ≥ 0.05 | 0.05 |
| quality filter | abs ≥ 0.3 | abs ≥ 0.30 | 0.30 |
| spike filter | zscore ≥ 2.0 | zscore > 1.5 | 1.5 |
| จำนวน panel | 8 | 9 (เพิ่ม `panel_baseline`) | 9 |
| ticker alias | 15 ตัว | 34 ตัว | 34 |
| z-score window | — | 24 ชั่วโมง **ย้อนหลัง** (ตารางที่ 4, 15) | trailing 24h ไม่รวมชั่วโมงปัจจุบัน |

### D5 — หน่วยข้อความที่ให้คะแนน

proposal §4.1 / §7.1 บอก "โพสต์และความคิดเห็น" → ให้คะแนนทั้ง submission (title + selftext) และ comment (body)
สำหรับ submission ให้สร้าง `final_text` จาก `title + " " + selftext` (ถ้า selftext ว่างให้ใช้ title อย่างเดียว — เป็น link post ที่ `text_status='available'` อยู่แล้ว)
เฉพาะ **ข้อความภาษาอังกฤษ** (proposal §4.1 ข้อจำกัด) → ต้องมีขั้นกรองภาษาใน T2

### D6 — ขอบเขตชุมชน Reddit (ใหม่): 6 ไม่ใช่ 9

`ingest/reddit_extract.py` บรรทัด 15–17 (`SUBREDDITS`) ยังดึง 9 ชุมชน จึงมีข้อมูลเกินขอบเขต 3,873,291 แถว (Bitcoin, Daytrading, dogecoin)

**แนะนำ**: **อย่าลบแถวออกจาก SQLite** (ไม่มีไฟล์ต้นฉบับสำรอง, VACUUM บน 12.76 GB หนักมาก) แต่ **กรอง `subreddit IN (6 ชุมชน)` ในทุก ETL/analysis query** และใส่ใน `DimSource` เฉพาะ 6 ชุมชน
- เก็บรายชื่อ 6 ชุมชนไว้ที่เดียว: `configs/subreddits.yaml` (อย่า hard-code ซ้ำหลายไฟล์)
- เขียน test ว่าไม่มี subreddit นอก 6 หลุดเข้า `processed_text` / panel
- README ยังกล่าวถึง 9 ชุมชน → แก้ให้ตรง (นอกขอบเขตของการแก้เอกสารรอบนี้)
- ตัดสินใจแยกอีกข้อ: จะปรับ `SUBREDDITS` ใน `ingest/reddit_extract.py` ให้เหลือ 6 สำหรับเดือนที่ fetch ต่อไปหรือไม่ (ตอนนี้ไม่มีเดือนค้างที่ต้อง fetch แล้ว จึงไม่เร่ง)

### D7 — ขอบเขต dashboard (ใหม่): 4 หน้า

proposal รูปที่ 5 มี Dashboard **7.1-1, 7.2-1, 7.5-1, 7.5-2** เท่านั้น
- dashboard "คุณภาพข้อมูล Reddit" และ "คุณภาพข้อมูลราคา" (D2/D4 เดิม) **ไม่มีใน proposal ปัจจุบัน** → ไม่ใช่ deliverable
- drill-down กลับถึงข้อความต้นทาง (D7 เดิม) **ไม่มีใน proposal** → เป็น extension (ทำถ้าเหลือเวลา)
- ตารางคุณภาพข้อมูลยังควรมีเป็น **เครื่องมือ QA ภายใน** (ใช้ทดสอบและเขียนข้อจำกัดในรายงาน) แต่ไม่อยู่ใน star schema

### D8 — SQLite ไฟล์เดียวหรือแยกไฟล์ (ใหม่)

proposal: SQLite เป็น "ฐานข้อมูลกลางแหล่งเดียว" แต่ไม่ได้บังคับว่าต้องไฟล์เดียว
**แนะนำ**: ไฟล์เดียว `output/reddit.sqlite3` ตามเจตนา proposal แต่ (1) สำรองก่อน (2) ตั้ง `PRAGMA journal_mode=WAL` (3) เช็กพื้นที่ว่างอย่างน้อย 2× ของส่วนที่จะเพิ่ม (sentiment_item ~22.8M แถว ≈ หลาย GB)
ทางเลือก: แยกไฟล์ `output/warehouse.sqlite3` สำหรับ dim/fact/panel/results แล้ว `ATTACH` ไฟล์ raw — ปลอดภัยกว่าต่อ raw data และ upload ขึ้น Colab ได้ง่ายกว่า (ไม่ต้องแบก raw 12.76 GB) **ให้เคาะก่อน W1**

### ข้อสงสัยใน proposal ที่ต้องเคาะ/ถามอาจารย์ (ใหม่)

| # | ประเด็น | ที่มา | ข้อเสนอ |
|---|---|---|---|
| O1 | `Reddit_volume` = โพสต์+คอมเมนต์ (ตารางที่ 3) หรือ **คอมเมนต์อย่างเดียว** (ตารางที่ 13 "จำนวนความคิดเห็น")? และต่อ ticker หมายถึง "ข้อความที่พูดถึง ticker นั้น" หรือ "ทั้งตลาด"? ใน `FactRedditVolume` ที่ key = (Time, Ticker, Source) ค่ารวมข้าม ticker ซ้ำซ้อนได้ | ตารางที่ 3, 4, 13, รูปที่ 2 | ใช้ตารางที่ 3 (โพสต์+คอมเมนต์); เก็บแยก ContentType ผ่าน DimSource; กำหนดว่า `reddit_volume` ต่อ ticker = จำนวนข้อความที่กล่าวถึง ticker นั้น และเขียนไว้ว่า **ห้าม SUM ข้าม ticker** ถ้าจะหาปริมาณทั้งตลาดให้ query จาก `processed_text` โดยตรง |
| O2 | `panel_baseline` = สุ่มทิศทาง หรือ "อัตราถูกต้องพื้นฐาน"? | ตารางที่ 12 | สุ่มทิศทาง seed คงที่บนชุดแถวเดียวกับ `panel_global` + รายงานอัตราพื้นฐาน (base rate) ควบคู่ |
| O3 | panel strong/quality กรองระดับ **ข้อความ** (ตารางที่ 12 "กรองเฉพาะข้อความ") ไม่ใช่กรองแถวรายชั่วโมง | ตารางที่ 12 | ทำตามนั้น → ต้อง aggregate ใหม่ต่อ panel (ดู P4) |
| O4 | conflict resolution ไม่ครอบคลุม: (ก) ทั้งสองโมเดล neutral, (ข) keyword เป็น `mixed` ใน Hard Conflict, (ค) โมเดลใดโมเดลหนึ่งไม่มีคะแนน | §7.3 ขั้นตอนที่ 3 | ดู S4 — กำหนดกฎเสริมและบันทึกใน `final_method` |
| O5 | `AssetClass` ของ BITO, IBIT, MARA, MSTR, COIN (ผูกกับคริปโตแต่เป็นหุ้น/ETF) | §4.2 แบ่ง 3 กลุ่มโดยไม่ระบุรายตัว | จัดเป็น `stock_etf` (เป็นหลักทรัพย์ที่ซื้อขายในตลาดหุ้น) — ตรวจกับ `TICKERS` ใน `ingest/market_fetch.py` ให้ตรงกัน |
| O6 | RSI ใช้ period เท่าไร (proposal ระบุ ATR 24h แต่ไม่ระบุ RSI) | ตารางที่ 7, 8 | RSI 14 แล้วบันทึกเป็น assumption |
| O7 | ตัวแปร 6 กลุ่มของ Logistic (Level, Direction, Vote, Volume, Lag, Momentum) แมปกับคอลัมน์ไหน | §7.4 ขั้นตอนที่ 3 | ดู A3 — เสนอการแมปและให้ยืนยัน |
| O8 | แหล่งราคา: proposal ให้ลองข้อมูลจุฬาฯ ก่อน แล้วค่อย yfinance (สำรอง) แต่รูปที่ 5 ใช้ yfinance | §4.2, §7.2 | ถ้ายังไม่เคยขอข้อมูลจุฬาฯ ให้บันทึกเหตุผลในรายงานว่าใช้ yfinance เพราะอะไร |

---

### ปรับตาม proposal ฉบับอนุมัติ (2026-10-24)

proposal ที่อนุมัติแล้ว (`data/Proposal_6782094726_Rithipong_Leanghirunkun.pdf`) เพิ่มกฎ 7.3 ที่โค้ดเดิมไม่มี — **ทำแล้ว** ใน `etl/resolve_sentiment.py` (ค่า 0.50 อยู่ `configs/sentiment.yaml: same_direction_max_gap`): (1) Same Direction ที่คะแนนต่างกัน > 0.50 ใช้คะแนนที่ใกล้ 0 กว่า, `final_method = same_direction_far` — วัดจริง 1,488,377 แถว (6.76% ของข้อความ; 21.9% ของที่เคยเป็น `same_direction`), `final_status` ไม่เปลี่ยนสักแถว; (2) คอลัมน์ `is_ambiguous` = 1 สำหรับ `hard_conflict_no_rule` + `hard_conflict_mixed_zero` + `small_conflict_rule_clash` — วัดจริง 2,574,368 แถว (11.69%), final ยัง 0.0/neutral. อัปเกรดตารางเดิมด้วย `python -m etl.resolve_sentiment --migrate` (จากคะแนนที่เก็บไว้ ไม่รันโมเดลใหม่; รันซ้ำได้).
**สายงานต่อรันใหม่แล้ว 2026-10-24 (ตัวเลขชุดนี้เป็นของรอบก่อนใส่ title โพสต์แม่ — ถูกแทนด้วยผลรอบ 2026-10-25 ในย่อหน้าถัดไป)** (steps 12–19, 21, 22 ใช้เวลารวม ~3 นาที): สัญญาณ 299,406 → 289,951; กลุ่มที่ weak convergence 50 → 55 จาก 180 เซลล์, strong convergence ยัง 0 (จัดอันดับ panel: spike > quality > strong > global ยังเหมือนเดิม). **S5**: เขียนสคริปต์แล้ว — `scripts/neutral_band_sensitivity.py` (step 25, รันกับข้อมูลทั้งหมดแล้ว: เกณฑ์ ±0.10 ทำให้ FinBERT neutral 40.81% → 58.35% และ final_status เปลี่ยน 11.39% ของข้อความ) และ `scripts/rule_validation.py` (step 26; **รอผู้ใช้ติดป้าย 210 ข้อความ** แล้วรัน `evaluate`). `scripts/check_proposal_coverage.py` แก้ regex จับ `จำนวนเต็ม` แล้ว — ตารางที่ 11 ครบ 11/11 รวม `is_ambiguous`; ตารางที่ 13 ขาด `current_return` (ในฐานข้อมูลชื่อ `log_return` — รอผู้ใช้เลือกว่าจะเปลี่ยนชื่อคอลัมน์หรือเขียนอธิบายในเล่ม).

**รันทั้งสายใหม่หลังใส่ title โพสต์แม่ให้คอมเมนต์ (cleaner 2.0) — เสร็จ 2026-10-25** (วัดจริง): `sentiment_item` 22,029,119 แถว, `is_ambiguous` = 1 จำนวน 2,714,134 แถว (12.3%), `ticker_mentions` 2,536,024 → 3,915,805 (title ของโพสต์ทำให้คอมเมนต์มี ticker มากขึ้น). ผลต่อความรู้สึกของคอมเมนต์ (`output/reports/context_effect.md`): final_status เปลี่ยน 21.82% (VADER 9.86%, FinBERT 27.21%); submission เปลี่ยน 9 จาก 275,242 แถว (ตัวควบคุม ≈ 0% แต่ไม่ใช่ศูนย์พอดี; FinBERT เปลี่ยน 11 แถว — ยังไม่ได้ตรวจสาเหตุ อาจเป็นความต่างของเลขทศนิยมระหว่างรอบ). สัญญาณ 6 ชุดเกณฑ์รวม 312,772; ผล A5: เซลล์ที่มีครบ 3 วิธี 152, weak convergence 60, strong convergence ยัง 0, ตัวควบคุม baseline 7 จาก 19. torch ใน venv เคยถูกแทนด้วยรุ่น CPU — ติดตั้ง `2.11.0+cu128` กลับแล้ว (wheel อยู่ใน scratchpad `wheels/`). ชีตติดป้าย S5 สุ่มใหม่บนข้อความที่มี title แล้ว (210 ข้อความ, คอลัมน์ `sample_id, final_text, thai_translation, human_label`; คำแปลไทยเป็นของ AI เพื่อช่วยอ่านเท่านั้น) — **รอผู้ใช้กรอก `human_label`** แล้วรัน `python steps/26_rule_validation.py evaluate`.

**ทดสอบระบบตาม 8.4 (2026-10-25, วัดจริง):** `scripts/system_tests.py` ตรวจ 32 ข้อกับ DB จริง ผ่านทั้งหมด (ช่วง ±1 ของคะแนน, สถานะตรงเกณฑ์ ±0.05, ticker เฉพาะ 34 ตัว, คำนวณ Current Return และ future_return 1/2/3/6/12h ซ้ำจากราคาแล้วตรง, key ซ้ำ/กำพร้าใน Fact = 0); unit test 153 ตัว error 9 ตัวเป็น PermissionError ของ Windows เดิม; ผล rule validation (ป้าย 210 ข้อความ): รวมผล 47.3% (tune) / 41.3% (test) เทียบ FinBERT เดี่ยว 56.4% / 42.9% และ VADER 40.6% / 37.1% — `output/reports/rule_validation/rule_validation.md`.

**งานรอบ 2026-10-25 (ค่ำ) — ส่วนขยาย, ผลทดสอบเพิ่ม, สรุปเล่ม (วัดจริง):**
- **super quality (|score| ≥ 0.50) / super spike (z > 2.0)** — `scripts/super_signal_sensitivity.py` (step 27, ส่วนขยาย เกณฑ์ตั้งก่อนดูผล): win rate ทุก panel ≈ 50%; `panel_global_super_spike` ที่ 6h/12h ดูต่ำ (47.7% / 48.0%) แต่แยกช่วง explore (ก่อน 2025-10-01) กับ hold-out แล้วไม่คงอยู่ (explore 45.4–45.8% → hold-out 49.6–50.8%) → `output/reports/super_signal_sensitivity.md`
- **เกณฑ์ neutral ±0.10 เทียบป้ายผู้ใช้ 210 ข้อความ + confusion matrix** — `scripts/rule_validation_extras.py` (step 29): ความแม่นถ่วงน้ำหนัก ทั้ง 210: final 44.3% → 42.4%, FinBERT 49.6% → 49.0%, VADER 38.8% → 38.4% → ±0.10 ไม่ดีกว่า คง ±0.05 → `output/reports/rule_validation/band_and_confusion.md`, `output/figures/s5_confusion_matrices.png`
- **ผู้ใช้เคาะ 2026-10-25: คงกฎรวมผลตาม proposal ไม่ตัดกฎ** รายงานผลตามจริงในเอกสารทดสอบ (ไฟล์ที่ 2)
- **ทดสอบ dashboard (8.4 ส่วนที่ 3)** — `scripts/dashboard_kpi_check.py` (step 30): 155/155 ข้อตรง SQL อิสระ (4 สินทรัพย์ × 2 ช่วงเวลา); รอบแรกพลาด 18 ข้อเพราะ SQL อ้างอิงของผมนับความรู้สึกทุกชั่วโมงแต่หน้า Market and Sentiment นับเฉพาะชั่วโมงที่มีแท่งราคา (ความต่างของนิยาม ไม่ใช่บั๊ก)
- **`current_return`** — `scripts/check_proposal_coverage.py` เพิ่ม alias `current_return → log_return` ตอนนี้พบครบ (ชื่อคอลัมน์ใน DB ยังเป็น `log_return` ตามที่เคาะ)
- **หน้า dashboard 6 Hot Events** (ส่วนขยาย; ป้ายเตือนไม่ใช่สัญญาณซื้อขาย + ช่วงความเชื่อมั่น Wilson) — `dashboard/pages/6_Hot_Events.py`, `dashboard.data.hot_events`, เทสต์ใน `tests/test_dashboard_smoke.py`
- **คู่มือผู้ใช้ §8.5** — `docs/USER_MANUAL_TH.md`; **ตารางและกราฟลงเล่ม (ร่าง)** — `scripts/make_book_tables.py` (step 31) → `output/tables/t1..t9_*.csv`, `output/figures/book_*.png`
- **เอกสารสรุป 3 ไฟล์** — `scripts/build_final_reports.py` (step 28) → `output/reports/final/1_beyond_proposal.md`, `2_tests_and_hypotheses.md`, `3_final_summary.md`
- **unit test 154 ตัวผ่านทั้งหมด** — แก้ 9 error เดิม (PermissionError บน Windows) โดยให้เทสต์ปิดไฟล์ SQLite ก่อนลบโฟลเดอร์ชั่วคราว (`tests/test_market_fetch.py`, `test_market_audit.py`, `test_pipeline_logs.py`, `test_pipeline_status.py`)
- **ความแม่นของเกณฑ์ Z-score 1.5/2.0/2.5 × |ความรู้สึก| 0.05/0.30/0.50/0.80** — `scripts/z_sentiment_grid.py` (step 32, ส่วนขยาย): 8 จาก 45 ช่อง p < 0.05 (คาดโชค ~2); เด่นสุด |s| ≥ 0.50 ที่ 1h = 52.8–54.4% (n 237–362) สูงกว่า 50% ทั้ง explore และ hold-out แต่ที่ 3h ต่ำกว่า 50% และ |s| ≥ 0.80 ข้อมูลไม่พอ → ข้อสังเกตไม่ใช่หลักฐาน; `output/reports/z_sentiment_grid.md`
- **ลบตาราง `*_v1` 5 ตารางแล้ว (ผู้ใช้สั่ง 2026-10-25; integrity_check ok, ไม่ได้ VACUUM ไฟล์จึงยัง 29.5 GB มีหน้าว่าง 3.4 GB)** — `scripts/compare_context_effect.py` และ `archive_sentiment_v1.py` รันซ้ำไม่ได้แล้ว ผลเดิมอยู่ใน `output/reports/context_effect.md`; git commit แล้ว
- **ผู้ใช้เคาะ 2026-10-28: ย้ายสคริปต์นำเข้าข้อมูล 4 ตัวจาก root เข้า `ingest/`** (reddit_extract, market_fetch, pipeline_status, pipeline_logs) เพื่อความเป็นระเบียบ; กระทบ: import ทุกที่เป็น `from ingest.<module> import ...` (analysis/, etl/, tests/, scripts/), ตัวเรียก `steps/00–02`, เอกสาร; เทสต์ 154 ตัวผ่านหลังย้าย
- **Dashboard 7.1 ครบ 3 มิติ + แบบเดียวกันทุกหน้า (ผู้ใช้สั่ง 2026-10-28; แก้หลายรอบตามหน้าจอ)** — ตัวกรองแถบข้าง หน้าตาเหมือนกันทุกบล็อก (หัวข้อมิติ › ชื่อระดับ › ช่องติ๊ก/รายการเลือก) เรียง เวลา › แหล่งข้อมูล › หลักทรัพย์: (1) เวลา = ช่วงวันที่ (เริ่มต้นย้อนหลัง **1 ปี**) + ระดับเวลาของกราฟ (รายการเลือก; ตัดตัวเลือกปี/เดือน/สัปดาห์/วัน เพราะซ้ำ); (2) แหล่งข้อมูล DimSource (หน้า 1–2) = ช่องติ๊กชุมชน 6 + โพสต์/ความคิดเห็น ติ๊กทั้งหมดตอนแรก; (3) หลักทรัพย์ DimTicker = ติ๊กกลุ่ม แล้วหน้า 1–2 ติ๊ก Ticker ได้หลายตัว (ติ๊กทั้งหมดตอนแรก + ปุ่มเลือก/ล้างทั้งหมด) หน้า 3–4 เลือกตัวเดียวจากรายการเดียวกัน (radio) หน้า 5–6/หน้าแรกไม่วาดรายการ Ticker; หน้า Price and Return มีสองมิติตาม proposal 7.2 (เวลา, หลักทรัพย์) เท่านั้น; (4) **ทุกหน้า**: การ์ดตัวเลขสรุป (`common.kpi_cards`, `st.metric(border=True)`) อยู่ด้านบนสุดใต้ชื่อหน้า แล้วกราฟเรียงลงมาทีละอันเต็มความกว้าง (ไม่แบ่งคอลัมน์ ทั้งกราฟและตาราง) ปุ่มเส้น/แท่งอยู่ที่แต่ละกราฟ; (5) หน้า 1 = ปริมาณทั้ง Reddit เมื่อติ๊กหลักทรัพย์ครบ และเปลี่ยนเป็นจำนวนครั้งที่ถูกพูดถึง (Ticker_mention_count รวมของตัวที่ติ๊ก) เมื่อติ๊กออกบางตัว พร้อมข้อความบอกใต้การ์ด; (6) ตัดส่วน drill-down ท้ายหน้า (`dashboard/drill.py`) บรรทัดสรุปตัวกรอง และคำอธิบายตัวกรองที่ไม่เกี่ยวกับหน้านั้น. ทดสอบ: `scripts/dashboard_kpi_check.py` 219/219 ข้อ, `test_dashboard_filters.py` (ลำดับตัวกรอง, ติ๊กออกแล้วตัวเลขเปลี่ยน, หลาย Ticker, ปุ่มเส้น/แท่ง, **ทุกหน้าเปิดด้วยการ์ดและไม่มีกราฟ/ตารางในคอลัมน์**), `test_dashboard_smoke.py`, unit test 166 ตัวผ่าน — ไม่ได้ทดสอบในเบราว์เซอร์จริง และไม่มีการคลิกแท่งกราฟเพื่อลงต่อ
- **หน้า Price and Return ครบตาม proposal 7.2 ตารางที่ 7–10 (2026-10-28):** การ์ด = KPI 3 ตัวของตารางที่ 8 (Current Return, Volume Z-score, Normalized Average True Range); ค่าวัด close, volume, RSI, ATR เป็นกราฟ + ตาราง "รายละเอียดค่าวัด" (ล่าสุด/เฉลี่ย/ต่ำสุด/สูงสุด, สัดส่วน RSI > 70 และ < 30) พร้อมคำอธิบายจากตารางที่ 7; ผลตอบแทนล่วงหน้า 5 ช่วงของ Ticker ที่เลือกเพิ่มจากแบบแยกกลุ่ม. ATR เป็น "ค่าวัด" (ตารางที่ 7 ลำดับ 9) ส่วน Normalized ATR เป็น "KPI" (ตารางที่ 8 ลำดับ 3) ไม่ใช่มิติ. ตัวกรองหน้านี้: เวลา และหลักทรัพย์ (กลุ่ม › ตัวเดียว) ไม่มีหลายตัวเพราะราคาต่างสเกลกันมาก (SPY ~600, BTC ~100,000) วางบนแกนเดียวกันอ่านไม่ได้; ติ๊กกลุ่มยังจำเป็นเพราะคำถามผู้บริหาร 2 ใน 3 ข้อเทียบ "แต่ละกลุ่มสินทรัพย์"
- **หน้า 4–6 (ระบบ 7.5) ตัวกรองตามมิติของตารางที่ 17 (ผู้ใช้สั่ง 2026-10-30, ใช้ design เดิม):** เวลา › หลักทรัพย์ (ติ๊กหลายตัวเหมือนหน้า 1–3) › Market and Sentiment: DimSentimentSource (ติ๊กชุมชน 6 + แบบจำลอง VADER+FinBERT ค่าเดียว) + DimMajoritySentiment (ติ๊ก positive/negative/neutral); Ranking and Signals: DimDetectionConfig (Z-score Threshold, Sentiment Threshold, Horizon ย้ายจากหน้าหลักมาแถบข้าง) + DimMajoritySentiment กรองสัญญาณตามประเภทความรู้สึกส่วนใหญ่ของชั่วโมงนั้น; Hot Events: เกณฑ์ 3 ตัว + DimMajoritySentiment. **ตารางใหม่ `reddit_hourly_community`** (`etl/reddit_hourly_community.py`, step 33, 559,223 แถว) เก็บผลรวมต่อ Ticker × ชั่วโมง × ชุมชน เพราะ `reddit_hourly` เดิมรวมทุกชุมชนแล้ว (รวมชุมชนกลับได้เท่าเดิมครบ 296,842 ชั่วโมง ต่าง 0 แถว; Sentiment Score/Volume Z-score/Momentum/ประเภทส่วนใหญ่ที่คำนวณใหม่ตรงกับค่าที่เก็บไว้ ต่างไม่เกิน 3e-13); เลือกหลาย Ticker ที่หน้า 4 = รวมข้อความของทุกตัวเป็นชุดเดียว (นับข้อความที่พูดถึงหลายตัวซ้ำ) + ราคาเป็นดัชนี; เอาตัวเลือก "เลือกตัวเดียว" (f_ticker) ออกทั้งระบบเพราะไม่มีหน้าไหนใช้แล้ว. ไม่ติ๊กอะไรเลย = การ์ด 0. ทดสอบ: `test_dashboard_filters.py`, `test_reddit_hourly_community.py`, `dashboard_kpi_check.py`
- **แก้หน้า 4 (ผู้ใช้ถาม 2026-10-30):** ตัวกรองประเภทส่วนใหญ่เดิมกรองแค่ Sentiment Score — สัดส่วนบวก/ลบ/กลาง ปริมาณ Z-score Momentum และตารางจำนวนชั่วโมงไม่เปลี่ยน; ตอนนี้ `data.mask_majority` ทำให้ชั่วโมงที่ไม่ติ๊กเสียค่าวัด Reddit ทุกตัว (NULL) ราคา/ปริมาณตลาดอยู่; เพิ่มส่วน "ราคาปิดและปริมาณการซื้อขาย" ด้านล่างสุด (ค่าวัด close, volume ที่ไม่ขึ้นกับตัวกรองความรู้สึก; เดิมไม่มีกราฟ volume); วัดจริง: ติ๊ก neutral ออก ชั่วโมง 8,764 → 7,740, Sentiment Score +0.008 → +0.010; test ใหม่ `tests/test_dashboard_sentiment.py` (9 ตัว)
- **หน้า 4 รอบสอง (ผู้ใช้ชี้ 2026-10-30):** การ์ดเหลือ 3 KPI ของตารางที่ 15/17 (Sentiment Score, Sentiment Momentum, Reddit Volume Z-score สูงสุด) — "ชั่วโมงที่มีข้อความ" ไม่ใช่ KPI จึงเอาออก และตาราง "ความครบถ้วนของข้อมูลความรู้สึก" ที่ย้ายไปไว้ก็เอาออกตามที่ผู้ใช้สั่ง (ตัวเลขอ้างอิง: ทั้ง 34 ตัว 62,680 / 124,914 ticker-ชั่วโมง = 50.2%)
- **Price and Return — ผู้ใช้เคาะ 2026-10-28: เลือกหลักทรัพย์ได้หลายตัว (ล้มข้อเสนอเดิมที่ให้เลือกตัวเดียว) และทุกอย่างในหน้าตามตัวที่ติ๊ก:** ตัวกรองเหมือนหน้า 1–2 (ติ๊กกลุ่ม → ติ๊กทั้งกลุ่ม, ติ๊ก Ticker รายตัว, ปุ่มเลือกทั้งหมด/ล้าง); ลำดับในหน้าเหมือนเดิม: การ์ด KPI 3 ตัว (เฉลี่ยของที่ติ๊กเมื่อหลายตัว) → กราฟแนวโน้ม (1 ตัว = ค่าจริง; 2–8 ตัว = เส้นละตัว โดยราคาและปริมาณเป็นดัชนีเพราะขนาดต่างกันมาก; มากกว่า 8 = ค่าเฉลี่ยของที่ติ๊ก) RSI (แกน 0–100) ATR (USD; แกนลอการิทึมเมื่อหลายตัว) Normalized ATR → ตารางรายละเอียดค่าวัดรายตัว → ด้านล่างตามเดิม: ผลตอบแทนล่วงหน้าแยกตามกลุ่ม และกลุ่มไหนผันผวนสุด (คำนวณเฉพาะตัวที่ติ๊ก). **การติ๊กกลุ่มสินทรัพย์ = ติ๊กทั้งกลุ่ม ใช้พฤติกรรมเดียวกันทุกหน้าที่มีตัวกรองหลายตัว (1, 2, 3)** (`common._group_toggled`); ปุ่ม "เลือกทั้งหมด"/"ล้าง" ติ๊ก/เลิกติ๊กทั้งหลักทรัพย์และกลุ่มสินทรัพย์พร้อมกัน (`common._set_all`, ผู้ใช้สั่ง; ล้างแล้วไม่ติ๊กเลย = **ไม่มีข้อมูลแสดง** การ์ดเป็น 0 — ผู้ใช้สั่งแก้จากเดิมที่แสดงทั้งหมด; ใช้กับทุกตัวกรองของหน้า 1–3, หน้าอื่นที่ไม่ติ๊กกลุ่มเลยได้ผลลัพธ์ว่าง ไม่พัง; `common.nothing_selected`). dashboard_kpi_check 351/351; unit test 168 ตัวผ่าน; ไม่ได้ทดสอบในเบราว์เซอร์จริง
- **หน้า Price and Return ครบค่าวัดตาม proposal 7.2 (ตรวจเทียบตารางที่ 7–10, 2026-10-28):** ค่าวัด close, volume, future_return 1–12h, RSI, ATR → กราฟราคา/ปริมาณ/RSI/**ATR (เพิ่มใหม่)** + **ผลตอบแทนล่วงหน้า 5 ช่วงของ Ticker ที่เลือก (เพิ่มใหม่; เดิมมีแต่แยกตามกลุ่ม)**; KPI 3 ตัวเป็นการ์ด: Current Return, Volume Z-score, Normalized ATR (ATR เป็น "ค่าวัด" ไม่ใช่ KPI และไม่ใช่มิติ; KPI คือ Normalized ATR = ATR ÷ close × 100); dashboard_kpi_check 275/275
- **ยังไม่ได้ทำ:** ตรวจสาเหตุ submission เปลี่ยน 9–11 แถวระหว่างรอบ

**ผู้ใช้เคาะ 2026-10-24:** (1) `current_return` — **คงชื่อคอลัมน์ `log_return` ในฐานข้อมูล** แต่ทุกอย่างที่ผู้ใช้เห็น (dashboard, กราฟ, รายงาน) ใช้คำว่า **Current Return** (แก้ป้ายแกนของ heatmap `a1_*.png` ใน `analysis/correlation.py` แล้ว; dashboard หน้า 3 ใช้ชื่อนี้อยู่แล้ว) ส่งผลให้ `check_proposal_coverage.py` ยังรายงาน `current_return` "ไม่พบ" ในตารางที่ 13 ซึ่งเป็นที่รู้กัน (2) **ลบ** `PROPOSAL_REVISIONS.md`, `PROPOSAL_EDIT_GUIDE.md`, `COVER_SHEET_ADDITIONS.md` แล้ว (3) ไฟล์ผลลัพธ์ที่สคริปต์สร้างต้องขึ้นต้นด้วย "ไฟล์นี้คืออะไร / สร้างเมื่อ / โดยสคริปต์ / ข้อมูลที่ใช้ / สร้างใหม่ด้วยคำสั่ง" (`etl.common.file_header`; CSV ใช้บรรทัดขึ้นต้น `#`; ไฟล์ที่โค้ดอ่านต่อหรือผู้ใช้ต้องกรอกอย่าง `labeling_sheet.csv` ใช้ README.md ในโฟลเดอร์แทน) (4) การติดป้าย S5 ผู้ใช้ต้องติดเอง — proposal ระบุ "ผู้พัฒนาติดป้าย"; ให้ AI ติดจะเท่ากับใช้โมเดลตัดสินโมเดล และขัดกับคำรับรองในแบบฟอร์มการใช้ AI

### ผลการเคาะล่าสุด (2026-10-09, โดยผู้ใช้)

| เรื่อง | ผลที่เคาะ | ผลต่อแผน |
|---|---|---|
| D6 ขอบเขตชุมชน | โฟกัส **6 ชุมชน** — 3 ชุมชนที่ดึงมาเกิน **กรองออกตอนประมวลผล** (ไม่ลบแถว) | ตามข้อเสนอ D6 อยู่แล้ว |
| D8 / การสำรองไฟล์ | **ข้าม** เรื่องสำรองและเรื่องไฟล์เดียว/แยก — ใช้ `output/reddit.sqlite3` ไฟล์เดียวต่อไป | ผู้ใช้รับความเสี่ยงเอง (ไฟล์ `.zst` ไม่มีสำรองแล้ว) — W1 ถือเป็นทางเลือก ไม่บังคับ; ยังแนะนำว่าอย่าลบแถวหรือ VACUUM ไฟล์หลัก |
| O1 `Reddit_volume` | `final_text` คือ title+body ของโพสต์ และ body ของคอมเมนต์ → **นับทุกแถวของ `final_text` เป็นหนึ่งหน่วย** (ผู้ใช้เรียกรวมว่า "คอมเมนต์") | ตรงกับตารางที่ 3 (โพสต์+คอมเมนต์); โพสต์มีแค่ ~3% (876,678 จาก 28.4M) ต่างจาก "คอมเมนต์อย่างเดียว" เล็กน้อย — **ถ้าความหมายคือคอมเมนต์อย่างเดียว ให้แจ้งแก้** |
| O2 `panel_baseline` | **สุ่มทิศทาง** — ตารางที่ 12 เขียนว่า "เช่น การสุ่มทิศทางผลตอบแทน **หรือ** การใช้ค่าอัตราความถูกต้องพื้นฐาน โดยไม่ใช้ตัวชี้วัดความรู้สึก" (proposal เปิดทางไว้ทั้งสองแบบ) | ใช้สุ่มทิศทาง seed คงที่ บนชุดแถวเดียวกับ `panel_global`; รายงาน base rate ควบคู่ได้ |
| FinBERT (D2) | **รันบนเครื่องตัวเอง**: RTX 5070 (12 GB VRAM), RAM 32 GB | **วัดจริงแล้ว (S0)**: ~6,000 ข้อความ/วินาที → ส่วนคำนวณทั้ง 22.84M ข้อความ ≈ 1.0–1.2 ชั่วโมง; รวมอ่าน/ล้าง/เขียนฐานข้อมูลประมาณ 2–3 ชั่วโมง → **ไม่ต้องลดขอบเขต รันครบทุกข้อความ** (รายละเอียด `docs/benchmark_finbert.md`) |
| O4 / G1 กฎ conflict resolution เสริม | **ใช้ตามที่เสนอ**: both neutral → เฉลี่ย (`both_neutral`); keyword `mixed` ใน Hard Conflict → 0.0 (`hard_conflict_mixed_zero`); มีโมเดลเดียว → ใช้ค่านั้น (`one_model`) | S4 ตามที่เขียนไว้แล้ว; เป็นส่วนขยายนอก proposal ต้องบันทึกในรายงาน (เดิมอยู่ใน PROPOSAL_REVISIONS.md §6 ซึ่งลบแล้ว 2026-10-24; สรุปใน docs/METHOD_DECISIONS_NOT_IN_PROPOSAL.md ข้อ 8) |
| O7 / G3 การแมปตัวแปร Logistic | **ใช้ตามที่เสนอ** ตามตารางใน A3 | A3 ตามที่เขียนไว้แล้ว; เก็บการแมปใน config เพื่อทำ ablation; รายละเอียดทางเทคนิคเคาะแล้วทั้งหมด (ตัวแปรตามตัดแถวผลตอบแทน = 0, ฟิตแยก panel × กลุ่มสินทรัพย์ × horizon, `TimeSeriesSplit(n_splits=5, gap=12)`, fit scaler เฉพาะชุดฝึก) ไม่ต้องถามอาจารย์ |
| G12 grain ของ fact (เดิมอยู่ใน PROPOSAL_REVISIONS.md §6 ซึ่งลบแล้ว 2026-10-24; สรุปใน docs/METHOD_DECISIONS_NOT_IN_PROPOSAL.md ข้อ 8) | **A ทั้ง 3 ข้อ**: `FactMarketSentiment` = 1 แถวต่อ ชั่วโมง × Ticker (sentiment รวม 6 ชุมชน); เกณฑ์ตรวจจับใช้ตอน query ไม่ซ้ำแถว; `winrate_*` เก็บใน `analysis_results` แล้วคัดลอกลง fact | W2: PK = (`TimeID`,`TickerID`); W4: `DimSentimentSource` ต้องมีแถว "ALL" (รวม 6 ชุมชน) เพิ่ม → 7 แถว ไม่ใช่ 6; โหลด fact หลัง `analysis_results` |
| ชื่อ `log_return` (proposal 2026-10-12 เปลี่ยนเป็น Current Return / `current_return`) | **ทาง 2**: เปลี่ยนเฉพาะป้ายที่คนเห็น (แดชบอร์ด, coverage check, ชื่อกราฟ, เอกสาร); คอลัมน์ในฐานข้อมูลยังชื่อ `log_return` | เพราะไม่ต้อง rebuild/รันขั้น 11–22 ใหม่; ตอนเขียนเล่มต้องจำว่าชื่อในเล่มต่างจากชื่อคอลัมน์ — รายละเอียดและวิธีเปลี่ยนชื่อจริงภายหลังอยู่ใน `docs/METHOD_DECISIONS_NOT_IN_PROPOSAL.md` §6 |

**FinBERT บนเครื่องนี้ — ผลวัดจริง (S0) เมื่อ 2026-10-09 สรุปไว้ที่ `docs/benchmark_finbert.md`**: 5,300–6,150 ข้อความ/วินาที (ตัดที่ 256 token, batch 128 ≈ 6,000/วินาที, VRAM 0.8 GB), ทั้งชุด ≈ 1.0–1.2 ชั่วโมง (เฉพาะส่วนคำนวณ). ข้อความข้างล่างเป็นประมาณการก่อนวัด เก็บไว้เป็นบันทึกเหตุผลเท่านั้น ถ้าขัดกับผลวัด ให้ยึดผลวัด:
- ความยาวข้อความจากตัวอย่าง 1:200 ของ 6 ชุมชน: คอมเมนต์เฉลี่ย 106 ตัวอักษร (median 58, p90 232, p99 813) ≈ 26 token โดยเฉลี่ย; โพสต์เฉลี่ย 557 ตัวอักษร (p90 1,335)
- ข้อความสั้นขนาดนี้ + จัด batch ตามความยาว + fp16 + ตัดที่ 128–256 token → น่าจะได้ราว 1,000–3,000 ข้อความ/วินาที → **22.84M แถว ≈ 2–7 ชั่วโมง** (ไม่ใช่เป็นวัน; ตัวเลข 300–600/วินาทีของ T4 ในแผนเดิมเป็นแบบระมัดระวังเกินสำหรับข้อความสั้น)
- **พร้อมรันแล้ว (2026-10-09)**: ติดตั้ง `torch 2.11.0+cu128` + `transformers 5.19.0` ใน venv (Python 3.14) สำเร็จ และ `import torch` เห็น RTX 5070 หลังผู้ใช้ปิด Smart App Control (ก่อนหน้านั้นถูกบล็อก `WinError 4551`); แพ็กเกจจดไว้ใน `requirements-sentiment.txt`
- ให้เขียนผลลงตารางทีละ batch (checkpoint) เพื่อกลับมารันต่อได้ และเนื่องจากรันในเครื่องเดียวกับ DB ข้อกังวลเรื่อง Colab/Google Drive (ข้อ 3 ใน §13) ไม่เกี่ยวแล้ว

---

## 2) งานเร่งด่วนก่อน (Q0 และ M2)

### Q0 — แก้ `ingest/pipeline_status.py` ให้เร็ว

**อาการเดิม**: query `WHERE source_archive LIKE '%_YYYY-MM.zst'` → full table scan ต่อเดือนต่อ 25 รอบ (ตอนนี้ตาราง 28.4M แถว) — รอบตรวจนี้รันจบ แต่ยังไม่ได้วัดเวลา และโค้ดบรรทัด 59 ยังเป็น `LIKE`
**แก้**: เพิ่มคอลัมน์ `source_month TEXT` (หรือ index บน `source_archive`) + query เดียวแบบ `GROUP BY` แทนการ loop ต่อเดือน
**เสร็จเมื่อ**: รันจบใน < 10 วินาที และผลลัพธ์เท่าเดิม

### M2 — ปิดช่องว่างข้อมูลราคา (ย้ายขึ้นมาเป็นงานเร่งด่วน)

**ผลตรวจจริง 2026-10-09** (แก้จากที่เคยสรุปว่า "partial 24/25 เดือน" ซึ่งฟังดูแย่เกินจริง):
- **ไม่มีเดือนไหนขาดทั้งเดือน**: Reddit 2024-10 → 2026-08 (23 เดือน) มีราคาครบทุกเดือน; ราคามีเกินมาแค่ 2024-09-30 (1 วัน) กับ 2026-09 (ไม่มี Reddit คู่กัน)
- ช่องว่างจริงน้อยมาก: `market_gaps` 2,017 แถว (1,405 อยู่ในช่วง Reddit) จาก 269,430 แถว ≈ 0.5%; `market_windows`: complete 1,930 / needs_review 353 / unavailable 612 (unavailable = ก.พ.–ก.ย. 2024 ที่เกินขีด 730 วันของ yfinance — โค้ดมีเงื่อนไข `last 730 days` อยู่แล้ว ยืนยันว่าข้อจำกัดเป็นจริง)
- เดือนที่ชั่วโมงขาดเยอะสุด (นับจาก needs_review): 2026-01 (392), 2024-12 (213), 2025-11 (142), 2025-10 (128), 2024-11 (97), 2025-06 (93); วันที่หนักสุด: 2026-02-02 (196), 2026-01-30 (156), 2025-11-29 (114), 2025-10-28 (66)
- ที่มาของ gap แยกตาม ticker: หุ้น/ETF ~14–15 ชั่วโมงต่อตัว — ส่วนใหญ่เป็น **วันตลาดปิดครึ่งวัน** (เช่น 2024-11-29, 2024-12-24, 2025-07-03, 2025-11-28) ที่ `expected_hours()` ไม่รู้จัก จึงนับเป็นขาดทั้งที่ไม่มีบาร์จริง (false positive); คริปโต ~130 ต่อตัว; ฟิวเจอร์ส 99–238 ต่อตัว
- **แถว `close = NULL` 19,177 แถว** (futures ~3,100 ต่อตัว, คริปโต ~35, หุ้น 14–15) — เป็นแถว placeholder ที่ yfinance คืนมาตอนตลาดปิด/พักรอบ (OHLC เป็น NULL, volume 0; ฟิวเจอร์สกระจุกที่ 21:00–22:00 UTC และเสาร์–อาทิตย์) **ไม่ใช่ราคาจริง ห้ามนับเป็นบาร์ที่ใช้คำนวณ return** (ดู M1)

**ขั้นตอน** (ลดขนาดงานลงจากเดิม):
1. รัน `ingest/market_fetch.py` ซ้ำเฉพาะ window ที่เป็น `needs_review` (353 windows) หนึ่งรอบ ดูว่า yfinance คืนข้อมูลเพิ่มไหม
2. ที่ยังขาด ถือเป็นข้อจำกัดของต้นทางและบันทึกเหตุผล (ไม่ต้องไล่ปิดทุกตัว)
3. (ไม่บังคับ) เพิ่มปฏิทินวันตลาดปิดครึ่งวันของ NYSE ใน `expected_hours()` เพื่อตัด false positive ของหุ้น/ETF ~320 แถว
**เสร็จเมื่อ**: รัน needs_review ซ้ำแล้ว และมีสรุปเหตุผลของ gap ที่เหลือ (ใช้ตัวเลขข้างบนเป็นฐาน)
**ระวัง**: ข้อมูลรายชั่วโมงของ yfinance ย้อนหลังได้ราว 730 วัน — วันนี้ 2026-10-09 → ย้อนไปได้ถึงประมาณ 2024-10-09 เท่านั้น ข้อมูลที่ได้มาแล้วของช่วงก่อนหน้านั้นจึงดึงใหม่ไม่ได้ อย่าลบ/เขียนทับแถวเดิมเมื่อรันซ้ำ (การสำรอง `market_bars` เป็นทางเลือก — ดูผลการเคาะข้างบน)

---

## 3) Stage W — Warehouse Foundation (SQLite)

### W1 — เตรียมฐานข้อมูลก่อนเขียนตารางใหม่
- **ตัดสินใจก่อน**: D8 (ไฟล์เดียว/แยก)
- **ขั้นตอน**: สำรอง `output/reddit.sqlite3` (13 GB) ไปไดรฟ์อื่น; ตรวจพื้นที่ว่าง; ตั้ง `PRAGMA journal_mode=WAL`, `synchronous=NORMAL`, `foreign_keys=ON`, `cache_size`/`mmap_size` ตามเครื่อง; รันงานเขียนหนักด้วย transaction ขนาด batch
- **DoD**: มีไฟล์สำรองที่เปิดอ่านได้ + `PRAGMA integrity_check` ผ่าน (บนไฟล์สำรอง) ก่อนเริ่ม W2
- **ระวัง**: อย่าเก็บ SQLite บน Google Drive แล้วเปิดเขียนตรง ๆ (FUSE ช้าและเสี่ยงไฟล์เสีย) — ดู §13

### W2 — เขียน DDL star schema ทั้ง 3 ดาว
- **Input**: proposal รูปที่ 2, 3, 4 (หน้า 20, 24, 41)
- **Output**: `db/schema.sql`
- **ตารางที่ต้องมี** (ชื่อคอลัมน์ให้ตรงรูปเป๊ะ เพราะต้องใช้อ้างในรายงาน — **ถอดจากรูปจริงแล้ว**):

```
DimTime(TimeID PK, Year, Month, Week, Day, Hour)
  -- เพิ่ม ts_utc TEXT UNIQUE เป็นคอลัมน์ช่วย join (ส่วนขยาย ไม่อยู่ในรูปที่ 2)
DimTicker(TickerID PK, AssetClass, TickerSymbol, TickerName)
DimSource(SourceID PK, Platform, Subreddit, ContentType)
DimSentimentSource(SourceID PK, Platform, Subreddit, ModelUsed)      -- ตัวอย่างค่า: Reddit, r/wallstreetbets, VADER+FinBERT
DimDetectionConfig(ConfigID PK, ZscoreThreshold, SentimentThreshold, Horizon)   -- ตัวอย่าง: 2.0, 0.3, 1h
DimMajoritySentiment(MajorityID PK, MajorityStatus)                  -- positive / negative / neutral

FactRedditVolume(TimeID, TickerID, SourceID, reddit_volume, ticker_mention_count)

FactMarketPrice(TimeID, TickerID, close, volume,
  future_return_1h, future_return_2h, future_return_3h, future_return_6h, future_return_12h,
  RSI, ATR)

FactMarketSentiment(TimeID, TickerID, SentimentSourceID, DetectionConfigID, MajorityID,
  close, volume, sentiment_mean, pos_ratio, neg_ratio, neu_ratio, reddit_volume,
  future_return_1h..12h,
  winrate_1h..12h, winrate_p_value_1h..12h)
```
- **DoD**: รัน `schema.sql` บน DB เปล่าได้ไม่ error, FK ครบตามเส้นในรูป, มี index บน (TickerID, TimeID) ของทุก fact
- **ระวัง**:
  - `future_return_*` ซ้ำใน `FactMarketPrice` กับ `FactMarketSentiment` โดยตั้งใจตาม proposal — อย่า normalize ออก
  - **ไม่ใส่** DimDataQuality / DimMarketQuality / removal_rate / continuity_rate / imbalance / voter_agreement_ratio ใน fact — ไม่อยู่ในรูปแล้ว (ค่าเหล่านี้ถ้าต้องใช้ ให้อยู่ในตารางรายชั่วโมงหรือตาราง QA ภายใน)
  - `FactMarketSentiment` มีทั้ง `DetectionConfigID` และ `winrate_*`: ต้องนิยามว่า winrate ผูกกับ config ไหน (ดู G1) ก่อนโหลด
  - `log_return` และ Volume Z-score / Normalized ATR เป็น KPI ที่คำนวณได้ ไม่ได้อยู่ใน fact ตามรูป → เก็บในตาราง feature (M1) แล้วให้ dashboard คำนวณ/อ่านจากตารางนั้น

### W3 — ดัชนีและตัวช่วยประสิทธิภาพ (แทน "ETL ไป Postgres" เดิม)
- **Output**: `db/indexes.sql` + (ถ้าทำ Q0) คอลัมน์ `source_month`
- **ขั้นตอน**: ไม่ต้องย้ายข้อมูล — raw อยู่ใน SQLite แล้ว; เพิ่ม index ที่ query หลักต้องใช้: `(subreddit, created_utc)`, `(ticker, timestamp_utc)` บน `market_bars` (ตรวจ index เดิมก่อน — มี `reddit_by_hour(created_utc, subreddit, content_type)` อยู่แล้ว)
- **DoD**: query นับโพสต์รายชั่วโมงของ 1 ชุมชนใน 1 เดือนตอบใน < 2 วินาที; ไม่มีแถวซ้ำ/หาย (นับ `reddit_content` = 28,392,470 ก่อน-หลัง)
- **ระวัง**: สร้าง index บนตาราง 28M แถวใช้เวลานานและกินพื้นที่ — ทำหลังสำรอง และทีละตัว

### W4 — seed ตาราง dimension
- **Output**: `etl/seed_dims.py`
- **ขั้นตอน**:
  - `DimTicker`: 34 ตัวจาก proposal §4.2 + `AssetClass` ∈ {stock_etf, crypto, futures} ตามที่ตารางที่ 13 ใช้ (`Big_Group`)
    - stock_etf (22): AAPL, AMC, AMD, BITO, BRK-B, COIN, GME, HOOD, IBIT, IWM, JNJ, JPM, KO, MARA, MSFT, MSTR, NVDA, PLTR, QQQ, SPY, TSLA, XOM
    - crypto (6): BTC-USD, DOGE-USD, ETH-USD, SHIB-USD, SOL-USD, XRP-USD
    - futures (6): CL=F, ES=F, GC=F, NG=F, NQ=F, RTY=F
    - (การจัด BITO/IBIT/MARA/MSTR/COIN เป็น stock_etf คือข้อเสนอ — ดู O5; ตรวจกับ `TICKERS` ใน `ingest/market_fetch.py`)
  - `DimTime`: generate ทุกชั่วโมง UTC ครอบคลุม 2024-09-30 → 2026-09-30 (ช่วงที่ market_bars มีจริง; ขยายได้ภายหลัง)
  - `DimSource`: **6 ชุมชน** × {Post, Comment} = 12 แถว (ตัวอย่างค่าใน proposal: Reddit, r/wallstreetbets, Post)
  - `DimSentimentSource`: Platform=Reddit × 6 ชุมชน × ModelUsed=`VADER+FinBERT`
  - `DimMajoritySentiment`: 3 แถว (positive, negative, neutral)
  - `DimDetectionConfig`: ชุดค่าเริ่มต้น (Z-score 1.5 / 2.0 / 2.5 × Sentiment 0.05 / 0.30 × Horizon 1h/2h/3h/6h/12h — ต้องมีค่าตัวอย่างของ proposal คือ 2.0, 0.3, 1h)
- **DoD**: `SELECT COUNT(*) FROM DimTicker` = 34, `DimSource` = 12, ทุก `ticker` ใน `market_bars` หา `TickerID` เจอครบ

> **ยกเลิก**: W3 (ETL → Postgres) และ W5 (partition) ฉบับก่อน — SQLite ไม่มี partition และไม่ต้องย้ายข้อมูล

---

## 4) Stage T — Text & Ticker Processing (ระบบ 7.1 ส่วน transform)

### T1 — โมดูลทำความสะอาดข้อความ

> **สถานะ 2026-10-09: ✅ เขียนและทดสอบแล้ว — ยังไม่ได้รันกับฐานข้อมูลหลัก** (รอผู้ใช้อนุญาต เพราะเขียนตารางหลาย GB ลง `output/reddit.sqlite3`). โค้ด `etl/clean_text.py` (+ `etl/common.py`, `configs/subreddits.yaml`), เทสต์ `tests/test_clean_text.py` 21 ตัวผ่านทั้งหมด. ทดลองกับตัวอย่าง 253,730 แถวบนฐานข้อมูลทดลอง: เขียน 250,156 แถว, ว่าง 3,574 แถว (1.4%), ความเร็ว ≈ 19,500 แถว/วินาที → ทั้งชุด (~24.5M แถวในขอบเขต) ประมาณ 20 นาที. คำสั่ง: `python -m etl.clean_text` (รันต่อได้, `--rebuild` เริ่มใหม่, `--limit-rows N` ทดลอง)
>
> **ต่างจากโค้ดเก่า (cell 5) โดยตั้งใจ**: (1) เก็บตัวพิมพ์ใหญ่/เล็กตามเดิม (VADER ให้น้ำหนักคำ ALL-CAPS) (2) เก็บเครื่องหมาย `'` (negation เช่น "don't") (3) อีโมจิแปลงเป็นคำธรรมดา "loudly crying face" ไม่ใช่ `:loudly_crying_face:` เพราะ VADER (NLTK) ไม่รู้จักอีโมจิและอ่านคำติดขีดล่างไม่ออก — ผลทดสอบ 😭: 0 → −0.48 (4) ลบ `u/ชื่อผู้ใช้` และ `r/ชุมชน` (จริยธรรม) (5) ถอด HTML entity และ backslash-escape ของ Reddit (`\$TSLA` → `$TSLA`). **ข้อจำกัด**: อีโมจิสแลงการเงิน เช่น 🚀 ยังเป็นคำกลาง ("rocket") ไม่ได้ถูกตีเป็น bullish — ถ้าจะแปลสแลงต้องเป็นส่วนขยายพร้อมเหตุผล
>
> **ส่วนเสริมใน `processed_text`** (นอกเหนือจากคอลัมน์ที่ TASKS ระบุ): `src_rowid` (PK, ใช้รันต่อ), `content_type`, `subreddit`, `created_utc` (คัดลอกมาเพื่อลดการ join ในขั้นถัดไป); `token_len` = จำนวนคำแยกด้วยช่องว่าง ไม่ใช่ token ของโมเดล

- **Input**: `reddit_content` (เฉพาะ 6 ชุมชน และ `text_status='available'` → 22,840,886 แถว)
- **Output**: `etl/clean_text.py`, ตาราง `processed_text(content_id, final_text, char_len, token_len, cleaned_at, cleaner_version)`
- **ขั้นตอน**: พอร์ต `clean_noise()` จาก cell 5 — ตัด URL, markdown, emote/image artifact, zero-width char, แต่ **ถนอม** `$TICKER`, `%`, `!`, ตัวเลขราคา (VADER ใช้สัญลักษณ์พวกนี้ตีความ — proposal §7.3 ระบุว่า $, %, ! สำคัญ); รวม title+selftext สำหรับ submission (ดู D5); ใส่ `cleaner_version` เพื่อ reproduce ย้อนหลังได้; แปลง `created_utc` เป็น datetime UTC และ hour bucket (proposal §4.1 "แปลงเวลาเผยแพร่เป็นวันที่และเวลา")
- **DoD**: unit test ครอบ ≥ 10 เคส (emoji, URL, code block, ข้อความว่างหลังล้าง, Thai text, `$GME` ต้องรอด); `final_text` ว่าง → ไม่เขียนลงตาราง (proposal §8.4: "final_text ที่ผ่านการล้างแล้วไม่เป็นค่าว่าง")
- **อ้างอิง**: proposal §4.1, §7.1, §8.4; old cell 5

### T2 — Quality filter + กรองภาษาอังกฤษ (QA ภายใน)

> **สถานะ 2026-10-10: ✅ เสร็จและรันกับ DB จริงแล้ว** — `etl/quality_filter.py`, เทสต์ `tests/test_quality_filter.py` 9 ตัวผ่าน. สร้างตาราง `text_filter` (เฉพาะแถวที่ถูกตัด), `data_quality_audit` (ชั่วโมง×ชุมชน×ชนิด×เหตุผล) และ view `filtered_text` (T4/S1/S2 ต้องอ่านจาก view นี้). **ผ่าน DoD**: ผลรวมใน audit = 24,519,179 = จำนวนแถวดิบของ 6 ชุมชน และ removed 1,589,925 / deleted 88,301 / empty 67 ตรง baseline. ผล (วัดจริง): passed 22,029,119 · bot_or_moderation_text 417,853 · empty_after_cleaning 319,136 · too_short 69,049 · non_english 5,729.
> หมายเหตุ: (1) ไม่พอร์ตกฎ `moderator` ของ cell 8 (กว้างเกิน) ใช้วลีเฉพาะที่ดูจากข้อความซ้ำถี่สุดแทน; (2) ภาษากรองด้วย heuristic (อักษรไม่ใช่ละติน + คำฟังก์ชันต่างชาติ) ไม่ใช้โมเดล จึงจับได้เฉพาะข้อความยาว ≥ 6 คำ; (3) คอลัมน์ audit ต่างจากที่เขียนไว้เดิมเล็กน้อย (ใช้ `remove_reason` + `row_count` แบบ long format); (4) เหลือ artefact `emote:t5 2th52:NNN` ใน final_text ~0.006% ไม่แก้
- **Input**: `reddit_content` ใน 6 ชุมชน + ผลจาก T1
- **Output**: `etl/quality_filter.py`, ตาราง QA ภายใน `data_quality_audit(ts_hour, subreddit, content_type, raw_count, removed_count, passed_count, removal_rate, remove_reason)`
- **ขั้นตอน**: จำแนกเหตุผลที่ตัดออกเป็น enum เดียว: `removed`, `deleted`, `empty`, `missing`, `bot_or_moderation_text`, `too_short`, `non_english`, `passed`; พอร์ตกฎจาก cell 8; **กรองภาษาอังกฤษ** (proposal §4.1 ข้อจำกัด: "วิเคราะห์เฉพาะข้อความภาษาอังกฤษ")
- **DoD**: `raw_count = removed_count + passed_count` ทุกชั่วโมง/subreddit; baseline ในขอบเขต 6 ชุมชนที่ต้องได้: removed 1,589,925 + deleted 88,301 + empty 67 (รวม 1,678,293) จาก `text_status` เดิม — ถ้าหลังกรองแล้วห่างมากแปลว่ากฎใหม่กินข้อมูลเกิน
- **ระวัง**:
  - สถานะ: **ไม่ใช่ deliverable ของ proposal ปัจจุบัน** (ไม่มี DimDataQuality / Removal Rate) แต่ยังต้องกรองข้อมูลจริง และตารางนี้ใช้ทำรายงานข้อจำกัด
  - กรองภาษากับ 22.8M แถวต้องเร็ว: ใช้ heuristic ราคาถูก (สัดส่วนตัวอักษร ASCII/ตัวอักษรละติน + stop-word อังกฤษ) ก่อน ห้ามเรียก language-detector ทีละแถว

### T3 — Ticker dictionary 34 สินทรัพย์

> **สถานะ 2026-10-09: ✅ เสร็จ** — `configs/tickers.yaml` (34 ตัว: stock_etf 22 / crypto 6 / futures 6), `etl/ticker_dict.py` (`TickerMatcher.find(text, subreddit, include_weak)`), เทสต์ `tests/test_ticker_dict.py` 19 ตัวผ่าน (รวม false positive KO, COIN, SOL, DOGE, Ripple effect, HOOD, MARA, ขอบเขตคำ, futures). กฎอยู่ใน YAML ไม่ hard-code: alias แบบ case-sensitive (HOOD, MARA, BITO, Apple, Ether), จำกัดตามชุมชน (`doge` นับเฉพาะ r/CryptoCurrency เพราะปี 2025 "DOGE" แปลว่ากรมรัฐบาลสหรัฐด้วย), regex (`Ripple` ไม่นับเมื่อตามด้วย "effect"), `weak` (คำทั่วไป เช่น "gold", "Russell 2000" — ตัดออกได้ตอนทำ sensitivity)
>
> **ทดลองกับตัวอย่างจริง 250,156 ข้อความ (ฐานข้อมูลทดลอง)**: ความเร็ว ≈ 19,400 ข้อความ/วินาที (ทั้งชุด 22.8M ≈ 20 นาที); **10.2% ของข้อความพูดถึง Ticker อย่างน้อย 1 ตัว**; พบครบทั้ง 34 ตัว; ตรวจตัวอย่างด้วยตา 14 ticker × 6 ข้อความ: alias แบบ strong แม่นดี (≥ 90%) ส่วนที่ต้องระวังดูด้านล่าง
>
> **ข้อควรระวังจากผลทดลอง**
> 1. **`gold` (GC=F) แม่นน้อย** — 2,550 mentions (อันดับ 5) ปนกับ "digital gold" (หมายถึง Bitcoin), "gold bonds" ฯลฯ → ควรให้ T4 เก็บแยกจำนวน strong กับ weak และใช้ strong เป็นค่าหลัก
> 2. **`Robinhood` (HOOD) = 924 mentions ส่วนใหญ่พูดถึงแอป/โบรกเกอร์ ไม่ใช่หุ้น** (ตัวเลขนับเป็น "พูดถึงบริษัท" ซึ่งสมเหตุสมผลกับนิยามใน proposal แต่ต้องรู้ไว้ตอนตีความ) เช่นเดียวกับ Coinbase (COIN) ในชุมชนคริปโตที่หมายถึงตลาดซื้อขาย
> 3. **Ticker ที่หายากมาก**: ขยายตัวอย่างเป็นทั้งชุด (×~91) → BITO ≈ 550, RTY=F ≈ 800, NQ=F ≈ 2,200, JNJ ≈ 3,300, KO ≈ 3,500 mentions ตลอด 23 เดือน → panel รายชั่วโมงของตัวเหล่านี้จะว่างเป็นส่วนใหญ่ (กระทบ G7 `min_messages_per_hour` และจำนวนตัวอย่างขั้นต่ำ n ≥ 30 ใน A2) — ตัวเลขนี้เป็นประมาณการจากตัวอย่าง
> 4. ข้อความจากบอท (เช่น "Ban Bet" ของ WSB, ตาราง "Most mentions on ..." ของ r/CryptoCurrency) ยังติดมา — ต้องกรองใน T2
- **Output**: `configs/tickers.yaml` (versioned) + `etl/ticker_dict.py`
- **ขั้นตอน**: ขยายจาก 15 ตัวใน cell 24 ให้ครบ 34 ตัว; กำหนด alias + **stop-word rule** ต่อ ticker (proposal §4.1: "กรองคำทั่วไป (Stop-words) ที่อาจซ้ำกับชื่อหลักทรัพย์")
- **กับดักที่ต้องจัดการให้ครบ** (จาก universe จริง):
  - `KO` ชนกับคำว่า "ko", "KO" ในบริบทมวย/เกม → ต้องบังคับ `$KO` หรือคำว่า "coca"
  - `COIN` ชนกับ "coin" ทั่วไป → ใช้ "coinbase" เท่านั้น
  - `GC=F`, `CL=F`, `NG=F`, `ES=F`, `NQ=F`, `RTY=F` — ไม่มีใครพิมพ์แบบนี้ใน Reddit ต้อง map จาก "gold", "crude", "nat gas", "es futures", "nasdaq futures", "russell"
  - `BRK-B` → "brk", "berkshire"
  - `IWM`/`QQQ`/`SPY` → ตัวย่อสั้น เสี่ยง false positive ต่ำ ใช้ได้
  - `SOL-USD` ชนกับชื่อคน/คำว่า "sol" → บังคับ "solana" หรือ `$SOL`
  - `AMC` ชนกับโรงหนัง (ซึ่งก็คือบริษัทเดียวกัน) → ปล่อยผ่านได้
- **DoD**: ทุก ticker ใน 34 รายการมีอย่างน้อย 1 alias; มี test ยืนยัน false positive ที่ระบุข้างบนไม่ติด; มี test ว่าระบบสกัดเฉพาะ 34 ตัวเป้าหมาย (proposal §8.4)

### T4 — Ticker extraction

> **สถานะ 2026-10-10: ✅ เสร็จและรันกับ DB จริงแล้ว** — `etl/extract_tickers.py` (+ `TickerMatcher.find_split` คืน strong/weak แยก), เทสต์ `tests/test_extract_tickers.py` ผ่าน. อ่านจาก view `filtered_text`; ตาราง `ticker_mentions(content_id, ticker, mention_count, strong_count, src_rowid)`. ผล (วัดจริง): สแกน 22,029,119 ข้อความ, **2,267,938 ข้อความ (10.3%) พูดถึง ticker**, 2,536,024 แถว, พบครบ 34 ตัว.
> ข้อค้นพบสำคัญ (วัดจริง): **GC=F (gold) 163,197 ข้อความ แต่เป็นคำชัดเจนแค่ 1,355** (ที่เหลือคือคำว่า "gold" ลอย ๆ) → ใช้ `strong_count` เป็นค่าหลักของ GC=F หรือยอมรับว่าเป็น "พูดถึงทอง" แบบกว้าง; **RTY=F strong เหลือ 94**. Ticker น้อยสุด: BITO 468, RTY=F 1,216, NQ=F 1,582, JNJ 2,040, ES=F 2,601 ข้อความตลอด 23 เดือน → panel รายชั่วโมงว่างเป็นส่วนใหญ่ (กระทบ G7 และ n ≥ 30 ใน A2). ต้องเคาะ: T5 จะใช้ `mention_count` หรือ `strong_count` เป็น Reddit volume ของ GC=F/RTY=F
- **Input**: `processed_text`
- **Output**: `etl/extract_tickers.py`, ตาราง `ticker_mentions(content_id, ticker, mention_count)` (long format)
- **ขั้นตอน**: พอร์ต regex alias จาก cell 24 (เรียง alias ยาว→สั้น, ใช้ `(?<!\w)...(?!\w)`); เก็บแบบ long ไม่ใช่ JSON list เพื่อ join ใน SQL ได้
- **DoD**: สุ่ม 100 ข้อความมา review ด้วยมือ → precision ≥ 0.9; `ticker_mention_count` ต่อชั่วโมงรวมแล้วตรงกับ measure ตารางที่ 3; คำนวณ KPI **Ticker Mention Rate = Ticker_mention_count ÷ Reddit_volume × 100** (ตารางที่ 4) ได้
- **ระวัง**: 22.8M ข้อความ × regex ใหญ่ = ช้า ต้อง batch + `re.compile` ครั้งเดียว + พิจารณา `multiprocessing`

### T5 — โหลด `FactRedditVolume` (ใหม่)

> **สถานะ 2026-10-10: ✅ เสร็จพร้อม W2 + W4** — `db/schema.sql` (Dim 6 + Fact 3 ตรงรูปที่ 2–4, index (TickerID, TimeID)), `etl/seed_dims.py` (DimTicker 34 / DimSource 12 / DimSentimentSource 7 รวมแถว 'ALL' / DimMajoritySentiment 3 / DimDetectionConfig 30 / DimTime 17,544), `etl/load_fact_reddit_volume.py`; เทสต์ `tests/test_load_fact_reddit_volume.py` 4 ตัวผ่าน (นับมือได้). **ผลจริง**: `FactRedditVolume` 563,726 แถว; ผ่าน DoD: ผลรวม reddit_volume = 2,536,024 = จำนวนแถว ticker_mentions และ ticker_mention_count รวม 3,025,917 ตรงกันพอดี.
> **⚠️ แก้ 2026-10-11**: ข้อความด้านบนเรื่อง `reddit_volume` = จำนวนข้อความที่พูดถึง ticker **ล้าสมัยแล้ว** — ตอนนี้ `reddit_volume` = ข้อความทั้งหมดของชั่วโมง×แหล่ง (ดูบล็อก "แก้ 2026-10-11" ใน D0) และ DoD ใหม่คือ ticker_mention_count รวม = 3,025,917 ตรงกับ `ticker_mentions`, ไม่มีแถวที่ reddit_volume ว่าง; จำนวนแถว Fact ยัง 563,726.
> **ตัดสินใจเดิม (ผู้ใช้ไม่ตอบ → ใช้ค่าตั้งต้น)**: ใช้ `mention_count` (นับรวมคำทั่วไปเช่น "gold") เป็น reddit_volume ของทุก ticker เพราะตรงนิยาม "พูดถึงสินทรัพย์"; `strong_count` เก็บไว้ใน `ticker_mentions` สำหรับ sensitivity. ชั่วโมงที่ไม่มีข้อความ ไม่มีแถว → ตอนทำ panel (P1) ต้อง LEFT JOIN แล้วเติม 0
- **Input**: `processed_text`, `ticker_mentions`, dims จาก W4
- **Output**: `etl/load_fact_reddit_volume.py` → `FactRedditVolume(TimeID, TickerID, SourceID, reddit_volume, ticker_mention_count)`
- **ขั้นตอน**: aggregate ต่อ (ชั่วโมง UTC, ticker, ชุมชน×ประเภทเนื้อหา); ตามข้อสงสัย O1
- **DoD**: ผลรวมต่อ (ชั่วโมง, source) ตรงกับ count จาก `processed_text`; มี test ข้อมูลเล็กที่นับมือได้; Dashboard 7.1-1 ดึงจากตารางนี้ได้โดยไม่ query raw

---

## 5) Stage S — Sentiment Engine (ระบบ 7.3)

### S0 — วัดความเร็วจริงก่อน (บังคับทำก่อน S2)

> **สถานะ 2026-10-09: ✅ เสร็จ** — สคริปต์ `scripts/benchmark_finbert.py`, ผลสรุป `docs/benchmark_finbert.md`. ผล: ~6,000 ข้อความ/วินาที (ตัด 256 token, batch 128), 22.84M ข้อความ ≈ 1.0–1.2 ชั่วโมง (เฉพาะส่วนคำนวณ), VRAM 0.8 GB; FinBERT จัดข้อความเป็น neutral (±0.05) 41.5% / negative 35.6% / positive 22.9% (ตัวอย่าง 10,000 ข้อความ). ข้อติดขัดเรื่อง Smart App Control ที่บล็อก torch แก้แล้วโดยผู้ใช้ปิดเอง
>
> **เหลือทำใน S2 ก่อนรันทั้งชุด**: เทียบคะแนน fp16 กับ fp32 บนตัวอย่าง ~1,000 ข้อความ (ยังไม่ได้ตรวจ)
- **Output**: บันทึกผลลง `docs/benchmark_finbert.md` หรือ comment ใน PR
- **ขั้นตอน**: รัน FinBERT 10,000 ข้อความจริงบนฮาร์ดแวร์ที่จะใช้จริง (Colab T4 ตาม proposal หรือเครื่องอื่น) วัด throughput แล้วคูณกลับเป็นเวลาสำหรับ **22.84M แถว**
- **DoD**: ได้ตัวเลขชัดเจนพอจะเคาะ D2 ได้

### S1 — VADER scoring

> **สถานะ 2026-10-10: ✅ เสร็จและรันกับ DB จริงแล้ว** — `etl/sentiment_vader.py` (+ `status_of` ใน `etl/common.py`), เทสต์ `tests/test_sentiment.py` ผ่าน. เก็บใน **ตาราง `sentiment_vader`** (ไม่ใช่คอลัมน์ใน `sentiment_item`; S4 จะประกอบเป็น `sentiment_item`). ให้คะแนน 22,029,119 ข้อความ (ครบทุกแถวใน `filtered_text`), ช่วง [-1, 1], ความเร็ว ~10,000/วินาที. สัดส่วน (วัดจริง): positive 36.2% · neutral 36.3% · negative 27.5%
- **Input**: `processed_text`
- **Output**: `etl/sentiment_vader.py`, คอลัมน์ `vader_score`, `vader_status` ในตาราง `sentiment_item`
- **ขั้นตอน**: `SentimentIntensityAnalyzer().polarity_scores(text)["compound"]`; batch + resumable (watermark `content_id`); `vader_status` จาก neutral band ±0.05 (D4)
- **DoD**: ทุกแถวใน `processed_text` มี `vader_score` ∈ [-1, 1]; รันซ้ำไม่คำนวณซ้ำ
- **อ้างอิง**: old cell 16; proposal ตารางที่ 11

### S2 — FinBERT scoring

> **สถานะ 2026-10-10: ✅ เสร็จและรันกับ DB จริงแล้ว** — `etl/sentiment_finbert.py`, `scripts/compare_finbert_precision.py`. fp16 เทียบ fp32 บน 1,000 ข้อความ: ต่างกันสูงสุด 0.005, สถานะเปลี่ยน 0.1% → ใช้ fp16. คะแนน = P(pos) − P(neg), ตัดที่ 256 token, batch 128, ความเร็ว ~7,300/วินาที, ตาราง `sentiment_finbert` 22,029,119 แถว. สัดส่วน (วัดจริง): positive 24.0% · neutral 40.8% · negative 35.2%.
> **VADER เทียบ FinBERT (วัดจริง ทั้ง 22.03 ล้านข้อความ)**: ทิศเดียวกัน (บวก-บวก/ลบ-ลบ) 30.8% · ทั้งคู่ neutral 19.6% · **Small Conflict (ฝั่งหนึ่ง neutral อีกฝั่งมีทิศ) 37.9%** · **Hard Conflict (ทิศตรงข้าม) 11.6%** → กฎ conflict resolution (S4) มีผลกับข้อความราว 49.5% ไม่ใช่กรณีขอบ
- **Output**: `etl/sentiment_finbert.py`, คอลัมน์ `finbert_score`, `finbert_status`
- **ขั้นตอน**: `transformers.pipeline("sentiment-analysis", model="ProsusAI/finbert")`; **แปลง label เป็นคะแนน -1..+1** (proposal ระบุแค่ผลลัพธ์อยู่ใน -1..+1 และใช้ neutral band เดียวกับ VADER — แนะนำ `positive_prob − negative_prob` แล้วบันทึกวิธีไว้); truncation 512 token; batch size ปรับตาม VRAM; checkpoint ทุก N batch (งานรันหลายชั่วโมง ต้องกลับมารันต่อได้)
- **DoD**: resume ได้จริงหลัง kill process กลางคัน; `finbert_score` ∈ [-1, 1]; มี log บอก throughput
- **ระวัง**: ถ้า D2 เลือกทางลดขอบเขต ต้องบันทึกว่าแถวไหนไม่ได้คะแนนและเพราะอะไร (`finbert_status = 'not_scored'`) อย่าปล่อย NULL เงียบ ๆ; ถ้ารันบน Colab ให้เขียนผลลง SQLite ไฟล์เล็กแยก (key = `content_id`) แล้วค่อย merge เข้า DB หลัก — ดู §13

### S3 — Rule-based financial keywords

> **สถานะ 2026-10-10: ✅ เสร็จ** (รวมอยู่ใน `etl/resolve_sentiment.py` + `configs/sentiment.yaml`). keyword ที่มี negator 2 คำก่อนหน้า ("not bullish") **ถูกข้าม ไม่ถูกพลิกเป็นตรงข้าม** (ข้อจำกัดที่ต้องเขียนในเล่ม). วัดจริง: none 98.77% · positive 0.76% · negative 0.41% · mixed 0.06% → keyword มีผลกับข้อความน้อยมาก (~1.2%)
> **เคาะแล้ว 2026-10-10: ขอบ band เป็น "มีทิศ"** (ตามธรรมเนียม VADER ของ Hutto & Gilbert: ≥ 0.05 บวก, ≤ −0.05 ลบ, กลาง = −0.05 < s < 0.05) — ตอนแรกเคยแก้เป็นขอบ = neutral ตามตัวอย่างหน้า 28 ของ proposal แล้วกลับคำเพราะขัดกับงานวิจัยที่อ้าง; ป้าย `vader_status` 771 แถวถูกแก้ไปแล้วคืนกลับ (ใช้ `scripts/recompute_status_band.py`), รัน `sentiment_item`/`sentiment_qa`/`reddit_hourly` ใหม่แล้ว. ผลต่อข้อมูลจิ๋วมาก (final positive 34.70% / negative 33.99% / neutral 31.31% เท่ากับก่อนแก้ ณ ทศนิยม 2 ตำแหน่ง). **ต้องแก้เล่ม**: ตัวอย่างหน้า 28–29 ที่เขียน "VADER +0.05 (neutral)" → ใช้ค่าอื่น เช่น +0.03. นิยาม panel strong "≥ 0.05" ใช้ได้ตามเดิม (สอดคล้องกับ status_of)
- **Output**: `configs/sentiment.yaml` (keyword lists), คอลัมน์ `rule_signal` ∈ {positive, negative, mixed, none}
- **ขั้นตอน**: พอร์ตจาก cell 22 แล้วขยายรายการ; proposal ยกตัวอย่าง positive: bullish, buy calls, go long / negative: bearish, buy puts, go short
- **DoD**: keyword อยู่ใน config ไม่ใช่ hard-code; มี test ว่า "not bullish" ไม่ถูกจับเป็น positive (negation handling — ระบุให้ชัดว่าจัดการหรือไม่จัดการ แล้วบันทึกเป็นข้อจำกัด)

### S4 — Conflict resolution → final sentiment

> **สถานะ 2026-10-10: ✅ เสร็จและรันกับ DB จริง** — `etl/resolve_sentiment.py`, เทสต์ `tests/test_resolve_sentiment.py` 7 ตัวผ่าน (รวมตัวอย่างตัวเลขจาก proposal หน้า 28–29). ตาราง `sentiment_item` 22,029,119 แถว, `final_sentiment` ∈ [-1,1] ครบ (bad_rows = 0). วัดจริง `final_method`: small_conflict_no_rule 37.39% · same_direction 30.86% · both_neutral 19.62% · hard_conflict_no_rule 11.45% · small_conflict_rule_agrees 0.28% · small_conflict_rule_clash 0.22% · hard_conflict_rule 0.17% · hard_conflict_mixed_zero 0.01%. final: positive 34.70% · negative 33.99% · neutral 31.31%. (S5 ดูด้านล่าง)
- **Input**: `vader_score/status`, `finbert_score/status`, `rule_signal`
- **Output**: `etl/resolve_sentiment.py`, คอลัมน์ `final_sentiment`, `final_status`, `final_method`
- **ขั้นตอน — ต้องตรงตาม proposal §7.3 ขั้นตอนที่ 3 เป๊ะ (3 กรณี)**:
  1. **Same Direction** — ทั้งคู่ทิศเดียวกัน → **ใช้ค่าเฉลี่ย** (เช่น +0.60, +0.40 → +0.50)
  2. **Small Conflict** (ตัวหนึ่งอยู่ใน neutral band −0.05..+0.05 อีกตัวมีทิศ) → ให้ความสำคัญกับโมเดลที่มีทิศ (Directional Model) แล้วใช้ keyword ตรวจ:
     - keyword สอดคล้องกับโมเดลที่มีทิศ → ใช้ค่าโมเดลนั้น
     - keyword ขัดแย้ง หรือ keyword ผสม (`mixed`) → `final_sentiment = 0.0`
     - ไม่มี keyword → ใช้ค่าโมเดลที่มีทิศ
  3. **Hard Conflict** (ทิศตรงข้ามกันชัดเจน) →
     - มี keyword ที่ระบุเจตนาชัดเจน → ใช้ค่าของโมเดลที่ทิศตรงกับ keyword
     - ไม่มี keyword → `final_sentiment = 0.0`
- **กฎเสริมที่ proposal ไม่ได้ระบุ (ต้องบันทึกเป็นส่วนขยาย/การตีความ — ดู O4)**:
  - **ทั้งสองโมเดล neutral** → ใช้ค่าเฉลี่ย, `final_status = neutral`, `final_method = both_neutral`
  - **keyword เป็น `mixed` ใน Hard Conflict** → ถือว่าไม่มีเจตนาชัดเจน → `0.0` (สอดคล้องกับหลักของ Small Conflict)
  - **มีโมเดลเดียวที่คำนวณได้** (เช่นเมื่อ D2 ลดขอบเขต FinBERT) → ใช้ค่านั้น, `final_method = one_model` — ไม่อยู่ใน proposal ตัวเลข "ทุกแถวมี final_sentiment" จะอ้างได้เฉพาะชุดข้อมูลที่นิยามไว้
- **DoD**: ทุกแถวมี `final_method` ที่ไม่ใช่ค่าว่าง; `final_sentiment` ∈ [-1, 1] (proposal §8.4); มี unit test หนึ่งเคสต่อหนึ่งกรณีย่อย (≥ 8 เคส รวมตัวอย่างตัวเลขจาก proposal: +0.60/+0.40 → +0.50; VADER +0.05/FinBERT +0.65 + "bullish" → +0.65; FinBERT +0.65/VADER −0.55 + "bearish" → −0.55); distribution ของ `final_method` print ได้
- **ระวัง**: โค้ดเก่า (cell 23) ใช้ค่า hard-code 0.70 เมื่อ rule override และใช้ "โมเดลที่แรงกว่า" เป็นตัวตัดสิน — **ทั้งสองอย่างนี้ไม่มีใน proposal** ถ้าจะใช้ต้องแก้ proposal หรือบันทึกเป็นส่วนขยายพร้อมเหตุผล

### S5 — Sentiment QA report

> **สถานะ 2026-10-10: ✅ เสร็จ** — `python -m etl.sentiment_qa` สร้างตาราง `sentiment_qa` (model_status, model_agreement, final_method, rule_signal, range_check). VADER vs FinBERT: same_direction 30.86% · both_neutral 19.62% · small_conflict 37.88% · hard_conflict 11.63%.
- **Output**: `etl/sentiment_qa.py` → ตาราง/รายงาน distribution
- **ขั้นตอน**: ตาม proposal §7.3 ขั้นตอนที่ 4 และ "ผลการวิเคราะห์" — Final Sentiment Distribution (positive/negative/neutral), สัดส่วนที่ VADER กับ FinBERT เห็นตรงกัน/ขัดแย้งกัน, distribution ของ `final_method`
- **DoD**: ออกรายงานเป็นตารางเดียวที่ใช้ตอบ management question "VADER และ FinBERT สอดคล้องกันระดับใด และกรณีขัดแย้งแก้ไขอย่างไร"

---

## 6) Stage M — Market Features (ระบบ 7.2)

### M1 — คำนวณ feature ราคา

> **สถานะ 2026-10-10: ✅ เสร็จและรันกับ DB จริงแล้ว** — `etl/market_features.py`, เทสต์ `tests/test_market_features.py` 8 ตัวผ่าน (ข้อมูลสังเคราะห์ที่รู้คำตอบ: future_return %, ข้าม gap เป็น NULL, z-score ไม่รวมชั่วโมงปัจจุบัน, ATR, RSI, ตัดแถว close NULL). ได้ตาราง `market_hourly_features` 250,253 แถว (= 269,430 − 19,177 แถว close NULL ตรงเป๊ะ) และ `FactMarketPrice` 250,253 แถว.
> **กติกาที่เคาะเอง (ตามค่าตั้งต้น)**: hour_bucket = ปัด timestamp เริ่มบาร์ลงเป็นต้นชั่วโมง (หุ้น 13:30 → 13:00); `future_return_nh` เป็น NULL ถ้าไม่มีบาร์ที่เริ่มหลัง n ชั่วโมงพอดี (NULL = ไม่ valid จึงไม่ต้องมีคอลัมน์ valid_for แยก); `log_return` ใช้เฉพาะเมื่อบาร์ก่อนหน้าห่างพอดี 1 ชั่วโมง; z-score ใช้ 24 ชั่วโมงก่อนหน้าไม่รวมปัจจุบัน (ขั้นต่ำ 5 บาร์); ATR = ค่าเฉลี่ย true range 24 ชั่วโมงรวมบาร์ปัจจุบัน; RSI Wilder 14 บนลำดับบาร์ที่ valid (ส่วนขยาย ข้ามช่วงตลาดปิด).
> **ตัวเลขจริงที่ต้องรู้** (จำนวนแถวที่มีค่าจากทั้งหมด): หุ้น/ETF ต่อ ticker ≈ 3,485 บาร์: future 1h 2,983 (86%), 3h 1,980 (57%), **6h 495 (14%), 12h = 0** · คริปโต ≈ 17,500 บาร์: ทุก horizon ≈ 99.9% · ฟิวเจอร์ส ≈ 11,400 บาร์: 1h 95%, 12h 85% → **หุ้น/ETF ที่ 12h ไม่มีตัวอย่างเลย และ 6h มีน้อยมาก** ต้องเขียนเป็นข้อจำกัดในรายงาน (หรือเคาะนิยาม horizon เป็นชั่วโมงทำการเป็นส่วนขยาย)
- **Input**: `market_bars`
- **Output**: `etl/market_features.py`, ตาราง `market_hourly_features` + โหลด `FactMarketPrice`
- **คอลัมน์ที่ต้องได้** (ตารางที่ 7–8): `close`, `volume`, `future_return_1h/2h/3h/6h/12h`, `RSI`, `ATR` และ KPI: `log_return`, `volume_zscore_24`, `normalized_atr`
- **ขั้นตอน**:
  - `log_return = ln(close_t / close_{t-1}) × 100` (หน่วย %) ต่อ ticker — **แก้จากฉบับก่อน** (ตารางที่ 8 คูณ 100)
  - `future_return_nh = (close_{t+n} − close_t) / close_t × 100` (หน่วย % ตามตารางที่ 7; โค้ดเก่า cell 28 ใช้ log — ยึด proposal)
  - `valid_for_{n}h` flag: true เฉพาะเมื่อ `ts_{t+n} − ts_t == n ชั่วโมงจริง` (กันข้ามวันหยุด/gap; proposal §4.2: "ใช้เฉพาะช่วงเวลาที่มีข้อมูลเพียงพอ")
  - `volume_zscore_24 = (volume_t − μ_24h) / σ_24h` โดยใช้ 24 ชั่วโมงย้อนหลัง
  - `ATR` ช่วง **24 ชั่วโมง**; `normalized_atr = ATR_24h ÷ close × 100` (**แก้จาก ATR 14 เดิม**)
  - `RSI` 14 (proposal ไม่ระบุ period — ดู O6)
- **DoD**: ไม่มีแถวที่ `future_return` คำนวณข้ามช่องว่างโดยไม่ถูก mark; test ด้วยข้อมูลสังเคราะห์ที่รู้คำตอบ; ตรวจเคส `BTC-USD` (24/7) กับ `AAPL` (ตลาดปิด) ว่าได้ flag ต่างกันถูกต้อง; unit test ว่า `future_return` คำนวณถูกตามกรอบเวลา (proposal §8.4)
- **ระวัง (ตรวจเจอจากข้อมูลจริง)**:
  - **ตัดแถว `close IS NULL` ออกก่อนคำนวณทุกอย่าง** (19,177 แถว เป็น placeholder ตลาดปิด ไม่ใช่ราคา) ไม่เช่นนั้น `log_return`/`future_return` จะเป็น NULL หรือคำนวณข้ามช่องผิด
  - **timestamp ของบาร์ = เวลาเริ่มบาร์**: หุ้น/ETF เป็น `xx:30` (13:30–19:30 UTC ≈ 7 บาร์ต่อวันทำการ), คริปโตและฟิวเจอร์สเป็น `xx:00` → join กับ Reddit (hour bucket `xx:00`) ด้วย timestamp ตรง ๆ **ไม่ติดสำหรับหุ้น** ต้องกำหนดกติกา เช่น `hour_bucket = floor(timestamp_utc ถึงชั่วโมง)` แล้วบันทึกไว้ใน §6 ของ blueprint; `close` ของบาร์ที่เริ่มเวลา t คือราคา ณ t+1 ชั่วโมง
  - **horizon 6h/12h ของหุ้น/ETF แทบไม่มีตัวอย่าง** ภายใต้กติกา `ts_{t+n} − ts_t == n ชั่วโมงจริง` เพราะตลาดเปิดแค่ ~7 ชั่วโมงต่อวัน: 12h เป็นไปไม่ได้เลย, 6h ได้เฉพาะบาร์แรกของวัน, 3h ได้ 4 บาร์แรก → ผลของ `stock_etf` ที่ 6h/12h จะเป็น `insufficient_data` (proposal §4.2 ตั้งใจกันข้ามช่วงตลาดปิดอยู่แล้ว) ต้องเขียนไว้ในรายงานเป็นข้อจำกัด หรือเลือกนิยาม horizon เป็นชั่วโมงทำการ (ถ้าเปลี่ยนต้องบันทึกเป็นส่วนขยาย)
  - ชั่วโมง Reddit ส่วนใหญ่ (~80%) ตกนอกเวลาตลาดหุ้น → หุ้น/ETF ใช้ Reddit ได้เฉพาะชั่วโมงที่มีบาร์
- **ระวัง**: นี่คือจุดที่ look-ahead bias เข้าได้ง่ายที่สุด — `future_return` ห้ามถูกใช้เป็น input ของโมเดลเด็ดขาด ใช้เป็น target เท่านั้น

> **M2 (ปิดช่องว่างข้อมูลราคา)** ย้ายขึ้นไปอยู่ §2 แล้ว — ต้องทำก่อน M1 จึงจะได้ future return ครบ
> **ยกเลิก**: M2 เดิม (Data Continuity Rate / Ticker Availability Rate / `missing_ticker_count`) — ไม่อยู่ใน proposal ปัจจุบัน ถ้าต้องการใช้เป็นตัวเลขอธิบายข้อจำกัดในรายงาน ให้ทำเป็นตาราง QA ภายในเท่านั้น (ใช้ `expected_hours()` จาก `ingest/market_fetch.py`)

---

## 7) Stage P — Hourly Aggregation & 9 Panels (เชื่อม 7.1+7.2+7.3 → 7.4)

### P1 — Reddit hourly features

> **สถานะ 2026-10-10: ✅ เสร็จและรันกับ DB จริง** — `etl/reddit_hourly.py`, เทสต์ `tests/test_reddit_hourly.py` 4 ตัวผ่าน (คำนวณมือ: mean, abs mean, ratio รวม = 1, strong กรองระดับข้อความ, ticker เฉพาะข้อความของตัวเอง, ชั่วโมงไม่มีข้อความ = ไม่มีแถว). ตาราง `reddit_hourly` (คีย์ variant × ticker × hour_utc) variant = all / strong (|s| > 0.05) / quality (|s| ≥ 0.30). แถว (วัดจริง): all 16,800 ชั่วโมงรวมตลาด + 282,885 ticker-ชั่วโมง · strong 16,800 + 255,376 · quality 16,798 + 225,880. ticker ครบ 34 ตัวตรง DimTicker. 16,800 จาก 17,544 ชั่วโมงใน DimTime → ตรวจแล้ว: Reddit ครอบคลุม 2024-10-01 00:00 → 2026-08-31 23:00 UTC **ต่อเนื่องไม่มีชั่วโมงว่างเลย**; 744 ชั่วโมงที่ต่างคือส่วนที่ DimTime กว้างกว่าข้อมูล (30 ก.ย. 2024 = 24 ชม. + ก.ย. 2026 = 720 ชม.) ไม่ใช่ช่องว่าง.
> **กติกาที่เคาะเอง**: majority เสมอกัน → neutral > positive > negative; strong ใช้ `>` 0.05 (ขอบ = neutral); `voter_agreement_ratio` คิดจาก final_status.
- **Input**: `sentiment_item` + `ticker_mentions`
- **Output**: `etl/reddit_hourly.py`, ตาราง `reddit_hourly_features`
- **คอลัมน์** (ตารางที่ 13–14): `Reddit_volume`, `sentiment_mean`, `sentiment_abs_mean`, `pos_ratio`, `neg_ratio`, `neu_ratio`, `majority_vader_status`, `majority_finbert_status`, `majority_final_status`, `voter_agreement_ratio` (+ `imbalance` เป็นตัวเลือก — ปรากฏในขอบเขต §4.4/§4.6 แต่ **ไม่อยู่ในตารางที่ 13 หรือ fact** จึงไม่บังคับ)
- **ขั้นตอน**: aggregate 2 ระดับ — (ก) รายชั่วโมงรวมทั้งตลาด [global] (ข) รายชั่วโมง × ticker [จาก `ticker_mentions`, เฉพาะข้อความที่ระบุ ticker นั้น]; พอร์ต `aggregate()` จาก cell 28 แต่เปลี่ยน threshold เป็น 0.05 และเพิ่ม `majority_*_status` 3 ตัว; **ฟังก์ชัน aggregate ต้องรับพารามิเตอร์ filter ระดับข้อความ** (เพื่อใช้ใน P4)
- **สูตรที่ต้องตรง**: `sentiment_mean = ผลรวม final_sentiment ÷ จำนวนข้อความในชั่วโมงนั้น` (ตารางที่ 15), `voter_agreement_ratio = จำนวนข้อความในประเภทที่พบมากสุด ÷ จำนวนข้อความทั้งหมดในชั่วโมงนั้น` (ตารางที่ 13)
- **DoD**: `pos_ratio + neg_ratio + neu_ratio = 1` ทุกแถว; test กับข้อมูลเล็กที่คำนวณมือได้

### P2 — Lag / z-score / momentum

> **สถานะ 2026-10-10: ✅ เสร็จและรันกับ DB จริง** — `etl/reddit_features.py`, เทสต์ `tests/test_reddit_features.py` 5 ตัวผ่าน (z-score ไม่รวมชั่วโมงปัจจุบัน, ชั่วโมงแรก ๆ = NULL, std=0 = NULL, lag นับตามชั่วโมงนาฬิกา ไม่ใช่แถวก่อนหน้า, ไม่ข้าม ticker). ตาราง `reddit_hourly_features` 814,539 แถว (= all 299,685 + strong 272,178 + quality 242,676).
> **กติกาที่เคาะเอง**: (1) ชั่วโมงที่ไม่มีข้อความ = volume 0 (จำนวนจริง) ในหน้าต่าง z-score; sentiment lag ของชั่วโมงที่ไม่มีข้อความ = NULL ไม่ใช่ 0 (2) z-score ใช้ population std เหมือน M1, ต้องมี ≥ 6 ชั่วโมงก่อนหน้าและ std > 0 (3) z-score กับ volume lag คำนวณจาก variant `all` ของ ticker เดียวกันแล้วคัดลอกไปแถว strong/quality เพื่อให้นิยาม "spike" เหมือนกันทุก panel.
- **Output**: เพิ่มคอลัมน์ใน `reddit_hourly_features`
- **คอลัมน์**: `Reddit_volume_zscore_24`, `Reddit_volume_lag_1h`, `sentiment_lag_1h/2h/3h/6h/12h`, `sentiment_momentum_1h` (= `sentiment_mean − sentiment_lag_1h`)
- **ขั้นตอน**: พอร์ต `add_ts_features()` จาก cell 28; z-score = (volume_t − ค่าเฉลี่ย 24 ชั่วโมงก่อนหน้า) ÷ SD 24 ชั่วโมงก่อนหน้า (ตารางที่ 4/15) — **หน้าต่างไม่รวมชั่วโมงปัจจุบัน** (`shift(1)` ก่อน rolling) และ `min_periods` ต้องกำหนดชัด (เช่น 6)
- **DoD**: ค่าที่ชั่วโมงแรก ๆ ของแต่ละ ticker เป็น NULL ไม่ใช่ 0; test ว่า shift ไม่ข้าม ticker; test ว่า z-score ไม่ใช้ข้อมูลของชั่วโมง t เอง

### P3 — Merged hourly panel

> **สถานะ 2026-10-10: ✅ เสร็จและรันกับ DB จริง** — `etl/merge_panel.py`, เทสต์ `tests/test_merge_panel.py` ผ่าน. ตาราง `merged_hourly_panel` = ตลาด 250,253 แถว × 6 บล็อก (scope `ticker`/`global` × variant all/strong/quality) ไม่มีแถวหาย. มี Reddit จริง: global 95.7% (ที่เหลือคือบาร์ราคา 30 ก.ย. 2024 และ ก.ย. 2026 ที่อยู่นอกช่วง Reddit) · ticker-all 49.1% · ticker-strong 45.0% · ticker-quality 40.6%. ไม่มี Reddit → `reddit_volume = 0`, ค่า sentiment = NULL, `has_reddit_data = 0`. `scope=global` คือความรู้สึกรวมทั้งตลาดจับคู่กับราคาของทุก ticker (ใช้กับ panel_global*), `scope=ticker` คือเฉพาะข้อความที่พูดถึง ticker นั้น.
- **Output**: ตาราง `merged_hourly_panel` (market LEFT JOIN reddit ON timestamp + ticker — proposal §7.4: "ใช้ Timestamp และ Ticker เป็น key")
- **ขั้นตอน**: ตั้งต้นจาก market แล้ว LEFT JOIN reddit; เพิ่ม `has_reddit_data` flag; `reddit_volume` ที่ไม่มี → 0 ไม่ใช่ NULL แต่ `sentiment_mean` ที่ไม่มี → NULL (อย่า fillna(0) เพราะ 0 แปลว่า neutral ซึ่งคนละความหมายกับ "ไม่มีข้อมูล"); เพิ่ม `Big_Group` จาก `DimTicker.AssetClass`
- **DoD**: จำนวนแถว = จำนวนแถวของ market ตั้งต้น; `has_reddit_data` นับได้ตรงกับจำนวนชั่วโมงที่มี reddit จริง

### P4 — สร้าง 9 panel

> **สถานะ 2026-10-10: ✅ เสร็จและรันกับ DB จริง** — `etl/build_panels.py`, เทสต์ `tests/test_build_panels.py` 2 ตัวผ่าน. ตาราง `panels` (วัดจริง, ทุก panel ครอบคลุม 34 ticker): global 239,394 · global_strong 239,394 · global_quality 239,377 · global_spike 46,485 · Ticker 122,817 · Ticker_strong 112,663 · Ticker_quality 101,644 · Ticker_spike 32,680 · baseline 239,394 (แถวเดียวกับ global + `random_direction` ±1, seed 42). เก็บเฉพาะแถวที่มี sentiment จริง; spike = `reddit_volume_zscore_24 > 1.5` (ค่า NULL ไม่เข้า). หมายเหตุ: global_strong จำนวนแถวเท่า global เพราะวัดระดับชั่วโมงรวมทั้งตลาด (ข้อความมหาศาลต่อชั่วโมง ทุกชั่วโมงมีข้อความ strong) — ความต่างอยู่ที่ค่า sentiment_mean ไม่ใช่จำนวนแถว.
- **Output**: `etl/build_panels.py`, 1 ตารางกับคอลัมน์ `panel_name` (query ง่ายกว่า 9 ตาราง)
- **นิยามทั้ง 9** (ตารางที่ 12):

| panel | นิยาม |
|---|---|
| `panel_baseline` | เกณฑ์มาตรฐาน ไม่ใช้ตัวชี้วัดความรู้สึก (สุ่มทิศทางผลตอบแทน หรืออัตราถูกต้องพื้นฐาน) — ดู O2 |
| `panel_global` | ความรู้สึกรวมทุก Ticker รายชั่วโมง |
| `panel_global_strong` | global แต่ใช้เฉพาะ **ข้อความ** ที่ `abs(final_sentiment) ≥ 0.05` |
| `panel_global_quality` | global แต่ใช้เฉพาะ **ข้อความ** ที่ `abs(final_sentiment) ≥ 0.30` |
| `panel_global_spike` | global เฉพาะ **ชั่วโมง** ที่ `Reddit_volume_zscore > 1.5` |
| `panel_Ticker` | แยกราย ticker เฉพาะข้อความที่ระบุ ticker นั้นโดยตรง |
| `panel_Ticker_strong` | Ticker + ข้อความ `abs ≥ 0.05` |
| `panel_Ticker_quality` | Ticker + ข้อความ `abs ≥ 0.30` |
| `panel_Ticker_spike` | Ticker + ชั่วโมงที่ `zscore > 1.5` เทียบค่าเฉลี่ยของ ticker นั้น |

- **สำคัญ — ต่างจากแผนฉบับก่อน**: `strong`/`quality` กรองที่ระดับ **ข้อความ** ก่อนสรุปรายชั่วโมง (ไม่ใช่กรองแถวรายชั่วโมงหลังสรุปแล้ว) → ต้องเรียก aggregate ของ P1 ใหม่กับชุดข้อความที่กรองแล้ว; `spike` กรองที่ระดับ **ชั่วโมง**
- **DoD**: เก็บเฉพาะแถวที่มี sentiment จริงตาม proposal §7.4 ("ลดความเบาบาง"); จำนวนแถวแต่ละ panel ลดหลั่นตามเหตุผล (global ≥ strong ≥ quality); มี test ว่าค่า `sentiment_mean` ของ strong ต่างจาก global ในชั่วโมงที่มีข้อความ neutral ปนอยู่ (พิสูจน์ว่ากรองที่ข้อความจริง)
- **ระวัง**: `panel_baseline` ต้องนิยามให้ชัดว่าคืออะไร — แนะนำ: สุ่มทิศทาง (+/−) ด้วย seed คงที่ บนชุดแถวเดียวกับ `panel_global` เพื่อให้เทียบ win rate กันได้ตรง ๆ

---

## 8) Stage A — Research Analytics (ระบบ 7.4)

ทุก task ในขั้นนี้ต้องเขียนผลลง `analysis_results` ตารางเดียวกัน (`run_id`, `panel_name`, `ticker`, `big_group`, `horizon`, `metric_name`, `metric_value`, `p_value`, `n_samples`, `config_hash`, `created_at`) เพื่อให้ dashboard 7.5-2 และระบบ 7.6 ดึงไปใช้ได้โดยไม่ต้องรันใหม่

### A1 — Correlation analysis

> **สถานะ 2026-10-10: ✅ เสร็จและรันกับ DB จริง** — `analysis/correlation.py` + `analysis/results_store.py` (ตาราง `analysis_results` ใช้ร่วม A1–A3), เทสต์ `tests/test_correlation.py` 5 ตัวผ่าน, heatmap 18 รูปใน `output/figures/a1_<panel>_<pearson|spearman>.png`. ได้ 15,048 แถว (13,356 คำนวณได้, 1,692 `insufficient_data` n < 30 เก็บเป็น NULL ไม่ใช่ 0). ติดตั้ง scipy/scikit-learn/matplotlib/seaborn แล้ว (`requirements-analysis.txt`).
> **ผลที่วัดได้ (Spearman, sentiment_mean, รวมทุก ticker)**: ความสัมพันธ์กับ future return **เล็กมาก** |ρ| ≈ 0.001–0.03 ทุก panel ทุก horizon; ที่เด่นสุดคือ panel_global ที่ 12h (ρ ≈ −0.021, n = 155,573) และ panel_global_spike ที่ 12h (−0.028); กับ `log_return` (ชั่วโมงเดียวกัน, ไม่ใช่การทำนาย) เป็นบวก 0.034 (global) และ 0.079 (global_spike) → ความรู้สึกมักตามราคามากกว่านำราคา. หุ้น/ETF ที่ 12h = ไม่มีข้อมูล (n = 0), 6h มี n = 10,406. ตรวจ sanity: panel_baseline (สุ่มทิศ) มี 9 จาก 182 การทดสอบที่ p < 0.05 = 4.9% ตรงกับที่คาดจากโอกาสสุ่ม.
> **ข้อควรระวังที่ต้องเขียนในรายงาน**: ข้อมูลรายชั่วโมงมี autocorrelation และ future return ต่าง horizon ซ้อนทับกัน → p-value เป็นค่าเชิงพรรณนา; ใน panel_global ทุก ticker ใช้ sentiment ตลาดรวมค่าเดียวกัน; การที่ panel_global ที่ 12h มี 9 จาก 9 ticker (BH p < 0.05) ไม่ควรอ่านเป็นหลักฐานนำราคา เพราะเป็นข้อมูลคริปโต/ฟิวเจอร์สที่เทรนด์ต่อเนื่องยาว. ตัวแปรเสริม (lag, momentum, volume z) และ BH เป็น "ส่วนขยาย" ติดป้ายไว้ในตาราง.
- **ขั้นตอน**: Pearson + Spearman ระหว่าง `sentiment_mean` กับ `log_return` และ `future_return_1h/2h/3h/6h/12h` (proposal §7.4 ขั้นตอนที่ 3); วนครบ **9 panel** × 5 horizon × (ราย ticker + ราย asset class + รวม); รายงาน p-value + n; **heatmap Pearson และ Spearman แยกรายตัว Ticker**
- **ส่วนขยาย (ไม่บังคับ)**: เพิ่ม `sentiment_lag_*`, `reddit_volume_zscore`, `sentiment_momentum_1h` เป็นตัวแปรต้นเพื่อตอบคำถามผู้บริหาร "ข้อมูลก่อนหน้าดีกว่าข้อมูล ณ ปัจจุบันหรือไม่"; Benjamini-Hochberg correction รายงานควบคู่ (ไม่อยู่ใน proposal)
- **DoD**: ได้ heatmap ต่อ panel; ผลถูกบันทึกลง `analysis_results`
- **อ้างอิง**: proposal §7.4; old cell 25 (31), 26 (32)

### A2 — Historical Win Rate + Binomial Test

> **สถานะ 2026-10-10: ✅ เสร็จและรันกับ DB จริง** — `analysis/winrate.py`, เทสต์ `tests/test_winrate.py` 4 ตัวผ่าน (คำนวณมือ, ผลตอบแทน = 0 ไม่นับเป็นเหตุการณ์, guard n < 30, Binomial 60/100 → p = 0.057), heatmap 9 รูป `output/figures/a2_<panel>_winrate.png`; ผลในตาราง `analysis_results` (analysis = 'winrate', 6,460 แถว, win rate เก็บเป็นสัดส่วน 0–1, แถว `baseline_winrate` คือ p0 ที่ใช้).
> **นิยามที่ใช้** (ข้อ 4 ใน METHOD_DECISIONS): เหตุการณ์ = ชั่วโมงที่ sentiment มีทิศ (sign ≠ 0 / majority เป็น positive หรือ negative) และ future_return คำนวณได้และ ≠ 0; ชนะ = ทิศตรงกัน; ทดสอบ Binomial สองด้านเทียบกับอัตราชนะของ `panel_baseline` (สุ่มทิศ) ในกลุ่ม/horizon เดียวกัน (baseline เทียบ 0.5), n < 30 → `insufficient_data`.
> **ผลที่วัดได้ (รวมทุก ticker)**: win rate อยู่ที่ **ประมาณ 50% ทุก panel ทุก horizon** — global 49.4–49.9% (ต่ำกว่าสุ่มเล็กน้อย), Ticker 50.0–50.8% (ไม่รวม spike; สูงสุดที่ 12h 50.5–50.8%), Ticker_spike 49.5–50.5%, global_spike 12h ต่ำสุด 48.0%; baseline 49.9–50.1% และมี 4 จาก 148 ticker ที่ p < 0.05 (2.7% ตามโอกาสสุ่ม). p-value ต่ำมากในหลายช่อง (เช่น global 6h) เพราะ n เป็นแสนแถวและข้อมูลซ้อนทับกัน ไม่ใช่เพราะมีความได้เปรียบ — **ห้ามเขียนในรายงานว่ามีนัยสำคัญ = ใช้ทำนายได้**; ความต่างจาก 50% ไม่เกิน ~1.5 จุด (ยกเว้น global_spike 12h).
- **ขั้นตอน**: เทียบทิศ `sign(sentiment_mean)` และ `majority_final_status` กับทิศ `future_return_nh` จริง → win rate; ทดสอบด้วย **Binomial Test** เทียบ `panel_baseline`/ค่าคาดหวังของโมเดลสุ่ม; heatmap win rate รายตัว Ticker; วนครบ 9 panel
- **DoD**: ได้ `winrate_1h..12h` + `winrate_p_value_1h..12h` ครบตามตารางที่ 14 (ลำดับ 13–22) และเขียนลง `FactMarketSentiment`; ต้องมี guard จำนวนตัวอย่างขั้นต่ำ (เช่น n ≥ 30) ไม่งั้น mark เป็น `insufficient_data`
- **อ้างอิง**: old cell 29 (35)

### A3 — Logistic Regression (ทำเมื่อข้อมูลครบเพียงพอ)

> **สถานะ 2026-10-10: ✅ เสร็จและรันกับ DB จริง** — `analysis/logistic.py`, เทสต์ `tests/test_logistic.py` 4 ตัวผ่าน (fold เรียงตามเวลาและเว้น 12 ชั่วโมงจริง, ชั่วโมงเดียวกันไม่อยู่ทั้งฝั่งฝึกและทดสอบ, สัญญาณจริง AUC > 0.8 / สัญญาณสุ่ม ≈ 0.5, แถวที่ขาด feature ถูกตัดไม่เติม 0, ผลตอบแทน = 0 ถูกตัด, ห้ามใช้ score/upvote_ratio/num_comments), รูป `output/figures/a3_auc.png`; ผลในตาราง `analysis_results` (analysis = 'logistic', 3,277 แถว, ฝึก 171 โมเดลสำเร็จ).
> **กติกาที่เคาะเอง**: ฝึกแยก panel × (3 กลุ่มสินทรัพย์ + รวมทุกตัว) × 5 horizon; `TimeSeriesSplit(5, gap=12)` ทำบน "ชั่วโมงไม่ซ้ำ" แล้วแมปกลับเป็นแถว (เพราะแถวรวมหลาย ticker ต่อชั่วโมง gap แบบนับแถวจะไม่ครอบคลุม 12 ชั่วโมง); StandardScaler fit เฉพาะชุดฝึกของแต่ละ fold; coefficient = ค่าเฉลี่ยข้าม fold; "ข้อมูลเพียงพอ" = complete-case ≥ 500 แถวและทุก fold มีทั้งสองคลาส; panel_baseline ใช้ feature เดียวคือ `random_direction`.
> **ผลที่วัดได้**: **AUC เฉลี่ย ≈ 0.50 ทุกช่อง** — รวมทุก ticker ช่วง 0.496–0.513 (panel_global 0.500–0.510, baseline 0.500–0.501) ส่วน fold-to-fold std ≈ 0.003–0.013; ค่าต่ำ/สูงสุด 0.477–0.534 อยู่ในช่องที่ตัวอย่างน้อย (1,244–5,751 แถว, panel_Ticker_spike) → ไม่มีหลักฐานว่าตัวแปร Reddit จำแนกทิศทางผลตอบแทนได้เหนือการสุ่ม. หุ้น/ETF ที่ 12h ไม่มีข้อมูล (insufficient_data 9 ช่อง). ความสำคัญของกลุ่มตัวแปรใน panel_global (รวมทุกตัว): Direction (pos/neg ratio) และ Level สูงสุด, Momentum/Volume ต่ำสุด — แต่เมื่อ AUC ≈ 0.5 ค่า coefficient ไม่ควรตีความเป็นอิทธิพลจริง.
- **ขั้นตอน**: target = ทิศของ `future_return_nh`; feature 6 กลุ่มตาม proposal; `StandardScaler`; `TimeSeriesSplit(n_splits=5)`; รายงาน **AUC-ROC เทียบ Random Baseline AUC** + coefficients (Feature Importance)
- **การแมปกลุ่มตัวแปร (ข้อเสนอ — ต้องยืนยัน, ดู O7)**:

| กลุ่ม | คอลัมน์ที่เสนอ |
|---|---|
| Level | `sentiment_mean`, `sentiment_abs_mean` |
| Direction | `pos_ratio`, `neg_ratio` |
| Vote | `majority_final_status` (encode), `voter_agreement_ratio` |
| Volume | `Reddit_volume_zscore_24` |
| Lag | `sentiment_lag_1h/2h/3h/6h/12h` |
| Momentum | `sentiment_momentum_1h` |

- **DoD**: **ห้ามใช้ shuffle หรือ `StratifiedKFold`** (โค้ดเก่า cell 33/39 ใช้ `StratifiedKFold` = leakage ตามเวลา) ต้องเป็น `TimeSeriesSplit` เท่านั้นตาม proposal
- **ระวัง**: feature ห้ามมี `score`, `upvote_ratio`, `num_comments` (เป็น snapshot จากอนาคต — ดู `SYSTEM_BLUEPRINT_TH.md` §7)
- **หมายเหตุ**: proposal ใช้คำว่า "ในกรณีที่ข้อมูลมีความครบถ้วนเพียงพอ" → ทำหลัง A1/A2 ได้ผลแล้ว และบันทึกเงื่อนไขว่า "เพียงพอ" หมายถึงอะไร

### F1 — โหลด FactMarketSentiment (รูปที่ 4) *(รหัสใหม่; "W3" เดิมคือ index)*

> **สถานะ 2026-10-10: ✅ เสร็จและรันกับ DB จริง** — `etl/load_fact_market_sentiment.py`, เทสต์ `tests/test_load_fact_market_sentiment.py` 3 ตัวผ่าน. `FactMarketSentiment` 250,253 แถว (= แถวตลาด = FactMarketPrice), มี sentiment จริง 122,817 แถว (= แถวของ panel_Ticker), winrate_1h ครบทุกแถว, winrate_12h 173,593 แถว (ticker ที่มีข้อมูล 12h).
> **เกรน (เคาะ 2026-10-10)**: 1 แถว = ชั่วโมง × ticker; `SentimentSourceID` = 'ALL', `DetectionConfigID` = ชุดเริ่มต้น (z 1.5, sentiment 0.30, 1h) ชุดเดียว (id 6) เพราะ win rate เป็นค่าสรุปหลายชั่วโมง ถ้าคูณ 30 ชุดจะได้ ~7.5 ล้านแถวที่ซ้ำกัน; อีก 29 ชุดอยู่ใน `DimDetectionConfig` ให้ระบบสัญญาณ (G) คำนวณตามที่ผู้ใช้เลือกแล้วเก็บใน `signal_events`. `winrate_*` เป็น % ของ A2 (panel_Ticker, sign(sentiment_mean)) ใส่ซ้ำทุกแถวของ ticker นั้น = **ค่าเต็มช่วงข้อมูล ห้ามใช้เป็น feature** (เขียนกำกับใน docstring แล้ว).

### A4 — Subgroup analysis

> **สถานะ 2026-10-10: ✅ เสร็จ** (รวมกับ A5 ใน `analysis/evaluate.py`; ตาราง `evaluation_by_group`).
- **ขั้นตอน**: แยกผล A1–A3 ตาม `Big_Group` ∈ {stock_etf, crypto, futures}
- **DoD**: ตอบคำถามผู้บริหาร "รูปแบบความสัมพันธ์แตกต่างกันอย่างไรระหว่างหุ้น/คริปโต/ฟิวเจอร์ส" ได้จากตารางเดียว
- **อ้างอิง**: old cell 28 (34)

### A5 — Result evaluation (ใหม่ — proposal §7.4 ขั้นตอนที่ 4)

> **สถานะ 2026-10-10: ✅ เสร็จและรันกับ DB จริง** — `analysis/evaluate.py`, เทสต์ `tests/test_evaluate.py` 5 ตัวผ่าน; ตาราง `evaluation_convergence`, `evaluation_by_group`, `evaluation_prior_vs_current`, `evaluation_factor_importance`, `evaluation_panel_ranking` และรายงาน `output/reports/a5_evaluation.md` (สร้างจากสคริปต์ ตัวเลขไม่ได้พิมพ์มือ).
> **นิยาม**: "edge" บวก = สัญญาณ Reddit ชี้ทางเดียวกับผลตอบแทนอนาคต (A1 = ρ, A2 = win rate − baseline, A3 = AUC − 0.5); weak convergence = ทั้งสามมีเครื่องหมายเดียวกัน; strong = weak + p ของ A1 และ A2 < 0.05 + AUC edge > fold std.
> **ผลที่วัดได้ (9 panel ไม่รวม baseline, ระดับรวม + 3 กลุ่มสินทรัพย์, ทุก horizon)**: 152 ช่องที่มีข้อมูลครบ 3 วิธี → weak convergence 43 ช่อง (28%) โดยเป็นทิศบวกแค่ 13 ช่อง; **strong convergence = 0**; ช่องควบคุม panel_baseline (สุ่ม) เห็นตรงกัน 7 จาก 19 ช่อง (37%) — สูงกว่าหรือเท่ากับ panel จริง ซึ่งเข้าได้กับกรณี "ไม่มีสัญญาณ" (สามเหรียญสุ่มเครื่องหมายตรงกัน 25% โดยบังเอิญ). **ข้อสรุปที่เขียนในรายงานได้**: ในระดับรวม ไม่พบหลักฐานว่าตัวชี้วัดจาก Reddit ให้ผลสอดคล้องกันทั้งสามวิธีเกินกว่าที่โอกาสสุ่มอธิบายได้ — **แต่ไม่ได้แปลว่า "ไม่มีผลเลย"**: (2026-10-11, สำรวจรายตัว) sentiment รวมทั้งตลาด (panel_global) มีความสัมพันธ์ **เชิงลบอ่อน ๆ ที่คงที่** กับผลตอบแทน 6–12 ชั่วโมงของ 9 ตัว (คริปโต BTC/SHIB/SOL/DOGE และฟิวเจอร์ส ES/NQ/RTY/GC; ρ −0.02…−0.07, เครื่องหมายเดียวกันทั้งครึ่งแรกและครึ่งหลังของข้อมูล, ใหญ่สุดที่ ES/NQ/RTY) ส่วน sentiment ที่พูดถึง ticker นั้นโดยตรง (panel_Ticker) ไม่มีช่องไหนผ่าน BH. ช่วงพูดคุยเยอะ (spike) ให้ค่าติดลบมากกว่าช่วงปกติในหลายช่อง (ยังไม่ได้ทดสอบความต่างอย่างเป็นทางการ). ข้อจำกัด: ผลเล็กมาก (ρ² < 0.5%), ES/NQ/RTY เคลื่อนไหวตามกันจึงนับเป็นหลักฐานชุดเดียว, ยังไม่ได้คุมผลของชั่วโมงในวัน/วันในสัปดาห์, สำรวจหลังเห็นข้อมูล (post-hoc) → ต้องยืนยันด้วยสคริปต์ A7 ก่อนเขียนเป็นข้อค้นพบ.
- **ขั้นตอน**: (1) ตรวจ **Convergence** — Correlation, Win Rate และ Logistic ชี้ทิศทางเดียวกันหรือไม่ (2) เทียบ 9 panel ว่าเงื่อนไขใดให้ความสัมพันธ์/win rate ชัดสุด (3) เทียบ 3 กลุ่มสินทรัพย์ (4) จาก AUC/coefficients สรุปว่ากลุ่มตัวแปรใด (เช่น Majority Vote vs Sentiment Mean) เกี่ยวข้องกับทิศผลตอบแทนมากสุด
- **DoD**: มีตารางสรุปเดียวต่อคำถามผู้บริหาร 4 ข้อใน §7.4 ข้อ 3

### A6 — Reproducibility harness (ส่วนขยาย)
- **ขั้นตอน**: ทุกครั้งที่รัน analysis ต้องบันทึก `run_id`, git commit, config hash, เวอร์ชันไลบรารี, seed
- **DoD**: รันซ้ำด้วย `run_id` เดิมได้ผลเลขเดียวกันทุกตัว

---

## 9) Stage G — Signal Detection (ระบบ 7.6)

### G1 — Detection config

> **สถานะ 2026-10-11: ✅ เสร็จ** — `configs/detection.yaml` เป็นที่เดียวของ grid (z {1.5, 2.0, 2.5} × sentiment {0.05, 0.30} × horizon 5 ค่า = 30 ชุด), ชุดเริ่มต้นของ Fact และกติการะดับสัญญาณ; `etl/seed_dims.py` และ `etl/load_fact_market_sentiment.py` อ่านจากไฟล์นี้แล้ว (เลิก hard-code). **เคาะแล้ว**: คำนวณล่วงหน้า 6 ชุด (z × sentiment) เก็บใน `signal_events`; horizon เป็นแค่ตัวเลือกสถิติที่แนบ จึงใส่ผ่าน view ไม่ต้องเก็บซ้ำ 5 เท่า.
- **Output**: ตาราง `DimDetectionConfig` ใช้งานจริง + `configs/detection.yaml`
- **พารามิเตอร์**: `ZscoreThreshold`, `SentimentThreshold`, `Horizon` (รูปที่ 4); ต้องตัดสินใจว่าสัญญาณ **คำนวณแบบ on-demand จากพารามิเตอร์ที่ผู้ใช้ตั้งบน dashboard 7.5-2** หรือ precompute ทั้ง grid (แนะนำ on-demand ด้วย SQL view/query + precompute grid เริ่มต้นไว้ให้ `FactMarketSentiment.DetectionConfigID` อ้างได้)

### G2 — Detection engine

> **สถานะ 2026-10-11: ✅ เสร็จและรันกับ DB จริง** — `analysis/signals.py`, เทสต์ `tests/test_signals.py` 5 ตัวผ่าน (ชนิดสัญญาณครบ 4 แบบ, z เท่าเกณฑ์พอดี **ไม่นับ**, ชั่วโมงไม่มีข้อมูล/ข้อความน้อยกว่า 3 ไม่เป็นสัญญาณ, ระดับ low/medium/high, เกณฑ์เข้มขึ้นสัญญาณไม่เพิ่ม). จำนวนสัญญาณ (วัดจริง, ครบ 34 ticker ทุกชุด): z>1.5 & |s|≥0.05 = 73,867 · z>1.5 & |s|≥0.30 = 38,682 · z>2.0 = 68,275 / 29,348 · z>2.5 = 65,327 / 23,907 → เปลี่ยนเกณฑ์แล้วจำนวนเปลี่ยนตามทิศทางที่ควร. ใช้ sentiment ระดับ ticker (เฉพาะข้อความที่พูดถึงตัวนั้น).
> **ส่วนขยายที่เคาะเอง (proposal ไม่กำหนด)**: ต้องมี ≥ 3 ข้อความต่อชั่วโมงจึงนับสัญญาณจาก sentiment; `signal_level` = คะแนน 1–3 จากระยะห่างเหนือเกณฑ์ (z ทุก +1.0 = +1 คะแนน; sentiment ถึง 0.5 / 0.8 = +1 คะแนน) เขียนไว้ใน `configs/detection.yaml`.
- **Output**: `analysis/signals.py`, ตาราง `signal_events` ตามตารางที่ 18: `timestamp, Ticker, Big_Group, sentiment_mean, Reddit_volume, Reddit_volume_zscore, horizon, winrate, correlation_value, signal_type, signal_level` (+ `config_id`, `detected_at` เป็นส่วนเสริม)
- **ประเภทสัญญาณ**: `volume_spike`, `positive_sentiment_spike`, `negative_sentiment_spike`, `combined_signal`
- **ขั้นตอน**: threshold-based ตาม config; `combined_signal` = zscore เกินเกณฑ์ **และ** `sentiment_mean` มีทิศชัด (บวก/ลบเกิน Sentiment Threshold); `signal_level` ∈ {low, medium, high} ตามระดับที่เกินเกณฑ์ (proposal ไม่กำหนดสูตรระดับ — ให้เขียนไว้ใน `configs/detection.yaml`)
- **DoD**: เปลี่ยนค่าใน config แล้วจำนวนสัญญาณเปลี่ยนตามอย่างสมเหตุสมผล; ไม่มีสัญญาณที่ `has_reddit_data = 0`; ตรวจสอบความครบถ้วน timestamp/Ticker/signal_type/signal_level (proposal §7.6 ขั้นตอนที่ 4)

### G3 — Historical statistic lookup

> **สถานะ 2026-10-11: ✅ เสร็จ** — view `v_signal_list` = ตารางที่ 18 (timestamp, ticker, big_group, sentiment_mean, reddit_volume, reddit_volume_zscore, horizon, winrate %, correlation_value, signal_type, signal_level) + `winrate_p_value`, `stat_status` ('insufficient_data' เมื่อ A2 มี n < 30 → ค่าเป็น NULL ไม่ใช่ 0) + คอลัมน์ `note` ว่าไม่ใช่การยืนยันผลตอบแทนหรือคำแนะนำการลงทุน. สถิติมาจาก A1/A2 ของ ticker เดียวกัน (panel_Ticker) ตาม horizon ของชุดเกณฑ์. query ชุดเริ่มต้น 38,682 แถวใช้ 0.04 วินาที (index ครบ). ตาราง `signal_summary` สรุปจำนวนสัญญาณ/จำนวน ticker ต่อชุดเกณฑ์ × ชนิด × กลุ่มสินทรัพย์ (ตัวชี้วัดที่ proposal 4.6 ให้เก็บ).
- **ขั้นตอน**: join `signal_events` กับ `analysis_results` ด้วย key (Ticker, Big_Group, horizon) เพื่อแนบ `winrate` และ `correlation_value`
- **DoD**: ทุกแถวสัญญาณมีสถิติย้อนหลังแนบ หรือระบุชัดว่าไม่มีข้อมูลพอ; ข้อความอธิบายระบุว่า "ไม่ถือเป็นการยืนยันผลตอบแทนหรือคำแนะนำการลงทุน"

---

## 10) Stage D — Streamlit Dashboards (ระบบ 7.5 + หน้าของ 7.1/7.2)

ต้องมี **4 หน้า** ตาม proposal ปัจจุบัน (รูปที่ 5) — ลดจาก 6 หน้าในแผนฉบับก่อน

### D0 — โครงแอป

> **สถานะ 2026-10-11: ✅ D0–D4 เสร็จ ทดสอบแล้ว (ยังไม่ได้ดูด้วยตาจริง — รอผู้ใช้ตรวจหน้าจอ)**. เปิดด้วย `streamlit run dashboard/app.py` (ติดตั้ง streamlit 1.65 แล้ว, อยู่ใน `requirements-analysis.txt`). โครง: `dashboard/app.py` (หน้าแรก), `dashboard/common.py` (ตัวกรองกลาง: กลุ่มสินทรัพย์ → Ticker → ช่วงเวลา, ค่าเริ่มต้นช่วงข้อมูล 30 วันล่าสุด; cache; กราฟ), `dashboard/data.py` (ทุก query, **เชื่อม SQLite แบบ read-only**, อ่านเฉพาะตารางที่ pipeline สร้าง ไม่แตะตาราง raw), `dashboard/pages/1_…4_*.py`. ทุกหน้ามีข้อความ "ไม่ใช่คำแนะนำการลงทุน". ทดสอบ `tests/test_dashboard_smoke.py` 3 ตัวผ่าน: ทุกหน้ารันโดยไม่มี exception (AppTest), ตัวเลขจาก data layer = SQL ตรง ๆ, สัญญาณที่คำนวณทันทีเท่ากับ `signal_events` ที่เก็บไว้ทุกชนิด/ระดับ (z 2.0, sentiment 0.3); เซิร์ฟเวอร์สตาร์ทและตอบ health ok.
> **แก้ 2026-10-11 (ผู้ใช้ทักว่าเข้าใจโจทย์ผิด)**: `Reddit_volume` ของ 7.1 = **ปริมาณโพสต์และความคิดเห็นทั้งหมด** (ตารางที่ 3) ไม่ใช่จำนวนข้อความที่พูดถึง ticker — หลักฐานคือตารางที่ 4: Ticker Mention Rate = Ticker_mention_count ÷ Reddit_volume × 100 (Reddit_volume ต้องเป็นตัวส่วน = ทั้งหมด). แก้แล้ว: `FactRedditVolume.reddit_volume` = ข้อความทั้งหมดของชั่วโมง×แหล่ง (ค่าซ้ำทุกแถว ticker ของชั่วโมงนั้น ห้ามรวมข้าม ticker), ตารางใหม่ `reddit_volume_hourly` (`etl/reddit_volume_total.py`), หน้า "Reddit Volume" ของแดชบอร์ดเริ่มด้วยปริมาณรวมของชุมชน (โพสต์/ความคิดเห็น, Z-score) แล้วค่อยส่วน "สินทรัพย์ที่ถูกพูดถึง". จำนวนข้อความที่พูดถึง ticker ยังอยู่ใน `reddit_hourly` ใช้กับ panel ของการวิเคราะห์ (ตาราง 12: panel_Ticker = เฉพาะข้อความที่ระบุถึงสินทรัพย์นั้น) ซึ่งไม่เปลี่ยน. หมายเหตุ: ปริมาณรวมนับเฉพาะข้อความที่ผ่านการล้างและกรอง (22,029,119 จาก 24.5 ล้านดิบ) โพสต์จึงเหลือน้อย (~0.8%) เพราะโพสต์ลิงก์/รูปที่ไม่มีเนื้อความถูกกรองออก.
> **ข้อเคาะ**: หน้า 4 คำนวณสัญญาณทันทีจากแถบเลื่อน (ไม่จำกัดแค่ค่าใน grid) และค่าที่อยู่ใน grid ให้ผลตรงกับ `signal_events`.
- **Output**: `dashboard/app.py` + `dashboard/pages/`
- **ขั้นตอน**: multipage Streamlit; เชื่อม SQLite แบบ **read-only**; `@st.cache_data` ทุก query; filter กลาง (ช่วงเวลา, ticker, asset class) แชร์ข้ามหน้า; อ่านจากตาราง fact/feature/panel/analysis ที่สร้างไว้ก่อน ไม่ query ตาราง raw 28M แถวตรง ๆ
- **DoD**: เปิดหน้าแรกได้ใน < 3 วินาทีบนข้อมูลเต็ม

### D1 — Dashboard 7.1-1 ปริมาณการกล่าวถึงรายชั่วโมง (Reddit Volume Dashboard)
- ปริมาณโพสต์/ความคิดเห็นรายชั่วโมง, จัดอันดับ ticker ที่ถูกพูดถึงมากสุด, ค่า Reddit Volume Z-score, กราฟแนวโน้ม, เลือก Ticker + ช่วงเวลาได้
- **Measures**: `Reddit_volume`, `Ticker_mention_count` | **KPIs**: Reddit Volume Z-score, Ticker Mention Rate | **Dims**: DimTime, DimTicker, DimSource

### D2 — Dashboard 7.2-1 ราคาและผลตอบแทนรายชั่วโมง (Price and Return Dashboard)
- ราคาปิด, ปริมาณซื้อขาย, future return 5 กรอบเวลา แยกตาม Ticker และกลุ่มสินทรัพย์; ตอบคำถาม "กลุ่มสินทรัพย์ใดผันผวนสูงสุด" (ใช้ Normalized ATR)
- **Measures**: `close`, `volume`, `future_return_1h..12h`, RSI, ATR | **KPIs**: Current Return (ในโค้ด/DB ชื่อ log_return), Volume Z-score, Normalized ATR | **Dims**: DimTime, DimTicker

### D3 — Dashboard 7.5-1 ภาพรวมตลาดและความรู้สึก (Market and Sentiment Overview)
- ราคาปิด + ปริมาณซื้อขาย + `sentiment_mean` + สัดส่วน pos/neg/neu + ประเภทความรู้สึกส่วนใหญ่ + `Reddit_volume` + Z-score พร้อมกราฟแนวโน้มย้อนหลัง เลือกสินทรัพย์/ช่วงเวลาได้
- **Measures**: `close`, `volume`, `sentiment_mean`, `pos_ratio`, `neg_ratio`, `neu_ratio`, `Reddit_volume` | **KPIs**: Sentiment Score, Sentiment Momentum, Reddit Volume Z-score | **Dims**: DimTime, DimTicker, DimSentimentSource, DimMajoritySentiment

### D4 — Dashboard 7.5-2 จัดอันดับและตั้งค่าเกณฑ์ตรวจจับสัญญาณ (Ranking and Detection Configuration)
- ตารางจัดอันดับตาม Historical Win Rate / p-value / Future Return / Reddit Volume Z-score แยกตามกรอบเวลาและกลุ่มสินทรัพย์
- **ต้องมี control ให้ผู้ใช้ปรับ** `Z-score Threshold`, `Sentiment Threshold`, `Horizon` แล้วรายการสัญญาณจาก 7.6 เปลี่ยนตามทันที
- **Measures**: `future_return_1h..12h`, `winrate_1h..12h`, `winrate_p_value_1h..12h`, `sentiment_mean`, `Reddit_volume` | **KPIs**: Historical Win Rate, Reddit Volume Z-score, Sentiment Threshold | **Dims**: DimTime, DimTicker, DimDetectionConfig, DimMajoritySentiment
- **DoD**: ปรับ slider แล้วตารางสัญญาณ re-query ใหม่ใน < 2 วินาที

### D5 — Drill-down กลับถึงข้อความต้นทาง (ส่วนขยาย — ไม่อยู่ใน proposal)
- จากสัญญาณ/ชั่วโมงที่สนใจ กดดูข้อความต้นทางได้ (ย้อนกลับถึง `reddit_content.permalink`) — ทำถ้าเหลือเวลาหลัง D1–D4
- **DoD**: ทุกจุดบนกราฟสืบกลับถึงข้อความจริงได้

> **ยกเลิก**: Dashboard "คุณภาพข้อมูล Reddit" (7.1-2) และ "คุณภาพข้อมูลราคา" (7.2-2) ของแผนฉบับก่อน

---

## 11) Stage Q — Testing & Documentation (proposal §8.4, §8.5)

proposal §8.4 แบ่งการทดสอบเป็น 3 ส่วน: **Unit & Logic**, **Integration**, **Dashboard**

| id | งาน | DoD |
|---|---|---|
| Q1 | Unit & Logic: `final_text` ไม่ว่าง · `final_sentiment` ∈ [−1, +1] · `future_return` คำนวณถูกตามกรอบเวลา · ticker extraction สกัดเฉพาะ 34 ตัวเป้าหมาย · เฉพาะ 6 ชุมชน | coverage ของ logic หลัก ≥ 80% |
| Q2 | Integration: Reddit ↔ ราคา ↔ sentiment ↔ future return เชื่อมกันถูกต้องผ่าน `timestamp + Ticker` และครบถ้วนในแต่ละ horizon | รันบน fixture เล็กจบใน < 2 นาที |
| Q3 | Data test: uniqueness key, null constraint, timestamp continuity, **leakage guard** (ไม่มี future column / `score` / `upvote_ratio` / `num_comments` ใน feature list), z-score ไม่ใช้ชั่วโมงปัจจุบัน | รันเป็นคำสั่งเดียว `pytest -m data` |
| Q4 | Dashboard test: ตัวเลขบนกราฟ/ตาราง/ตัวกรองตรงกับ query ตรงจาก DB และสัญญาณจาก 7.6 แสดงบน 7.5 ครบถ้วน | ทุก KPI บน 4 หน้าตรงกับ SQL |
| Q5 | คู่มือผู้ใช้ตาม §8.5 | อธิบายวิธีอ่าน Reddit Volume Z-score, Sentiment Score, Historical Win Rate, Future Return + วิธีปรับ Z-score Threshold / Sentiment Threshold / Horizon + ระบุข้อจำกัด (ข้อมูลย้อนหลังจาก Academic Torrents ไม่ใช่ real-time, ไม่ใช่คำแนะนำการลงทุนหรือการทำนายราคา) |

---

## 12) ลำดับการทำและ dependency

```
Q0 (แก้ status)  ─── ทำได้เลย ไม่ขึ้นกับใคร
M2 (ปิด gap ราคา) ─── ทำได้เลย (สำรอง market_bars ก่อน) — ต้องเสร็จก่อน M1 จะได้ future return ครบ
D1–D8, O1–O8 (เคาะการตัดสินใจ) ─── ต้องก่อนทุกอย่าง
  │
  ├─ W1 → W2 → W3 → W4                (SQLite foundation: สำรอง → DDL → index → seed dims)
  │        │
  │        └─ T1 → T2                 (ทำขนานกับ T3 ได้)
  │             T3 → T4 → T5
  │                  │
  │                  ├─ S0 → S1, S2 → S3 → S4 → S5
  │                  │
  │                  └─ M1             (ทำขนานกับ S ได้ทั้งหมด หลัง M2)
  │                          │
  │                          └─ P1 → P2 → P3 → P4
  │                                           │
  │                                           ├─ A1, A2, A3 (ขนานกันได้) → A4 → A5 → A6
  │                                           │                              │
  │                                           └─ G1 → G2 ───────────────────┴→ G3
  │                                                                              │
  └─────────────────────────────────────────────────────── D0 → D1..D4 (D5 ถ้าเหลือเวลา)
                                                                        │
                                                                        Q1..Q5
```

**เส้นทางวิกฤต (critical path)**: D2 → S0 → S2 (FinBERT) → P4 → A2 → D4
ถ้า FinBERT ช้ากว่าที่ประเมิน ทั้งสายหลัง S2 เลื่อนหมด → ตัดสินใจ D2 ให้เร็วที่สุด

**ทำขนานได้ตั้งแต่แรก**: M2/M1 (ข้อมูลราคา) ไม่ต้องรอ Reddit เลย
**ที่ตัดออกจากกราฟเดิม**: W1(Docker/Postgres), W3(ETL), W5(partition), M2 เดิม (quality KPI), D2/D4/D7 เดิม

---

## 13) กับดักที่รู้แล้วล่วงหน้า

1. **ไฟล์ `.zst` ของทุกเดือนที่ import ถูกลบหมดแล้ว** (`archive=missing` ทั้ง 25 แถวใน `pipeline_status`) — SQLite คือสำเนาเดียวของข้อมูลดิบ อย่าวางแผนที่ต้อง re-import; **สำรอง `output/reddit.sqlite3` (12.76 GB) ก่อนเขียนตารางใหม่** และห้ามลบ 3 ชุมชนนอกขอบเขตออกจากไฟล์หลัก (กรองใน query แทน — D6)
2. **FinBERT ไม่ใช่คอขวดแล้ว (วัดจริงแล้ว)** — 22.84M ข้อความ ≈ 1.0–1.2 ชั่วโมงเฉพาะส่วนคำนวณบน RTX 5070 (~6,000 ข้อความ/วินาที) รวมอ่าน/ล้าง/เขียนฐานข้อมูลประมาณ 2–3 ชั่วโมง (ฉบับก่อนประเมิน 11–21 ชั่วโมงบน T4); คอขวดจริงของ pipeline จึงน่าจะเป็นการล้างข้อความ/สกัด Ticker (regex กับ 22.8M แถว) และการเขียนฐานข้อมูล ดู `docs/benchmark_finbert.md`
3. **Colab + Google Drive (ตาม proposal) vs SQLite 12.76 GB**: ผู้ใช้เลือกรันบนเครื่องตัวเอง จึงไม่มีปัญหานี้ในทางปฏิบัติ; ถ้าภายหลังต้องใช้ Colab อย่าเปิด SQLite บน Drive แล้วเขียนตรง ๆ ให้เขียนผลลง SQLite ไฟล์เล็กแยกแล้ว merge
4. **โค้ดเก่าใช้ `StratifiedKFold`** = leakage ตามเวลา ต้องเป็น `TimeSeriesSplit` เท่านั้น
5. **`future_return` ใน proposal เป็น % และ `log_return` เป็น ln × 100** — โค้ดเก่าเป็น log return ของ future ยึด proposal; ถ้าจะใช้ log ต้องเพิ่มเป็นคอลัมน์แยก
6. **`sentiment_mean = NULL` ≠ `0`** — 0 แปลว่า neutral, NULL แปลว่าไม่มีข้อความ อย่า fillna
7. **ticker alias ชนคำทั่วไป** (`KO`, `COIN`, `SOL`) — ดู T3
8. **ช่วงเวลา market ยาวกว่า reddit เล็กน้อย**: market 2024-09-30 → 2026-09-30 vs Reddit 2024-10-01 → 2026-08-31 — ชั่วโมงที่ `has_reddit_data = 0` มีแค่ราว 1 วัน (2024-09-30) กับทั้งเดือน 2026-09 (ฉบับก่อนเขียน "7 เดือน" ซึ่งล้าสมัยแล้ว) → ตัดหรือเก็บต้องประกาศให้ชัด
9. **`score`/`upvote_ratio`/`num_comments` เป็น snapshot จากอนาคต** — ห้ามเข้าโมเดล (README อธิบายไว้แล้ว)
10. **พื้นที่ดิสก์**: SQLite 12.76 GB + ไฟล์สำรอง 13 GB + ตารางใหม่ (`processed_text`, `sentiment_item` ≈ 22.8M แถวต่อตาราง) → เตรียมว่างอย่างน้อย ~50 GB (ฉบับก่อนเขียน 25 GB สำหรับ Postgres ซึ่งไม่ใช้แล้ว)
11. **yfinance จำกัดข้อมูลรายชั่วโมงย้อนหลังราว 730 วัน** (ตรวจยืนยันก่อนเชื่อ) — ช่วง 2024-09/10 อาจดึงซ้ำไม่ได้ ดังนั้นแถวใน `market_bars` ที่ได้มาแล้วคือสำเนาเดียว → สำรองก่อนรัน M2
12. **ชื่อ measure/KPI/dimension ในโค้ดต้องตรง proposal** (เช่น `Reddit_volume`, `Ticker_mention_count`, `DimMajoritySentiment`) จะได้อ้างอิงตอนสอบ — ทั้งนี้ proposal ใช้ตัวพิมพ์ต่างกันบางที่ (`Reddit_volume` ในตารางที่ 3 vs `reddit_volume` ในรูปที่ 2) ให้ใช้ตามรูป DDL
13. **proposal อ้างอิงชุดข้อมูล Academic Torrents ช่วง 2005-06 ถึง 2025-12 (บรรณานุกรม)** แต่ใน warehouse มีข้อมูลถึง 2026-08 — ตรวจให้แน่ใจว่าการอ้างอิงในรายงานตรงกับ torrent ที่ใช้จริง
14. **Timeline ใน proposal (ตารางที่ 19: มี.ค.–ก.ค. 2569)** ยังไม่ตรงกับสถานะปัจจุบัน (ยังไม่มีขั้น transform/sentiment/dashboard) — ตรวจกับอาจารย์ที่ปรึกษาว่าไทม์ไลน์ยังใช้ตามนี้หรือปรับ
15. **แถวราคา `close IS NULL` 19,177 แถวคือ placeholder ไม่ใช่ราคา** (ฟิวเจอร์สพักรอบ/เสาร์–อาทิตย์) — กรองก่อนคำนวณ return (ดู M1)
16. **timestamp หุ้นเป็น `xx:30`, คริปโต/ฟิวเจอร์สเป็น `xx:00`** — ต้องมีกติกา hour bucket ก่อน merge กับ Reddit (ดู M1/P3)
17. **horizon 6h/12h ของหุ้น/ETF แทบไม่มีตัวอย่าง** เพราะตลาดเปิดวันละ ~7 ชั่วโมง — คาดว่าผล `stock_etf` ที่ horizon ยาวจะเป็น `insufficient_data` (ดู M1)
18. **`expected_hours()` ไม่รู้จักวันตลาดปิดครึ่งวัน** — หุ้น/ETF ~14–15 ชั่วโมงต่อตัวที่ถูกนับเป็น gap เป็น false positive
