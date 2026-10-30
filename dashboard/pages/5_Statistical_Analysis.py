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

common.setup("Statistical Analysis (วิเคราะห์เชิงสถิติ)", "🏆")
_, start, end, _ = common.sidebar(multi=True, sentiment=True, detection="overview", majority=True)
tickers = common.selected_tickers()
communities = common.selected_communities()
statuses = common.selected_statuses()
content_types = common.selected_content_types()
CARDS = ["Historical Win Rate", "Spearman p-value", "Pearson p-value", "Logistic AUC"]
if not tickers or not communities or not statuses or not content_types:
    common.nothing_selected(CARDS, "ไม่ได้เลือกหลักทรัพย์ ชุมชน หรือประเภทความรู้สึกส่วนใหญ่ จึงไม่มีข้อมูลแสดง")
z_th = st.session_state.get("d_z", 0.0)
s_th = st.session_state.get("d_s", 0.0)
PREDICTOR_OF = {label: key for key, label in data.PREDICTORS.items()}
predictor = PREDICTOR_OF.get(st.session_state.get("p5_predictor"), "sentiment_mean")      # EXTENSION: the variable that is measured (the radio is drawn below the cards)
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
def panel_stat(family, variant, tickers, start, end, communities, model, statuses, z_th, s_th, content_types, predictor):
    """The live statistics table of one panel after every filter of the sidebar (cached: the same filters are never computed twice)."""
    prices = q("price_series_for", tickers, start, end)
    returns = prices[["ticker", "hour_utc", "log_return", *["future_return_" + h for h in data.HORIZONS]]]

    def frame(fam, var):
        if fam == "global":
            sent = q("global_hourly", start, end, communities, model, var, content_types)
        else:
            sent = q("sentiment_hourly", tickers, start, end, communities, model, var, content_types)
        return data.sentiment_frame(sent, start, end)

    base = frame("global" if variant == "baseline" else family, "all")
    own = frame(family, variant) if variant in ("strong", "quality") else None
    samples = data.panel_samples(base, own, returns, family, variant, statuses, z_th, s_th, predictor=predictor)
    if samples.empty:
        return pd.DataFrame(columns=data.STAT_COLUMNS)
    return data.stat_table(samples, sentiment="predictor", directional=predictor != "zscore")


def stat(family, variant):
    return panel_stat(family, variant, tuple(tickers), start, end, tuple(communities), model, tuple(statuses), z_th, s_th,
                      tuple(content_types), predictor)


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
            "ค่ากลางของ p-value ทุกคู่ (สินทรัพย์ × Horizon ล่วงหน้า) ที่เลือก โดย p ต่ำกว่า 0.05 ใน %d จาก %d คู่ (ก่อนปรับ BH)  \n"
            "หากความรู้สึกไม่เกี่ยวกับราคา ค่ากลางควรอยู่ราว 0.5" % (n_sig, n_tests))


common.kpi_cards([
    ("Historical Win Rate", "n/a" if not wins else "{:.1f}%".format(100.0 * hits / wins),
     "สัดส่วนชั่วโมงที่ทิศทางของความรู้สึกตรงกับทิศทางผลตอบแทนอนาคต (ทุก Horizon รวมกัน)  \n50%% เท่ากับการสุ่ม  \np-value ของทั้งชุดเท่ากับ %s"
     % ("n/a" if np.isnan(win_p) else "{:.3f}".format(win_p))),
    p_card("spearman_p", "Spearman p-value"), p_card("pearson_p", "Pearson p-value"),
    ("Logistic AUC", "n/a" if auc.empty else "{:.3f}".format(auc.value.mean()),
     "AUC เฉลี่ยทุก Horizon ของ Logistic Regression (ผลเต็มช่วงข้อมูลของระบบ 7.4 ของกลุ่มสินทรัพย์ที่เลือก ไม่เปลี่ยนตามเวลา)  \n0.5 เท่ากับการสุ่ม")])
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
    if measure == "Win Rate" and predictor == "zscore":
        st.info("Reddit Volume Z-score ไม่มีทิศทางบวกหรือลบ จึงไม่มี Win Rate (ดูได้เฉพาะ Spearman และ Pearson)")
        return
    if stat[stat.ticker.isin(tickers)][BASE[measure][0]].notna().sum() == 0:
        st.info("ไม่มีค่า %s ของสินทรัพย์ที่เลือกใน panel นี้ (ข้อมูลน้อยกว่า 30 ชั่วโมงต่อคู่)" % measure)
        return
    common.show(heatmap(stat, measure))
    st.caption("ตัวเลขใหญ่ในแต่ละช่องคือ %s  \n"
               "บรรทัดที่สองคือ p-value ของค่านั้น (ต่ำกว่า 0.05 ถือว่าน่าสนใจ)  \n"
               "บรรทัดที่สามคือ n หรือจำนวนชั่วโมงที่ใช้คำนวณ  \n"
               "เครื่องหมาย ★ หมายถึง p-value ที่ปรับด้วย Benjamini-Hochberg แล้วต่ำกว่า 0.05  \n"
               "ช่องว่างหมายถึงข้อมูลน้อยกว่า 30 ชั่วโมง ไม่ใช่ค่า 0  \n"
               "Current Return คือผลตอบแทนของชั่วโมงเดียวกัน (เกิดพร้อมกัน ไม่ใช่การทำนาย) ส่วน 1h ถึง 12h คือผลตอบแทนล่วงหน้า  \n"
               "%s"
               % (("Win Rate (%)" if measure == "Win Rate" else "ค่าสหสัมพันธ์ %s" % measure),
                  ("สี: แดงคือต่ำกว่า 50 เขียวคือสูงกว่า 50 (50 เท่ากับการสุ่ม)" if measure == "Win Rate" else
                   "สี: แดงคือค่าลบ เขียวคือค่าบวก ค่า 0 คือไม่มีความสัมพันธ์")))


METHOD_NOTE = """
**เป้าหมายที่ให้โมเดลทาย**  
ผลตอบแทนที่ Horizon นั้นเป็นบวก (ขึ้น = 1) หรือเป็นลบ (ลง = 0) ผลตอบแทนที่เท่ากับ 0 พอดีไม่นับ  Current Return คือ ทิศทางของชั่วโมงเดียวกัน (เกิดพร้อมกัน ไม่ใช่การทำนาย)

**ตัวแปรที่ป้อนให้โมเดล (6 กลุ่มตามที่ proposal กำหนด)**  
Level (ค่าความรู้สึกเฉลี่ย, ความแรง), Direction (สัดส่วนบวก/ลบ), Vote (ประเภทความรู้สึกส่วนใหญ่, สัดส่วนที่เห็นตรงกัน), Volume (Reddit Volume Z-score), Lag (ความรู้สึก 1, 2, 3, 6, 12 ชั่วโมงก่อนหน้า), Momentum (การเปลี่ยนแปลงจากชั่วโมงก่อน)  ไม่ใช้ score, upvote_ratio, num_comments และไม่ใช้ผลตอบแทนอนาคตเป็นตัวแปรป้อนเข้า

**วิธีทดสอบ (เฉลี่ยจาก 5 รอบ)**  
เรียงข้อมูลตามเวลา แล้วแบ่งแบบ TimeSeriesSplit เป็น 5 รอบ แต่ละรอบให้โมเดลเรียนจากข้อมูล**ช่วงก่อนหน้า**แล้วทดสอบกับข้อมูล**ช่วงถัดมา** (ไม่สลับช่วงเวลา) และเว้นห่าง 12 ชั่วโมงระหว่างชุดเรียนกับชุดทดสอบ เพื่อไม่ให้ผลตอบแทนล่วงหน้า 12 ชั่วโมงของชุดเรียนซ้อนกับชุดทดสอบ  ทุกรอบปรับสเกลตัวแปร (StandardScaler) ด้วยข้อมูลชุดเรียนเท่านั้น  **AUC และสัมประสิทธิ์ในหน้านี้คือค่าเฉลี่ยของ 5 รอบ**

**แถวข้อมูล**  
ใช้เฉพาะแถวที่ตัวแปรครบทุกตัว (ไม่เติม 0 แทนค่าที่ขาด เพราะ 0 หมายถึงเป็นกลาง) ต้องมีอย่างน้อย 500 แถวและทุกรอบต้องมีทั้งขึ้นและลง ไม่งั้นไม่แสดงผล  ตัวเลขนับรวมทุกสินทรัพย์ในกลุ่มที่เลือก (ทุกชั่วโมงของทุกสินทรัพย์ในที่เดียว)

**วิธีอ่านผล**  
AUC เท่ากับ 0.5 คือการสุ่ม และ 1.0 คือทายถูกทั้งหมด  
สัมประสิทธิ์มาตรฐานคือการเปลี่ยนแปลงของโอกาสที่ราคาขึ้น (ในสเกลของโมเดล) เมื่อตัวแปรนั้นเพิ่ม 1 ส่วนเบี่ยงเบนมาตรฐาน ค่าบวกดันให้ขึ้น ค่าลบดันให้ลง  ผลทั้งหมดเป็นการบรรยายข้อมูลย้อนหลัง ไม่ใช่คำแนะนำการลงทุน
"""


def logistic_view():
    """The stored Logistic Regression: AUC of every panel and horizon, then the coefficients and the importance of the variable groups."""
    st.caption("ผลเต็มช่วงข้อมูลของระบบ 7.4 (ไม่เปลี่ยนตามเวลา/ชุมชน/เกณฑ์ เพราะเป็นโมเดลที่ตรวจสอบข้ามช่วงเวลา)  โมเดลทายว่าผลตอบแทนจะ \"ขึ้น\" หรือ \"ลง\" "
               "จากตัวแปรความรู้สึกทั้ง 6 กลุ่ม  AUC เท่ากับ 0.5 หมายถึงทำนายได้ไม่ดีกว่าการสุ่ม")
    with st.expander("รายละเอียดวิธีทำ (Logistic Regression)"):
        st.markdown(METHOD_NOTE)
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
    st.caption("สีเหลืองคือ 0.5 (เท่ากับการสุ่ม) สีเขียวคือสูงกว่า 0.5 สีแดงคือต่ำกว่า 0.5 (สีเดียวกับ heat map ด้านบน)  \nค่าเกือบทุกช่องอยู่ที่ 0.50 ± 0.01 หมายความว่าทำนายได้ไม่ดีกว่าการสุ่ม  \n"
               "Current Return คือ ผลตอบแทนของชั่วโมงเดียวกัน (เกิดพร้อมกัน ไม่ใช่การทำนาย)")
    st.write("สัมประสิทธิ์ของแต่ละตัวแปร (ตัวแปรใดมีผลต่อทิศทางราคา) เลือก panel ได้")
    by_label = {v: k for k, v in labels.items()}                                          # the dropdown lists Global first, then Ticker
    panel_pick = by_label[st.selectbox("panel", list(by_label), key="p5_log_panel", label_visibility="collapsed")]
    one = lg[lg.panel == panel_pick]
    coefs = one[one.metric.str.startswith("coef:")].assign(column=lambda d: d.metric.str[5:])
    if coefs.empty:
        st.info("ไม่มีสัมประสิทธิ์ของ panel นี้ในขอบเขตที่เลือก")
        return
    coefs = coefs.assign(ตัวแปร=coefs.column.map(data.variable_label), ช่วง=coefs.horizon.map(TARGET_LABEL),
                         กลุ่ม=coefs.column.map(lambda c: data.VARIABLE_GROUPS.get(data.VARIABLES.get(c, ("", ""))[1], "")),
                         effect=data.effect_points(coefs.value))
    coefs["label"] = coefs.effect.map("{:+.1f}".format)
    row_order = [data.variable_label(c) for c in data.VARIABLES if c in set(coefs.column)]         # grouped: Level, Direction, Vote, Volume, Lag, Momentum

    # 1. one bar per variable: the mean effect over the future horizons and how steady its direction is
    summary = data.effect_summary(coefs)
    summary = summary.assign(ตัวแปร=summary.column.map(data.variable_label), กลุ่ม=summary.column.map(
        lambda c: data.VARIABLE_GROUPS.get(data.VARIABLES.get(c, ("", ""))[1], "")))
    summary["ทิศทางเดียวกัน"] = ["%d/%d Horizon" % (s, h) for s, h in zip(summary.same_sign, summary.horizons)]
    st.write("สรุปผลของแต่ละตัวแปรต่อโอกาสที่ราคาจะขึ้น (จุดเปอร์เซ็นต์) เฉลี่ยจาก 6 ช่วง ได้แก่ Current Return และ Horizon 1h ถึง 12h")
    pad = max(summary.effect.abs().max(), 0.5) * 1.45                                       # room at both ends for the label after the bar
    x_scale = alt.Scale(domain=[-pad, pad], nice=False)
    bars = alt.Chart(summary).encode(y=alt.Y("ตัวแปร:N", sort=row_order, title=None, axis=alt.Axis(labelLimit=520, labelOverlap=False)))
    layer = bars.mark_bar().encode(
        x=alt.X("effect:Q", title="เปลี่ยนโอกาสที่ราคาขึ้น (จุดเปอร์เซ็นต์) เมื่อตัวแปรเพิ่ม 1 ส่วนเบี่ยงเบนมาตรฐาน", scale=x_scale),
        color=alt.condition(alt.datum.effect > 0, alt.value("#2ca02c"), alt.value("#d62728")),
        tooltip=["ตัวแปร", "กลุ่ม", alt.Tooltip("effect:Q", title="ผลเฉลี่ย (จุด%)", format="+.2f"), "ทิศทางเดียวกัน"])
    tag_up = bars.mark_text(fontSize=10, color="#444444", align="left", dx=6).transform_filter("datum.effect > 0").encode(x=alt.X("effect:Q", scale=x_scale), text="ทิศทางเดียวกัน:N")
    tag_down = bars.mark_text(fontSize=10, color="#444444", align="right", dx=-6).transform_filter("datum.effect <= 0").encode(x=alt.X("effect:Q", scale=x_scale), text="ทิศทางเดียวกัน:N")
    common.show((layer + tag_up + tag_down + common.zero_rule_x()).properties(height=28 * len(summary) + 40))
    st.caption("**วิธีอ่าน**  \n"
               "แท่งสีเขียวคือตัวแปรที่สูงขึ้นแล้วโอกาสที่ราคาขึ้นสูงขึ้น แท่งสีแดงคือตรงข้าม  \n"
               "ความยาวแท่งคือจำนวนจุดเปอร์เซ็นต์ (เช่น −2 คือโอกาสขึ้นลดจาก 50% เหลือราว 48%)  \n"
               "ข้อความท้ายแท่งบอกว่าใน 6 ช่วง (Current Return, 1h, 2h, 3h, 6h, 12h) มีกี่ช่วงที่ทิศทางตรงกับค่าเฉลี่ย (6/6 คือทิศทางเดียวกันตลอด)  \n"
               "Current Return คือราคาของชั่วโมงเดียวกัน (เกิดพร้อมกัน ไม่ใช่การทำนาย) ค่าเฉลี่ยจึงมีส่วนของการเคลื่อนไหวพร้อมกันปนอยู่  \n"
               "**ตัวแปรที่มีผลจริงต้องผ่านครบ 3 เงื่อนไข**  \n"
               "แท่งยาวพอ (อย่างน้อยราว 1 จุดเปอร์เซ็นต์)  \n"
               "ทิศทางเดียวกันทุกช่วง (6/6)  \n"
               "โมเดลโดยรวมมี AUC ห่างจาก 0.5  \n"
               "หากแท่งสั้นกว่า 1 จุดเปอร์เซ็นต์หรือทิศทางสลับไปมา แสดงว่าไม่มีผล")

    # 2. the detail: every horizon
    st.write("รายละเอียดผลของแต่ละตัวแปรในแต่ละ Horizon (จุดเปอร์เซ็นต์ของโอกาสที่ราคาขึ้น)")
    chart = alt.Chart(coefs).encode(
        x=alt.X("ช่วง:O", sort=[TARGET_LABEL[t] for t in data.STAT_TARGETS], title=None, axis=alt.Axis(labelAngle=0, orient="top")),
        y=alt.Y("ตัวแปร:N", sort=row_order, title=None, axis=alt.Axis(labelLimit=520, labelOverlap=False)))
    rect = chart.mark_rect().encode(
        color=alt.Color("effect:Q", title="จุด% ของโอกาสขึ้น", scale=alt.Scale(domain=[-2.5, 2.5], scheme="redyellowgreen", clamp=True)),
        tooltip=["ตัวแปร", "กลุ่ม", "ช่วง", alt.Tooltip("effect:Q", title="จุดเปอร์เซ็นต์", format="+.2f"),
                 alt.Tooltip("value:Q", title="สัมประสิทธิ์มาตรฐาน (ค่าดิบของโมเดล)", format="+.4f")])
    text = chart.mark_text(fontSize=11, color="#222222").encode(text="label:N")
    common.show((rect + text).properties(height=30 * len(row_order) + 40))
    st.caption("ค่าในช่องคือจำนวนจุดเปอร์เซ็นต์ที่โอกาสขึ้นเปลี่ยนไปเมื่อตัวแปรเพิ่ม 1 ส่วนเบี่ยงเบนมาตรฐาน (คิดจากสัมประสิทธิ์ ÷ 4 × 100 ซึ่งใช้ได้เมื่อโอกาสใกล้ 50% ดูสัมประสิทธิ์ดิบของโมเดลได้ที่ tooltip)  \n"
               "สีเขียวคือดันให้ขึ้น สีแดงคือดันให้ลง  \nCurrent Return คือชั่วโมงเดียวกัน (เกิดพร้อมกัน ไม่ใช่การทำนาย) จึงมักแรงกว่าคอลัมน์อื่น เพราะราคากับความรู้สึกเปลี่ยนไปพร้อมกัน")
    imp = one[one.metric.str.startswith("group_importance:")].assign(
        กลุ่มตัวแปร=lambda d: d.metric.str[17:].map(lambda g: data.VARIABLE_GROUPS.get(g, g)), ช่วง=lambda d: d.horizon.map(TARGET_LABEL),
        label=lambda d: d.value.map("{:.3f}".format))
    if not imp.empty:
        st.write("ความสำคัญของกลุ่มตัวแปร (ผลรวมขนาดสัมประสิทธิ์ของกลุ่ม ยิ่งสูงยิ่งมีอิทธิพลต่อโมเดลมาก)")
        chart = alt.Chart(imp).encode(
            x=alt.X("ช่วง:O", sort=[TARGET_LABEL[t] for t in data.STAT_TARGETS], title=None, axis=alt.Axis(labelAngle=0, orient="top")),
            y=alt.Y("กลุ่มตัวแปร:N", sort=[g for g in data.VARIABLE_GROUPS.values() if g in set(imp.กลุ่มตัวแปร)], title=None,
                    axis=alt.Axis(labelLimit=300, labelOverlap=False)))
        rect = chart.mark_rect().encode(color=alt.Color("value:Q", title="ความสำคัญ", scale=alt.Scale(scheme="greens")),
                                        tooltip=["กลุ่มตัวแปร", "ช่วง", alt.Tooltip("value:Q", title="ความสำคัญ", format=".4f")])
        text = chart.mark_text(fontSize=11, color="#222222").encode(text="label:N")
        common.show((rect + text).properties(height=34 * imp.กลุ่มตัวแปร.nunique() + 40))
        st.caption("6 กลุ่มตัวแปรตามที่ proposal กำหนด  กลุ่มที่ค่าสูงกว่ามีอิทธิพลต่อโมเดลมากกว่า แต่เมื่อ AUC ใกล้ 0.5 โมเดลโดยรวมก็ยังทำนายไม่ได้")


st.radio("ตัวแปรที่วัด (ส่วนขยายนอก proposal: proposal วัดค่าความรู้สึกเฉลี่ย)", list(PREDICTOR_OF), horizontal=True, key="p5_predictor")
st.caption("ตัวแปรที่วัดคือตัวเลขรายชั่วโมงที่นำมาเทียบกับผลตอบแทน  \nMomentum คือความรู้สึกชั่วโมงนี้ลบด้วยชั่วโมงก่อน  \nLag 1h คือความรู้สึกของชั่วโมงก่อนหน้า  \n"
           "Reddit Volume Z-score ไม่มีทิศทาง จึงไม่มี Win Rate  \nการ์ดและทุกแท็บเปลี่ยนตามตัวแปรที่เลือก")

# ---- one tab per kind of text; ALL of them are computed with the page (cached, so a second visit and every tab switch is instant) --------------
variants = list(data.PANEL_VARIANTS)
names_tabs = [data.PANEL_VARIANTS[v] for v in variants]
tabs = st.tabs(names_tabs)
for tab, variant in zip(tabs, variants):
    with tab:
        if variant == "baseline":
            family = "global"
            st.info("**Baseline ทิศทางสุ่มคืออะไร**  \nเป็นกลุ่มควบคุมไว้เทียบ ระบบนำความรู้สึกจริงออก แล้วสุ่มทิศทางบวกหรือลบ (เหมือนโยนเหรียญ) ใส่แทนในชั่วโมงเดียวกับ panel Global "
                    "แล้วคำนวณ Spearman, Pearson และ Win Rate แบบเดียวกัน  \nผลที่ได้คือ \"หน้าตาของการไม่มีสัญญาณเลย\" (Win Rate ราว 50%, p-value กระจาย 0 ถึง 1) "
                    "หาก panel จริงไม่ต่างจากแท็บนี้ แสดงว่าความรู้สึกจากชุมชน Reddit ไม่ได้ให้ข้อมูลเกี่ยวกับราคา")
        else:
            family = st.radio("ข้อความที่ใช้", list(data.PANEL_FAMILIES), format_func=data.PANEL_FAMILIES.get, horizontal=True, key="p5_family_" + variant)
        panel_view(stat_all if (variant, family) == ("all", "global") else stat(family, variant), variant)

# ---- the Logistic Regression is below the panels --------------------------------------------------------------------------
st.subheader("Logistic Regression (ความรู้สึกทำนายทิศทางราคาขึ้นหรือลงได้หรือไม่)")
logistic_view()
