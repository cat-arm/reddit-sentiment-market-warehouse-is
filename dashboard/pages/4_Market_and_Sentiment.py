"""Dashboard 7.5-1  Market and Sentiment Overview  (proposal 7.5: close, volume, sentiment_mean, pos/neg/neu ratio,
majority status, Reddit_volume, Volume Z-score, Sentiment Momentum).

Dimensions of the dashboard (table 17): DimTime, DimTicker, DimSentimentSource, DimDetectionConfig, DimMajoritySentiment.  They are the
four blocks of the sidebar: time range and level; asset classes and tickers (several tickers are taken together);
communities of the sentiment source (the model is always VADER+FinBERT); majority status of the hour.
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

common.setup("Market and Sentiment: ภาพรวมตลาดและความรู้สึก", "🧭")
_, start, end, _ = common.sidebar(multi=True, sentiment=True, detection="overview", majority=True)
how = common.granularity(start, end, "g_sent")
tickers = common.selected_tickers()
communities = common.selected_communities()
statuses = common.selected_statuses()
z_th = st.session_state.get("d_z", 0.0)                 # DimDetectionConfig: filters the hours (0 = no filter)
s_th = st.session_state.get("d_s", 0.0)
if not tickers or not communities or not statuses:
    common.nothing_selected(["Sentiment Score", "Sentiment Momentum", "Reddit Volume Z-score สูงสุด"],
                            "ไม่ได้เลือกหลักทรัพย์ ชุมชน หรือประเภทความรู้สึกส่วนใหญ่ จึงไม่มีข้อมูลแสดง")
one = len(tickers) == 1
names = dict(zip(q("tickers").ticker, q("tickers").name))
label = tickers[0] if one else "รวม %d ตัว" % len(tickers)

# ---- prices of the ticked tickers (hours with a valid bar) and the sentiment KPIs recombined from the chosen communities
prices = q("price_series_for", tickers, start, end)
sent = q("sentiment_hourly", tickers, start, end, communities, common.selected_model())
if prices.empty:
    st.info("ไม่มีข้อมูลราคาของหลักทรัพย์ที่เลือกในช่วงนี้ (ตลาดอาจปิด)")
    st.stop()
per_ticker = data.sentiment_frame(sent, start, end)                       # one series per ticker
# the same filter on every ticker-hour: an hour that fails the thresholds loses its majority status, so the samples below skip it
per_ticker_kept = per_ticker.assign(majority=per_ticker.majority.where(data.threshold_mask(per_ticker, z_th, s_th)))
series_frame = data.sentiment_frame(sent, start, end, combined=not one)   # what the charts show


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
series = series.rename(columns={"texts": "reddit_volume", "majority": "majority_final_status"})

# hours whose majority status is not ticked lose every Reddit measure (price and market volume stay); no text = NULL
series = data.mask_majority(series, statuses)
# hours that do not meet the thresholds of DimDetectionConfig lose their Reddit measures too (0 / 0 = nothing removed)
series = data.mask_thresholds(series, z_th, s_th)


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
        "close": "last", "volume": "sum" if one else "mean", "reddit_volume": "sum", "zscore": "max", "momentum": "mean",
        **{c + "_w": "sum" for c in ("sentiment_mean", "pos_ratio", "neg_ratio", "neu_ratio")}, "texts_w": "sum"})
    for col in ("sentiment_mean", "pos_ratio", "neg_ratio", "neu_ratio"):
        daily[col] = (daily[col + "_w"] / daily["texts_w"]).where(daily["texts_w"] > 0)   # no text -> NULL, not 0
    return daily.reset_index()


shown = weighted_resample(series, how)

# KPI cards first: the three KPIs of dashboard 1 (tables 15 and 17): Sentiment Score, Sentiment Momentum, Reddit Volume Z-score
w = series.reddit_volume.where(series.sentiment_mean.notna())
common.kpi_cards([
    ("Sentiment Score", "n/a" if not w.sum() else "{:+.3f}".format((series.sentiment_mean * w).sum() / w.sum()),
     "ผลรวม final_sentiment ÷ จำนวนความคิดเห็น เฉลี่ยถ่วงน้ำหนักด้วยจำนวนข้อความของแต่ละชั่วโมง"),
    ("Sentiment Momentum", common.money(series.momentum.mean()), "(sentiment_mean ชั่วโมงนี้ − ชั่วโมงก่อนหน้า) เฉลี่ย"),
    ("Reddit Volume Z-score สูงสุด", common.money(series.zscore.max()), "เทียบ 24 ชั่วโมงก่อนหน้า ไม่รวมชั่วโมงปัจจุบัน")])

st.subheader("%s: ราคาปิดเทียบค่าความรู้สึกเฉลี่ย" % label)
price_col = "close"
if shown.sentiment_mean.notna().sum() == 0:
    st.info("ไม่มีข้อความที่พูดถึง %s ในช่วงนี้ จึงแสดงเฉพาะราคา" % label)
    common.show(common.line(shown, "time", price_col, "ราคาปิด (USD)" if one else "ราคาปิด ดัชนี (ค่าแรก = 100)",
                                bar=common.kind(st, "s_close")), width="stretch")
else:
    price_title = "ราคาปิด (USD)" if one else "ราคาปิด ดัชนี (ค่าแรก = 100)"
    common.dual_chart(shown, "time", price_col, "sentiment_mean", price_title, "Sentiment Score", "s_price_sent", "ราคาปิด", "Sentiment Score")
    st.caption("สีน้ำเงิน = ราคาปิด  \nสีเขียวอมฟ้า = Sentiment Score (ผลรวม final_sentiment ÷ จำนวนข้อความของชั่วโมงนั้น) "
               "ช่วงที่สีเขียวอมฟ้าขาด = ไม่มีข้อความ ไม่ใช่ค่ากลาง")

    st.subheader("%s: Reddit Volume Z-score เทียบค่าความรู้สึกเฉลี่ย" % label)
    common.dual_chart(shown, "time", "zscore", "sentiment_mean", "Reddit Volume Z-score", "Sentiment Score", "s_z_sent",
                      "Reddit Volume Z-score", "Sentiment Score", left_color=common.C_Z, left_fmt=".2f")
    st.caption("สีแดง = Reddit Volume Z-score (ปริมาณข้อความเทียบ 24 ชั่วโมงก่อนหน้า)  \nสีเขียวอมฟ้า = Sentiment Score  "
               "ถ้าคนพูดถึงมากผิดปกติแล้วความรู้สึกเปลี่ยน สองสีจะขยับไปด้วยกันหรือสวนกัน")

    st.subheader("%s: ราคาปิดเทียบ Reddit Volume Z-score" % label)
    common.dual_chart(shown, "time", price_col, "zscore", price_title, "Reddit Volume Z-score", "s_price_z", "ราคาปิด",
                      "Reddit Volume Z-score", right_color=common.C_Z, right_fmt=".2f")
    st.caption("สีน้ำเงิน = ราคาปิด  \nสีแดง = Reddit Volume Z-score  ช่วงที่ปริมาณพุ่ง (สีแดงสูง) ราคาขยับตามหรือไม่")

# ---- does higher sentiment go with a higher return?  every ticked ticker-hour with text is one sample
st.subheader("ความรู้สึกยิ่งสูง ผลตอบแทนยิ่งสูงไหม")
MEASURES = {"Current Return (ชั่วโมงเดียวกัน)": "log_return", **{"ผลตอบแทนล่วงหน้า %s" % h: "future_return_" + h for h in common.data.HORIZONS}}
st.session_state.setdefault("s_bar_measure", "ผลตอบแทนล่วงหน้า " + common.data.HORIZONS[0])
picked = st.radio("วัดผลตอบแทนแบบ", list(MEASURES), horizontal=True, key="s_bar_measure", label_visibility="collapsed")
column = MEASURES[picked]
returns = prices[["ticker", "hour_utc", "log_return", *["future_return_" + h for h in common.data.HORIZONS]]]
samples = per_ticker_kept.rename(columns={"series": "ticker"})[["ticker", "hour_utc", "sentiment_mean", "majority"]].merge(
    returns, on=["ticker", "hour_utc"])
samples = samples[samples.majority.isin(statuses)]
buckets = data.sentiment_buckets(samples, column)
if buckets.empty:
    st.info("ตัวอย่างน้อยเกินไปสำหรับแบ่งกลุ่มความรู้สึก (ต้องมีอย่างน้อย 50 ticker-ชั่วโมงที่มีทั้งข้อความและผลตอบแทน)")
else:
    levels = data.SENTIMENT_LEVELS
    buckets["ระดับความรู้สึก"] = [levels[int(b)][0] for b in buckets.bucket]
    buckets["ช่วงความรู้สึก"] = ["Sentiment Score " + levels[int(b)][1] for b in buckets.bucket]
    buckets["ป้าย"] = ["%s (%s)" % levels[int(b)] for b in buckets.bucket]
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
    st.caption("วิธีอ่าน: เอาทุก ticker-ชั่วโมงที่มีข้อความ มาใส่ 5 ระดับตาม Sentiment Score ของชั่วโมงนั้น โดยใช้เกณฑ์ตายตัวของ proposal: ±0.05 = ขอบเป็นกลาง, ±0.30 = เกณฑ์ความรู้สึกชัดเจน  \n"
               "แท่ง = ผลตอบแทนเฉลี่ยของระดับนั้น (ระดับที่ไม่มีข้อมูลจะไม่มีแท่ง) เส้นดำ = ช่วงเชื่อมั่น 95%% ถ้าเส้นคลุมศูนย์ แปลว่าแยกจากศูนย์ไม่ได้  \n"
               "Spearman ρ ระหว่างความรู้สึกกับผลตอบแทน = %+.3f (%s ticker-ชั่วโมง)  \n"
               "ใช้ผลตอบแทนแทนระดับราคา เพราะระดับราคาขึ้นลงตามแนวโน้มระยะยาว เทียบกับความรู้สึกตรงๆ จะหลอกตา"
               % (paired.sentiment_mean.corr(paired[column], method="spearman"), "{:,}".format(len(paired))))

st.subheader("สัดส่วนความคิดเห็นเชิงบวก / ลบ / เป็นกลาง")
RATIO_MODES = ("ความคิดเห็นจริง (สัดส่วนข้อความ)", "ผลโหวตส่วนใหญ่ (สัดส่วนชั่วโมง)")
mode = st.radio("นับสัดส่วนจาก", RATIO_MODES, horizontal=True, key="s_ratio_mode", label_visibility="collapsed")
COLORS = alt.Scale(domain=["บวก", "ลบ", "เป็นกลาง"], range=["#2ca02c", "#d62728", "#7f7f7f"])
if mode == RATIO_MODES[0]:
    ratios = shown.melt(id_vars="time", value_vars=["pos_ratio", "neg_ratio", "neu_ratio"], var_name="ประเภท",
                        value_name="สัดส่วน").dropna()
    ratios["ประเภท"] = ratios["ประเภท"].map({"pos_ratio": "บวก", "neg_ratio": "ลบ", "neu_ratio": "เป็นกลาง"})
    caption = ("สัดส่วนของข้อความ บวก / ลบ / เป็นกลาง ภายในชั่วโมงที่ผ่านตัวกรอง (ค่าจริงของ pos_ratio, neg_ratio, neu_ratio) "
               "ชั่วโมงที่ส่วนใหญ่เป็นประเภทที่ติ๊กออกไม่ถูกนับ แต่ชั่วโมงที่เหลือยังมีข้อความประเภทนั้นปนอยู่")
else:
    votes = data.vote_shares(series, None if how == "Hourly" else common.RESAMPLE[how])
    ratios = votes.rename(columns={"share": "สัดส่วน"}).assign(ประเภท=lambda d: d.status.map(
        {"positive": "บวก", "negative": "ลบ", "neutral": "เป็นกลาง"}))
    caption = ("สัดส่วนของ**ชั่วโมง**ที่ผลโหวตส่วนใหญ่เป็น บวก / ลบ / เป็นกลาง (นับ 1 ชั่วโมง = 1 โหวต) "
               "ประเภทที่ติ๊กออกจะเป็น 0 ทั้งหมด")
if not ratios.empty:
    area = (alt.Chart(ratios).mark_area().encode(
        x=alt.X("time:T", title=None), y=alt.Y("สัดส่วน:Q", stack="normalize", axis=alt.Axis(format="%")),
        color=alt.Color("ประเภท:N", scale=COLORS), tooltip=["time:T", "ประเภท", alt.Tooltip("สัดส่วน:Q", format=".1%")])
        .properties(height=common.CHART_HEIGHT))
    common.show(area, width="stretch")
    st.caption(caption)

# ---- DimDetectionConfig drill-down: the hours that meet the thresholds of the sidebar, and what the price did next
rule_text = ("ทุกชั่วโมงที่มีข้อความ (เกณฑ์ Z-score และ Sentiment เป็น 0 = ไม่กรอง)" if not (z_th or s_th) else
             "Z-score > %.1f และ |Sentiment| ≥ %.2f" % (z_th, s_th) if z_th and s_th else
             "Z-score > %.1f" % z_th if z_th else "|Sentiment| ≥ %.2f" % s_th)
# the Horizon belongs to this chart only (the sidebar filters apply to the whole page)
st.session_state.setdefault("s_drill_h", common.data.HORIZONS[0])
st.subheader("ชั่วโมงที่เข้าเงื่อนไขตรวจจับ (%s) ราคาเป็นอย่างไรต่อ %s" % (rule_text, st.session_state["s_drill_h"]))
horizon = st.radio("Horizon (ดูผลตอบแทนล่วงหน้ากี่ชั่วโมง)", list(common.data.HORIZONS), horizontal=True, key="s_drill_h")
hours = per_ticker.rename(columns={"series": "ticker"})[["ticker", "hour_utc", "texts", "sentiment_mean", "zscore", "majority"]]
hours = hours[hours.majority.isin(statuses)].merge(prices[["ticker", "hour_utc", "future_return_" + horizon]], on=["ticker", "hour_utc"])
col = "future_return_" + horizon
hit = data.signal_hours(hours, z_th, s_th)
if hit.empty:
    st.info("ไม่พบชั่วโมงที่เข้าเงื่อนไขในช่วงที่เลือก ลองลดเกณฑ์ Z-score หรือ Sentiment Threshold ที่แถบด้านซ้าย")
else:
    rs = data.return_by_signal(hours, col, z_th, s_th)
    rs["กลุ่ม"] = rs.group.map({"signal_positive": "สัญญาณบวก", "signal_negative": "สัญญาณลบ", "all_hours": "ทุกชั่วโมงที่มีข้อความ (เทียบ)"})
    rs["ป้าย"] = ["%s (n=%s)" % (g, "{:,}".format(n)) for g, n in zip(rs["กลุ่ม"], rs.n)]
    base = alt.Chart(rs).encode(x=alt.X("ป้าย:N", sort=list(rs["ป้าย"]), axis=alt.Axis(labelAngle=0, labelLimit=240),
                                        title="ชนิดของชั่วโมง (n = จำนวน ticker-ชั่วโมงที่มีผลตอบแทน %s)" % horizon))
    bars = base.mark_bar(color=common.C_PRICE).encode(
        y=alt.Y("mean:Q", title="ผลตอบแทนล่วงหน้า %s เฉลี่ย (%%)" % horizon),
        tooltip=["กลุ่ม", alt.Tooltip("n:Q", title="จำนวนตัวอย่าง", format=","), alt.Tooltip("mean:Q", title="ผลตอบแทนเฉลี่ย (%)", format="+.4f"),
                 alt.Tooltip("ci_lo:Q", title="ช่วงเชื่อมั่น 95% ล่าง", format="+.4f"), alt.Tooltip("ci_hi:Q", title="ช่วงเชื่อมั่น 95% บน", format="+.4f")])
    errors = base.mark_rule(color="#222222", strokeWidth=2).encode(y="ci_lo:Q", y2="ci_hi:Q")
    zero = common.zero_rule()
    common.show(bars + errors + zero, width="stretch")
    st.caption("พบ %s ticker-ชั่วโมงที่ Reddit คึกคักผิดปกติ (Z-score เกินเกณฑ์) และความรู้สึกชัดเจน (|Sentiment Score| ถึงเกณฑ์)  \n"
               "เส้นดำ = ช่วงเชื่อมั่น 95%% ถ้าคร่อมศูนย์ แปลว่าแยกจากไม่มีการขยับไม่ได้ เทียบกับแท่งขวาสุดที่เป็นค่าเฉลี่ยของทุกชั่วโมง"
               % "{:,}".format(len(hit)))
    listing = hit.sort_values("hour_utc", ascending=False).head(300).copy()
    listing["เวลา (UTC)"] = pd.to_datetime(listing.hour_utc, unit="s", utc=True).dt.strftime("%Y-%m-%d %H:%M")
    listing["สินทรัพย์"] = listing.ticker.map(lambda s: "%s · %s" % (s, names.get(s, "")))
    common.table(listing[["เวลา (UTC)", "สินทรัพย์", "direction", "sentiment_mean", "texts", "zscore", col]].rename(
        columns={"direction": "ทิศทาง", "sentiment_mean": "Sentiment Score", "texts": "ข้อความ", "zscore": "Volume Z-score",
                 col: "ผลตอบแทนล่วงหน้า %s (%%)" % horizon}).round(3), hide_index=True, width="stretch", height=380)
    st.caption("รายการล่าสุดไม่เกิน 300 ชั่วโมง ผลตอบแทนว่าง = ไม่มีแท่งราคาที่ครบ %s หลังชั่วโมงนั้น" % horizon)
