# Reddit Sentiment × Market Warehouse

คลังข้อมูล (data warehouse) + แดชบอร์ด ที่เอา **ความรู้สึกของข้อความใน Reddit** มาเทียบกับ **ราคาหลักทรัพย์ 34 ตัว (รายชั่วโมง)** เพื่อดูว่าความรู้สึกบน Reddit มีความสัมพันธ์กับราคาในอนาคตหรือไม่

โปรเจกต์วิทยานิพนธ์/โครงการพิเศษ จุฬาฯ MSc BIT — requirement ทั้งหมดอิงตัว proposal (`data/…rev1.pdf`)

> ข้อควรรู้ก่อนเริ่ม
> - ใช้ข้อมูล **ย้อนหลัง** ไม่ใช่ real-time
> - เป็นเครื่องมือช่วยวิเคราะห์ **ไม่ใช่คำแนะนำการลงทุน** และไม่ใช่การทำนายราคา
> - ข้อมูล Reddit/ราคา/ฐานข้อมูล **ไม่ถูกเผยแพร่** (โฟลเดอร์ `data/` และ `output/` ถูก gitignore) โปรเจกต์นี้ไม่ได้แจกจ่ายเนื้อหา Reddit
> - ไม่ใช้ชื่อผู้ใช้ Reddit (`author`) ในการวิเคราะห์หรือโชว์บนแดชบอร์ด

---

## 1) ภาพรวม: ระบบนี้ทำอะไรทีละขั้น

คิดเหมือนสายพานโรงงาน: ของดิบเข้าทางซ้าย ของสำเร็จออกทางขวา และทุกขั้นเก็บผลลงฐานข้อมูล SQLite ไฟล์เดียว (`output/reddit.sqlite3`)

```
 ① Reddit ดิบ (ไฟล์ .zst รายเดือน)        ② ราคา (Yahoo Finance)
        │  reddit_extract.py                    │  market_fetch.py
        ▼                                       ▼
   reddit_content  ─────────────────────►   market_bars
        │  (ข้อความดิบ ทุกโพสต์/คอมเมนต์)         │ (ราคารายชั่วโมง 34 ตัว)
        ▼                                       │
 ③ ล้างข้อความ → กรองคุณภาพ/ภาษา → หาชื่อหุ้น    │
        ▼                                       │
 ④ ให้คะแนนความรู้สึก VADER + FinBERT          │
   → รวมผล/แก้ขัดแย้ง → sentiment_item          │
        ▼                                       ▼
 ⑤ สรุปรายชั่วโมงต่อ ticker  ──────►  ⑥ รวมกับราคา (merged_hourly_panel) → 9 panel
                                                │
                                                ▼
                         ⑦ วิเคราะห์: Correlation · Win Rate · Logistic Regression
                                                │
                                                ▼
                         ⑧ ตรวจจับสัญญาณ  →  ⑨ Dashboard (Streamlit 5 หน้า)
```

**ขอบเขตที่ล็อกไว้ (อยู่ใน `configs/` ที่เดียว)**

| อะไร | ค่า | ไฟล์ |
|---|---|---|
| ชุมชน Reddit | 6 ชุมชน: wallstreetbets, stocks, investing, StockMarket, options, CryptoCurrency | `configs/subreddits.yaml` |
| สินทรัพย์ | 34 ตัว (หุ้น/ETF, คริปโต, ฟิวเจอร์ส) + ชื่อเรียกอื่น (alias) | `configs/tickers.yaml` |
| คำสำคัญทางการเงิน (bullish, buy calls …) | ใช้ตัดสินตอนโมเดลสองตัวเห็นไม่ตรงกัน | `configs/sentiment.yaml` |
| เกณฑ์ตรวจจับสัญญาณ | Z-score / Sentiment / Horizon | `configs/detection.yaml` |

> ฐานข้อมูลมี 3 ชุมชนเกินมา (Bitcoin, Daytrading, dogecoin) เพราะตัวนำเข้าดึงมา 9 ชุมชน — **ไม่ลบแถวทิ้ง** แต่ทุก query ปลายน้ำกรองให้เหลือ 6 ชุมชนเอง

---

## 2) ของที่ต้องมีก่อนเริ่ม

| ของ | ใช้ทำอะไร | จำเป็นเมื่อไหร่ |
|---|---|---|
| Windows (PowerShell) หรือ macOS (zsh/bash) | เอกสารนี้ให้คำสั่งทั้งสองแบบทุกจุดที่ต่างกัน | ทุกขั้น |
| Python (ที่ใช้จริง 3.14; README เก่าบอก 3.9+) | รันทุกสคริปต์ | ทุกขั้น |
| `aria2c` | ดาวน์โหลดไฟล์ Reddit จาก torrent | ขั้น 01 แบบ `fetch` เท่านั้น |
| ไฟล์ `.torrent` ของแต่ละเดือน (วางใน `data/`) | บอก aria2c ว่าจะโหลดอะไร | ขั้น 01 แบบ `fetch` เท่านั้น |
| **Windows**: การ์ดจอ NVIDIA + CUDA 12.8 (ตัวที่ใช้: RTX 5070 12 GB) | รัน FinBERT (~6,000 ข้อความ/วินาที) | ขั้น 08 **เท่านั้น** |
| เน็ต | โหลดราคาจาก Yahoo, โหลดโมเดล FinBERT / VADER lexicon ครั้งแรก | ขั้น 02, 07, 08 |
| ดิสก์ว่างอย่างน้อยหลายสิบ GB | ฐานข้อมูลดิบ ~12.8 GB + ตารางที่สร้างเพิ่ม (sentiment ~22M แถว) | ทุกขั้น |

> ⚠️ **ขั้น 08 (FinBERT) รันได้เฉพาะเครื่องที่มี CUDA GPU เท่านั้น** โค้ดเช็กและหยุดทันทีถ้าไม่เจอ (`CUDA GPU not available`) — **Mac ไม่มี NVIDIA GPU จึงรันขั้น 08 ไม่ได้** (ไม่ใช่แค่ช้า แต่รันไม่ได้เลยตามที่โค้ดตั้งใจล็อกไว้ เพราะข้อมูล 22 ล้านแถวไม่มี GPU จะช้าเกินจะใช้งานจริง) ดูทางแก้ที่ §3.3
>
> ถ้าคุณ **มี `output/reddit.sqlite3` อยู่แล้ว** (เช่นเครื่องนี้) ข้ามขั้น 01–02 ได้ แล้วเริ่มที่ขั้น 03

---

## 3) ติดตั้ง (ทำครั้งเดียว)

### 3.1 สร้างและเปิด virtual environment

**Windows (PowerShell)**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS (zsh/bash)**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

เปิดสำเร็จเมื่อหน้าบรรทัดมี `(.venv)`

> ⚠️ **คำสั่ง activate ของสอง OS ใช้แทนกันไม่ได้**
> - รัน `.\.venv\Scripts\Activate.ps1` บน macOS (zsh) → ไม่รู้จักคำสั่ง (zsh กินเครื่องหมาย `\` ทิ้งจนกลายเป็น path เพี้ยน เช่น `..venvScriptsActivate.ps1`)
> - รัน `source .venv/bin/activate` บน Windows PowerShell → ขึ้น `source : The term 'source' is not recognized`
> เช็กว่าอยู่ OS ไหนแล้วใช้บล็อกที่ตรงกัน
> บน PowerShell ถ้าเจอ "running scripts is disabled" ให้สั่งครั้งเดียว: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` แล้วลอง `Activate.ps1` ใหม่
> (โฟลเดอร์จะชื่อ `venv` หรือ `.venv` ก็ได้ ขอให้ activate ตรงชื่อที่สร้าง)

### 3.2 ติดตั้งแพ็กเกจ — แบ่ง 3 ชุดตามขั้นที่ใช้

```powershell
python -m pip install -r requirements.txt            # ชุดที่ 1: นำเข้า Reddit + ดึงราคา + อ่าน config
python -m pip install -r requirements-analysis.txt   # ชุดที่ 2: pandas, scipy, scikit-learn, matplotlib, streamlit
```

| ไฟล์ | มีอะไร | ทำไมแยก |
|---|---|---|
| `requirements.txt` | zstandard, yfinance, pyyaml, emoji | ขั้นต้นน้ำ (01–06) ใช้แค่นี้ |
| `requirements-analysis.txt` | pandas, numpy, scipy, scikit-learn, matplotlib, seaborn, streamlit | ขั้นวิเคราะห์และแดชบอร์ด (11–24) |
| `requirements-sentiment.txt` | torch, transformers, nltk | หนักมาก (torch ~2.8 GB) ติดตั้งเมื่อจะรันขั้น 07–08 |

### 3.3 ติดตั้งชุด sentiment (torch)

**Windows (NVIDIA GPU, CUDA 12.8) — ระวังเป็นพิเศษ**

torch ต้องใช้ build CUDA 12.8 (การ์ด RTX 50xx ต้อง CUDA ≥ 12.8) และไฟล์ใหญ่มาก pip ติดตั้งตรง ๆ อาจล้มด้วย `WinError 32` (Defender ล็อกไฟล์ชั่วคราว) ให้ **โหลดไฟล์ก่อนแล้วค่อยติดตั้ง**:

```powershell
pip download torch==2.11.0 --no-deps --index-url https://download.pytorch.org/whl/cu128 -d wheels
pip install wheels\torch-2.11.0+cu128-cp314-cp314-win_amd64.whl
python -m pip install transformers==5.19.0 nltk==3.10.3
python -c "import nltk; nltk.download('vader_lexicon')"
```

ตรวจว่า GPU เห็นจริง (อย่าเชื่อแค่ว่า pip จบโดยไม่ error):

```powershell
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

> ถ้า `import torch` ขึ้น `WinError 4551` แปลว่า Windows (Smart App Control) บล็อก `c10.dll` — **อย่าหลบนโยบายความปลอดภัยเอง** ให้ตัดสินใจเรื่องเปิด/ปิดด้วยตัวคุณเอง (เครื่องพัฒนาเครื่องนี้ผู้ใช้ปิดเองแล้ว)

**macOS — ขั้น 08 รันไม่ได้ (ตั้งใจล็อกไว้), ขั้น 07 รันได้ปกติ**

โค้ด `etl/sentiment_finbert.py` เช็ก `torch.cuda.is_available()` แล้ว `raise SystemExit("CUDA GPU not available...")` ทันทีถ้าไม่เจอ — Mac ไม่มี NVIDIA GPU จึงชน error นี้เสมอ **ไม่ต้องติดตั้ง torch/transformers บน Mac** เพราะใช้ไม่ได้อยู่ดี ติดตั้งแค่ nltk พอ (ใช้กับขั้น 07 VADER):

```bash
python -m pip install nltk==3.10.3
python -c "import nltk; nltk.download('vader_lexicon')"
```

**วิธีทำงานข้าม OS ที่แนะนำ:** รันขั้น 08 บนเครื่อง Windows+GPU เท่านั้น ขั้นที่เหลือ (01–07, 09–24) รันบน Mac ได้ปกติ — เสร็จขั้น 08 บน Windows แล้วก๊อปปี้ `output/reddit.sqlite3` (มีตาราง `sentiment_finbert` ติดไปด้วย) มาที่ Mac แล้วรันขั้น 09 ต่อ
>
> ถ้าอยากให้ Mac รันขั้น 08 เองได้ (ช้ากว่ามาก ผ่าน MPS หรือ CPU) ต้องแก้โค้ด `etl/sentiment_finbert.py` ให้เลือกอุปกรณ์อัตโนมัติแทนการบังคับ `.cuda()` — เป็นการเปลี่ยนโค้ดที่กระทบตัวเลขความเร็วที่อ้างอิงใน `docs/benchmark_finbert.md` (วัดบน RTX 5070) **ควรคุยกับทีมก่อนแก้** ไม่ใช่แค่เปลี่ยนเพื่อความสะดวก

### 3.4 ตรวจว่าติดตั้งถูก

```powershell
python pipeline_status.py --db output/reddit.sqlite3
```

ถ้ายังไม่มี DB คำสั่งนี้ก็รันได้ (แค่รายงานว่ายังว่าง) — มันอ่านอย่างเดียว ปลอดภัย

---

## 4) วิธีรัน: ทีละขั้น พร้อมเหตุผล

ทุกขั้นเรียกผ่านโฟลเดอร์ **`steps/`** ซึ่งมีไฟล์ขึ้นต้นด้วยเลข 00–24 รันตามเลขจากน้อยไปมาก

```powershell
python steps/<ชื่อไฟล์>.py [ตัวเลือก]        # ใส่ --help เพื่อดูตัวเลือกของขั้นนั้น
```

ทำไมต้องมี launcher: ไฟล์โค้ดจริงอยู่ที่ `etl/`, `analysis/`, `scripts/` และ root ซึ่ง Python import ชื่อที่ขึ้นต้นด้วยตัวเลขไม่ได้ จึงเอาเลขลำดับไว้ที่ตัวเรียกแทน (ไม่ต้องใช้ launcher ก็ได้ เช่น `python -m etl.clean_text` ให้ผลเหมือนกัน)

**หลักการร่วมของทุกขั้น**
- ตัวเลือก `--db` ค่าเริ่มต้นคือ `output/reddit.sqlite3`
- **รันซ้ำได้** ไม่ได้แถวซ้ำ; งานยาว (ล้างข้อความ, ให้คะแนน) ทำเป็นก้อน ๆ แล้วต่อจากที่ค้างได้
- `--rebuild` = ทิ้งตารางผลของขั้นนั้นแล้วทำใหม่ทั้งหมด (ไม่แตะข้อมูลดิบ)
- `--limit-rows N` = ลองรันแค่ N แถวแรกเพื่อทดสอบก่อน (มีใน 04, 05, 06, 07, 08, 09)

---

### ช่วง A — เอาข้อมูลดิบเข้าฐานข้อมูล

#### ขั้น 00 · ดูสถานะ (รันตอนไหนก็ได้)

```powershell
python steps/00_pipeline_status.py --db output/reddit.sqlite3
```
**ทำไม:** บอกว่าเดือนไหนนำเข้า Reddit แล้ว เดือนไหนมีราคาแล้ว/ยังขาด อ่านอย่างเดียว ไม่แก้ DB

#### ขั้น 01 · นำเข้าข้อมูล Reddit → ตาราง `reddit_content`

**ข้อมูลดิบคืออะไร:** Reddit แจกข้อมูลเป็นไฟล์บีบอัดรายเดือนแบบ `.zst` (Pushshift/Academic Torrents) เดือนละ 2 ไฟล์
- `RS_YYYY-MM.zst` = โพสต์ (submissions)
- `RC_YYYY-MM.zst` = คอมเมนต์ (comments)

เดือนหนึ่งสองไฟล์รวมกัน **~45–50 GB** ห้ามแตกไฟล์เอง (สคริปต์อ่านแบบสตรีมจากไฟล์บีบอัดโดยตรง)

**วิธีที่ 1 — ทำให้จบในคำสั่งเดียว (แนะนำ)**
```powershell
python steps/01_extract_reddit.py fetch 2024-10 --db output/reddit.sqlite3
```
คำสั่งนี้ทำ 3 อย่างต่อกัน:
1. หาไฟล์ `.torrent` ของเดือนนั้นใน `data/` (ค้นจากข้อความ "from 2024-10" ในไฟล์) แล้วสั่ง `aria2c` โหลดมา
2. อ่านทั้ง `RS_` และ `RC_` → เลือกเฉพาะ 9 ชุมชน → ใส่ตาราง `reddit_content`
3. **ลบไฟล์ `.zst` ทิ้ง** เพื่อประหยัดดิสก์ (ใส่ `--keep-archive` ถ้าไม่อยากลบ)

> ⚠️ เพราะข้อ 3 ไฟล์ `.zst` ของเดือนที่นำเข้าแล้วจึงหายไปหมด — **`reddit.sqlite3` คือสำเนาเดียวของข้อมูลดิบ** อย่าลบไฟล์นี้ และอย่าสั่ง DELETE/UPDATE/DROP/VACUUM ตารางดิบ

ตัวเลือก: `--data <โฟลเดอร์>` ถ้า torrent/archive ไม่ได้อยู่ใน `data/` · รันเดือนเดิมซ้ำปลอดภัย (ตรวจเจอว่านำเข้าแล้วจะข้าม; ID ของโพสต์/คอมเมนต์เป็น key ไม่ซ้ำ)

**วิธีที่ 2 — มีไฟล์ `.zst` อยู่แล้ว (ไม่ผ่าน torrent)**

Windows (PowerShell):
```powershell
python steps/01_extract_reddit.py import --db output/reddit.sqlite3 --submissions data\reddit-2024-10\reddit\submissions\RS_2024-10.zst --comments data\reddit-2024-10\reddit\comments\RC_2024-10.zst
```
(ใส่ทั้งคำสั่งในบรรทัดเดียว อย่าใช้ `\` ต่อบรรทัด; path ที่มีเว้นวรรคให้ใส่เครื่องหมายคำพูด)

macOS (zsh/bash) — path ใช้ `/` แทน `\`:
```bash
python steps/01_extract_reddit.py import --db output/reddit.sqlite3 --submissions data/reddit-2024-10/reddit/submissions/RS_2024-10.zst --comments data/reddit-2024-10/reddit/comments/RC_2024-10.zst
```

**วิธีที่ 3 — ส่งออกเป็น JSON (ไม่บังคับ)**

Windows:
```powershell
python steps/01_extract_reddit.py export --db output/reddit.sqlite3 --output output\reddit_2024-10.json
```
macOS:
```bash
python steps/01_extract_reddit.py export --db output/reddit.sqlite3 --output output/reddit_2024-10.json
```

**ผลลัพธ์:** ตาราง `reddit_content` เก็บโพสต์และคอมเมนต์ในตารางเดียว (`content_type` = `submission` หรือ `comment`) พร้อมคอลัมน์ `text_status` = `available` / `removed` / `deleted` / `empty` / `missing`

**ทำเฉพาะเดือนที่ยังไม่มี:** ช่วงข้อมูลที่ใช้คือ **2024-10 → 2026-08** (23 เดือนติดกัน) ส่วน 2024-09 และ 2026-09 ต้นทางไม่มีข้อมูลให้โหลด

**ข้อควรระวังเรื่องคะแนนความนิยม:** ฐานข้อมูลเก็บ `score`, `upvote_ratio`, `num_comments` ไว้ แต่ค่าเหล่านี้เป็น "ภาพถ่ายตอนดึงข้อมูล" ไม่ใช่สิ่งที่รู้ ณ เวลาที่โพสต์ — **ห้ามใช้เป็น feature ทำนาย** (จะเป็นการแอบดูอนาคต / look-ahead bias)

#### ขั้น 02 · ดึงราคารายชั่วโมง → ตาราง `market_bars`

```powershell
python steps/02_fetch_market.py nov24              # ดึงเดือน พ.ย. 2024
python steps/02_fetch_market.py oct24 jan25        # ดึงตั้งแต่ ต.ค. 2024 ถึง ม.ค. 2025 (เดือนท้าย "รวม" ด้วย)
python steps/02_fetch_market.py oct24 --audit-only # ตรวจราคาที่มีแล้ว ไม่ยิง Yahoo
```
ตัวเลือกอื่น: `--ticker AAPL` (ทดลองตัวเดียว) · `--start 2024-10-01 --end 2024-11-01` (กำหนดวันเอง, วันจบไม่รวม) · `--days 14` ขนาดหน้าต่างต่อคำขอ · `--retries 3` · `--pause 2` วินาที

**ทำไมต้องรัน:** ต้องมีราคาไว้เทียบกับความรู้สึก 34 ตัว (หุ้น/ETF, คริปโต, ฟิวเจอร์ส) แบบรายชั่วโมง ใช้ yfinance (Yahoo)

**สิ่งที่สคริปต์ทำให้:** ดึงทีละ 14 วัน, ลองใหม่ถ้าว่าง/error, บันทึกทุกแท่งที่ Yahoo ส่งมา (รวมแท่งที่ราคาเป็นค่าว่าง), ข้ามหน้าต่างที่สำเร็จแล้วเมื่อรันซ้ำ, และสรุปช่องว่างลง `market_windows` / `market_gaps`

**ข้อจำกัดที่ต้องรู้**
- Yahoo ให้ข้อมูลรายชั่วโมงย้อนหลังแค่ **~730 วัน** → ช่วงที่เก่ากว่านั้น **ดึงใหม่ไม่ได้** (จะถูกทำเครื่องหมาย `unavailable`) อย่าลบหรือเขียนทับราคาที่มีอยู่แล้ว
- "ดึงสำเร็จ" ไม่ได้แปลว่า Yahoo มีครบทุกชั่วโมง ตลาดปิดเสาร์–อาทิตย์/วันหยุด ฟิวเจอร์สมีเวลาซื้อขายเฉพาะตัว — ช่องว่างที่ตรวจพบเป็นการประมาณ ต้องเทียบปฏิทินตลาดเอง
- แถวที่ `close` เป็น NULL (ราว 19,000 แถว) คือ placeholder ตอนตลาดปิด **ไม่ใช่ราคา** — ขั้น 11 ตัดทิ้งเอง
- เวลาของแท่งคือเวลา **เริ่ม** แท่ง: หุ้น/ETF เป็น `xx:30` ส่วนคริปโต/ฟิวเจอร์สเป็น `xx:00` (ดู §6)

---

### ช่วง B — เตรียมฐานข้อมูลและข้อความ

#### ขั้น 03 · สร้างโครง star schema + ตารางมิติ (Dim)

```powershell
python steps/03_create_schema_and_dims.py
```
**ทำไม:** สร้างตารางตามรูปที่ 2–4 ของ proposal (`db/schema.sql`) และใส่ข้อมูลตารางมิติ: `DimTime` (ทุกชั่วโมง), `DimTicker` (34), `DimSource` (12 = 6 ชุมชน × Post/Comment), `DimSentimentSource` (7), `DimDetectionConfig` (30), `DimMajoritySentiment` (3) ชื่อตาราง/คอลัมน์ต้องตรง proposal เพราะต้องอ้างในรายงาน รันซ้ำปลอดภัย (`IF NOT EXISTS`)

#### ขั้น 04 · ล้างข้อความ → `processed_text`

```powershell
python steps/04_clean_text.py
```
**ทำไม:** ข้อความดิบมี URL, markdown, ตัวอักษรแปลก ๆ โมเดลอ่านแล้วเพี้ยน สคริปต์จึงสร้าง `final_text` ที่สะอาด โดยโพสต์ = `title + selftext` (ไม่มี selftext ใช้แค่ title), คอมเมนต์ = `body` — **ตั้งใจเก็บสัญลักษณ์ที่มีความหมายทางการเงิน** เช่น `$`, `%`, `!`, ตัวพิมพ์ใหญ่ และเครื่องหมายอะพอสทรอฟี เพราะ VADER ใช้ตัวพิมพ์ใหญ่/เครื่องหมายเหล่านี้ช่วยตัดสินอารมณ์ และเก็บเวลาเป็นชั่วโมง UTC ให้พร้อม join กับราคา
กรองเฉพาะ 6 ชุมชนที่ขั้นนี้ (ไม่ลบข้อมูลดิบ)

#### ขั้น 05 · กรองคุณภาพ/ภาษา → `text_filter`, view `filtered_text`

```powershell
python steps/05_quality_filter.py
```
**ทำไม:** ไม่ใช่ทุกข้อความควรให้คะแนน ขั้นนี้ติดป้ายสถานะ เช่น ถูกลบ/removed, ว่าง, สั้นเกินไป, ไม่ใช่ภาษาอังกฤษ (proposal จำกัดภาษาอังกฤษ) และผ่าน (`passed`) แล้วสร้าง view `filtered_text` = เฉพาะข้อความที่ผ่าน ขั้นต่อไปทั้งหมดใช้ view นี้ ตาราง `data_quality_audit` เก็บบันทึกไว้เขียนข้อจำกัดในรายงาน

#### ขั้น 06 · หาชื่อหุ้น/เหรียญในข้อความ → `ticker_mentions`

```powershell
python steps/06_extract_tickers.py
```
**ทำไม:** ต้องรู้ว่าข้อความไหนพูดถึงสินทรัพย์ตัวไหน (AAPL, TSLA, BTC …) จึงจะรวมความรู้สึกต่อ ticker ได้ ใช้พจนานุกรม `configs/tickers.yaml` (cashtag เช่น `$TSLA`, ชื่อบริษัท, alias)
**ระวังคำกำกวม:** คำสั้นที่ชนกับคำทั่วไป (KO, COIN, SOL, ES, NQ, GC, CL, NG, RTY) **ไม่ถูกจับแบบคำเปล่า** จับได้เฉพาะ cashtag/ชื่อเต็ม และ DOGE นับเฉพาะใน r/CryptoCurrency ใช้ `--rebuild` เพื่อสร้างใหม่หลังแก้พจนานุกรม

---

### ช่วง C — ให้คะแนนความรู้สึก (sentiment)

คะแนนทุกตัวอยู่ในช่วง **−1 ถึง +1**; ช่วง **−0.05 < คะแนน < +0.05 ถือว่า neutral** (ค่านี้อยู่ใน config ปรับเพื่อทำ sensitivity analysis ได้)

#### ขั้น 07 · VADER → `sentiment_vader`

```powershell
python steps/07_sentiment_vader.py
```
**ทำไม:** VADER เป็นพจนานุกรมอารมณ์ที่เร็วและออกแบบมาสำหรับข้อความโซเชียล (เข้าใจ `!!!`, ตัวพิมพ์ใหญ่) เป็นโมเดลตัวที่ 1 ต้องโหลด `vader_lexicon` ของ NLTK ไว้ก่อน (ขั้น 3.3)

#### ขั้น 08 · FinBERT → `sentiment_finbert` (ใช้ GPU)

```powershell
python steps/08_sentiment_finbert.py                    # ค่าเริ่มต้น fp16
python steps/08_sentiment_finbert.py --limit-rows 50000 # ลองก่อนนิดหน่อย
```
**ทำไม:** FinBERT (`ProsusAI/finbert`) เป็นโมเดลภาษาที่ฝึกกับข้อความการเงิน เข้าใจบริบทดีกว่าพจนานุกรม เป็นโมเดลตัวที่ 2 — เปิดดูคะแนนสองตัวเทียบกันแล้วลดการตีความผิดของตัวใดตัวหนึ่ง
**คะแนนคำนวณยังไง:** FinBERT ให้ความน่าจะเป็น 3 ค่า (pos/neg/neutral) → ใช้ `P(positive) − P(negative)` ได้ค่า −1..+1
**เวลา:** ส่วนคำนวณ ~1.0–1.2 ชม. สำหรับ 22 ล้านข้อความ (วัดจริง ~6,000 ข้อความ/วินาที ตัดที่ 256 token, batch 128, VRAM < 1 GB) แต่เวลารวมจริงนานกว่านี้เพราะต้องอ่าน/เขียนฐานข้อมูล
**ครั้งแรก** จะดาวน์โหลดโมเดลจาก Hugging Face (ต้องมีเน็ต)
ตัวเลือก: `--dtype fp32` (ช้ากว่า แม่นยำกว่านิดเดียว; ตรวจแล้ว fp16 ต่างจาก fp32 ไม่เกิน 0.005) · `--window` ขนาดก้อนต่อรอบ · `--rebuild`

#### ขั้น 09 · รวมผล + แก้ความขัดแย้ง → `sentiment_item`

```powershell
python steps/09_resolve_sentiment.py
```
**ทำไม:** โมเดลสองตัวอาจเห็นไม่ตรงกัน (ตัวหนึ่งบวก อีกตัวลบ) ขั้นนี้สรุปเป็น `final_sentiment` ต่อข้อความตามกฎ 3 กรณีของ proposal:

| กรณี | ทำยังไง |
|---|---|
| Same Direction (ทิศเดียวกัน) | เฉลี่ยสองคะแนน |
| Small Conflict (ตัวหนึ่ง neutral อีกตัวมีทิศ) | ดูคำสำคัญ (`configs/sentiment.yaml`) ช่วยตัดสิน |
| Hard Conflict (ทิศตรงข้าม) | ใช้คำสำคัญตัดสิน ถ้าไม่มี/ปนกัน = 0.0 |

บวกกฎเสริม 3 ข้อที่ proposal ไม่ได้ระบุ (**ส่วนขยาย**): both_neutral, hard_conflict_mixed_zero, one_model — ทุกข้อความบันทึกวิธีที่ใช้ไว้ใน `final_method` เพื่อตรวจย้อนหลัง รายละเอียด: `docs/METHOD_DECISIONS_NOT_IN_PROPOSAL.md`

#### ขั้น 10 · ตรวจคุณภาพความรู้สึก → `sentiment_qa`

```powershell
python steps/10_sentiment_qa.py
```
**ทำไม:** สรุปการกระจายของคะแนน และสัดส่วนที่ VADER กับ FinBERT เห็นตรงกัน/ขัดกัน ไว้ใช้เขียนรายงาน

---

### ช่วง D — สร้างตารางรายชั่วโมง แล้วรวมกับราคา

#### ขั้น 11 · feature ของราคา → `market_hourly_features`, `FactMarketPrice`

```powershell
python steps/11_market_features.py
```
**ทำไม:** แปลงราคาดิบเป็นตัวแปรที่ใช้วิเคราะห์ โดยตัดแถว `close IS NULL` ก่อน:
- Current Return = `ln(close_t / close_{t-1}) × 100` — ใน proposal ชื่อ `current_return` แต่ **คอลัมน์ในฐานข้อมูลยังชื่อ `log_return`** (เปลี่ยนเฉพาะป้ายที่แสดง; ดู `docs/METHOD_DECISIONS_NOT_IN_PROPOSAL.md` §6)
- `future_return_1h/2h/3h/6h/12h` — ผลตอบแทนอนาคต **หน่วยเป็น %** (ใช้เป็น "เป้าหมาย" เท่านั้น ห้ามเป็น feature)
- RSI, ATR (24 ชม.), Normalized ATR = ATR ÷ close × 100, Volume Z-score
- ธงว่าคู่ข้อมูลใช้ได้ไหม (ไม่คำนวณผลตอบแทนข้ามช่องว่างแบบไม่ติดป้าย)

**หมายเหตุ:** หุ้น/ETF เปิดวันละ ~7 ชั่วโมง ผลตอบแทน 6 ชม./12 ชม. จึงมีตัวอย่างน้อยมาก — ระบบติดป้าย `insufficient_data`

#### ขั้น 12 · สรุป Reddit รายชั่วโมงต่อ ticker → `reddit_hourly`

```powershell
python steps/12_reddit_hourly.py
```
**ทำไม:** รวมคะแนนของข้อความทั้งหมดที่พูดถึง ticker หนึ่งในชั่วโมงหนึ่งให้เป็นแถวเดียว: `sentiment_mean`, สัดส่วน pos/neg/neu, เสียงข้างมาก, จำนวนข้อความ ฯลฯ
**กฎสำคัญ:** `sentiment_mean = NULL` (ชั่วโมงนั้นไม่มีข้อความ) **ไม่เท่ากับ** `0` (มีข้อความและกลาง ๆ) — ห้าม `fillna(0)`

#### ขั้น 13 · lag / momentum / Z-score → `reddit_hourly_features`

```powershell
python steps/13_reddit_features.py
```
**ทำไม:** สร้างตัวแปรเชิงเวลา: ความรู้สึกย้อนหลัง 1/2/3/6/12 ชม., momentum, และ Z-score ของปริมาณ Reddit — **คิดจาก 24 ชั่วโมงก่อนหน้า ไม่รวมชั่วโมงปัจจุบัน** (ถ้ารวมจะเป็นการแอบดูอนาคต)

#### ขั้น 14 · รวมราคา + Reddit → `merged_hourly_panel`

```powershell
python steps/14_merge_panel.py
```
**ทำไม:** เชื่อมสองฝั่งด้วย (ชั่วโมง UTC, ticker) ปัญหาคือเวลาแท่งหุ้นเป็น `xx:30` แต่ Reddit เป็นชั่วโมงเต็ม → ปัดเวลาแท่งราคาลงเป็นต้นชั่วโมงก่อน join (ดู §6)

#### ขั้น 15 · สร้าง 9 panel → `panels`

```powershell
python steps/15_build_panels.py            # ใส่ --seed 42 เปลี่ยนเมล็ดสุ่มของ panel_baseline ได้
```
**ทำไม:** proposal ให้เปรียบเทียบ 9 ชุดข้อมูล เพื่อดูว่าการกรองข้อความแบบต่าง ๆ ทำให้ความสัมพันธ์ชัดขึ้นไหม:

| กลุ่ม | ความหมาย |
|---|---|
| `panel_global` / `panel_Ticker` | ทุกข้อความ (รวมตลาด / แยกต่อ ticker) |
| `*_strong` | เฉพาะข้อความที่ \|คะแนน\| ≥ 0.05 |
| `*_quality` | เฉพาะข้อความที่ \|คะแนน\| ≥ 0.30 |
| `*_spike` | เฉพาะชั่วโมงที่ปริมาณพุ่ง (Z-score > 1.5) |
| `panel_baseline` | สุ่มทิศทาง (seed คงที่) ไว้เป็นตัวเทียบ "ถ้าเดาสุ่มจะได้เท่าไร" |

---

### ช่วง E — วิเคราะห์ทางสถิติ

> ทั้งหมดเขียนผลลง `analysis_results` และรูปลง `output/figures/` (ใส่ `--no-figures` ถ้าไม่ต้องการรูป)

#### ขั้น 16 · Correlation

```powershell
python steps/16_correlation.py
```
**ทำไม:** วัด Pearson และ Spearman ระหว่างความรู้สึกกับผลตอบแทน (ปัจจุบัน/อนาคต) ทุก panel × กลุ่มสินทรัพย์ × horizon พร้อม heatmap

#### ขั้น 17 · Historical Win Rate

```powershell
python steps/17_winrate.py
```
**ทำไม:** นับว่า "ความรู้สึกบวก → ราคาขึ้นจริง / ความรู้สึกลบ → ราคาลงจริง" กี่ % แล้วทดสอบด้วย Binomial Test เทียบ `panel_baseline` กลุ่มที่มีเหตุการณ์ < 30 รายการติดป้าย `insufficient_data`

#### ขั้น 18 · Logistic Regression

```powershell
python steps/18_logistic.py
```
**ทำไม:** ทดสอบว่าตัวแปร 6 กลุ่ม (Level, Direction, Vote, Volume, Lag, Momentum) ทายทิศทางผลตอบแทนอนาคตได้ดีกว่าเดาไหม วัดด้วย AUC-ROC
**กันการแอบดูอนาคต:** แบ่งข้อมูลด้วย `TimeSeriesSplit(n_splits=5, gap=12)` เท่านั้น (ห้าม shuffle / StratifiedKFold), fit `StandardScaler` เฉพาะชุดฝึก, ไม่ใช้ `future_return_*` / `score` / `upvote_ratio` / `num_comments` เป็นตัวแปรอิสระ

#### ขั้น 19 · สรุปผลสามวิธี → `evaluation_*` + รายงาน

```powershell
python steps/19_evaluate.py
```
**ทำไม:** เอาผลของขั้น 16–18 มาดูว่าชี้ไปทางเดียวกันไหม (convergence) เปรียบเทียบ 9 panel และ 3 กลุ่มสินทรัพย์ → สร้างรายงาน `output/reports/a5_evaluation.md`

---

### ช่วง F — โหลดตาราง Fact, ตรวจจับสัญญาณ, เปิดแดชบอร์ด

#### ขั้น 20 · `FactRedditVolume`

```powershell
python steps/20_load_fact_reddit_volume.py
```
**ทำไม:** ตารางข้อเท็จจริงฝั่ง Reddit ตามรูปที่ 2 ของ proposal (ต้องรันหลังขั้น 06) — คำนวณปริมาณรวมต่อชั่วโมงให้ด้วย (`reddit_volume_hourly`)
`reddit_volume` ในแต่ละแถว = ข้อความ **ทั้งหมด** ของชั่วโมง/แหล่งนั้น (ตัวหารของ Ticker Mention Rate) จึงมีค่าซ้ำกันทุก ticker ในชั่วโมงเดียวกัน → **ห้าม SUM ข้าม ticker**
สร้างใหม่ทุกครั้งที่รัน (ใช้เวลาไม่กี่นาที)

#### ขั้น 21 · `FactMarketSentiment`

```powershell
python steps/21_load_fact_market_sentiment.py
```
**ทำไม:** ตารางข้อเท็จจริงฝั่งความรู้สึก+ราคาตามรูปที่ 4 — **ต้องรันหลังขั้น 17** เพราะคัดลอกค่า win rate จาก `analysis_results` มาใส่ (1 แถวต่อ ชั่วโมง × ticker)

#### ขั้น 22 · ตรวจจับสัญญาณ → `signal_events`, `signal_summary`, `v_signal_list`

```powershell
python steps/22_detect_signals.py
```
**ทำไม:** ระบบ 7.6 ของ proposal — ชี้ชั่วโมงที่ปริมาณ/ความรู้สึกผิดปกติ (`volume_spike`, `positive_sentiment_spike`, `negative_sentiment_spike`, `combined_signal`) พร้อมระดับ low/medium/high และแนบ win rate/correlation ย้อนหลังของ ticker นั้น เกณฑ์ (Z-score 1.5/2.0/2.5 · Sentiment 0.05/0.30 · Horizon 1–12 ชม.) อยู่ใน `configs/detection.yaml`
`v_signal_list` = ตารางที่ 18 ของ proposal; ไม่มีการส่งแจ้งเตือนออกนอกระบบ

#### ขั้น 23 · เปิดแดชบอร์ด

```powershell
python steps/23_run_dashboard.py                      # หรือ: streamlit run dashboard/app.py
python steps/23_run_dashboard.py --server.port 8502   # เปลี่ยนพอร์ต
```
เปิดเบราว์เซอร์ที่ http://localhost:8501 — **อ่านฐานข้อมูลอย่างเดียว** ไม่ต้องรันขั้นก่อนหน้าใหม่

| หน้า | ตามหัวข้อ proposal | ดูอะไร |
|---|---|---|
| หน้าแรก | — | ภาพรวมตามตัวกรอง |
| 1 Reddit Volume | 7.1-1 | ปริมาณโพสต์+คอมเมนต์รวม และ Z-score |
| 2 Ticker Mentions | 7.1-1 (ต่อ) | สินทรัพย์ที่ถูกพูดถึง / อัตราการพูดถึง — proposal มีแดชบอร์ด 7.1 แค่ตัวเดียว โค้ดแยกเป็น 2 หน้า |
| 3 Price and Return | 7.2-1 | ราคา ปริมาณ ผลตอบแทนล่วงหน้า ความผันผวน |
| 4 Market and Sentiment | 7.5-1 | ราคาเทียบความรู้สึก สัดส่วน บวก/ลบ/กลาง |
| 5 Ranking and Signals | 7.5-2 | จัดอันดับด้วย Win Rate + ปรับเกณฑ์สัญญาณได้ทันที |

#### ขั้น 24 · ตรวจว่าครบตาม proposal

```powershell
python steps/24_check_proposal_coverage.py
```
**ทำไม:** เช็กอัตโนมัติว่า DB + แดชบอร์ดตอบตารางค่าวัด/KPI ของ proposal ครบหรือยัง → `output/reports/proposal_coverage.md` (อ่านอย่างเดียว)

---

## 5) สรุปลำดับรัน (ก๊อปไปใช้)

```powershell
# --- Windows: ครั้งแรก ติดตั้ง (ดู §3) ---
python -m venv .venv ; .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-analysis.txt   # + torch/transformers/nltk (ดู §3.3, ขั้น 08 ต้องรันบน Windows+GPU)
```

```bash
# --- macOS: ครั้งแรก ติดตั้ง (ดู §3) ---
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-analysis.txt nltk==3.10.3   # ไม่ต้องลง torch/transformers (ดู §3.3)
```

จากตรงนี้ คำสั่ง `python steps/...` เหมือนกันทุก OS (หลัง activate venv แล้ว `python` ชี้เข้า venv เสมอ) — **ยกเว้นขั้น 08 ที่รันได้บน Windows+GPU เท่านั้น**

```powershell
# --- ข้อมูลดิบ (ข้ามได้ถ้ามี reddit.sqlite3 อยู่แล้ว) ---
python steps/01_extract_reddit.py fetch 2024-10 --db output/reddit.sqlite3   # ทำซ้ำทีละเดือน
python steps/02_fetch_market.py oct24 aug26

# --- ประมวลผล ---
python steps/03_create_schema_and_dims.py
python steps/04_clean_text.py
python steps/05_quality_filter.py
python steps/06_extract_tickers.py
python steps/07_sentiment_vader.py
python steps/08_sentiment_finbert.py          # Windows + NVIDIA GPU เท่านั้น — Mac ข้ามบรรทัดนี้ (ดู §3.3)
python steps/09_resolve_sentiment.py
python steps/10_sentiment_qa.py
python steps/11_market_features.py
python steps/12_reddit_hourly.py
python steps/13_reddit_features.py
python steps/14_merge_panel.py
python steps/15_build_panels.py

# --- วิเคราะห์ ---
python steps/16_correlation.py
python steps/17_winrate.py
python steps/18_logistic.py
python steps/19_evaluate.py

# --- ตาราง Fact + สัญญาณ + แดชบอร์ด ---
python steps/20_load_fact_reddit_volume.py
python steps/21_load_fact_market_sentiment.py     # ต้องหลัง 17
python steps/22_detect_signals.py
python steps/24_check_proposal_coverage.py
python steps/23_run_dashboard.py
```

**ลำดับที่บังคับ:** 21 ต้องหลัง 17 · 20 ต้องหลัง 06 · 09 ต้องหลัง 07 และ 08 · 11 ทำคู่ขนานกับ 04–10 ได้ (ใช้แค่ราคา) แต่ 14 ต้องหลังทั้ง 11 และ 13

---

## 6) กติกาสำคัญที่ห้ามทำพลาด

**เรื่องเวลา (ทำไมต้องปัดเป็นต้นชั่วโมง)**
- เวลาทุกอย่างเป็น **UTC**
- ข้อความ Reddit ถูกใส่ในช่วง [H:00, H+1:00) ตาม `created_utc`
- แท่งราคาใช้เวลา **เริ่ม** แท่ง หุ้น `13:30` → ปัดเป็นชั่วโมง `13:00` แล้วค่อย join ผลตอบแทนอนาคตคำนวณจากราคาปิดของแท่งที่เริ่มหลังข้อความสุดท้ายเสมอ จึงไม่มี look-ahead

**เรื่องค่าตายตัวจาก proposal**

| ค่า | เท่าไร |
|---|---|
| Neutral band | ±0.05 |
| Strong / Quality | \|s\| ≥ 0.05 / ≥ 0.30 |
| Spike | Z-score > 1.5 |
| Horizon | 1 / 2 / 3 / 6 / 12 ชั่วโมง |
| Z-score | 24 ชั่วโมงก่อนหน้า ไม่รวมชั่วโมงปัจจุบัน |

**เรื่องข้อมูล**
- ห้าม DELETE/UPDATE/DROP/VACUUM ตาราง `reddit_content`, `market_bars`, `market_windows`, `market_gaps`; ตารางผลลัพธ์ใหม่เพิ่มได้ เปิดอ่านแบบ read-only: `sqlite3.connect('file:output/reddit.sqlite3?mode=ro', uri=True)`
- ขั้น 04–22 เขียนตารางใหม่ลงไฟล์เดียวกัน → ปิดโปรแกรมอื่นที่เปิด DB ค้างไว้ก่อน และเช็กดิสก์ว่าง
- **ทุกตัวเลข/ตาราง/กราฟที่จะลงเล่มต้องมาจากสคริปต์** ไม่ใช่ query ที่รันมือแล้วจำผล

---

## 7) ตารางที่ได้ในฐานข้อมูล

| กลุ่ม | ตาราง | มาจากขั้น |
|---|---|---|
| ดิบ (ห้ามแก้) | `reddit_content`, `market_bars`, `market_windows`, `market_gaps` | 01, 02 |
| ข้อความ | `processed_text`, `text_filter` (+ view `filtered_text`), `ticker_mentions`, `data_quality_audit` | 04–06 |
| ความรู้สึก | `sentiment_vader`, `sentiment_finbert`, `sentiment_item`, `sentiment_qa` | 07–10 |
| ฟีเจอร์รายชั่วโมง | `market_hourly_features`, `reddit_hourly`, `reddit_hourly_features`, `merged_hourly_panel`, `panels` | 11–15 |
| ผลวิเคราะห์ | `analysis_results`, `evaluation_*` (5 ตาราง) | 16–19 |
| Star schema | `DimTime`, `DimTicker`, `DimSource`, `DimSentimentSource`, `DimDetectionConfig`, `DimMajoritySentiment`, `FactRedditVolume`, `FactMarketPrice`, `FactMarketSentiment` | 03, 11, 20, 21 |
| สัญญาณ | `signal_events`, `signal_summary`, view `v_signal_list` | 22 |

ไฟล์ผลลัพธ์นอกฐานข้อมูล: `output/figures/*.png` (กราฟ A1–A3), `output/reports/a5_evaluation.md`, `output/reports/proposal_coverage.md`, `output/logs/` (log การรัน)

---

## 8) โครงโฟลเดอร์

```
reddit_extract.py   market_fetch.py   pipeline_status.py   pipeline_logs.py   # ขั้นต้นน้ำ + ดูสถานะ + log (อยู่ที่ root)
configs/    ค่าตั้งทั้งหมด (ชุมชน, ticker, sentiment, detection)
db/         schema.sql (star schema)
etl/        ขั้น 03–15, 20, 21 (ล้างข้อความ → sentiment → รายชั่วโมง → fact)
analysis/   ขั้น 16–19, 22 (correlation, win rate, logistic, evaluate, signals)
dashboard/  Streamlit 5 หน้า (data.py = ชั้น query อ่านอย่างเดียว)
steps/      ตัวเรียกมีเลขลำดับ 00–24 (+ steps/README.md)
scripts/    benchmark FinBERT, ตรวจ proposal coverage, สคริปต์ซ่อม/ตรวจ
tests/      unittest
docs/       METHOD_DECISIONS_NOT_IN_PROPOSAL.md, benchmark_finbert.md
data/ output/ old_code/    ข้อมูล/ผลลัพธ์/โค้ดเก่า — อยู่ใน .gitignore ห้าม commit
```

## 9) ทดสอบ

```powershell
python -m unittest discover -s tests -v
```
- ห้ามใส่ `-t .` (เกิด ImportError)
- บน Windows จะมีเทสต์ **error 9 จาก 18 ตัว** ในชุดเดิม เป็น `PermissionError [WinError 32]` ตอนลบโฟลเดอร์ชั่วคราว (ไฟล์ SQLite ในเทสต์ยังไม่ปิด) — เป็นปัญหาของตัวเทสต์บน Windows ไม่ใช่ตรรกะของระบบ; บน macOS ไม่มีปัญหาล็อกไฟล์แบบนี้ เทสต์ชุดเดียวกันน่าจะผ่านครบ (ยังไม่ได้วัดจริงบนเครื่อง Mac)

## 10) แก้ปัญหาที่เจอบ่อย

**Windows**

| อาการ | สาเหตุ / ทางแก้ |
|---|---|
| `source : The term 'source' is not recognized` | ใช้คำสั่ง macOS/Linux ใน PowerShell → ใช้ `.\.venv\Scripts\Activate.ps1` |
| `running scripts is disabled on this system` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `aria2c` not found | ติดตั้ง aria2 และให้อยู่ใน PATH (หรือคัดลอก `aria2c.exe` ไว้ใน `.venv\Scripts`) |
| `pip install torch` ล้มด้วย `WinError 32` | Defender ล็อกไฟล์ → `pip download` ก่อนแล้ว `pip install <ไฟล์.whl>` (§3.3) |
| `import torch` ขึ้น `WinError 4551` | Windows บล็อก DLL → แจ้ง/ตัดสินใจเรื่องนโยบายความปลอดภัยเอง อย่าหลบเอง |
| `torch.cuda.is_available()` เป็น `False` | ติดตั้ง torch รุ่น CPU มา → ลงรุ่น `cu128` ใหม่ |

**macOS**

| อาการ | สาเหตุ / ทางแก้ |
|---|---|
| `zsh: command not found: ..venvScriptsActivate.ps1` (หรือคล้ายกัน) | ก๊อปคำสั่ง PowerShell มารันใน zsh → zsh ตัด `\` ทิ้งจน path เพี้ยน ใช้ `source .venv/bin/activate` แทน (§3.1) |
| `aria2c` not found | `brew install aria2` |
| `SystemExit: CUDA GPU not available; FinBERT on 22 M texts needs the GPU` (ขั้น 08) | ตั้งใจล็อกไว้ ไม่ใช่บั๊ก — Mac ไม่มี NVIDIA GPU รันขั้นนี้ไม่ได้ ดูวิธีทำงานข้าม OS ที่ §3.3 |
| `python: command not found` (ก่อน activate venv) | Mac บางเครื่องมีแค่ `python3` ก่อน activate ให้ใช้ `python3 -m venv .venv` แล้ว activate — หลัง activate แล้ว `python` จะใช้ได้ปกติ |

**ทุก OS**

| อาการ | สาเหตุ / ทางแก้ |
|---|---|
| `No .torrent for 2025-xx under data` | ไม่มีไฟล์ torrent ของเดือนนั้นใน `data/` → วางไฟล์ `.torrent` แล้วรันใหม่ หรือใช้ `import` กับไฟล์ที่มีอยู่ |
| Yahoo ขึ้น `last 730 days` | ข้อมูลรายชั่วโมงย้อนได้ไม่เกิน ~730 วัน เป็นข้อจำกัดต้นทาง ไม่ใช่บั๊ก |
| ดิสก์เต็มระหว่างรัน | ฐานข้อมูลโตขึ้นมากหลังขั้น 07–09 → เคลียร์พื้นที่ แล้วรันขั้นเดิมซ้ำ (ต่อจากที่ค้าง) |
| รันขั้นยาวค้างกลางทาง | รันคำสั่งเดิมซ้ำได้ ไม่ต้อง `--rebuild` ยกเว้นต้องการทำใหม่ทั้งหมด |

---

## 11) เอกสารอื่นในโปรเจกต์ (เรียงตามอำนาจ)

1. `data/Wait_for_approve_Proposal_…_rev1.pdf` — **source of truth** ของ requirement ถ้าขัดกับไฟล์อื่นให้ยึด proposal
2. `docs/METHOD_DECISIONS_NOT_IN_PROPOSAL.md` — วิธีที่เลือกเองในจุดที่ proposal ไม่ได้ระบุ (7 ข้อ) พร้อมข้อความพร้อมวางในรายงาน — ส่วนที่ทำเกิน proposal ติดป้าย "ส่วนขยาย"
3. `TASKS.md` — รายการงานละเอียด สถานะข้อมูลจริง และกับดัก
4. `SYSTEM_BLUEPRINT_TH.md` — สถาปัตยกรรม, time alignment, leakage policy
5. `CODE_STRUCTURE.md` — แผนที่ proposal → สคริปต์ → ตารางผลลัพธ์ + เช็กลิสต์ก่อนปิดเล่ม
6. `steps/README.md` — ตารางลำดับรัน 00–24
7. `CLAUDE.md` — กติกาสำหรับผู้ช่วย AI ที่ช่วยเขียนโค้ดในโปรเจกต์นี้

## 12) เผยแพร่ขึ้น GitHub

ก่อน push ตรวจ `git status` และ `git ls-files` ว่าไม่มี `data/`, `output/`, `old_code/` (โน้ตบุ๊กเก่ามีข้อความ Reddit จริงฝังอยู่), ไฟล์ `.torrent`, `.zst`, `.sqlite3` หลุดเข้ามา — ทั้งหมดอยู่ใน `.gitignore` แล้ว
