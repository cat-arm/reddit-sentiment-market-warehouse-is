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

import altair as alt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import importlib  # noqa: E402

from analysis import hot_events  # noqa: E402

hot_events = importlib.reload(hot_events)       # streamlit reruns the page but keeps imported modules: a change to the scoring shows without a restart
from dashboard import common, data  # noqa: E402
from dashboard.common import GROUP_LABELS, q  # noqa: E402

SPIKE_Z = 1.5                                  # proposal: a volume spike is a Reddit Volume Z-score above 1.5 (the sidebar counts the texts instead)

HORIZONS = ("1h", "2h", "3h", "6h", "12h")
MIN_N = 1                                   # no minimum n: a rate needs one signal; a symbol marks n < 30 (WARN_N)
WARN_N = 30
TARGETS = [("log_return", "Current Return"), *[("future_return_" + h, h) for h in HORIZONS]]
NAMES = {"log_return": "ราคาชั่วโมงเดียวกัน (Current Return %)", **{"future_return_" + h: "ราคาหลัง %s ชั่วโมง (%%)" % h[:-1] for h in HORIZONS}}

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
state = st.session_state
z_min, v_min, s_min = 0.0, 0, 0.0                                                 # no filter before the score: the score decides what is a signal (a volume spike stays "Z > 1.5" of the proposal)
found = q("market_signals", start, end, tuple(tickers), tuple(statuses), z_min, s_min, tuple(communities), model, tuple(content_types), v_min, SPIKE_Z)      # every hour of the market x every asset with a price bar

bars = q("price_series_for", tuple(tickers), start, end)[["ticker", "hour_utc", "normalized_atr", "volume"]].rename(columns={"volume": "trading_volume"})
found = found.merge(bars, on=["ticker", "hour_utc"], how="left")

# ---- the score of a signal: six measures, each with ONE threshold; the number of measures a row passes decides low / medium / high ----
# (EXTENSION: the proposal names the three levels, not how they are reached).  The KPIs, default thresholds / cuts and the scoring live in
# analysis/hot_events.py, shared with the forward check (scripts/hot_events_forward_check.py): only measures known in the hour itself or from the
# hours before it; no statistic of the whole history (Spearman, Win Rate ...) is scored (look-ahead): those stay as columns beside the signal.
LEVELS, METRICS, DEFAULT_CUTS = hot_events.LEVELS, hot_events.METRICS, hot_events.DEFAULT_CUTS_PCT


def PASS_RATE(m, threshold):
    """Share of every asset x hour that passes the threshold of one KPI (the data of the page, before the asset picker): shown in its tooltip."""
    return float((pd.to_numeric(hot_events.SOURCE[m](found), errors="coerce") > threshold).mean()) if len(found) else float("nan")


def reset_scoring():
    for m, _, threshold, _ in METRICS:
        state["hs_%s_t" % m] = threshold
        state["hs_%s_w" % m] = hot_events.DEFAULT_WEIGHTS[m]
    for lv in LEVELS:
        state["hs_cut_" + lv] = DEFAULT_CUTS[lv]


for m, _, threshold, _ in METRICS:
    state.setdefault("hs_%s_t" % m, threshold)
    state.setdefault("hs_%s_w" % m, hot_events.DEFAULT_WEIGHTS[m])
for lv in LEVELS:
    state.setdefault("hs_cut_" + lv, DEFAULT_CUTS[lv])

common.block("ตั้งค่าเกณฑ์และระดับของสัญญาณ (low / medium / high)",
             "ใช้กำหนดเกณฑ์ของตัวชี้วัดและระดับของสัญญาณ เพื่อคัดชั่วโมง × สินทรัพย์ที่ควรติดตาม",
             how="คะแนน (%) = ผลรวมน้ำหนัก (%) ของตัวชี้วัดที่แต่ละแถว (ชั่วโมง × สินทรัพย์) ผ่านเกณฑ์ น้ำหนักรวมของตัวชี้วัดที่ใช้ = 100% ยิ่งคะแนนสูง ระดับยิ่งสูง")
with st.expander("เกณฑ์ และระดับ", expanded=False):
    with st.form("h_score_form", border=False):                                       # nothing below changes until the button Apply is pressed
        head = st.columns([6, 2, 2])
        head[0].markdown("**ตัวชี้วัด**")
        head[1].markdown("**เกณฑ์ (ผ่านเมื่อค่า >)**")
        head[2].markdown("**น้ำหนัก (%)**")
        for m, label, _, step in METRICS:
            row = st.columns([6, 2, 2])
            what, origin = hot_events.ABOUT[m]
            t_now = state.get("hs_%s_t" % m)
            passed = "" if t_now is None else "  \nผ่านเกณฑ์ในข้อมูลจริง: %.1f%% ของชั่วโมง × สินทรัพย์" % (100.0 * PASS_RATE(m, t_now))
            row[0].markdown(label, help="**คืออะไร:** %s  \n**ที่มาของเกณฑ์:** %s%s" % (what, origin, passed))
            row[1].number_input(label + " เกณฑ์", value=None, step=step, key="hs_%s_t" % m, placeholder="ไม่ใช้", label_visibility="collapsed")
            row[2].number_input(label + " น้ำหนัก (%)", min_value=0.0, max_value=100.0, step=1.0, key="hs_%s_w" % m, label_visibility="collapsed")
        st.markdown("**ระดับ** คะแนน (%) ตั้งแต่:")
        cuts_row = st.columns(3)
        for col, lv in zip(cuts_row, LEVELS):
            col.number_input(lv + " (%)", min_value=1.0, max_value=100.0, step=1.0, key="hs_cut_" + lv)
        apply_col, reset_col, _ = st.columns([2, 2, 6])
        apply_col.form_submit_button("ใช้เกณฑ์นี้ (Apply)", type="primary", key="h_apply")
        reset_col.form_submit_button("คืนค่าเริ่มต้น", on_click=reset_scoring, key="h_level_reset")

with common.sticky_bar("h_bar"):                                         # the pickers the whole page follows stay in reach while it scrolls
    time_col, asset_col = st.columns([2, 3])
    fwd_h = time_col.radio("ช่วงเวลา", list(hot_events.HORIZONS), horizontal=True, key="h_fwd_h", index=0,
                           format_func=lambda h: "Current Return" if h == "now" else h)
    level_pick = time_col.radio("ระดับ", ["all", *LEVELS], horizontal=True, key="h_levels")
    tickers_shown = asset_col.multiselect("สินทรัพย์", sorted(found.ticker.unique()), key="h_tickers", placeholder="ทั้งหมด")   # empty = every asset
levels_shown = list(LEVELS) if level_pick == "all" else [level_pick]
if tickers_shown:
    found = found[found.ticker.isin(tickers_shown)]
horizon, column = "Current Return", "log_return"                       # the statistics beside a signal are those of the same hour (Current Return); no horizon to pick
rules = {m: float(state["hs_%s_t" % m]) for m, *_ in METRICS if state.get("hs_%s_t" % m) is not None}
cuts = {lv: float(state["hs_cut_" + lv]) for lv in LEVELS}
weights = {m: float(state["hs_%s_w" % m]) for m, *_ in METRICS}
if abs(sum(weights.values()) - 100.0) > 0.01:
    st.error("น้ำหนักของตัวชี้วัดรวมกันต้องเท่ากับ 100%% (ตอนนี้รวมได้ %.1f%%) โปรดแก้ในกล่อง \"เกณฑ์ และระดับ\" แล้วกด Apply" % sum(weights.values()))
    st.stop()
if not rules:
    st.info("ต้องใช้ตัวชี้วัดอย่างน้อย 1 ตัว (มีเกณฑ์)")
    st.stop()
if not cuts["low"] <= cuts["medium"] <= cuts["high"]:
    st.info("คะแนน (%) ของระดับต้องเรียงจากน้อยไปมาก: low ≤ medium ≤ high")
    st.stop()
GREEN, RED = "color: #1a9850; font-weight: 600", "color: #d73027; font-weight: 600"


def listed_for(basis, horizon=horizon, column=column):
    """The signals of one tab with their score and level: every (asset x hour) the sidebar lets through, joined with the statistics of its asset (looked up
    from the system 7.4: the numbers of the Statistical Analysis page with the same filters) for `horizon`, kept when it can be judged (a move of `column`
    and a direction) and its points reach at least the level low.  -> (rows, win_table)."""
    stat74 = common.panel_stat("global", "all", tuple(tickers), start, end, tuple(communities), model, tuple(statuses), z_min, s_min, tuple(content_types), basis, v_min)
    win_table = pd.DataFrame({"ticker": stat74.ticker, "horizon": stat74.target.map(data.LOOKUP_HORIZONS), "n": stat74.win_n, "win_rate": stat74.winrate,
                              "rho": stat74.spearman_rho, "pearson": stat74.pearson_rho, "p": stat74.win_p, "p_bh": stat74.win_bh})
    pair = win_table[win_table.horizon == horizon].set_index("ticker")[["n", "win_rate", "rho", "pearson", "p", "p_bh"]].add_prefix("pair_")
    listed = found.join(pair, on="ticker")
    direction = listed.sentiment_mean if basis == "sentiment_mean" else listed.majority_final_status.map({"positive": 1.0, "negative": -1.0, "neutral": 0.0})
    listed = listed.assign(direction=direction)
    judged = listed[column].notna() & (listed[column] != 0) & listed.direction.notna() & (listed.direction != 0)
    listed = listed[judged]                                                    # only signals that can be judged (a price move and a direction), the ones the win rate counts
    score = hot_events.score_pct(listed, rules, weights)                              # the % of the KPIs the row passes; a missing value never passes
    level = hot_events.level(score, cuts)
    listed = listed.assign(score=score, level_name=level)
    return listed[level != ""], win_table                                       # a signal below the level low is dropped


listed_score, _ = listed_for("sentiment_mean")
if found.empty:
    st.info("ไม่พบชั่วโมงตามตัวกรองด้านซ้ายในช่วงที่เลือก โปรดลดเกณฑ์หรือขยายช่วงเวลา")
    st.stop()
if listed_score.empty:
    st.info("ไม่มีสัญญาณที่ได้คะแนนถึงระดับ low โปรดลดเกณฑ์หรือขยายช่วงเวลา")
    st.stop()

# ---- 1b. how many asset x hours reach each level (the page counts; what the price did after is in scripts/hot_events_forward_check.py) --------------------------------
tab_horizon, tab_column = ("Current Return", "log_return") if fwd_h == "now" else (fwd_h, "future_return_" + fwd_h)   # the list below follows the picker
RET = "Current Return (%)" if fwd_h == "now" else "Return %s (%%)" % fwd_h
level_of = hot_events.level(hot_events.score_pct(found, rules, weights), cuts).replace("", "ไม่ถึง low")      # every asset x hour, scored with the thresholds and weights above
counts = level_of.value_counts()
summary = pd.DataFrame({"ระดับ": ["high", "medium", "low", "ไม่ถึง low"]})
summary["จำนวน"] = summary["ระดับ"].map(counts).fillna(0).astype(int)
summary["สัดส่วน (%)"] = (100.0 * summary["จำนวน"] / max(int(summary["จำนวน"].sum()), 1)).round(1)
summary.loc[len(summary)] = ["รวม", int(summary["จำนวน"].sum()), 100.0 if summary["จำนวน"].sum() else 0.0]
common.block("สรุปจำนวนสัญญาณตามระดับ", "ใช้ตรวจสอบว่ามีข้อมูลกี่รายการในแต่ละระดับ (high, medium, low และต่ำกว่า low)")
common.table(summary, hide_index=True, width="stretch")

# ---- 2. the list, with the statistics of its asset (looked up from the system 7.4) -------------------------------------------------------------
common.block("รายการสัญญาณที่ตรวจพบ (ล่าสุด 300 รายการ)",
             "ใช้ตรวจสอบชั่วโมง × สินทรัพย์ที่ผ่านเกณฑ์ พร้อมสถิติของสินทรัพย์นั้น (คลิกหัวคอลัมน์เพื่อเรียงลำดับ)",
             how="คะแนน % = สัดส่วนตัวชี้วัดที่ผ่านเกณฑ์ในชั่วโมงนั้น · Match/Opposite = ราคาในช่วงเวลาที่เลือกไปทางเดียวกับ/ตรงข้ามกับความรู้สึก, "
                 "n, Spearman, Pearson, Win Rate = สถิติของสินทรัพย์ทั้งช่วงข้อมูลจากระบบ 4, ★ = ผ่านการทดสอบหลังปรับ BH")


def signal_table(basis):
    """The list: `basis` = how the sentiment is read ('sentiment_mean' = the score).  One table, no majority tab and no majority columns
    (user request 2026-11-14)."""
    listed, _ = listed_for(basis, tab_horizon, tab_column)
    listed = listed[listed.level_name.isin(levels_shown)]
    if listed.empty:
        st.info("ไม่มีสัญญาณในระดับที่เลือกที่ตัดสินได้ ในแท็บนี้ โปรดเลือกระดับเพิ่มหรือลดเกณฑ์")
        return
    view = listed.head(300)
    follow = np.sign(view.direction) * np.sign(view[tab_column])               # +1 the price went with the sentiment, -1 against
    OUTCOME = "Price vs sentiment"
    SENT = "ความรู้สึกเฉลี่ย (ทั้งตลาด)" if basis == "sentiment_mean" else "ทิศทางส่วนใหญ่ (ทั้งตลาด)"
    shown = pd.DataFrame({
        "เวลา (UTC)": pd.to_datetime(view.hour_utc, unit="s", utc=True).dt.strftime("%Y-%m-%d %H:%M"),
        "สินทรัพย์": view.ticker, "กลุ่ม": view.big_group.map(GROUP_LABELS), "ระดับ": view.level_name, "คะแนน (%)": view.score,
        "Ticker Mention Count": view.mentions, "Reddit Volume (ทั้งตลาด)": view.market_volume, RET: view[tab_column],
        "Trading Volume (ของสินทรัพย์)": view.trading_volume,
        SENT: view.sentiment_mean if basis == "sentiment_mean" else view.majority_final_status,
        OUTCOME: np.where(follow > 0, "Match", np.where(follow < 0, "Opposite", "-")),
        "n ของสินทรัพย์ (จำนวนชั่วโมงที่นับ)": view.pair_n, "Spearman ρ ของสินทรัพย์": view.pair_rho, "Pearson ρ ของสินทรัพย์": view.pair_pearson,
        "Win Rate ของสินทรัพย์ (%)": view.pair_win_rate, "p ของ Win Rate (ดิบ)": view.pair_p, "p ของ Win Rate (ปรับ BH)": view.pair_p_bh,
        "นัยสำคัญหลังปรับ": np.where(view.pair_p_bh < 0.05, "★", "")})
    colour = lambda col: [GREEN if v == "Match" else (RED if v == "Opposite" else "") for v in col]
    numbers = {"คะแนน (%)": "{:.0f}", "Ticker Mention Count": "{:,.0f}", "Reddit Volume (ทั้งตลาด)": "{:,.0f}", "Trading Volume (ของสินทรัพย์)": "{:,.0f}", RET: "{:+.3f}",
               "ความรู้สึกเฉลี่ย (ทั้งตลาด)": "{:.3f}", "n ของสินทรัพย์ (จำนวนชั่วโมงที่นับ)": "{:,.0f}", "Spearman ρ ของสินทรัพย์": "{:.3f}", "Pearson ρ ของสินทรัพย์": "{:.3f}",
               "Win Rate ของสินทรัพย์ (%)": "{:.1f}", "p ของ Win Rate (ดิบ)": "{:.3f}", "p ของ Win Rate (ปรับ BH)": "{:.3f}"}
    styled = shown.style.apply(colour, subset=[OUTCOME]).format({k: v for k, v in numbers.items() if k in shown.columns}, na_rep="-")
    # a header of the grid cannot take two lines (the grid draws one line and cuts the rest), so the headers are short and every column has a width and a tooltip with the full
    # name: the whole table is readable on one screen without scrolling sideways
    HEAD = {"เวลา (UTC)": ("เวลา (UTC)", 125, "เวลาต้นชั่วโมงที่ข้อความโพสต์ (UTC)"), "สินทรัพย์": ("สินทรัพย์", 90, None), "กลุ่ม": ("กลุ่ม", 75, None),
            "ระดับ": ("ระดับ", 70, "ระดับจากคะแนน (%) ของตัวชี้วัดที่ผ่านเกณฑ์"), "คะแนน (%)": ("คะแนน %", 75, "คะแนน (%) = ตัวชี้วัดที่ผ่านเกณฑ์ในชั่วโมงนั้น ÷ ตัวชี้วัดที่ใช้ × 100"),
            "Ticker Mention Count": ("Mention", 70, "Ticker Mention Count: จำนวนข้อความที่พูดถึงสินทรัพย์นี้ในชั่วโมงนั้น"),
            "Reddit Volume (ทั้งตลาด)": ("Reddit Vol", 85, "Reddit Volume: จำนวนโพสต์และคอมเมนต์ของทั้งตลาดในชั่วโมงนั้น"),
            RET: ("Cur. Return %" if fwd_h == "now" else "Return %s %%" % fwd_h, 105,
                  "ผลตอบแทนของสินทรัพย์ในชั่วโมงเดียวกัน (ln)" if fwd_h == "now" else "ผลตอบแทนของสินทรัพย์ %s หลังชั่วโมงนั้น (ln)" % fwd_h),
            "Trading Volume (ของสินทรัพย์)": ("Trading Vol", 105, "Trading Volume: ปริมาณซื้อขายของสินทรัพย์ในชั่วโมงนั้น (0 = ไม่มีข้อมูล)"),
            SENT: ("ความรู้สึก" if basis == "sentiment_mean" else "ทิศทาง", 90, "ความรู้สึกเฉลี่ย (หรือทิศทางส่วนใหญ่) ของข้อความทั้งตลาดในชั่วโมงนั้น"),
            OUTCOME: ("Price vs sent.", 100, "Match = ราคา (ตามช่วงเวลาที่เลือก) ไปทางเดียวกับความรู้สึก, Opposite = ทิศทางตรงข้าม"),
            "n ของสินทรัพย์ (จำนวนชั่วโมงที่นับ)": ("n", 60, "n ของสินทรัพย์: จำนวนชั่วโมงที่นับใน Win Rate ทั้งช่วงข้อมูล"),
            "Spearman ρ ของสินทรัพย์": ("Spearman", 85, "Spearman ρ ของสินทรัพย์ (ระบบ 7.4)"), "Pearson ρ ของสินทรัพย์": ("Pearson", 80, "Pearson ρ ของสินทรัพย์ (ระบบ 7.4)"),
            "Win Rate ของสินทรัพย์ (%)": ("Win Rate %", 90, "Win Rate ของสินทรัพย์ (%) (ระบบ 7.4)"), "p ของ Win Rate (ดิบ)": ("p ดิบ", 65, "p-value ของ Win Rate (Binomial เทียบ 50%)"),
            "p ของ Win Rate (ปรับ BH)": ("p ปรับ", 65, "p-value ของ Win Rate ที่ปรับด้วย Benjamini-Hochberg"),
            "นัยสำคัญหลังปรับ": ("นัยสำคัญ", 80, "★ = p ปรับ BH ต่ำกว่า 0.05")}
    config = {name: st.column_config.Column(label=label, width=width, help=tip) for name, (label, width, tip) in HEAD.items() if name in shown.columns}
    st.dataframe(styled, hide_index=True, width="stretch", height=380, column_config=config)          # the numbers stay numbers, so a click on a header sorts them right


signal_table("sentiment_mean")

