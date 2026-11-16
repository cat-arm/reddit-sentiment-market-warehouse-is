"""Dashboard 7.5-2  Statistical Analysis  (proposal 7.5 dashboard 2 "Ranking and Detection Configuration", table 17: Historical Win Rate, p-value per asset and
horizon; the figures a1_*, a2_*, a3_* of output/figures made interactive).

Same filters as Market and Sentiment (table 17): time, assets, sentiment source (communities, model), the two thresholds, majority
status.  EVERY number is computed live on the ticker-hours the filters leave, so changing the time range changes the p-values:
  * the nine panels of table 12 in two layers: Global / Ticker / Baseline, then the kind of text (all / strong / quality / spike).  The two panels
    "all" follow every filter of the sidebar (also the Reddit Volume Z-score Threshold and the Sentiment Threshold); the other seven (strong, quality, spike
    of both families and the random baseline) use their own fixed cut of table 12 and ignore those two thresholds (the other filters apply).  The
    cards (two rows: Global, Ticker) are the two panels "all";
  * a switch for how the sentiment is read: the score or the majority status (+ / -);
  * a heat map asset x horizon of the Spearman correlation (rho, its p-value from the circular-shift test, its 95% interval from a block bootstrap, a star when the
    Benjamini-Hochberg p < 0.05) or the Win Rate; Pearson is not shown (the data are not normal: scripts/normality_check.py);
  * the Logistic Regression (stored result of system 7.4, whole data set) is its own page, `9_Logistic_Regression.py` (moved out 2026-11-13).
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

common.setup("การวิเคราะห์เชิงสถิติ (Statistical Analysis)", "🏆")
state = st.session_state
SHOW_PANEL_KIND = False                                                                  # the picker "ชนิดข้อความ" (all / strong / quality / spike / baseline) is hidden (user, 2026-11-16); True brings it back
SHOW_BASIS = False                                                                       # the picker "วัดความรู้สึกด้วย" (score / majority) is hidden (user, 2026-11-16); True brings it back
if state.get("p5_family_all") in ("Ticker", "compare") and state.get("p5_panel") == "baseline":        # the random baseline belongs to Global only
    state["p5_panel"] = "all"
fixed_panel = SHOW_PANEL_KIND and state.get("p5_panel", "all") != "all" and state.get("p5_family_all") != "compare"       # a fixed panel of table 12 ignores the two thresholds: the sidebar greys them out; the comparison is Global and Ticker "all": the thresholds work
_, start, end, _ = common.sidebar(multi=True, sentiment=True, detection="overview", majority=True, detection_locked=fixed_panel)
tickers = common.selected_tickers()
communities = common.selected_communities()
statuses = common.selected_statuses()
content_types = common.selected_content_types()
CARDS = ["Historical Win Rate", "Spearman p-value"]
if not tickers or not communities or not statuses or not content_types:
    common.nothing_selected(CARDS, "ยังไม่ได้เลือกหลักทรัพย์ ชุมชน หรือประเภทความรู้สึกส่วนใหญ่ จึงไม่มีข้อมูลแสดง")
z_th = st.session_state.get("d_z", 0.0)
s_th = common.sentiment_cut()                           # a float (absolute) or the name of the signed variant
PREDICTOR_OF = {label: key for key, label in data.PREDICTORS.items()}
predictor = PREDICTOR_OF.get(st.session_state.get("p5_basis"), "sentiment_mean") if SHOW_BASIS else "sentiment_mean"      # how the sentiment is read: the score or the majority (+ / -); the radio is drawn below the cards
model = common.selected_model()
universe = q("tickers")
group_of = dict(zip(universe.ticker, universe.big_group))
names = dict(zip(universe.ticker, universe.name))
ORDER = list(universe[universe.ticker.isin(tickers)].sort_values(["big_group", "ticker"]).ticker)
TARGET_LABEL = {"log_return": "Current Return", "1h": "1h", "2h": "2h", "3h": "3h", "6h": "6h", "12h": "12h"}
# (value column, p-value column, BH column, format of the value, colour domain, n column): the heat map shows the value or its p-value
BASE = {"Spearman": ("spearman_rho", "spearman_p_shift", "spearman_bh_shift", "+.3f", [-0.1, 0.1], "n"),             # the p-value of Spearman is the circular-shift one (it keeps the autocorrelation)
        "Win Rate": ("winrate", "win_p", "win_bh", ".1f", [40, 60], "win_n")}
VIEWS = ["Spearman", "Win Rate"]                                          # one switch: the cell shows the value AND its p-value

prices = q("price_series_for", tickers, start, end)
if prices.empty:
    common.kpi_cards([(c, "n/a", None) for c in CARDS])
    st.info("ไม่มีข้อมูลราคาของหลักทรัพย์ที่เลือกในช่วงนี้ (ตลาดอาจปิด)")
    st.stop()
def stat(family, variant):
    return common.panel_stat(family, variant, tuple(tickers), start, end, tuple(communities), model, tuple(statuses), z_th, s_th,
                      tuple(content_types), predictor)


# ---- cards: two rows, the panel Global and the panel Ticker (every text; the filters of the sidebar apply), future horizons only ---------------------

def card_row(family):
    """The four cards of one panel (Global: the sentiment of the whole market against every asset; Ticker: only the texts that mention the asset)."""
    frame = stat(family, "all")
    base = frame[frame.target != "log_return"]
    hits, wins = base.win_hits.sum(), base.win_n.sum()
    win_p = stats.binomtest(int(hits), int(wins), 0.5).pvalue if wins else np.nan

    def p_card(column, label):
        p = base[column].dropna()
        n_sig, n_tests = data.significant_share(base, column)
        what = ("ความรู้สึกกับผลตอบแทนที่ตามมา มีความสัมพันธ์กันจริงหรือแค่บังเอิญ (p ต่ำ = ไม่น่าบังเอิญ) Spearman ดูว่าลำดับสูง-ต่ำไปทางเดียวกันไหม ทนค่าสุดโต่ง "
                "และ p คิดว่าชั่วโมงติดกันคล้ายกัน (เลื่อนอนุกรมความรู้สึกแบบวงกลม)")
        return (label, "n/a" if p.empty else "{:.3f}".format(p.median()),
                common.explain(what, "หา p-value ของทุกคู่ (สินทรัพย์ × ช่วงเวลาล่วงหน้า 1–12 ชม.) แล้วเอาค่ากลาง ถ้าไม่เกี่ยวกันจริงค่ากลางควรอยู่ราว 0.5",
                               "p ต่ำกว่า 0.05 อยู่ %d จาก %d คู่ (ก่อนปรับ BH)" % (n_sig, n_tests)))

    common.kpi_cards([
        ("Historical Win Rate", "n/a" if not wins else "{:.1f}%".format(100.0 * hits / wins),
         common.explain("ความรู้สึกทายทิศราคาถูกกี่ % (50% = เดาสุ่ม)",
                        "นับชั่วโมงที่ทิศของความรู้สึก (บวก/ลบ) ตรงกับทิศราคาที่ตามมา (ขึ้น/ลง) ทุกช่วงเวลาล่วงหน้า 1–12 ชม. รวมกัน หารด้วยจำนวนชั่วโมงทั้งหมด",
                        "p-value ของทั้งชุด = %s (ทดสอบเทียบ 50%%)" % ("n/a" if np.isnan(win_p) else "{:.3f}".format(win_p)))),
        p_card("spearman_p_shift", "Spearman p-value")])
    return frame


st.markdown("**Panel Global** (ความรู้สึกรวมของทั้งตลาด เทียบกับผลตอบแทนของแต่ละสินทรัพย์ที่เลือก)")
stat_all = card_row("global")
st.markdown("**Panel Ticker** (เฉพาะข้อความที่พูดถึงสินทรัพย์นั้นโดยตรง)")
stat_ticker = card_row("Ticker")


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


HEATMAP_ROW, HEATMAP_ROOM = 68, 130                                         # px per ticker row of a heat map, and the legend + column labels around the cells


def heatmap(stat, measure):
    """Ticker x horizon heat map.  Every cell shows the Spearman rho (a star when the Benjamini-Hochberg p of the circular-shift test is below 0.05) with that p-value, the 95% interval
    of rho (block bootstrap over the UTC days), the Win Rate with its p-value and n; the measure that is clicked above sets the colour of the cells and is the one printed bold."""
    value, p_col, bh_col, fmt, domain, n_col = BASE[measure]
    d = stat[stat.ticker.isin(tickers)].copy()
    d["ช่วง"] = d.target.map(TARGET_LABEL)
    d["value"] = d[value]
    d["asset"] = [asset_label(t) for t in d.ticker]
    d["dark"] = dark_cell(d.value, domain)
    short = {"Spearman": "S", "Win Rate": "W"}
    for name in VIEWS:                                                     # one label per measure: "S +0.021★ p=0.004", "W 52.1★ p=0.233"
        col, pcol, bh, f, _, _ = BASE[name]
        d["lab_" + name] = ["" if pd.isna(v) else "%s %s%s   %s" % (short[name], ("{:%s}" % f).format(v), "★" if b < 0.05 else "", "p<0.001" if pp < 0.001 else "p=%.3f" % pp)
                            for v, b, pp in zip(d[col], d[bh], d[pcol])]
    d["lab_ci"] = ["" if (pd.isna(a) or pd.isna(b)) else "ช่วงเชื่อมั่น 95%%: %+.3f ถึง %+.3f" % (a, b) for a, b in zip(d.spearman_ci_low, d.spearman_ci_high)]
    d["lab_n"] = ["" if pd.isna(a) else "%sn=%s · Win n=%s" % ("⚠ " if (a < 30 or (not pd.isna(w) and w < 30)) else "", "{:,}".format(int(a)), "-" if pd.isna(w) else "{:,}".format(int(w)))
                  for a, w in zip(d.n, d.win_n)]
    order = [TARGET_LABEL[t] for t in data.STAT_TARGETS]
    chart = alt.Chart(d).encode(x=alt.X("ช่วง:O", sort=order, title=None, axis=alt.Axis(labelAngle=0, orient="top")),
                                y=alt.Y("asset:N", sort=[asset_label(t) for t in ORDER], title=None, axis=alt.Axis(labelLimit=220)))
    valid = "isValid(datum.value)"
    d["bh"], d["n_used"] = d[bh_col], d[n_col]                              # the chosen measure (the page test reads these)
    tips = ["asset", "ช่วง"]
    d["sp_lo"], d["sp_hi"] = d.spearman_ci_low, d.spearman_ci_high
    for name, key in (("Spearman", "sp"), ("Win Rate", "wr")):
        col, pc, bh, f, _, nc = BASE[name]
        d[key + "_v"], d[key + "_p"], d[key + "_bh"], d[key + "_n"] = d[col], d[pc], d[bh], d[nc]
        tips += [alt.Tooltip(key + "_v:Q", title=name, format=f), alt.Tooltip(key + "_p:Q", title="p-value " + name, format=".4f"),
                 alt.Tooltip(key + "_bh:Q", title="p-value (BH) " + name, format=".4f"), alt.Tooltip(key + "_n:Q", title="จำนวนตัวอย่าง " + name, format=",")]
        if key == "sp":
            tips += [alt.Tooltip("sp_lo:Q", title="ช่วงเชื่อมั่น 95% ต่ำ", format="+.4f"), alt.Tooltip("sp_hi:Q", title="ช่วงเชื่อมั่น 95% สูง", format="+.4f")]
    rect = chart.mark_rect().transform_filter(valid).encode(
        color=alt.Color("value:Q", title=measure + (" (%)" if measure == "Win Rate" else " ค่าสหสัมพันธ์"),
                        scale=alt.Scale(domain=domain, scheme="redyellowgreen", clamp=True)), tooltip=tips)
    layers = [rect]
    for line, name in ((-24, "Spearman"), (8, "Win Rate")):                  # the value and its p-value; the chosen measure is bigger and bold
        chosen = name == measure
        layers.append(chart.mark_text(fontSize=11 if chosen else 9, fontWeight="bold" if chosen else "normal", dy=line).transform_filter(valid).encode(
            text="lab_%s:N" % name, color=ink("#222222" if chosen else "#555555"), tooltip=tips))
    layers.append(chart.mark_text(fontSize=9, dy=-8).transform_filter(valid).encode(text="lab_ci:N", color=ink("#555555"), tooltip=tips))      # the 95% interval of the Spearman rho
    layers.append(chart.mark_text(fontSize=9, dy=24).transform_filter(valid).encode(text="lab_n:N", color=ink("#555555"), tooltip=tips))       # the number of hours behind the values
    # Streamlit fits the WHOLE chart (colour legend on top, labels of the columns on top) into `height`: ~130 px of it is not cells (measured on screen: a chart of
    # 340 px had 210 px of cells), so the height is 68 px per row (the four lines of text of a cell) plus that room
    return alt.layer(*layers).properties(height=HEATMAP_ROW * len(ORDER) + HEATMAP_ROOM)


def panel_view(stat, measure):
    """The content of one panel: the heat map of the measure that is picked in the sticky bar above."""
    if stat.empty or stat.n.fillna(0).sum() == 0:
        st.info("ไม่มีข้อมูลเพียงพอสำหรับ panel นี้ตามตัวกรองที่เลือก (ไม่มีชั่วโมงที่ผ่านตัวกรองและมีทั้งความรู้สึกกับราคา โปรดขยายช่วงเวลาหรือลดเกณฑ์)")
        return
    if stat[stat.ticker.isin(tickers)][BASE[measure][0]].notna().sum() == 0:
        st.info("ไม่มีค่า %s ของสินทรัพย์ที่เลือกใน panel นี้ (ข้อมูลน้อยกว่า 3 ชั่วโมงต่อคู่ คำนวณสหสัมพันธ์ไม่ได้)" % measure)
        return
    common.show(heatmap(stat, measure))


if SHOW_BASIS:
    st.radio("วัดความรู้สึกด้วย", list(PREDICTOR_OF), horizontal=True, key="p5_basis")

# ---- the nine panels of table 12 in two layers: the family (Global / Ticker / Baseline), then the kind of text (all / strong / quality / spike) ------------
FAMILIES = {"global": "Global (ความรู้สึกรวมของทั้งตลาด)", "Ticker": "Ticker (เฉพาะข้อความที่พูดถึงสินทรัพย์นั้น)", "compare": "เปรียบเทียบ Global กับ Ticker"}


def compare_view(measure):
    """Global next to Ticker (the only two panels left), in the pattern of the single heat map: every cell shows, for Spearman and for Win Rate, how much Ticker is above (+) or below (-)
    Global and the two values themselves; the measure picked above sets the colour (Ticker - Global) and is the one printed bold."""
    cols = ["ticker", "target", "spearman_rho", "winrate", "n", "win_n"]
    both = stat_all[stat_all.ticker.isin(tickers)][cols].merge(stat_ticker[stat_ticker.ticker.isin(tickers)][cols], on=["ticker", "target"], suffixes=("_g", "_t"))
    d = both.dropna(subset=["spearman_rho_g", "spearman_rho_t"], how="all").copy()
    d = d[d[["spearman_rho_g", "spearman_rho_t", "winrate_g", "winrate_t"]].notna().any(axis=1)]
    if d.empty:
        st.info("ไม่มีช่องที่ทั้งสอง panel คำนวณได้พร้อมกัน (ข้อมูลน้อยเกินไปหรือไม่มีชั่วโมงที่ผ่านตัวกรอง) โปรดขยายช่วงเวลา")
        return
    d["period"] = d.target.map(TARGET_LABEL)
    d["asset"] = [asset_label(t) for t in d.ticker]
    d["d_s"] = d.spearman_rho_t - d.spearman_rho_g
    d["d_w"] = d.winrate_t - d.winrate_g
    color_col, scale = ("d_w", 5.0) if measure == "Win Rate" else ("d_s", 0.1)
    d["diff"] = d[color_col]
    d["dark"] = dark_cell(d["diff"], [-scale, scale])
    num = lambda v, f: "-" if pd.isna(v) else f % v
    d["lab_ds"] = ["S  Ticker − Global = " + num(v, "%+.3f") for v in d.d_s]
    d["lab_vs"] = ["Global " + num(a, "%+.3f") + " · Ticker " + num(b, "%+.3f") for a, b in zip(d.spearman_rho_g, d.spearman_rho_t)]
    d["lab_dw"] = ["W  Ticker − Global = " + num(v, "%+.1f") + " จุด" for v in d.d_w]
    d["lab_vw"] = ["Global " + num(a, "%.1f") + "% · Ticker " + num(b, "%.1f") + "%" for a, b in zip(d.winrate_g, d.winrate_t)]
    d["lab_n"] = [("⚠ " if min(x, y) < 30 else "") + "n %s · %s" % ("{:,}".format(int(x)), "{:,}".format(int(y))) for x, y in zip(d.n_g.fillna(0), d.n_t.fillna(0))]
    order = [TARGET_LABEL[t] for t in data.STAT_TARGETS]
    chart = alt.Chart(d).encode(x=alt.X("period:O", sort=order, title=None, axis=alt.Axis(labelAngle=0, orient="top")),
                                y=alt.Y("asset:N", sort=[asset_label(t) for t in ORDER], title=None, axis=alt.Axis(labelLimit=220)))
    valid = "isValid(datum.diff)"
    tips = ["asset", "period", alt.Tooltip("spearman_rho_g:Q", title="Spearman Global", format="+.4f"), alt.Tooltip("spearman_rho_t:Q", title="Spearman Ticker", format="+.4f"),
            alt.Tooltip("winrate_g:Q", title="Win Rate Global (%)", format=".2f"), alt.Tooltip("winrate_t:Q", title="Win Rate Ticker (%)", format=".2f"),
            alt.Tooltip("n_g:Q", title="n ของ Global", format=","), alt.Tooltip("n_t:Q", title="n ของ Ticker", format=",")]
    rect = chart.mark_rect().transform_filter(valid).encode(
        color=alt.Color("diff:Q", title="Ticker − Global (%s)" % ("จุดเปอร์เซ็นต์" if measure == "Win Rate" else "ρ"), scale=alt.Scale(domain=[-scale, scale], scheme="redyellowgreen", clamp=True)),
        tooltip=tips)
    layers = [rect]
    for line, field, bold in ((-26, "lab_ds", measure == "Spearman"), (-12, "lab_vs", False), (4, "lab_dw", measure == "Win Rate"), (18, "lab_vw", False), (32, "lab_n", False)):
        layers.append(chart.mark_text(fontSize=11 if bold else 9, fontWeight="bold" if bold else "normal", dy=line).transform_filter(valid).encode(
            text=field + ":N", color=ink("#222222" if bold else "#555555"), tooltip=tips))
    common.show(alt.layer(*layers).properties(height=(HEATMAP_ROW + 16) * len(ORDER) + HEATMAP_ROOM))   # five lines of text per cell: 16 px more per row than `heatmap`
    higher, total = int((d["diff"] > 0).sum()), int(d["diff"].notna().sum())
    st.caption("**สรุป:** Ticker สูงกว่า Global ใน %d จาก %d ช่อง (ต่ำกว่า %d ช่อง)" % (higher, total, int((d["diff"] < 0).sum())))


common.block("ความสัมพันธ์ระหว่างความรู้สึกกับผลตอบแทน รายสินทรัพย์และรายช่วงเวลา",
             "ใช้ตรวจสอบว่าความรู้สึกของ Reddit สัมพันธ์กับผลตอบแทนของแต่ละสินทรัพย์ในช่วงเวลาต่าง ๆ หรือไม่ (★ = ผ่านการทดสอบหลังปรับ BH)",
             how="Spearman = สหสัมพันธ์อิงอันดับของความรู้สึกกับผลตอบแทน (−1 ถึง +1, 0 = ไม่สัมพันธ์) ใช้ได้กับข้อมูลที่ไม่เป็นแจกแจงปกติ, "
                 "ช่วงเชื่อมั่น 95% ของ ρ มาจากการสุ่มทั้งวันใส่คืน 1,000 รอบ (ถ้าช่วงไม่คร่อม 0 แปลว่าสัมพันธ์จริง), Win Rate = ร้อยละของชั่วโมงที่ทิศความรู้สึกตรงกับทิศราคา (50% = เดาสุ่ม) · "
                 "แต่ละช่องมี p-value เพื่อตรวจว่าความสัมพันธ์น่าจะเกิดจากความบังเอิญหรือไม่ (ของ Spearman คิดว่าชั่วโมงติดกันคล้ายกันด้วยการเลื่อนอนุกรมความรู้สึกแบบวงกลมทุกระยะ), "
                 "BH = ปรับ p-value เมื่อทดสอบหลายคู่พร้อมกัน, n = จำนวนชั่วโมงที่ใช้คำนวณ (⚠ = น้อยกว่า 30)")
kind = None
with common.sticky_bar("p5_bar"):                                                  # the picker of the panel and of the measure stays at the top while the heat map scrolls
    family = st.radio("ข้อความที่ใช้ (panel ตามตาราง 12)", list(FAMILIES), format_func=FAMILIES.get, horizontal=True, key="p5_family_all")
    KINDS = data.PANEL_VARIANTS if family != "Ticker" else {k: v for k, v in data.PANEL_VARIANTS.items() if k != "baseline"}       # the random baseline is a view of Global only
    if family == "compare":
        measure = st.radio("ตัวชี้วัด", VIEWS, horizontal=True, key="p5_cmp_measure")
    else:
        kind = st.radio("ชนิดข้อความ", list(KINDS), format_func=KINDS.get, horizontal=True, key="p5_panel") if SHOW_PANEL_KIND else "all"
        measure = st.radio("ตัวชี้วัด", VIEWS, horizontal=True, key="p5_measure_all")
if family == "compare":
    compare_view(measure)
elif kind == "all":
    chosen = stat_all if family == "global" else stat_ticker                       # the panels that follow the sidebar: the cards above
else:                                                                              # the fixed panels: their own cut of table 12, whatever the two thresholds of the sidebar say
    chosen = common.panel_stat(family, kind, tuple(tickers), start, end, tuple(communities), model, tuple(statuses),
                               0.0, 0.0, tuple(content_types), predictor, 0)
    if kind == "baseline":
        pass
    else:
        rule = {"strong": "ตัดแถว (ชั่วโมง × สินทรัพย์) ที่ |Sentiment Score เฉลี่ยของชั่วโมง| ต่ำกว่า 0.05 ออก",
                "quality": "เก็บเฉพาะแถวที่ |Sentiment Score เฉลี่ยของชั่วโมง| ตั้งแต่ 0.30",
                "spike": "เก็บเฉพาะแถวของชั่วโมงที่ Reddit Volume Z-score > 1.5"}[kind]
if family != "compare":
    panel_view(chosen, measure)


# ---- the ranking of the assets (proposal 7.5 dashboard 2): the panel Global (every text of the market) after every filter, sortable --------------
common.block("จัดอันดับสินทรัพย์",
             "ใช้ตรวจสอบว่าสินทรัพย์ใดมีความสัมพันธ์ระหว่างความรู้สึกกับผลตอบแทนชัดเจนที่สุด (คลิกหัวคอลัมน์เพื่อเรียงลำดับ)")
own_frame = data.sentiment_frame(q("sentiment_hourly", tuple(tickers), start, end, tuple(communities), model, "all", tuple(content_types)), start, end)
reddit_volume = own_frame.groupby("series").texts.sum()                               # Reddit volume of the asset: the posts and comments that mention it, in the range
trading_volume = prices.groupby("ticker").volume.mean()                                # trading volume of the asset: the mean per hour of the range (the units differ per asset)
ranking = stat_all[stat_all.ticker.isin(tickers)].copy()
if ranking.empty or ranking.winrate.notna().sum() == 0:
    st.info("ไม่มีสินทรัพย์ที่มีข้อมูลพอ ตามตัวกรองที่เลือก")
else:
    st.session_state.setdefault("p5_rank_h", "Current Return")
    horizon = st.radio("Horizon ของ Spearman และ Win Rate", [TARGET_LABEL[t] for t in data.STAT_TARGETS], horizontal=True, key="p5_rank_h")
    one = ranking[ranking.target.map(TARGET_LABEL) == horizon].set_index("ticker")                 # the mean return follows the same horizon (the hours that pass the filters)
    RETURN_NAME = "ผลตอบแทนเฉลี่ย %s (%%)" % horizon
    table = pd.DataFrame({
        "กลุ่ม": one.index.map(lambda t: GROUP_LABELS.get(group_of.get(t), "")), "สินทรัพย์": one.index,
        "Reddit Volume (ข้อความที่พูดถึง)": one.index.map(reddit_volume), "Trading Volume (เฉลี่ยต่อชั่วโมง)": one.index.map(trading_volume),
        "Spearman ρ": one.spearman_rho.values, "ช่วงเชื่อมั่น 95% ต่ำ": one.spearman_ci_low.values, "ช่วงเชื่อมั่น 95% สูง": one.spearman_ci_high.values,
        "p เลื่อนวงกลม (Spearman)": one.spearman_p_shift.values, "Win Rate (%)": one.winrate.values,
        "p ดิบ (Win Rate)": one.win_p.values, "p ปรับ BH (Win Rate)": one.win_bh.values,
        "นัยสำคัญหลังปรับ": np.where(one.win_bh.values < 0.05, "★", ""),
        "n (Win Rate)": one.win_n.values, "n น้อย": np.where((one.win_n.values < 30) | (one.n.values < 30), "⚠", ""),
        RETURN_NAME: one.mean_return.values})
    table = table.sort_values("p ปรับ BH (Win Rate)", na_position="last")
    formats = {"Reddit Volume (ข้อความที่พูดถึง)": "{:,.0f}", "Trading Volume (เฉลี่ยต่อชั่วโมง)": "{:,.0f}", "n (Win Rate)": "{:,.0f}", "Win Rate (%)": "{:.1f}",
               "p ดิบ (Win Rate)": "{:.3f}", "p ปรับ BH (Win Rate)": "{:.3f}", "Spearman ρ": "{:+.3f}", "ช่วงเชื่อมั่น 95% ต่ำ": "{:+.3f}", "ช่วงเชื่อมั่น 95% สูง": "{:+.3f}", "p เลื่อนวงกลม (Spearman)": "{:.3f}",
               RETURN_NAME: "{:+.4f}"}
    st.dataframe(table.style.format(formats, na_rep="-"), hide_index=True, width="stretch", height=420)


