"""Dashboard 7.5-2  Ranking and Detection Configuration  (proposal 7.5 + the signal list of 7.6).

  * Ranking of the assets by Historical Win Rate / Binomial p-value / Future Return / Reddit Volume Z-score for the
    chosen horizon, split by asset class.
  * Three controls - Z-score Threshold, Sentiment Threshold, Horizon - that re-run the signal detection immediately
    (analysis.signals.detect on the cached ticker-hour table, well under 2 seconds).
    The values of the pre-computed grid (configs/detection.yaml) give exactly the rows stored in `signal_events`.
Win rate / p-value / correlation are FULL-SAMPLE historical statistics of the asset (A1/A2, panel_Ticker). They are
context for reading a signal, not a confirmation of any return and not investment advice.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from analysis import signals  # noqa: E402
from dashboard import common  # noqa: E402
from dashboard.common import GROUP_LABELS, q  # noqa: E402

common.setup("Ranking and Signals: จัดอันดับและตั้งค่าเกณฑ์ตรวจจับสัญญาณ", "🚦")
# dimensions of the dashboard (table 17): DimTime, DimTicker, DimDetectionConfig, DimMajoritySentiment
_, start, end, _ = common.sidebar(multi=True, detection="signals", majority=True)
tickers = common.selected_tickers()
statuses = common.selected_statuses()
if not tickers or not statuses:
    common.nothing_selected(["จำนวนสัญญาณที่ตรวจพบ", "จำนวนสินทรัพย์ที่เข้าเงื่อนไข", "ชนิดสัญญาณที่พบ"],
                            "ไม่ได้เลือกหลักทรัพย์หรือประเภทความรู้สึกส่วนใหญ่ จึงไม่มีข้อมูลแสดง")

# ---- DimDetectionConfig (sidebar): Z-score Threshold, Sentiment Threshold, Horizon -------------------------------
grid = signals.GRID
z_th = st.session_state.get("s_z", 1.5)
s_th = st.session_state.get("s_s", 0.30)
horizon = st.session_state.get("s_h", grid["horizons"][0])

# ---- detection (on demand) ----------------------------------------------------------------------------------
panel = q("signal_panel")
found = signals.detect(panel, z_th, s_th)
found = found[(found.hour_utc >= start) & (found.hour_utc <= end) & found.ticker.isin(tickers)
              & found.majority_final_status.isin(statuses)]

stats = q("ranking_table")
stats = stats[stats.horizon == horizon][["ticker", "winrate", "p_value", "correlation", "n_samples"]]
period = q("ticker_period_stats", start, end, horizon)
universe = q("tickers")

common.kpi_cards([("จำนวนสัญญาณที่ตรวจพบ", "{:,}".format(len(found)), None),
                  ("จำนวนสินทรัพย์ที่เข้าเงื่อนไข", str(found.ticker.nunique()), None),
                  ("ชนิดสัญญาณที่พบ", str(found.signal_type.nunique()), None)])

if found.empty:
    st.info("ไม่พบสัญญาณตามเกณฑ์นี้ในช่วงที่เลือก ลองลดเกณฑ์หรือขยายช่วงเวลา")
else:
    by_type = found.groupby(["signal_type", "signal_level"]).size().reset_index(name="n")
    chart = (alt.Chart(by_type).mark_bar().encode(
        x=alt.X("n:Q", title="จำนวนสัญญาณ"), y=alt.Y("signal_type:N", title=None),
        color=alt.Color("signal_level:N", sort=["low", "medium", "high"], title="ระดับ",
                        scale=alt.Scale(domain=["low", "medium", "high"], range=["#9ecae1", "#fdae6b", "#d62728"])),
        tooltip=["signal_type", "signal_level", "n"]).properties(height=200))
    common.show(chart, width="stretch")
    by_group = found.groupby("big_group").agg(สัญญาณ=("ticker", "size"), สินทรัพย์=("ticker", "nunique")).reset_index()
    by_group["big_group"] = by_group.big_group.map(GROUP_LABELS)
    st.dataframe(by_group.rename(columns={"big_group": "กลุ่ม"}), hide_index=True, width="stretch")

# ---- ranking ------------------------------------------------------------------------------------------------
st.subheader("จัดอันดับสินทรัพย์ (Horizon %s)" % horizon)
count = found.groupby("ticker").size().rename("signals") if not found.empty else pd.Series(dtype=int, name="signals", index=pd.Index([], name="ticker"))
rank = (universe.merge(stats, on="ticker", how="left").merge(period, on="ticker", how="left")
        .merge(count, on="ticker", how="left"))
rank = rank[rank.ticker.isin(tickers)].copy()
rank["signals"] = rank.signals.fillna(0).astype(int)
order = st.selectbox("เรียงตาม", ["Historical Win Rate (%)", "p-value (น้อย→มาก)", "Future Return เฉลี่ย (%)",
                                   "Volume Z-score เฉลี่ย", "จำนวนสัญญาณ"], key="s_order")
sort_col, ascending = {"Historical Win Rate (%)": ("winrate", False), "p-value (น้อย→มาก)": ("p_value", True),
                       "Future Return เฉลี่ย (%)": ("mean_future_return_pct", False),
                       "Volume Z-score เฉลี่ย": ("mean_zscore", False), "จำนวนสัญญาณ": ("signals", False)}[order]
rank = rank.sort_values(sort_col, ascending=ascending, na_position="last")
rank["กลุ่ม"] = rank.big_group.map(GROUP_LABELS)
view = rank[["ticker", "กลุ่ม", "winrate", "p_value", "correlation", "n_samples", "mean_future_return_pct", "mean_zscore",
             "signals"]].rename(columns={
    "winrate": "Historical Win Rate (%)", "p_value": "p-value", "correlation": "Spearman ρ", "n_samples": "จำนวนเหตุการณ์",
    "mean_future_return_pct": "Future Return เฉลี่ย (%)", "mean_zscore": "Volume Z-score เฉลี่ย", "signals": "สัญญาณ"})
common.table(view.round(4), hide_index=True, width="stretch", height=420)
st.caption("ช่องว่าง = ข้อมูลไม่เพียงพอ (น้อยกว่า 30 เหตุการณ์) ไม่ใช่ 0  \nWin Rate ≈ 50% คือระดับเดียวกับการสุ่มทิศทาง  \n"
           "p-value เป็นค่าเชิงพรรณนา (ข้อมูลรายชั่วโมงเกี่ยวเนื่องกันและกรอบเวลาซ้อนทับ) อย่าตีความว่าใช้ทำนายได้")

# ---- the signal list (table 18) ----------------------------------------------------------------------------
st.subheader("รายการสัญญาณที่ตรวจพบ (ล่าสุด 300 รายการ)")
if not found.empty:
    listing = (found.merge(stats, on="ticker", how="left").sort_values("hour_utc", ascending=False).head(300).copy())
    listing["timestamp"] = pd.to_datetime(listing.hour_utc, unit="s", utc=True).dt.strftime("%Y-%m-%d %H:%M")
    listing["horizon"] = horizon
    common.table(listing[["timestamp", "ticker", "big_group", "signal_type", "signal_level", "sentiment_mean",
                          "reddit_volume", "reddit_volume_zscore_24", "horizon", "winrate", "correlation"]].rename(
        columns={"reddit_volume_zscore_24": "reddit_volume_zscore", "correlation": "correlation_value"}).round(3),
        hide_index=True, width="stretch", height=380)
    st.caption("winrate / correlation_value = สถิติย้อนหลังเต็มช่วงของสินทรัพย์นั้น ณ Horizon ที่เลือก "
               "ไม่ถือเป็นการยืนยันผลตอบแทนหรือคำแนะนำการลงทุน")
