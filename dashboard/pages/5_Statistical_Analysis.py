"""Dashboard 7.5-2  Statistical Analysis  (proposal 7.5 dashboard 2 "Ranking and Detection Configuration", table 17: Historical Win Rate, p-value, Logistic Regression per asset and
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

common.setup("Statistical Analysis: วิเคราะห์เชิงสถิติ", "🏆")
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
# (value column, p-value column, BH column, format of the value, colour domain, n column): the heat map shows the value or its p-value
BASE = {"Spearman": ("spearman_rho", "spearman_p", "spearman_bh", "+.3f", [-0.1, 0.1], "n"),
        "Pearson": ("pearson_rho", "pearson_p", "pearson_bh", "+.3f", [-0.1, 0.1], "n"),
        "Win Rate": ("winrate", "win_p", "win_bh", ".1f", [40, 60], "win_n")}
VIEWS = ["Spearman", "Pearson", "Win Rate"]                                          # one switch: the cell shows the value AND its p-value
groups_chosen = sorted({group_of[t] for t in tickers})

prices = q("price_series_for", tickers, start, end)
if prices.empty:
    common.kpi_cards([(c, "n/a", None) for c in CARDS])
    st.info("ไม่มีข้อมูลราคาของหลักทรัพย์ที่เลือกในช่วงนี้ (ตลาดอาจปิด)")
    st.stop()
@st.cache_data(show_spinner="กำลังคำนวณ p-value และ Win Rate ...", max_entries=40)
def panel_stat(family, variant, tickers, start, end, communities, model, statuses, z_th, s_th):
    """The live statistics table of one panel after every filter of the sidebar (cached: the same filters are never computed twice)."""
    prices = q("price_series_for", tickers, start, end)
    returns = prices[["ticker", "hour_utc", "log_return", *["future_return_" + h for h in data.HORIZONS]]]

    def frame(fam, var):
        if fam == "global":
            sent = q("global_hourly", start, end, communities, model, var)
        else:
            sent = q("sentiment_hourly", tickers, start, end, communities, model, var)
        return data.sentiment_frame(sent, start, end)

    base = frame("global" if variant == "baseline" else family, "all")
    own = frame(family, variant) if variant in ("strong", "quality") else None
    samples = data.panel_samples(base, own, returns, family, variant, statuses, z_th, s_th)
    return data.stat_table(samples) if not samples.empty else pd.DataFrame(columns=data.STAT_COLUMNS)


def stat(family, variant):
    return panel_stat(family, variant, tuple(tickers), start, end, tuple(communities), model, tuple(statuses), z_th, s_th)


# ---- cards: the default panel (every text of the market), future horizons only ---------------------------------
stat_all = stat("global", "all")
base = stat_all[stat_all.target != "log_return"]
hits, wins = base.win_hits.sum(), base.win_n.sum()
win_p = stats.binomtest(int(hits), int(wins), 0.5).pvalue if wins else np.nan
logi = q("logistic_results")
logi_ok = logi[(logi.status == "ok") & (logi.panel == "panel_global") & (logi.metric == "auc")]
auc = logi_ok[(logi_ok.level == "all")] if len(groups_chosen) > 1 else logi_ok[(logi_ok.level == "big_group") & (logi_ok.big_group == groups_chosen[0])]
auc = auc[auc.horizon != "log_return"]                  # the prediction of the future only, like the other cards


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


def asset_label(ticker):
    """The name on the left of the heat map: the ticker and, in brackets, its asset class (หุ้น/ETF, ฟิวเจอร์ส, คริปโต)."""
    return "%s (%s)" % (ticker, GROUP_LABELS[group_of[ticker]])


def heatmap(stat, measure):
    """Ticker x horizon heat map of one measure.  Every cell: the value (the colour and the big number, a star when the Benjamini-Hochberg
    p < 0.05), under it its p-value and under that the number of samples n it is computed from."""
    value, p_col, bh_col, fmt, domain, n_col = BASE[measure]
    d = stat[stat.ticker.isin(tickers)].copy()
    d["ช่วง"] = d.target.map(TARGET_LABEL)
    d["value"] = d[value]
    d["p"] = d[p_col]
    d["bh"] = d[bh_col]
    d["n_used"] = d[n_col]
    d["asset"] = [asset_label(t) for t in d.ticker]
    d["label"] = [("" if pd.isna(v) else ("{:%s}" % fmt).format(v) + ("★" if b < 0.05 else "")) for v, b in zip(d.value, d.bh)]
    d["plabel"] = ["" if pd.isna(v) else ("p<0.001" if pp < 0.001 else "p=%.3f" % pp) for v, pp in zip(d.value, d.p)]
    d["nlabel"] = ["" if pd.isna(v) else "n=%s" % "{:,}".format(int(n)) for v, n in zip(d.value, d.n_used)]
    order = [TARGET_LABEL[t] for t in data.STAT_TARGETS]
    chart = alt.Chart(d).encode(x=alt.X("ช่วง:O", sort=order, title=None, axis=alt.Axis(labelAngle=0, orient="top")),
                                y=alt.Y("asset:N", sort=[asset_label(t) for t in ORDER], title=None, axis=alt.Axis(labelLimit=220)))
    valid = "isValid(datum.value)"
    rect = chart.mark_rect().transform_filter(valid).encode(
        color=alt.Color("value:Q", title=measure + (" (%)" if measure == "Win Rate" else " ค่าสหสัมพันธ์"),
                        scale=alt.Scale(domain=domain, scheme="redyellowgreen", clamp=True)),
        tooltip=["asset", "ช่วง", alt.Tooltip("value:Q", title=measure, format=fmt), alt.Tooltip("p:Q", title="p-value", format=".4f"),
                 alt.Tooltip("bh:Q", title="p-value (BH)", format=".4f"), alt.Tooltip("n_used:Q", title="จำนวนตัวอย่าง", format=",")])
    text = chart.mark_text(fontSize=11, dy=-12, color="#222222").transform_filter(valid).encode(text="label:N")
    ptext = chart.mark_text(fontSize=9, dy=0, color="#444444").transform_filter(valid).encode(text="plabel:N")
    ntext = chart.mark_text(fontSize=9, dy=11, color="#555555").transform_filter(valid).encode(text="nlabel:N")
    return (rect + text + ptext + ntext).properties(height=max(120, 46 * len(ORDER) + 30))


def panel_view(stat, key):
    """The content of one panel: the switch between the three measures and the heat map."""
    if stat.empty or stat.n.fillna(0).sum() == 0:
        st.info("ไม่มีข้อมูลเพียงพอสำหรับ panel นี้ตามตัวกรองที่เลือก (ต้องมีอย่างน้อย 30 ชั่วโมงต่อคู่ ลองขยายช่วงเวลาหรือลดเกณฑ์)")
        return
    measure = st.radio("แสดง", VIEWS, horizontal=True, key="p5_measure_" + key, label_visibility="collapsed")
    if stat[stat.ticker.isin(tickers)][BASE[measure][0]].notna().sum() == 0:
        st.info("ไม่มีค่า %s ของสินทรัพย์ที่เลือกใน panel นี้ (ข้อมูลน้อยกว่า 30 ชั่วโมงต่อคู่)" % measure)
        return
    common.show(heatmap(stat, measure))
    st.caption("ตัวเลขใหญ่ในแต่ละช่อง = %s  บรรทัดที่สอง = p-value ของค่านั้น (ต่ำกว่า 0.05 = น่าสนใจ)  บรรทัดที่สาม = n จำนวนชั่วโมงที่ใช้คำนวณ  ★ = p-value ที่ปรับด้วย Benjamini-Hochberg < 0.05  "
               "ช่องว่าง = ข้อมูลน้อยกว่า 30 ชั่วโมง ไม่ใช่ 0  "
               "Current Return = ผลตอบแทนของชั่วโมงเดียวกัน (เกิดพร้อมกัน ไม่ใช่การทำนาย) 1h–12h = ผลตอบแทนล่วงหน้า"
               % ("Win Rate (%) สี: แดง ต่ำ เขียว สูง 50 = เดา" if measure == "Win Rate" else
                  "ค่าสหสัมพันธ์ %s สี: แดง ลบ เขียว บวก 0 = ไม่เกี่ยวกัน" % measure))


def logistic_view():
    """The stored Logistic Regression: AUC of every panel and horizon, then the coefficients and the importance of the variable groups."""
    st.caption("ผลเต็มช่วงข้อมูลของระบบ 7.4 (ไม่เปลี่ยนตามเวลา/ชุมชน/เกณฑ์ เพราะเป็นโมเดลที่ตรวจสอบข้ามช่วงเวลา)  แบ่งแบบ TimeSeriesSplit 5 ส่วน ห่าง 12 ชั่วโมง "
               "ปรับตัวแปรด้วย StandardScaler เฉพาะชุดฝึก  โมเดลทายว่าผลตอบแทนจะ \"ขึ้น\" หรือ \"ลง\" จากตัวแปรความรู้สึกทั้ง 6 กลุ่ม  AUC 0.5 = ทำนายไม่ได้ดีกว่าเดา")
    scopes = {"ทุกสินทรัพย์รวมกัน": ("all", "ALL")}
    scopes.update({GROUP_LABELS[g]: ("big_group", g) for g in groups_chosen})
    default_scope = list(scopes)[0] if len(groups_chosen) > 1 else GROUP_LABELS[groups_chosen[0]]
    scope_pick = st.radio("ขอบเขต", list(scopes), index=list(scopes).index(default_scope), horizontal=True, key="p5_scope", label_visibility="collapsed")
    level, group = scopes[scope_pick]
    lg = logi[(logi.status == "ok") & (logi.level == level) & (logi.big_group == group)]
    auc_grid = lg[lg.metric == "auc"].copy()
    if auc_grid.empty:
        st.info("ไม่มีผล Logistic ของขอบเขตนี้")
        return
    labels = {p: "%s (%s)" % (p.replace("panel_", ""), data.STORED_PANELS[p]) for p in data.STORED_PANELS}
    auc_grid["panel_label"] = auc_grid.panel.map(labels)
    auc_grid["ช่วง"] = auc_grid.horizon.map(TARGET_LABEL)
    auc_grid["label"] = auc_grid.value.map("{:.3f}".format)
    chart = alt.Chart(auc_grid).encode(
        x=alt.X("ช่วง:O", sort=[TARGET_LABEL[t] for t in data.STAT_TARGETS], title=None, axis=alt.Axis(labelAngle=0, orient="top")),
        y=alt.Y("panel_label:N", sort=[labels[p] for p in data.STORED_PANELS], title=None, axis=alt.Axis(labelLimit=260)))
    rect = chart.mark_rect().encode(
        color=alt.Color("value:Q", title="AUC", scale=alt.Scale(domain=[0.47, 0.53], scheme="redyellowgreen", clamp=True)),
        tooltip=["panel_label", "ช่วง", alt.Tooltip("value:Q", title="AUC", format=".4f"), alt.Tooltip("n:Q", title="จำนวนตัวอย่าง", format=",")])
    text = chart.mark_text(fontSize=11, color="#222222").encode(text="label:N")
    st.write("AUC แต่ละ panel × Horizon (รูป a3_auc)")
    common.show((rect + text).properties(height=34 * auc_grid.panel.nunique() + 30))
    st.caption("เหลือง = 0.5 (เดา) เขียว = สูงกว่า 0.5 แดง = ต่ำกว่า 0.5 (สีเดียวกับ heat map ด้านบน)  ค่าเกือบทุกช่องอยู่ที่ 0.50 ± 0.01 คือทำนายไม่ได้ดีกว่าเดา  "
               "Current Return = ผลตอบแทนของชั่วโมงเดียวกัน (เกิดพร้อมกัน ไม่ใช่การทำนาย)")
    st.write("สัมประสิทธิ์: เลือก panel และ Horizon")
    by_label = {v: k for k, v in labels.items()}                                          # the dropdown lists Global first, then Ticker
    panel_pick = by_label[st.selectbox("panel", list(by_label), key="p5_log_panel", label_visibility="collapsed")]
    horizon_pick = st.radio("Horizon ที่ดูสัมประสิทธิ์", list(TARGET_LABEL), index=0, format_func=TARGET_LABEL.get, horizontal=True,
                            key="p5_log_h", label_visibility="collapsed")
    one = lg[(lg.panel == panel_pick) & (lg.horizon == horizon_pick)]
    coefs = one[one.metric.str.startswith("coef:")].assign(ตัวแปร=lambda d: d.metric.str[5:])
    imp = one[one.metric.str.startswith("group_importance:")].assign(กลุ่มตัวแปร=lambda d: d.metric.str[17:])
    if not coefs.empty:
        st.write("สัมประสิทธิ์ของแต่ละตัวแปร (%s, %s)" % (labels[panel_pick], TARGET_LABEL[horizon_pick]))
        common.show(alt.Chart(coefs).mark_bar().encode(
            y=alt.Y("ตัวแปร:N", sort="-x", title=None, axis=alt.Axis(labelLimit=320, labelOverlap=False)),
            x=alt.X("value:Q", title="สัมประสิทธิ์มาตรฐาน (เฉลี่ยข้าม 5 ส่วน)"),
            color=alt.condition(alt.datum.value > 0, alt.value("#2ca02c"), alt.value("#d62728")),
            tooltip=["ตัวแปร", alt.Tooltip("value:Q", title="สัมประสิทธิ์", format="+.4f")]).properties(height=26 * len(coefs) + 40))
        st.caption("สัมประสิทธิ์ = ถ้าตัวแปรนั้นเพิ่มขึ้น 1 ส่วนเบี่ยงเบนมาตรฐาน โอกาสที่ราคาขึ้น (เทียบกับลง) เปลี่ยนไปเท่าไรในสเกลของโมเดล  "
                   "บวก = โอกาสขึ้นสูงขึ้น (เขียว) ลบ = ต่ำลง (แดง)  ใน panel และ Horizon นี้ ค่าที่ไกล 0 ที่สุดคือ %+.3f (%s) ซึ่งใกล้ 0 มาก "
                   "คือแต่ละตัวแปรแทบไม่มีอิทธิพล (ถ้า AUC ของ panel นี้ใกล้ 0.5)" % (coefs.value.loc[coefs.value.abs().idxmax()], coefs.ตัวแปร.loc[coefs.value.abs().idxmax()]))
    if not imp.empty:
        st.write("ความสำคัญของกลุ่มตัวแปร (ผลรวมขนาดสัมประสิทธิ์ของกลุ่ม)")
        common.show(alt.Chart(imp).mark_bar(color=common.C_PRICE).encode(
            y=alt.Y("กลุ่มตัวแปร:N", sort="-x", title=None), x=alt.X("value:Q", title="ความสำคัญของกลุ่ม (ผลรวม |สัมประสิทธิ์|)"),
            tooltip=["กลุ่มตัวแปร", alt.Tooltip("value:Q", title="ความสำคัญ", format=".4f")]).properties(height=200))
        st.caption("กลุ่มตัวแปร: Level, Direction, Vote, Volume, Lag, Momentum ตามที่ proposal กำหนด  กลุ่มที่แท่งยาวกว่ามีอิทธิพลต่อโมเดลมากกว่า "
                   "แต่เมื่อ AUC ใกล้ 0.5 โมเดลโดยรวมก็ยังทำนายไม่ได้")


# ---- one tab per kind of text; ALL of them are computed with the page (cached, so a second visit and every tab switch is instant) --------------
variants = list(data.PANEL_VARIANTS)
names_tabs = [data.PANEL_VARIANTS[v] for v in variants]
tabs = st.tabs(names_tabs)
for tab, variant in zip(tabs, variants):
    with tab:
        if variant == "baseline":
            family = "global"
            st.info("**Baseline ทิศทางสุ่ม คืออะไร:** กลุ่มควบคุมไว้เทียบ  ระบบเอาความรู้สึกจริงออก แล้วสุ่มทิศทางบวก/ลบ (เหมือนโยนเหรียญ) ใส่แทนในชั่วโมงเดียวกับ panel Global "
                    "แล้วคำนวณ Spearman, Pearson และ Win Rate แบบเดียวกัน  ผลที่ได้คือ \"หน้าตาของการไม่มีสัญญาณเลย\" (Win Rate ราว 50%, p-value กระจาย 0 ถึง 1) "
                    "ถ้า panel จริงดูไม่ต่างจากแท็บนี้ แปลว่าความรู้สึกจากชุมชน Reddit ไม่ได้ให้ข้อมูลเกี่ยวกับราคา")
        else:
            family = st.radio("ข้อความที่ใช้", list(data.PANEL_FAMILIES), format_func=data.PANEL_FAMILIES.get, horizontal=True, key="p5_family_" + variant)
        panel_view(stat_all if (variant, family) == ("all", "global") else stat(family, variant), variant)

# ---- the Logistic Regression is below the panels --------------------------------------------------------------------------
st.subheader("Logistic Regression: ความรู้สึกทำนายทิศทางราคา (ขึ้น/ลง) ได้ไหม")
logistic_view()
