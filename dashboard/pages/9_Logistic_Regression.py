"""Dashboard extension 9  Logistic Regression  (proposal 7.4, extended 2026-11-16 after the advisor's remark: train, predict on a test set, L1 / L2 to select the variables).

Two separate analyses of `analysis.logistic_eval` (nothing is written to the database), computed LIVE for the panel and the horizon picked on the page, on the rows that pass
the filters of the sidebar (time, assets, communities, model, types of text, majority status; the Reddit Volume Z-score and Sentiment Thresholds act on the panels "all" only):
  1  Is the model of the panel better or worse than a random guess?  AUC on the test set (the last 25% of the hours) with a 95% interval.
  2  How much does each variable add?  add-one and drop-one on the validation set; the test set scores the cut model once.
Above them an overview of the nine panels, precomputed (`output/reports/logistic_panels.csv`, no filter).  Descriptive only: no investment advice.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import altair as alt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard import common, data  # noqa: E402
from dashboard.common import q  # noqa: E402

common.setup("การถดถอยโลจิสติก (Logistic Regression)", "📈")
state = st.session_state
_, start, end, _ = common.sidebar(multi=True, sentiment=True, detection="overview", majority=True)
tickers = common.selected_tickers()
communities = common.selected_communities()
statuses = common.selected_statuses()
content_types = common.selected_content_types()
if not tickers or not communities or not statuses or not content_types:
    st.info("ยังไม่ได้เลือกหลักทรัพย์ ชุมชน ประเภทเนื้อหา หรือประเภทความรู้สึกส่วนใหญ่ จึงไม่มีข้อมูลแสดง")
    st.stop()
z_th = state.get("d_z", 0.0)
s_th = common.sentiment_cut()
model = common.selected_model()
TARGET_LABEL = {"log_return": "Current Return", "1h": "1h", "2h": "2h", "3h": "3h", "6h": "6h", "12h": "12h"}
BOOT = 100                                                                                  # bootstrap rounds of the live interval (the stored report uses 300)


def ink(light_cell_color):
    """Text colour: white on a dark cell, `light_cell_color` on a light one (the field `dark` of the data)."""
    return alt.condition(alt.datum.dark, alt.value("#ffffff"), alt.value(light_cell_color))


def verdict(low, high):
    """'ดีกว่าเดาสุ่ม' / 'แย่กว่าเดาสุ่ม' / 'แยกไม่ออกจากเดาสุ่ม' from the 95% interval of the AUC."""
    if pd.isna(low) or pd.isna(high):
        return "ไม่มีข้อมูล"
    return "ดีกว่าเดาสุ่ม" if low > 0.5 else "แย่กว่าเดาสุ่ม" if high < 0.5 else "แยกไม่ออกจากเดาสุ่ม"


def overview():
    """The AUC on the test set of the nine panels at every horizon, from the precomputed file (default settings, no filter)."""
    d = data.stored_logistic_panels()
    if d.empty:
        return
    d = d[d.status == "ok"].copy()
    labels = {p: "%s (%s)" % (p.replace("panel_", ""), data.STORED_PANELS[p]) for p in data.STORED_PANELS}
    d["panel_label"] = d.panel.map(labels)
    d["ช่วง"] = d.horizon.map(TARGET_LABEL)
    d["verdict"] = [verdict(lo, hi) for lo, hi in zip(d.auc_low, d.auc_high)]
    d["label"] = ["{:.3f}".format(v) + (" ✔" if w == "ดีกว่าเดาสุ่ม" else " ✘" if w == "แย่กว่าเดาสุ่ม" else "") for v, w in zip(d.auc, d.verdict)]
    lo, hi = 0.50, 0.53
    d["dark"] = ((d.auc - lo) / (hi - lo) > 0.6).fillna(False)
    names = [p for p in data.STORED_PANELS if p in set(d.panel)]
    chart = alt.Chart(d).encode(
        x=alt.X("ช่วง:O", sort=[TARGET_LABEL[t] for t in data.STAT_TARGETS], title=None, axis=alt.Axis(labelAngle=0, orient="top")),
        y=alt.Y("panel_label:N", sort=[labels[p] for p in names], title=None, axis=alt.Axis(labelLimit=260)))
    rect = chart.mark_rect().encode(
        color=alt.Color("auc:Q", title="Area Under the ROC Curve (AUC) บนชุดทดสอบ", scale=alt.Scale(domain=[lo, hi], range=["#f1faec", "#0b4d1f"], clamp=True)),
        tooltip=["panel_label", "ช่วง", alt.Tooltip("auc:Q", title="Area Under the ROC Curve (AUC)", format=".4f"), alt.Tooltip("auc_low:Q", title="ช่วงเชื่อมั่น 95% ต่ำ", format=".4f"),
                 alt.Tooltip("auc_high:Q", title="ช่วงเชื่อมั่น 95% สูง", format=".4f"), "verdict", alt.Tooltip("n_test:Q", title="จำนวนแถวชุดทดสอบ", format=",")])
    text = chart.mark_text(fontSize=12).encode(text="label:N", color=ink("#222222"))
    common.block("Area Under the ROC Curve (AUC) ของแต่ละ panel",
                 "panel คือชุดข้อมูลรายชั่วโมงที่ใช้ฝึกและทดสอบแบบจำลอง โดยที่ Global ใช้ความรู้สึกรวมของทั้งตลาด, Ticker ใช้เฉพาะข้อความที่พูดถึงสินทรัพย์นั้น, "
                 "strong / quality / spike คือเฉพาะชั่วโมงที่ความรู้สึกชัดเจน (|s| ≥ 0.05) ความรู้สึกคุณภาพ (|s| ≥ 0.30) หรือปริมาณพุ่ง (Z-score > 1.5), Baseline ใช้ทิศทางสุ่มเป็นตัวเทียบ ",
                 how="แบ่งเวลาเป็นชุดฝึก 75% และชุดทดสอบ 25% เว้น 12 ชั่วโมง เลือก L1 หรือ L2 และค่า C ด้วย TimeSeriesSplit 3 รอบในชุดฝึกเท่านั้น แล้วทายชุดทดสอบครั้งเดียว "
                     "Area Under the ROC Curve (AUC) = ความน่าจะเป็นที่แบบจำลองให้คะแนนชั่วโมงที่ราคาขึ้นสูงกว่าชั่วโมงที่ราคาลง (0.5 = เดาสุ่ม) ✔ = ช่วงเชื่อมั่น 95% สูงกว่า 0.5 ✘ = ต่ำกว่า 0.5")
    common.show((rect + text).properties(height=50 * len(names) + 100))
    rank_p = {labels[p]: i for i, p in enumerate(names)}                                                 # the order of the heat map: the panels top to bottom, the horizons left to right
    rank_h = {TARGET_LABEL[t]: i for i, t in enumerate(data.STAT_TARGETS)}
    d = d.assign(_p=d.panel_label.map(rank_p), _h=d["ช่วง"].map(rank_h)).sort_values(["_p", "_h"])
    pick = st.radio("ช่วงเวลา", list(rank_h), horizontal=True, key="lg_metric_h")                       # the table shows the nine panels at ONE horizon
    metrics = d[d["ช่วง"] == pick][["panel_label", "auc", "accuracy", "balanced_accuracy", "precision", "recall", "f1"]].rename(columns={
        "panel_label": "panel", "auc": "Area Under the ROC Curve (AUC)", "accuracy": "Accuracy", "balanced_accuracy": "Balanced Accuracy", "precision": "Precision", "recall": "Recall", "f1": "F1"})
    st.dataframe(metrics.style.format({c: "{:.3f}" for c in metrics.columns[1:]}), hide_index=True, width="stretch", height=38 * (len(metrics) + 1) + 3)


def reason(r):
    """(result, reason) of one variable: the price variables are the base; a Reddit variable stays when adding it to the price-only model raises the AUC (the 95% interval
    does not contain 0), otherwise it is cut."""
    if r.side == "price":
        return "ฐานราคา (คงไว้)", "ตัวแปรราคาของชั่วโมงเดียวกัน ใช้เป็นฐานเปรียบเทียบ ไม่ถูกตัด"
    gain = "AUC เพิ่ม %+.4f (ช่วงเชื่อมั่น 95%%: %+.4f ถึง %+.4f)" % (r.add_one_delta, r.add_one_low, r.add_one_high)
    if r.add_one_low > 0:
        return "ช่วยจริง (เก็บไว้)", gain
    why = "AUC ไม่เพิ่มอย่างมีนัยสำคัญ (%+.4f ช่วงเชื่อมั่น 95%%: %+.4f ถึง %+.4f คร่อม 0)" % (r.add_one_delta, r.add_one_low, r.add_one_high)
    return "ไม่ช่วย (ตัดออก)", why


def variable_chart(feats, row):
    """The AUC of the price-only model plus ONE Reddit variable, one dot per variable: the dashed line is the price-only AUC (the base), the dotted grey line 0.5 (a random guess),
    the black line the 95% interval of the gain put on the base.  Green dot = the interval is above the base (kept), grey = it is not (taken out)."""
    base_auc = feats.auc_price_val.iloc[0] if "auc_price_val" in feats and not feats.empty else None            # the price-only AUC on the VALIDATION set: the gains are measured there
    var = feats[(feats.kind == "variable") & (feats.side == "reddit")].copy()
    if var.empty or base_auc is None or pd.isna(base_auc):
        return
    var["ตัวแปร"] = ["%s (%s)" % (c, data.VARIABLES.get(c, ("", ""))[0]) for c in var.name]
    var["AUC"] = base_auc + var.add_one_delta
    var["ต่ำ"] = base_auc + var.add_one_low
    var["สูง"] = base_auc + var.add_one_high
    var["ผล"] = ["ช่วยจริง" if low > 0 else "ไม่ช่วย" for low in var.add_one_low]
    var = var.sort_values("AUC", ascending=False)
    base = alt.Chart(var).encode(y=alt.Y("ตัวแปร:N", sort=list(var["ตัวแปร"]), title=None, axis=alt.Axis(labelLimit=420, labelOverlap=False)))
    whisker = base.mark_rule(color="#333333").encode(x=alt.X("ต่ำ:Q", scale=alt.Scale(zero=False), title="Area Under the ROC Curve (AUC) บน validation ของแบบจำลองราคาล้วน + ตัวแปรนี้"), x2="สูง:Q")
    dots = base.mark_circle(size=110, opacity=1).encode(
        x="AUC:Q", color=alt.Color("ผล:N", title=None, scale=alt.Scale(domain=["ช่วยจริง", "ไม่ช่วย"], range=["#1a9850", "#9e9e9e"])),
        tooltip=["ตัวแปร", alt.Tooltip("AUC:Q", title="Area Under the ROC Curve (AUC)", format=".4f"), alt.Tooltip("ต่ำ:Q", title="ช่วงเชื่อมั่น 95% ต่ำ", format=".4f"), alt.Tooltip("สูง:Q", title="ช่วงเชื่อมั่น 95% สูง", format=".4f"), "ผล"])
    lines = alt.Chart(pd.DataFrame({"x": [base_auc, 0.5], "เส้น": ["ราคาล้วน", "เดาสุ่ม (0.5)"]}))
    ref = lines.mark_rule(strokeDash=[6, 4], size=2).encode(x="x:Q", color=alt.Color("เส้น:N", title=None, scale=alt.Scale(domain=["ราคาล้วน", "เดาสุ่ม (0.5)"], range=["#1f77b4", "#888888"])))
    common.show(alt.layer(ref, whisker, dots).resolve_scale(color="independent").properties(height=30 * len(var) + 50))        # two colour scales: the dots and the lines


def reduced_metrics(row):
    """The metrics on the test set of the model with every variable and of the model with only the variables kept in the table."""
    full, red = row, row.get("reduced")
    if not red:
        return
    names = {"auc": "Area Under the ROC Curve (AUC)", "accuracy": "Accuracy", "balanced_accuracy": "Balanced Accuracy", "precision": "Precision", "recall": "Recall", "f1": "F1"}
    out = pd.DataFrame([{"แบบจำลอง": "ก่อนตัด (ทุกตัวแปร 19 ตัว)", **{v: full[k] for k, v in names.items()}},
                        {"แบบจำลอง": "หลังตัด (%d ตัวแปรที่เก็บไว้)" % red["n_vars"], **{v: red[k] for k, v in names.items()}}])
    st.dataframe(out.style.format({v: "{:.3f}" for v in names.values()}), hide_index=True, width="stretch")
    st.caption("ตัวแปรที่เก็บไว้ถูกเลือกด้วยชุด validation ตารางนี้ใช้ชุดทดสอบประเมินครั้งเดียว ไม่ได้ใช้เลือกตัวแปร")


def variable_table(feats):
    """One row per variable: kept or cut, and why."""
    var = feats[feats.kind == "variable"].copy()
    if var.empty:
        return
    out = pd.DataFrame({"ตัวแปร": ["%s (%s)" % (c, data.VARIABLES.get(c, ("", ""))[0]) for c in var.name]})
    verdicts = [reason(r) for r in var.itertuples()]
    out["ผล"] = [v[0] for v in verdicts]
    out["เหตุผล"] = [v[1] for v in verdicts]
    out["VIF"] = var["vif"].to_numpy() if "vif" in var else None
    green = lambda v: "color: #1a7a3a; font-weight: 600" if "เก็บไว้" in v or "คงไว้" in v else ""                  # the variables that stay
    st.dataframe(out.style.map(green, subset=["ผล"]).format({"VIF": lambda v: "เป็นผลรวมของตัวอื่น" if np.isinf(v) else "%.1f" % v}, na_rep="-"), hide_index=True, width="stretch", height=38 * len(out) + 40)
    st.caption("VIF (Variance Inflation Factor) บอกว่าตัวแปรซ้ำซ้อนกับตัวแปรอื่นในโมเดลแค่ไหน: 1 = ไม่ซ้ำ, เกิน 5 = ซ้ำ, เกิน 10 = ซ้ำมาก (ตีความน้ำหนักรายตัวไม่ได้), เป็นผลรวมของตัวอื่น = คำนวณได้จากตัวแปรอื่นตรง ๆ (momentum = ความรู้สึกชั่วโมงนี้ − ชั่วโมงก่อน) คำนวณบนชุดฝึก ไม่เกี่ยวกับตัวทาย")


overview()
common.block("การตัดตัวแปร",
             "จากตัวแปรทั้งหมด 19 ตัว (Reddit 16 ตัว + ราคา 3 ตัว) ใช้ดูว่าตัวใดเก็บไว้ ตัวใดตัดออก และเพราะอะไร ของ panel Global (ความรู้สึกรวมของทั้งตลาด) ที่ Current Return คำนวณสดตามตัวกรองด้านซ้าย",
             how="แบ่งเวลาเป็น ชุดฝึก → ชุด validation → ชุดทดสอบ, ตัวแปรถูกเลือกด้วย validation (ส่วนท้ายของชุดฝึก) ไม่ใช้ชุดทดสอบ, เริ่มจากแบบจำลองราคาล้วน (3 ตัว) แล้วเติมตัวแปร Reddit ทีละตัว ตัวที่ทำให้ Area Under the ROC Curve (AUC) บน validation เพิ่มอย่างมีนัยสำคัญ (ช่วงเชื่อมั่น 95% ไม่คร่อม 0) เก็บไว้ ตัวที่ไม่เพิ่มตัดออก, "
                 "แล้วใช้ชุดทดสอบประเมินแบบจำลองสุดท้ายครั้งเดียว (ตารางก่อนตัด / หลังตัด)")
family = "global"
row, feats = common.logistic_test_live(family, "all", tuple(tickers), start, end, tuple(communities), model, tuple(statuses), z_th, s_th, tuple(content_types), 0,
                                        "log_return", BOOT)
if row.get("status") != "ok":
    st.info("ข้อมูลไม่พอ (ต้องมีแถวครบทุกตัวแปรและแบ่งเป็นชุดฝึกและชุดทดสอบได้) โปรดขยายช่วงเวลาหรือเพิ่มหลักทรัพย์")
elif not feats.empty:
    variable_chart(feats, row)
    reduced_metrics(row)
    variable_table(feats)
