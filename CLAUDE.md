# CLAUDE.md

โปรเจกต์วิทยานิพนธ์/โครงการพิเศษ (จุฬาฯ MSc BIT): คลังข้อมูล + BI ของ **ความรู้สึกจาก Reddit เทียบกับราคาหลักทรัพย์ 34 ตัว** (รายชั่วโมง) — ข้อมูลย้อนหลัง ไม่ใช่ real-time ไม่ใช่คำแนะนำการลงทุน

## เอกสารที่ต้องอ่าน (เรียงตามอำนาจ)

1. `data/Proposal_6782094726_Rithipong_Leanghirunkun.pdf` — **source of truth** ของ requirement (**ฉบับที่ได้รับอนุมัติแล้ว**, 58 หน้า; ถ้าขัดกับไฟล์อื่น ให้ยึด proposal). ไฟล์ `Wait_for_approve_…rev1/rev2.pdf` ถูกลบแล้ว; เอกสารช่วยแก้ proposal (`PROPOSAL_REVISIONS.md`, `PROPOSAL_EDIT_GUIDE.md`, `COVER_SHEET_ADDITIONS.md`) ผู้ใช้สั่งลบแล้ว 2026-10-24 — เหตุผลของส่วนที่ proposal ไม่ได้ระบุอยู่ที่ `docs/METHOD_DECISIONS_NOT_IN_PROPOSAL.md`
2. `docs/METHOD_DECISIONS_NOT_IN_PROPOSAL.md` — วิธีที่เลือกเองในจุดที่ proposal ไม่ได้ระบุ (7 ข้อ) + สถานะโค้ด
3. `TASKS.md` — งานระดับลงมือทำ (รหัส T/S/M/P/A/G/D/Q/W), สถานะข้อมูลจริง, "ผลการเคาะล่าสุด", กับดัก (§13)
4. `SYSTEM_BLUEPRINT_TH.md` — สถาปัตยกรรม, time alignment, leakage policy
5. `CODE_STRUCTURE.md` — โครงโฟลเดอร์ + แผนที่ proposal → สคริปต์ → ตารางผลลัพธ์ + เช็กลิสต์ก่อนปิดเล่ม
6. `README.md` — วิธีใช้ `ingest/reddit_extract.py` (ยังเขียนว่า 9 ชุมชน — ล้าสมัย)

ส่วนที่ทำเกิน proposal ต้องติดป้าย "ส่วนขยาย" และจดไว้ในรายงาน

## กฎที่ห้ามพลาด

- **`output/reddit.sqlite3` (~12.8 GB) คือสำเนาเดียวของข้อมูลดิบ** (ไฟล์ `.zst` ถูกลบหมดแล้ว) ห้าม DELETE/UPDATE/DROP/VACUUM ตาราง `reddit_content`, `market_bars`, `market_windows`, `market_gaps`; อ่านด้วย `sqlite3.connect('file:output/reddit.sqlite3?mode=ro', uri=True)`; ตารางใหม่เพิ่มได้ แต่ถามก่อนทำงานเขียนหนัก (ผู้ใช้เลือกไม่ทำไฟล์สำรอง = รับความเสี่ยงเอง)
- **ใช้เฉพาะ 6 ชุมชน**: wallstreetbets, stocks, investing, StockMarket, options, CryptoCurrency — ใน DB มีอีก 3 (Bitcoin, Daytrading, dogecoin) ให้ **กรองใน query ไม่ลบแถว**
- **ราคา**: ตัดแถว `close IS NULL` (19,177 แถว เป็น placeholder ตลาดปิด ไม่ใช่ราคา); timestamp ของบาร์ = เวลา **เริ่ม** บาร์ (หุ้น `xx:30`, คริปโต/ฟิวเจอร์ส `xx:00`) → ปัดเป็นต้นชั่วโมงก่อน join กับ Reddit
- **Leakage**: ห้ามใช้ `score`/`upvote_ratio`/`num_comments` หรือ `future_return_*` เป็น feature; แบ่งข้อมูลด้วย `TimeSeriesSplit(n_splits=5, gap=12)` เท่านั้น (ห้าม shuffle/StratifiedKFold); fit `StandardScaler` เฉพาะชุดฝึก
- **ค่าตายตัวจาก proposal**: neutral band ±0.05 · strong |s| ≥ 0.05 · quality |s| ≥ 0.30 · spike z > 1.5 · horizon 1/2/3/6/12 ชั่วโมง · `future_return` เป็น **%** · `log_return = ln(close_t/close_{t-1}) × 100` · z-score ใช้ 24 ชั่วโมง **ก่อนหน้า ไม่รวมชั่วโมงปัจจุบัน**
- `sentiment_mean = NULL` (ไม่มีข้อความ) ≠ `0` (neutral) — ห้าม `fillna(0)`
- ชื่อตาราง/คอลัมน์ star schema ต้องตรงรูปที่ 2–4 ของ proposal (DDL อยู่ที่ TASKS W2) เพราะต้องอ้างในรายงาน
- ไม่เอาชื่อผู้ใช้ Reddit (`author`) ไปใช้วิเคราะห์หรือโชว์บนแดชบอร์ด
- ถามก่อนติดตั้งแพ็กเกจใหญ่ หรือดาวน์โหลดโมเดล/ข้อมูลจากเน็ต; อย่า commit `data/`, `output/`, `old_code/` (โน้ตบุ๊ก MVP เก่า มีข้อความ Reddit จริงฝังอยู่ใน output — อยู่ใน `.gitignore` แล้ว)

## คำสั่ง (Windows / PowerShell)

```powershell
.\venv\Scripts\Activate.ps1                          # ถ้าไม่ได้: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
python ingest/pipeline_status.py --db output/reddit.sqlite3 # สถานะรายเดือน (Reddit import / market)
python ingest/reddit_extract.py fetch 2026-03 --db output/reddit.sqlite3   # ต้องมี aria2c (ก๊อปไว้ใน venv\Scripts แล้ว)
python -m unittest discover -s tests                 # ห้ามใส่ -t .  (ImportError)
```

- venv ใช้ Python 3.14 (README บอก 3.9+) — แพ็กเกจที่ต้อง wheel (torch ฯลฯ) ตรวจความเข้ากันได้ก่อน
- **เทสต์: 154 ตัวผ่านทั้งหมด (2026-10-25)** — เดิม error 9 ตัวเป็น `PermissionError [WinError 32]` เพราะเทสต์ไม่ปิดไฟล์ SQLite ก่อนลบโฟลเดอร์ชั่วคราว แก้แล้วด้วย `closing`/`committing` ในเทสต์; `tests/test_reddit_extract.py` ว่างเปล่า
- เครื่อง: Windows 11 (PC ส่วนตัว ไม่ใช่เครื่ององค์กร), RTX 5070 (12 GB), RAM 32 GB, ดิสก์ C: ว่าง ~350 GB
- **Smart App Control: ผู้ใช้ปิดเองแล้ว (2026-10-09)** เพราะมันบล็อก `torch\lib\c10.dll` (`WinError 4551`); หลังปิด `import torch` ใช้ได้และเห็น RTX 5070 (`torch 2.11.0+cu128`, capability 12.0) — ถ้าเจอ `WinError 4551` กับไลบรารีอื่นอีก **ห้ามหลบ/ปิดนโยบายความปลอดภัยเอง** ให้แจ้งผู้ใช้ตัดสินใจ
- แพ็กเกจที่ติดตั้งเพิ่มใน venv แล้ว: `torch`, `transformers` (ยังไม่ได้เพิ่มลง `requirements*.txt`); ไฟล์ wheel ของ torch เก็บไว้ที่ scratchpad (`...\scratchpad\wheels\`)
- pip บน Windows: ติดตั้งไฟล์ใหญ่ (torch ~2.8 GB) ตรง ๆ อาจล้มด้วย `WinError 32` (Defender ล็อกไฟล์ชั่วคราว) → ใช้ `pip download -d <โฟลเดอร์>` ก่อน แล้ว `pip install <ไฟล์.whl>`; **อย่าเชื่อ exit code ของคำสั่งที่ต่อท่อกับ `tail`** — ตรวจด้วย `import` จริง

**`final_text` ของคอมเมนต์ = title ของโพสต์แม่ + body คอมเมนต์** (cleaner_version 2.0, เคาะ 2026-10-24; รุ่นแรกที่ใช้ body อย่างเดียวผิด ไม่ตรงงานเก่า) — `own_text` คือสิ่งที่คนเขียนเอง ใช้ใน T2 และคำสำคัญ S3; อย่าย้อนกลับไปใช้ body อย่างเดียว

## ลำดับรัน

โฟลเดอร์ `steps/` มีตัวเรียกที่ขึ้นต้นด้วยเลข (`01_extract_reddit.py` … `24_check_proposal_coverage.py`) เรียกโค้ดจริงตามลำดับ — ไฟล์โค้ดจริงไม่เปลี่ยนชื่อ (python import โมดูลที่ขึ้นต้นด้วยตัวเลขไม่ได้); เพิ่ม/เปลี่ยนขั้นตอนต้องอัปเดต `steps/README.md` และ `tests/test_steps.py`. `scripts/check_proposal_coverage.py` ตรวจว่า DB + dashboard ตอบตารางค่าวัด/KPI ของ proposal ครบ

## ทุกอย่างต้องเป็นโค้ด (เพราะต้องลงรูปเล่ม)

ทุกขั้นตอนของ pipeline ต้องเป็นสคริปต์ `.py` ที่รันซ้ำได้จาก command line; **ตัวเลข ตาราง กราฟที่จะลงเล่ม ต้องมาจากสคริปต์** (ไม่ใช่ query ที่รันมือแล้วจำผล); notebook ใช้สำรวจเท่านั้น. ถ้าผมคำนวณอะไรด้วยโค้ดชั่วคราวระหว่างแชท แล้วตัวเลขนั้นจะถูกใช้ต่อ ให้ย้ายเป็นสคริปต์ใน `scripts/` (ดูกติกา 6 ข้อใน `CODE_STRUCTURE.md`) และเมื่อเพิ่ม/เปลี่ยนสคริปต์ ให้อัปเดตตารางแผนที่ใน `CODE_STRUCTURE.md` ด้วย

ไฟล์ผลลัพธ์ที่สคริปต์สร้าง (รายงาน .md, ตาราง .csv) ต้องขึ้นต้นด้วยคำอธิบายว่าไฟล์นี้คืออะไร + วันเวลาที่สร้าง + สคริปต์ + คำสั่งสร้างใหม่ — ใช้ `etl.common.file_header(...)`; สิ่งที่ผู้ใช้เห็น (UI/กราฟ/รายงาน) เรียก `log_return` ว่า **Current Return** (ชื่อคอลัมน์ในฐานข้อมูลคงเดิม)

## สไตล์โค้ด

- `ingest/reddit_extract.py` ใช้ **tab**; `ingest/market_fetch.py`, `ingest/pipeline_status.py`, `ingest/pipeline_logs.py` ใช้ **4 space** — ตามสไตล์ของไฟล์ที่แก้
- ใช้ `sqlite3` มาตรฐาน + `unittest` (ตามที่มีอยู่); คอมเมนต์/ชื่อในโค้ดเป็นอังกฤษ
- โค้ดใหม่แยกเป็นโฟลเดอร์ `configs/`, `db/`, `etl/`, `analysis/`, `dashboard/` ตามเป้าหมายใน Blueprint §4; สคริปต์นำเข้าข้อมูล 4 ตัวอยู่ใน `ingest/` (ย้ายจาก root 2026-10-28 ตามที่ผู้ใช้สั่ง)
- ค่าตั้ง (6 ชุมชน, 34 ticker/alias, threshold) อยู่ใน config ที่เดียว ไม่ hard-code ซ้ำ
- ไฟล์ชั่วคราว/ผลสำรวจ → โฟลเดอร์ scratchpad ไม่ใช่ในรีโป

## วิธีทำงานกับผู้ใช้

- **ตอบเป็นภาษาไทย ใช้คำง่าย ๆ** — ผู้ใช้บอกชัดว่าถ้าอธิบายยากจะงง ให้ยกตัวอย่างสั้น ๆ แทนศัพท์; ผู้ใช้พิมพ์เร็วมักมีคำผิด ตีความตามบริบท ถ้าไม่ชัด (เช่นตอบสั้น ๆ ว่า "ง") ให้ถามยืนยันสั้น ๆ ก่อนลงมือ
- เมื่อผู้ใช้ **เคาะเรื่องใด** ให้บันทึก 3 อย่าง: ตัดสินใจอะไร + เพราะอะไร + กระทบโค้ดข้อไหน ลงใน `docs/METHOD_DECISIONS_NOT_IN_PROPOSAL.md` (ถ้าเป็นเรื่องที่ proposal ไม่ได้ระบุ) และตาราง "ผลการเคาะล่าสุด" ใน `TASKS.md`
- ก่อนอ้างตัวเลขข้อมูล ให้ตรวจจาก DB จริง (ตัวเลขใน TASKS §0 ตรวจเมื่อ 2026-10-09 อาจเก่า) และบอกให้ชัดว่าอันไหน "วัดจริง" อันไหน "ประมาณการ"
- ตัวช่วยตรวจสถานะเร็ว ๆ: `ingest/pipeline_status.py` (Reddit รายเดือน + market), ตาราง `market_windows` (สถานะ complete/needs_review/unavailable)
- ลำดับงานที่ตกลงกันไว้: ติดตั้ง torch + วัดความเร็ว FinBERT (S0) → T1–T4 (ล้างข้อความ, ticker) → M1 (feature ราคา) → S1–S5 → P → A → G → D; รายละเอียดและ DoD ดู `TASKS.md`
