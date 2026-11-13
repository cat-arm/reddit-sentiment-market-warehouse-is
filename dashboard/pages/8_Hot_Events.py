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
common.hide_sidebar()                                                           # the whole width of the page
common.keep_filters()                                                           # no filter on this page: it works on ALL the data, the filters of the other pages are kept for them
info = q("data_range")
start, end = int(info["reddit_lo"]), int(info["reddit_hi"])                       # the whole period of the Reddit data, the latest hour included
tickers = list(q("tickers").ticker)                                               # every asset
communities = list(dict.fromkeys(q("sources").subreddit))                         # every community
statuses = ["positive", "negative", "neutral"]                                    # every majority status
content_types = ["Post", "Comment"]                                               # posts and comments
model = "VADER+FinBERT"                                                           # the final sentiment of the proposal
z_min, v_min, s_min = 0.0, 0, 0.0                                                 # no threshold: the score below decides what is a signal (a volume spike stays "Z > 1.5" of the proposal)
found = q("market_signals", start, end, tuple(tickers), tuple(statuses), z_min, s_min, tuple(communities), model, tuple(content_types), v_min, SPIKE_Z)      # every hour of the market x every asset with a price bar

bars = q("price_series_for", tuple(tickers), start, end)[["ticker", "hour_utc", "normalized_atr", "volume"]].rename(columns={"volume": "trading_volume"})
found = found.merge(bars, on=["ticker", "hour_utc"], how="left")

# ---- the score of a signal: every measure has ONE threshold and some points; the points of the measures a signal passes add up, and the total decides low / medium / high ----
# (EXTENSION: the proposal names the three levels, not how they are reached)
state = st.session_state
LEVELS = ("low", "medium", "high")
METRICS = [("rz", "Reddit Volume Z-score (ทั้งตลาด) >", 1.5, 3, 0.5), ("mr", "Ticker Mention Rate (%) >", 0.5, 1, 0.5),
           ("ss", "|Sentiment Score| ของชั่วโมง >", 0.05, 2, 0.01), ("sm", "|Sentiment Momentum| (เปลี่ยนจากชั่วโมงก่อน) >", 0.02, 1, 0.01),
           ("tz", "Trading Volume Z-score (ของสินทรัพย์) >", 2.0, 1, 0.5), ("na", "Normalized ATR (%) (ความผันผวน) >", 1.0, 1, 0.1),
           ("cr", "|Current Return| (%) >", 1.0, 1, 0.1)]
# (key, label, default threshold, default points, step); the default points add up to 10.  Only KPIs written in the proposal (the measure tables of the dashboards) and known in
# the hour itself or from the hours before it; no statistic of the whole history (Spearman, Win Rate ...) is a point, because it could not be known when the signal appeared
# (look-ahead): those stay as columns beside the signal.
DEFAULT_CUTS = {"low": 3, "medium": 5, "high": 8}                                      # the total points a signal needs for the level (of 10)


def reset_scoring():
    for m, _, threshold, points, _ in METRICS:
        state["hs_%s_t" % m], state["hs_%s_p" % m] = threshold, points
    for lv in LEVELS:
        state["hs_cut_" + lv] = DEFAULT_CUTS[lv]


for m, _, threshold, points, _ in METRICS:
    state.setdefault("hs_%s_t" % m, threshold)
    state.setdefault("hs_%s_p" % m, points)
for lv in LEVELS:
    state.setdefault("hs_cut_" + lv, DEFAULT_CUTS[lv])

st.subheader("ตั้งค่าคะแนนและระดับของสัญญาณ (low / medium / high)")
st.caption("แต่ละตัวชี้วัดมี **เกณฑ์เดียว** และ **คะแนน**: ถ้าสัญญาณนั้นผ่านเกณฑ์ (ค่า > เกณฑ์) ได้คะแนนของตัวชี้วัดนั้น แล้วเอาคะแนนที่ได้มาบวกกัน ผลรวมถึงกี่คะแนนก็ได้ระดับนั้น "
           "(เช่น คะแนนเต็ม 10 ผลรวมตั้งแต่ 8 = high)  เว้นเกณฑ์ว่างหรือใส่คะแนน 0 = ไม่ใช้ตัวชี้วัดนั้น  \n"
           "คะแนนมาจาก KPI ที่เขียนไว้ใน proposal (Reddit Volume Z-score, Ticker Mention Rate, Sentiment Score และ Momentum, Trading Volume Z-score, Normalized ATR, Current Return) ซึ่งรู้ ณ ชั่วโมงนั้นและย้อนหลังเท่านั้น (Z-score เทียบ 24 ชั่วโมงก่อนหน้า) ไม่ใช้สถิติย้อนหลังทั้งช่วง (Win Rate, Spearman, Pearson) เพราะตอนที่สัญญาณเกิดยังรู้ค่าเหล่านั้นไม่ได้ ค่าเหล่านั้นแสดงเป็นคอลัมน์ประกอบการตีความ  \n"
           "สัญญาณที่ได้คะแนนไม่ถึงระดับ low จะไม่ถูกแสดง ค่าเริ่มต้นตั้งตามการกระจายของข้อมูลจริง (low ≥ 3, medium ≥ 5, high ≥ 8)")
with st.expander("เกณฑ์ คะแนน และระดับ", expanded=False):
    with st.form("h_score_form", border=False):                                       # nothing below changes until the button Apply is pressed
        head = st.columns([4, 2, 2])
        head[0].markdown("**ตัวชี้วัด**")
        head[1].markdown("**เกณฑ์ (ผ่านเมื่อค่า >)**")
        head[2].markdown("**คะแนนที่ได้**")
        for m, label, _, _, step in METRICS:
            row = st.columns([4, 2, 2])
            row[0].write(label)
            row[1].number_input(label + " เกณฑ์", value=None, step=step, key="hs_%s_t" % m, placeholder="ไม่ใช้", label_visibility="collapsed")
            row[2].number_input(label + " คะแนน", min_value=0.0, step=0.5, key="hs_%s_p" % m, label_visibility="collapsed")
        total = sum(float(state["hs_%s_p" % m]) for m, *_ in METRICS if state.get("hs_%s_t" % m) is not None)
        st.markdown("**คะแนนเต็ม = %g** (ของเกณฑ์ที่ใช้อยู่ตอนนี้)  ระดับต้องการคะแนนรวมตั้งแต่:" % total)
        cuts_row = st.columns(3)
        for col, lv in zip(cuts_row, LEVELS):
            col.number_input(lv, min_value=0.0, step=0.5, key="hs_cut_" + lv)
        apply_col, reset_col, _ = st.columns([2, 2, 6])
        apply_col.form_submit_button("ใช้เกณฑ์นี้ (Apply)", type="primary", key="h_apply")
        reset_col.form_submit_button("คืนค่าเริ่มต้น", on_click=reset_scoring, key="h_level_reset")
    st.caption("แก้เกณฑ์ คะแนน หรือระดับแล้วกด **ใช้เกณฑ์นี้ (Apply)** เกณฑ์จึงจะทำงานกับการ์ดและตารางด้านล่าง (ยังไม่กด ตัวเลขด้านล่างยังเป็นของเกณฑ์เดิม)")

horizon, column = "Current Return", "log_return"                          # the statistics beside a signal are those of the same hour (Current Return); no horizon to pick
rules = {m: (float(state["hs_%s_t" % m]), float(state["hs_%s_p" % m])) for m, *_ in METRICS if state.get("hs_%s_t" % m) is not None and float(state["hs_%s_p" % m]) > 0}
cuts = {lv: float(state["hs_cut_" + lv]) for lv in LEVELS}
if not rules:
    st.info("ต้องใช้ตัวชี้วัดอย่างน้อย 1 ตัว (มีเกณฑ์และคะแนนมากกว่า 0)")
    st.stop()
if not cuts["low"] <= cuts["medium"] <= cuts["high"] or cuts["low"] <= 0:
    st.info("คะแนนของระดับต้องเรียงจากน้อยไปมาก: low ≤ medium ≤ high และ low มากกว่า 0")
    st.stop()
if cuts["high"] > total:
    st.warning("ระดับ high ต้องการ %g คะแนน แต่คะแนนเต็มมีแค่ %g จึงไม่มีสัญญาณระดับ high" % (cuts["high"], total))
GREEN, RED = "color: #1a9850; font-weight: 600", "color: #d73027; font-weight: 600"
SOURCE = {"rz": lambda d: d.reddit_volume_zscore_24, "mr": lambda d: d.mention_rate, "ss": lambda d: d.sentiment_mean.abs(), "sm": lambda d: d.momentum.abs(),
          "tz": lambda d: pd.to_numeric(d.volume_zscore_24, errors="coerce"), "na": lambda d: pd.to_numeric(d.normalized_atr, errors="coerce"),
          "cr": lambda d: pd.to_numeric(d.log_return, errors="coerce").abs()}


def listed_for(basis):
    """The signals of one tab with their score and level: every (asset x hour) the sidebar lets through, joined with the statistics of its asset (looked up
    from the system 7.4: the numbers of the Statistical Analysis page with the same filters), kept when it can be judged (a price move and a direction)
    and its points reach at least the level low.  -> (rows, win_table)."""
    stat74 = common.panel_stat("global", "all", tuple(tickers), start, end, tuple(communities), model, tuple(statuses), z_min, s_min, tuple(content_types), basis, v_min)
    win_table = pd.DataFrame({"ticker": stat74.ticker, "horizon": stat74.target.map(data.LOOKUP_HORIZONS), "n": stat74.win_n, "win_rate": stat74.winrate,
                              "rho": stat74.spearman_rho, "pearson": stat74.pearson_rho, "p": stat74.win_p, "p_bh": stat74.win_bh})
    pair = win_table[win_table.horizon == horizon].set_index("ticker")[["n", "win_rate", "rho", "pearson", "p", "p_bh"]].add_prefix("pair_")
    listed = found.join(pair, on="ticker")
    direction = listed.sentiment_mean if basis == "sentiment_mean" else listed.majority_final_status.map({"positive": 1.0, "negative": -1.0, "neutral": 0.0})
    listed = listed.assign(direction=direction)
    judged = listed[column].notna() & (listed[column] != 0) & listed.direction.notna() & (listed.direction != 0)
    listed = listed[judged]                                                    # only signals that can be judged (a price move and a direction), the ones the win rate counts
    score = pd.Series(0.0, index=listed.index)
    for m, (threshold, points) in rules.items():
        score += (SOURCE[m](listed) > threshold).astype(float) * points         # a missing value never passes
    level = pd.Series("", index=listed.index).mask(score >= cuts["low"], "low").mask(score >= cuts["medium"], "medium").mask(score >= cuts["high"], "high")
    listed = listed.assign(score=score, level_name=level)
    return listed[level != ""], win_table                                       # a signal below the level low is dropped


listed_score, _ = listed_for("sentiment_mean")
if found.empty:
    st.info("ไม่พบชั่วโมงตามตัวกรองด้านซ้ายในช่วงที่เลือก ลองลดเกณฑ์หรือขยายช่วงเวลา")
    st.stop()
common.kpi_cards([(CARDS[0], "{:,}".format(len(listed_score)), "สัญญาณที่ได้คะแนนถึงระดับ low และตัดสินได้ (นับตามแท็บคะแนน) ที่ต่ำกว่า low ถูกคัดทิ้ง"),
                  (CARDS[1], str(listed_score.ticker.nunique()), None),
                  (CARDS[2], "{:,}".format(listed_score.hour_utc.nunique()), "หลายสินทรัพย์เกิดในชั่วโมงเดียวกันได้")])
if listed_score.empty:
    st.info("ไม่มีสัญญาณที่ได้คะแนนถึงระดับ low ลองลดเกณฑ์หรือขยายช่วงเวลา")
    st.stop()

st.caption("หน้านี้ใช้ข้อมูลทั้งหมด (ทั้งช่วงข้อมูล Reddit ถึงชั่วโมงล่าสุด, ทุกสินทรัพย์, ทุกชุมชน, โพสต์และคอมเมนต์, โมเดล VADER+FinBERT) ไม่มีตัวกรองด้านซ้าย  \n"
           "Reddit Volume, Z-score และความรู้สึกคิดจากข้อความทั้งหมดของตลาดในชั่วโมงนั้น ทุกสินทรัพย์ในชั่วโมงเดียวกันจึงได้ค่าตลาดเท่ากัน สินทรัพย์ต่างกันที่ราคา ปริมาณซื้อขาย และจำนวนข้อความที่พูดถึง  \n"
           "ระดับมาจากคะแนนที่ตั้งไว้ด้านบน (proposal ระบุแค่ว่ามี low / medium / high ส่วนวิธีให้คะแนนเป็นส่วนขยาย)  \n"
           "รายการนี้ใช้ประกอบการวิเคราะห์ ไม่ใช่คำแนะนำการลงทุน")

# ---- 1. how many ----------------------------------------------------------------------------------------------------------------
st.write("จำนวนสัญญาณ แยกตามกลุ่มสินทรัพย์และระดับ (แท็บคะแนน)")
summary = pd.crosstab(listed_score.big_group.map(GROUP_LABELS).rename("กลุ่ม"), listed_score.level_name.rename("ระดับ").astype(
    pd.CategoricalDtype(list(LEVELS), ordered=True)), margins=True, margins_name="รวม").reset_index()
common.table(summary, hide_index=True, width="stretch")

# ---- 2. the list, with the statistics of its asset (looked up from the system 7.4) -------------------------------------------------------------
st.subheader("รายการสัญญาณที่ตรวจพบ (ล่าสุด 300 รายการ)")
level_pick = st.radio("ระดับที่แสดงในตาราง", ["all", *LEVELS], horizontal=True, key="h_levels", help="เลือกระดับที่อยากเห็นในรายการ all = ทุกระดับ (การ์ดและตารางสรุปนับทุกระดับเสมอ)")
levels_shown = list(LEVELS) if level_pick == "all" else [level_pick]
tab_score, tab_major = st.tabs(["วัดจากคะแนนความรู้สึก (sentiment_mean)", "วัดจากทิศทางส่วนใหญ่ (majority: บวก / ลบ)"])


def signal_table(basis):
    """One tab of the list: `basis` = how the sentiment is read ('sentiment_mean' = the score, 'majority' = + / - of the majority status)."""
    listed, win_table = listed_for(basis)
    listed = listed[listed.level_name.isin(levels_shown)]
    if listed.empty:
        st.info("ไม่มีสัญญาณในระดับที่เลือกที่ตัดสินได้ ในแท็บนี้ ลองเลือกระดับเพิ่มหรือลดเกณฑ์")
        return
    view = listed.head(300)
    follow = np.sign(view.direction) * np.sign(view[column])                   # +1 the price went with the sentiment, -1 against
    OUTCOME = "ราคาตามความรู้สึก"
    SENT = "ความรู้สึกเฉลี่ย (ทั้งตลาด)" if basis == "sentiment_mean" else "ทิศทางส่วนใหญ่ (ทั้งตลาด)"
    shown = pd.DataFrame({
        "เวลา (UTC)": pd.to_datetime(view.hour_utc, unit="s", utc=True).dt.strftime("%Y-%m-%d %H:%M"),
        "สินทรัพย์": view.ticker, "กลุ่ม": view.big_group.map(GROUP_LABELS), "ระดับ": view.level_name, "คะแนน": view.score,
        "Ticker Mention Count": view.mentions, "Reddit Volume (ทั้งตลาด)": view.market_volume, "Current Return (%)": view.log_return,
        "Trading Volume (ของสินทรัพย์)": view.trading_volume,
        SENT: view.sentiment_mean if basis == "sentiment_mean" else view.majority_final_status,
        OUTCOME: np.where(follow > 0, "ตรง", np.where(follow < 0, "สวน", "-")),
        "n ของสินทรัพย์ (จำนวนชั่วโมงที่นับ)": view.pair_n, "Spearman ρ ของสินทรัพย์": view.pair_rho, "Pearson ρ ของสินทรัพย์": view.pair_pearson,
        "Win Rate ของสินทรัพย์ (%)": view.pair_win_rate, "p ของ Win Rate (ดิบ)": view.pair_p, "p ของ Win Rate (ปรับ BH ส่วนขยาย)": view.pair_p_bh,
        "นัยสำคัญหลังปรับ": np.where(view.pair_p_bh < 0.05, "★", "")})
    colour = lambda col: [GREEN if v == "ตรง" else (RED if v == "สวน" else "") for v in col]
    numbers = {"คะแนน": "{:.1f}", "Ticker Mention Count": "{:,.0f}", "Reddit Volume (ทั้งตลาด)": "{:,.0f}", "Trading Volume (ของสินทรัพย์)": "{:,.0f}", "Current Return (%)": "{:+.3f}",
               "ความรู้สึกเฉลี่ย (ทั้งตลาด)": "{:.3f}", "n ของสินทรัพย์ (จำนวนชั่วโมงที่นับ)": "{:,.0f}", "Spearman ρ ของสินทรัพย์": "{:.3f}", "Pearson ρ ของสินทรัพย์": "{:.3f}",
               "Win Rate ของสินทรัพย์ (%)": "{:.1f}", "p ของ Win Rate (ดิบ)": "{:.3f}", "p ของ Win Rate (ปรับ BH ส่วนขยาย)": "{:.3f}"}
    styled = shown.style.apply(colour, subset=[OUTCOME]).format({k: v for k, v in numbers.items() if k in shown.columns}, na_rep="-")
    st.dataframe(styled, hide_index=True, width="stretch", height=380)          # the numbers stay numbers, so a click on a header sorts them right
    tested = int(win_table.p.notna().sum())
    passed = int((win_table.p_bh < 0.05).sum())
    st.caption("กดหัวคอลัมน์เพื่อเรียงลำดับ  \n"
               "**ราคาตามความรู้สึก**: \"ตรง\" (เขียว) คือราคาของชั่วโมงเดียวกันไปทางเดียวกับความรู้สึก \"สวน\" (แดง) คือตรงข้าม  รายการแสดงเฉพาะสัญญาณที่ตัดสินได้ คือมีราคา ผลตอบแทนไม่ใช่ 0 และทิศทางความรู้สึกไม่ใช่ 0  \n"
               "Spearman, Pearson, Win Rate และ p เป็นค่าของสินทรัพย์ (ทุกแถวของสินทรัพย์เดียวกันได้ค่าเดียวกัน) จากหน้า Statistical Analysis (ระบบ 7.4, panel Global ทุกข้อความ, ตัวกรองชุดเดียวกัน) ที่ Current Return  \n"
               "n คือจำนวนชั่วโมงของสินทรัพย์นั้นที่นับใน Win Rate ทั้งช่วงที่เลือก ไม่ใช่จำนวนแถวที่เห็น (ตารางแสดงล่าสุด 300 แถว) p คือ p-value ของ Win Rate (Binomial เทียบ 50%%) ★ คือ p ปรับ BH ต่ำกว่า 0.05 (BH เป็นส่วนขยายจาก proposal)  \n"
               "ทดสอบ %d คู่ (สินทรัพย์ × Horizon) ถ้าไม่มีความสัมพันธ์จริง คาดว่าราว %.1f คู่จะได้ p ต่ำกว่า 0.05 เพียงเพราะโชค ผ่านการปรับ BH จริง %d คู่" % (tested, 0.05 * tested, passed))


with tab_score:
    signal_table("sentiment_mean")
with tab_major:
    signal_table("majority")

st.warning("**ดูเหตุการณ์ย้อนหลัง ไม่ใช่สัญญาณซื้อขาย**  \n"
           "ผลทดสอบทั้งโครงการพบว่าความรู้สึกบน Reddit ทำนายทิศทางราคาได้ไม่ดีกว่าการสุ่ม (ราว 50%)  ค่าที่ดูสูงในบางช่องมักเป็นความบังเอิญ โดยเฉพาะเมื่อ n น้อย")
