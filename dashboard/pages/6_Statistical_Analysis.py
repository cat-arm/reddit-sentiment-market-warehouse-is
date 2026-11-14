"""Dashboard 7.5-2  Statistical Analysis  (proposal 7.5 dashboard 2 "Ranking and Detection Configuration", table 17: Historical Win Rate, p-value per asset and
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
CARDS = ["Historical Win Rate", "Spearman p-value", "Pearson p-value"]
if not tickers or not communities or not statuses or not content_types:
    common.nothing_selected(CARDS, "ยังไม่ได้เลือกหลักทรัพย์ ชุมชน หรือประเภทความรู้สึกส่วนใหญ่ จึงไม่มีข้อมูลแสดง")
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

prices = q("price_series_for", tickers, start, end)
if prices.empty:
    common.kpi_cards([(c, "n/a", None) for c in CARDS])
    st.info("ไม่มีข้อมูลราคาของหลักทรัพย์ที่เลือกในช่วงนี้ (ตลาดอาจปิด)")
    st.stop()
def stat(family, variant):
    return common.panel_stat(family, variant, tuple(tickers), start, end, tuple(communities), model, tuple(statuses), z_th, s_th,
                      tuple(content_types), predictor, v_th)


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
        return (label, "n/a" if p.empty else "{:.3f}".format(p.median()),
                "ค่ากลางของ p-value ทุกคู่ (สินทรัพย์ × Horizon ล่วงหน้า) ที่เลือก โดย p ต่ำกว่า 0.05 ใน %d จาก %d คู่ (ก่อนปรับ BH)  \n"
                "หากความรู้สึกไม่เกี่ยวกับราคา ค่ากลางควรอยู่ราว 0.5" % (n_sig, n_tests))

    common.kpi_cards([
        ("Historical Win Rate", "n/a" if not wins else "{:.1f}%".format(100.0 * hits / wins),
         "สัดส่วนชั่วโมงที่ทิศทางของความรู้สึกตรงกับทิศทางผลตอบแทนอนาคต (ทุก Horizon รวมกัน)  \n50%% เท่ากับการสุ่ม  \np-value ของทั้งชุดเท่ากับ %s"
         % ("n/a" if np.isnan(win_p) else "{:.3f}".format(win_p))),
        p_card("spearman_p", "Spearman p-value"), p_card("pearson_p", "Pearson p-value")])
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


def panel_view(stat, measure):
    """The content of one panel: the heat map of the measure that is picked in the sticky bar above."""
    if stat.empty or stat.n.fillna(0).sum() == 0:
        st.info("ไม่มีข้อมูลเพียงพอสำหรับ panel นี้ตามตัวกรองที่เลือก (ไม่มีชั่วโมงที่ผ่านตัวกรองและมีทั้งความรู้สึกกับราคา โปรดขยายช่วงเวลาหรือลดเกณฑ์)")
        return
    if stat[stat.ticker.isin(tickers)][BASE[measure][0]].notna().sum() == 0:
        st.info("ไม่มีค่า %s ของสินทรัพย์ที่เลือกใน panel นี้ (ข้อมูลน้อยกว่า 3 ชั่วโมงต่อคู่ คำนวณสหสัมพันธ์ไม่ได้)" % measure)
        return
    common.show(heatmap(stat, measure))


st.radio("วัดความรู้สึกด้วย", list(PREDICTOR_OF), horizontal=True, key="p5_basis")

# ---- the nine panels of table 12 in two layers: the family (Global / Ticker / Baseline), then the kind of text (all / strong / quality / spike) ------------
FAMILIES = {"global": "Global (ความรู้สึกรวมของทั้งตลาด)", "Ticker": "Ticker (เฉพาะข้อความที่พูดถึงสินทรัพย์นั้น)", "compare": "เปรียบเทียบ 2 panel"}
PANEL_CHOICES = {"%s:%s" % (f, k): "%s · %s" % ("Global" if f == "global" else "Ticker", v) for f in ("global", "Ticker") for k, v in data.PANEL_VARIANTS.items()
                 if not (f == "Ticker" and k == "baseline")}


def panel_table(choice):
    """The statistics table of one of the nine panels ('global:all', 'Ticker:strong', 'global:baseline', ...): the two panels "all" follow the sidebar, the others are fixed."""
    fam, kd = choice.split(":")
    if kd == "all":
        return stat_all if fam == "global" else stat_ticker
    return common.panel_stat(fam, kd, tuple(tickers), start, end, tuple(communities), model, tuple(statuses), 0.0, 0.0, tuple(content_types), predictor, 0)


def compare_pickers():
    """The two selectboxes of the comparison (drawn in the sticky bar): A = the base, B = compared with A."""
    st.session_state.setdefault("p5_cmp_a", "global:baseline")                # the base: the random direction
    st.session_state.setdefault("p5_cmp_b", "global:all")                     # compared with: every text, as the sidebar thresholds set it
    left, right = st.columns(2)
    a_key = left.selectbox("A (ฝั่งซ้าย ฐานเปรียบเทียบ)", list(PANEL_CHOICES), format_func=PANEL_CHOICES.get, key="p5_cmp_a")
    b_key = right.selectbox("B (ฝั่งขวา เทียบกับ A)", list(PANEL_CHOICES), format_func=PANEL_CHOICES.get, key="p5_cmp_b")
    return a_key, b_key


def compare_view(a_key, b_key, measure):
    """Two panels as one heat map of the difference B - A for the measure picked in the sticky bar."""
    if a_key == b_key:
        st.info("เลือก panel สองอันที่ต่างกัน")
        return
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
    table = pd.DataFrame({"สินทรัพย์": d.ticker, "Horizon": d.period, "A": d.a, "B": d.b, "B − A": d["diff"], "เปอร์เซ็นต์เทียบ A (%)": d.rel if pct else np.nan,
                          "n A": d.na, "n B": d.nb, "n น้อย": np.where((d.na < 30) | (d.nb < 30), "⚠", "")}).sort_values("B − A", ascending=False)
    if not pct:
        table = table.drop(columns="เปอร์เซ็นต์เทียบ A (%)")
    formats = {"A": "{:" + fmt + "}", "B": "{:" + fmt + "}", "B − A": "{:+.3f}" if not pct else "{:+.2f}", "n A": "{:,.0f}", "n B": "{:,.0f}", "เปอร์เซ็นต์เทียบ A (%)": "{:+.1f}"}
    st.dataframe(table.style.format(formats, na_rep="-"), hide_index=True, width="stretch", height=320)


kind = None
with common.sticky_bar("p5_bar"):                                                  # the picker of the panel and of the measure stays at the top while the heat map scrolls
    family = st.radio("ข้อความที่ใช้ (panel ตามตาราง 12)", list(FAMILIES), format_func=FAMILIES.get, horizontal=True, key="p5_family_all")
    KINDS = data.PANEL_VARIANTS if family != "Ticker" else {k: v for k, v in data.PANEL_VARIANTS.items() if k != "baseline"}       # the random baseline is a view of Global only
    if family == "compare":
        a_key, b_key = compare_pickers()
        measure = st.radio("ตัวชี้วัด", VIEWS, horizontal=True, key="p5_cmp_measure")
    else:
        kind = st.radio("ชนิดข้อความ", list(KINDS), format_func=KINDS.get, horizontal=True, key="p5_panel")
        measure = st.radio("ตัวชี้วัด", VIEWS, horizontal=True, key="p5_measure_all")
if family == "compare":
    compare_view(a_key, b_key, measure)
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
st.subheader("จัดอันดับสินทรัพย์ (คลิกที่หัวคอลัมน์เพื่อเรียง)")
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
        "p ดิบ (Win Rate)": one.win_p.values, "p ปรับ BH (Win Rate)": one.win_bh.values,
        "นัยสำคัญหลังปรับ": np.where(one.win_bh.values < 0.05, "★", ""),
        "n (Win Rate)": one.win_n.values, "n น้อย": np.where((one.win_n.values < 30) | (one.n.values < 30), "⚠", ""),
        RETURN_NAME: one.mean_return.values})
    table = table.sort_values("p ปรับ BH (Win Rate)", na_position="last")
    formats = {"Reddit Volume (ข้อความที่พูดถึง)": "{:,.0f}", "Trading Volume (เฉลี่ยต่อชั่วโมง)": "{:,.0f}", "n (Win Rate)": "{:,.0f}", "Win Rate (%)": "{:.1f}",
               "p ดิบ (Win Rate)": "{:.3f}", "p ปรับ BH (Win Rate)": "{:.3f}", "Spearman ρ": "{:+.3f}", "Pearson ρ": "{:+.3f}",
               RETURN_NAME: "{:+.4f}"}
    st.dataframe(table.style.format(formats, na_rep="-"), hide_index=True, width="stretch", height=420)


