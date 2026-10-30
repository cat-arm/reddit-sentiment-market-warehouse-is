"""Dashboard 7.5-3  Statistical Analysis  (EXTENSION: deeper analysis of the relation between Reddit sentiment and returns).

Static part (full-sample results of the analyses of proposal 7.4, stored in `analysis_results`; they follow the TICKER filter
only, not the time / community / majority filters):
  * A1 Pearson and Spearman correlation + p-value (raw and Benjamini-Hochberg) per ticker and horizon
  * A2 Historical Win Rate + Binomial p-value per ticker and horizon
  * A3 Logistic Regression: AUC with the spread over the 5 time-ordered folds, coefficients, importance of the variable groups
Live part (follows every filter of the sidebar, computed from the texts of the chosen communities and model):
  * who moves first (Spearman between the Sentiment Score and the return k hours away), sentiment by prior return,
  * DimDetectionConfig drill-down: the hours that meet the Z-score / Sentiment thresholds and what the price did next.
Descriptive only: hourly data are autocorrelated and the horizons overlap, so p-values are not exact; no investment advice.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import altair as alt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard import common, data  # noqa: E402
from dashboard.common import GROUP_LABELS, q  # noqa: E402

common.setup("Statistical Analysis: วิเคราะห์เชิงลึก", "🔬")
_, start, end, _ = common.sidebar(multi=True, sentiment=True, detection="signals", majority=True)
tickers = common.selected_tickers()
communities = common.selected_communities()
statuses = common.selected_statuses()
if not tickers or not communities or not statuses:
    common.nothing_selected(["Spearman ที่ p < 0.05", "ผ่านการปรับ Benjamini-Hochberg", "Win Rate ที่ p < 0.05", "Logistic AUC เฉลี่ย"],
                            "ไม่ได้เลือกหลักทรัพย์ ชุมชน หรือประเภทความรู้สึกส่วนใหญ่ จึงไม่มีข้อมูลแสดง")
names = dict(zip(q("tickers").ticker, q("tickers").name))
universe = q("tickers")
ORDER = list(universe[universe.ticker.isin(tickers)].sort_values(["big_group", "ticker"]).ticker)
HORIZON_ORDER = ["Current Return", "1h", "2h", "3h", "6h", "12h"]

corr = q("correlation_results")
corr = corr[corr.ticker.isin(tickers)].assign(ช่วง=lambda d: d.horizon.map(data.HORIZON_LABELS))
win = q("winrate_results")
win = win[win.ticker.isin(tickers)].assign(ช่วง=lambda d: d.horizon.map(data.HORIZON_LABELS))
logi = q("logistic_results")

# ---- KPI cards first: how many of the tests of the stored analyses are significant (future horizons only) ----------------
future_corr = corr[(corr.method == "spearman") & (corr.horizon != "log_return")]
n_sig, n_tests = data.significant_share(future_corr)
n_bh, n_bh_tests = data.significant_share(future_corr, "p_bh")
w_sig, w_tests = data.significant_share(win)
auc = logi[(logi.panel == "panel_Ticker") & (logi.level == "all") & (logi.metric == "auc") & (logi.status == "ok")]
common.kpi_cards([
    ("Spearman ที่ p < 0.05", "%d / %d" % (n_sig, n_tests), "คู่ (สินทรัพย์ × Horizon) ที่ Spearman ของความรู้สึกกับผลตอบแทนอนาคตมี p-value < 0.05 (ก่อนปรับค่า)"),
    ("ผ่านการปรับ Benjamini-Hochberg", "%d / %d" % (n_bh, n_bh_tests), "เมื่อปรับ p-value ตามจำนวนการทดสอบที่ทำพร้อมกัน (ส่วนขยาย)"),
    ("Win Rate ที่ p < 0.05", "%d / %d" % (w_sig, w_tests), "คู่ (สินทรัพย์ × Horizon) ที่ Win Rate ต่างจากการเดา 50% อย่างมีนัยสำคัญ (Binomial)"),
    ("Logistic AUC เฉลี่ย", "n/a" if auc.empty else "{:.3f}".format(auc.value.mean()), "AUC เฉลี่ยของทุก Horizon (ทุกสินทรัพย์รวมกัน); 0.5 = เดา")])
st.caption("การ์ดและส่วน A1–A3 เป็นผลวิเคราะห์เต็มช่วงข้อมูล ตามตัวกรองหลักทรัพย์เท่านั้น (ไม่ตามเวลา ชุมชน หรือประเภทส่วนใหญ่); "
           "ส่วนล่างของหน้าตามตัวกรองทุกอัน  ค่า p-value เป็นเชิงพรรณนา เพราะข้อมูลรายชั่วโมงเกี่ยวเนื่องกันและกรอบเวลาซ้อนทับกัน")


def heatmap(df, value, p_col, title, domain, scheme, fmt):
    """Ticker x horizon heat map; a star marks p < 0.05; empty cells = not enough data (never 0)."""
    d = df.assign(ดาว=np.where(df[p_col] < 0.05, "★", ""))
    height = max(120, 18 * d.ticker.nunique() + 40)
    base = alt.Chart(d).encode(x=alt.X("ช่วง:O", sort=HORIZON_ORDER, title=None, axis=alt.Axis(labelAngle=0, orient="top")),
                               y=alt.Y("ticker:N", sort=ORDER, title=None))
    rect = base.mark_rect().transform_filter("isValid(datum.%s)" % value).encode(
        color=alt.Color(value + ":Q", title=title, scale=alt.Scale(domain=domain, scheme=scheme)),
        tooltip=["ticker", "ช่วง", alt.Tooltip(value + ":Q", title=title, format=fmt), alt.Tooltip(p_col + ":Q", title="p-value", format=".4f"),
                 alt.Tooltip("n:Q", title="จำนวนตัวอย่าง", format=",")])
    star = base.mark_text(fontSize=11, color="#222222").encode(text="ดาว:N")
    return (rect + star).properties(height=height)


# ---- A1 correlation -------------------------------------------------------------------------------------------------
st.subheader("A1 ความสัมพันธ์ของความรู้สึกกับผลตอบแทน: Pearson และ Spearman พร้อม p-value")
METHODS = {"Spearman (จัดอันดับ ทนค่าสุดโต่ง)": "spearman", "Pearson (เชิงเส้น)": "pearson"}
method_pick = st.radio("วิธี", list(METHODS), horizontal=True, key="a_method", label_visibility="collapsed")
method = METHODS[method_pick]
cm = corr[corr.method == method]
if cm.rho.notna().sum() == 0:
    st.info("ไม่มีผลวิเคราะห์ของหลักทรัพย์ที่เลือก (ข้อมูลไม่พอ)")
else:
    st.altair_chart(heatmap(cm, "rho", "p_value", "ρ (%s)" % method, [-0.1, 0.1], "redblue", "+.3f"), width="stretch")
    st.caption("สี = ค่าสหสัมพันธ์ ρ (แดง ลบ, น้ำเงิน บวก; ช่วงสี ±0.1)  ★ = p-value < 0.05 (ก่อนปรับ)  ช่องว่าง = ข้อมูลน้อยกว่า 30 คู่  "
               "Current Return = ผลตอบแทนของชั่วโมงเดียวกัน (เกิดพร้อมกัน ไม่ใช่การทำนาย) ส่วน 1h–12h = ผลตอบแทนล่วงหน้า")
    pick = st.radio("ดูตารางของ", HORIZON_ORDER, index=1, horizontal=True, key="a_horizon", label_visibility="collapsed")
    at_pick = corr[corr.ช่วง == pick]
    parts = [at_pick[at_pick.method == m][["ticker", "big_group", "rho", "p_value"]].rename(
        columns={"rho": "%s ρ" % m.capitalize(), "p_value": "%s p-value" % m.capitalize()}) for m in ("spearman", "pearson")]
    bh = at_pick[at_pick.method == method][["ticker", "p_bh", "n"]]
    table = parts[0].merge(parts[1], on=["ticker", "big_group"], how="outer").merge(bh, on="ticker", how="left")
    table["สินทรัพย์"] = table.ticker.map(lambda s: "%s · %s" % (s, names.get(s, "")))
    table["กลุ่ม"] = table.big_group.map(GROUP_LABELS)
    table[method.capitalize() + " p (BH)"] = table.p_bh
    table["มีนัยสำคัญ (p<0.05)"] = np.where(table[method.capitalize() + " p-value"] < 0.05, "★", "")
    cols = ["สินทรัพย์", "กลุ่ม", "Spearman ρ", "Spearman p-value", "Pearson ρ", "Pearson p-value", method.capitalize() + " p (BH)", "n",
            "มีนัยสำคัญ (p<0.05)"]
    common.table(table.sort_values(method.capitalize() + " p-value")[cols].round(4), hide_index=True, width="stretch", height=420)
    st.caption("เรียงตาม p-value ของวิธีที่เลือก น้อยไปมาก  p (BH) = ปรับด้วย Benjamini-Hochberg ตามจำนวนสินทรัพย์ที่ทดสอบพร้อมกัน  "
               "ถ้าความรู้สึกมีผลจริง ρ ควรเบี่ยงจาก 0 มากกว่าการสุ่ม และ p ต่ำแม้หลังปรับ")

# ---- A2 win rate ----------------------------------------------------------------------------------------------------
st.subheader("A2 Historical Win Rate และ p-value")
if win.winrate.notna().sum() == 0:
    st.info("ไม่มีผล Win Rate ของหลักทรัพย์ที่เลือก")
else:
    st.altair_chart(heatmap(win, "winrate", "p_value", "Win Rate (%)", [40, 60], "redblue", ".1f"), width="stretch")
    st.caption("Win Rate = สัดส่วนชั่วโมงที่ทิศทางผลตอบแทนอนาคตตรงกับเครื่องหมายของความรู้สึก (50% = เดา)  ★ = Binomial p-value < 0.05")
    wp = st.radio("ดูตารางของ ", HORIZON_ORDER[1:], horizontal=True, key="a_win_horizon", label_visibility="collapsed")
    wt = win[win.ช่วง == wp].copy()
    wt["สินทรัพย์"] = wt.ticker.map(lambda s: "%s · %s" % (s, names.get(s, "")))
    wt["กลุ่ม"] = wt.big_group.map(GROUP_LABELS)
    wt["ต่างจากการเดา (จุด %)"] = wt.winrate - 50
    wt["มีนัยสำคัญ (p<0.05)"] = np.where(wt.p_value < 0.05, "★", "")
    common.table(wt.sort_values("p_value")[["สินทรัพย์", "กลุ่ม", "winrate", "baseline", "ต่างจากการเดา (จุด %)", "p_value", "n",
                                            "มีนัยสำคัญ (p<0.05)"]].rename(columns={"winrate": "Win Rate (%)", "baseline": "Baseline (%)",
                                                                                     "p_value": "p-value"}).round(4),
                 hide_index=True, width="stretch", height=420)
    st.caption("Baseline = สัดส่วนชั่วโมงที่ราคาขึ้นเฉยๆ ของสินทรัพย์นั้น (ถ้า Win Rate ไม่เกิน Baseline แปลว่าความรู้สึกไม่ช่วยอะไร)")

# ---- A3 logistic ----------------------------------------------------------------------------------------------------
st.subheader("A3 Logistic Regression: ความรู้สึกทำนายทิศทางราคา (ขึ้น/ลง) ได้ไหม")
lg = logi[logi.status == "ok"]
if lg.empty:
    st.info("ไม่มีผล Logistic")
else:
    st.write("AUC ของแต่ละ Horizon เทียบกับการเดาแบบสุ่ม (panel_baseline) แบ่งข้อมูลแบบ TimeSeriesSplit 5 ส่วน ห่าง 12 ชั่วโมง")
    ar = lg[(lg.metric.isin(["auc", "auc_std"])) & (lg.level == "all")]
    ar = ar.pivot_table(index=["panel", "horizon"], columns="metric", values="value", aggfunc="first").reset_index()
    ar["ชุดข้อมูล"] = ar.panel.map({"panel_Ticker": "ความรู้สึกจริง (6 กลุ่มตัวแปร)", "panel_baseline": "เดาแบบสุ่ม (เปรียบเทียบ)"})
    ar["ช่วง"] = ar.horizon.map(data.HORIZON_LABELS)
    ar["lo"], ar["hi"] = ar.auc - ar.auc_std, ar.auc + ar.auc_std
    base = alt.Chart(ar).encode(x=alt.X("ช่วง:O", sort=HORIZON_ORDER, title="Horizon", axis=alt.Axis(labelAngle=0)),
                                xOffset="ชุดข้อมูล:N")
    bars = base.mark_bar().encode(y=alt.Y("auc:Q", title="AUC (0.5 = เดา)", scale=alt.Scale(domain=[0.4, 0.6])),
                                  color=alt.Color("ชุดข้อมูล:N", scale=alt.Scale(range=["#1f77b4", "#9e9e9e"]), legend=alt.Legend(orient="top", title=None)),
                                  tooltip=["ชุดข้อมูล", "ช่วง", alt.Tooltip("auc:Q", format=".4f"), alt.Tooltip("auc_std:Q", title="ส่วนเบี่ยงเบนข้ามส่วน", format=".4f")])
    err = base.mark_rule(color="#222222").encode(y="lo:Q", y2="hi:Q")
    line = alt.Chart(alt.Data(values=[{"y": 0.5}])).mark_rule(strokeDash=[4, 4], color="gray").encode(y="y:Q")
    st.altair_chart(bars + err + line, width="stretch")
    st.caption("เส้นประ = AUC 0.5 (ทำนายไม่ได้ดีกว่าการเดา)  เส้นดำ = ± ส่วนเบี่ยงเบนมาตรฐานของ AUC ข้าม 5 ส่วน  "
               "AUC ใกล้ 0.5 หรือไม่ต่างจากแท่งเทา แปลว่าตัวแปรความรู้สึกไม่ช่วยทำนาย")
    levels = lg[(lg.metric == "auc") & (lg.panel == "panel_Ticker")].copy()
    levels["ระดับ"] = np.where(levels.level == "all", "ทุกสินทรัพย์รวมกัน", levels.big_group.map(GROUP_LABELS))
    levels["ช่วง"] = levels.horizon.map(data.HORIZON_LABELS)
    grid = levels.pivot_table(index="ระดับ", columns="ช่วง", values="value", aggfunc="first").reindex(columns=HORIZON_ORDER[1:])
    counts = levels.pivot_table(index="ระดับ", columns="ช่วง", values="n", aggfunc="first").reindex(columns=HORIZON_ORDER[1:])
    st.write("AUC แยกตามกลุ่มสินทรัพย์")
    common.table(grid.round(4).reset_index(), hide_index=True, width="stretch")
    st.caption("จำนวนตัวอย่างต่อช่อง: " + ", ".join("%s/%s=%s" % (i, c, "{:,}".format(int(counts.loc[i, c]))) for i in counts.index
                                                  for c in counts.columns if pd.notna(counts.loc[i, c])))
    lh = st.radio("Horizon ที่ดูสัมประสิทธิ์", HORIZON_ORDER[1:], horizontal=True, key="a_log_horizon")
    hz = {v: k for k, v in data.HORIZON_LABELS.items()}[lh]
    one = lg[(lg.panel == "panel_Ticker") & (lg.level == "all") & (lg.horizon == hz)]
    coefs = one[one.metric.str.startswith("coef:")].assign(ตัวแปร=lambda d: d.metric.str[5:])
    imp = one[one.metric.str.startswith("group_importance:")].assign(กลุ่มตัวแปร=lambda d: d.metric.str[17:])
    if not coefs.empty:
        cb = alt.Chart(coefs).mark_bar().encode(
            y=alt.Y("ตัวแปร:N", sort="-x", title=None), x=alt.X("value:Q", title="สัมประสิทธิ์มาตรฐาน (เฉลี่ยข้าม 5 ส่วน)"),
            color=alt.condition(alt.datum.value > 0, alt.value("#2ca02c"), alt.value("#d62728")),
            tooltip=["ตัวแปร", alt.Tooltip("value:Q", title="สัมประสิทธิ์", format="+.4f")]).properties(height=330)
        st.altair_chart(cb, width="stretch")
        st.caption("สัมประสิทธิ์บวก = ตัวแปรสูงขึ้นแล้วโอกาสที่ราคาขึ้นสูงขึ้น (เขียว) ลบ = ตรงข้าม (แดง) ค่าที่ใกล้ 0 มากแปลว่าไม่มีอิทธิพล  "
                   "ขนาดเทียบกันได้เพราะปรับตัวแปรเป็นหน่วยมาตรฐานแล้ว (StandardScaler ใช้เฉพาะชุดฝึก)")
    if not imp.empty:
        ib = alt.Chart(imp).mark_bar(color="#1f77b4").encode(
            y=alt.Y("กลุ่มตัวแปร:N", sort="-x", title=None), x=alt.X("value:Q", title="ความสำคัญของกลุ่ม (ผลรวม |สัมประสิทธิ์|)"),
            tooltip=["กลุ่มตัวแปร", alt.Tooltip("value:Q", title="ความสำคัญ", format=".4f")]).properties(height=200)
        st.altair_chart(ib, width="stretch")
        st.caption("กลุ่มตัวแปร: Level, Direction, Vote, Volume, Lag, Momentum ตามที่ proposal กำหนด  กลุ่มที่แท่งยาวกว่ามีอิทธิพลต่อโมเดลมากกว่า "
                   "แต่ถ้า AUC ใกล้ 0.5 ก็คือโมเดลโดยรวมยังทำนายไม่ได้")

# ---- live part: follows every filter of the sidebar ---------------------------------------------------------------------
st.subheader("ส่วนล่าง: ตามตัวกรองทุกอันที่แถบด้านซ้าย")
prices = q("price_series_for", tickers, start, end)
sent = q("sentiment_hourly", tickers, start, end, communities, common.selected_model())
if prices.empty:
    st.info("ไม่มีข้อมูลราคาของหลักทรัพย์ที่เลือกในช่วงนี้ (ตลาดอาจปิด)")
    st.stop()
per_ticker = data.sentiment_frame(sent, start, end)

# ---- who moves first?  the same ticker-hours as above, now looking back as well as forward
st.subheader("ใครขยับก่อนกัน: ความรู้สึก หรือ ราคา")
timing = per_ticker.rename(columns={"series": "ticker"})[["ticker", "hour_utc", "sentiment_mean", "majority"]]
timing = timing[timing.majority.isin(statuses)].merge(prices[["ticker", "hour_utc", "log_return"]], on=["ticker", "hour_utc"], how="left")
lags = data.lag_correlation(timing)
if lags.rho.notna().sum() == 0:
    st.info("ตัวอย่างน้อยเกินไปสำหรับวัดความสัมพันธ์ข้ามเวลา")
else:
    lags["ช่วงเวลา"] = lags.lag.map(lambda k: "ชั่วโมงเดียวกัน" if k == 0 else ("ราคาก่อน %d ชม." % -k if k < 0 else "ราคาหลัง %d ชม." % k))
    lags["ฝั่ง"] = lags.lag.map(lambda k: "ราคาขยับก่อนข้อความ" if k < 0 else ("ชั่วโมงเดียวกัน" if k == 0 else "ราคาขยับหลังข้อความ"))
    base = alt.Chart(lags).encode(x=alt.X("lag:O", title="ผลตอบแทนของชั่วโมงที่ห่างจากชั่วโมงที่มีข้อความกี่ชั่วโมง (ลบ = ก่อนมีข้อความ, บวก = หลังมีข้อความ)",
                                          axis=alt.Axis(labelAngle=0)))
    bars = base.mark_bar().encode(
        y=alt.Y("rho:Q", title="Spearman ρ (ความรู้สึก vs ผลตอบแทน)"),
        color=alt.Color("ฝั่ง:N", scale=alt.Scale(domain=["ราคาขยับก่อนข้อความ", "ชั่วโมงเดียวกัน", "ราคาขยับหลังข้อความ"],
                                                  range=["#d62728", "#7f7f7f", "#1f77b4"]), legend=alt.Legend(orient="top", title=None)),
        tooltip=["ช่วงเวลา", alt.Tooltip("rho:Q", title="Spearman ρ", format="+.3f"), alt.Tooltip("n:Q", title="จำนวนตัวอย่าง", format=","),
                 alt.Tooltip("ci_lo:Q", title="ช่วงเชื่อมั่น 95% ล่าง", format="+.3f"), alt.Tooltip("ci_hi:Q", title="ช่วงเชื่อมั่น 95% บน", format="+.3f")])
    errors = base.mark_rule(color="#222222", strokeWidth=2).encode(y="ci_lo:Q", y2="ci_hi:Q")
    zero = alt.Chart(alt.Data(values=[{"y": 0}])).mark_rule(color="#555555").encode(y="y:Q")
    st.altair_chart(bars + errors + zero, width="stretch")
    st.caption("วิธีอ่าน: แต่ละแท่งคือความสัมพันธ์ระหว่าง Sentiment Score ของชั่วโมงที่มีข้อความ กับผลตอบแทนรายชั่วโมงที่ห่างไปกี่ชั่วโมง "
               "ถ้าราคาขยับก่อนแล้วคนค่อยโพสต์ แท่งสีแดง (ฝั่งซ้าย) จะสูงกว่าสีน้ำเงิน ถ้าความรู้สึกนำราคา แท่งสีน้ำเงิน (ฝั่งขวา) จะสูงกว่า "
               "เส้นดำ = ช่วงเชื่อมั่น 95% ถ้าคร่อมศูนย์ แปลว่าแยกจากไม่มีความสัมพันธ์ไม่ได้")

st.subheader("ราคาขึ้นหรือลงมาก่อน แล้วความรู้สึกเป็นอย่างไร")
PAST = {"%d ชั่วโมงก่อนหน้า" % h: h for h in (1, 2, 3, 6, 12)}              # the horizons of the proposal (1 / 2 / 3 / 6 / 12 hours)
st.session_state.setdefault("s_past_hours", "3 ชั่วโมงก่อนหน้า")
past_pick = st.radio("ดูผลตอบแทน", list(PAST), horizontal=True, key="s_past_hours", label_visibility="collapsed")
timing = timing.assign(past=data.past_return(timing, PAST[past_pick]))
rb = data.return_buckets(timing, "past")
if rb.empty:
    st.info("ตัวอย่างน้อยเกินไปสำหรับแบ่งกลุ่มตามผลตอบแทนก่อนหน้า (ต้องมีอย่างน้อย 50 ticker-ชั่วโมงที่มีทั้งข้อความและราคาก่อนหน้า)")
else:
    price_levels = ["ตกแรงสุด", "ตกเล็กน้อย", "ทรงตัว", "ขึ้นเล็กน้อย", "ขึ้นแรงสุด"]
    rb["ระดับราคา"] = [price_levels[int(b)] if len(rb) == 5 else "กลุ่ม %d" % (int(b) + 1) for b in rb.bucket]
    rb["ป้าย"] = rb.apply(lambda r: "%s (%+.2f%% ถึง %+.2f%%)" % (r["ระดับราคา"], r.lo, r.hi), axis=1)
    base = alt.Chart(rb).encode(x=alt.X("ป้าย:N", sort=list(rb["ป้าย"]), axis=alt.Axis(labelAngle=0, labelLimit=200),
                                        title="ผลตอบแทนก่อนชั่วโมงที่มีข้อความ (แบ่ง 5 กลุ่มเท่าๆ กัน จากตกแรงสุดไปขึ้นแรงสุด)"))
    bars = base.mark_bar(color="#1f77b4").encode(
        y=alt.Y("mean:Q", title="Sentiment Score เฉลี่ย"),
        tooltip=["ระดับราคา", alt.Tooltip("mean_return:Q", title="ผลตอบแทนก่อนหน้าเฉลี่ย (%)", format="+.3f"),
                 alt.Tooltip("n:Q", title="จำนวนตัวอย่าง", format=","), alt.Tooltip("mean:Q", title="Sentiment Score เฉลี่ย", format="+.4f"),
                 alt.Tooltip("ci_lo:Q", title="ช่วงเชื่อมั่น 95% ล่าง", format="+.4f"), alt.Tooltip("ci_hi:Q", title="ช่วงเชื่อมั่น 95% บน", format="+.4f")])
    errors = base.mark_rule(color="#222222", strokeWidth=2).encode(y="ci_lo:Q", y2="ci_hi:Q")
    zero = alt.Chart(alt.Data(values=[{"y": 0}])).mark_rule(color="#555555").encode(y="y:Q")
    st.altair_chart(bars + errors + zero, width="stretch")
    st.caption("วิธีอ่าน: แบ่ง ticker-ชั่วโมงที่มีข้อความเป็น 5 กลุ่มเท่าๆ กันตามผลตอบแทนของราคาก่อนชั่วโมงนั้น แล้วดู Sentiment Score เฉลี่ยของแต่ละกลุ่ม "
               "ถ้า \"ราคาตก คนก็กลัว\" แท่งซ้าย (ตกแรงสุด) ควรต่ำกว่าแท่งขวา (ขึ้นแรงสุด) เส้นดำ = ช่วงเชื่อมั่น 95%")

# ---- DimDetectionConfig drill-down: the hours that meet the thresholds of the sidebar, and what the price did next
z_th = st.session_state.get("s_z", 1.5)
s_th = st.session_state.get("s_s", 0.30)
horizon = st.session_state.get("s_h", common.data.HORIZONS[0])
st.subheader("ชั่วโมงที่เข้าเงื่อนไขตรวจจับ (Z-score > %.1f และ |Sentiment| ≥ %.2f) ราคาเป็นอย่างไรต่อ %s" % (z_th, s_th, horizon))
hours = per_ticker.rename(columns={"series": "ticker"})[["ticker", "hour_utc", "texts", "sentiment_mean", "zscore", "majority"]]
hours = hours[hours.majority.isin(statuses)].merge(prices[["ticker", "hour_utc", "future_return_" + horizon]], on=["ticker", "hour_utc"])
col = "future_return_" + horizon
hit = data.signal_hours(hours, z_th, s_th)
if hit.empty:
    st.info("ไม่พบชั่วโมงที่เข้าเงื่อนไขในช่วงที่เลือก ลองลดเกณฑ์ Z-score หรือ Sentiment Threshold ที่แถบด้านซ้าย")
else:
    rs = data.return_by_signal(hours, col, z_th, s_th)
    rs["กลุ่ม"] = rs.group.map({"signal_positive": "สัญญาณบวก", "signal_negative": "สัญญาณลบ", "all_hours": "ทุกชั่วโมงที่มีข้อความ (เทียบ)"})
    rs["ป้าย"] = ["%s (n=%s)" % (g, "{:,}".format(n)) for g, n in zip(rs["กลุ่ม"], rs.n)]
    base = alt.Chart(rs).encode(x=alt.X("ป้าย:N", sort=list(rs["ป้าย"]), axis=alt.Axis(labelAngle=0, labelLimit=240),
                                        title="ชนิดของชั่วโมง (n = จำนวน ticker-ชั่วโมงที่มีผลตอบแทน %s)" % horizon))
    bars = base.mark_bar(color="#1f77b4").encode(
        y=alt.Y("mean:Q", title="ผลตอบแทนล่วงหน้า %s เฉลี่ย (%%)" % horizon),
        tooltip=["กลุ่ม", alt.Tooltip("n:Q", title="จำนวนตัวอย่าง", format=","), alt.Tooltip("mean:Q", title="ผลตอบแทนเฉลี่ย (%)", format="+.4f"),
                 alt.Tooltip("ci_lo:Q", title="ช่วงเชื่อมั่น 95% ล่าง", format="+.4f"), alt.Tooltip("ci_hi:Q", title="ช่วงเชื่อมั่น 95% บน", format="+.4f")])
    errors = base.mark_rule(color="#222222", strokeWidth=2).encode(y="ci_lo:Q", y2="ci_hi:Q")
    zero = alt.Chart(alt.Data(values=[{"y": 0}])).mark_rule(color="#555555").encode(y="y:Q")
    st.altair_chart(bars + errors + zero, width="stretch")
    st.caption("พบ %s ticker-ชั่วโมงที่ Reddit คึกคักผิดปกติ (Z-score เกินเกณฑ์) และความรู้สึกชัดเจน (|Sentiment Score| ถึงเกณฑ์)  \n"
               "เส้นดำ = ช่วงเชื่อมั่น 95%% ถ้าคร่อมศูนย์ แปลว่าแยกจากไม่มีการขยับไม่ได้ เทียบกับแท่งขวาสุดที่เป็นค่าเฉลี่ยของทุกชั่วโมง"
               % "{:,}".format(len(hit)))
    listing = hit.sort_values("hour_utc", ascending=False).head(300).copy()
    listing["เวลา (UTC)"] = pd.to_datetime(listing.hour_utc, unit="s", utc=True).dt.strftime("%Y-%m-%d %H:%M")
    listing["สินทรัพย์"] = listing.ticker.map(lambda s: "%s · %s" % (s, names.get(s, "")))
    common.table(listing[["เวลา (UTC)", "สินทรัพย์", "direction", "sentiment_mean", "texts", "zscore", col]].rename(
        columns={"direction": "ทิศทาง", "sentiment_mean": "Sentiment Score", "texts": "ข้อความ", "zscore": "Volume Z-score",
                 col: "ผลตอบแทนล่วงหน้า %s (%%)" % horizon}).round(3), hide_index=True, width="stretch", height=380)
    st.caption("รายการล่าสุดไม่เกิน 300 ชั่วโมง ผลตอบแทนว่าง = ไม่มีแท่งราคาที่ครบ %s หลังชั่วโมงนั้น" % horizon)

