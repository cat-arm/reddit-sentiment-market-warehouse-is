"""Dashboard 7.5-1  Market and Sentiment Overview  (proposal 7.5: close, volume, sentiment_mean, pos/neg/neu ratio,
majority status, Reddit_volume, Volume Z-score, Sentiment Momentum).

Questions answered: is the community positive or negative in the chosen period, which assets are the most positive /
negative, and does the majority sentiment of an hour agree with the direction of the following return?
Sentiment here = only the texts that MENTION the selected ticker (ticker-level, all texts).
Data: merged_hourly_panel (scope = ticker, variant = all).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard import common  # noqa: E402
from dashboard.common import GROUP_LABELS, q  # noqa: E402

common.setup("Market and Sentiment: ภาพรวมตลาดและความรู้สึก", "🧭")
ticker, start, end, groups = common.sidebar()
how = common.granularity(start, end, "g_sent")
# Page-specific controls live in the MAIN area (like the thresholds of the ranking page); the sidebar holds only the
# central filters, identical on every page.
statuses = st.multiselect("เลือกเฉพาะชั่วโมงที่ประเภทความรู้สึกส่วนใหญ่เป็น", ["positive", "negative", "neutral"],
                          default=["positive", "negative", "neutral"], key="f_majority")

series = q("overview_series", ticker, start, end)
if series.empty:
    st.info("ไม่มีข้อมูลของ %s ในช่วงนี้" % ticker)
    st.stop()

# hours whose majority status is not selected lose their sentiment (price stays); hours without text keep NULL
mask = series.majority_final_status.isin(statuses) | series.majority_final_status.isna()
series = series.assign(sentiment_mean=series.sentiment_mean.where(mask))


def weighted_resample(df, how):
    """Sentiment of a day / week / month / year = mean of the hourly values weighted by the number of texts (hours with
    text only)."""
    if how == "Hourly":
        return df
    d = df.copy()
    has = d.sentiment_mean.notna()
    for col in ("sentiment_mean", "pos_ratio", "neg_ratio", "neu_ratio"):
        d[col + "_w"] = (d[col] * d.reddit_volume).where(has)
    d["texts_w"] = d.reddit_volume.where(has)
    daily = d.set_index("time").resample(**common.RESAMPLE[how]).agg({
        "close": "last", "volume": "sum", "reddit_volume": "sum", "zscore": "max", "momentum": "mean",
        **{c + "_w": "sum" for c in ("sentiment_mean", "pos_ratio", "neg_ratio", "neu_ratio")}, "texts_w": "sum"})
    for col in ("sentiment_mean", "pos_ratio", "neg_ratio", "neu_ratio"):
        daily[col] = (daily[col + "_w"] / daily["texts_w"]).where(daily["texts_w"] > 0)   # no text -> NULL, not 0
    return daily.reset_index()


shown = weighted_resample(series, how)
st.subheader("%s: ราคาปิดเทียบค่าความรู้สึกเฉลี่ย" % ticker)
if shown.sentiment_mean.notna().sum() == 0:
    st.info("ไม่มีข้อความที่พูดถึง %s ในช่วงนี้ จึงแสดงเฉพาะราคา" % ticker)
    st.altair_chart(common.line(shown, "time", "close", "ราคาปิด (USD)"), width="stretch")
else:
    st.altair_chart(common.dual_axis(shown, "time", "close", "sentiment_mean", "ราคาปิด (USD)", "Sentiment Score"),
                    width="stretch")
    st.caption("เส้นน้ำเงิน = ราคาปิด  \nเส้นแดง = Sentiment Score (ผลรวม final_sentiment ÷ จำนวนข้อความของชั่วโมงนั้น) "
               "ช่วงที่เส้นแดงขาด = ไม่มีข้อความ ไม่ใช่ค่ากลาง")

k1, k2, k3, k4 = st.columns(4)
text_hours = series.sentiment_mean.notna().sum()
k1.metric("ชั่วโมงที่มีข้อความ", "{:,} / {:,}".format(int(text_hours), len(series)))
w = series.reddit_volume.where(series.sentiment_mean.notna())
k2.metric("Sentiment Score เฉลี่ย", "n/a" if not w.sum() else "{:+.3f}".format((series.sentiment_mean * w).sum() / w.sum()))
k3.metric("Sentiment Momentum เฉลี่ย", common.money(series.momentum.mean()))
k4.metric("Reddit Volume Z-score สูงสุด", common.money(series.zscore.max()))

st.subheader("สัดส่วนความคิดเห็นเชิงบวก / ลบ / เป็นกลาง")
ratios = shown.melt(id_vars="time", value_vars=["pos_ratio", "neg_ratio", "neu_ratio"], var_name="ประเภท",
                    value_name="สัดส่วน").dropna()
ratios["ประเภท"] = ratios["ประเภท"].map({"pos_ratio": "บวก", "neg_ratio": "ลบ", "neu_ratio": "เป็นกลาง"})
if not ratios.empty:
    area = (alt.Chart(ratios).mark_area().encode(
        x=alt.X("time:T", title=None), y=alt.Y("สัดส่วน:Q", stack="normalize", axis=alt.Axis(format="%")),
        color=alt.Color("ประเภท:N", scale=alt.Scale(domain=["บวก", "ลบ", "เป็นกลาง"],
                                                    range=["#2ca02c", "#d62728", "#7f7f7f"])),
        tooltip=["time:T", "ประเภท", alt.Tooltip("สัดส่วน:Q", format=".1%")]).properties(height=240))
    st.altair_chart(area, width="stretch")

left, right = st.columns(2)
with left:
    st.subheader("ประเภทความรู้สึกส่วนใหญ่ (จำนวนชั่วโมง)")
    maj = series.majority_final_status.value_counts().rename_axis("ประเภท").reset_index(name="ชั่วโมง")
    common.table(maj, hide_index=True, width="stretch")
with right:
    st.subheader("ปริมาณการกล่าวถึง")
    st.altair_chart(common.line(shown, "time", "reddit_volume", "Reddit Volume (ข้อความ)", "#ff7f0e", 200),
                    width="stretch")

st.subheader("ประเภทความรู้สึกส่วนใหญ่ สอดคล้องกับทิศทางผลตอบแทนอนาคตหรือไม่")
mv = q("majority_vs_return", ticker, start, end)
if mv.empty:
    st.info("ไม่มีข้อมูลเพียงพอ")
else:
    table = mv.pivot(index="majority", columns="horizon", values="share_up").reindex(columns=list(common.data.HORIZONS))
    counts = mv.pivot(index="majority", columns="horizon", values="n").reindex(columns=list(common.data.HORIZONS))
    st.write("สัดส่วนชั่วโมงที่ผลตอบแทนอนาคตเป็นบวก (แยกตามประเภทความรู้สึกส่วนใหญ่)")
    st.dataframe((table * 100).map(lambda v: "n/a" if pd.isna(v) else "%.1f" % v), width="stretch")
    st.caption("ถ้าความรู้สึกบวกนำราคา แถว positive ควรสูงกว่าแถว negative  \nจำนวนตัวอย่างต่อช่อง: "
               + ", ".join("%s/%s=%s" % (i, c, "{:,}".format(int(counts.loc[i, c]))) for i in counts.index
                           for c in counts.columns if pd.notna(counts.loc[i, c]))[:400])

st.subheader("สินทรัพย์ใดมีความรู้สึกเชิงบวก/ลบมากที่สุดในช่วงนี้")
rank = q("sentiment_by_ticker", start, end)
rank = rank[rank.big_group.isin(groups)].copy()
rank["กลุ่ม"] = rank.big_group.map(GROUP_LABELS)
common.table(rank[["ticker", "กลุ่ม", "mean_sentiment", "pos_ratio", "neg_ratio", "hours_with_text", "texts"]].rename(
    columns={"mean_sentiment": "Sentiment Score เฉลี่ย", "pos_ratio": "สัดส่วนบวก", "neg_ratio": "สัดส่วนลบ",
             "hours_with_text": "ชั่วโมงที่มีข้อความ", "texts": "ข้อความ"}).round(3), hide_index=True,
    width="stretch", height=330)
