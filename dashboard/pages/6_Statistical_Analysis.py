"""Dashboard 7.5-2  Statistical Analysis  (proposal 7.5 dashboard 2 "Ranking and Detection Configuration", table 17: Historical Win Rate, p-value, Logistic Regression per asset and
horizon; the figures a1_*, a2_*, a3_* of output/figures made interactive).

Same filters as Market and Sentiment (table 17): time, assets, sentiment source (communities, model), the two thresholds, majority
status.  EVERY number is computed live on the ticker-hours the filters leave, so changing the time range changes the p-values:
  * the nine panels of table 12 in two layers: Global / Ticker / Baseline, then the kind of text (all / strong / quality / spike).  The two panels
    "all" follow every filter of the sidebar (also the Reddit Volume Threshold and the Sentiment Threshold); the other seven (strong, quality, spike
    of both families and the random baseline) use their own fixed cut of table 12 and ignore those two thresholds (the other filters apply).  The
    cards (two rows: Global, Ticker) are the two panels "all";
  * a switch for how the sentiment is read: the score or the majority status (+ / -);
  * a heat map asset x horizon of the Spearman / Pearson correlation or the Win Rate (value, n, a star when the
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
state = st.session_state
if state.get("p5_family_all") in ("Ticker", "compare") and state.get("p5_panel") == "baseline":        # the random baseline belongs to Global only
    state["p5_panel"] = "all"
if state.get("p5_family_all") == "compare":                                              # the comparison: the thresholds act on the sides that are "all" only
    fixed_panel = not (str(state.get("p5_cmp_a", "global:baseline")).endswith(":all") or str(state.get("p5_cmp_b", "global:all")).endswith(":all"))
else:
    fixed_panel = state.get("p5_panel", "all") != "all"                                  # a fixed panel of table 12 ignores the two thresholds: the sidebar greys them out
_, start, end, _ = common.sidebar(multi=True, sentiment=True, detection="overview", majority=True, detection_locked=fixed_panel)
tickers = common.selected_tickers()
communities = common.selected_communities()
statuses = common.selected_statuses()
content_types = common.selected_content_types()
CARDS = ["Historical Win Rate", "Spearman p-value", "Pearson p-value", "Logistic AUC"]
st.caption("**หมายเหตุ:** ไม่มีเกณฑ์จำนวนตัวอย่างขั้นต่ำ ทุกค่าที่คำนวณได้จะแสดง (สหสัมพันธ์ต้องมีอย่างน้อย 3 ชั่วโมงจึงมีค่าทางคณิตศาสตร์) ค่าที่ n น้อยกว่า 30 ติดเครื่องหมาย ⚠ แปลว่าไม่น่าเชื่อถือ ให้ดู n และ ★ (p ปรับ BH) ประกอบเสมอ")
if not tickers or not communities or not statuses or not content_types:
    common.nothing_selected(CARDS, "ไม่ได้เลือกหลักทรัพย์ ชุมชน หรือประเภทความรู้สึกส่วนใหญ่ จึงไม่มีข้อมูลแสดง")
z_th = st.session_state.get("d_z", 0.0)
v_th = int(st.session_state.get("d_v", 0))             # the Reddit Volume Threshold: hours with fewer texts in the whole market are dropped
s_th = common.sentiment_cut()                           # a float (absolute) or the name of the signed variant
PREDICTOR_OF = {label: key for key, label in data.PREDICTORS.items()}
predictor = PREDICTOR_OF.get(st.session_state.get("p5_basis"), "sentiment_mean")      # how the sentiment is read: the score or the majority (+ / -); the radio is drawn below the cards
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
def stat(family, variant):
    return common.panel_stat(family, variant, tuple(tickers), start, end, tuple(communities), model, tuple(statuses), z_th, s_th,
                      tuple(content_types), predictor, v_th)


# ---- cards: two rows, the panel Global and the panel Ticker (every text; the filters of the sidebar apply), future horizons only ---------------------
logi = q("logistic_results")


def card_row(family):
    """The four cards of one panel (Global: the sentiment of the whole market against every asset; Ticker: only the texts that mention the asset)."""
    frame = stat(family, "all")
    base = frame[frame.target != "log_return"]
    hits, wins = base.win_hits.sum(), base.win_n.sum()
    win_p = stats.binomtest(int(hits), int(wins), 0.5).pvalue if wins else np.nan
    logi_ok = logi[(logi.status == "ok") & (logi.panel == "panel_" + family) & (logi.metric == "auc")]
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
    return frame


st.markdown("**Panel Global** (ความรู้สึกรวมของทั้งตลาด เทียบกับผลตอบแทนของแต่ละสินทรัพย์ที่เลือก)")
stat_all = card_row("global")
st.markdown("**Panel Ticker** (เฉพาะข้อความที่พูดถึงสินทรัพย์นั้นโดยตรง)")
stat_ticker = card_row("Ticker")
st.caption("การ์ดทั้งสองแถวคิดจาก panel ทุกข้อความของชั่วโมงที่ผ่านตัวกรองทุกอัน (รวม Reddit Volume Threshold และ Sentiment Threshold ในแถบซ้าย)  ค่า p-value เป็นเชิงพรรณนา "
           "เพราะข้อมูลรายชั่วโมงเกี่ยวเนื่องกันและกรอบเวลาซ้อนทับกัน")


def asset_label(ticker):
    """The name on the left of the heat map: the ticker and, in brackets, its asset class (หุ้น/ETF, ฟิวเจอร์ส, คริปโต)."""
    return "%s (%s)" % (ticker, GROUP_LABELS[group_of[ticker]])


def dark_cell(values, domain):
    """True where the colour of a cell is dark (the two ends of the red-yellow-green scale): the text on it must be white to be read."""
    lo, hi = domain
    t = ((pd.to_numeric(values, errors="coerce") - lo) / (hi - lo)).clip(0, 1)
    return ((t < 0.22) | (t > 0.78)).fillna(False)


def ink(light_cell_color):
    """Text colour: white on a dark cell, `light_cell_color` on a light one (the field `dark` of the data)."""
    return alt.condition(alt.datum.dark, alt.value("#ffffff"), alt.value(light_cell_color))


def heatmap(stat, measure):
    """Ticker x horizon heat map.  Every cell shows the three values (Spearman, Pearson, Win Rate; a star when the Benjamini-Hochberg p < 0.05);
    the measure that is clicked above sets the colour of the cells and is the one printed big and bold.  The p-values and n are in the tooltip."""
    value, p_col, bh_col, fmt, domain, n_col = BASE[measure]
    d = stat[stat.ticker.isin(tickers)].copy()
    d["ช่วง"] = d.target.map(TARGET_LABEL)
    d["value"] = d[value]
    d["asset"] = [asset_label(t) for t in d.ticker]
    d["dark"] = dark_cell(d.value, domain)
    short = {"Spearman": "S", "Pearson": "P", "Win Rate": "W"}
    for name in VIEWS:                                                     # one label per measure: "S +0.021★", "P +0.010", "W 52.1★"
        col, _, bh, f, _, _ = BASE[name]
        pcol = BASE[name][1]
        d["lab_" + name] = ["" if pd.isna(v) else "%s %s%s   %s" % (short[name], ("{:%s}" % f).format(v), "★" if b < 0.05 else "", "p<0.001" if pp < 0.001 else "p=%.3f" % pp)
                            for v, b, pp in zip(d[col], d[bh], d[pcol])]
    d["lab_n"] = ["" if pd.isna(a) else "%sn=%s · Win n=%s" % ("⚠ " if (a < 30 or (not pd.isna(w) and w < 30)) else "", "{:,}".format(int(a)), "-" if pd.isna(w) else "{:,}".format(int(w)))
                  for a, w in zip(d.n, d.win_n)]
    order = [TARGET_LABEL[t] for t in data.STAT_TARGETS]
    chart = alt.Chart(d).encode(x=alt.X("ช่วง:O", sort=order, title=None, axis=alt.Axis(labelAngle=0, orient="top")),
                                y=alt.Y("asset:N", sort=[asset_label(t) for t in ORDER], title=None, axis=alt.Axis(labelLimit=220)))
    valid = "isValid(datum.value)"
    d["bh"], d["n_used"] = d[bh_col], d[n_col]                              # the chosen measure (the page test reads these)
    tips = ["asset", "ช่วง"]
    for name, key in (("Spearman", "sp"), ("Pearson", "pe"), ("Win Rate", "wr")):
        col, pc, bh, f, _, nc = BASE[name]
        d[key + "_v"], d[key + "_p"], d[key + "_bh"], d[key + "_n"] = d[col], d[pc], d[bh], d[nc]
        tips += [alt.Tooltip(key + "_v:Q", title=name, format=f), alt.Tooltip(key + "_p:Q", title="p-value " + name, format=".4f"),
                 alt.Tooltip(key + "_bh:Q", title="p-value (BH) " + name, format=".4f"), alt.Tooltip(key + "_n:Q", title="จำนวนตัวอย่าง " + name, format=",")]
    rect = chart.mark_rect().transform_filter(valid).encode(
        color=alt.Color("value:Q", title=measure + (" (%)" if measure == "Win Rate" else " ค่าสหสัมพันธ์"),
                        scale=alt.Scale(domain=domain, scheme="redyellowgreen", clamp=True)), tooltip=tips)
    layers = [rect]
    for line, name in zip((-24, -8, 8), VIEWS):                            # a line per measure (value, star, p-value); the chosen one is bigger and bold
        chosen = name == measure
        layers.append(chart.mark_text(fontSize=11 if chosen else 9, fontWeight="bold" if chosen else "normal", dy=line).transform_filter(valid).encode(
            text="lab_%s:N" % name, color=ink("#222222" if chosen else "#555555")))
    layers.append(chart.mark_text(fontSize=9, dy=24).transform_filter(valid).encode(text="lab_n:N", color=ink("#555555")))      # the number of hours behind the values
    return alt.layer(*layers).properties(height=max(170, 68 * len(ORDER) + 30))


def panel_view(stat, key):
    """The content of one panel: the switch between the three measures and the heat map."""
    if stat.empty or stat.n.fillna(0).sum() == 0:
        st.info("ไม่มีข้อมูลเพียงพอสำหรับ panel นี้ตามตัวกรองที่เลือก (ไม่มีชั่วโมงที่ผ่านตัวกรองและมีทั้งความรู้สึกกับราคา ลองขยายช่วงเวลาหรือลดเกณฑ์)")
        return
    measure = st.radio("แสดง", VIEWS, horizontal=True, key="p5_measure_" + key, label_visibility="collapsed")
    if stat[stat.ticker.isin(tickers)][BASE[measure][0]].notna().sum() == 0:
        st.info("ไม่มีค่า %s ของสินทรัพย์ที่เลือกใน panel นี้ (ข้อมูลน้อยกว่า 3 ชั่วโมงต่อคู่ คำนวณสหสัมพันธ์ไม่ได้)" % measure)
        return
    common.show(heatmap(stat, measure))
    st.caption("ทุกช่องแสดง 3 ค่า: S = Spearman, P = Pearson, W = Win Rate (%%)  กดปุ่มด้านบนเพื่อเปลี่ยนว่าสีของช่องตามค่าไหน (ค่าที่เลือกพิมพ์ตัวใหญ่ตัวหนา)  \n"
               "ทุกค่ามี p-value (ก่อนปรับ) ต่อท้าย และบรรทัดล่างสุดคือ n (จำนวนชั่วโมงของ Spearman / Pearson) กับ Win n (จำนวนชั่วโมงที่นับใน Win Rate ไม่รวมกรณีที่ราคาหรือความรู้สึกเป็น 0) ชี้ที่ช่องเพื่อดู p ปรับ BH  \n   p ต่ำกว่า 0.05 ถือว่าน่าสนใจ แต่ต้องดู p ปรับ BH ด้วย  \n"
               "เครื่องหมาย ★ ท้ายค่า หมายถึง p-value ของค่านั้นที่ปรับด้วย Benjamini-Hochberg (ส่วนขยาย) แล้วต่ำกว่า 0.05  \n"
               "ช่องว่างหมายถึงคำนวณไม่ได้ (น้อยกว่า 3 ชั่วโมง) ไม่ใช่ค่า 0  \n⚠ หน้า n หมายถึง n น้อยกว่า 30 ไม่น่าเชื่อถือ  \n"
               "Current Return คือผลตอบแทนของชั่วโมงเดียวกัน (เกิดพร้อมกัน ไม่ใช่การทำนาย) ส่วน 1h ถึง 12h คือผลตอบแทนล่วงหน้า  \n"
               "%s"
               % ("สี: แดงคือต่ำกว่า 50 เขียวคือสูงกว่า 50 (50 เท่ากับการสุ่ม)" if measure == "Win Rate" else
                  "สี: แดงคือค่าลบ เขียวคือค่าบวก ค่า 0 คือไม่มีความสัมพันธ์"))


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
    auc_grid["dark"] = dark_cell(auc_grid.value, (0.47, 0.53))
    chart = alt.Chart(auc_grid).encode(
        x=alt.X("ช่วง:O", sort=[TARGET_LABEL[t] for t in data.STAT_TARGETS], title=None, axis=alt.Axis(labelAngle=0, orient="top")),
        y=alt.Y("panel_label:N", sort=[labels[p] for p in data.STORED_PANELS], title=None, axis=alt.Axis(labelLimit=260)))
    rect = chart.mark_rect().encode(
        color=alt.Color("value:Q", title="AUC", scale=alt.Scale(domain=[0.47, 0.53], scheme="redyellowgreen", clamp=True)),
        tooltip=["panel_label", "ช่วง", alt.Tooltip("value:Q", title="AUC", format=".4f"), alt.Tooltip("n:Q", title="จำนวนตัวอย่าง", format=",")])
    text = chart.mark_text(fontSize=11).encode(text="label:N", color=ink("#222222"))
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
    coefs["dark"] = dark_cell(coefs.effect, (-2.5, 2.5))
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
    text = chart.mark_text(fontSize=11).encode(text="label:N", color=ink("#222222"))
    common.show((rect + text).properties(height=30 * len(row_order) + 40))
    st.caption("ค่าในช่องคือจำนวนจุดเปอร์เซ็นต์ที่โอกาสขึ้นเปลี่ยนไปเมื่อตัวแปรเพิ่ม 1 ส่วนเบี่ยงเบนมาตรฐาน (คิดจากสัมประสิทธิ์ ÷ 4 × 100 ซึ่งใช้ได้เมื่อโอกาสใกล้ 50% ดูสัมประสิทธิ์ดิบของโมเดลได้ที่ tooltip)  \n"
               "สีเขียวคือดันให้ขึ้น สีแดงคือดันให้ลง  \nCurrent Return คือชั่วโมงเดียวกัน (เกิดพร้อมกัน ไม่ใช่การทำนาย) จึงมักแรงกว่าคอลัมน์อื่น เพราะราคากับความรู้สึกเปลี่ยนไปพร้อมกัน")
    imp = one[one.metric.str.startswith("group_importance:")].assign(
        กลุ่มตัวแปร=lambda d: d.metric.str[17:].map(lambda g: data.VARIABLE_GROUPS.get(g, g)), ช่วง=lambda d: d.horizon.map(TARGET_LABEL),
        label=lambda d: d.value.map("{:.3f}".format))
    imp["dark"] = (imp.value / imp.value.max()) > 0.7 if len(imp) else False
    if not imp.empty:
        st.write("ความสำคัญของกลุ่มตัวแปร (ผลรวมขนาดสัมประสิทธิ์ของกลุ่ม ยิ่งสูงยิ่งมีอิทธิพลต่อโมเดลมาก)")
        chart = alt.Chart(imp).encode(
            x=alt.X("ช่วง:O", sort=[TARGET_LABEL[t] for t in data.STAT_TARGETS], title=None, axis=alt.Axis(labelAngle=0, orient="top")),
            y=alt.Y("กลุ่มตัวแปร:N", sort=[g for g in data.VARIABLE_GROUPS.values() if g in set(imp.กลุ่มตัวแปร)], title=None,
                    axis=alt.Axis(labelLimit=300, labelOverlap=False)))
        rect = chart.mark_rect().encode(color=alt.Color("value:Q", title="ความสำคัญ", scale=alt.Scale(scheme="greens")),
                                        tooltip=["กลุ่มตัวแปร", "ช่วง", alt.Tooltip("value:Q", title="ความสำคัญ", format=".4f")])
        text = chart.mark_text(fontSize=11).encode(text="label:N", color=ink("#222222"))
        common.show((rect + text).properties(height=34 * imp.กลุ่มตัวแปร.nunique() + 40))
        st.caption("6 กลุ่มตัวแปรตามที่ proposal กำหนด  กลุ่มที่ค่าสูงกว่ามีอิทธิพลต่อโมเดลมากกว่า แต่เมื่อ AUC ใกล้ 0.5 โมเดลโดยรวมก็ยังทำนายไม่ได้")


st.radio("วัดความรู้สึกด้วย", list(PREDICTOR_OF), horizontal=True, key="p5_basis")
st.caption("proposal 7.4 เทียบทิศทางของทั้งคะแนนความรู้สึก (sentiment_mean) และประเภทความรู้สึกส่วนใหญ่ (majority_final_status)  \n"
           "แบบ majority ไม่ใช้คะแนน ใช้แค่ บวก (+1) ลบ (−1) หรือเป็นกลาง (0 = ไม่มีทิศทาง ไม่นับใน Win Rate)  การ์ด แท็บ และตารางจัดอันดับเปลี่ยนตามตัวเลือกนี้")

# ---- the nine panels of table 12 in two layers: the family (Global / Ticker / Baseline), then the kind of text (all / strong / quality / spike) ------------
FAMILIES = {"global": "Global (ความรู้สึกรวมของทั้งตลาด)", "Ticker": "Ticker (เฉพาะข้อความที่พูดถึงสินทรัพย์นั้น)", "compare": "เปรียบเทียบ 2 panel"}
family = st.radio("ข้อความที่ใช้ (panel ตามตาราง 12)", list(FAMILIES), format_func=FAMILIES.get, horizontal=True, key="p5_family_all")
KINDS = data.PANEL_VARIANTS if family != "Ticker" else {k: v for k, v in data.PANEL_VARIANTS.items() if k != "baseline"}       # the random baseline is a view of Global only
PANEL_CHOICES = {"%s:%s" % (f, k): "%s · %s" % ("Global" if f == "global" else "Ticker", v) for f in ("global", "Ticker") for k, v in data.PANEL_VARIANTS.items()
                 if not (f == "Ticker" and k == "baseline")}


def panel_table(choice):
    """The statistics table of one of the nine panels ('global:all', 'Ticker:strong', 'global:baseline', ...): the two panels "all" follow the sidebar, the others are fixed."""
    fam, kd = choice.split(":")
    if kd == "all":
        return stat_all if fam == "global" else stat_ticker
    return common.panel_stat(fam, kd, tuple(tickers), start, end, tuple(communities), model, tuple(statuses), 0.0, 0.0, tuple(content_types), predictor, 0)


def compare_view():
    """Two panels side by side as one heat map of the difference B - A (a click picks which of the three measures)."""
    st.session_state.setdefault("p5_cmp_a", "global:baseline")                # the base: the random direction
    st.session_state.setdefault("p5_cmp_b", "global:all")                     # compared with: every text, as the sidebar thresholds set it
    left, right = st.columns(2)
    a_key = left.selectbox("A (ฝั่งซ้าย ฐานเปรียบเทียบ)", list(PANEL_CHOICES), format_func=PANEL_CHOICES.get, key="p5_cmp_a")
    b_key = right.selectbox("B (ฝั่งขวา เทียบกับ A)", list(PANEL_CHOICES), format_func=PANEL_CHOICES.get, key="p5_cmp_b")
    if a_key == b_key:
        st.info("เลือก panel สองอันที่ต่างกัน")
        return
    measure = st.radio("แสดง", VIEWS, horizontal=True, key="p5_cmp_measure", label_visibility="collapsed")
    value, _, _, fmt, domain, n_col = BASE[measure]
    ta, tb = panel_table(a_key), panel_table(b_key)
    cols = ["ticker", "target", value, n_col]
    both = ta[ta.ticker.isin(tickers)][cols].merge(tb[tb.ticker.isin(tickers)][cols], on=["ticker", "target"], suffixes=("_a", "_b"))
    d = both.rename(columns={value + "_a": "a", value + "_b": "b", n_col + "_a": "na", n_col + "_b": "nb"})
    d = d.dropna(subset=["a", "b"]).copy()
    if d.empty:
        st.info("ไม่มีช่องที่ทั้งสอง panel คำนวณได้พร้อมกัน (ข้อมูลน้อยเกินไปหรือไม่มีชั่วโมงที่ผ่านตัวกรอง) ลองขยายช่วงเวลา")
        return
    pct = measure == "Win Rate"
    d["diff"] = d.b - d.a
    d["rel"] = np.where(d.a != 0, 100.0 * d["diff"] / d.a.abs(), np.nan)
    d["period"] = d.target.map(TARGET_LABEL)
    d["asset"] = [asset_label(t) for t in d.ticker]
    scale = 5.0 if pct else 0.1
    d["dark"] = dark_cell(d["diff"], [-scale, scale])
    unit = " จุด" if pct else ""
    d["lab_a"] = ["A " + ("{:%s}" % fmt).format(v) for v in d.a]
    d["lab_b"] = ["B " + ("{:%s}" % fmt).format(v) for v in d.b]
    d["lab_d"] = [("Δ %+.1f%s (%+.1f%%)" % (x, unit, r) if pct and not pd.isna(r) else "Δ %+.1f%s" % (x, unit)) if pct else "Δ %+.3f" % x for x, r in zip(d["diff"], d.rel)]
    d["lab_n"] = [("⚠ " if min(x, y) < 30 else "") + "n A=%s · B=%s" % ("{:,}".format(int(x)), "{:,}".format(int(y))) for x, y in zip(d.na.fillna(0), d.nb.fillna(0))]
    order = [TARGET_LABEL[t] for t in data.STAT_TARGETS]
    chart = alt.Chart(d).encode(x=alt.X("period:O", sort=order, title=None, axis=alt.Axis(labelAngle=0, orient="top")),
                                y=alt.Y("asset:N", sort=[asset_label(t) for t in ORDER], title=None, axis=alt.Axis(labelLimit=220)))
    rect = chart.mark_rect().encode(
        color=alt.Color("diff:Q", title="B − A (%s)" % ("จุดเปอร์เซ็นต์" if pct else "ผลต่างของ ρ"), scale=alt.Scale(domain=[-scale, scale], scheme="redyellowgreen", clamp=True)),
        tooltip=["asset", "period", alt.Tooltip("a:Q", title="A", format=fmt), alt.Tooltip("b:Q", title="B", format=fmt), alt.Tooltip("diff:Q", title="B − A", format="+.4f"),
                 alt.Tooltip("na:Q", title="n ของ A", format=","), alt.Tooltip("nb:Q", title="n ของ B", format=",")])
    layers = [rect]
    for line, field, bold in ((-22, "lab_a", False), (-8, "lab_b", False), (8, "lab_d", True), (24, "lab_n", False)):
        layers.append(chart.mark_text(fontSize=11 if bold else 9, fontWeight="bold" if bold else "normal", dy=line).encode(
            text=field + ":N", color=ink("#222222" if bold else "#555555")))
    common.show(alt.layer(*layers).properties(height=max(170, 68 * len(ORDER) + 30)))
    higher, total = int((d["diff"] > 0).sum()), len(d)
    st.caption("**สรุป:** %s สูงกว่า %s ใน %d จาก %d ช่อง (ต่ำกว่า %d ช่อง) ผลต่างเฉลี่ย %s" % (PANEL_CHOICES[b_key], PANEL_CHOICES[a_key], higher, total, int((d["diff"] < 0).sum()),
               ("%+.2f จุดเปอร์เซ็นต์" if pct else "%+.4f") % d["diff"].mean()))
    st.caption("สีเขียวคือ B สูงกว่า A สีแดงคือ B ต่ำกว่า A ในช่องมีค่า A, ค่า B, ผลต่าง Δ (Win Rate เป็นจุดเปอร์เซ็นต์ ในวงเล็บคือเปอร์เซ็นต์เทียบกับค่า A ส่วน Spearman และ Pearson เป็นผลต่างของ ρ เพราะเปอร์เซ็นต์ของค่าใกล้ 0 ไม่มีความหมาย) และ n ของสองฝั่ง ⚠ = n ฝั่งใดน้อยกว่า 30  \n"
               "เป็นการเทียบเชิงพรรณนา ยังไม่ผ่านการทดสอบนัยสำคัญของผลต่าง (panel strong / quality เป็นส่วนย่อยของ panel ทุกข้อความ ไม่ใช่ข้อมูลอิสระ)  \n"
               "สไลเดอร์ Reddit Volume Threshold และ Sentiment Threshold ด้านซ้ายมีผลเฉพาะฝั่งที่เป็น **ทุกข้อความ** ฝั่งอื่นใช้เกณฑ์ตายตัวของตาราง 12 ตัวกรองอื่นมีผลกับทั้งสองฝั่ง")
    table = pd.DataFrame({"สินทรัพย์": d.ticker, "Horizon": d.period, "A": d.a, "B": d.b, "B − A": d["diff"], "เปอร์เซ็นต์เทียบ A (%)": d.rel if pct else np.nan,
                          "n A": d.na, "n B": d.nb, "n น้อย": np.where((d.na < 30) | (d.nb < 30), "⚠", "")}).sort_values("B − A", ascending=False)
    if not pct:
        table = table.drop(columns="เปอร์เซ็นต์เทียบ A (%)")
    formats = {"A": "{:" + fmt + "}", "B": "{:" + fmt + "}", "B − A": "{:+.3f}" if not pct else "{:+.2f}", "n A": "{:,.0f}", "n B": "{:,.0f}", "เปอร์เซ็นต์เทียบ A (%)": "{:+.1f}"}
    st.dataframe(table.style.format(formats, na_rep="-"), hide_index=True, width="stretch", height=320)


kind = None
if family == "compare":
    compare_view()
else:
    kind = st.radio("ชนิดข้อความ", list(KINDS), format_func=KINDS.get, horizontal=True, key="p5_panel")
if family == "compare":
    pass
elif kind == "all":
    chosen = stat_all if family == "global" else stat_ticker                       # the panels that follow the sidebar: the cards above
    st.caption("panel นี้ตามตัวกรองด้านซ้ายทุกอัน รวม Reddit Volume Threshold และ Sentiment Threshold (กรอง**ทีละข้อความ**ก่อนเฉลี่ยเป็นความรู้สึกรายชั่วโมง ส่วน Volume กรอง**ทั้งชั่วโมง**)")
else:                                                                              # the fixed panels: their own cut of table 12, whatever the two thresholds of the sidebar say
    chosen = common.panel_stat(family, kind, tuple(tickers), start, end, tuple(communities), model, tuple(statuses),
                               0.0, 0.0, tuple(content_types), predictor, 0)
    if kind == "baseline":
        st.caption("**Baseline ทิศทางสุ่ม** คือเส้นเทียบ: เอาชั่วโมงเดียวกับ panel Global แต่ **โยนเหรียญแทนความรู้สึก** (ทิศทางบวก/ลบสุ่ม ด้วยเมล็ดตายตัว จึงได้ค่าเดิมทุกครั้ง) ถ้าความรู้สึกจริงช่วยทำนายราคาได้ "
                   "Win Rate ของ panel อื่นต้องสูงกว่า Baseline อย่างชัดเจน ส่วน Baseline เองควรอยู่ราว 50% และสหสัมพันธ์ใกล้ 0 (ถ้าไม่ใช่ แปลว่าราคาเองมีแนวโน้มที่ทำให้ Win Rate เบี่ยง ไม่ใช่เพราะความรู้สึก)  \n"
                   "panel นี้ใช้เกณฑ์ตายตัว ไม่ตาม Reddit Volume Threshold และ Sentiment Threshold ด้านซ้าย (ตัวกรองอื่นยังมีผล)")
    else:
        rule = {"strong": "ตัดแถว (ชั่วโมง × สินทรัพย์) ที่ |Sentiment Score เฉลี่ยของชั่วโมง| ต่ำกว่า 0.05 ออก",
                "quality": "เก็บเฉพาะแถวที่ |Sentiment Score เฉลี่ยของชั่วโมง| ตั้งแต่ 0.30",
                "spike": "เก็บเฉพาะแถวของชั่วโมงที่ Reddit Volume Z-score > 1.5"}[kind]
        st.caption("ข้อมูลของหน้านี้คือตาราง ชั่วโมง × สินทรัพย์ × Sentiment Score เฉลี่ย / ทิศทางส่วนใหญ่ แต่ละ panel **กรองแถว**ของตารางนี้ก่อน แล้วค่อยคำนวณ Spearman, Pearson และ Win Rate ใหม่  \n"
                   "**%s**: %s  \n"
                   "ไม่ตาม Reddit Volume Threshold และ Sentiment Threshold ด้านซ้าย ตัวกรองอื่น (ช่วงเวลา สินทรัพย์ ชุมชน โมเดล ประเภทข้อความ ความรู้สึกส่วนใหญ่) ยังมีผล  \n"
                   "ทั้งโหมดคะแนนและโหมด majority กรองแถวด้วย Sentiment Score เฉลี่ยของชั่วโมงเดียวกัน (majority เปลี่ยนแค่วิธีอ่านทิศทาง)" % (KINDS[kind], rule))
if family != "compare":
    panel_view(chosen, "all")


# ---- the ranking of the assets (proposal 7.5 dashboard 2): the panel Global (every text of the market) after every filter, sortable --------------
st.subheader("จัดอันดับสินทรัพย์ (กดหัวคอลัมน์เพื่อเรียง)")
own_frame = data.sentiment_frame(q("sentiment_hourly", tuple(tickers), start, end, tuple(communities), model, "all", tuple(content_types)), start, end)
reddit_volume = own_frame.groupby("series").texts.sum()                               # Reddit volume of the asset: the posts and comments that mention it, in the range
trading_volume = prices.groupby("ticker").volume.mean()                                # trading volume of the asset: the mean per hour of the range (the units differ per asset)
ranking = stat_all[stat_all.ticker.isin(tickers)].copy()
if ranking.empty or ranking.winrate.notna().sum() == 0:
    st.info("ไม่มีสินทรัพย์ที่มีข้อมูลพอ ตามตัวกรองที่เลือก")
else:
    st.session_state.setdefault("p5_rank_h", "Current Return")
    horizon = st.radio("Horizon ของ Spearman, Pearson และ Win Rate", [TARGET_LABEL[t] for t in data.STAT_TARGETS], horizontal=True, key="p5_rank_h")
    one = ranking[ranking.target.map(TARGET_LABEL) == horizon].set_index("ticker")                 # the mean return follows the same horizon (the hours that pass the filters)
    RETURN_NAME = "ผลตอบแทนเฉลี่ย %s (%%)" % horizon
    table = pd.DataFrame({
        "กลุ่ม": one.index.map(lambda t: GROUP_LABELS.get(group_of.get(t), "")), "สินทรัพย์": one.index,
        "Reddit Volume (ข้อความที่พูดถึง)": one.index.map(reddit_volume), "Trading Volume (เฉลี่ยต่อชั่วโมง)": one.index.map(trading_volume),
        "Spearman ρ": one.spearman_rho.values, "Pearson ρ": one.pearson_rho.values, "Win Rate (%)": one.winrate.values,
        "p ดิบ (Win Rate)": one.win_p.values, "p ปรับ BH (Win Rate, ส่วนขยาย)": one.win_bh.values,
        "นัยสำคัญหลังปรับ": np.where(one.win_bh.values < 0.05, "★", ""),
        "n (Win Rate)": one.win_n.values, "n น้อย": np.where((one.win_n.values < 30) | (one.n.values < 30), "⚠", ""),
        RETURN_NAME: one.mean_return.values})
    table = table.sort_values("p ปรับ BH (Win Rate, ส่วนขยาย)", na_position="last")
    formats = {"Reddit Volume (ข้อความที่พูดถึง)": "{:,.0f}", "Trading Volume (เฉลี่ยต่อชั่วโมง)": "{:,.0f}", "n (Win Rate)": "{:,.0f}", "Win Rate (%)": "{:.1f}",
               "p ดิบ (Win Rate)": "{:.3f}", "p ปรับ BH (Win Rate, ส่วนขยาย)": "{:.3f}", "Spearman ρ": "{:+.3f}", "Pearson ρ": "{:+.3f}",
               RETURN_NAME: "{:+.4f}"}
    st.dataframe(table.style.format(formats, na_rep="-"), hide_index=True, width="stretch", height=420)
    st.caption("แถวละ สินทรัพย์ เรียงเริ่มต้นตาม p ปรับ BH ของ Win Rate จากน้อยไปมาก (กดหัวคอลัมน์เพื่อเรียงใหม่)  \n"
               "Spearman, Pearson และ Win Rate คิดที่ Horizon ที่เลือกด้านบน ผลตอบแทนเฉลี่ยก็เป็นของ Horizon นั้นด้วย (Current Return คือส่วนขยาย) คิดจากชั่วโมงที่ผ่านตัวกรองและเกณฑ์ที่ตั้งไว้  \n"
               "Reddit Volume คือจำนวนโพสต์และความคิดเห็นที่พูดถึงสินทรัพย์นั้นในช่วงที่เลือก ส่วน Trading Volume คือปริมาณซื้อขายเฉลี่ยต่อชั่วโมง (หน่วยต่างกันตามสินทรัพย์ เทียบข้ามสินทรัพย์ไม่ได้)")


# ---- the Logistic Regression is below the panels --------------------------------------------------------------------------
st.subheader("Logistic Regression (ความรู้สึกทำนายทิศทางราคาขึ้นหรือลงได้หรือไม่)")
logistic_view()
