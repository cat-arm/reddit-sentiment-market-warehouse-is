# Rule validation (proposal 7.3 step 5)

> ไฟล์นี้คืออะไร: ความแม่นของ VADER เดี่ยว, FinBERT เดี่ยว, วิธีรวมผล และรูปแบบข้อความ 3 แบบ เมื่อเทียบกับป้ายที่ผู้พัฒนาติดเอง (450 คอมเมนต์ที่ใช้ได้, ยังไม่มีป้าย 0, ติด unclear 0)  
> สร้างเมื่อ: 2026-11-16 00:56 (เวลาเครื่อง) โดยสคริปต์ scripts/rule_validation.py evaluate  
> ข้อมูลที่ใช้: labeling_sheet.csv (ป้าย) + sample_key.csv + variant_scores.csv ในโฟลเดอร์เดียวกัน  
> สร้างใหม่ด้วยคำสั่ง: python steps/26_rule_validation.py evaluate --cap-per-split 25 --cap-seed 20261104  

ความแม่น = สัดส่วนที่ประเภทความรู้สึก (positive/negative/neutral) ตรงกับป้ายที่ผู้พัฒนาติดเอง; ชุด tune ใช้ปรับกฎ, ชุด test ใช้ยืนยัน/รายงานผล

**เกณฑ์ตัดสินที่ตั้งไว้ก่อนดูผล:** จะเปลี่ยนกฎ (หรือรูปแบบข้อความ) ก็ต่อเมื่อทางเลือกชนะ final อย่างน้อย 5 จุดในชุด tune **และ** ชุด test ให้ทิศทางเดียวกันด้วย sign test p < 0.05 (แบบดิบ) — ถ้าไม่ถึง ถือว่า "แยกไม่ออก" และคงกฎเดิม. ตารางเทียบกฎมี 21 การทดสอบ จึงแสดง p ที่ปรับด้วย Holm ควบคู่ด้วย

## ชุด tune

| กลุ่ม | n | VADER | FinBERT | รวมผล (final) |
|---|---|---|---|---|
| same_direction | 25 | 48.0% | 48.0% | 48.0% |
| same_direction_far | 25 | 36.0% | 36.0% | 36.0% |
| both_neutral | 25 | 68.0% | 68.0% | 68.0% |
| small_conflict_keyword | 50 | 32.0% | 34.0% | 48.0% |
| small_conflict_no_keyword | 25 | 44.0% | 48.0% | 40.0% |
| hard_conflict_keyword | 25 | 40.0% | 44.0% | 64.0% |
| hard_conflict_no_keyword | 25 | 16.0% | 36.0% | 48.0% |
| hard_conflict_mixed_zero | 25 | 24.0% | 36.0% | 40.0% |
| **ถ่วงน้ำหนักตามจำนวนข้อความของกลุ่ม** | | 45.8% | 49.7% | 48.3% |

## ชุด test

| กลุ่ม | n | VADER | FinBERT | รวมผล (final) |
|---|---|---|---|---|
| same_direction | 25 | 48.0% | 48.0% | 48.0% |
| same_direction_far | 25 | 36.0% | 36.0% | 36.0% |
| both_neutral | 25 | 64.0% | 64.0% | 64.0% |
| small_conflict_keyword | 50 | 30.0% | 30.0% | 42.0% |
| small_conflict_no_keyword | 25 | 40.0% | 40.0% | 32.0% |
| hard_conflict_keyword | 25 | 52.0% | 40.0% | 72.0% |
| hard_conflict_no_keyword | 25 | 20.0% | 32.0% | 48.0% |
| hard_conflict_mixed_zero | 25 | 24.0% | 32.0% | 44.0% |
| **ถ่วงน้ำหนักตามจำนวนข้อความของกลุ่ม** | | 43.9% | 45.4% | 44.4% |

## ความแม่นรายกรณีของกฎรวมผล (final_method, แยกกรณีเล็กที่ถูกรวมในตารางกลุ่ม)

n น้อยมากในกรณี small_conflict_rule_agrees / small_conflict_rule_clash อ่านด้วยความระวัง; hard_conflict_mixed_zero ไม่ถูกสุ่ม

| กรณี | ชุด | n | VADER | FinBERT | รวมผล (final) |
|---|---|---|---|---|---|
| both_neutral | test | 25 | 64.0% | 64.0% | 64.0% |
| both_neutral | tune | 25 | 68.0% | 68.0% | 68.0% |
| hard_conflict_mixed_zero | test | 25 | 24.0% | 32.0% | 44.0% |
| hard_conflict_mixed_zero | tune | 25 | 24.0% | 36.0% | 40.0% |
| hard_conflict_no_rule | test | 25 | 20.0% | 32.0% | 48.0% |
| hard_conflict_no_rule | tune | 25 | 16.0% | 36.0% | 48.0% |
| hard_conflict_rule | test | 25 | 52.0% | 40.0% | 72.0% |
| hard_conflict_rule | tune | 25 | 40.0% | 44.0% | 64.0% |
| same_direction | test | 25 | 48.0% | 48.0% | 48.0% |
| same_direction | tune | 25 | 48.0% | 48.0% | 48.0% |
| same_direction_far | test | 25 | 36.0% | 36.0% | 36.0% |
| same_direction_far | tune | 25 | 36.0% | 36.0% | 36.0% |
| small_conflict_no_rule | test | 25 | 40.0% | 40.0% | 32.0% |
| small_conflict_no_rule | tune | 25 | 44.0% | 48.0% | 40.0% |
| small_conflict_rule_agrees | test | 25 | 48.0% | 28.0% | 60.0% |
| small_conflict_rule_agrees | tune | 25 | 40.0% | 44.0% | 64.0% |
| small_conflict_rule_clash | test | 25 | 12.0% | 32.0% | 24.0% |
| small_conflict_rule_clash | tune | 25 | 24.0% | 24.0% | 32.0% |

## ผลตามเกณฑ์ตัดสินที่ตั้งไว้ รายกรณี (9 กรณี)

ส่วนต่าง = ความแม่นของวิธีเทียบ − ความแม่นของกฎรวมผล (จุดร้อยละ; บวก = วิธีเทียบดีกว่า) · p = sign test แบบ exact ของชุด test · เปลี่ยนกฎก็ต่อเมื่อส่วนต่างชุด tune ≥ +5 และชุด test เป็นบวกด้วย และ p < 0.05; ไม่ถึง = คงกฎรวมผล

| กรณี | เทียบกับ | ส่วนต่าง tune | ส่วนต่าง test | p (test) | ผล |
|---|---|---|---|---|---|
| same_direction | VADER | +0 | +0 | 1.000 | คงกฎ |
| same_direction | FinBERT | +0 | +0 | 1.000 | คงกฎ |
| same_direction | เป็นกลางทุกข้อ | -8 | -12 | 0.664 | คงกฎ |
| same_direction_far | VADER | +0 | +0 | 1.000 | คงกฎ |
| same_direction_far | FinBERT | +0 | +0 | 1.000 | คงกฎ |
| same_direction_far | เป็นกลางทุกข้อ | +28 | +4 | 1.000 | คงกฎ |
| both_neutral | VADER | +0 | +0 | 1.000 | คงกฎ |
| both_neutral | FinBERT | +0 | +0 | 1.000 | คงกฎ |
| both_neutral | เป็นกลางทุกข้อ | +0 | +0 | 1.000 | คงกฎ |
| small_conflict_rule_agrees | VADER | -24 | -12 | 0.375 | คงกฎ |
| small_conflict_rule_agrees | FinBERT | -20 | -32 | 0.057 | คงกฎ |
| small_conflict_rule_agrees | เป็นกลางทุกข้อ | -44 | -44 | 0.019 | คงกฎ |
| small_conflict_rule_clash | VADER | -8 | -12 | 0.508 | คงกฎ |
| small_conflict_rule_clash | FinBERT | -8 | +8 | 0.500 | คงกฎ |
| small_conflict_rule_clash | เป็นกลางทุกข้อ | +0 | +0 | 1.000 | คงกฎ |
| small_conflict_no_rule | VADER | +4 | +8 | 0.625 | คงกฎ |
| small_conflict_no_rule | FinBERT | +8 | +8 | 0.804 | คงกฎ |
| small_conflict_no_rule | เป็นกลางทุกข้อ | +12 | +16 | 0.503 | คงกฎ |
| hard_conflict_rule | VADER | -24 | -20 | 0.125 | คงกฎ |
| hard_conflict_rule | FinBERT | -20 | -32 | 0.077 | คงกฎ |
| hard_conflict_rule | เป็นกลางทุกข้อ | -48 | -64 | 0.000 | คงกฎ |
| hard_conflict_no_rule | VADER | -32 | -28 | 0.143 | คงกฎ |
| hard_conflict_no_rule | FinBERT | -12 | -16 | 0.503 | คงกฎ |
| hard_conflict_no_rule | เป็นกลางทุกข้อ | +0 | +0 | 1.000 | คงกฎ |
| hard_conflict_mixed_zero | VADER | -16 | -20 | 0.332 | คงกฎ |
| hard_conflict_mixed_zero | FinBERT | -4 | -12 | 0.648 | คงกฎ |
| hard_conflict_mixed_zero | เป็นกลางทุกข้อ | +0 | +0 | 1.000 | คงกฎ |

รวม: เปลี่ยนกฎ 0 จาก 27 การเปรียบเทียบ

## รวมทุกกรณี (เพิ่มเติม — ไม่ได้ตั้งเกณฑ์ไว้ก่อนดูผล)

รวมชุด tune + test (ไม่ได้ปรับกฎด้วยชุด tune จึงรวมได้) ทุกกรณีน้ำหนักเท่ากันเพราะสุ่มจำนวนเท่ากัน ต่างจากตารางถ่วงน้ำหนักตามจำนวนข้อความจริงที่กรณีใหญ่สุด (small_conflict_no_rule 37% ของข้อความ) FinBERT สูงกว่า — ต้องอ่านคู่กัน · p = sign test แบบ exact

| ขอบเขต | n | VADER | FinBERT | กฎรวมผล | p เทียบ VADER | p เทียบ FinBERT |
|---|---|---|---|---|---|---|
| ทั้ง 9 กรณี | 450 | 38.0% | 40.9% | 48.2% | 0.0001 (88 : 42) | 0.0125 (99 : 66) |
| 6 กรณีที่โมเดลขัดกัน | 300 | 32.0% | 36.3% | 47.3% | 0.0001 (88 : 42) | 0.0125 (99 : 66) |

(ในวงเล็บ = ข้อที่ถูกเฉพาะกฎรวมผล : ข้อที่ถูกเฉพาะวิธีเทียบ)

## ป้ายของคนในแต่ละกลุ่มกฎ (ตอบ "ข้อความกลุ่มนี้เป็นบวก/ลบ/กลางจริงกี่ข้อความ")

| กลุ่ม | n | positive | negative | neutral |
|---|---|---|---|---|
| same_direction | 50 | 14 (28%) | 17 (34%) | 19 (38%) |
| same_direction_far | 50 | 8 (16%) | 16 (32%) | 26 (52%) |
| both_neutral | 50 | 9 (18%) | 8 (16%) | 33 (66%) |
| small_conflict_keyword | 100 | 32 (32%) | 45 (45%) | 23 (23%) |
| small_conflict_no_keyword | 50 | 10 (20%) | 15 (30%) | 25 (50%) |
| hard_conflict_keyword | 50 | 25 (50%) | 19 (38%) | 6 (12%) |
| hard_conflict_no_keyword | 50 | 8 (16%) | 18 (36%) | 24 (48%) |
| hard_conflict_mixed_zero | 50 | 11 (22%) | 18 (36%) | 21 (42%) |
| (เฉพาะแถวที่ระบบตั้งสถานะกำกวม is_ambiguous=1) | 150 | 36 (24%) | 55 (37%) | 59 (39%) |

## เทียบกฎรวมผล (final) กับทางเลือกง่าย ๆ ทีละกลุ่ม

ทางเลือก: ใช้ VADER เดี่ยว, FinBERT เดี่ยว, หรือตอบ neutral ทุกข้อ (= "คง neutral" ตามข้อสังเกตของอาจารย์). p = exact binomial สองทางของสองคอลัมน์ "ถูกเฉพาะ" (p สูง = แยกไม่ออกว่าวิธีไหนดีกว่า)

### ชุด test (ใช้ยืนยัน)

| กลุ่ม | เทียบกับ | n | final (ช่วงเชื่อมั่น 95%) | วิธีเทียบ | ถูกเฉพาะ final | ถูกเฉพาะวิธีเทียบ | p | p (Holm) |
|---|---|---|---|---|---|---|---|---|
| same_direction | VADER | 25 | 48.0% (30–67) | 48.0% | 0 | 0 | 1.000 | 1.000 |
| same_direction | FinBERT | 25 | 48.0% (30–67) | 48.0% | 0 | 0 | 1.000 | 1.000 |
| same_direction | เป็นกลางทุกข้อ | 25 | 48.0% (30–67) | 36.0% | 12 | 9 | 0.664 | 1.000 |
| same_direction_far | VADER | 25 | 36.0% (20–55) | 36.0% | 0 | 0 | 1.000 | 1.000 |
| same_direction_far | FinBERT | 25 | 36.0% (20–55) | 36.0% | 0 | 0 | 1.000 | 1.000 |
| same_direction_far | เป็นกลางทุกข้อ | 25 | 36.0% (20–55) | 40.0% | 9 | 10 | 1.000 | 1.000 |
| both_neutral | VADER | 25 | 64.0% (45–80) | 64.0% | 0 | 0 | 1.000 | 1.000 |
| both_neutral | FinBERT | 25 | 64.0% (45–80) | 64.0% | 0 | 0 | 1.000 | 1.000 |
| both_neutral | เป็นกลางทุกข้อ | 25 | 64.0% (45–80) | 64.0% | 0 | 0 | 1.000 | 1.000 |
| small_conflict_keyword | VADER | 50 | 42.0% (29–56) | 30.0% | 10 | 4 | 0.180 | 1.000 |
| small_conflict_keyword | FinBERT | 50 | 42.0% (29–56) | 30.0% | 11 | 5 | 0.210 | 1.000 |
| small_conflict_keyword | เป็นกลางทุกข้อ | 50 | 42.0% (29–56) | 20.0% | 15 | 4 | 0.019 | 0.442 |
| small_conflict_no_keyword | VADER | 25 | 32.0% (17–52) | 40.0% | 1 | 3 | 0.625 | 1.000 |
| small_conflict_no_keyword | FinBERT | 25 | 32.0% (17–52) | 40.0% | 7 | 9 | 0.804 | 1.000 |
| small_conflict_no_keyword | เป็นกลางทุกข้อ | 25 | 32.0% (17–52) | 48.0% | 8 | 12 | 0.503 | 1.000 |
| hard_conflict_keyword | VADER | 25 | 72.0% (52–86) | 52.0% | 6 | 1 | 0.125 | 1.000 |
| hard_conflict_keyword | FinBERT | 25 | 72.0% (52–86) | 40.0% | 12 | 4 | 0.077 | 1.000 |
| hard_conflict_keyword | เป็นกลางทุกข้อ | 25 | 72.0% (52–86) | 8.0% | 18 | 2 | 0.000 | 0.010 |
| hard_conflict_no_keyword | VADER | 25 | 48.0% (30–67) | 20.0% | 12 | 5 | 0.143 | 1.000 |
| hard_conflict_no_keyword | FinBERT | 25 | 48.0% (30–67) | 32.0% | 12 | 8 | 0.503 | 1.000 |
| hard_conflict_no_keyword | เป็นกลางทุกข้อ | 25 | 48.0% (30–67) | 48.0% | 0 | 0 | 1.000 | 1.000 |
| hard_conflict_mixed_zero | VADER | 25 | 44.0% (27–63) | 24.0% | 11 | 6 | 0.332 | 1.000 |
| hard_conflict_mixed_zero | FinBERT | 25 | 44.0% (27–63) | 32.0% | 11 | 8 | 0.648 | 1.000 |
| hard_conflict_mixed_zero | เป็นกลางทุกข้อ | 25 | 44.0% (27–63) | 44.0% | 0 | 0 | 1.000 | 1.000 |

### ชุด tune (ใช้ปรับ)

| กลุ่ม | เทียบกับ | n | final (ช่วงเชื่อมั่น 95%) | วิธีเทียบ | ถูกเฉพาะ final | ถูกเฉพาะวิธีเทียบ | p | p (Holm) |
|---|---|---|---|---|---|---|---|---|
| same_direction | VADER | 25 | 48.0% (30–67) | 48.0% | 0 | 0 | 1.000 | – |
| same_direction | FinBERT | 25 | 48.0% (30–67) | 48.0% | 0 | 0 | 1.000 | – |
| same_direction | เป็นกลางทุกข้อ | 25 | 48.0% (30–67) | 40.0% | 12 | 10 | 0.832 | – |
| same_direction_far | VADER | 25 | 36.0% (20–55) | 36.0% | 0 | 0 | 1.000 | – |
| same_direction_far | FinBERT | 25 | 36.0% (20–55) | 36.0% | 0 | 0 | 1.000 | – |
| same_direction_far | เป็นกลางทุกข้อ | 25 | 36.0% (20–55) | 64.0% | 9 | 16 | 0.230 | – |
| both_neutral | VADER | 25 | 68.0% (48–83) | 68.0% | 0 | 0 | 1.000 | – |
| both_neutral | FinBERT | 25 | 68.0% (48–83) | 68.0% | 0 | 0 | 1.000 | – |
| both_neutral | เป็นกลางทุกข้อ | 25 | 68.0% (48–83) | 68.0% | 0 | 0 | 1.000 | – |
| small_conflict_keyword | VADER | 50 | 48.0% (35–61) | 32.0% | 15 | 7 | 0.134 | – |
| small_conflict_keyword | FinBERT | 50 | 48.0% (35–61) | 34.0% | 9 | 2 | 0.065 | – |
| small_conflict_keyword | เป็นกลางทุกข้อ | 50 | 48.0% (35–61) | 26.0% | 16 | 5 | 0.027 | – |
| small_conflict_no_keyword | VADER | 25 | 40.0% (23–59) | 44.0% | 4 | 5 | 1.000 | – |
| small_conflict_no_keyword | FinBERT | 25 | 40.0% (23–59) | 48.0% | 6 | 8 | 0.791 | – |
| small_conflict_no_keyword | เป็นกลางทุกข้อ | 25 | 40.0% (23–59) | 52.0% | 10 | 13 | 0.678 | – |
| hard_conflict_keyword | VADER | 25 | 64.0% (45–80) | 40.0% | 7 | 1 | 0.070 | – |
| hard_conflict_keyword | FinBERT | 25 | 64.0% (45–80) | 44.0% | 9 | 4 | 0.267 | – |
| hard_conflict_keyword | เป็นกลางทุกข้อ | 25 | 64.0% (45–80) | 16.0% | 16 | 4 | 0.012 | – |
| hard_conflict_no_keyword | VADER | 25 | 48.0% (30–67) | 16.0% | 12 | 4 | 0.077 | – |
| hard_conflict_no_keyword | FinBERT | 25 | 48.0% (30–67) | 36.0% | 12 | 9 | 0.664 | – |
| hard_conflict_no_keyword | เป็นกลางทุกข้อ | 25 | 48.0% (30–67) | 48.0% | 0 | 0 | 1.000 | – |
| hard_conflict_mixed_zero | VADER | 25 | 40.0% (23–59) | 24.0% | 10 | 6 | 0.454 | – |
| hard_conflict_mixed_zero | FinBERT | 25 | 40.0% (23–59) | 36.0% | 10 | 9 | 1.000 | – |
| hard_conflict_mixed_zero | เป็นกลางทุกข้อ | 25 | 40.0% (23–59) | 40.0% | 0 | 0 | 1.000 | – |

### รวมทั้งหมด (เพิ่มกำลังทดสอบ)

| กลุ่ม | เทียบกับ | n | final (ช่วงเชื่อมั่น 95%) | วิธีเทียบ | ถูกเฉพาะ final | ถูกเฉพาะวิธีเทียบ | p | p (Holm) |
|---|---|---|---|---|---|---|---|---|
| same_direction | VADER | 50 | 48.0% (35–61) | 48.0% | 0 | 0 | 1.000 | – |
| same_direction | FinBERT | 50 | 48.0% (35–61) | 48.0% | 0 | 0 | 1.000 | – |
| same_direction | เป็นกลางทุกข้อ | 50 | 48.0% (35–61) | 38.0% | 24 | 19 | 0.542 | – |
| same_direction_far | VADER | 50 | 36.0% (24–50) | 36.0% | 0 | 0 | 1.000 | – |
| same_direction_far | FinBERT | 50 | 36.0% (24–50) | 36.0% | 0 | 0 | 1.000 | – |
| same_direction_far | เป็นกลางทุกข้อ | 50 | 36.0% (24–50) | 52.0% | 18 | 26 | 0.291 | – |
| both_neutral | VADER | 50 | 66.0% (52–78) | 66.0% | 0 | 0 | 1.000 | – |
| both_neutral | FinBERT | 50 | 66.0% (52–78) | 66.0% | 0 | 0 | 1.000 | – |
| both_neutral | เป็นกลางทุกข้อ | 50 | 66.0% (52–78) | 66.0% | 0 | 0 | 1.000 | – |
| small_conflict_keyword | VADER | 100 | 45.0% (36–55) | 31.0% | 25 | 11 | 0.029 | – |
| small_conflict_keyword | FinBERT | 100 | 45.0% (36–55) | 32.0% | 20 | 7 | 0.019 | – |
| small_conflict_keyword | เป็นกลางทุกข้อ | 100 | 45.0% (36–55) | 23.0% | 31 | 9 | 0.001 | – |
| small_conflict_no_keyword | VADER | 50 | 36.0% (24–50) | 42.0% | 5 | 8 | 0.581 | – |
| small_conflict_no_keyword | FinBERT | 50 | 36.0% (24–50) | 44.0% | 13 | 17 | 0.585 | – |
| small_conflict_no_keyword | เป็นกลางทุกข้อ | 50 | 36.0% (24–50) | 50.0% | 18 | 25 | 0.360 | – |
| hard_conflict_keyword | VADER | 50 | 68.0% (54–79) | 46.0% | 13 | 2 | 0.007 | – |
| hard_conflict_keyword | FinBERT | 50 | 68.0% (54–79) | 42.0% | 21 | 8 | 0.024 | – |
| hard_conflict_keyword | เป็นกลางทุกข้อ | 50 | 68.0% (54–79) | 12.0% | 34 | 6 | 0.000 | – |
| hard_conflict_no_keyword | VADER | 50 | 48.0% (35–61) | 18.0% | 24 | 9 | 0.014 | – |
| hard_conflict_no_keyword | FinBERT | 50 | 48.0% (35–61) | 34.0% | 24 | 17 | 0.349 | – |
| hard_conflict_no_keyword | เป็นกลางทุกข้อ | 50 | 48.0% (35–61) | 48.0% | 0 | 0 | 1.000 | – |
| hard_conflict_mixed_zero | VADER | 50 | 42.0% (29–56) | 24.0% | 21 | 12 | 0.163 | – |
| hard_conflict_mixed_zero | FinBERT | 50 | 42.0% (29–56) | 34.0% | 21 | 17 | 0.627 | – |
| hard_conflict_mixed_zero | เป็นกลางทุกข้อ | 50 | 42.0% (29–56) | 42.0% | 0 | 0 | 1.000 | – |

## รูปแบบข้อความ: A คอมเมนต์อย่างเดียว / B หัวข้อโพสต์+คอมเมนต์ / C หัวข้อ+เนื้อโพสต์+คอมเมนต์ / cascade

cascade = ใช้ A; ถ้าได้ neutral ใช้ B; ถ้ายัง neutral ใช้ C. ป้ายคนเป็นท่าทีของผู้เขียนคอมเมนต์ที่อ่านพร้อมบริบทโพสต์ จึงไม่เอนเอียงไปทางรูปแบบใดรูปแบบหนึ่ง. ความแม่นถ่วงน้ำหนักตามจำนวนข้อความของแต่ละกลุ่ม (กลุ่มถูกกำหนดจากกฎของ B)

| รูปแบบ | ชุด | n | VADER | FinBERT | final |
|---|---|---|---|---|---|
| A | tune | 225 | 49.3% | 41.7% | 46.8% |
| A | test | 225 | 42.7% | 50.1% | 40.3% |
| A | รวม | 450 | 46.0% | 45.9% | 43.6% |
| B | tune | 225 | 45.8% | 49.7% | 48.3% |
| B | test | 225 | 43.9% | 45.4% | 44.4% |
| B | รวม | 450 | 44.9% | 47.5% | 46.3% |
| C | tune | 225 | 35.1% | 39.8% | 37.2% |
| C | test | 225 | 30.7% | 43.3% | 35.5% |
| C | รวม | 450 | 32.9% | 41.5% | 36.4% |
| cascade | tune | 225 | – | – | 38.3% |
| cascade | test | 225 | – | – | 32.0% |
| cascade | รวม | 450 | – | – | 35.1% |

### เทียบเป็นคู่กับ B (final ของแต่ละรูปแบบ)

ถูกเฉพาะรูปแบบนั้น = รูปแบบนั้นถูกแต่ B ผิด. C เทียบเฉพาะคอมเมนต์ที่โพสต์มีเนื้อหา (ที่เหลือ C = B); A เทียบเฉพาะคอมเมนต์ที่รู้หัวข้อโพสต์ (ที่เหลือ A = B)

| รูปแบบ | ชุด | n | ถูกเฉพาะรูปแบบนั้น | ถูกเฉพาะ B | p |
|---|---|---|---|---|---|
| A | tune | 224 | 16 | 19 | 0.736 |
| A | test | 224 | 15 | 18 | 0.728 |
| A | รวม | 448 | 31 | 37 | 0.545 |
| C | tune | 198 | 20 | 33 | 0.098 |
| C | test | 199 | 16 | 31 | 0.040 |
| C | รวม | 397 | 36 | 64 | 0.007 |
| cascade | tune | 225 | 18 | 29 | 0.144 |
| cascade | test | 225 | 19 | 27 | 0.302 |
| cascade | รวม | 450 | 37 | 56 | 0.061 |

