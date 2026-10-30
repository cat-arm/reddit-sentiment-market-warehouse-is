"""Dashboard 7.5-2  Ranking and Statistics  (proposal 7.5 dashboard 2: Historical Win Rate, p-value, Logistic Regression per asset and
horizon; the figures a1_*, a2_*, a3_* of output/figures made interactive).

Same filters as Market and Sentiment (table 17): time, assets, sentiment source (communities, model), the two thresholds, majority
status.  EVERY number is computed live on the ticker-hours the filters leave, so changing the time range changes the p-values:
  * one tab per kind of text (table 12 of the proposal): every text, the clear ones (strong), the quality ones, the hours of a
    Volume Z-score spike, the random baseline;
  * inside a tab: the texts that mention the asset itself (Ticker) or the sentiment of the whole market (Global);
  * per panel: a heat map asset x horizon of the Spearman / Pearson correlation or the Win Rate (value, n, a star when the
    Benjamini-Hochberg p < 0.05) and the table of the p-values behind it;
  * the Logistic Regression is the stored result of system 7.4 (whole data set; a cross-validated model is not recomputed per filter).
Descriptive only: hourly data are autocorrelated and the horizons overlap, so p-values are not exact; no investment advice.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import altair as alt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402
from scipy import stats  # noqa: E402

from dashboard import common, data  # noqa: E402
from dashboard.common import GROUP_LABELS, q  # noqa: E402

common.setup("Ranking and Statistics: จัดอันดับและสถิติความสัมพันธ์", "🏆")
_, start, end, _ = common.sidebar(multi=True, sentiment=True, detection="overview", majority=True)
tickers = common.selected_tickers()
communities = common.selected_communities()
statuses = common.selected_statuses()
CARDS = ["Historical Win Rate", "Spearman p-value", "Pearson p-value", "Logistic AUC"]
if not tickers or not communities or not statuses:
    common.nothing_selected(CARDS, "ไม่ได้เลือกหลักทรัพย์ ชุมชน หรือประเภทความรู้สึกส่วนใหญ่ จึงไม่มีข้อมูลแสดง")
z_th = st.session_state.get("d_z", 0.0)
s_th = st.session_state.get("d_s", 0.0)
model = common.selected_model()
universe = q("tickers")
group_of = dict(zip(universe.ticker, universe.big_group))
names = dict(zip(universe.ticker, universe.name))
ORDER = list(universe[universe.ticker.isin(tickers)].sort_values(["big_group", "ticker"]).ticker)
TARGET_LABEL = {"log_return": "Current Return", "1h": "1h", "2h": "2h", "3h": "3h", "6h": "6h", "12h": "12h"}
MEASURES = {"Spearman": ("spearman_rho", "spearman_p", "spearman_bh", "+.3f", [-0.1, 0.1]),
            "Pearson": ("pearson_rho", "pearson_p", "pearson_bh", "+.3f", [-0.1, 0.1]),
            "Win Rate": ("winrate", "win_p", "win_bh", ".1f", [40, 60])}
groups_chosen = sorted({group_of[t] for t in tickers})

prices = q("price_series_for", tickers, start, end)
if prices.empty:
    common.kpi_cards([(c, "n/a", None) for c in CARDS])
    st.info("ไม่มีข้อมูลราคาของหลักทรัพย์ที่เลือกในช่วงนี้ (ตลาดอาจปิด)")
    st.stop()
returns = prices[["ticker", "hour_utc", "log_return", *["future_return_" + h for h in data.HORIZONS]]]


def frame(family, variant):
    """`sentiment_frame` of the texts of a family ('Ticker' = those that mention the asset, 'global' = every text) and a variant."""
    if family == "global":
        sent = q("global_hourly", start, end, communities, model, variant)
    else:
        sent = q("sentiment_hourly", tickers, start, end, communities, model, variant)
    return data.sentiment_frame(sent, start, end)


def panel_stat(family, variant):
    """The live statistics table of one panel after every filter of the sidebar."""
    base = frame("global" if variant == "baseline" else family, "all")
    own = frame(family, variant) if variant in ("strong", "quality") else None
    samples = data.panel_samples(base, own, returns, family, variant, statuses, z_th, s_th)
    return data.stat_table(samples) if not samples.empty else pd.DataFrame(columns=data.STAT_COLUMNS)


# ---- cards: the default panel (every text of the market), future horizons only ---------------------------------
stat_all = panel_stat("global", "all")
base = stat_all[stat_all.target != "log_return"]
hits, wins = base.win_hits.sum(), base.win_n.sum()
win_p = stats.binomtest(int(hits), int(wins), 0.5).pvalue if wins else np.nan
logi = q("logistic_results")
logi_ok = logi[(logi.status == "ok") & (logi.panel == "panel_global") & (logi.metric == "auc")]
auc = logi_ok[(logi_ok.level == "all")] if len(groups_chosen) > 1 else logi_ok[(logi_ok.level == "big_group") & (logi_ok.big_group == groups_chosen[0])]


def p_card(column, label):
    p = base[column].dropna()
    n_sig, n_tests = data.significant_share(base, column)
    return (label, "n/a" if p.empty else "{:.3f}".format(p.median()),
            "ค่ากลางของ p-value ทุกคู่ (สินทรัพย์ × Horizon ล่วงหน้า) ที่เลือก: p ต่ำกว่า 0.05 ใน %d จาก %d คู่ (ก่อนปรับ BH) "
            "ถ้าความรู้สึกไม่เกี่ยวกับราคา ค่ากลางควรอยู่ราว 0.5" % (n_sig, n_tests))


common.kpi_cards([
    ("Historical Win Rate", "n/a" if not wins else "{:.1f}%".format(100.0 * hits / wins),
     "สัดส่วนชั่วโมงที่ทิศทางของความรู้สึกตรงกับทิศทางผลตอบแทนอนาคต (ทุก Horizon รวมกัน) 50%% = เดา  p-value ของทั้งก้อน = %s"
     % ("n/a" if np.isnan(win_p) else "{:.3f}".format(win_p))),
    p_card("spearman_p", "Spearman p-value"), p_card("pearson_p", "Pearson p-value"),
    ("Logistic AUC", "n/a" if auc.empty else "{:.3f}".format(auc.value.mean()),
     "AUC เฉลี่ยทุก Horizon ของ Logistic Regression (ผลเต็มช่วงข้อมูลของระบบ 7.4 ของกลุ่มสินทรัพย์ที่เลือก ไม่เปลี่ยนตามเวลา) 0.5 = เดา")])
st.caption("การ์ดคิดจาก panel Global ทุกข้อความ (ความรู้สึกรวมของทั้งตลาด เทียบกับผลตอบแทนของแต่ละสินทรัพย์ที่เลือก) ของชั่วโมงที่ผ่านตัวกรองทุกอัน  ค่า p-value เป็นเชิงพรรณนา "
           "เพราะข้อมูลรายชั่วโมงเกี่ยวเนื่องกันและกรอบเวลาซ้อนทับกัน")


def heatmap(stat, measure):
    """Ticker x horizon heat map of one measure: the value and n in every cell, a star when the Benjamini-Hochberg p < 0.05."""
    value, p_col, bh_col, fmt, domain = MEASURES[measure]
    d = stat[stat.ticker.isin(tickers)].copy()
    if measure == "Win Rate":
        d = d[d.target != "log_return"]
    d["ช่วง"] = d.target.map(TARGET_LABEL)
    d["value"] = d[value]
    d["p"] = d[p_col]
    d["bh"] = d[bh_col]
    d["label"] = [("" if pd.isna(v) else ("{:%s}" % fmt).format(v) + ("★" if b < 0.05 else "")) for v, b in zip(d.value, d.bh)]
    d["nlabel"] = ["" if pd.isna(v) else "n=%s" % "{:,}".format(int(n)) for v, n in zip(d.value, d.win_n if measure == "Win Rate" else d.n)]
    order = [TARGET_LABEL[t] for t in data.STAT_TARGETS if not (measure == "Win Rate" and t == "log_return")]
    chart = alt.Chart(d).encode(x=alt.X("ช่วง:O", sort=order, title=None, axis=alt.Axis(labelAngle=0, orient="top")),
                                y=alt.Y("ticker:N", sort=ORDER, title=None))
    valid = "isValid(datum.value)"
    rect = chart.mark_rect().transform_filter(valid).encode(
        color=alt.Color("value:Q", title=measure + (" (%)" if measure == "Win Rate" else " ρ"),
                        scale=alt.Scale(domain=domain, scheme="redyellowgreen", clamp=True)),
        tooltip=["ticker", "ช่วง", alt.Tooltip("value:Q", title=measure, format=fmt), alt.Tooltip("p:Q", title="p-value", format=".4f"),
                 alt.Tooltip("bh:Q", title="p-value (BH)", format=".4f"), alt.Tooltip("nlabel:N", title="จำนวนตัวอย่าง")])
    text = chart.mark_text(fontSize=11, dy=-6, color="#222222").transform_filter(valid).encode(text="label:N")
    count = chart.mark_text(fontSize=9, dy=8, color="#555555").transform_filter(valid).encode(text="nlabel:N")
    return (rect + text + count).properties(height=max(120, 34 * len(ORDER) + 30))


def pvalue_table(stat, measure):
    """The p-values behind the heat map: asset x horizon, raw p-value, sorted by the smallest."""
    _, p_col, bh_col, _, _ = MEASURES[measure]
    d = stat[stat.ticker.isin(tickers)]
    if measure == "Win Rate":
        d = d[d.target != "log_return"]
    wide = d.pivot_table(index="ticker", columns="target", values=p_col, aggfunc="first", dropna=False)
    wide = wide.reindex(columns=[t for t in data.STAT_TARGETS if t in wide.columns])
    wide.columns = [TARGET_LABEL[c] for c in wide.columns]
    best = d.groupby("ticker")[bh_col].min().rename("p (BH) ต่ำสุด")
    out = wide.assign(**{"p ต่ำสุด": wide.min(axis=1)}).join(best).reset_index()
    out.insert(1, "กลุ่ม", out.ticker.map(group_of).map(GROUP_LABELS))
    out.insert(0, "สินทรัพย์", out.ticker.map(lambda s: "%s · %s" % (s, names.get(s, ""))))
    return out.drop(columns="ticker").sort_values("p ต่ำสุด")


def panel_view(stat, key):
    """The content of one panel: the measure switch, the heat map and the table of the p-values."""
    if stat.empty or stat.n.fillna(0).sum() == 0:
        st.info("ไม่มีข้อมูลเพียงพอสำหรับ panel นี้ตามตัวกรองที่เลือก (ต้องมีอย่างน้อย 30 ชั่วโมงต่อคู่ ลองขยายช่วงเวลาหรือลดเกณฑ์)")
        return
    measure = st.radio("วัดด้วย", list(MEASURES), horizontal=True, key="p5_measure_" + key, label_visibility="collapsed")
    value = MEASURES[measure][0]
    if stat[stat.ticker.isin(tickers)][value].notna().sum() == 0:
        st.info("ไม่มีค่า %s ของสินทรัพย์ที่เลือกใน panel นี้ (ข้อมูลน้อยกว่า 30 ชั่วโมงต่อคู่)" % measure)
        return
    common.show(heatmap(stat, measure))
    st.caption("สี = %s (แดง ต่ำ เขียว สูง)  ★ = p-value ที่ปรับด้วย Benjamini-Hochberg < 0.05  ช่องว่าง = ข้อมูลน้อยกว่า 30 ชั่วโมง ไม่ใช่ 0  "
               "Current Return = ผลตอบแทนของชั่วโมงเดียวกัน (เกิดพร้อมกัน ไม่ใช่การทำนาย)  1h–12h = ผลตอบแทนล่วงหน้า"
               % ("ค่าสหสัมพันธ์ ρ" if measure != "Win Rate" else "Win Rate (%) 50 = เดา"))
    st.write("p-value ของ %s (ดิบ) เรียงจากน้อยไปมาก" % measure)
    common.table(pvalue_table(stat, measure).round(4), hide_index=True, width="stretch", height=min(480, 60 + 36 * len(ORDER)))


# ---- one tab per kind of text; inside it the texts of the asset itself or of the whole market ----------------------------------
variants = list(data.PANEL_VARIANTS)
tabs = st.tabs([data.PANEL_VARIANTS[v] for v in variants], key="p5_tabs", on_change="rerun")
for tab, variant in zip(tabs, variants):
    with tab:
        if not tab.open:
            continue
        if variant == "baseline":
            family = "global"
            st.caption("Baseline = ทิศทางสุ่ม (+1/−1) แทนความรู้สึก ในชั่วโมงเดียวกับ panel Global  ใช้ดูว่าค่าสุ่มให้ผลหน้าตาแบบไหน "
                       "ถ้า panel จริงไม่ต่างจากแท็บนี้ แปลว่าไม่มีสัญญาณ")
        else:
            family = st.radio("ข้อความที่ใช้", list(data.PANEL_FAMILIES), format_func=data.PANEL_FAMILIES.get, horizontal=True, key="p5_family_" + variant)
        panel_view(stat_all if (variant, family) == ("all", "global") else panel_stat(family, variant), variant)

# ---- regression: the stored Logistic Regression of the proposal ------------------------------------------------------------
st.subheader("Logistic Regression: ความรู้สึกทำนายทิศทางราคา (ขึ้น/ลง) ได้ไหม")
st.caption("ผลเต็มช่วงข้อมูลของระบบ 7.4 (ไม่เปลี่ยนตามเวลา/ชุมชน/เกณฑ์ เพราะเป็นโมเดลที่ตรวจสอบข้ามช่วงเวลา)  แบ่งแบบ TimeSeriesSplit 5 ส่วน ห่าง 12 ชั่วโมง "
           "ปรับตัวแปรด้วย StandardScaler เฉพาะชุดฝึก  AUC 0.5 = ทำนายไม่ได้ดีกว่าเดา")
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
    labels = {p: "%s (%s)" % (p.replace("panel_", ""), data.STORED_PANELS[p]) for p in data.STORED_PANELS}
    auc_grid["panel_label"] = auc_grid.panel.map(labels)
    auc_grid["ช่วง"] = auc_grid.horizon.map(TARGET_LABEL)
    auc_grid["label"] = auc_grid.value.map("{:.3f}".format)
    chart = alt.Chart(auc_grid).encode(
        x=alt.X("ช่วง:O", sort=[TARGET_LABEL[t] for t in data.STAT_TARGETS[1:]], title=None, axis=alt.Axis(labelAngle=0, orient="top")),
        y=alt.Y("panel_label:N", sort=[labels[p] for p in data.STORED_PANELS], title=None, axis=alt.Axis(labelLimit=260)))
    rect = chart.mark_rect().encode(
        color=alt.Color("value:Q", title="AUC", scale=alt.Scale(domain=[0.47, 0.53], scheme="redblue", reverse=True, clamp=True)),
        tooltip=["panel_label", "ช่วง", alt.Tooltip("value:Q", title="AUC", format=".4f"), alt.Tooltip("n:Q", title="จำนวนตัวอย่าง", format=",")])
    text = chart.mark_text(fontSize=11, color="#222222").encode(text="label:N")
    common.show((rect + text).properties(height=34 * auc_grid.panel.nunique() + 30))
    st.caption("AUC ของแต่ละ panel และ Horizon (เหมือนรูป a3_auc)  แดง = สูงกว่า 0.5 น้ำเงิน = ต่ำกว่า 0.5  ค่าเกือบทุกช่องอยู่ที่ 0.50 ± 0.01 คือทำนายไม่ได้ดีกว่าเดา")
    horizon_pick = st.radio("Horizon ที่ดูสัมประสิทธิ์", list(TARGET_LABEL)[1:], horizontal=True, key="p5_log_h", label_visibility="collapsed")
    one = lg[(lg.panel == "panel_global") & (lg.horizon == horizon_pick)]
    coefs = one[one.metric.str.startswith("coef:")].assign(ตัวแปร=lambda d: d.metric.str[5:])
    imp = one[one.metric.str.startswith("group_importance:")].assign(กลุ่มตัวแปร=lambda d: d.metric.str[17:])
    if not coefs.empty:
        common.show(alt.Chart(coefs).mark_bar().encode(
            y=alt.Y("ตัวแปร:N", sort="-x", title=None), x=alt.X("value:Q", title="สัมประสิทธิ์มาตรฐาน (เฉลี่ยข้าม 5 ส่วน)"),
            color=alt.condition(alt.datum.value > 0, alt.value("#2ca02c"), alt.value("#d62728")),
            tooltip=["ตัวแปร", alt.Tooltip("value:Q", title="สัมประสิทธิ์", format="+.4f")]).properties(height=330))
        st.caption("สัมประสิทธิ์ของ panel Global ที่ Horizon %s: บวก = ตัวแปรสูงขึ้นแล้วโอกาสที่ราคาขึ้นสูงขึ้น (เขียว) ลบ = ตรงข้าม (แดง) ค่าที่ใกล้ 0 = ไม่มีอิทธิพล" % horizon_pick)
    if not imp.empty:
        common.show(alt.Chart(imp).mark_bar(color=common.C_PRICE).encode(
            y=alt.Y("กลุ่มตัวแปร:N", sort="-x", title=None), x=alt.X("value:Q", title="ความสำคัญของกลุ่ม (ผลรวม |สัมประสิทธิ์|)"),
            tooltip=["กลุ่มตัวแปร", alt.Tooltip("value:Q", title="ความสำคัญ", format=".4f")]).properties(height=200))
        st.caption("กลุ่มตัวแปร: Level, Direction, Vote, Volume, Lag, Momentum ตามที่ proposal กำหนด")
