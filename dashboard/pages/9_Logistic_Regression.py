"""Dashboard extension 9  Logistic Regression  (proposal 7.4: AUC-ROC and the coefficients of the variables, "to help the interpretation").

The model of system 7.4 (`analysis.logistic`: a model per panel of table 12 and per horizon, TimeSeriesSplit with 5 folds and a gap of 12 hours, scaler
fitted on the training part only) TRAINED LIVE on the ticker-hours that pass the filters of the sidebar (time, assets, communities, model, types of text,
majority status; the Reddit Volume and Sentiment Thresholds act on the panels "all" only, the fixed panels strong / quality / spike / baseline ignore
them, like on Statistical Analysis).  With no filter it gives the stored result of `analysis_results` (checked by a test).
Moved out of Statistical Analysis on 2026-11-13.  Descriptive only: no investment advice.
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

common.setup("Logistic Regression (ส่วนขยาย: โมเดลทายทิศทางราคาจากความรู้สึก)", "📈")
state = st.session_state
if state.get("l9_family") in ("Ticker", "compare") and state.get("l9_kind") == "baseline":        # the random baseline belongs to Global only
    state["l9_kind"] = "all"
if state.get("l9_family") == "compare":                                                         # the comparison: the thresholds act on the sides that are "all" only
    fixed_panel = not (str(state.get("l9_cmp_a", "global:all")).endswith(":all") or str(state.get("l9_cmp_b", "global:strong")).endswith(":all"))
else:
    fixed_panel = state.get("l9_kind", "all") != "all"                                          # a fixed panel of table 12 ignores the two thresholds: the sidebar greys them out
_, start, end, _ = common.sidebar(multi=True, sentiment=True, detection="overview", majority=True, detection_locked=fixed_panel)
tickers = common.selected_tickers()
communities = common.selected_communities()
statuses = common.selected_statuses()
content_types = common.selected_content_types()
if not tickers or not communities or not statuses or not content_types:
    st.info("ไม่ได้เลือกหลักทรัพย์ ชุมชน ประเภทเนื้อหา หรือประเภทความรู้สึกส่วนใหญ่ จึงไม่มีข้อมูลแสดง")
    st.stop()
z_th = state.get("d_z", 0.0)
v_th = int(state.get("d_v", 0))
s_th = common.sentiment_cut()
model = common.selected_model()
TARGET_LABEL = {"log_return": "Current Return", "1h": "1h", "2h": "2h", "3h": "3h", "6h": "6h", "12h": "12h"}
FAMILIES = {"global": "Global (ความรู้สึกรวมของทั้งตลาด)", "Ticker": "Ticker (เฉพาะข้อความที่พูดถึงสินทรัพย์นั้น)", "compare": "เปรียบเทียบ 2 panel"}
PANEL_CHOICES = {"%s:%s" % (f, k): "%s · %s" % ("Global" if f == "global" else "Ticker", v) for f in ("global", "Ticker") for k, v in data.PANEL_VARIANTS.items()
                 if not (f == "Ticker" and k == "baseline")}
universe = q("tickers")
group_of = dict(zip(universe.ticker, universe.big_group))


def live_rows(scope):
    """The Logistic Regression of the nine panels on the assets chosen in the sidebar (scope 'ALL' of `common.logistic_live`), trained live (cached per set of filters)."""
    parts = []
    for choice in PANEL_CHOICES:
        fam, kd = choice.split(":")
        fixed = kd != "all"                                                                 # the fixed panels of table 12 ignore the two thresholds
        parts.append(common.logistic_live(fam, kd, scope, tuple(tickers), start, end, tuple(communities), model, tuple(statuses),
                                          0.0 if fixed else z_th, 0.0 if fixed else s_th, tuple(content_types), 0 if fixed else v_th))
    return pd.concat(parts, ignore_index=True)


def dark_cell(values, domain):
    """True where the colour of a cell is dark (the two ends of the red-yellow-green scale): the text on it must be white to be read."""
    lo, hi = domain
    t = ((pd.to_numeric(values, errors="coerce") - lo) / (hi - lo)).clip(0, 1)
    return ((t < 0.22) | (t > 0.78)).fillna(False)


def ink(light_cell_color):
    """Text colour: white on a dark cell, `light_cell_color` on a light one (the field `dark` of the data)."""
    return alt.condition(alt.datum.dark, alt.value("#ffffff"), alt.value(light_cell_color))


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


def logistic_pickers():
    """The two selectboxes of the comparison (drawn in the sticky bar): A = the base, B = compared with A."""
    choices = {k: v for k, v in PANEL_CHOICES.items() if not k.endswith(":baseline")}          # the random baseline has no variable in common with the others
    st.session_state.setdefault("l9_cmp_a", "global:all")
    st.session_state.setdefault("l9_cmp_b", "global:strong")
    left, right = st.columns(2)
    a_key = left.selectbox("A (ฝั่งซ้าย ฐานเปรียบเทียบ)", list(choices), format_func=choices.get, key="l9_cmp_a")
    b_key = right.selectbox("B (ฝั่งขวา เทียบกับ A)", list(choices), format_func=choices.get, key="l9_cmp_b")
    return a_key, b_key


def logistic_compare(lg, a_key, b_key):
    """Two Logistic panels as one heat map of the difference B - A of the effect of every variable at every horizon (percentage points)."""
    if a_key == b_key:
        st.info("เลือก panel สองอันที่ต่างกัน")
        return

    def effects(choice):
        fam, kd = choice.split(":")
        part = lg[lg.panel == data.panel_name(kd, fam)]
        c = part[part.metric.str.startswith("coef:")].assign(column=lambda d: d.metric.str[5:])
        return c.assign(effect=data.effect_points(c.value))[["column", "horizon", "effect"]]

    ea, eb = effects(a_key), effects(b_key)
    d = ea.merge(eb, on=["column", "horizon"], suffixes=("_a", "_b"))
    if d.empty:
        st.info("ไม่มีตัวแปรและ Horizon ที่ทั้งสอง panel มีผลพร้อมกัน (panel ที่ข้อมูลน้อยไม่มีผลโมเดล)")
        return
    d["diff"] = d.effect_b - d.effect_a
    d["ตัวแปร"] = d.column.map(data.variable_label)
    d["ช่วง"] = d.horizon.map(TARGET_LABEL)
    d["label"] = d["diff"].map("{:+.1f}".format)
    d["dark"] = dark_cell(d["diff"], (-2.5, 2.5))
    row_order = [data.variable_label(c) for c in data.VARIABLES if c in set(d.column)]
    chart = alt.Chart(d).encode(
        x=alt.X("ช่วง:O", sort=[TARGET_LABEL[t] for t in data.STAT_TARGETS], title=None, axis=alt.Axis(labelAngle=0, orient="top")),
        y=alt.Y("ตัวแปร:N", sort=row_order, title=None, axis=alt.Axis(labelLimit=520, labelOverlap=False)))
    rect = chart.mark_rect().encode(
        color=alt.Color("diff:Q", title="B − A (จุด%)", scale=alt.Scale(domain=[-2.5, 2.5], scheme="redyellowgreen", clamp=True)),
        tooltip=["ตัวแปร", "ช่วง", alt.Tooltip("effect_a:Q", title="A (จุด%)", format="+.2f"), alt.Tooltip("effect_b:Q", title="B (จุด%)", format="+.2f"),
                 alt.Tooltip("diff:Q", title="B − A", format="+.2f")])
    text = chart.mark_text(fontSize=11).encode(text="label:N", color=ink("#222222"))
    st.write("ผลต่างของผลแต่ละตัวแปร B − A (จุดเปอร์เซ็นต์ของโอกาสที่ราคาขึ้น)")
    common.show((rect + text).properties(height=30 * len(row_order) + 40))
    st.caption("ค่าในช่องคือผลของตัวแปรใน B ลบด้วยผลของตัวแปรเดียวกันใน A (จุดเปอร์เซ็นต์ของโอกาสที่ราคาขึ้น เมื่อตัวแปรเพิ่ม 1 ส่วนเบี่ยงเบนมาตรฐาน) สีเขียวคือ B ดันให้ขึ้นมากกว่า A สีแดงคือน้อยกว่า ชี้ที่ช่องเพื่อดูค่าของ A และ B  \n"
               "เป็นการเทียบเชิงพรรณนา โมเดลของสอง panel ฝึกจากข้อมูลคนละชุด (strong / quality เป็นส่วนย่อยของ ทุกข้อความ) และ AUC ของโมเดลใกล้ 0.5 ผลต่างที่เห็นจึงมักเป็นเสียงรบกวน ไม่ควรตีความเกินจริง")


def logistic_view():
    """The stored Logistic Regression: AUC of every panel and horizon, then the coefficients and the importance of the variable groups."""
    st.caption("ฝึกโมเดลสดจากชั่วโมงที่ผ่านตัวกรองด้านซ้าย (ฝึกและทดสอบข้ามช่วงเวลา 5 รอบ ไม่สลับเวลา) ไม่ใช่ผลที่เก็บไว้ ตอนไม่กรองได้ผลเท่ากับตารางที่เก็บไว้  "
               "โมเดลทายว่าผลตอบแทนจะ \"ขึ้น\" หรือ \"ลง\" จากตัวแปรความรู้สึกทั้ง 6 กลุ่ม  AUC เท่ากับ 0.5 หมายถึงทำนายได้ไม่ดีกว่าการสุ่ม  "
               "panel ทุกข้อความตามเกณฑ์ด้านซ้าย ส่วน panel อื่นใช้เกณฑ์ตายตัวของตาราง 12 (แถบเกณฑ์เป็นสีเทาเมื่อเลือก panel เหล่านั้น)")
    with st.expander("รายละเอียดวิธีทำ (Logistic Regression)"):
        st.markdown(METHOD_NOTE)
    lg = live_rows("ALL")                                                                  # the assets are chosen in the sidebar (class and ticker boxes)
    lg = lg[lg.status == "ok"]
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
    with common.sticky_bar("l9_bar"):                                                     # the picker stays at the top while the long heat maps below scroll
        log_family = st.radio("ข้อความที่ใช้ (panel ตามตาราง 12)", list(FAMILIES), format_func=FAMILIES.get, horizontal=True, key="l9_family",
                              label_visibility="collapsed")                                  # the same layers as the heat map of Statistical Analysis
        if log_family == "compare":
            a_key, b_key = logistic_pickers()
        else:
            log_kinds = data.PANEL_VARIANTS if log_family == "global" else {k: v for k, v in data.PANEL_VARIANTS.items() if k != "baseline"}
            if st.session_state.get("l9_kind") not in log_kinds:
                st.session_state["l9_kind"] = "all"
            log_kind = st.radio("ชนิดข้อความ", list(log_kinds), format_func=log_kinds.get, horizontal=True, key="l9_kind", label_visibility="collapsed")
    if log_family == "compare":
        logistic_compare(lg, a_key, b_key)
        return
    panel_pick = data.panel_name(log_kind, log_family)
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

    imp = one[one.metric.str.startswith("group_importance:")].assign(
        กลุ่มตัวแปร=lambda d: d.metric.str[17:].map(lambda g: data.VARIABLE_GROUPS.get(g, g)), ช่วง=lambda d: d.horizon.map(TARGET_LABEL),
        label=lambda d: d.value.map("{:.3f}".format))
    imp["dark"] = (imp.value / imp.value.max()) > 0.7 if len(imp) else False
    if not imp.empty:
        st.write("ความสำคัญของกลุ่มตัวแปร (ผลรวมขนาดสัมประสิทธิ์ของกลุ่ม ยิ่งสูงยิ่งมีอิทธิพลต่อโมเดลมาก) ดูกลุ่มก่อน แล้วเจาะรายตัวแปรด้านล่าง")
        chart = alt.Chart(imp).encode(
            x=alt.X("ช่วง:O", sort=[TARGET_LABEL[t] for t in data.STAT_TARGETS], title=None, axis=alt.Axis(labelAngle=0, orient="top")),
            y=alt.Y("กลุ่มตัวแปร:N", sort=[g for g in data.VARIABLE_GROUPS.values() if g in set(imp.กลุ่มตัวแปร)], title=None,
                    axis=alt.Axis(labelLimit=300, labelOverlap=False)))
        rect = chart.mark_rect().encode(color=alt.Color("value:Q", title="ความสำคัญ", scale=alt.Scale(scheme="greens")),
                                        tooltip=["กลุ่มตัวแปร", "ช่วง", alt.Tooltip("value:Q", title="ความสำคัญ", format=".4f")])
        text = chart.mark_text(fontSize=11).encode(text="label:N", color=ink("#222222"))
        common.show((rect + text).properties(height=34 * imp.กลุ่มตัวแปร.nunique() + 40))
        st.caption("6 กลุ่มตัวแปรตามที่ proposal กำหนด  กลุ่มที่ค่าสูงกว่ามีอิทธิพลต่อโมเดลมากกว่า แต่เมื่อ AUC ใกล้ 0.5 โมเดลโดยรวมก็ยังทำนายไม่ได้  \nความสำคัญบอกแค่ว่ากลุ่มไหนมีอิทธิพลมาก ไม่บอกทิศทาง (ขึ้นหรือลง) ดูทิศทางของแต่ละตัวแปรในกราฟถัดไป")

    # the effect of every variable at every horizon, one heat map (the same layout as the heat maps above: no horizon to pick)
    st.write("เจาะรายตัวแปร: ผลของแต่ละตัวแปรในแต่ละ Horizon (จุดเปอร์เซ็นต์ของโอกาสที่ราคาขึ้น มีทิศทางบวก/ลบ)")
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
               "สีเขียวคือดันให้ขึ้น สีแดงคือดันให้ลง  \nCurrent Return คือชั่วโมงเดียวกัน (เกิดพร้อมกัน ไม่ใช่การทำนาย) จึงมักแรงกว่าคอลัมน์อื่น เพราะราคากับความรู้สึกเปลี่ยนไปพร้อมกัน  \n"
               "`sentiment_mean` คือความรู้สึกของชั่วโมงปัจจุบัน (lag 0) ส่วน sentiment_lag_1h ถึง 12h คือความรู้สึกของชั่วโมงก่อนหน้า  \n"
               "**ตัวแปรที่มีผลจริงต้องผ่านครบ**: ค่าสูงพอ (อย่างน้อยราว 1 จุดเปอร์เซ็นต์) ทิศทางเดียวกันในหลาย Horizon และโมเดลโดยรวมมี AUC ห่างจาก 0.5 หากค่าน้อยหรือทิศทางสลับไปมา แสดงว่าไม่มีผล")


logistic_view()
