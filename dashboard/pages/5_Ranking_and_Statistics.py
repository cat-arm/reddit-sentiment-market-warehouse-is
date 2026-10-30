"""Dashboard 7.5-2  Ranking and Statistics  (proposal 7.5 dashboard 2: Historical Win Rate, p-value, Future Return, Reddit Volume
Z-score of each asset, in every horizon; the figures a1_*, a2_*, a3_* of output/figures made interactive).

Same filters as Market and Sentiment (table 17): time, assets, sentiment source, the two thresholds, majority status.
The cards on top and the first four tabs are computed LIVE from the ticker-hours the filters leave (the texts of the chosen
communities and model, the hours inside the range that pass the thresholds and the majority status), so choosing two tickers
shows two tickers.  The fifth tab shows the stored results of the proposal's system 7.4 for each of its nine panels (the whole
data set: only the tickers follow the filter).  The regression section shows the stored Logistic Regression.
Descriptive history only: hourly data are autocorrelated and the horizons overlap, so p-values are not exact; no investment advice.
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

common.setup("Ranking and Statistics: จัดอันดับและสถิติความสัมพันธ์", "🏆")
_, start, end, _ = common.sidebar(multi=True, sentiment=True, detection="overview", majority=True)
tickers = common.selected_tickers()
communities = common.selected_communities()
statuses = common.selected_statuses()
CARDS = ["Historical Win Rate", "Spearman ที่ p < 0.05", "Logistic AUC เฉลี่ย", "Reddit Volume Z-score สูงสุด"]
if not tickers or not communities or not statuses:
    common.nothing_selected(CARDS, "ไม่ได้เลือกหลักทรัพย์ ชุมชน หรือประเภทความรู้สึกส่วนใหญ่ จึงไม่มีข้อมูลแสดง")
z_th = st.session_state.get("d_z", 0.0)
s_th = st.session_state.get("d_s", 0.0)
universe = q("tickers")
group_of = dict(zip(universe.ticker, universe.big_group))
names = dict(zip(universe.ticker, universe.name))
ORDER = list(universe[universe.ticker.isin(tickers)].sort_values(["big_group", "ticker"]).ticker)
TARGET_LABEL = {"log_return": "Current Return", "1h": "1h", "2h": "2h", "3h": "3h", "6h": "6h", "12h": "12h"}
MEASURES = {"Spearman": ("spearman_rho", "spearman_p", "spearman_bh", "+.3f", [-0.1, 0.1], "ρ"),
            "Pearson": ("pearson_rho", "pearson_p", "pearson_bh", "+.3f", [-0.1, 0.1], "ρ"),
            "Win Rate": ("winrate", "win_p", "win_bh", ".1f", [40, 60], "%")}

# ---- the ticker-hours that pass every filter, with the returns that follow ------------------------------------------------
prices = q("price_series_for", tickers, start, end)
sent = q("sentiment_hourly", tickers, start, end, communities, common.selected_model())
per_ticker = data.sentiment_frame(sent, start, end).rename(columns={"series": "ticker"})
keep = per_ticker.majority.isin(statuses) & data.threshold_mask(per_ticker, z_th, s_th) & per_ticker.sentiment_mean.notna()
samples = per_ticker[keep][["ticker", "hour_utc", "sentiment_mean", "zscore"]].merge(
    prices[["ticker", "hour_utc", "log_return", *["future_return_" + h for h in data.HORIZONS]]], on=["ticker", "hour_utc"])

logi = q("logistic_results")
logi_ok = logi[(logi.status == "ok") & (logi.panel == "panel_Ticker")]
groups_chosen = sorted({group_of[t] for t in tickers})
logi_scope = logi_ok[(logi_ok.level == "all") if len(groups_chosen) > 1 else ((logi_ok.level == "big_group") & (logi_ok.big_group == groups_chosen[0]))]
auc = logi_scope[logi_scope.metric == "auc"]

live_all = data.stat_table(samples) if not samples.empty else pd.DataFrame(columns=data.STAT_COLUMNS)
future = live_all[live_all.target != "log_return"]
n_sig, n_tests = data.significant_share(future, "spearman_p")
win_n = future.win_n.sum()
common.kpi_cards([
    ("Historical Win Rate", "n/a" if not win_n else "{:.1f}%".format(100.0 * future.win_hits.sum() / win_n),
     "สัดส่วนชั่วโมงที่ทิศทางของความรู้สึกตรงกับทิศทางผลตอบแทนอนาคต (ทุก Horizon รวมกัน ถ่วงด้วยจำนวนชั่วโมง) 50% = เดา"),
    ("Spearman ที่ p < 0.05", "%d / %d" % (n_sig, n_tests),
     "คู่ (สินทรัพย์ × Horizon) ที่ Spearman ของความรู้สึกกับผลตอบแทนอนาคตมี p-value < 0.05 (ก่อนปรับค่า)"),
    ("Logistic AUC เฉลี่ย", "n/a" if auc.empty else "{:.3f}".format(auc.value.mean()),
     "AUC เฉลี่ยทุก Horizon ของ Logistic Regression (ผลเต็มช่วงข้อมูล ของกลุ่มสินทรัพย์ที่เลือก) 0.5 = เดา"),
    ("Reddit Volume Z-score สูงสุด", common.money(samples.zscore.max()) if not samples.empty else "n/a",
     "เทียบ 24 ชั่วโมงก่อนหน้า ไม่รวมชั่วโมงปัจจุบัน (ชั่วโมงที่ผ่านตัวกรอง)")])
st.caption("การ์ดและ 4 แท็บแรกคำนวณสดจากชั่วโมงที่ผ่านตัวกรองทุกอัน  แท็บ \"ผลเต็มช่วง 7.4\" และส่วน Logistic เป็นผลวิเคราะห์เต็มช่วงข้อมูลที่เก็บไว้ ตามตัวกรองหลักทรัพย์เท่านั้น  "
           "ค่า p-value เป็นเชิงพรรณนา เพราะข้อมูลรายชั่วโมงเกี่ยวเนื่องกันและกรอบเวลาซ้อนทับกัน")


def heatmap(stat, measure):
    """Ticker x horizon heat map of one measure: the value and n in every cell, a star when the Benjamini-Hochberg p < 0.05."""
    value, p_col, bh_col, fmt, domain, unit = MEASURES[measure]
    d = stat[stat.ticker.isin(tickers) & (stat.target != "log_return" if measure == "Win Rate" else True)].copy()
    d["ช่วง"] = d.target.map(TARGET_LABEL)
    d["value"] = d[value]
    d["p"] = d[p_col]
    d["bh"] = d[bh_col]
    d["label"] = [("" if pd.isna(v) else ("{:%s}" % fmt).format(v) + ("★" if b < 0.05 else "")) for v, b in zip(d.value, d.bh)]
    d["nlabel"] = ["" if pd.isna(v) else "n=%s" % "{:,}".format(int(n)) for v, n in zip(d.value, d.win_n if measure == "Win Rate" else d.n)]
    order = [TARGET_LABEL[t] for t in data.STAT_TARGETS if not (measure == "Win Rate" and t == "log_return")]
    base = alt.Chart(d).encode(x=alt.X("ช่วง:O", sort=order, title=None, axis=alt.Axis(labelAngle=0, orient="top")),
                               y=alt.Y("ticker:N", sort=ORDER, title=None))
    valid = "isValid(datum.value)"
    rect = base.mark_rect().transform_filter(valid).encode(
        color=alt.Color("value:Q", title=measure + (" ρ" if unit == "ρ" else " (%)"), scale=alt.Scale(domain=domain, scheme="redyellowgreen", clamp=True)),
        tooltip=["ticker", "ช่วง", alt.Tooltip("value:Q", title=measure, format=fmt), alt.Tooltip("p:Q", title="p-value", format=".4f"),
                 alt.Tooltip("bh:Q", title="p-value (BH)", format=".4f"), alt.Tooltip("nlabel:N", title="จำนวนตัวอย่าง")])
    text = base.mark_text(fontSize=11, dy=-6, color="#222222").transform_filter(valid).encode(text="label:N")
    count = base.mark_text(fontSize=9, dy=8, color="#555555").transform_filter(valid).encode(text="nlabel:N")
    return (rect + text + count).properties(height=max(120, 34 * len(ORDER) + 30))


def pvalue_table(stat, measure):
    """The p-values behind the heat map: ticker x horizon, raw p-value, sorted by the smallest."""
    _, p_col, bh_col, _, _, _ = MEASURES[measure]
    d = stat[stat.ticker.isin(tickers)]
    if measure == "Win Rate":
        d = d[d.target != "log_return"]
    wide = d.pivot_table(index="ticker", columns="target", values=p_col, aggfunc="first", dropna=False)
    wide = wide.reindex(columns=[t for t in data.STAT_TARGETS if t in wide.columns])
    wide.columns = [TARGET_LABEL[c] for c in wide.columns]
    best = d.groupby("ticker")[bh_col].min().rename("BH ต่ำสุด")
    out = wide.assign(**{"p ต่ำสุด": wide.min(axis=1)}).join(best).reset_index()
    out.insert(1, "กลุ่ม", out.ticker.map(group_of).map(GROUP_LABELS))
    out.insert(0, "สินทรัพย์", out.ticker.map(lambda s: "%s · %s" % (s, names.get(s, ""))))
    return out.drop(columns="ticker").sort_values("p ต่ำสุด")


def panel_view(stat, key):
    """The content of one panel tab: the measure switch, the heat map and the table of p-values."""
    if stat.empty or stat.n.fillna(0).sum() == 0:
        st.info("ไม่มีข้อมูลเพียงพอสำหรับ panel นี้ตามตัวกรองที่เลือก (ต้องมีอย่างน้อย 30 ชั่วโมงต่อคู่)")
        return
    measure = st.radio("วัดด้วย", list(MEASURES), horizontal=True, key="p5_measure_" + key, label_visibility="collapsed")
    value = MEASURES[measure][0]
    if stat[stat.ticker.isin(tickers)][value].notna().sum() == 0:
        st.info("ไม่มีค่า %s ของสินทรัพย์ที่เลือก (ข้อมูลไม่พอ)" % measure)
        return
    common.show(heatmap(stat, measure))
    st.caption("สี = %s (แดง ต่ำ เขียว สูง)  ★ = p-value ที่ปรับด้วย Benjamini-Hochberg < 0.05  ช่องว่าง = ข้อมูลน้อยกว่า 30 ชั่วโมง ไม่ใช่ 0  "
               "Current Return = ผลตอบแทนของชั่วโมงเดียวกัน (เกิดพร้อมกัน ไม่ใช่การทำนาย)  1h–12h = ผลตอบแทนล่วงหน้า" % ("ค่าสหสัมพันธ์ ρ" if measure != "Win Rate" else "Win Rate (%) 50 = เดา"))
    st.write("p-value ของ %s (ดิบ) เรียงจากน้อยไปมาก" % measure)
    common.table(pvalue_table(stat, measure).round(4), hide_index=True, width="stretch", height=min(480, 60 + 36 * len(ORDER)))


# ---- the panels: four live tabs and the stored results of the proposal ---------------------------------------------------
LIVE = list(data.PANEL_SUBSETS)
tab_names = [data.PANEL_SUBSETS[k] for k in LIVE] + ["ผลเต็มช่วง 7.4 (เลือก panel)"]
tabs = st.tabs(tab_names, key="p5_tabs", on_change="rerun")
for tab, subset in zip(tabs, LIVE):
    with tab:
        if tab.open:
            sub = data.panel_subset(samples, subset)
            panel_view(live_all if subset == "all" else (data.stat_table(sub) if not sub.empty else live_all.iloc[0:0]), subset)
with tabs[-1]:
    if tabs[-1].open:
        panel = st.selectbox("panel ของระบบ 7.4", list(data.STORED_PANELS), format_func=data.STORED_PANELS.get, key="p5_panel")
        panel_view(q("stored_stat_table", panel), "stored")
        if panel.startswith("panel_global"):
            st.caption("Global = ใช้ความรู้สึกรวมของทั้งตลาดเป็นตัวทำนายให้ทุกสินทรัพย์ (ไม่ใช่เฉพาะข้อความที่พูดถึงสินทรัพย์นั้น)")
        if panel == "panel_baseline":
            st.caption("Baseline = ทิศทางสุ่ม ไม่ดูความรู้สึกเลย ใช้ดูว่าค่าสุ่มให้ผลหน้าตาแบบไหน")

# ---- regression: the stored Logistic Regression of the proposal ------------------------------------------------------------
st.subheader("Logistic Regression: ความรู้สึกทำนายทิศทางราคา (ขึ้น/ลง) ได้ไหม")
st.caption("ผลเต็มช่วงข้อมูล: แบ่งแบบ TimeSeriesSplit 5 ส่วน ห่าง 12 ชั่วโมง ปรับตัวแปรด้วย StandardScaler เฉพาะชุดฝึก  AUC 0.5 = ทำนายไม่ได้ดีกว่าเดา")
scopes = {"ทุกสินทรัพย์รวมกัน": ("all", "ALL")}
scopes.update({GROUP_LABELS[g]: ("big_group", g) for g in groups_chosen})
default_scope = list(scopes)[0] if len(groups_chosen) > 1 else GROUP_LABELS[groups_chosen[0]]
scope_pick = st.radio("ขอบเขต", list(scopes), index=list(scopes).index(default_scope), horizontal=True, key="p5_scope", label_visibility="collapsed")
level, group = scopes[scope_pick]
lg = logi[(logi.status == "ok") & (logi.level == level) & (logi.big_group == group)]
auc_grid = lg[lg.metric == "auc"].copy()
if auc_grid.empty:
    st.info("ไม่มีผล Logistic ของขอบเขตนี้")
else:
    auc_grid["panel_label"] = auc_grid.panel.map(data.STORED_PANELS)
    auc_grid["ช่วง"] = auc_grid.horizon.map(TARGET_LABEL)
    auc_grid["label"] = auc_grid.value.map("{:.3f}".format)
    base = alt.Chart(auc_grid).encode(x=alt.X("ช่วง:O", sort=[TARGET_LABEL[t] for t in data.STAT_TARGETS[1:]], title=None, axis=alt.Axis(labelAngle=0, orient="top")),
                                      y=alt.Y("panel_label:N", sort=[data.STORED_PANELS[p] for p in data.STORED_PANELS], title=None, axis=alt.Axis(labelLimit=260)))
    rect = base.mark_rect().encode(color=alt.Color("value:Q", title="AUC", scale=alt.Scale(domain=[0.47, 0.53], scheme="redblue", reverse=True, clamp=True)),
                                   tooltip=["panel_label", "ช่วง", alt.Tooltip("value:Q", title="AUC", format=".4f"), alt.Tooltip("n:Q", title="จำนวนตัวอย่าง", format=",")])
    text = base.mark_text(fontSize=11, color="#222222").encode(text="label:N")
    common.show((rect + text).properties(height=34 * auc_grid.panel.nunique() + 30))
    st.caption("AUC แต่ละ panel และ Horizon (เหมือนรูป a3_auc)  แดง = สูงกว่า 0.5 น้ำเงิน = ต่ำกว่า 0.5  ค่าเกือบทุกช่องอยู่ที่ 0.50 ± 0.01 คือทำนายไม่ได้ดีกว่าเดา")
    horizon_pick = st.radio("Horizon ที่ดูสัมประสิทธิ์", list(TARGET_LABEL)[1:], horizontal=True, key="p5_log_h", label_visibility="collapsed")
    one = lg[(lg.panel == "panel_Ticker") & (lg.horizon == horizon_pick)]
    coefs = one[one.metric.str.startswith("coef:")].assign(ตัวแปร=lambda d: d.metric.str[5:])
    imp = one[one.metric.str.startswith("group_importance:")].assign(กลุ่มตัวแปร=lambda d: d.metric.str[17:])
    if not coefs.empty:
        common.show(alt.Chart(coefs).mark_bar().encode(
            y=alt.Y("ตัวแปร:N", sort="-x", title=None), x=alt.X("value:Q", title="สัมประสิทธิ์มาตรฐาน (เฉลี่ยข้าม 5 ส่วน)"),
            color=alt.condition(alt.datum.value > 0, alt.value("#2ca02c"), alt.value("#d62728")),
            tooltip=["ตัวแปร", alt.Tooltip("value:Q", title="สัมประสิทธิ์", format="+.4f")]).properties(height=330))
        st.caption("สัมประสิทธิ์ของ panel Ticker ที่ Horizon %s: บวก = ตัวแปรสูงขึ้นแล้วโอกาสที่ราคาขึ้นสูงขึ้น (เขียว) ลบ = ตรงข้าม (แดง) ค่าที่ใกล้ 0 = ไม่มีอิทธิพล" % horizon_pick)
    if not imp.empty:
        common.show(alt.Chart(imp).mark_bar(color=common.C_PRICE).encode(
            y=alt.Y("กลุ่มตัวแปร:N", sort="-x", title=None), x=alt.X("value:Q", title="ความสำคัญของกลุ่ม (ผลรวม |สัมประสิทธิ์|)"),
            tooltip=["กลุ่มตัวแปร", alt.Tooltip("value:Q", title="ความสำคัญ", format=".4f")]).properties(height=200))
        st.caption("กลุ่มตัวแปร: Level, Direction, Vote, Volume, Lag, Momentum ตามที่ proposal กำหนด")
