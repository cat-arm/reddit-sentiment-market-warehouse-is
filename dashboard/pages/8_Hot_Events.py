"""Dashboard 7  Detected Signal List (proposal 7.6, table 18): only the signal events, as the proposal says: timestamp, Ticker, Big_Group, the measures, signal_type, signal_level, and the
historical statistics looked up from the system 7.4.

The system 7.6 only CATCHES: it lays every asset x hour in the chosen range on the table and lists the ones that pass the Z-score and
Sentiment thresholds of the sidebar (the same two thresholds as pages 4, 5 and 6; 0 = no threshold).  The statistics beside each signal are NOT
computed here: they are looked up from the system 7.4 (step 3 of 7.6), the very numbers of the Statistical Analysis page with the same filters.
Z-score AND Sentiment Score = all texts of the market in that hour (proposal tables 3 and 18, panel_global); the asset only adds its price and its Ticker Mention Rate.  A look
at history, NOT a trading signal: win rates near 50% are what a random direction gives (see output/reports/final/2_tests_and_hypotheses.md).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard import common, data  # noqa: E402
from dashboard.common import GROUP_LABELS, q  # noqa: E402

SPIKE_Z = 1.5                                  # proposal: a volume spike is a Reddit Volume Z-score above 1.5 (the sidebar counts the texts instead)

HORIZONS = ("1h", "2h", "3h", "6h", "12h")
MIN_N = 1                                   # no minimum n: a rate needs one signal; a symbol marks n < 30 (WARN_N)
WARN_N = 30
TARGETS = [("log_return", "Current Return"), *[("future_return_" + h, h) for h in HORIZONS]]
NAMES = {"log_return": "ราคาชั่วโมงเดียวกัน (Current Return %)", **{"future_return_" + h: "ราคาหลัง %s ชั่วโมง (%%)" % h[:-1] for h in HORIZONS}}
CARDS = ["จำนวนสัญญาณ (ชั่วโมง × สินทรัพย์)", "จำนวนสินทรัพย์ที่เกิดสัญญาณ", "จำนวนชั่วโมงที่ต่างกัน"]

common.setup("รายการสัญญาณ (Hot Events)", "🔥")
_, start, end, _ = common.sidebar(multi=True, sentiment=True, detection="overview", majority=True)   # the same filters as the Statistical Analysis page
tickers = common.selected_tickers()
communities = common.selected_communities()
statuses = common.selected_statuses()
content_types = common.selected_content_types()
model = common.selected_model()
st.caption("**หมายเหตุ:** ไม่มีเกณฑ์จำนวนตัวอย่างขั้นต่ำ ทุกค่าที่คำนวณได้จะแสดง (สหสัมพันธ์ต้องมีอย่างน้อย 3 ชั่วโมงจึงมีค่าทางคณิตศาสตร์) ค่าที่ n น้อยกว่า 30 ติดเครื่องหมาย ⚠ แปลว่าไม่น่าเชื่อถือ ให้ดู n และ ★ (p ปรับ BH) ประกอบเสมอ")
if not tickers or not communities or not statuses or not content_types:
    common.nothing_selected(CARDS, "ไม่ได้เลือกหลักทรัพย์ ชุมชน หรือประเภทความรู้สึกส่วนใหญ่ จึงไม่มีข้อมูลแสดง")

z_min = float(st.session_state.get("d_z", 0.0))             # not on a slider any more: the Reddit Volume Threshold counts the texts (v_min), a volume spike stays "Z > 1.5" (proposal)
v_min = int(st.session_state.get("d_v", 0))
s_min = common.sentiment_cut()                              # the Sentiment Threshold of the sidebar (a float, or the name of a signed variant), the same on pages 5, 6 and 7
found = q("market_signals", start, end, tuple(tickers), tuple(statuses), z_min, s_min, tuple(communities), model, tuple(content_types), v_min, SPIKE_Z)      # the hours of the whole market that pass, x the assets chosen

common.kpi_cards([(CARDS[0], "{:,}".format(len(found)), None),
                  (CARDS[1], str(found.ticker.nunique()), None),
                  (CARDS[2], "{:,}".format(found.hour_utc.nunique()), "หลายสินทรัพย์เกิดในชั่วโมงเดียวกันได้")])

st.subheader("รายการสัญญาณ (Detected Signal List)")
st.caption("Z-score และความรู้สึกในหน้านี้คิดจากข้อความทั้งหมดของตลาดในชั่วโมงนั้น (เหมือนหน้า Statistical Analysis) สินทรัพย์ต่างกันที่ราคาและ Ticker Mention Rate  \n"
           "เกณฑ์ปัจจุบันคือ Reddit Volume อย่างน้อย %s ข้อความต่อชั่วโมง และ Sentiment Threshold: %s (ค่า 0 คือไม่กรอง ปรับได้ที่แถบด้านซ้าย)  \n"
           "Z-score เทียบกับ 24 ชั่วโมงก่อนหน้า ทุกสินทรัพย์ในชั่วโมงเดียวกันจึงได้ Z และความรู้สึกเท่ากัน  \n"
           "**ชนิดของสัญญาณ**  \n"
           "volume_spike คือปริมาณพุ่งอย่างเดียว (Reddit Volume Z-score > 1.5 ตาม proposal)  \n"
           "positive_sentiment_spike และ negative_sentiment_spike คือความรู้สึกบวกหรือลบอย่างเดียว  \n"
           "combined_signal คือปริมาณพุ่งและความรู้สึกมีทิศทางพร้อมกัน  \n"
           "Reddit Volume Z-score คือปริมาณข้อความทั้งหมดของตลาดเทียบ 24 ชั่วโมงก่อนหน้า (เหมือนกันทุกสินทรัพย์ในชั่วโมงเดียวกัน) ส่วน Trading Volume Z-score คือปริมาณซื้อขายของราคาของสินทรัพย์นั้นเอง (ตารางที่ 8 ข้อ 2) ว่างเมื่อไม่มีข้อมูลปริมาณซื้อขาย  \n**ระดับ (signal_level)** คือคะแนนความแรงของสัญญาณ 1 / 2 / 3 = low / medium / high (สูตรตั้งเองใน configs/detection.yaml ส่วนขยายจาก proposal):  \n"
           "คะแนนปริมาณ = 1 เมื่อ Reddit Volume Z-score เกิน 1.5 แล้วเพิ่ม 1 คะแนนทุก ๆ 1.0 ของ Z ที่สูงขึ้น (Z 1.5–2.5 = 1, 2.5–3.5 = 2, ตั้งแต่ 3.5 = 3)  \n"
           "คะแนนความรู้สึก = นับว่า |Sentiment Score เฉลี่ยของชั่วโมง| ถึงกี่เกณฑ์จาก [ขั้นต่ำ, 0.5, 0.8] (ค่าเฉลี่ยของทั้งตลาดมักต่ำกว่า 0.5 จึงมักได้ 1)  \n"
           "combined_signal ใช้คะแนนที่สูงกว่าของสองอย่าง สูงสุด 3  ในทางปฏิบัติระดับจึงขึ้นกับ Z-score เป็นหลัก ไม่ขึ้นกับสไลเดอร์ Sentiment Threshold  \n"
           "รายการนี้ใช้ประกอบการวิเคราะห์ ไม่ใช่คำแนะนำการลงทุน" % ("{:,}".format(v_min) if v_min else "0 (ไม่กรอง)", common.cut_label(s_min)))
if found.empty:
    st.info("ไม่พบสัญญาณตามเกณฑ์นี้ในช่วงที่เลือก ลองลดเกณฑ์หรือขยายช่วงเวลา")
    st.stop()

# ---- 1. how many ----------------------------------------------------------------------------------------------------------------
st.write("จำนวนสัญญาณ แยกตามกลุ่มสินทรัพย์และประเภทสัญญาณ")
summary = pd.crosstab(found.big_group.map(GROUP_LABELS).rename("กลุ่ม"), found.signal_type, margins=True, margins_name="รวม").reset_index()
common.table(summary, hide_index=True, width="stretch")

# ---- 2. the list, with what the price did after each signal and the statistics of its asset (looked up from the system 7.4) ------------------
st.subheader("รายการสัญญาณที่ตรวจพบ (ล่าสุด 300 รายการ)")
st.session_state.setdefault("h_wh", "Current Return")
st.session_state.setdefault("h_wr", 0)

# ---- the thresholds of DimDetectionConfig, also here: the same values as the sidebar (changing one moves the other), so the list is built by pressing the filters in one place
state = st.session_state
PAIRS = {"h_v": "d_v", "h_mode": "d_mode", "h_s": "d_s", "h_ss": "d_ss"}                    # widget here -> the shared value of the sidebar


def to_sidebar(here):
    def callback():
        state[PAIRS[here]] = state[here]
    return callback


for here, shared in PAIRS.items():                                                          # the shared value (the sidebar's) is the truth at every run
    if shared in state:
        state[here] = state[shared]
st.markdown("**เกณฑ์การตรวจจับสัญญาณ (DimDetectionConfig)** ค่าเดียวกับแถบด้านซ้าย ปรับที่ไหนก็ได้")
col_v, col_s = st.columns(2)
col_v.slider("Reddit Volume Threshold (ชั่วโมงที่ข้อความทั้งตลาดอย่างน้อยกี่ข้อความ ค่า 0 = ไม่กรอง)", 0, 6000, step=100, key="h_v", on_change=to_sidebar("h_v"))
col_s.radio("Sentiment Threshold", common.SENTIMENT_MODES, format_func=common.MODE_LABELS.get, horizontal=True, key="h_mode", on_change=to_sidebar("h_mode"),
            help="absolute: เก็บข้อความที่ |ความรู้สึก| ≥ ค่านี้  ค่าปกติ: ค่าบวกเก็บข้อความที่คะแนน ≥ ค่านี้ ค่าลบเก็บข้อความที่คะแนน ≤ ค่านี้  0 = ไม่กรอง")
if state.get("h_mode", "absolute") == "absolute":
    col_s.slider("Sentiment Threshold (absolute)", 0.0, 0.95, step=0.05, key="h_s", on_change=to_sidebar("h_s"), label_visibility="collapsed")
else:
    col_s.slider("Sentiment Threshold (ค่าปกติ)", -0.95, 0.95, step=0.05, key="h_ss", on_change=to_sidebar("h_ss"), label_visibility="collapsed")

horizon = st.radio("Horizon ของ Win Rate", [name for _, name in TARGETS], horizontal=True, key="h_wh",
                   help="กรอบเวลาที่ใช้ดูว่าราคาตามความรู้สึกหรือไม่ ใช้กับคอลัมน์ผลตอบแทน และ Win Rate / Correlation ของสินทรัพย์ (ค่าจากระบบ 7.4)")
st.slider("Win Rate ขั้นต่ำของสินทรัพย์ (%)", 0, 80, key="h_wr", help="แสดงเฉพาะแถวของสินทรัพย์ที่ Win Rate (ที่ Horizon นี้) ไม่ต่ำกว่าค่านี้ ค่า 0 คือไม่กรอง")
column = dict((name, col) for col, name in TARGETS)[horizon]
filtering = st.session_state["h_wr"] > 0
GREEN, RED = "color: #1a9850; font-weight: 600", "color: #d73027; font-weight: 600"
tab_score, tab_major = st.tabs(["วัดจากคะแนนความรู้สึก (sentiment_mean)", "วัดจากทิศทางส่วนใหญ่ (majority: บวก / ลบ)"])


def signal_table(basis):
    """One tab of the list: `basis` = how the sentiment is read ('sentiment_mean' = the score, 'majority' = + / - of the majority status).  The Win
    Rate, the correlations and the p-values of the asset are looked up from the system 7.4 (the very numbers of the Statistical Analysis page with the
    same filters: panel_global 'all texts', the sentiment of the whole market, the hours that pass the same thresholds)."""
    stat74 = common.panel_stat("global", "all", tuple(tickers), start, end, tuple(communities), model, tuple(statuses), z_min, s_min, tuple(content_types), basis, v_min)
    win_table = pd.DataFrame({"ticker": stat74.ticker, "horizon": stat74.target.map(data.LOOKUP_HORIZONS), "n": stat74.win_n, "win_rate": stat74.winrate,
                              "rho": stat74.spearman_rho, "pearson": stat74.pearson_rho, "p": stat74.win_p, "p_bh": stat74.win_bh})
    pair = win_table[win_table.horizon == horizon].set_index("ticker")[["n", "win_rate", "rho", "pearson", "p", "p_bh"]].add_prefix("pair_")
    listed = found.join(pair, on="ticker")
    direction = listed.sentiment_mean if basis == "sentiment_mean" else listed.majority_final_status.map({"positive": 1.0, "negative": -1.0, "neutral": 0.0})
    listed = listed.assign(direction=direction)
    judged = listed[column].notna() & (listed[column] != 0) & listed.direction.notna() & (listed.direction != 0)
    listed = listed[judged]                                                    # only signals that can be judged (a price move and a direction), the ones the win rate counts
    if filtering:
        listed = listed[listed.pair_win_rate >= st.session_state["h_wr"]]      # assets with fewer than MIN_N signals have no win rate, so they never pass
    tested = int(win_table.p.notna().sum())
    passed = int((win_table.p_bh < 0.05).sum())
    st.caption("Win Rate และ Correlation ของสินทรัพย์คือตัวเลขชุดเดียวกับหน้า Statistical Analysis (ระบบ 7.4, แท็บ \"ทุกข้อความ\", ความรู้สึกของข้อความทั้งตลาด, ตัวกรองชุดเดียวกัน) "
               "ทดสอบ %d คู่ (สินทรัพย์ × Horizon) ถ้าไม่มีความสัมพันธ์จริง คาดว่าราว %.1f คู่จะได้ p ต่ำกว่า 0.05 เพียงเพราะโชค ผ่านการปรับ BH จริง %d คู่ (BH ปรับข้ามสินทรัพย์ภายในแต่ละ Horizon) "
               "เกณฑ์ Win Rate กรองเฉพาะรายการด้านล่าง ไม่กรองการ์ด ตารางสรุป และกราฟ Win Rate รวม" % (tested, 0.05 * tested, passed))
    if listed.empty:
        st.info("ไม่มีสัญญาณที่ตัดสินได้หรือผ่านเกณฑ์ Win Rate นี้ ลองลดเกณฑ์")
        return
    view = listed.head(300)
    follow = np.sign(view.direction) * np.sign(view[column])                   # +1 the price went with the sentiment, -1 against
    OUTCOME = "ราคาตามความรู้สึก (%s)" % horizon
    shown = pd.DataFrame({
        "เวลา (UTC)": pd.to_datetime(view.hour_utc, unit="s", utc=True).dt.strftime("%Y-%m-%d %H:%M"),
        "สินทรัพย์": view.ticker, "กลุ่ม": view.big_group.map(GROUP_LABELS), "ชนิด": view.signal_type, "ระดับ": view.signal_level,
        "Reddit Volume (ทั้งตลาด)": view.market_volume, "Ticker Mention Count": view.mentions, "Ticker Mention Rate (%)": view.mention_rate,
        "Reddit Volume Z-score (ทั้งตลาด)": view.reddit_volume_zscore_24, "Trading Volume Z-score (ของสินทรัพย์)": pd.to_numeric(view.volume_zscore_24, errors="coerce"),
        ("ความรู้สึก (ทั้งตลาด)" if basis == "sentiment_mean" else "ทิศทางส่วนใหญ่"): view.sentiment_mean if basis == "sentiment_mean" else view.majority_final_status,
        "|ความรู้สึก| เฉลี่ย (ความแรง)": view.abs_mean,
        NAMES[column]: view[column].where(view[column] != 0),
        OUTCOME: np.where(follow > 0, "ตรง", np.where(follow < 0, "สวน", "-")),
        "Win Rate ของสินทรัพย์ (%)": view.pair_win_rate, "n ของสินทรัพย์ (จำนวนชั่วโมงที่นับ)": view.pair_n, "Spearman ρ ของสินทรัพย์": view.pair_rho,
        "Pearson ρ ของสินทรัพย์": view.pair_pearson, "p ของ Win Rate (ดิบ)": view.pair_p, "p ของ Win Rate (ปรับ BH ส่วนขยาย)": view.pair_p_bh,
        "นัยสำคัญหลังปรับ": np.where(view.pair_p_bh < 0.05, "★", ""), "n น้อย": np.where(view.pair_n < WARN_N, "⚠", "")})
    colour = lambda col: [GREEN if (v == "ตรง" or (isinstance(v, float) and v > 0)) else (RED if (v == "สวน" or (isinstance(v, float) and v < 0)) else "") for v in col]
    numbers = {"Ticker Mention Rate (%)": "{:.3f}", "Reddit Volume Z-score (ทั้งตลาด)": "{:.2f}", "Trading Volume Z-score (ของสินทรัพย์)": "{:.2f}", "ความรู้สึก (ทั้งตลาด)": "{:.3f}", "|ความรู้สึก| เฉลี่ย (ความแรง)": "{:.3f}", NAMES[column]: "{:.3f}", "Win Rate ของสินทรัพย์ (%)": "{:.1f}",
               "Spearman ρ ของสินทรัพย์": "{:.3f}", "Pearson ρ ของสินทรัพย์": "{:.3f}", "p ของ Win Rate (ดิบ)": "{:.3f}", "p ของ Win Rate (ปรับ BH ส่วนขยาย)": "{:.3f}",
               "Reddit Volume (ทั้งตลาด)": "{:,.0f}", "Ticker Mention Count": "{:,.0f}", "n ของสินทรัพย์ (จำนวนชั่วโมงที่นับ)": "{:,.0f}"}
    styled = shown.style.apply(colour, subset=[NAMES[column], OUTCOME]).format({k: v for k, v in numbers.items() if k in shown.columns}, na_rep="-")
    st.dataframe(styled, hide_index=True, width="stretch", height=380)          # the numbers stay numbers, so a click on a header sorts them right
    st.caption("กดหัวคอลัมน์เพื่อเรียงลำดับ  \n"
               "**ความรู้สึก (ทั้งตลาด)** คือค่าเฉลี่ยของข้อความที่ผ่านเกณฑ์ บวกกับลบหักล้างกัน ค่าจึงอาจต่ำกว่าเกณฑ์ที่ตั้ง (ตั้ง 0.70 แต่ได้ −0.18 ได้) ส่วน **|ความรู้สึก| เฉลี่ย** คือความแรงโดยไม่สนทิศ (ส่วนขยาย) ซึ่งไม่ต่ำกว่าเกณฑ์  \n"
               "รายการแสดงเฉพาะสัญญาณที่ตัดสินได้ว่าตรงหรือสวน คือมีราคาใน Horizon ที่เลือก ผลตอบแทนไม่ใช่ 0 และทิศทางความรู้สึกไม่ใช่ 0 (ตรงกับที่ Win Rate นับ) สัญญาณที่ไม่มีราคา เช่น ตลาดปิด จะถูกซ่อน  \n"
               "\"ตรง\" (เขียว) คือราคาไปทางเดียวกับความรู้สึก \"สวน\" (แดง) คือตรงข้าม  \n"
               "Correlation (ρ) บวก = ไปทางเดียวกัน ลบ = สวนกัน ใกล้ 0 = แทบไม่เกี่ยวกัน Spearman ดูลำดับ Pearson ดูความสัมพันธ์เชิงเส้น ส่วน Win Rate นับแค่ว่าตรงหรือสวน  \n"
               "Win Rate, ρ, n และ p เป็นค่าของสินทรัพย์ (ทุกแถวของสินทรัพย์เดียวกันได้ค่าเดียวกัน) n คือจำนวนชั่วโมงของสินทรัพย์นั้นที่ผ่านเกณฑ์และนับใน Win Rate ทั้งช่วงที่เลือก ไม่ใช่จำนวนแถวที่เห็นในตาราง (ตารางแสดงล่าสุด 300 แถว) และ p คือ p-value ของ Win Rate (Binomial เทียบ 50%%) ⚠ คือ n ของสินทรัพย์น้อยกว่า %d ไม่น่าเชื่อถือ  \n"
               "p ดิบ ต่ำกว่า 0.05 อย่างเดียวยังไม่พอ เพราะเราลองหลายสิบคู่ ต้องดู p ปรับ BH ด้วย ★ คือ p ปรับ BH ต่ำกว่า 0.05 (การปรับ BH เป็นส่วนขยายจาก proposal)" % WARN_N)


with tab_score:
    signal_table("sentiment_mean")
with tab_major:
    signal_table("majority")
if filtering:
    st.warning("**คัดหลังเห็นผลแล้ว ใช้เป็นข้อมูลสำรวจเท่านั้น**  \n"
               "การเลือกสินทรัพย์ที่ Win Rate สูงจากหลายสิบคู่ มักได้คู่ที่สูงเพราะโชค โดยเฉพาะเมื่อ n น้อย ดูช่วงเชื่อมั่นและ p ปรับ BH ประกอบเสมอ คู่ที่ไม่มี ★ แยกจากการสุ่มไม่ได้")


st.warning("**ดูเหตุการณ์ย้อนหลัง ไม่ใช่สัญญาณซื้อขาย**  \n"
           "ผลทดสอบทั้งโครงการพบว่าความรู้สึกบน Reddit ทำนายทิศทางราคาได้ไม่ดีกว่าการสุ่ม (ราว 50%)  ค่าที่ดูสูงในบางช่องมักเป็นความบังเอิญ โดยเฉพาะเมื่อ n น้อย")
