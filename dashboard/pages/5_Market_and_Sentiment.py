"""Dashboard 7.5-1  Market and Sentiment Overview  (proposal 7.5: close, volume, sentiment_mean, pos/neg/neu ratio,
majority status, Reddit_volume, Volume Z-score, Sentiment Momentum).

Dimensions of the dashboard (table 17): DimTime, DimTicker, DimSentimentSource, DimDetectionConfig, DimMajoritySentiment.  They are the
four blocks of the sidebar: time range and level; asset classes and tickers (several tickers are taken together);
communities of the sentiment source (and the model: VADER+FinBERT, VADER or FinBERT); majority status of the hour.
Sentiment here = only the texts that MENTION the chosen tickers.  It is recombined from `reddit_hourly_community`
(sums per community), so any choice of communities is exact; with every community ticked it equals the stored KPIs.
Several tickers: one combined series (texts of all of them summed, price as an index) plus a table per ticker.
Data: reddit_hourly_community, market_hourly_features.
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

common.setup("Market and Sentiment (ภาพรวมตลาดและความรู้สึก)", "🧭")
_, start, end, _ = common.sidebar(multi=True, sentiment=True, detection="overview", majority=True)
how = common.granularity(start, end, "g_sent")
tickers = common.selected_tickers()
communities = common.selected_communities()
statuses = common.selected_statuses()
content_types = common.selected_content_types()
z_th = st.session_state.get("d_z", 0.0)                 # DimDetectionConfig: filters the hours (0 = no filter)
v_th = int(st.session_state.get("d_v", 0))             # the Reddit Volume Threshold: hours with fewer texts in the whole market are dropped
s_th = common.sentiment_cut()                           # a float (absolute) or the name of the signed variant
if not tickers or not communities or not statuses or not content_types:
    common.nothing_selected(["Sentiment Score", "Sentiment Momentum", "Reddit Volume Z-score สูงสุด"],
                            "ยังไม่ได้เลือกหลักทรัพย์ ชุมชน หรือประเภทความรู้สึกส่วนใหญ่ จึงไม่มีข้อมูลแสดง")
one = len(tickers) == 1
names = dict(zip(q("tickers").ticker, q("tickers").name))
label = tickers[0] if one else "รวม %d ตัว" % len(tickers)

# ---- prices of the ticked tickers (hours with a valid bar) and the sentiment KPIs recombined from the chosen communities
prices = q("price_series_for", tickers, start, end)
sent = q("sentiment_hourly", tickers, start, end, communities, common.selected_model(), common.text_variant(), content_types)      # the texts that pass the Sentiment Threshold
sent_all = q("sentiment_hourly", tickers, start, end, communities, common.selected_model(), "all", content_types) if common.text_variant() != "all" else None   # the volume stays that of ALL the texts
if prices.empty:
    st.info("ไม่มีข้อมูลราคาของหลักทรัพย์ที่เลือกในช่วงนี้ (ตลาดอาจปิด)")
    st.stop()
market = q("market_zscore", start, end, common.sentiment_source_ids())    # the Z-score of ALL the texts of the hour (the proposal's Reddit_volume), for every series
per_ticker = data.sentiment_frame(sent, start, end, market=market, volume=sent_all)        # one series per ticker
# the same filter on every ticker-hour: an hour that fails the thresholds loses its majority status, so the samples below skip it
per_ticker_kept = per_ticker.assign(majority=per_ticker.majority.where(data.threshold_mask(per_ticker, z_th, 0.0, v_min=v_th)))
series_frame = data.sentiment_frame(sent, start, end, combined=not one, market=market, volume=sent_all)   # what the charts show


def rebased(df):
    """close and volume of every ticker as an index (first close = 100, mean volume = 100): comparable and averageable."""
    out = df[["ticker", "hour_utc", "time", "close", "volume"]].copy()
    first = out.groupby("ticker").close.transform(lambda s: s.dropna().iloc[0] if s.notna().any() else np.nan)
    mean_volume = out.groupby("ticker").volume.transform("mean")
    out["price_index"] = 100.0 * out.close / first
    out["volume_index"] = 100.0 * out.volume / mean_volume
    return out


if one:
    market = prices[["hour_utc", "time", "close", "volume"]].copy()
else:
    idx = rebased(prices)
    market = idx.groupby("hour_utc", as_index=False).agg(time=("time", "first"), close=("price_index", "mean"),
                                                         volume=("volume_index", "mean"))
series = market.merge(series_frame.drop(columns="series"), on="hour_utc", how="left")
series["texts"] = series.texts.fillna(0)
series["sent_texts"] = series.sent_texts.fillna(0)                      # the texts the sentiment is made of (those that pass the Sentiment Threshold)
series = series.rename(columns={"texts": "reddit_volume", "majority": "majority_final_status"})

# hours whose majority status is not ticked lose every Reddit measure (price and market volume stay); no text = NULL
series = data.mask_majority(series, statuses)
# hours that do not meet the thresholds of DimDetectionConfig lose their Reddit measures too (0 / 0 = nothing removed)
series = data.mask_thresholds(series, z_th, 0.0, v_min=v_th)


def weighted_resample(df, how):
    """Sentiment of a day / week / month / year = mean of the hourly values weighted by the number of texts (hours with
    text only)."""
    if how == "Hourly":
        return df
    d = df.copy()
    has = d.sentiment_mean.notna()
    for col in ("sentiment_mean", "pos_ratio", "neg_ratio", "neu_ratio"):
        d[col + "_w"] = (d[col] * d.sent_texts).where(has)
    d["texts_w"] = d.sent_texts.where(has)
    daily = d.set_index("time").resample(**common.RESAMPLE[how]).agg({
        "close": "last", "volume": "sum" if one else "mean", "reddit_volume": "sum", "zscore": "max", "momentum": "mean",
        **{c + "_w": "sum" for c in ("sentiment_mean", "pos_ratio", "neg_ratio", "neu_ratio")}, "texts_w": "sum"})
    for col in ("sentiment_mean", "pos_ratio", "neg_ratio", "neu_ratio"):
        daily[col] = (daily[col + "_w"] / daily["texts_w"]).where(daily["texts_w"] > 0)   # no text -> NULL, not 0
    return daily.reset_index()


shown = weighted_resample(series, how)

# KPI cards first: the three KPIs of dashboard 1 (tables 15 and 17): Sentiment Score, Sentiment Momentum, Reddit Volume Z-score
w = series.sent_texts.where(series.sentiment_mean.notna())
common.kpi_cards([
    ("Sentiment Score", "n/a" if not w.sum() else "{:+.3f}".format((series.sentiment_mean * w).sum() / w.sum()),
     "ผลรวม final_sentiment ÷ จำนวนความคิดเห็น เฉลี่ยถ่วงน้ำหนักด้วยจำนวนข้อความของแต่ละชั่วโมง"),
    ("Sentiment Momentum", common.money(series.momentum.mean()), "(sentiment_mean ชั่วโมงนี้ − ชั่วโมงก่อนหน้า) เฉลี่ย"),
    ("Reddit Volume Z-score สูงสุด", common.money(series.zscore.max()), "เทียบ 24 ชั่วโมงก่อนหน้า ไม่รวมชั่วโมงปัจจุบัน" + common.REDDIT_Z_NOTE)])

# ---- (EXTENSION) the hourly mean of each model on its own: the final Sentiment Score (VADER + FinBERT after the rule that settles the conflicts) and the raw
# score of VADER and of FinBERT, so that one can see how far the two models agree (question 3 of the system 7.3).  The page filters apply (assets, time, communities,
# types of text, Sentiment Threshold); the model button of the sidebar does not: all three are always drawn.
MODEL_LINES = (("VADER+FinBERT", "ผลรวม (กฎรวมผล)", common.C_SENT), ("VADER", "VADER", "#555555"), ("FinBERT", "FinBERT", "#bcbd22"))


def model_series(model):
    sent_m = q("sentiment_hourly", tickers, start, end, communities, model, common.text_variant(), content_types)
    frame = data.sentiment_frame(sent_m, start, end, combined=not one)[["hour_utc", "sentiment_mean", "texts"]]
    frame = frame.assign(time=pd.to_datetime(frame.hour_utc, unit="s", utc=True))
    weight = frame.texts.where(frame.sentiment_mean.notna())
    frame = frame.assign(sw=frame.sentiment_mean * weight, w=weight)
    if how != "Hourly":                                                   # a day / week / ...: the mean of the hours weighted by their number of texts
        frame = common.resample(frame[["time", "sw", "w"]], {"sw": "sum", "w": "sum"}, how)
        frame = frame.assign(sentiment_mean=(frame.sw / frame.w).where(frame.w > 0))
    frame.attrs["overall"] = float(sent_m.sentiment_sum.sum() / sent_m.texts.sum()) if len(sent_m) and sent_m.texts.sum() else float("nan")      # the mean of all the texts of the range
    return frame[["time", "sentiment_mean"]].copy().rename_axis(None)


by_model = {name: model_series(model) for model, name, _ in MODEL_LINES}
overall = {name: by_model[name].attrs.get("overall", float("nan")) for _, name, _ in MODEL_LINES}
st.subheader("ความรู้สึกเฉลี่ยรายชั่วโมงแยกตามแบบจำลอง (%s)" % label)
ticks = st.columns(len(MODEL_LINES))
visible = [(name, color) for (model, name, color), cell in zip(MODEL_LINES, ticks)
           if cell.checkbox("%s (%s)" % (name, common.COLOR_NAMES.get(color, "เทาเข้ม" if color == "#555555" else "เขียวมะกอก")), value=True, key="ms_" + model)]
if not visible:
    st.info("เลือกแสดงอย่างน้อย 1 เส้น")
elif all(by_model[name].sentiment_mean.notna().sum() == 0 for name, _ in visible):
    st.info("ไม่มีข้อความที่พูดถึง %s ในช่วงนี้" % label)
else:
    long = pd.concat([by_model[name].assign(model=name) for name, _ in visible], ignore_index=True).dropna(subset=["sentiment_mean"])
    how_ticks = {"tickCount": common.TICK_STEP[how]} if how in common.TICK_STEP else {}
    lines = alt.Chart(long).mark_line(opacity=0.85).encode(
        x=alt.X("time:T", title=None, axis=alt.Axis(format=common.DATE_FORMAT[how], labelOverlap=True, **how_ticks)),
        y=alt.Y("sentiment_mean:Q", title="Sentiment Score (เฉลี่ยของชั่วโมง)", axis=alt.Axis(format="+.2f")),
        color=alt.Color("model:N", scale=alt.Scale(domain=[n for n, _ in visible], range=[c for _, c in visible]), legend=None))
    hover = alt.Chart(long).mark_circle(size=150, opacity=0).encode(
        x="time:T", y="sentiment_mean:Q", color=alt.Color("model:N", scale=alt.Scale(domain=[n for n, _ in visible], range=[c for _, c in visible]), legend=None),
        tooltip=[alt.Tooltip("time:T", title=common.PERIOD_LABEL[how], format=common.DATE_TIP[how]), alt.Tooltip("model:N", title="แบบจำลอง"), alt.Tooltip("sentiment_mean:Q", title="Sentiment Score", format="+.3f")])
    common.show((lines + hover + common.zero_rule()).properties(height=common.CHART_HEIGHT), width="stretch")
    both = by_model["VADER"].merge(by_model["FinBERT"], on="time", suffixes=("_v", "_f")).dropna()
    agree = "n/a" if len(both) < 3 else "{:+.2f}".format(both.sentiment_mean_v.corr(both.sentiment_mean_f))

st.subheader("ราคาปิดเทียบค่าความรู้สึกเฉลี่ย (%s)" % label)
price_col = "close"
if shown.sentiment_mean.notna().sum() == 0:
    st.info("ไม่มีข้อความที่พูดถึง %s ในช่วงนี้ จึงแสดงเฉพาะราคา" % label)
    common.show(common.line(shown, "time", price_col, "ราคาปิด (USD)" if one else "ราคาปิด (เฉลี่ยของที่เลือก)",
                                bar=common.kind(st, "s_close")), width="stretch")
else:
    price_title = "ราคาปิด (USD)" if one else "ราคาปิด (เฉลี่ยของที่เลือก)"
    common.dual_chart(shown, "time", price_col, "sentiment_mean", price_title, "Sentiment Score", "s_price_sent", "ราคาปิด", "Sentiment Score")

    st.subheader("Reddit Volume เทียบค่าความรู้สึกเฉลี่ย (%s)" % label)
    common.dual_chart(shown, "time", "reddit_volume", "sentiment_mean", "Reddit Volume (จำนวนข้อความ)", "Sentiment Score", "s_z_sent",
                      "Reddit Volume", "Sentiment Score", left_color=common.C_REDDIT, left_fmt=",.0f")

# ---- does higher sentiment go with a higher return?  every ticked ticker-hour with text is one sample
st.subheader("ความสัมพันธ์ระหว่างระดับความรู้สึกกับผลตอบแทน")
MEASURES = {"Current Return (ชั่วโมงเดียวกัน)": "log_return", **{"ผลตอบแทนล่วงหน้า %s" % h: "future_return_" + h for h in common.data.HORIZONS}}
st.session_state.setdefault("s_bar_measure", list(MEASURES)[0])        # default: Current Return
picked = st.radio("วัดผลตอบแทนแบบ", list(MEASURES), horizontal=True, key="s_bar_measure", label_visibility="collapsed")
column = MEASURES[picked]
returns = prices[["ticker", "hour_utc", "log_return", *["future_return_" + h for h in common.data.HORIZONS]]]
samples = per_ticker_kept.rename(columns={"series": "ticker"})[["ticker", "hour_utc", "sentiment_mean", "majority"]].merge(
    returns, on=["ticker", "hour_utc"])
samples = samples[samples.majority.isin(statuses)]
buckets = data.sentiment_buckets(samples, column)
if buckets.empty:
    st.info("ตัวอย่างน้อยเกินไปสำหรับแบ่งกลุ่มความรู้สึก (ต้องมีอย่างน้อย 50 ticker-hourที่มีทั้งข้อความและผลตอบแทน)")
else:
    levels = data.SENTIMENT_LEVELS
    buckets["ระดับความรู้สึก"] = [levels[int(b)][0] for b in buckets.bucket]
    buckets["ช่วงความรู้สึก"] = ["Sentiment Score " + levels[int(b)][1] for b in buckets.bucket]
    buckets["ป้าย"] = ["%s (%s)\nn = %s" % (*levels[int(b)], "{:,}".format(int(n))) for b, n in zip(buckets.bucket, buckets.n)]
    order = list(buckets["ป้าย"])
    base = alt.Chart(buckets).encode(x=alt.X("ป้าย:N", sort=order, axis=alt.Axis(labelAngle=0, labelLimit=200), title="ระดับความรู้สึก (ช่วง Sentiment Score ของแต่ละกลุ่ม)"))
    bars = base.mark_bar(color=common.C_PRICE).encode(
        y=alt.Y("mean:Q", title="ผลตอบแทนเฉลี่ย (%)"),
        tooltip=["ระดับความรู้สึก", "ช่วงความรู้สึก", alt.Tooltip("n:Q", title="จำนวนตัวอย่าง", format=","),
                 alt.Tooltip("sent_mean:Q", title="Sentiment Score เฉลี่ย", format="+.3f"), alt.Tooltip("mean:Q", title="ผลตอบแทนเฉลี่ย (%)", format=".4f"), alt.Tooltip("ci_lo:Q", title="ช่วงเชื่อมั่น 95% ล่าง", format=".4f"),
                 alt.Tooltip("ci_hi:Q", title="ช่วงเชื่อมั่น 95% บน", format=".4f")])
    errors = base.mark_rule(color="#222222", strokeWidth=2).encode(y="ci_lo:Q", y2="ci_hi:Q")
    zero = common.zero_rule()
    common.show(bars + errors + zero, width="stretch")
    paired = samples[["sentiment_mean", column]].dropna()

st.subheader("สัดส่วนความคิดเห็นเชิงบวก ลบ และเป็นกลาง")
RATIO_MODES = ("ความคิดเห็นจริง (สัดส่วนข้อความ)", "ผลโหวตส่วนใหญ่ (สัดส่วนชั่วโมง)")
mode = st.radio("นับสัดส่วนจาก", RATIO_MODES, horizontal=True, key="s_ratio_mode", label_visibility="collapsed")
COLORS = alt.Scale(domain=["บวก", "ลบ", "เป็นกลาง"], range=["#2ca02c", "#d62728", "#7f7f7f"])
if mode == RATIO_MODES[0]:
    ratios = shown.melt(id_vars="time", value_vars=["pos_ratio", "neg_ratio", "neu_ratio"], var_name="ประเภท",
                        value_name="สัดส่วน").dropna()
    ratios["ประเภท"] = ratios["ประเภท"].map({"pos_ratio": "บวก", "neg_ratio": "ลบ", "neu_ratio": "เป็นกลาง"})
    caption = ("สัดส่วนของข้อความบวก ลบ และเป็นกลางในชั่วโมงที่ผ่านตัวกรอง (ค่าจริงของ pos_ratio, neg_ratio และ neu_ratio)  \n"
               "ชั่วโมงที่ส่วนใหญ่เป็นประเภทที่ยกเลิกการเลือกจะไม่ถูกนับ แต่ชั่วโมงที่เหลือยังมีข้อความประเภทนั้นปนอยู่")
else:
    votes = data.vote_shares(series, None if how == "Hourly" else common.RESAMPLE[how])
    ratios = votes.rename(columns={"share": "สัดส่วน"}).assign(ประเภท=lambda d: d.status.map(
        {"positive": "บวก", "negative": "ลบ", "neutral": "เป็นกลาง"}))
    caption = ("สัดส่วนของ**ชั่วโมง**ที่ผลโหวตส่วนใหญ่เป็นบวก ลบ หรือเป็นกลาง (1 ชั่วโมงนับเป็น 1 โหวต)  \n"
               "ประเภทที่ยกเลิกการเลือกจะเป็น 0 ทั้งหมด")
if not ratios.empty:
    area = (alt.Chart(ratios).mark_area().encode(
        x=alt.X("time:T", title=None), y=alt.Y("สัดส่วน:Q", stack="normalize", axis=alt.Axis(format="%")),
        color=alt.Color("ประเภท:N", scale=COLORS), tooltip=["time:T", "ประเภท", alt.Tooltip("สัดส่วน:Q", format=".1%")])
        .properties(height=common.CHART_HEIGHT))
    common.show(area, width="stretch")
    st.caption(caption)

# ---- which asset is the most positive / negative?  (management question 2 of 7.3): one row per ticked ticker
st.subheader("สินทรัพย์ใดมีความรู้สึกเป็นบวกหรือลบมากที่สุด")
if one:
    st.info("เลือกหลักทรัพย์ตัวเดียว จึงไม่มีอะไรให้เรียงอันดับ เลือกหลายตัวเพื่อเทียบกัน")
else:
    passes = data.threshold_mask(per_ticker, z_th, 0.0, v_min=v_th) & per_ticker.majority.isin(statuses)      # the hours that pass the Reddit Volume Threshold and the majority filter
    has_text = per_ticker[passes].dropna(subset=["sentiment_mean"])
    weight = has_text.texts
    ranked = has_text.assign(
        s=has_text.sentiment_mean * weight, p=has_text.pos_ratio * weight, n=has_text.neg_ratio * weight, w=weight
    ).groupby("series", as_index=False)[["s", "p", "n", "w"]].sum()
    ranked = ranked[ranked.w > 0].assign(sentiment=lambda d: d.s / d.w, pos=lambda d: 100 * d.p / d.w, neg=lambda d: 100 * d.n / d.w)
    ranked = ranked.sort_values("sentiment", ascending=False)
    if ranked.empty:
        st.info("ไม่มีสินทรัพย์ที่มีข้อความในช่วงนี้")
    else:
        groups = dict(zip(q("tickers").ticker, q("tickers").big_group))
        ranked["กลุ่ม"] = ranked.series.map(lambda s: GROUP_LABELS.get(groups.get(s), ""))
        ranked.insert(0, "อันดับ", range(1, len(ranked) + 1))
        common.table(ranked[["อันดับ", "series", "กลุ่ม", "w", "sentiment", "pos", "neg"]].rename(columns={
            "series": "สินทรัพย์", "w": "จำนวนข้อความ", "sentiment": "Sentiment Score เฉลี่ย", "pos": "เชิงบวก (%)",
            "neg": "เชิงลบ (%)"}).round(3), hide_index=True, width="stretch", height=min(420, 60 + 36 * len(ranked)))

# ---- DimDetectionConfig drill-down: the hours that meet the thresholds of the sidebar, and what the price did next
