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

MIN_TEXTS = 3                                                     # the asset's own sentiment needs this many texts in the hour (a mean of 1-2 texts is noise)
own = common.hourly_base("Ticker", common.text_variant(), tuple(tickers), start, end, tuple(communities), model, tuple(content_types))
own = own[["series", "hour_utc", "sentiment_mean", "momentum", "own_zscore", "voter_agreement", "sent_texts"]].rename(columns={
    "series": "ticker", "sentiment_mean": "t_sent", "momentum": "t_mom", "own_zscore": "t_oz", "voter_agreement": "t_va", "sent_texts": "t_n"})
for col in ("t_sent", "t_mom", "t_va"):
    own.loc[own.t_n < MIN_TEXTS, col] = np.nan                    # too few texts: the asset's own sentiment measures do not score
bars = q("price_series_for", tuple(tickers), start, end)[["ticker", "hour_utc", "rsi", "normalized_atr"]]
found = found.merge(own, on=["ticker", "hour_utc"], how="left").merge(bars, on=["ticker", "hour_utc"], how="left")

cards_slot = st.container()                                       # the cards come first on the page; they are filled once the score below is known
# ---- the score of a signal: every measure has ONE threshold and some points; the points of the measures a signal passes add up, and the total decides low / medium / high ----
# (EXTENSION: the proposal names the three levels, not how they are reached)
state = st.session_state
LEVELS = ("low", "medium", "high")
METRICS = [("rz", "Reddit Volume Z-score (ทั้งตลาด) >", 1.5, 2, 0.5), ("oz", "Reddit Volume Z-score ของสินทรัพย์เอง (ข้อความที่พูดถึง) >", 1.5, 1, 0.5),
           ("mr", "Ticker Mention Rate (%) >", 0.5, 1, 0.5), ("ss", "|Sentiment Score| ของทั้งตลาด >", 0.05, 1, 0.01),
           ("ts", "|Sentiment Score| ของสินทรัพย์เอง >", 0.2, 1, 0.05), ("al", "ความรู้สึกของสินทรัพย์สอดคล้องกับตลาด (1 = ทิศเดียวกัน) >", 0.0, 1, 0.5),
           ("va", "ความเห็นตรงกัน (voter agreement ของสินทรัพย์) >", 0.6, 0, 0.05), ("sm", "|Sentiment Momentum| ของสินทรัพย์ (เปลี่ยนจากชั่วโมงก่อน) >", 0.2, 0, 0.05),
           ("tz", "Trading Volume Z-score (ของสินทรัพย์) >", 2.0, 1, 0.5), ("cr", "|Current Return| (%) >", 1.0, 1, 0.1),
           ("rs", "|RSI − 50| (ห่างจากกลาง) >", 20.0, 0, 1.0), ("na", "Normalized ATR (%) (ความผันผวน) >", 1.0, 1, 0.1)]
# (key, label, default threshold, default points, step); the default points add up to 10.  Every measure is a KPI of the dashboards and is known in the hour itself or from the
# hours before it: no statistic of the whole history (Spearman, Win Rate ...) is a point, because it could not be known when the signal appeared (look-ahead); those stay as columns.
DEFAULT_CUTS = {"low": 3, "medium": 5, "high": 7}                                      # the total points a signal needs for the level (of 10)


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
           "คะแนนมาจาก KPI ของแดชบอร์ดทั้งหมด (ปริมาณ Reddit, ความรู้สึกของตลาดและของสินทรัพย์เอง, ปริมาณซื้อขาย, ผลตอบแทน, RSI, ความผันผวน) ซึ่งรู้ ณ ชั่วโมงนั้นและย้อนหลังเท่านั้น (Z-score เทียบ 24 ชั่วโมงก่อนหน้า) ไม่ใช้สถิติย้อนหลังทั้งช่วง (Win Rate, Spearman, Pearson) เพราะตอนที่สัญญาณเกิดยังรู้ค่าเหล่านั้นไม่ได้ ค่าเหล่านั้นแสดงเป็นคอลัมน์ประกอบการตีความ  \n"
           "ตัวกรองด้านซ้าย (รวมสองเกณฑ์ Reddit Volume / Sentiment Threshold) ยังทำงานเหมือนเดิม คือกรองชั่วโมงและข้อความออกก่อน แล้วค่อยให้คะแนน  \n"
           "สัญญาณที่ได้คะแนนไม่ถึงระดับ low จะไม่ถูกแสดง ค่าเริ่มต้นตั้งตามการกระจายของข้อมูลจริง")
with st.expander("เกณฑ์ คะแนน และระดับ", expanded=True):
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
    st.markdown("**คะแนนเต็ม = %g** (รวมคะแนนของตัวชี้วัดที่ใช้)  ระดับต้องการคะแนนรวมตั้งแต่:" % total)
    cuts_row = st.columns(3)
    for col, lv in zip(cuts_row, LEVELS):
        col.number_input(lv, min_value=0.0, step=0.5, key="hs_cut_" + lv)
    st.button("คืนค่าเริ่มต้น", on_click=reset_scoring, key="h_level_reset")

state.setdefault("h_wh", "Current Return")
horizon = st.radio("Horizon ของ Win Rate", [name for _, name in TARGETS], horizontal=True, key="h_wh",
                   help="กรอบเวลาที่ใช้ดูว่าราคาตามความรู้สึกหรือไม่ ใช้กับคอลัมน์ผลตอบแทน และ Win Rate / Correlation ของสินทรัพย์ (ค่าจากระบบ 7.4)")
column = dict((name, col) for col, name in TARGETS)[horizon]
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
SOURCE = {"rz": lambda d: d.reddit_volume_zscore_24, "oz": lambda d: d.t_oz, "mr": lambda d: d.mention_rate, "ss": lambda d: d.sentiment_mean.abs(),
          "ts": lambda d: d.t_sent.abs(), "al": lambda d: np.sign(d.t_sent) * np.sign(d.sentiment_mean), "va": lambda d: d.t_va, "sm": lambda d: d.t_mom.abs(),
          "tz": lambda d: pd.to_numeric(d.volume_zscore_24, errors="coerce"), "cr": lambda d: pd.to_numeric(d.log_return, errors="coerce").abs(),
          "rs": lambda d: (pd.to_numeric(d.rsi, errors="coerce") - 50).abs(), "na": lambda d: pd.to_numeric(d.normalized_atr, errors="coerce")}


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
    # the type of the signal follows the same thresholds: the volume side (Reddit Volume Z-score) and the sentiment side (|Sentiment Score|) of the proposal
    nothing = pd.Series(False, index=listed.index)

    def passes(metric):
        return (SOURCE[metric](listed) > rules[metric][0]) if metric in rules else nothing
    volume_side = passes("rz") | passes("oz")                                  # the volume side: the market's or the asset's own Reddit volume is past its threshold
    sentiment_side = passes("ss") | passes("ts")                               # the sentiment side: the market's or the asset's own sentiment is past its threshold
    direction_of_kind = np.where(passes("ts"), listed.t_sent, listed.sentiment_mean)       # the sign of the sentiment that passed (the asset's own when it passed)
    kind = np.select([volume_side & sentiment_side, volume_side, sentiment_side & (direction_of_kind > 0), sentiment_side],
                     ["combined_signal", "volume_spike", "positive_sentiment_spike", "negative_sentiment_spike"], "")
    listed = listed.assign(score=score, level_name=level, kind=kind)
    return listed[(level != "") & (listed.kind != "")], win_table             # a signal needs the volume side or the sentiment side; the other measures only add points


listed_score, _ = listed_for("sentiment_mean")
with cards_slot:
    common.kpi_cards([(CARDS[0], "{:,}".format(len(listed_score)), "สัญญาณที่ได้คะแนนถึงระดับ low และตัดสินได้ (นับตามแท็บคะแนน)"),
                      (CARDS[1], str(listed_score.ticker.nunique()), None),
                      (CARDS[2], "{:,}".format(listed_score.hour_utc.nunique()), "หลายสินทรัพย์เกิดในชั่วโมงเดียวกันได้")])

st.subheader("รายการสัญญาณ (Detected Signal List)")
st.caption("Z-score และความรู้สึกในหน้านี้คิดจากข้อความทั้งหมดของตลาดในชั่วโมงนั้น (เหมือนหน้า Statistical Analysis) สินทรัพย์ต่างกันที่ราคาและ Ticker Mention Rate  \n"
           "เกณฑ์ปัจจุบันคือ Reddit Volume อย่างน้อย %s ข้อความต่อชั่วโมง และ Sentiment Threshold: %s (ค่า 0 คือไม่กรอง ปรับได้ที่แถบด้านซ้าย)  \n"
           "Z-score เทียบกับ 24 ชั่วโมงก่อนหน้า ทุกสินทรัพย์ในชั่วโมงเดียวกันจึงได้ Z และความรู้สึกเท่ากัน  \n"
           "**ชนิดของสัญญาณ** ตามเกณฑ์ของตัวชี้วัดด้านบน (ด้านปริมาณ = Reddit Volume Z-score ผ่านเกณฑ์, ด้านความรู้สึก = |Sentiment Score| ผ่านเกณฑ์):  \n"
           "volume_spike คือผ่านเฉพาะด้านปริมาณ  \n"
           "positive_sentiment_spike และ negative_sentiment_spike คือผ่านเฉพาะด้านความรู้สึก (บวกหรือลบตามเครื่องหมายของ sentiment_mean)  \n"
           "combined_signal คือผ่านทั้งสองด้านพร้อมกัน  \n"
           "สัญญาณต้องผ่านอย่างน้อยหนึ่งในสองด้านนี้ ตัวชี้วัดอื่นเพิ่มแค่คะแนน  \n"
           "Reddit Volume Z-score คือปริมาณข้อความทั้งหมดของตลาดเทียบ 24 ชั่วโมงก่อนหน้า (เหมือนกันทุกสินทรัพย์ในชั่วโมงเดียวกัน) ส่วน Trading Volume Z-score คือปริมาณซื้อขายของราคาของสินทรัพย์นั้นเอง (ตารางที่ 8 ข้อ 2) ว่างเมื่อไม่มีข้อมูลปริมาณซื้อขาย  \n**ระดับ (signal_level)** low / medium / high คือระดับจากคะแนนรวมตามเกณฑ์ที่ตั้งไว้ด้านบน (proposal ระบุแค่ว่ามี 3 ระดับ ส่วนวิธีให้คะแนนเป็นส่วนขยาย) คอลัมน์คะแนนคือผลรวม  \n"
           "รายการนี้ใช้ประกอบการวิเคราะห์ ไม่ใช่คำแนะนำการลงทุน" % ("{:,}".format(v_min) if v_min else "0 (ไม่กรอง)", common.cut_label(s_min)))
if found.empty:
    st.info("ไม่พบสัญญาณตามเกณฑ์นี้ในช่วงที่เลือก ลองลดเกณฑ์หรือขยายช่วงเวลา")
    st.stop()
if listed_score.empty:
    st.info("ไม่มีสัญญาณที่ได้คะแนนถึงระดับ low ลองลดเกณฑ์หรือขยายช่วงเวลา")
    st.stop()

# ---- 1. how many ----------------------------------------------------------------------------------------------------------------
st.write("จำนวนสัญญาณ แยกตามกลุ่มสินทรัพย์และระดับ (แท็บคะแนน)")
summary = pd.crosstab(listed_score.big_group.map(GROUP_LABELS).rename("กลุ่ม"), listed_score.level_name.rename("ระดับ").astype(
    pd.CategoricalDtype(list(LEVELS), ordered=True)), margins=True, margins_name="รวม").reset_index()
common.table(summary, hide_index=True, width="stretch")

# ---- 2. the list, with what the price did after each signal and the statistics of its asset (looked up from the system 7.4) ------------------
st.subheader("รายการสัญญาณที่ตรวจพบ (ล่าสุด 300 รายการ)")
tab_score, tab_major = st.tabs(["วัดจากคะแนนความรู้สึก (sentiment_mean)", "วัดจากทิศทางส่วนใหญ่ (majority: บวก / ลบ)"])


def signal_table(basis):
    """One tab of the list: `basis` = how the sentiment is read ('sentiment_mean' = the score, 'majority' = + / - of the majority status)."""
    listed, win_table = listed_for(basis)
    tested = int(win_table.p.notna().sum())
    passed = int((win_table.p_bh < 0.05).sum())
    st.caption("Win Rate และ Correlation ของสินทรัพย์คือตัวเลขชุดเดียวกับหน้า Statistical Analysis (ระบบ 7.4, แท็บ \"ทุกข้อความ\", ความรู้สึกของข้อความทั้งตลาด, ตัวกรองชุดเดียวกัน) "
               "ทดสอบ %d คู่ (สินทรัพย์ × Horizon) ถ้าไม่มีความสัมพันธ์จริง คาดว่าราว %.1f คู่จะได้ p ต่ำกว่า 0.05 เพียงเพราะโชค ผ่านการปรับ BH จริง %d คู่ (BH ปรับข้ามสินทรัพย์ภายในแต่ละ Horizon) "
               "" % (tested, 0.05 * tested, passed))
    if listed.empty:
        st.info("ไม่มีสัญญาณที่ตัดสินได้และได้คะแนนถึงระดับ low ในแท็บนี้ ลองลดเกณฑ์")
        return
    view = listed.head(300)
    follow = np.sign(view.direction) * np.sign(view[column])                   # +1 the price went with the sentiment, -1 against
    OUTCOME = "ราคาตามความรู้สึก (%s)" % horizon
    shown = pd.DataFrame({
        "เวลา (UTC)": pd.to_datetime(view.hour_utc, unit="s", utc=True).dt.strftime("%Y-%m-%d %H:%M"),
        "สินทรัพย์": view.ticker, "กลุ่ม": view.big_group.map(GROUP_LABELS), "ชนิด": view.kind, "ระดับ": view.level_name, "คะแนน": view.score,
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
st.warning("**ดูเหตุการณ์ย้อนหลัง ไม่ใช่สัญญาณซื้อขาย**  \n"
           "ผลทดสอบทั้งโครงการพบว่าความรู้สึกบน Reddit ทำนายทิศทางราคาได้ไม่ดีกว่าการสุ่ม (ราว 50%)  ค่าที่ดูสูงในบางช่องมักเป็นความบังเอิญ โดยเฉพาะเมื่อ n น้อย")
